#!/usr/bin/env python3
"""Run a frozen, sequential consumption-study campaign through ShinkaEvolve.

Plan schema: {"schema_version": 1, "runs": [{"id", "condition", "replicate",
"run_dir", "context", "initial_program", "task_prompt", "evaluator",
"budget_minutes", "search_seed"}], "postprocess_command": [optional argv]}.
Paths in run specifications are relative to the plan's directory. Postprocessing
argv is passed directly, without a shell, with the repository as working directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_evolution import atomic_json, canonical_sha256, input_contract
from swarm_societies.shinka_bridge import subscription_environment

PATH_FIELDS = ("run_dir", "context", "initial_program", "task_prompt", "evaluator")
TERMINAL_RUN_STATUSES = {"budget_exhausted", "completed"}


def read_json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def load_plan(path: Path) -> dict:
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise RuntimeError("Campaign requires schema_version=1")
    if not isinstance(raw.get("runs"), list) or not raw["runs"]:
        raise RuntimeError("Campaign must contain at least one run")
    plan = {**raw, "runs": []}
    ids, directories, contexts = set(), set(), set()
    for entry in raw["runs"]:
        required = {"id", "condition", "replicate", "budget_minutes", "search_seed", *PATH_FIELDS}
        if not isinstance(entry, dict) or required - entry.keys():
            raise RuntimeError(f"Incomplete campaign run: {entry}")
        if not isinstance(entry["id"], str) or not entry["id"] or entry["id"] in ids:
            raise RuntimeError("Run ids must be nonempty and unique")
        if entry["condition"] not in {"coevolution", "fixed_institution"}:
            raise RuntimeError(f"Unknown condition: {entry['condition']}")
        if type(entry["replicate"]) is not int or entry["replicate"] < 0:
            raise RuntimeError("replicate must be a nonnegative integer")
        budget = float(entry["budget_minutes"])
        if not math.isfinite(budget) or budget <= 0:
            raise RuntimeError("Every budget must be finite and positive")
        if type(entry["search_seed"]) is not int or not 0 <= entry["search_seed"] < 2**32:
            raise RuntimeError("Every search seed must be an integer in [0, 2**32)")
        run = {**entry, "budget_minutes": budget}
        for key in PATH_FIELDS:
            value = Path(entry[key])
            run[key] = str((value if value.is_absolute() else path.parent / value).resolve())
        if run["run_dir"] in directories or run["context"] in contexts:
            raise RuntimeError("Every campaign run needs a distinct run directory and context")
        ids.add(run["id"]); directories.add(run["run_dir"]); contexts.add(run["context"])
        plan["runs"].append(run)
    command = plan.get("postprocess_command")
    if command is not None and (not isinstance(command, list) or not command
                               or any(not isinstance(v, str) or not v for v in command)):
        raise RuntimeError("postprocess_command must be a nonempty argv list")
    return plan


def run_arguments(run: dict) -> SimpleNamespace:
    return SimpleNamespace(**{key: Path(run[key]) for key in PATH_FIELDS},
                           budget_minutes=run["budget_minutes"],
                           max_generations=run.get("max_generations", 100000),
                           search_seed=run["search_seed"], resume=False)


def initialize_checkpoint(plan: dict, previous: dict | None) -> dict:
    digest = canonical_sha256(plan)
    contracts = {run["id"]: input_contract(run_arguments(run)) for run in plan["runs"]}
    if previous is not None:
        if previous.get("plan_sha256") != digest:
            raise RuntimeError("Campaign plan changed: order, budgets and run specifications are immutable")
        if previous.get("input_contracts") != contracts:
            raise RuntimeError("Campaign critical inputs changed; refusing to mix experimental definitions")
        return previous
    return {
        "schema_version": 1, "plan_sha256": digest, "input_contracts": contracts,
        "created_utc": datetime.now(timezone.utc).isoformat(), "status": "ready",
        "planned_search_seconds": sum(run["budget_minutes"] * 60 for run in plan["runs"]),
        "runs": [{"id": run["id"], "condition": run["condition"],
                  "replicate": run["replicate"], "status": "pending",
                  "budget_seconds": run["budget_minutes"] * 60,
                  "elapsed_search_seconds": 0.0} for run in plan["runs"]],
        "postprocess": {"status": "pending" if plan.get("postprocess_command") else "not_requested"},
    }


def runner_command(run: dict) -> list[str]:
    command = [sys.executable, str(ROOT / "scripts/run_evolution.py")]
    for key in PATH_FIELDS:
        command.extend(["--" + key.replace("_", "-"), str(run[key])])
    command.extend(["--budget-minutes", str(run["budget_minutes"]),
                    "--search-seed", str(run["search_seed"])])
    if "max_generations" in run:
        command.extend(["--max-generations", str(run["max_generations"])])
    if (Path(run["run_dir"]) / "budget_checkpoint.json").exists():
        command.append("--resume")
    return command


def sync_run_status(entry: dict, run: dict) -> dict | None:
    budget = read_json(Path(run["run_dir"]) / "budget_checkpoint.json")
    if budget is not None:
        if budget.get("budget_seconds") != run["budget_minutes"] * 60:
            raise RuntimeError(f"Original budget differs for run {run['id']}")
        entry.update({key: budget[key] for key in
                      ("status", "elapsed_search_seconds", "remaining_search_seconds") if key in budget})
    return budget


def kill_worker_from_checkpoint(run: dict) -> None:
    """Last-resort cleanup only after a campaign-owned supervisor won't stop."""
    import psutil
    budget = read_json(Path(run["run_dir"]) / "budget_checkpoint.json", {})
    pid = budget.get("worker_pid")
    if not pid:
        return
    try:
        proc = psutil.Process(pid)
        argv = proc.cmdline()
        if (str(ROOT / "scripts/run_evolution.py") in argv and "--worker" in argv
                and run["run_dir"] in argv and os.getpgid(pid) == pid):
            os.killpg(pid, signal.SIGKILL)
    except (psutil.Error, ProcessLookupError):
        pass


def stop_process(process, run: dict | None = None) -> None:
    if process.poll() is not None:
        return
    if run is not None:
        # Let the run supervisor checkpoint and kill its separately grouped worker.
        process.terminate()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if run is not None:
            kill_worker_from_checkpoint(run)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=10)


def save_checkpoint(path: Path, state: dict) -> None:
    state["updated_utc"] = datetime.now(timezone.utc).isoformat()
    state["elapsed_search_seconds"] = sum(r.get("elapsed_search_seconds", 0) for r in state["runs"])
    atomic_json(path, state)


def run_campaign(plan_path: Path, resume=False) -> int:
    plan_path = plan_path.resolve()
    plan = load_plan(plan_path)
    state_path = plan_path.parent / "campaign_checkpoint.json"
    with (plan_path.parent / "campaign.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another supervisor already owns this campaign")
        previous = read_json(state_path)
        if previous is not None and not resume:
            raise RuntimeError("Campaign already exists; use --resume")
        state = initialize_checkpoint(plan, previous)
        interrupted = False

        def handle_signal(signum, frame):
            nonlocal interrupted
            interrupted = True

        old_handlers = {sig: signal.signal(sig, handle_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
        state["supervisor_pid"] = os.getpid()
        save_checkpoint(state_path, state)
        child, active_run = None, None
        try:
            for run, entry in zip(plan["runs"], state["runs"]):
                # Validate queued inputs again: no method changes between conditions.
                if input_contract(run_arguments(run)) != state["input_contracts"][run["id"]]:
                    raise RuntimeError(f"Critical inputs changed before run {run['id']}")
                budget = sync_run_status(entry, run)
                if budget and budget["status"] in TERMINAL_RUN_STATUSES:
                    save_checkpoint(state_path, state)
                    continue
                if interrupted:
                    state["status"] = "interrupted"
                    save_checkpoint(state_path, state)
                    return 130
                state["status"] = "running"
                state["active_run_id"] = run["id"]
                entry["status"] = "starting"
                save_checkpoint(state_path, state)
                directory = Path(run["run_dir"])
                directory.mkdir(parents=True, exist_ok=True)
                with (directory / "supervisor.log").open("a", buffering=1) as log:
                    active_run = run
                    child = subprocess.Popen(runner_command(run), stdout=log, stderr=subprocess.STDOUT,
                                             env=subscription_environment(), cwd=ROOT,
                                             start_new_session=True)
                    entry["supervisor_pid"] = child.pid
                    next_progress = 0.0
                    while child.poll() is None:
                        sync_run_status(entry, run)
                        save_checkpoint(state_path, state)
                        now = time.monotonic()
                        if now >= next_progress:
                            print(json.dumps({"campaign_status": state["status"], "run": entry}), flush=True)
                            next_progress = now + 30
                        if interrupted:
                            stop_process(child, run)
                            break
                        time.sleep(0.5)
                    returncode = child.wait()
                child = None
                terminal = sync_run_status(entry, run)
                entry["supervisor_returncode"] = returncode
                if interrupted or (terminal and terminal["status"] == "interrupted"):
                    state["status"] = "interrupted"
                    save_checkpoint(state_path, state)
                    return 130
                if returncode or terminal is None or terminal["status"] not in TERMINAL_RUN_STATUSES:
                    state["status"] = "failed"
                    entry["status"] = "failed"
                    save_checkpoint(state_path, state)
                    return 1
                save_checkpoint(state_path, state)
            state["active_run_id"] = None
            command = plan.get("postprocess_command")
            if command and state["postprocess"]["status"] != "completed":
                if interrupted:
                    state["status"] = "interrupted"
                    save_checkpoint(state_path, state)
                    return 130
                state["status"] = "postprocessing"
                state["postprocess"] = {"status": "running", "command": command,
                                        "started_utc": datetime.now(timezone.utc).isoformat()}
                save_checkpoint(state_path, state)
                with (plan_path.parent / "postprocess.log").open("a", buffering=1) as log:
                    active_run = None
                    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                             env=subscription_environment(), cwd=ROOT,
                                             start_new_session=True)
                    state["postprocess"]["pid"] = child.pid
                    save_checkpoint(state_path, state)
                    while child.poll() is None:
                        if interrupted:
                            stop_process(child)
                            break
                        time.sleep(0.5)
                    returncode = child.wait()
                child = None
                state["postprocess"].update(returncode=returncode,
                                            status="interrupted" if interrupted else "completed" if not returncode else "failed")
                if interrupted or returncode:
                    state["status"] = "interrupted" if interrupted else "postprocess_failed"
                    save_checkpoint(state_path, state)
                    return 130 if interrupted else 1
            state["status"] = "completed"
            save_checkpoint(state_path, state)
            print(json.dumps({"campaign_status": "completed", "elapsed_search_seconds": state["elapsed_search_seconds"]}), flush=True)
            return 0
        except Exception as exc:
            if child is not None:
                stop_process(child, active_run)
                if active_run is not None:
                    entry = next(e for e in state["runs"] if e["id"] == active_run["id"])
                    sync_run_status(entry, active_run)
            state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            save_checkpoint(state_path, state)
            raise
        finally:
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "runs/consumption-v2/campaign.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    try:
        if args.status:
            plan = load_plan(args.plan.resolve())
            state = read_json(args.plan.resolve().parent / "campaign_checkpoint.json")
            print(json.dumps(state if state is not None else {
                "status": "not_started", "planned_runs": len(plan["runs"]),
                "planned_search_seconds": sum(r["budget_minutes"] * 60 for r in plan["runs"]),
            }, indent=2))
            return 0
        return run_campaign(args.plan, args.resume)
    except Exception as exc:
        print(f"Campaign blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
