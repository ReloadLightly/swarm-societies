#!/usr/bin/env python3
"""Recompute saved need-panel statistics from raw primitives, without simulation.

Uses only Python's standard library. Does not import the policy, engine, study
runner, aggregate function or figure renderer. Agent consumption, inventories
and trajectories are recorded primitives, not independently replayed physics.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


CONDITIONS = ("need_0", "need_2", "focal_greedy_need_0", "focal_greedy_need_2")
WEIGHTS = (0., .05, .2)
CHECKS = 0
MAX_ERROR = 0.


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mean(values):
    values = list(values)
    return math.fsum(values) / len(values)


def number(value):
    assert type(value) in (int, float) and math.isfinite(value), value
    return value


def check(actual, expected, context):
    global CHECKS, MAX_ERROR
    actual, expected = number(actual), number(expected)
    error = abs(actual - expected)
    MAX_ERROR = max(MAX_ERROR, error)
    CHECKS += 1
    assert error <= 2e-12 * max(1., abs(actual), abs(expected)), (context, actual, expected)


def desc(values):
    values = list(values)
    return {"mean": mean(values), "min": min(values), "max": max(values),
            "positive": sum(x > 1e-12 for x in values),
            "negative": sum(x < -1e-12 for x in values), "n": len(values)}


def episode_primitives(case, episode):
    cfg, horizon = case["config"], case["horizon"]
    agents, ticks = episode["agents"], episode["trajectory"]
    n, patches = cfg["n_agents"], cfg["n_patches"]
    assert [a["id"] for a in agents] == list(range(n))
    assert [t["tick"] for t in ticks] == list(range(1, horizon + 1))
    prefix = case["id"] + "/" + episode["condition"]
    consumption = mean(number(a["consumption_per_tick"]) for a in agents)
    shortfall = mean(number(a["shortfall_per_tick"]) for a in agents)
    check(consumption, math.fsum(t["consumption"] for t in ticks) / (horizon * n), prefix + "/consumption flows")
    check(shortfall, math.fsum(t["shortfall"] for t in ticks) / (horizon * n), prefix + "/shortfall flows")
    check(consumption + shortfall, cfg["need"], prefix + "/need conservation")
    late = mean(a["late_consumption_per_tick"] for a in agents)
    late_count = max(1, horizon // 4)
    check(late, math.fsum(t["consumption"] for t in ticks[-late_count:]) / (late_count * n), prefix + "/late flows")
    inventory = mean(a["terminal_inventory"] for a in agents)
    check(inventory, ticks[-1]["reserves"] / n, prefix + "/terminal inventory flow")
    moves = mean(a["movement_steps"] for a in agents)
    check(moves, math.fsum(t["moves"] for t in ticks) / n, prefix + "/movement flows")
    for field in ("movement_cost", "harvest_cost"):
        check(math.fsum(a[field] for a in agents), math.fsum(t[field] for t in ticks), prefix + "/" + field + " flows")
    for agent in agents:
        check(agent["consumption_per_tick"] + agent["shortfall_per_tick"], cfg["need"], prefix + "/agent need")
        for weight in WEIGHTS:
            check(agent["utility"][str(weight)],
                  agent["consumption_per_tick"] + weight * agent["terminal_inventory"] / horizon,
                  prefix + "/agent utility " + str(weight))
        assert 0 <= agent["terminal_inventory"] <= cfg["inventory_capacity"] + 1e-12
    calculated = {
        "consumption_per_agent_tick": consumption,
        "shortfall_per_agent_tick": shortfall,
        "late_consumption_per_agent_tick": late,
        "terminal_inventory_per_agent": inventory,
        "terminal_stock_fraction": ticks[-1]["stock"] / (patches * cfg["patch_capacity"]),
        "depleted_patch_time_fraction": math.fsum(t["depleted_patches"] for t in ticks) / (horizon * patches),
        "movement_steps_per_agent": moves,
        "total_movement_cost": math.fsum(a["movement_cost"] for a in agents),
        "total_harvest_cost": math.fsum(a["harvest_cost"] for a in agents),
        "total_waste": math.fsum(t["waste"] for t in ticks),
        "max_unaffordable_known_returns": max(t["unaffordable_known_returns"] for t in ticks),
    }
    assert calculated["max_unaffordable_known_returns"] == 0
    assert calculated["total_waste"] <= horizon * 1e-9
    for field, value in calculated.items():
        check(episode["summary"][field], value, prefix + "/summary " + field)
    for field in ("max_ledger_residual", "max_relative_ledger_residual"):
        # Only the saved diagnostic maximum is available: per-agent and per-
        # patch residuals cannot be independently reconstructed from this bank.
        calculated[field] = number(episode["summary"][field])
    assert calculated["max_ledger_residual"] + 1e-12 >= max(abs(t["accounting_residual"]) for t in ticks)
    return calculated


def audit(source):
    manifest = json.loads((source / "manifest.json").read_text())
    assert manifest["complete"] is True
    assert manifest["version"] == "commons-v3-need-development-v1"
    for name, expected in manifest["artifacts_sha256"].items():
        assert digest(source / name) == expected, name
    design = json.loads((source / "design.json").read_text())
    saved_summary = json.loads((source / "summary.json").read_text())
    assert design["conditions"] == list(CONDITIONS)
    assert design["wealth_weights"] == list(WEIGHTS)
    assert design["experimental_model_calls"] == design["evolutionary_runs"] == 0
    assert design["qualification_data"] is False
    grouped = {}
    sources = []
    ticks = decisions = 0
    for case in design["cases"]:
        path = source / "cases" / (case["id"] + ".json.gz")
        with gzip.open(path, "rt") as stream:
            record = json.load(stream)
        assert record["case"] == case
        assert [episode["condition"] for episode in record["episodes"]] == list(CONDITIONS)
        assert len({e["weather_sha256"] for e in record["episodes"]}) == 1
        summaries = {e["condition"]: episode_primitives(case, e) for e in record["episodes"]}
        key = (case["panel"], case["config"]["renewal_rate"], case["config"]["need"])
        grouped.setdefault(key, []).append((record, summaries))
        sources.append({"path": str(path), "sha256": digest(path)})
        ticks += len(CONDITIONS) * case["horizon"]
        decisions += len(CONDITIONS) * case["horizon"] * case["config"]["n_agents"]
    check(manifest["cases"], len(design["cases"]), "manifest cases")
    check(saved_summary["configurations"], len(design["cases"]), "configurations")
    check(saved_summary["episodes"], len(design["cases"]) * len(CONDITIONS), "episodes")
    check(saved_summary["physical_ticks"], ticks, "physical ticks")
    check(saved_summary["agent_decisions"], decisions, "agent decisions")
    saved_cells = {(c["panel"], c["renewal_rate"], c["need"]): c for c in saved_summary["cells"]}
    assert len(saved_cells) == len(saved_summary["cells"])
    assert saved_cells.keys() == grouped.keys()
    calculated_cells = []
    for key, rows in grouped.items():
        saved_cell = saved_cells[key]
        check(saved_cell["paired_configurations"], len(rows), str(key) + "/pairs")
        means = {}
        for condition in CONDITIONS:
            means[condition] = {}
            for field in rows[0][1][condition]:
                value = mean(summaries[condition][field] for _, summaries in rows)
                check(saved_cell["conditions"][condition][field], value, str(key) + "/condition " + condition + "/" + field)
                means[condition][field] = value
        focal = {}
        for baseline in ("need_0", "need_2"):
            contrasts = {name: [] for name in ("consumption", "late_consumption", "peer_consumption",
                          "world_consumption", "terminal_inventory", "utility_0.0", "utility_0.05", "utility_0.2")}
            for record, primitives in rows:
                case = record["case"]
                identity = case["focal_id"]
                horizon = case["horizon"]
                episodes = {e["condition"]: {a["id"]: a for a in e["agents"]} for e in record["episodes"]}
                before, after = episodes[baseline], episodes["focal_greedy_" + baseline]
                left, right = before[identity], after[identity]
                dc = right["consumption_per_tick"] - left["consumption_per_tick"]
                di = right["terminal_inventory"] - left["terminal_inventory"]
                dp = mean(after[i]["consumption_per_tick"] - before[i]["consumption_per_tick"]
                          for i in before if i != identity)
                dw = (dc + (len(before) - 1) * dp) / len(before)
                check(dw, primitives["focal_greedy_" + baseline]["consumption_per_agent_tick"]
                      - primitives[baseline]["consumption_per_agent_tick"], str(key) + "/world/focal/peer identity")
                contrasts["consumption"].append(dc)
                contrasts["late_consumption"].append(right["late_consumption_per_tick"] - left["late_consumption_per_tick"])
                contrasts["terminal_inventory"].append(di)
                contrasts["peer_consumption"].append(dp)
                contrasts["world_consumption"].append(dw)
                for weight in WEIGHTS:
                    # Reconstruct from consumption and inventory; do not reuse
                    # the runner's stored per-agent utility or focal summary.
                    contrasts["utility_" + str(weight)].append(dc + weight * di / horizon)
            focal[baseline] = {name: desc(values) for name, values in contrasts.items()}
            for name, stats in focal[baseline].items():
                for stat, value in stats.items():
                    check(saved_cell["focal_deviation"][baseline][name][stat], value,
                          str(key) + "/focal " + baseline + "/" + name + "/" + stat)
        reserve = {field: desc(summaries["need_2"][field] - summaries["need_0"][field]
                              for _, summaries in rows) for field in rows[0][1]["need_0"]}
        for field, stats in reserve.items():
            for stat, value in stats.items():
                check(saved_cell["reserve_comparison"][field][stat], value, str(key) + "/reserve/" + field + "/" + stat)
        calculated_cells.append({"panel": key[0], "renewal_rate": key[1], "need": key[2],
                                 "pairs": len(rows), "conditions": means, "focal_deviation": focal,
                                 "reserve_comparison": reserve})
    return {"version": "commons-v3-need-independent-primitive-audit-v1", "verified": True,
            "scope": "Independent standard-library aggregation of saved primitives; no simulation or qualification.",
            "qualification_status": "not_run", "experimental_model_calls": 0, "evolutionary_runs": 0,
            "limitations": ["Recorded primitive fields are inputs, not independently replayed physical states.",
                            "Residual maxima are saved diagnostics, not reconstructible per-agent/patch primitives."],
            "cases": len(design["cases"]), "episodes": len(design["cases"]) * len(CONDITIONS),
            "physical_ticks": ticks, "agent_decisions": decisions,
            "reference_case": design["reference_frames_case"], "numeric_checks": CHECKS,
            "max_absolute_numeric_difference": MAX_ERROR, "tolerance_relative_to_max_one": 2e-12,
            "manifest_sha256": digest(source / "manifest.json"), "script_sha256": digest(__file__),
            "sources": sources, "cells": calculated_cells}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("evidence/commons-v3-need-v1"))
    parser.add_argument("--output", type=Path, default=Path("runs/commons-v3-need-v1-validation/independent_audit.json"))
    args = parser.parse_args()
    assert not args.output.exists(), "audit output must be a new file"
    result = audit(args.source)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("verified", "cases", "episodes", "numeric_checks", "max_absolute_numeric_difference")}, sort_keys=True))


if __name__ == "__main__":
    main()
