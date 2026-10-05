#!/usr/bin/env python3
"""Run the actual pinned ShinkaEvolve engine under a resumable wall-clock budget."""
from __future__ import annotations

import argparse
import atexit
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shlex
import signal
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.shinka_bridge import (  # noqa: E402
    MODEL, EFFORT, SERVICE_TIER, UPSTREAM_REVISION, check_subscription,
    subscription_environment,
)


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True))
    temporary.replace(path)


# The evaluator atomically updates these fields as ecological selection proceeds.
# Everything else in the context is an immutable experimental input.
MUTABLE_CONTEXT_FIELDS = frozenset({
    "institutions", "members", "evaluations", "accepted_member_updates",
    "accepted_institution_updates", "updated_utc",
})


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def input_contract(args) -> dict:
    """Hash immutable inputs, excluding the evaluator's mutable lineage state."""
    paths = {key: str(Path(getattr(args, key)).resolve()) for key in
             ("context", "initial_program", "task_prompt", "evaluator")}
    for value in paths.values():
        if not Path(value).is_file():
            raise RuntimeError(f"Required input missing: {value}")
    context = json.loads(Path(paths["context"]).read_text())
    for name, expected in context.get("frozen_source_hashes", {}).items():
        source = Path(name)
        source = source if source.is_absolute() else ROOT / source
        if file_sha256(source) != expected:
            raise RuntimeError(f"Frozen evaluator dependency changed: {source}")
    immutable = {key: value for key, value in context.items()
                 if key not in MUTABLE_CONTEXT_FIELDS}
    source_hashes = {}

    def collect_initial_sources(value):
        if isinstance(value, dict):
            for item in value.values():
                collect_initial_sources(item)
        elif isinstance(value, list):
            for item in value:
                collect_initial_sources(item)
        elif isinstance(value, str) and value.endswith(".py"):
            source = Path(value)
            if not source.is_absolute():
                source = ROOT / source
            source_hashes[str(source.resolve())] = file_sha256(source)

    for key, value in immutable.items():
        if key.startswith("initial_"):
            collect_initial_sources(value)
    return {
        "paths": paths,
        "critical_input_sha256": {
            **{key: file_sha256(Path(paths[key])) for key in
               ("initial_program", "task_prompt", "evaluator")},
            "context_immutable": canonical_sha256(immutable),
        },
        "initial_population_source_sha256": source_hashes,
    }


def freeze_run_plan(args, previous: dict, budget: float) -> dict:
    """A resume cannot grow its allowance or silently change experiment inputs."""
    plan_path = args.run_dir / "run_plan.json"
    contract = input_contract(args)
    immutable_plan = {
        "schema_version": 1, "budget_seconds": budget,
        "max_generations": args.max_generations, "search_seed": args.search_seed,
        "route": {"model": MODEL, "reasoning_effort": EFFORT,
                  "service_tier": SERVICE_TIER, "shinka_revision": UPSTREAM_REVISION},
        **contract,
    }
    if plan_path.exists():
        recorded = json.loads(plan_path.read_text())
        if recorded.get("immutable_plan") != immutable_plan:
            raise RuntimeError("Run plan/input mismatch on resume; budget, seed and critical inputs are immutable")
        if recorded.get("plan_sha256") != canonical_sha256(immutable_plan):
            raise RuntimeError("Stored run-plan digest is inconsistent")
        return recorded
    if previous:
        raise RuntimeError("Unfinished legacy run has no frozen input manifest; inspect it before migrating")
    recorded = {
        "immutable_plan": immutable_plan,
        "plan_sha256": canonical_sha256(immutable_plan),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "initial_context_sha256": file_sha256(args.context),
        "context_hash_note": "Only immutable context fields gate resume; full terminal context hashes are audit-only",
    }
    frozen_dir = args.run_dir / "frozen_inputs"
    frozen_dir.mkdir(exist_ok=True)
    for key in ("context", "initial_program", "task_prompt", "evaluator"):
        source = Path(contract["paths"][key])
        (frozen_dir / f"{key}{source.suffix}").write_bytes(source.read_bytes())
    atomic_json(plan_path, recorded)
    return recorded


def worker_command(args) -> list[str]:
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--run-dir", str(args.run_dir), "--context", str(args.context),
               "--initial-program", str(args.initial_program),
               "--task-prompt", str(args.task_prompt), "--evaluator", str(args.evaluator),
               "--max-generations", str(args.max_generations)]
    if args.search_seed is not None:
        command.extend(["--search-seed", str(args.search_seed)])
    return command


def terminate_worker_group(process) -> None:
    """Also reap model descendants if the engine exits unexpectedly."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        process.wait(timeout=10)


def database_progress(directory: Path) -> dict:
    path = directory / "programs.sqlite"
    if not path.exists():
        return {"evaluated_candidates": 0, "valid_candidates": 0, "invalid_candidates": 0}
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as db:
            total, valid = db.execute("SELECT COUNT(*), SUM(correct) FROM programs").fetchone()
            return {"evaluated_candidates": total, "valid_candidates": valid or 0,
                    "invalid_candidates": total - (valid or 0)}
    except sqlite3.Error as exc:
        return {"database_progress_error": str(exc)}


def run_worker(args) -> int:
    # Native ShinkaEvolve Headless provider invokes this audited protocol adapter.
    os.environ["SHINKA_HEADLESS_COMMAND"] = shlex.join([
        sys.executable, str(ROOT / "swarm_societies/shinka_bridge.py")
    ])
    os.environ["SHINKA_HEADLESS_TIMEOUT"] = "930"
    os.environ["SWARM_CODEX_TIMEOUT"] = "900"
    os.environ["PYTHONPATH"] = str(ROOT)
    for name in list(os.environ):
        if name.endswith("API_KEY"):
            del os.environ[name]
    from shinka.core import EvolutionConfig, ShinkaEvolveRunner
    from shinka.database import DatabaseConfig
    from shinka.launch import LocalJobConfig
    if args.search_seed is not None:
        import numpy as np
        random.seed(args.search_seed)
        np.random.seed(args.search_seed)
    prompt = args.task_prompt.read_text()
    evo = EvolutionConfig(
        task_sys_msg=prompt, patch_types=["full", "diff"],
        patch_type_probs=[0.6, 0.4], num_generations=args.max_generations,
        max_patch_resamples=1, max_patch_attempts=1,
        job_type="local", language="python",
        llm_models=[f"headless/codex@{MODEL}?effort={EFFORT}"],
        llm_dynamic_selection="fixed", llm_kwargs={"temperatures": [0.0]},
        embedding_model=None, meta_rec_interval=None, meta_llm_models=None,
        novelty_llm_models=None, max_novelty_attempts=1,
        evolve_prompts=False, enable_wandb_logging=False,
        use_text_feedback=True, enable_controlled_oversubscription=False,
        init_program_path=str(args.initial_program), results_dir=str(args.run_dir),
    )
    jobs = LocalJobConfig(
        eval_program_path=str(args.evaluator),
        extra_cmd_args={"context": str(args.context)},
        # Upstream measures LocalJobConfig.time from proposal start, so it
        # includes the subscription inference (up to 900 s). The trusted
        # evaluator separately enforces 120 CPU seconds; the supervisor still
        # enforces the cumulative 3,600 s run limit.
        python_executable=sys.executable, time="00:20:00",
        numeric_threads_per_job=1,
    )
    db = DatabaseConfig(
        db_path=str(args.run_dir / "programs.sqlite"), num_islands=1,
        archive_size=8, num_archive_inspirations=1, num_top_k_inspirations=1,
        migration_rate=0.0, enable_dynamic_islands=False,
        parent_selection_strategy="weighted",
    )
    runner = ShinkaEvolveRunner(
        evo_config=evo, job_config=jobs, db_config=db,
        max_evaluation_jobs=1, max_proposal_jobs=1, max_db_workers=1,
        verbose=True,
    )
    runner.run()
    return 0


def supervise(args) -> int:
    import fcntl
    args.run_dir.mkdir(parents=True, exist_ok=True)
    # Filesystem locks also work across container PID namespaces, unlike a
    # process-existence check alone. Keep the handle live for this invocation.
    with (args.run_dir / "supervisor.lock").open("a+") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A supervisor already owns this run directory")
        return _supervise_locked(args)


def _supervise_locked(args) -> int:
    import psutil
    checkpoint_path = args.run_dir / "budget_checkpoint.json"
    if checkpoint_path.exists() and not args.resume:
        raise RuntimeError("Run already exists; use --resume to retain the cumulative budget")
    previous = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    if previous.get("status") == "running":
        old_pid = previous.get("supervisor_pid", -1)
        try:
            if abs(psutil.Process(old_pid).create_time() - previous.get("supervisor_create_time", 0)) < 1:
                raise RuntimeError(f"Supervisor {old_pid} is still running")
        except psutil.NoSuchProcess:
            pass
    spent = float(previous.get("elapsed_search_seconds", 0))
    # Charge the last heartbeat interval conservatively after an ungraceful crash.
    if previous.get("status") == "running":
        spent += 10
    budget = args.budget_minutes * 60
    if not math.isfinite(budget) or budget <= 0:
        raise RuntimeError("Budget must be finite and positive")
    if previous and float(previous.get("budget_seconds", budget)) != budget:
        raise RuntimeError("Resume cannot change the original search budget")
    if spent >= budget:
        if (args.run_dir / "run_plan.json").exists():
            freeze_run_plan(args, previous, budget)
        print(json.dumps({"status": "budget_exhausted", "elapsed_search_seconds": spent}))
        return 0
    plan = freeze_run_plan(args, previous, budget)
    settings = check_subscription()
    settings.update({
        "shinka_revision": UPSTREAM_REVISION, "embedding_model": None,
        "meta_rec_interval": None, "novelty_llm_models": None,
        "evolve_prompts": False, "search_islands": 1, "archive_size": 8,
        "evaluation_concurrency": 1, "proposal_concurrency": 1,
        "scheduler_pipeline_timeout_seconds": 1200,
        "max_generations": args.max_generations, "budget_seconds": budget,
        "initial_program": str(args.initial_program), "context": str(args.context),
        "task_prompt": str(args.task_prompt), "evaluator": str(args.evaluator),
        "run_plan_sha256": plan["plan_sha256"],
        "critical_input_sha256": plan["immutable_plan"]["critical_input_sha256"],
        "service_tier_note": "Preserved from local Codex config; subscription usage, no paid API calls",
        "shinka_temperature_request": 0.0,
        "effective_inference_temperature": "not exposed or forwarded by Codex CLI",
        "search_rng_seed": args.search_seed,
        "search_rng_note": (
            "Python/NumPy seeded at each worker startup; inference remains stochastic; resume restarts these RNG streams"
            if args.search_seed is not None else
            "Unseeded upstream Python/NumPy defaults; proposal trajectory is not deterministic"
        ),
        "resume_note": "Ecological/database/budget checkpoints resume; future stochastic proposal trajectory is not guaranteed identical",
    })
    atomic_json(args.run_dir / "actual_settings.json", settings)
    command = worker_command(args)
    started = time.monotonic()
    interrupted = False

    def handle_signal(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    status = "running"
    peak_rss = int(previous.get("peak_process_tree_rss_bytes", 0))
    peak_cpu = float(previous.get("observed_process_tree_cpu_seconds", 0))
    with (args.run_dir / "engine_console.log").open("a", buffering=1) as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=subscription_environment(), start_new_session=True)
        # Normal terminal paths unregister this hook. It also cleans up if an
        # unexpected supervisor exception reaches main() and exits the process.
        atexit.register(terminate_worker_group, process)
        next_output = 0.0
        while True:
            elapsed = spent + time.monotonic() - started
            returncode = process.poll()
            if returncode is not None:
                status = "completed" if returncode == 0 else "failed"
            elif interrupted:
                status = "interrupted"
            elif elapsed >= budget:
                status = "budget_exhausted"
            try:
                leader = psutil.Process(process.pid)
                tree = [leader, *leader.children(recursive=True)]
                rss, cpu = 0, 0.0
                for child in tree:
                    try:
                        rss += child.memory_info().rss
                        times = child.cpu_times()
                        cpu += times.user + times.system
                    except psutil.Error:
                        pass
                peak_rss = max(peak_rss, rss)
                peak_cpu = max(peak_cpu, cpu)
            except psutil.Error:
                pass
            checkpoint = {
                "status": status, "budget_seconds": budget,
                "elapsed_search_seconds": min(elapsed, budget),
                "remaining_search_seconds": max(0, budget - elapsed),
                "updated_utc": datetime.now(timezone.utc).isoformat(),
                "supervisor_pid": os.getpid(),
                "supervisor_create_time": psutil.Process().create_time(),
                "worker_pid": process.pid, "worker_returncode": returncode,
                "run_plan_sha256": plan["plan_sha256"],
                "peak_process_tree_rss_bytes": peak_rss,
                "observed_process_tree_cpu_seconds": peak_cpu,
                "cpu_measurement_note": "Peak sampled sum of live process CPU times; excludes exited children",
                **database_progress(args.run_dir),
            }
            atomic_json(checkpoint_path, checkpoint)
            if elapsed >= next_output or status != "running":
                print(json.dumps(checkpoint), flush=True)
                next_output = elapsed + 30
            if status != "running":
                # Strict cutoff: no in-flight request or evaluation may continue.
                terminate_worker_group(process)
                atexit.unregister(terminate_worker_group)
                checkpoint["worker_returncode"] = process.returncode
                checkpoint["terminal_context_sha256"] = file_sha256(args.context)
                atomic_json(checkpoint_path, checkpoint)
                return 1 if status == "failed" else 0
            time.sleep(min(1, max(0, budget - elapsed)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "runs/first")
    parser.add_argument("--context", type=Path)
    parser.add_argument("--initial-program", type=Path, default=ROOT / "seeds/initial.py")
    parser.add_argument("--task-prompt", type=Path, default=ROOT / "docs/evolution-prompt.md")
    parser.add_argument("--evaluator", type=Path, default=ROOT / "scripts/evaluate_candidate.py")
    parser.add_argument("--search-seed", type=int)
    parser.add_argument("--budget-minutes", type=float, default=60)
    parser.add_argument("--max-generations", type=int, default=100000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()
    args.context = (args.context or args.run_dir / "evolution_context.json").resolve()
    args.initial_program = args.initial_program.resolve()
    args.task_prompt = args.task_prompt.resolve()
    args.evaluator = args.evaluator.resolve()
    if not math.isfinite(args.budget_minutes) or args.budget_minutes <= 0:
        parser.error("Budget must be finite and positive")
    if args.max_generations <= 0:
        parser.error("max-generations must be positive")
    if args.search_seed is not None and not 0 <= args.search_seed < 2**32:
        parser.error("search-seed must be between 0 and 2**32 - 1")
    try:
        return run_worker(args) if args.worker else supervise(args)
    except Exception as exc:
        print(f"Evolution blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
