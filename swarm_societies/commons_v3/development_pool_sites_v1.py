"""Approved A1 perfect-sharing reference, G3-prime and gated D continuation.

Completed Ticket B/D banks and their source remain unchanged. New records use
existing canonical serialization, compressed cases and exact replay tooling.
No fresh evaluation or parameter selection is performed by this module.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import sys

from . import development_learning_sites_v1 as base
from . import engine_sites_v1 as engine
from . import worlds_sites_v1 as worlds
from .development_navigation_v1 import canonical, digest, read_case, _save_json, _save_record
from .development_learning_sites_v1 import (BeliefMetrics, BIASED_IDS,
    BELIEF_CHECKPOINTS, PAIR_COLUMNS, HORIZON, PHI, SEEDS, CONDITIONS, NEEDS,
    physical_initial_digest, _material_frame, _worker_heartbeat)

VERSION = "commons-v3-pooling-development-sites-v1"
SHARING_VERSION = "commons-v3-sharing-development-sites-v1"
Q = .25
BASE_SUMMARY_SHA256 = "72b22a10d5f9222608623c6122da867a0238cfb7cef8b5f5b23bb9cd62f21400"
BASE_ROOT = "evidence/commons-v3-learning-development-v1"
REFERENCE_ROOT = "evidence/commons-v3-world-model-consequence-v1"
POOL_ROOT = "evidence/commons-v3-pooling-development-v1"
SHARING_ROOT = "evidence/commons-v3-sharing-development-v1"


def pool_jobs():
    return [{**job, "arm": "R-pool"} for job in base.candidate_jobs(Q)]


def _record_pool_episode(job, state, policies, coordinator, horizon=HORIZON):
    from .observations_messages_sites_v1 import observations
    initial = engine.snapshot(state)
    capacities, population = state.config.site_capacities, len(state.agents)
    biased = tuple(identity for identity in BIASED_IDS if identity < population) if job["arm"].endswith("-biased") else ()
    measurement = BeliefMetrics(capacities, population, biased)
    trajectory = hashlib.sha256(canonical(initial) + b"\n")
    weather = hashlib.sha256()
    frames, epistemic, checkpoints = [], [], []
    late_baseline, previous_result = [0.] * population, None
    max_residual = 0.
    patch_at = {(p.x, p.y): p.id for p in state.patches}
    for tick in range(horizon + 1):
        packets = observations(state, previous_result)
        coordinator.prepare(packets, previous_result)
        measurement.observe_sites(packets)
        if tick == horizon:
            for policy, packet in zip(policies, packets):
                policy.observe(packet)
            actions = None
        else:
            actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        frame, pairs = measurement.measure(policies, tick, raw=tick in BELIEF_CHECKPOINTS or tick == horizon)
        epistemic.append(frame)
        if pairs:
            checkpoints.append({"tick": tick, "pairs": pairs})
        if tick == horizon:
            trajectory.update(canonical({"terminal_observation_tick": tick,
                                          "updates": [policy.last_updates for policy in policies],
                                          "beliefs": frame}) + b"\n")
            break
        result = engine.step(state, actions)
        state, previous_result = result.state, result
        trajectory.update(canonical({"tick": tick, "actions": [asdict(a) for a in actions],
            "updates": [policy.last_updates for policy in policies], "beliefs": frame,
            "ledger": asdict(result.ledger)}) + b"\n")
        weather.update(canonical([p.weather for p in result.ledger.patches]) + b"\n")
        frames.append(_material_frame(result, actions, patch_at, capacities, job["phi"]))
        max_residual = max(max_residual, abs(result.ledger.residual),
                           *(abs(row.residual) for row in result.ledger.agents),
                           *(abs(row.residual) for row in result.ledger.patches))
        if state.tick == 3 * horizon // 4:
            late_baseline = [agent.consumption for agent in state.agents]
        _worker_heartbeat(job, state.tick, horizon)
    late_ticks = horizon - 3 * horizon // 4
    agents = [{"id": a.id, "biased": a.id in biased,
               "share_of_need": a.consumption / (horizon * job["need"]),
               "final_quarter_share_of_need": (a.consumption - late_baseline[a.id]) / (late_ticks * job["need"])}
              for a in state.agents]
    denominator = population * horizon * job["need"]
    summary = {"share_of_need": st.mean(row["share_of_need"] for row in agents),
        "final_quarter_share_of_need": st.mean(row["final_quarter_share_of_need"] for row in agents),
        "first64_share_of_need": math.fsum(row["consumption"] for row in frames[:64]) / (population * min(64, horizon) * job["need"]),
        "starvation_next_to_food_share_of_need": math.fsum(f["starvation_next_to_food_shortfall"] for f in frames) / denominator,
        "starvation_next_to_food_agent_tick_fraction": sum(f["starvation_next_to_food_agents"] for f in frames) / (population * horizon),
        "local_collapse_site_tick_fraction": sum(f["collapsed_sites"] for f in frames) / (len(capacities) * horizon),
        "message_attempts": sum(f["message_attempts"] for f in frames),
        "messages_delivered": sum(f["messages_delivered"] for f in frames),
        "message_attempted_bytes": sum(f["message_attempted_bytes"] for f in frames),
        "message_paid_bytes": sum(f["message_paid_bytes"] for f in frames),
        "message_delivered_bytes": sum(f["message_delivered_bytes"] for f in frames),
        "message_cost": math.fsum(f["message_cost"] for f in frames),
        "agent_consumption_share_min": min(a["share_of_need"] for a in agents),
        "agent_consumption_share_max": max(a["share_of_need"] for a in agents),
        "agent_consumption_share_sd": st.pstdev(a["share_of_need"] for a in agents),
        "max_ledger_residual": max_residual}
    for name, predicate in (("biased", lambda a: a["biased"]), ("other", lambda a: not a["biased"])):
        cohort = [a for a in agents if predicate(a)]
        summary[name + "_share_of_need"] = st.mean(a["share_of_need"] for a in cohort) if cohort else None
        for suffix, operation in (("min", min), ("max", max), ("sd", st.pstdev)):
            summary[name + "_agent_consumption_share_" + suffix] = operation(a["share_of_need"] for a in cohort) if cohort else None
    for key in ("capacity_absolute_log_error", "coverage90", "mean_log_interval_width",
                "between_agent_log_median_dispersion", "ever_within10_fraction"):
        summary["terminal_" + key] = epistemic[-1][key]
        summary["time_mean_" + key] = st.mean(frame[key] for frame in epistemic[1:])
    summary.update({key: value for key, value in epistemic[-1].items() if key.startswith("evidence_")})
    summary["clean_eligible_fraction"] = epistemic[-1]["clean_eligible_fraction"]
    summary["first_within10_mean_tick_if_reached"] = st.mean(measurement.first_accurate.values()) if measurement.first_accurate else None
    for key in ("seen_only_absolute_log_error", "seen_only_coverage90", "biased_absolute_log_error", "other_absolute_log_error"):
        summary["terminal_" + key] = epistemic[-1][key]
    return {"version": VERSION, "job": job, "horizon": horizon,
            "initial_snapshot": initial, "final_snapshot": engine.snapshot(state),
            "initial_physical_sha256": physical_initial_digest(initial),
            "trajectory_sha256": trajectory.hexdigest(), "weather_sha256": weather.hexdigest(),
            "final_policy_memory_sha256": [digest(policy.memory()) for policy in policies],
            "final_pool_memory_sha256": digest(coordinator.memory()),
            "summary": summary, "agents": agents, "ticks": frames, "belief_ticks": epistemic,
            "belief_pair_columns": list(PAIR_COLUMNS), "belief_checkpoints": checkpoints,
            "first_within10_columns": ["agent", "site", "first_tick_or_null"],
            "first_within10": measurement.first_accuracy_rows()}


def run_pool_episode(job):
    if job not in pool_jobs():
        raise ValueError("case is outside the approved R-pool menu")
    from .policies_pool_sites_v1 import PoolCoordinator, PoolForager
    try:
        state = worlds.initialize(job["condition"], job["need"], job["seed"])
        state = replace(state, config=replace(state.config, max_messages=4))
        coordinator = PoolCoordinator()
        policies = [PoolForager(coordinator, agent.id, phi=PHI, q=Q) for agent in state.agents]
        result = _record_pool_episode(job, state, policies, coordinator)
        if any(result["summary"][key] != 0 for key in
               ("message_attempts", "message_paid_bytes", "message_cost")):
            raise ValueError("R-pool must have no message traffic or costs")
        return result
    except Exception as error:
        print(f"failed {base.case_id(job)}: {error!r}", file=sys.stderr, flush=True)
        raise RuntimeError("pool episode failed: " + base.case_id(job)) from error


def load_baseline(root=BASE_ROOT, reference_root=REFERENCE_ROOT):
    root = Path(root)
    saved = json.loads((root / "summary.json").read_text())
    if digest(saved) != BASE_SUMMARY_SHA256:
        raise ValueError("completed known-rate L0 summary differs from approved checkpoint")
    references, reference_record = base.load_references(reference_root)
    jobs = base.candidate_jobs()
    base._require_paths(root, jobs)
    rows = [read_case(base._path(root, job)) for job in jobs]
    if canonical(base.summarize(rows, references, reference_record)) != canonical(saved):
        raise ValueError("completed baseline aggregate no longer reconstructs exactly")
    selected = [row for row in rows if row["job"]["q"] == Q]
    base._require_jobs(selected, base.candidate_jobs(Q))
    return selected, references, {"summary_sha256": digest(saved),
        "preserved_G3": saved["G3"], "reference_record": reference_record,
        "selected_case_sha256": {base.case_id(row["job"]): digest(row) for row in selected}}


def g3_prime(pool_rows, l0_rows):
    base._require_jobs(pool_rows, pool_jobs())
    base._require_jobs(l0_rows, base.candidate_jobs(Q))
    if any(row["horizon"] != HORIZON for row in [*pool_rows, *l0_rows]):
        raise ValueError("G3-prime requires the whole 512-tick horizon")
    cells = []
    for condition in CONDITIONS:
        for need in NEEDS:
            selected = lambda rows: {row["job"]["seed"]: row["summary"]["share_of_need"]
                for row in rows if (row["job"]["condition"], row["job"]["need"]) == (condition, need)}
            pooled, alone = selected(pool_rows), selected(l0_rows)
            paired = [{"seed": seed, "R-pool": pooled[seed], "L0": alone[seed],
                       "pool_minus_L0": pooled[seed] - alone[seed]} for seed in SEEDS]
            cells.append({"condition": condition, "need": need, "paired": paired,
                          "pool_minus_L0": base.descriptive(row["pool_minus_L0"] for row in paired)})
    target = next(cell for cell in cells if cell["condition"] == "wide" and cell["need"] == 1.6)
    passed = target["pool_minus_L0"]["mean"] >= .02
    return {"measurement": "paired whole-run consumption/need, four reused development seeds",
            "condition": "wide", "need": 1.6, "threshold": .02, "cells": cells,
            "passed": passed, "decision": "run declared sharing development arms" if passed
            else "use approved unknown-rate fallback once, after joint G2 recalibration"}


def _epistemic_value(row, metric):
    if metric == "time_mean_seen_only_absolute_log_error":
        values = [frame["seen_only_absolute_log_error"] for frame in row["belief_ticks"][1:]
                  if frame["seen_only_absolute_log_error"] is not None]
        return st.mean(values) if values else None
    return row["summary"][metric]


def comparison_cells(rows, references, *, include_pool=False):
    """Descriptive comparisons; keep endpoint and population definitions explicit."""
    arms = ("L0", "R-pool") if include_pool else base.ARMS
    metric_names = ("share_of_need", "final_quarter_share_of_need",
                    "time_mean_capacity_absolute_log_error", "terminal_capacity_absolute_log_error",
                    "time_mean_seen_only_absolute_log_error", "terminal_seen_only_absolute_log_error",
                    "time_mean_coverage90", "terminal_coverage90")
    cells = []
    for condition in CONDITIONS:
        for need in NEEDS:
            group = [row for row in rows if (row["job"]["condition"], row["job"]["need"]) == (condition, need)]
            indexed = {arm: {row["job"]["seed"]: row for row in group if row["job"]["arm"] == arm} for arm in arms}
            contrasts = (("R-pool", "L0"),) if include_pool else (("L1", "L0"), ("L2", "L0"),
                        ("L3", "L2"), ("L3-biased", "L2-biased"))
            gaps = {}
            for left, right in contrasts:
                paired = []
                for seed in SEEDS:
                    values = {metric: (_epistemic_value(indexed[left][seed], metric),
                                       _epistemic_value(indexed[right][seed], metric)) for metric in metric_names}
                    paired.append({"seed": seed, **{metric: a - b if a is not None and b is not None else None
                                                    for metric, (a, b) in values.items()}})
                gaps[left + "_minus_" + right] = {"paired": paired,
                    "statistics": {key: base.descriptive(pair[key] for pair in paired) for key in metric_names}}
            cells.append({"condition": condition, "need": need,
                "arms": {arm: {key: base.descriptive(row["summary"][key] for row in indexed[arm].values())
                                for key in next(iter(indexed[arm].values()))["summary"]} for arm in arms},
                "contrasts": gaps,
                "belief_trajectories": {arm: [{"tick": tick, **{key: base.descriptive(row["belief_ticks"][tick][key]
                    for row in indexed[arm].values()) for key in next(iter(indexed[arm].values()))["belief_ticks"][tick]
                    if key != "tick"}} for tick in BELIEF_CHECKPOINTS] for arm in arms},
                "reference_consumption": {arm: base.descriptive(row["summary"]["share_of_need"] for row in references
                    if row["job"]["arm"] == arm and (row["job"]["condition"], row["job"]["need"]) == (condition, need))
                    for arm in ("R-oracle", "R-fixed", "R-greedy")}})
    return cells


def summarize_pool(pool_rows, l0_rows, references, baseline_record):
    gate = g3_prime(pool_rows, l0_rows)
    base._paired_worlds([*pool_rows, *l0_rows], references)
    return {"version": VERSION, "amendment": "A1", "rate_known": True,
        "scope": "development only; four reused seeds; all uncertainty intervals descriptive",
        "seeds": list(SEEDS), "horizon": HORIZON, "phi": PHI, "q": Q,
        "episodes": len(pool_rows), "L0_episodes_reused": len(l0_rows), "reference_episodes_reused": len(references),
        "baseline": baseline_record, "G3_prime": gate,
        "cells": comparison_cells([*l0_rows, *pool_rows], references, include_pool=True),
        "pool_information": "union of legal local stocks at consecutive ticks, total site extraction; unique(site,tick) events; likelihood before bounds; instantaneous pooled beliefs",
        "navigation": "each agent retains only its own local site observations and navigation records",
        "seen_pairs": "direct sightings by each individual, including for R-pool; pooled knowledge does not change direct_seen",
        "pool_counter_semantics": "clean_receipts counts privileged pooled transitions assimilated per agent, not paid receipts; their sum counts recipients as in L1",
        "experimental_model_calls": 0, "evolutionary_runs": 0, "fresh_evaluation_episodes": 0}


def _run_jobs(output, jobs, workers, runner, *, verify=False):
    base._workers(workers)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for number, (job, replay) in enumerate(zip(jobs, pool.map(runner, jobs)), start=1):
            path = base._path(output, job)
            if path.exists():
                if canonical(read_case(path)) != canonical(replay):
                    raise ValueError("exact replay differs: " + base.case_id(job))
            elif verify:
                raise ValueError("missing case during verification: " + base.case_id(job))
            else:
                _save_record(path, replay)
            rows.append(replay)
            print(f"{'verified' if verify else 'completed'} {number}/{len(jobs)} {base.case_id(job)}", file=sys.stderr, flush=True)
    return rows


def run_pool(output=POOL_ROOT, baseline_root=BASE_ROOT, reference_root=REFERENCE_ROOT, workers=2):
    output = Path(output)
    if (output / "summary.json").exists():
        raise ValueError("completed R-pool bank; use pool-verify")
    l0, refs, record = load_baseline(baseline_root, reference_root)
    rows = _run_jobs(output, pool_jobs(), workers, run_pool_episode)
    summary = summarize_pool(rows, l0, refs, record)
    base._require_paths(output, pool_jobs())
    _save_json(output / "summary.json", summary)
    return summary


def _load_pool(output, l0, refs, record):
    output = Path(output)
    saved = json.loads((output / "summary.json").read_text())
    base._require_paths(output, pool_jobs())
    rows = [read_case(base._path(output, job)) for job in pool_jobs()]
    if canonical(summarize_pool(rows, l0, refs, record)) != canonical(saved):
        raise ValueError("R-pool aggregate differs from saved records")
    return rows, saved


def verify_pool(output=POOL_ROOT, baseline_root=BASE_ROOT, reference_root=REFERENCE_ROOT, workers=2):
    l0, refs, record = load_baseline(baseline_root, reference_root)
    _, saved = _load_pool(output, l0, refs, record)
    rows = _run_jobs(output, pool_jobs(), workers, run_pool_episode, verify=True)
    if canonical(summarize_pool(rows, l0, refs, record)) != canonical(saved):
        raise ValueError("R-pool aggregate differs on exact replay")
    return {"version": VERSION, "exact_episodes": len(rows), "summary_sha256": digest(saved), "G3_prime": saved["G3_prime"]}


def run_floors(output=POOL_ROOT, baseline_root=BASE_ROOT, reference_root=REFERENCE_ROOT, workers=2):
    from .floor_diagnostic_sites_v1 import diagnose_case, summarize
    base._workers(workers)
    l0, refs, _ = load_baseline(baseline_root, reference_root)
    path = Path(output) / "floor-diagnostics.json"
    if path.exists():
        raise ValueError("completed floor diagnostic; preserve the saved record")
    originals = [*l0, *(row for row in refs if row["job"]["arm"] == "R-oracle")]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for number, row in enumerate(pool.map(diagnose_case, originals), 1):
            rows.append(row)
            print(f"floor replay {number}/{len(originals)}", file=sys.stderr, flush=True)
    result = summarize(rows)
    _save_json(path, result)
    return result


def summarize_sharing(rows, l0, refs, baseline_record, pool_summary):
    base._require_jobs(rows, base.candidate_jobs(Q, base.ARMS[1:]))
    if not pool_summary["G3_prime"]["passed"]:
        raise ValueError("A1 G3-prime has not authorized known-rate sharing")
    selected = [*l0, *rows]
    base._paired_worlds(selected, refs)
    return {"version": SHARING_VERSION, "amendment": "A1", "rate_known": True,
        "scope": "development only on four reused seeds; no evaluation Holm tests",
        "seeds": list(SEEDS), "horizon": HORIZON, "phi": PHI, "q": Q,
        "episodes": len(rows), "L0_episodes_reused": len(l0), "reference_episodes_reused": len(refs),
        "baseline": baseline_record, "pool_summary_sha256": digest(pool_summary), "G3_prime": pool_summary["G3_prime"],
        "cells": comparison_cells(selected, refs), "development_contrasts": base.development_contrasts(selected),
        "experimental_model_calls": 0, "evolutionary_runs": 0, "fresh_evaluation_episodes": 0,
        "decision": "stop at development review and report; no freeze or fresh evaluation"}


def run_sharing(output=SHARING_ROOT, pool_root=POOL_ROOT, baseline_root=BASE_ROOT,
                reference_root=REFERENCE_ROOT, workers=2, *, verify=False):
    output = Path(output)
    if not verify and (output / "summary.json").exists():
        raise ValueError("completed sharing bank; use sharing-verify")
    l0, refs, record = load_baseline(baseline_root, reference_root)
    _, pool_summary = _load_pool(pool_root, l0, refs, record)
    if not pool_summary["G3_prime"]["passed"]:
        raise ValueError("G3-prime failed: joint fallback calibration is required before more arms")
    jobs = base.candidate_jobs(Q, base.ARMS[1:])
    rows = _run_jobs(output, jobs, workers, base.run_episode, verify=verify)
    base._require_paths(output, jobs)
    summary = summarize_sharing(rows, l0, refs, record, pool_summary)
    if verify:
        saved = json.loads((output / "summary.json").read_text())
        if canonical(saved) != canonical(summary):
            raise ValueError("sharing aggregate differs on exact replay")
        return {"version": SHARING_VERSION, "exact_episodes": len(rows), "summary_sha256": digest(saved)}
    _save_json(output / "summary.json", summary)
    return summary
