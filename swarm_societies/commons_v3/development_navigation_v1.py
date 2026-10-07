"""Frozen numerical selection and fresh comparisons of local commons foragers.

Only audited built-in policies execute. Tuning and evaluation are separately
sealed; evaluation cannot influence the finite-grid population selection.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import tempfile

from .engine import Config, initialize, observations, restore, snapshot, step
from .policies_need_v1 import NeedTargetPolicy
from .policies_navigation_v1 import ForagerPolicy

VERSION = "commons-v3-navigation-development-v1"
SELECTION_VERSION = "commons-v3-navigation-selection-v1"
CONDITIONS = ("legacy_need2", "fixed_forager", "fixed_floor", "selected",
              "focal_aggressive_selected", "all_aggressive")
WEIGHTS = (0., .05, .2)
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py",
           "swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/policies_need_v1.py",
           "swarm_societies/commons_v3/policies_navigation_v1.py",
           "swarm_societies/commons_v3/development_navigation_v1.py",
           "scripts/run_commons_v3_navigation_v1.py", "docs/commons-v3-foundation-protocol.md",
           "docs/commons-v3-foundation-protocol-v2.md", "docs/commons-v3-need-protocol-v1.md",
           "docs/commons-v3-navigation-protocol-v1.md")
POLICY_SOURCE = "swarm_societies/commons_v3/policies_navigation_v1.py"
FIXED_FORAGER = {"reserve_ticks": 2, "stock_floor_fraction": 0., "route_mode": "net_yield"}
FIXED_FLOOR = {**FIXED_FORAGER, "stock_floor_fraction": .5}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def candidates():
    return [{"id": f"r{reserve}-f{int(floor * 100):02d}-{route}",
             "parameters": {"reserve_ticks": reserve, "stock_floor_fraction": floor, "route_mode": route}}
            for reserve in (0, 2, 4) for floor in (0., .25, .5) for route in ("nearest", "net_yield")]


def physical_cases(seeds, *, sensitivities):
    cfg = Config(initial_patch_stock=40., need=1.2)
    cases = []
    for rate in (.12, .24, .36):
        for need in (.8, 1.2, 1.6):
            for i, seed in enumerate(seeds):
                cases.append({"id": f"grid-r{rate:.2f}-n{need:.1f}-s{seed}", "panel": "grid",
                              "seed": seed, "focal_id": i * 6, "horizon": 256,
                              "config": asdict(replace(cfg, renewal_rate=rate, need=need))})
    if sensitivities:
        variants = (("long_horizon", {}, 512), ("keyed_priority", {"contention": "keyed_priority"}, 256),
                    ("lower_stock", {"initial_patch_stock": 22.}, 256),
                    ("additive", {"renewal_law": "additive"}, 256),
                    ("small_inventory", {"inventory_capacity": 8.}, 256))
        for panel, changes, horizon in variants:
            for i, seed in enumerate(seeds):
                cases.append({"id": f"{panel}-s{seed}", "panel": panel, "seed": seed,
                              "focal_id": i * 6, "horizon": horizon,
                              "config": asdict(replace(cfg, **changes))})
    return cases


def design():
    tuning_seeds, evaluation_seeds = [62001, 62002], [63001, 63002, 63003, 63004]
    return {"version": VERSION,
            "scope": "exploratory fixed-family numerical selection and disjoint-seed comparison; not ecological or incentive qualification",
            "candidates": candidates(), "fixed_forager": FIXED_FORAGER, "fixed_floor": FIXED_FLOOR,
            "tuning": {"seeds": tuning_seeds, "cases": physical_cases(tuning_seeds, sensitivities=False)},
            "evaluation": {"seeds": evaluation_seeds,
                           "cases": physical_cases(evaluation_seeds, sensitivities=True),
                           "conditions": list(CONDITIONS), "reference_frames_case": "grid-r0.24-n1.2-s63001"},
            "selection_rule": {"primary": "mean population consumption per agent-tick divided by case need, equally weighted cases",
                               "secondary": "mean final-quarter population consumption divided by case need",
                               "tie_break": "lexicographically smallest candidate ID; exact float comparison",
                               "failure_rule": "halt and preserve the complete failed bank; never omit unsuccessful cases"},
            "wealth_weights": list(WEIGHTS), "depletion_threshold_capacity_fraction": .1,
            "late_window_fraction": .25, "ledger_relative_tolerance": 1e-9,
            "experimental_model_calls": 0, "evolutionary_runs": 0, "numerical_selection_runs": 1,
            "qualification_data": False}


def population(condition, n, focal, *, selected=None, candidate=None):
    if type(n) is not int or n < 2 or type(focal) is not int or not 0 <= focal < n:
        raise ValueError("comparisons require at least two agents and a valid focal ID")
    if candidate is not None:
        parameters = candidate["parameters"]
        kinds = (candidate["id"],) * n
    elif condition == "legacy_need2":
        return (condition,) * n, [NeedTargetPolicy(reserve_ticks=2) for _ in range(n)]
    elif condition in ("fixed_forager", "fixed_floor"):
        parameters = FIXED_FORAGER if condition == "fixed_forager" else FIXED_FLOOR
        kinds = (condition,) * n
    elif condition in ("selected", "focal_aggressive_selected", "all_aggressive") and selected is not None:
        parameters = selected["parameters"]
        kinds = tuple("aggressive" if condition == "all_aggressive" or
                      (condition == "focal_aggressive_selected" and i == focal) else "selected" for i in range(n))
    else:
        raise ValueError("unknown condition or missing selected candidate")
    return kinds, [ForagerPolicy(**parameters, aggressive=kind == "aggressive") for kind in kinds]


def _frame(state, kinds):
    return {"tick": state.tick, "agents": [{"id": a.id, "x": a.x, "y": a.y,
             "inventory": a.inventory, "policy": kinds[a.id]} for a in state.agents],
            "sites": [{"id": p.id, "x": p.x, "y": p.y, "stock": p.stock} for p in state.patches]}


def episode(case, condition, *, selected=None, candidate=None, spatial=False):
    cfg, horizon = Config(**case["config"]), case["horizon"]
    state = initialize(cfg, case["seed"])
    kinds, policies = population(condition, cfg.n_agents, case["focal_id"], selected=selected, candidate=candidate)
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
        occupied_cells = {(agent.x, agent.y) for agent in state.agents}
        off_site = {agent.id for agent in state.agents if (agent.x, agent.y) not in occupied_sites}
        trajectory.append({"tick": state.tick, "consumption": ledger.consumption,
                           "shortfall": sum(a.shortfall for a in ledger.agents),
                           "stock": result.metrics.stocks, "reserves": result.metrics.reserves,
                           "growth": ledger.growth, "growth_waste": ledger.growth_waste,
                           "movement_cost": ledger.movement_cost, "harvest_cost": ledger.harvest_cost,
                           "waste": ledger.waste, "moves": sum(a.moved for a in ledger.agents),
                           "unaffordable_known_returns": unaffordable_returns,
                           "off_site_agents": len(off_site),
                           "hungry_off_site_agents": sum(a.id in off_site and a.shortfall > 0 for a in ledger.agents),
                           "unoccupied_stock_fraction": sum(p.stock for p in state.patches if (p.x, p.y) not in occupied_cells)
                                                        / (cfg.n_patches * cfg.patch_capacity),
                           "mean_known_sites": statistics.mean(len(policy.sites) for policy in policies),
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
               "mean_off_site_agent_fraction": statistics.mean(row["off_site_agents"] / cfg.n_agents for row in trajectory),
               "mean_hungry_off_site_agent_fraction": statistics.mean(row["hungry_off_site_agents"] / cfg.n_agents for row in trajectory),
               "terminal_unoccupied_stock_fraction": trajectory[-1]["unoccupied_stock_fraction"],
               "terminal_mean_known_sites": trajectory[-1]["mean_known_sites"],
               "max_ledger_residual": max_residual, "max_relative_ledger_residual": max_relative}
    cohorts = {kind: {"n": kinds.count(kind), "consumption_per_tick": statistics.mean(
        a["consumption_per_tick"] for a in agents if a["policy"] == kind),
        "late_consumption_per_tick": statistics.mean(a["late_consumption_per_tick"] for a in agents if a["policy"] == kind)}
        for kind in sorted(set(kinds))}
    return {"condition": condition, "summary": summary, "agents": agents, "cohorts": cohorts,
            "trajectory": trajectory, "spatial_frames": frames, "weather_sha256": weather.hexdigest(),
            "final_state_sha256": snapshot(state)["sha256"], "checkpoint_continuation_checked": checkpoint_verified}



def tuning_record(case, candidate):
    return {"version": VERSION, "case": case, "candidate": candidate,
            "episode": episode(case, candidate["id"], candidate=candidate)}


def evaluation_record(case, specification, selected):
    rows = [episode(case, condition, selected=selected,
                    spatial=case["id"] == specification["evaluation"]["reference_frames_case"])
            for condition in CONDITIONS]
    if len({row["weather_sha256"] for row in rows}) != 1:
        raise ValueError("paired evaluation weather differs")
    return {"version": VERSION, "case": case, "selected_candidate": selected, "episodes": rows}


def descriptive(values):
    values = list(values)
    return {"mean": statistics.mean(values), "min": min(values), "max": max(values),
            "positive": sum(v > 1e-12 for v in values), "negative": sum(v < -1e-12 for v in values), "n": len(values)}


def tuning_summary(records, specification):
    expected = {(case["id"], candidate["id"]) for case in specification["tuning"]["cases"]
                for candidate in specification["candidates"]}
    observed = [(row["case"]["id"], row["candidate"]["id"]) for row in records]
    if len(observed) != len(expected) or set(observed) != expected:
        raise ValueError("tuning record inventory differs")
    for case in specification["tuning"]["cases"]:
        weather = {row["episode"]["weather_sha256"] for row in records if row["case"]["id"] == case["id"]}
        if len(weather) != 1:
            raise ValueError("paired tuning weather differs")
    scores = []
    for candidate in specification["candidates"]:
        rows = [row for row in records if row["candidate"]["id"] == candidate["id"]]
        primary = [row["episode"]["summary"]["consumption_per_agent_tick"] / row["case"]["config"]["need"] for row in rows]
        late = [row["episode"]["summary"]["late_consumption_per_agent_tick"] / row["case"]["config"]["need"] for row in rows]
        cells = {}
        for row, value in zip(rows, primary):
            cfg = row["case"]["config"]
            cells.setdefault((cfg["renewal_rate"], cfg["need"]), []).append(value)
        scores.append({**candidate, "episodes": len(rows), "score": statistics.mean(primary),
                       "late_score": statistics.mean(late), "worst_case_score": min(primary),
                       "worst_cell_score": min(statistics.mean(values) for values in cells.values())})
    ordered = sorted(scores, key=lambda row: (-row["score"], -row["late_score"], row["id"]))
    return {"version": VERSION, "phase": "tuning", "scope": specification["scope"],
            "candidates": scores, "selected_candidate_id": ordered[0]["id"],
            "configurations": len(specification["tuning"]["cases"]), "episodes": len(records),
            "physical_ticks": sum(row["case"]["horizon"] for row in records),
            "agent_decisions": sum(row["case"]["horizon"] * row["case"]["config"]["n_agents"] for row in records),
            "max_ledger_residual": max(row["episode"]["summary"]["max_ledger_residual"] for row in records),
            "experimental_model_calls": 0, "evolutionary_runs": 0, "numerical_selection_runs": 1}


def aggregate(records, specification):
    grouped = {}
    for record in records:
        cfg = record["case"]["config"]
        grouped.setdefault((record["case"]["panel"], cfg["renewal_rate"], cfg["need"]), []).append(record)
    cells = []
    for (panel, rate, need), rows in grouped.items():
        by_condition = {condition: [next(e for e in row["episodes"] if e["condition"] == condition) for row in rows]
                        for condition in CONDITIONS}
        means = {condition: {key: statistics.mean(e["summary"][key] for e in episodes)
                             for key in episodes[0]["summary"]} for condition, episodes in by_condition.items()}
        fixed_contrasts = {baseline: {key: descriptive(after["summary"][key] - before["summary"][key]
                                 for before, after in zip(by_condition[baseline], by_condition["selected"]))
                         for key in by_condition[baseline][0]["summary"]}
                         for baseline in ("legacy_need2", "fixed_forager", "fixed_floor")}
        differences = {key: [] for key in ("consumption", "late_consumption", "peer_consumption", "world_consumption",
                                          "terminal_inventory", *("utility_" + str(w) for w in WEIGHTS))}
        for record, before, after in zip(rows, by_condition["selected"], by_condition["focal_aggressive_selected"]):
            focal = record["case"]["focal_id"]
            left, right = before["agents"][focal], after["agents"][focal]
            differences["consumption"].append(right["consumption_per_tick"] - left["consumption_per_tick"])
            differences["late_consumption"].append(right["late_consumption_per_tick"] - left["late_consumption_per_tick"])
            differences["terminal_inventory"].append(right["terminal_inventory"] - left["terminal_inventory"])
            differences["peer_consumption"].append(statistics.mean(
                after["agents"][i]["consumption_per_tick"] - before["agents"][i]["consumption_per_tick"]
                for i in range(len(before["agents"])) if i != focal))
            differences["world_consumption"].append(after["summary"]["consumption_per_agent_tick"] - before["summary"]["consumption_per_agent_tick"])
            for weight in WEIGHTS:
                differences["utility_" + str(weight)].append(right["utility"][str(weight)] - left["utility"][str(weight)])
        widespread = {key: descriptive(after["summary"][key] - before["summary"][key]
                                      for before, after in zip(by_condition["selected"], by_condition["all_aggressive"]))
                      for key in by_condition["selected"][0]["summary"]}
        cells.append({"panel": panel, "renewal_rate": rate, "need": need, "paired_configurations": len(rows),
                      "conditions": means, "selected_minus_fixed": fixed_contrasts,
                      "focal_deviation": {key: descriptive(values) for key, values in differences.items()},
                      "all_aggressive_minus_selected": widespread})
    return {"version": VERSION, "phase": "evaluation", "scope": specification["scope"], "cells": cells,
            "configurations": len(records), "episodes": len(records) * len(CONDITIONS),
            "physical_ticks": sum(row["case"]["horizon"] * len(CONDITIONS) for row in records),
            "agent_decisions": sum(row["case"]["horizon"] * row["case"]["config"]["n_agents"] * len(CONDITIONS) for row in records),
            "max_ledger_residual": max(e["summary"]["max_ledger_residual"] for row in records for e in row["episodes"]),
            "max_relative_ledger_residual": max(e["summary"]["max_relative_ledger_residual"] for row in records for e in row["episodes"]),
            "experimental_model_calls": 0, "evolutionary_runs": 0, "numerical_selection_runs": 1,
            "qualification_status": "not_run",
            "qualification_note": "Fresh comparison seeds do not establish ecological or incentive qualification or a private optimum."}


def read_case(path):
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def _publish_bytes(path, value):
    """Publish a complete file without exposing interrupted partial output."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def _save_json(path, value):
    value = canonical(value) + b"\n"
    if path.exists():
        if path.read_bytes() != value:
            raise ValueError("existing JSON differs: " + str(path))
    else:
        _publish_bytes(path, value)


def _save_record(path, record):
    if path.exists():
        if canonical(read_case(path)) != canonical(record):
            raise ValueError("existing case differs on replay")
    else:
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as stream:
            stream.write(canonical(record))
        _publish_bytes(path, buffer.getvalue())


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    pins = {}
    for name in SOURCES:
        destination = output / "sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
        pins[name] = sha(ROOT / name)
    _save_json(output / "design.json", design())
    _save_json(output / "sources.json", pins)
    (output / "tuning/cases").mkdir(parents=True)
    (output / "evaluation/cases").mkdir(parents=True)


def check_sources(output):
    output = Path(output)
    pins = json.loads((output / "sources.json").read_text())
    if set(pins) != set(SOURCES):
        raise ValueError("incomplete source freeze")
    for name, expected in pins.items():
        if sha(ROOT / name) != expected or sha(output / "sources" / name) != expected:
            raise ValueError("source changed: " + name)
    saved = json.loads((output / "design.json").read_text())
    if canonical(saved) != canonical(design()):
        raise ValueError("development design changed")
    return saved


def tuning_path(case, candidate):
    return "tuning/cases/" + case["id"] + "--" + candidate["id"] + ".json.gz"


def tuning_artifacts(specification):
    return {"tuning/summary.json", *(tuning_path(case, candidate) for case in specification["tuning"]["cases"]
                                    for candidate in specification["candidates"])}


def expected_artifacts(specification):
    return {"design.json", "sources.json", *("sources/" + name for name in SOURCES),
            *tuning_artifacts(specification), "tuning/manifest.json", "selection.json", "summary.json",
            *("evaluation/cases/" + case["id"] + ".json.gz" for case in specification["evaluation"]["cases"])}


def _preflight(output, specification):
    if any(output.rglob("*-failure.json")):
        raise FileExistsError("failed development bank is preserved; choose a new output")
    present = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    if not present <= expected_artifacts(specification) | {"manifest.json"}:
        raise ValueError("unexpected evidence inventory")


def _manifest(output, specification, *, phase):
    files = tuning_artifacts(specification) if phase == "tuning" else expected_artifacts(specification)
    return {"version": VERSION, "phase": phase, "complete": True,
            "configurations": len(specification[phase]["cases"]),
            "episodes": len(specification[phase]["cases"]) * (len(specification["candidates"]) if phase == "tuning" else len(CONDITIONS)),
            "design_sha256": sha(output / "design.json"), "sources_sha256": sha(output / "sources.json"),
            "artifacts_sha256": {name: sha(output / name) for name in sorted(files)}}


def _load_tuning(output, specification, *, replay):
    expected = tuning_artifacts(specification)
    path = output / "tuning/manifest.json"
    saved_manifest = json.loads(path.read_text())
    if canonical(saved_manifest) != canonical(_manifest(output, specification, phase="tuning")):
        raise ValueError("tuning manifest or artifact inventory differs")
    if set(saved_manifest["artifacts_sha256"]) != expected:
        raise ValueError("tuning inventory differs")
    records = []
    for case in specification["tuning"]["cases"]:
        for candidate in specification["candidates"]:
            saved = read_case(output / tuning_path(case, candidate))
            if (saved.get("version") != VERSION or canonical(saved["case"]) != canonical(case)
                    or canonical(saved["candidate"]) != canonical(candidate)):
                raise ValueError("tuning case inventory differs")
            if replay and canonical(saved) != canonical(tuning_record(case, candidate)):
                raise ValueError("tuning semantic replay differs")
            records.append(saved)
    summary = tuning_summary(records, specification)
    if canonical(summary) != canonical(json.loads((output / "tuning/summary.json").read_text())):
        raise ValueError("tuning aggregate differs")
    return summary


def _selection(output, specification, summary):
    selected = next(candidate for candidate in specification["candidates"] if candidate["id"] == summary["selected_candidate_id"])
    pins = json.loads((output / "sources.json").read_text())
    return {"version": SELECTION_VERSION, "candidate": selected, "selection_rule": specification["selection_rule"],
            "selected_policy_sha256": digest({"source_sha256": pins[POLICY_SOURCE], "parameters": selected["parameters"], "aggressive": False}),
            "tuning_manifest_sha256": sha(output / "tuning/manifest.json"),
            "tuning_summary_sha256": sha(output / "tuning/summary.json"),
            "evaluation_spec_sha256": digest(specification["evaluation"]),
            "design_sha256": sha(output / "design.json"), "sources_sha256": sha(output / "sources.json")}


def _failure(output, label, error):
    _save_json(output / (label + "-failure.json"),
               {"version": VERSION, "label": label, "error": type(error).__name__, "detail": str(error)})


def tune(output):
    output = Path(output)
    specification = check_sources(output)
    _preflight(output, specification)
    if (output / "manifest.json").exists():
        raise FileExistsError("completed development bank is preserved; choose a new output")
    if (output / "tuning/manifest.json").exists():
        if (output / "selection.json").exists():
            raise FileExistsError("completed tuning bank is preserved; continue with evaluate")
        summary = _load_tuning(output, specification, replay=True)
        _save_json(output / "selection.json", _selection(output, specification, summary))
        return summary
    records = []
    for case in specification["tuning"]["cases"]:
        for candidate in specification["candidates"]:
            label = "tuning-" + case["id"] + "--" + candidate["id"]
            try:
                record = tuning_record(case, candidate)
                _save_record(output / tuning_path(case, candidate), record)
                records.append(record)
                print(json.dumps({"phase": "tuning", "case": case["id"], "candidate": candidate["id"], "status": "ok"}), flush=True)
            except Exception as error:
                _failure(output, label, error)
                raise
    try:
        summary = tuning_summary(records, specification)
        _save_json(output / "tuning/summary.json", summary)
        _save_json(output / "tuning/manifest.json", _manifest(output, specification, phase="tuning"))
        _save_json(output / "selection.json", _selection(output, specification, summary))
    except Exception as error:
        _failure(output, "tuning-completion", error)
        raise
    return summary


def evaluate(output):
    output = Path(output)
    specification = check_sources(output)
    _preflight(output, specification)
    if (output / "manifest.json").exists():
        raise FileExistsError("completed development bank is preserved; choose a new output")
    summary = _load_tuning(output, specification, replay=False)
    selection = _selection(output, specification, summary)
    _save_json(output / "selection.json", selection)
    records = []
    for case in specification["evaluation"]["cases"]:
        try:
            record = evaluation_record(case, specification, selection["candidate"])
            _save_record(output / "evaluation/cases" / (case["id"] + ".json.gz"), record)
            records.append(record)
            print(json.dumps({"phase": "evaluation", "case": case["id"], "status": "ok"}), flush=True)
        except Exception as error:
            _failure(output, "evaluation-" + case["id"], error)
            raise
    try:
        result = aggregate(records, specification)
        result["selected_candidate"] = selection["candidate"]
        result["selection_sha256"] = sha(output / "selection.json")
        result["total_tuning_and_evaluation"] = {key: summary[key] + result[key]
                                                  for key in ("episodes", "physical_ticks", "agent_decisions")}
        _save_json(output / "summary.json", result)
        _save_json(output / "manifest.json", _manifest(output, specification, phase="evaluation"))
    except Exception as error:
        _failure(output, "evaluation-completion", error)
        raise
    return result


def verify(output, *, phase="all", replay=True):
    if phase not in ("all", "tuning", "evaluation"):
        raise ValueError("unknown verification phase")
    output = Path(output)
    specification = check_sources(output)
    _preflight(output, specification)
    summary = _load_tuning(output, specification, replay=replay and phase != "evaluation")
    selection = _selection(output, specification, summary)
    if canonical(selection) != canonical(json.loads((output / "selection.json").read_text())):
        raise ValueError("selection binding differs")
    receipt = {"version": VERSION, "verified": True, "phase": phase, "semantic_replay": replay,
               "tuning_semantic_replay": replay and phase != "evaluation", "tuning_episodes": summary["episodes"],
               "selection_sha256": sha(output / "selection.json")}
    if phase == "tuning":
        return receipt
    present = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    if present != expected_artifacts(specification) | {"manifest.json"}:
        raise ValueError("evaluation evidence inventory differs")
    saved_manifest = json.loads((output / "manifest.json").read_text())
    if canonical(saved_manifest) != canonical(_manifest(output, specification, phase="evaluation")):
        raise ValueError("evaluation manifest or artifact inventory differs")
    records = []
    for case in specification["evaluation"]["cases"]:
        saved = read_case(output / "evaluation/cases" / (case["id"] + ".json.gz"))
        if (saved.get("version") != VERSION or canonical(saved["case"]) != canonical(case)
                or canonical(saved["selected_candidate"]) != canonical(selection["candidate"])
                or [e["condition"] for e in saved["episodes"]] != list(CONDITIONS)):
            raise ValueError("evaluation case inventory differs")
        if replay and canonical(saved) != canonical(evaluation_record(case, specification, selection["candidate"])):
            raise ValueError("evaluation semantic replay differs")
        records.append(saved)
    result = aggregate(records, specification)
    result["selected_candidate"] = selection["candidate"]
    result["selection_sha256"] = sha(output / "selection.json")
    result["total_tuning_and_evaluation"] = {key: summary[key] + result[key]
                                              for key in ("episodes", "physical_ticks", "agent_decisions")}
    if canonical(result) != canonical(json.loads((output / "summary.json").read_text())):
        raise ValueError("evaluation aggregate differs")
    return {**receipt, "evaluation_semantic_replay": replay, "evaluation_episodes": result["episodes"],
            "manifest_sha256": sha(output / "manifest.json"), **result["total_tuning_and_evaluation"]}
