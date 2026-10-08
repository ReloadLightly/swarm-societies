"""Approved A2: joint-rate calibration before one bounded fallback comparison.

No prior search, controller retuning, fresh seeds or second fallback belongs
here. The physical rate remains .24; the agent observation adapter hides it.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import statistics as st

from . import development_learning_sites_v1 as base
from . import development_pool_sites_v1 as pool
from . import engine_sites_v1 as engine
from . import worlds_sites_v1 as worlds
from .development_navigation_v1 import canonical, digest, read_case, _save_json
from .development_learning_sites_v1 import (BeliefMetrics, BIASED_IDS,
    BELIEF_CHECKPOINTS, PAIR_COLUMNS, HORIZON, PHI, SEEDS,
    physical_initial_digest, _material_frame, _worker_heartbeat)

VERSION = "commons-v3-joint-learning-development-sites-v1"
FALLBACK_ROOT = "evidence/commons-v3-joint-learning-development-v1"
CALIBRATION_ROOT = "evidence/commons-v3-joint-site-calibration-v1"
RATE_PRIOR = {"distribution": "log_uniform", "low": .12, "high": .48,
              "shared_across_sites": True}
Q = .25


def _prior(site=0, biased=False):
    from .calibration_joint_sites_v1 import RESOLUTION
    from .policies_joint_sites_v1 import new_prior
    return new_prior(site=site, biased=biased, **RESOLUTION)


def fallback_jobs():
    return [*base.candidate_jobs(Q), *pool.pool_jobs()]


def _record_unknown_episode(job, state, policies, coordinator=None, horizon=HORIZON):
    from .observations_joint_sites_v1 import observations
    initial = engine.snapshot(state)
    capacities, population = state.config.site_capacities, len(state.agents)
    biased = tuple(identity for identity in BIASED_IDS if identity < population) if job["arm"].endswith("-biased") else ()
    measurement = BeliefMetrics(capacities, population, biased, prior_factory=_prior)
    trajectory = hashlib.sha256(canonical(initial) + b"\n")
    weather = hashlib.sha256()
    frames, epistemic, checkpoints = [], [], []
    late_baseline, previous_result = [0.] * population, None
    max_residual = 0.
    patch_at = {(p.x, p.y): p.id for p in state.patches}
    for tick in range(horizon + 1):
        packets = observations(state, previous_result)
        if coordinator is not None:
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
            "final_pool_memory_sha256": digest(coordinator.memory()) if coordinator is not None else None,
            "rate_known": False, "rate_prior": dict(RATE_PRIOR),
            "summary": summary, "agents": agents, "ticks": frames, "belief_ticks": epistemic,
            "belief_pair_columns": list(PAIR_COLUMNS), "belief_checkpoints": checkpoints,
            "first_within10_columns": ["agent", "site", "first_tick_or_null"],
            "first_within10": measurement.first_accuracy_rows()}


def run_episode(job):
    if job not in fallback_jobs():
        raise ValueError("case is outside the single approved fallback menu")
    from .policies_joint_sites_v1 import UnknownForager, UnknownPoolCoordinator, UnknownPoolForager
    from .calibration_joint_sites_v1 import RESOLUTION
    state = worlds.initialize(job["condition"], job["need"], job["seed"])
    state = replace(state, config=replace(state.config, max_messages=4))
    if job["arm"] == "R-pool":
        coordinator = UnknownPoolCoordinator(**RESOLUTION)
        policies = [UnknownPoolForager(coordinator, agent.id, phi=PHI, q=Q) for agent in state.agents]
    else:
        coordinator = None
        policies = [UnknownForager("L0", phi=PHI, q=Q, **RESOLUTION) for _ in state.agents]
    return _record_unknown_episode(job, state, policies, coordinator)


def summarize(rows, references, known_pool_summary, calibration_record):
    base._require_jobs(rows, fallback_jobs())
    if any(row.get("version") != VERSION or row.get("rate_known") is not False
           or row.get("rate_prior") != RATE_PRIOR for row in rows):
        raise ValueError("fallback records require the approved unknown-rate model")
    if known_pool_summary["G3_prime"]["passed"]:
        raise ValueError("A2 is authorized only by a failed A1 comparison")
    if not calibration_record["G2"]["passed"]:
        raise ValueError("joint G2 calibration must pass before fallback episodes")
    l0 = [row for row in rows if row["job"]["arm"] == "L0"]
    pooled = [row for row in rows if row["job"]["arm"] == "R-pool"]
    base._paired_worlds(rows, references)
    gate = pool.g3_prime(pooled, l0)
    gate["decision"] = ("run declared sharing development arms under the approved unknown-rate model"
                        if gate["passed"] else "stop the contracted design; no further fallback")
    return {"version": VERSION, "amendment": "A2", "rate_known": False, "rate_prior": dict(RATE_PRIOR),
        "scope": "single fallback development comparison on the same four reused seeds",
        "seeds": list(SEEDS), "horizon": HORIZON, "phi": PHI, "q": Q, "episodes": len(rows),
        "reference_episodes_reused": len(references),
        "known_rate_pool_summary_sha256": digest(known_pool_summary),
        "joint_calibration": calibration_record, "G3_prime": gate,
        "cells": pool.comparison_cells(rows, references, include_pool=True),
        "experimental_model_calls": 0, "evolutionary_runs": 0, "fresh_evaluation_episodes": 0,
        "decision": gate["decision"]}


def _load_prerequisites(pool_root, baseline_root, reference_root, calibration_root):
    # The calibration loader is provided by the separate, independently
    # generated synthetic G2 implementation. It validates its aggregate.
    from .calibration_joint_sites_v1 import load_passed
    l0, references, baseline_record = pool.load_baseline(baseline_root, reference_root)
    _, saved_pool = pool._load_pool(pool_root, l0, references, baseline_record)
    if saved_pool["G3_prime"]["passed"]:
        raise ValueError("A2 cannot run after a passed A1 gate")
    calibration = load_passed(calibration_root)
    if not calibration["G2"]["passed"]:
        raise ValueError("joint G2 must pass before fallback development")
    return references, saved_pool, calibration


def run(output=FALLBACK_ROOT, *, pool_root=pool.POOL_ROOT, baseline_root=pool.BASE_ROOT,
        reference_root=pool.REFERENCE_ROOT, calibration_root=CALIBRATION_ROOT, workers=2, verify=False):
    output = Path(output)
    if not verify and (output / "summary.json").exists():
        raise ValueError("completed fallback bank; use verify")
    references, known, calibration = _load_prerequisites(pool_root, baseline_root, reference_root, calibration_root)
    jobs = fallback_jobs()
    rows = pool._run_jobs(output, jobs, workers, run_episode, verify=verify)
    base._require_paths(output, jobs)
    summary = summarize(rows, references, known, calibration)
    if verify:
        saved = json.loads((output / "summary.json").read_text())
        if canonical(summary) != canonical(saved):
            raise ValueError("fallback aggregate differs on replay")
        return {"version": VERSION, "exact_episodes": len(rows), "summary_sha256": digest(saved), "G3_prime": saved["G3_prime"]}
    _save_json(output / "summary.json", summary)
    return summary
