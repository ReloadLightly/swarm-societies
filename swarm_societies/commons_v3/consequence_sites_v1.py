"""Ticket B only: finite development references and Gate G1.

No learner, fresh evaluation, or changed physical/policy source is introduced.
Case compression, immutable writes and canonical replay comparisons reuse the
existing navigation tooling. Selection is global across the four cells.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import statistics as st

from . import engine_sites_v1 as engine
from . import worlds_sites_v1 as worlds
from .development_navigation_v1 import canonical, digest, read_case, _save_json, _save_record
from .policies_sites_v1 import ReferenceForager

VERSION = "commons-v3-world-model-consequence-v1"
SEEDS = (90001, 90002, 90003, 90004)  # Reused scratch development seeds, never evaluation.
PHIS = (.375, .5)
FIXED_CAPACITIES = (20., 30., 40.)
HORIZON = 512
CONDITIONS = ("moderate", "wide")
NEEDS = (1.2, 1.6)


def candidate_jobs(arm, phi=None):
    if arm == "R-oracle":
        if phi is not None:
            raise ValueError("oracle candidates include both floor fractions")
        parameters = [(p, None) for p in PHIS]
    elif arm in ("R-fixed", "R-greedy") and phi in PHIS:
        parameters = [(phi, k) for k in FIXED_CAPACITIES] if arm == "R-fixed" else [(phi, None)]
    else:
        raise ValueError("unknown reference arm or missing selected phi")
    return [{"condition": condition, "need": need, "seed": seed,
             "arm": arm, "phi": p, "fixed_capacity": capacity}
            for p, capacity in parameters for condition in CONDITIONS
            for need in NEEDS for seed in SEEDS]


def case_id(job):
    return (f"{job['condition']}-n{job['need']:g}-s{job['seed']}-{job['arm']}"
            f"-phi{job['phi']:g}-K{job['fixed_capacity']}")


def run_episode(job):
    if job not in candidate_jobs(job["arm"], None if job["arm"] == "R-oracle" else job["phi"]):
        raise ValueError("case is outside the contracted development panel")
    state = worlds.initialize(job["condition"], job["need"], job["seed"])
    initial = engine.snapshot(state)
    capacities = state.config.site_capacities
    n = state.config.n_agents
    parameters = {"phi": job["phi"], "fixed_capacity": job["fixed_capacity"]}
    if job["arm"] == "R-oracle":
        parameters["true_capacities"] = capacities
    policies = [ReferenceForager(job["arm"], **parameters) for _ in range(n)]
    trajectory = hashlib.sha256(canonical(initial) + b"\n")
    weather = hashlib.sha256()
    frames, late_baseline = [], [0.] * n
    patch_at = {(p.x, p.y): p.id for p in state.patches}
    max_residual = 0.
    for tick in range(HORIZON):
        packets = engine.observations(state)
        actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        result = engine.step(state, actions)
        state, ledger = result.state, result.ledger
        trajectory.update(canonical({"state": asdict(state), "actions": [asdict(a) for a in actions],
                                     "memories": [p.memory() for p in policies],
                                     "ledger": asdict(ledger)}) + b"\n")
        weather.update(canonical([p.weather for p in ledger.patches]) + b"\n")
        # Consumption happens after movement/extraction and before regrowth.
        # This diagnostic counts food remaining at that time, not new growth.
        hungry_next_to_food = []
        for agent, row in zip(state.agents, ledger.agents):
            site = patch_at.get((agent.x, agent.y))
            if (site is not None and row.shortfall > 1e-12
                    and ledger.patches[site].stock_after_harvest > job["phi"] * capacities[site]):
                hungry_next_to_food.append(row.shortfall)
        collapse = sum(p.stock < .1 * capacities[p.id] for p in state.patches)
        frames.append({"tick": state.tick, "consumption": ledger.consumption,
                       "starvation_next_to_food_shortfall": math.fsum(hungry_next_to_food),
                       "starvation_next_to_food_agents": len(hungry_next_to_food),
                       "collapsed_sites": collapse,
                       "message_bytes": sum(a.message_bytes for a in ledger.agents),
                       "message_cost": ledger.message_cost})
        max_residual = max(max_residual, abs(ledger.residual),
                           *(abs(a.residual) for a in ledger.agents),
                           *(abs(p.residual) for p in ledger.patches))
        if state.tick == 3 * HORIZON // 4:
            late_baseline = [a.consumption for a in state.agents]
    agents = [{"id": a.id, "share_of_need": a.consumption / (HORIZON * job["need"]),
               "final_quarter_share_of_need": (a.consumption - late_baseline[a.id]) / (HORIZON / 4 * job["need"])}
              for a in state.agents]
    denominator = n * HORIZON * job["need"]
    summary = {
        "share_of_need": math.fsum(a.consumption for a in state.agents) / denominator,
        "final_quarter_share_of_need": st.mean(a["final_quarter_share_of_need"] for a in agents),
        "starvation_next_to_food_share_of_need": math.fsum(f["starvation_next_to_food_shortfall"] for f in frames) / denominator,
        "starvation_next_to_food_agent_tick_fraction": sum(f["starvation_next_to_food_agents"] for f in frames) / (n * HORIZON),
        "local_collapse_site_tick_fraction": sum(f["collapsed_sites"] for f in frames) / (len(capacities) * HORIZON),
        "message_bytes": sum(f["message_bytes"] for f in frames),
        "message_cost": math.fsum(f["message_cost"] for f in frames),
        "agent_consumption_share_min": min(a["share_of_need"] for a in agents),
        "agent_consumption_share_max": max(a["share_of_need"] for a in agents),
        "agent_consumption_share_sd": st.pstdev(a["share_of_need"] for a in agents),
        "max_ledger_residual": max_residual,
    }
    return {"version": VERSION, "job": job, "horizon": HORIZON,
            "initial_snapshot": initial, "final_snapshot": engine.snapshot(state),
            "trajectory_sha256": trajectory.hexdigest(), "weather_sha256": weather.hexdigest(),
            "summary": summary, "agents": agents, "ticks": frames}


def _require_jobs(rows, jobs):
    actual = [canonical(row["job"]) for row in rows]
    expected = {canonical(job) for job in jobs}
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("development case inventory differs")
    for row in rows:
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in row["summary"].values()):
            raise ValueError("development summary values must be finite numbers")


def _select(rows, arm, parameter, values, jobs):
    rows = [r for r in rows if r["job"]["arm"] == arm]
    _require_jobs(rows, jobs)
    scores = []
    for value in values:
        group = [r for r in rows if r["job"][parameter] == value]
        scores.append({parameter: value, "episodes": len(group),
                       "share_of_need": st.mean(r["summary"]["share_of_need"] for r in group),
                       "final_quarter_share_of_need": st.mean(r["summary"]["final_quarter_share_of_need"] for r in group)})
    winner = min(scores, key=lambda r: (-r["share_of_need"], -r["final_quarter_share_of_need"], r[parameter]))
    return {"selected": winner[parameter], "candidates": scores}


def select_oracle(rows):
    return _select(rows, "R-oracle", "phi", PHIS, candidate_jobs("R-oracle"))


def select_fixed(rows, phi):
    return _select(rows, "R-fixed", "fixed_capacity", FIXED_CAPACITIES, candidate_jobs("R-fixed", phi))


def descriptive(values):
    values = list(values)
    if len(values) != 4:
        raise ValueError("descriptive interval requires the four development seeds")
    mean = st.mean(values)
    half = 3.182446305284263 * st.stdev(values) / math.sqrt(4)
    return {"n": 4, "mean": mean, "ci95": [mean - half, mean + half],
            "min": min(values), "max": max(values)}


def summarize(rows):
    oracle = select_oracle(rows)
    phi = oracle["selected"]
    fixed = select_fixed(rows, phi)
    jobs = candidate_jobs("R-oracle") + candidate_jobs("R-fixed", phi) + candidate_jobs("R-greedy", phi)
    _require_jobs(rows, jobs)
    for condition in CONDITIONS:
        for need in NEEDS:
            for seed in SEEDS:
                paired = [r for r in rows if (r["job"]["condition"], r["job"]["need"], r["job"]["seed"]) == (condition, need, seed)]
                if len({r["initial_snapshot"]["sha256"] for r in paired}) != 1 or len({r["weather_sha256"] for r in paired}) != 1:
                    raise ValueError("paired initial world or weather differs")
    selected = [r for r in rows if (r["job"]["phi"] == phi and
                (r["job"]["arm"] != "R-fixed" or r["job"]["fixed_capacity"] == fixed["selected"]))]
    cells = []
    for condition in CONDITIONS:
        for need in NEEDS:
            group = [r for r in selected if (r["job"]["condition"], r["job"]["need"]) == (condition, need)]
            by_arm = {arm: {r["job"]["seed"]: r for r in group if r["job"]["arm"] == arm}
                      for arm in ("R-oracle", "R-fixed", "R-greedy")}
            differences = [{"seed": s,
                            "share_of_need": by_arm["R-oracle"][s]["summary"]["share_of_need"] - by_arm["R-fixed"][s]["summary"]["share_of_need"],
                            "final_quarter_share_of_need": by_arm["R-oracle"][s]["summary"]["final_quarter_share_of_need"] - by_arm["R-fixed"][s]["summary"]["final_quarter_share_of_need"]}
                           for s in SEEDS]
            cells.append({"condition": condition, "need": need,
                          "arms": {arm: {key: descriptive(r["summary"][key] for r in by_seed.values())
                                         for key in next(iter(by_seed.values()))["summary"]}
                                   for arm, by_seed in by_arm.items()},
                          "paired_differences": differences,
                          "oracle_minus_fixed": {key: descriptive(d[key] for d in differences)
                                                  for key in ("share_of_need", "final_quarter_share_of_need")}})
    gate_cell = next(c for c in cells if c["condition"] == "wide" and c["need"] == 1.6)
    contrast = gate_cell["oracle_minus_fixed"]["share_of_need"]
    return {"version": VERSION, "scope": "development only; selected on these same four reused seeds",
            "seeds": list(SEEDS), "horizon": HORIZON, "episodes": len(rows), "selected_episodes": len(selected),
            "selection_rule": "equal-weight mean consumption over all 16 cases; final-quarter mean then smaller parameter break ties",
            "oracle_selection": oracle, "fixed_selection": fixed, "cells": cells,
            "G1": {"threshold": .08, "contrast": contrast, "passed": contrast["mean"] >= .08,
                   "decision": "stop at G1 and report to Roland; no Ticket C"},
            "experimental_model_calls": 0, "evolutionary_runs": 0}


def _path(output, job):
    return Path(output) / "cases" / (case_id(job) + ".json.gz")


def _run_jobs(output, jobs, workers):
    rows, missing = [], []
    for job in jobs:
        path = _path(output, job)
        if path.exists():
            row = read_case(path)
            if row["job"] != job:
                raise ValueError("saved case has different job")
            rows.append(row)
        else:
            missing.append(job)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(run_episode, missing):
            _save_record(_path(output, row["job"]), row)
            rows.append(row)
    return rows


def run(output, workers=2):
    output = Path(output)
    if (output / "summary.json").exists():
        raise ValueError("completed development bank; use verify")
    rows = _run_jobs(output, candidate_jobs("R-oracle"), workers)
    phi = select_oracle(rows)["selected"]
    rows.extend(_run_jobs(output, candidate_jobs("R-fixed", phi) + candidate_jobs("R-greedy", phi), workers))
    summary = summarize(rows)
    _save_json(output / "summary.json", summary)
    return summary


def verify(output, workers=2):
    output = Path(output)
    import json
    saved = json.loads((output / "summary.json").read_text())
    phi = saved["oracle_selection"]["selected"]
    jobs = candidate_jobs("R-oracle") + candidate_jobs("R-fixed", phi) + candidate_jobs("R-greedy", phi)
    paths = {_path(output, job) for job in jobs}
    if set((output / "cases").glob("*.json.gz")) != paths:
        raise ValueError("saved case inventory differs")
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for job, replay in zip(jobs, pool.map(run_episode, jobs)):
            row = read_case(_path(output, job))
            if canonical(row) != canonical(replay):
                raise ValueError("exact replay differs: " + case_id(job))
            rows.append(row)
    if canonical(summarize(rows)) != canonical(saved):
        raise ValueError("summary differs on replay")
    return {"version": VERSION, "exact_replays": len(rows), "summary_sha256": digest(saved), "G1": saved["G1"]}
