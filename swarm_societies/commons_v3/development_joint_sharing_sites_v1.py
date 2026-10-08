"""Approved sharing development under A2's unknown shared renewal rate.

Implementation can be prepared while the fallback computes. Scientific runs
require all 32 fallback records, their reconstructed passing G3-prime and the
unchanged calibration prerequisites. No fresh evaluation is performed here.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from . import development_joint_sites_v1 as joint
from . import development_learning_sites_v1 as base
from . import development_pool_sites_v1 as pool
from .development_navigation_v1 import canonical, digest, read_case, _save_json


VERSION = "commons-v3-joint-sharing-development-sites-v1"
SHARING_ROOT = "evidence/commons-v3-joint-sharing-development-v1"

# The unchanged joint recorder's v1 fields. A truncated record must fail before
# any continuation is submitted, including fields outside the primary gate.
SUMMARY_FIELDS = frozenset("""agent_consumption_share_max agent_consumption_share_min agent_consumption_share_sd
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
MATERIAL_FIELDS = frozenset("""collapsed_sites consumption message_attempted_bytes message_attempts message_cost
message_delivered_bytes message_paid_bytes messages_delivered starvation_next_to_food_agents
starvation_next_to_food_shortfall tick""".split())
BELIEF_FIELDS = frozenset("""agent_site_pairs between_agent_log_median_dispersion biased_absolute_log_error
capacity_absolute_log_error clean_eligible_fraction coverage90 directly_seen_pairs ever_within10_fraction
evidence_belief_messages evidence_clean_own evidence_clean_receipts evidence_confounded evidence_duplicates
evidence_eligible evidence_new_relay mean_log_interval_width other_absolute_log_error pairs_with_posterior
seen_only_absolute_log_error seen_only_coverage90 tick""".split())


def sharing_jobs():
    return base.candidate_jobs(joint.Q, base.ARMS[1:])


def _require_complete(row, job, version):
    """Check saved terminal topology; this does not claim an episode replay."""
    try:
        state = joint.worlds.initialize(job["condition"], job["need"], job["seed"])
        state = replace(state, config=replace(state.config, max_messages=4))
        initial = joint.engine.snapshot(state)
        final = joint.engine.restore(row["final_snapshot"])
        pairs = [(agent.id, patch.id) for agent in state.agents for patch in state.patches]
        checks = (
            row["job"] == job, row["version"] == version,
            row["horizon"] == joint.HORIZON,
            row["rate_known"] is False, row["rate_prior"] == joint.RATE_PRIOR,
            row["initial_snapshot"] == initial,
            row["initial_physical_sha256"] == base.physical_initial_digest(initial),
            final.tick == joint.HORIZON, final.seed == state.seed,
            final.config == state.config,
            [frame["tick"] for frame in row["ticks"]] == list(range(1, joint.HORIZON + 1)),
            [frame["tick"] for frame in row["belief_ticks"]] == list(range(joint.HORIZON + 1)),
            all(set(frame) == MATERIAL_FIELDS for frame in row["ticks"]),
            all(set(frame) == BELIEF_FIELDS for frame in row["belief_ticks"]),
            set(row["summary"]) == SUMMARY_FIELDS,
            [frame["tick"] for frame in row["belief_checkpoints"]] == list(base.BELIEF_CHECKPOINTS),
            row["belief_pair_columns"] == list(base.PAIR_COLUMNS),
            all([tuple(pair[:2]) for pair in frame["pairs"]] == pairs
                and all(len(pair) == len(base.PAIR_COLUMNS) for pair in frame["pairs"])
                for frame in row["belief_checkpoints"]),
            [agent["id"] for agent in row["agents"]] == list(range(len(state.agents))),
            row["first_within10_columns"] == ["agent", "site", "first_tick_or_null"],
            [tuple(pair[:2]) for pair in row["first_within10"]] == pairs,
            all(len(pair) == 3 for pair in row["first_within10"]),
            len(row["final_policy_memory_sha256"]) == len(state.agents),
            (row["final_pool_memory_sha256"] is not None) == (job["arm"] == "R-pool"),
        )
        hashes = [row["trajectory_sha256"], row["weather_sha256"], *row["final_policy_memory_sha256"]]
        if row["final_pool_memory_sha256"] is not None:
            hashes.append(row["final_pool_memory_sha256"])
        if not all(checks) or any(not isinstance(value, str) or len(value) != 64
                                 or any(c not in "0123456789abcdef" for c in value) for value in hashes):
            raise ValueError("incomplete fields")
        base._require_jobs([row], [job])
        canonical(row)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("incomplete or mismatched unknown-rate record: " + base.case_id(job)) from error


def load_fallback(fallback_root=joint.FALLBACK_ROOT, pool_root=pool.POOL_ROOT,
                  baseline_root=pool.BASE_ROOT, reference_root=pool.REFERENCE_ROOT,
                  calibration_root=joint.CALIBRATION_ROOT):
    """Reconstruct the saved gate, never trust a standalone passed flag."""
    root = Path(fallback_root)
    if not (root / "summary.json").is_file():
        raise ValueError("A2 comparison incomplete; sharing requires its completed passing G3-prime")
    jobs = joint.fallback_jobs()
    base._require_paths(root, jobs)
    rows = [read_case(base._path(root, job)) for job in jobs]
    for row, job in zip(rows, jobs):
        _require_complete(row, job, joint.VERSION)
    references, known, calibration = joint._load_prerequisites(
        pool_root, baseline_root, reference_root, calibration_root)
    reconstructed = joint.summarize(rows, references, known, calibration)
    saved = json.loads((root / "summary.json").read_text())
    if canonical(reconstructed) != canonical(saved):
        raise ValueError("fallback aggregate differs from saved cases")
    if not reconstructed["G3_prime"]["passed"]:
        raise ValueError("A2 G3-prime failed; stop the contracted design, no sharing runs")
    return [row for row in rows if row["job"]["arm"] == "L0"], references, reconstructed


def run_episode(job):
    """Audited fixed-menu worker; the public run entry point enforces G3-prime."""
    if job not in sharing_jobs():
        raise ValueError("case is outside the approved unknown-rate sharing menu")
    from .calibration_joint_sites_v1 import RESOLUTION
    from .policies_joint_sharing_sites_v1 import UnknownSharingForager

    state = joint.worlds.initialize(job["condition"], job["need"], job["seed"])
    state = replace(state, config=replace(state.config, max_messages=4))
    arm = job["arm"].split("-")[0]
    policies = [UnknownSharingForager(arm, phi=joint.PHI, q=joint.Q,
                biased=job["arm"].endswith("-biased") and agent.id in base.BIASED_IDS,
                **RESOLUTION) for agent in state.agents]
    record = joint._record_unknown_episode(job, state, policies)
    return {**record, "version": VERSION}


def summarize(rows, l0, references, fallback_summary):
    base._require_jobs(rows, sharing_jobs())
    base._require_jobs(l0, base.candidate_jobs(joint.Q))
    if (fallback_summary.get("version") != joint.VERSION
            or fallback_summary.get("rate_known") is not False
            or fallback_summary.get("rate_prior") != joint.RATE_PRIOR
            or fallback_summary.get("G3_prime", {}).get("passed") is not True):
        raise ValueError("passed A2 G3-prime is required for unknown-rate sharing")
    for records, version in ((rows, VERSION), (l0, joint.VERSION)):
        for row in records:
            _require_complete(row, row["job"], version)
    selected = [*l0, *rows]
    base._paired_worlds(selected, references)
    return {"version": VERSION, "amendment": "A2", "rate_known": False,
        "rate_prior": dict(joint.RATE_PRIOR),
        "scope": "development only on four reused seeds; no evaluation Holm tests",
        "seeds": list(base.SEEDS), "horizon": joint.HORIZON, "phi": joint.PHI, "q": joint.Q,
        "episodes": len(rows), "L0_episodes_reused": len(l0),
        "reference_episodes_reused": len(references), "biased_ids": list(base.BIASED_IDS),
        "fallback_summary_sha256": digest(fallback_summary),
        "joint_calibration": fallback_summary["joint_calibration"],
        "G3_prime": fallback_summary["G3_prime"],
        "cells": pool.comparison_cells(selected, references),
        "development_contrasts": base.development_contrasts(selected),
        "experimental_model_calls": 0, "evolutionary_runs": 0, "fresh_evaluation_episodes": 0,
        "decision": "stop at development review and report; no freeze or fresh evaluation"}


def run(output=SHARING_ROOT, *, fallback_root=joint.FALLBACK_ROOT,
        pool_root=pool.POOL_ROOT, baseline_root=pool.BASE_ROOT,
        reference_root=pool.REFERENCE_ROOT, calibration_root=joint.CALIBRATION_ROOT,
        workers=2, verify=False):
    base._workers(workers)
    output = Path(output)
    if not verify and (output / "summary.json").exists():
        raise ValueError("completed unknown-rate sharing bank; use verify")
    l0, references, fallback = load_fallback(
        fallback_root, pool_root, baseline_root, reference_root, calibration_root)
    jobs = sharing_jobs()
    if verify:
        base._require_paths(output, jobs)
        if not (output / "summary.json").is_file():
            raise ValueError("completed sharing summary is required for verification")
    rows = pool._run_jobs(output, jobs, workers, run_episode, verify=verify)
    base._require_paths(output, jobs)
    summary = summarize(rows, l0, references, fallback)
    if verify:
        saved = json.loads((output / "summary.json").read_text())
        if canonical(summary) != canonical(saved):
            raise ValueError("unknown-rate sharing aggregate differs on exact replay")
        return {"version": VERSION, "exact_episodes": len(rows), "summary_sha256": digest(saved)}
    _save_json(output / "summary.json", summary)
    return summary
