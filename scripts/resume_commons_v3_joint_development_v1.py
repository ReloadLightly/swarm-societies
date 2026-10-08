#!/usr/bin/env python3
"""Resume only missing approved A2 cases, saving each as soon as it completes.

Start only after checking the host's original A2 runner has exited: a sandbox
process list cannot establish host absence. Publish/review every saved case and
refresh origin/main before supplying its pinned --published-commit. Preservation
checks below establish integrity/completeness, not scientific replay; `verify`
retains the original exact full-bank replay. No scientific settings are changed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.commons_v3 import development_joint_sites_v1 as dev
from swarm_societies.commons_v3 import development_pool_sites_v1 as pool
from swarm_societies.commons_v3.development_navigation_v1 import (
    canonical, read_case, _save_json, _save_record,
)

# Existing A2 v1 record fields, checked before recovery schedules any work.
SUMMARY_KEYS = frozenset("""agent_consumption_share_max agent_consumption_share_min agent_consumption_share_sd
biased_agent_consumption_share_max biased_agent_consumption_share_min biased_agent_consumption_share_sd
biased_share_of_need clean_eligible_fraction evidence_belief_messages evidence_clean_own evidence_clean_receipts
evidence_confounded evidence_duplicates evidence_eligible evidence_new_relay final_quarter_share_of_need
first64_share_of_need first_within10_mean_tick_if_reached local_collapse_site_tick_fraction max_ledger_residual
message_attempted_bytes message_attempts message_cost message_delivered_bytes message_paid_bytes messages_delivered
other_agent_consumption_share_max other_agent_consumption_share_min other_agent_consumption_share_sd other_share_of_need
share_of_need starvation_next_to_food_agent_tick_fraction starvation_next_to_food_share_of_need
terminal_between_agent_log_median_dispersion terminal_biased_absolute_log_error terminal_capacity_absolute_log_error
terminal_coverage90 terminal_ever_within10_fraction terminal_mean_log_interval_width terminal_other_absolute_log_error
terminal_seen_only_absolute_log_error terminal_seen_only_coverage90 time_mean_between_agent_log_median_dispersion
time_mean_capacity_absolute_log_error time_mean_coverage90 time_mean_ever_within10_fraction time_mean_mean_log_interval_width""".split())
MATERIAL_KEYS = frozenset("""collapsed_sites consumption message_attempted_bytes message_attempts message_cost
message_delivered_bytes message_paid_bytes messages_delivered starvation_next_to_food_agents
starvation_next_to_food_shortfall tick""".split())
BELIEF_KEYS = frozenset("""agent_site_pairs between_agent_log_median_dispersion biased_absolute_log_error
capacity_absolute_log_error clean_eligible_fraction coverage90 directly_seen_pairs ever_within10_fraction
evidence_belief_messages evidence_clean_own evidence_clean_receipts evidence_confounded evidence_duplicates
evidence_eligible evidence_new_relay mean_log_interval_width other_absolute_log_error pairs_with_posterior
seen_only_absolute_log_error seen_only_coverage90 tick""".split())


def _assert_no_active_runner():
    # Conservatively reject any visible original runner, including its workers.
    names = {"run_commons_v3_joint_development_v1.py",
             "resume_commons_v3_joint_development_remaining.py",
             "commons_v3_joint_handoff.py"}
    for process in psutil.process_iter():
        if process.pid == os.getpid():
            continue
        try:
            if process.uids().real != os.getuid():
                continue
            if any(Path(arg).name in names for arg in process.cmdline()):
                raise ValueError(f"A2 runner still active: PID {process.pid}")
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise ValueError("cannot inspect a potentially active A2 runner") from exc


@contextmanager
def _exclusive(output):
    key = hashlib.sha256(str(output.resolve()).encode()).hexdigest()
    lock = Path(tempfile.gettempdir()) / ("commons-v3-a2-" + key + ".lock")
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another A2 resume/verify holds this output lock") from exc
        try:
            _assert_no_active_runner()
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True).stdout


def _published_cases(commit):
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("supply the full reviewed published commit SHA")
    try:
        _git("cat-file", "-e", commit + "^{commit}")
        _git("merge-base", "--is-ancestor", commit, "refs/remotes/origin/main")
        prefix = dev.FALLBACK_ROOT + "/cases/"
        names = _git("ls-tree", "-r", "--name-only", commit, "--", prefix).decode().splitlines()
        return {Path(name).name: hashlib.sha256(_git("show", commit + ":" + name)).hexdigest()
                for name in names if name.endswith(".json.gz")}
    except subprocess.CalledProcessError as exc:
        raise ValueError("published commit must be available and reachable from recorded origin/main") from exc


def _validate_record(row, job):
    """Reject partial terminal records without treating a heartbeat as a save."""
    try:
        state = dev.worlds.initialize(job["condition"], job["need"], job["seed"])
        state = replace(state, config=replace(state.config, max_messages=4))
        initial = dev.engine.snapshot(state)
        final = dev.engine.restore(row["final_snapshot"])
        pairs = [(agent.id, patch.id) for agent in state.agents for patch in state.patches]
        checks = (
            row["job"] == job, row["version"] == dev.VERSION,
            row["horizon"] == dev.HORIZON, row["rate_known"] is False,
            row["rate_prior"] == dev.RATE_PRIOR, row["initial_snapshot"] == initial,
            row["initial_physical_sha256"] == dev.physical_initial_digest(initial),
            final.tick == dev.HORIZON, final.seed == state.seed, final.config == state.config,
            [frame["tick"] for frame in row["ticks"]] == list(range(1, dev.HORIZON + 1)),
            [frame["tick"] for frame in row["belief_ticks"]] == list(range(dev.HORIZON + 1)),
            all(set(frame) == MATERIAL_KEYS for frame in row["ticks"]),
            all(set(frame) == BELIEF_KEYS for frame in row["belief_ticks"]),
            set(row["summary"]) == SUMMARY_KEYS,
            [frame["tick"] for frame in row["belief_checkpoints"]] == list(dev.BELIEF_CHECKPOINTS),
            row["belief_pair_columns"] == list(dev.PAIR_COLUMNS),
            all([tuple(pair[:2]) for pair in frame["pairs"]] == pairs
                and all(len(pair) == len(dev.PAIR_COLUMNS) for pair in frame["pairs"])
                for frame in row["belief_checkpoints"]),
            [agent["id"] for agent in row["agents"]] == list(range(len(state.agents))),
            row["first_within10_columns"] == ["agent", "site", "first_tick_or_null"],
            [tuple(pair[:2]) for pair in row["first_within10"]] == pairs,
            all(len(pair) == 3 for pair in row["first_within10"]),
            len(row["final_policy_memory_sha256"]) == len(state.agents),
            (row["final_pool_memory_sha256"] is None) == (job["arm"] == "L0"),
        )
        hashes = [row["trajectory_sha256"], row["weather_sha256"], *row["final_policy_memory_sha256"]]
        if job["arm"] == "R-pool":
            hashes.append(row["final_pool_memory_sha256"])
        if not all(checks) or any(not isinstance(value, str) or len(value) != 64
                                 or any(c not in "0123456789abcdef" for c in value) for value in hashes):
            raise ValueError("incomplete fields")
        dev.base._require_jobs([row], [job])
        canonical(row)  # Reject non-finite nested measurements too.
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("incomplete or mismatched A2 record: " + dev.base.case_id(job)) from exc


def _load_saved(output, jobs, published_commit):
    published = _published_cases(published_commit)
    expected = {dev.base._path(output, job).name for job in jobs}
    actual = {path.name for path in (output / "cases").glob("*.json.gz")}
    if actual != set(published) or not actual <= expected:
        raise ValueError("saved inventory differs from published commit; publish/review or restore before resume")
    rows = [None] * len(jobs)
    for index, job in enumerate(jobs):
        path = dev.base._path(output, job)
        if path.name not in actual:
            continue
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != published[path.name]:
            raise ValueError("published saved record differs: " + path.name)
        rows[index] = read_case(path)
        _validate_record(rows[index], job)
    return rows


def _complete_missing(output, jobs, rows, workers):
    missing = [(index, job) for index, job in enumerate(jobs) if rows[index] is None]
    if missing:
        failure = None
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(dev.run_episode, job): (index, job) for index, job in missing}
            for future in as_completed(futures):
                if future.cancelled():
                    continue
                index, job = futures[future]
                try:
                    row = future.result()
                    _validate_record(row, job)
                    _save_record(dev.base._path(output, job), row)
                except Exception as error:
                    if failure is None:
                        failure = error
                        for pending in futures:
                            pending.cancel()
                    continue  # Drain and persist successful work already running.
                rows[index] = row
                print(f"saved {sum(row is not None for row in rows)}/{len(jobs)} "
                      + dev.base.case_id(job), file=sys.stderr, flush=True)
        if failure is not None:
            raise failure
    return rows  # Fixed original order, regardless of completion order.


def run(output=dev.FALLBACK_ROOT, *, published_commit=None, workers=2, verify=False,
        pool_root=pool.POOL_ROOT, baseline_root=pool.BASE_ROOT,
        reference_root=pool.REFERENCE_ROOT, calibration_root=dev.CALIBRATION_ROOT):
    output = Path(output)
    dev.base._workers(workers)
    if not verify and (output / "summary.json").exists():
        raise ValueError("completed fallback bank; use verify")
    with _exclusive(output):
        if not verify and (output / "summary.json").exists():
            raise ValueError("completed fallback bank; use verify")
        jobs = dev.fallback_jobs()
        if verify:
            dev.base._require_paths(output, jobs)
            if not (output / "summary.json").is_file():
                raise ValueError("full replay requires a completed summary")
            return dev.run(output, pool_root=pool_root, baseline_root=baseline_root,
                           reference_root=reference_root, calibration_root=calibration_root,
                           workers=workers, verify=True)
        rows = _load_saved(output, jobs, published_commit)
        references, known, calibration = dev._load_prerequisites(
            pool_root, baseline_root, reference_root, calibration_root)
        _complete_missing(output, jobs, rows, workers)
        dev.base._require_paths(output, jobs)
        summary = dev.summarize(rows, references, known, calibration)
        _save_json(output / "summary.json", summary)
        return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("resume", "verify"))
    parser.add_argument("--published-commit", help="full reviewed commit SHA, reachable from recorded origin/main")
    parser.add_argument("--output", type=Path, default=Path(dev.FALLBACK_ROOT))
    parser.add_argument("--pool", type=Path, default=Path(pool.POOL_ROOT))
    parser.add_argument("--baseline", type=Path, default=Path(pool.BASE_ROOT))
    parser.add_argument("--references", type=Path, default=Path(pool.REFERENCE_ROOT))
    parser.add_argument("--calibration", type=Path, default=Path(dev.CALIBRATION_ROOT))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.command == "resume" and not args.published_commit:
        parser.error("resume requires --published-commit after reviewing/publishing saved records")
    result = run(args.output, published_commit=args.published_commit, workers=args.workers,
                 verify=args.command == "verify", pool_root=args.pool, baseline_root=args.baseline,
                 reference_root=args.references, calibration_root=args.calibration)
    print(json.dumps(result, indent=2, sort_keys=True))
