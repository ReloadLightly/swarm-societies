"""Exploratory need-targeted baselines on the preserved physical-development cases.

This runner executes audited built-ins only. It does not load candidate source,
start model calls, or qualify the ecology or social incentives.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

from .engine import Config, initialize, observations, restore, snapshot, step
from .policies_v2 import LocalPolicy
from .policies_need_v1 import NeedTargetPolicy

VERSION = "commons-v3-need-development-v1"
BASELINES = ("need_0", "need_2")
CONDITIONS = (*BASELINES, "focal_greedy_need_0", "focal_greedy_need_2")
WEIGHTS = (0., .05, .2)
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py", "swarm_societies/commons_v3/engine.py",
           "swarm_societies/commons_v3/policies_v2.py", "swarm_societies/commons_v3/policies_need_v1.py",
           "swarm_societies/commons_v3/development_need_v1.py", "scripts/run_commons_v3_need_v1.py",
           "docs/commons-v3-foundation-protocol.md", "docs/commons-v3-foundation-protocol-v2.md",
           "docs/commons-v3-need-protocol-v1.md")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def design():
    cfg = Config(initial_patch_stock=40., need=1.2)
    cases = []
    for rate in (.12, .24, .36):
        for need in (.8, 1.2, 1.6):
            for i, seed in enumerate(range(61001, 61005)):
                cases.append({"id": f"grid-r{rate:.2f}-n{need:.1f}-s{seed}", "panel": "grid",
                              "seed": seed, "focal_id": i * 6, "horizon": 256,
                              "config": asdict(replace(cfg, renewal_rate=rate, need=need))})
    variants = (("long_horizon", {}, 512), ("keyed_priority", {"contention": "keyed_priority"}, 256),
                ("lower_stock", {"initial_patch_stock": 22.}, 256),
                ("additive", {"renewal_law": "additive"}, 256),
                ("small_inventory", {"inventory_capacity": 8.}, 256))
    for panel, changes, horizon in variants:
        for i, seed in enumerate(range(61001, 61005)):
            cases.append({"id": f"{panel}-s{seed}", "panel": panel, "seed": seed,
                          "focal_id": i * 6, "horizon": horizon, "config": asdict(replace(cfg, **changes))})
    return {"version": VERSION, "scope": "exploratory need-targeted baselines on reused development seeds; not qualification",
            "preceding_panel": "commons-v3-foundation-development-v2",
            "policy_comparison": "zero or two needs of soft inventory reserve; frozen v2 greedy focal replacements",
            "reused_cases": True, "qualification_data": False,
            "baseline_reserve_ticks": {"need_0": 0, "need_2": 2},
            "conditions": list(CONDITIONS), "wealth_weights": list(WEIGHTS), "cases": cases,
            "depletion_threshold_capacity_fraction": .1, "late_window_fraction": .25,
            "ledger_relative_tolerance": 1e-9, "experimental_model_calls": 0,
            "evolutionary_runs": 0,
            "reference_frames_case": "grid-r0.24-n1.2-s61001"}


def modes(condition, n, focal):
    if condition not in CONDITIONS:
        raise ValueError("unknown population condition")
    if type(n) is not int or n < 2 or type(focal) is not int or not 0 <= focal < n:
        raise ValueError("development comparisons require at least two agents and a valid focal ID")
    baseline = condition.removeprefix("focal_greedy_")
    return tuple("greedy" if condition.startswith("focal_greedy_") and i == focal
                 else baseline for i in range(n))


def _frame(state, kinds):
    return {"tick": state.tick, "agents": [{"id": a.id, "x": a.x, "y": a.y,
             "inventory": a.inventory, "policy": kinds[a.id]} for a in state.agents],
            "sites": [{"id": p.id, "x": p.x, "y": p.y, "stock": p.stock} for p in state.patches]}


def episode(case, condition, *, spatial=False):
    cfg, horizon = Config(**case["config"]), case["horizon"]
    state = initialize(cfg, case["seed"])
    kinds = modes(condition, cfg.n_agents, case["focal_id"])
    policies = [LocalPolicy("greedy") if kind == "greedy" else NeedTargetPolicy(reserve_ticks=int(kind[-1]))
                for kind in kinds]
    trajectory, frames = [], [_frame(state, kinds)] if spatial else []
    late = [0.] * cfg.n_agents
    moves = [0] * cfg.n_agents
    late_start = horizon - max(1, horizon // 4)
    max_residual = max_relative = 0.
    flow = sum(a.inventory for a in state.agents) + sum(p.stock for p in state.patches)
    weather = hashlib.sha256()
    resumed = None
    checkpoint_verified = False
    for tick in range(horizon):
        packets = observations(state)
        actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        result = step(state, actions)
        if resumed is not None:
            resumed = step(resumed, actions).state
            if resumed != result.state:
                raise ValueError("restored checkpoint diverged")
        state, ledger = result.state, result.ledger
        flow += ledger.growth + ledger.consumption + ledger.movement_cost + ledger.message_cost + ledger.harvest_cost + ledger.waste
        residual = max(abs(ledger.residual), *(abs(a.residual) for a in ledger.agents),
                       *(abs(p.residual) for p in ledger.patches))
        max_residual = max(max_residual, residual)
        max_relative = max(max_relative, residual / max(1., flow))
        if residual > 1e-9 * max(1., flow):
            raise ValueError("material accounting failed")
        if ledger.waste > 1e-9:
            raise ValueError("capacity-aware diagnostic policy wasted extracted resources")
        for a in ledger.agents:
            moves[a.id] += int(a.moved)
            if tick >= late_start:
                late[a.id] += a.consumption
        for p in ledger.patches:
            weather.update(canonical([p.weather_event_id, p.weather]))
        occupied_sites = {(p.x, p.y) for p in state.patches}
        unaffordable_returns = 0
        for agent, policy in zip(state.agents, policies):
            if (agent.x, agent.y) in occupied_sites or not policy.sites:
                continue
            distance = min(abs(agent.x - x) + abs(agent.y - y) for x, y in policy.sites.values())
            if agent.inventory < cfg.movement_cost * distance:
                unaffordable_returns += 1
        if unaffordable_returns:
            raise ValueError("diagnostic policy lost its prospective return-fuel invariant")
        trajectory.append({"tick": state.tick, "consumption": ledger.consumption,
                           "shortfall": sum(a.shortfall for a in ledger.agents),
                           "stock": result.metrics.stocks, "reserves": result.metrics.reserves,
                           "growth": ledger.growth, "growth_waste": ledger.growth_waste,
                           "movement_cost": ledger.movement_cost, "harvest_cost": ledger.harvest_cost,
                           "waste": ledger.waste, "moves": sum(a.moved for a in ledger.agents),
                           "unaffordable_known_returns": unaffordable_returns,
                           "depleted_patches": sum(p.stock < .1 * cfg.patch_capacity for p in state.patches),
                           "accounting_residual": ledger.residual})
        if spatial and state.tick in {horizon // 4, horizon // 2, horizon}:
            frames.append(_frame(state, kinds))
        if spatial and state.tick == horizon // 2:
            resumed = restore(snapshot(state))
    if resumed is not None:
        checkpoint_verified = resumed == state
    agents = []
    for agent in state.agents:
        agents.append({"id": agent.id, "policy": kinds[agent.id],
                       "consumption_per_tick": agent.consumption / horizon,
                       "shortfall_per_tick": agent.shortfall / horizon,
                       "late_consumption_per_tick": late[agent.id] / (horizon - late_start),
                       "terminal_inventory": agent.inventory,
                       "movement_steps": moves[agent.id],
                       "movement_cost": agent.movement_cost,
                       "harvest_cost": agent.harvest_cost,
                       "utility": {str(weight): (agent.consumption + weight * agent.inventory) / horizon
                                   for weight in WEIGHTS}})
    mean = lambda name: statistics.mean(row[name] for row in agents)
    summary = {"consumption_per_agent_tick": mean("consumption_per_tick"),
               "shortfall_per_agent_tick": mean("shortfall_per_tick"),
               "late_consumption_per_agent_tick": mean("late_consumption_per_tick"),
               "terminal_inventory_per_agent": mean("terminal_inventory"),
               "terminal_stock_fraction": sum(p.stock for p in state.patches) / (cfg.n_patches * cfg.patch_capacity),
               "depleted_patch_time_fraction": sum(r["depleted_patches"] for r in trajectory) / (horizon * cfg.n_patches),
               "movement_steps_per_agent": mean("movement_steps"),
               "total_movement_cost": sum(a.movement_cost for a in state.agents),
               "total_harvest_cost": sum(a.harvest_cost for a in state.agents),
               "total_waste": sum(a.waste for a in state.agents),
               "max_unaffordable_known_returns": max(row["unaffordable_known_returns"] for row in trajectory),
               "max_ledger_residual": max_residual, "max_relative_ledger_residual": max_relative}
    cohorts = {kind: {"n": kinds.count(kind), "consumption_per_tick": statistics.mean(
        a["consumption_per_tick"] for a in agents if a["policy"] == kind),
        "late_consumption_per_tick": statistics.mean(a["late_consumption_per_tick"] for a in agents if a["policy"] == kind)}
        for kind in sorted(set(kinds))}
    return {"condition": condition, "summary": summary, "agents": agents, "cohorts": cohorts,
            "trajectory": trajectory, "spatial_frames": frames, "weather_sha256": weather.hexdigest(),
            "final_state_sha256": snapshot(state)["sha256"], "checkpoint_continuation_checked": checkpoint_verified}


def run_case(case, specification):
    rows = [episode(case, condition, spatial=case["id"] == specification["reference_frames_case"])
            for condition in CONDITIONS]
    if len({row["weather_sha256"] for row in rows}) != 1:
        raise ValueError("paired weather differs between conditions")
    return {"version": VERSION, "case": case, "episodes": rows}


def descriptive(values):
    values = list(values)
    return {"mean": statistics.mean(values), "min": min(values), "max": max(values),
            "positive": sum(v > 1e-12 for v in values), "negative": sum(v < -1e-12 for v in values),
            "n": len(values)}


def aggregate(records, specification):
    grouped = {}
    for record in records:
        case = record["case"]
        key = case["panel"], case["config"]["renewal_rate"], case["config"]["need"]
        grouped.setdefault(key, []).append(record)
    cells = []
    for (panel, rate, need), rows in grouped.items():
        by_condition = {condition: [next(e for e in row["episodes"] if e["condition"] == condition)
                                    for row in rows] for condition in CONDITIONS}
        means = {condition: {key: statistics.mean(e["summary"][key] for e in episodes)
                             for key in episodes[0]["summary"]} for condition, episodes in by_condition.items()}
        focal_deviation = {}
        for baseline in BASELINES:
            differences = {key: [] for key in ("consumption", "late_consumption", "peer_consumption",
                                              "world_consumption", "terminal_inventory",
                                              *("utility_" + str(w) for w in WEIGHTS))}
            for record, before, after in zip(rows, by_condition[baseline], by_condition["focal_greedy_" + baseline]):
                focal = record["case"]["focal_id"]
                left, right = before["agents"][focal], after["agents"][focal]
                differences["consumption"].append(right["consumption_per_tick"] - left["consumption_per_tick"])
                differences["late_consumption"].append(right["late_consumption_per_tick"] - left["late_consumption_per_tick"])
                differences["terminal_inventory"].append(right["terminal_inventory"] - left["terminal_inventory"])
                peers = [i for i in range(len(before["agents"])) if i != focal]
                differences["peer_consumption"].append(statistics.mean(
                    after["agents"][i]["consumption_per_tick"] - before["agents"][i]["consumption_per_tick"] for i in peers))
                differences["world_consumption"].append(after["summary"]["consumption_per_agent_tick"] - before["summary"]["consumption_per_agent_tick"])
                for weight in WEIGHTS:
                    differences["utility_" + str(weight)].append(right["utility"][str(weight)] - left["utility"][str(weight)])
            focal_deviation[baseline] = {key: descriptive(values) for key, values in differences.items()}
        reserve_comparison = {
            key: descriptive(after["summary"][key] - before["summary"][key]
                             for before, after in zip(by_condition["need_0"], by_condition["need_2"]))
            for key in by_condition["need_0"][0]["summary"]}
        cells.append({"panel": panel, "renewal_rate": rate, "need": need, "paired_configurations": len(rows),
                      "conditions": means, "focal_deviation": focal_deviation,
                      "reserve_comparison": reserve_comparison})
    return {"version": VERSION, "scope": specification["scope"], "configurations": len(records),
            "episodes": len(records) * len(CONDITIONS), "cells": cells,
            "physical_ticks": sum(row["case"]["horizon"] * len(CONDITIONS) for row in records),
            "agent_decisions": sum(row["case"]["horizon"] * row["case"]["config"]["n_agents"] * len(CONDITIONS) for row in records),
            "max_ledger_residual": max(e["summary"]["max_ledger_residual"] for r in records for e in r["episodes"]),
            "max_relative_ledger_residual": max(e["summary"]["max_relative_ledger_residual"] for r in records for e in r["episodes"]),
            "experimental_model_calls": 0, "evolutionary_runs": 0,
            "qualification_status": "not_run",
            "qualification_note": "This development panel is not the disjoint qualification gate; no favorable result is required."}


def read_case(path):
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "cases").mkdir()
    (output / "sources").mkdir()
    pins = {}
    for name in SOURCES:
        source, destination = ROOT / name, output / "sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        pins[name] = sha(source)
    (output / "design.json").write_bytes(canonical(design()) + b"\n")
    (output / "sources.json").write_bytes(canonical(pins) + b"\n")


def check_sources(output):
    for name, expected in json.loads((output / "sources.json").read_text()).items():
        if name not in SOURCES or sha(ROOT / name) != expected or sha(output / "sources" / name) != expected:
            raise ValueError("source changed: " + name)
    if set(json.loads((output / "sources.json").read_text())) != set(SOURCES):
        raise ValueError("incomplete source freeze")
    saved = json.loads((output / "design.json").read_text())
    if canonical(saved) != canonical(design()):
        raise ValueError("development design changed")
    return saved


def expected_artifacts(specification):
    return {"design.json", "sources.json", "summary.json", *("sources/" + name for name in SOURCES),
            *("cases/" + case["id"] + ".json.gz" for case in specification["cases"])}


def run(output):
    output = Path(output)
    specification = check_sources(output)
    if (output / "manifest.json").exists():
        raise FileExistsError("completed development bank is preserved; choose a new output")
    if any(output.glob("*-failure.json")):
        raise FileExistsError("failed development bank is preserved; choose a new output")
    present = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
    if not present <= expected_artifacts(specification):
        raise ValueError("unexpected artifacts in unfinished development bank")
    records = []
    for case in specification["cases"]:
        path = output / "cases" / (case["id"] + ".json.gz")
        try:
            result = run_case(case, specification)
            if path.exists():
                if canonical(read_case(path)) != canonical(result):
                    raise ValueError("existing case differs on replay")
            else:
                with path.open("xb") as raw:
                    with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as stream:
                        stream.write(canonical(result))
            records.append(result)
            print(json.dumps({"case": case["id"], "status": "ok"}), flush=True)
        except Exception as error:
            with (output / (case["id"] + "-failure.json")).open("x") as stream:
                json.dump({"case": case, "error": type(error).__name__, "detail": str(error)}, stream, indent=2)
            raise
    (output / "summary.json").write_bytes(canonical(aggregate(records, specification)) + b"\n")
    files = sorted(p for p in output.rglob("*") if p.is_file())
    manifest = {"version": VERSION, "complete": True, "cases": len(records),
                "artifacts_sha256": {str(p.relative_to(output)): sha(p) for p in files}}
    with (output / "manifest.json").open("x") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return json.loads((output / "summary.json").read_text())


def verify(output, *, replay=True):
    output = Path(output)
    specification = check_sources(output)
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest.get("version") != VERSION or manifest.get("complete") is not True:
        raise ValueError("incomplete development manifest")
    expected = expected_artifacts(specification)
    if (set(manifest["artifacts_sha256"]) != expected or type(manifest["cases"]) is not int
            or manifest["cases"] != len(specification["cases"])):
        raise ValueError("unexpected evidence inventory")
    present = {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
    if present != expected | {"manifest.json"}:
        raise ValueError("unexpected evidence inventory")
    for name, digest in manifest["artifacts_sha256"].items():
        if sha(output / name) != digest:
            raise ValueError("artifact changed: " + name)
    records = []
    for case in specification["cases"]:
        saved = read_case(output / "cases" / (case["id"] + ".json.gz"))
        if (saved.get("version") != VERSION or canonical(saved["case"]) != canonical(case)
                or [e["condition"] for e in saved["episodes"]] != list(CONDITIONS)):
            raise ValueError("case inventory differs")
        if replay and canonical(saved) != canonical(run_case(case, specification)):
            raise ValueError("semantic replay differs: " + case["id"])
        records.append(saved)
    if canonical(aggregate(records, specification)) != canonical(json.loads((output / "summary.json").read_text())):
        raise ValueError("aggregate differs")
    return {"version": VERSION, "verified": True, "cases": len(records), "episodes": len(CONDITIONS) * len(records),
            "semantic_replay": replay, "manifest_sha256": sha(output / "manifest.json")}
