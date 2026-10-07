#!/usr/bin/env python3
"""Audit navigation statistics with the Python standard library only.

No engine, policy, runner, verifier, aggregator or renderer is imported.
Recorded agents, trajectories and frames are inputs, not independent physics.
Accumulation diagnostics use fsum and tolerance 2e-12. Selection and integer/
sign counts are checked exactly; no tolerance can change the winning candidate.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

VERSION = "commons-v3-navigation-development-v1"
CONDITIONS = ("legacy_need2", "fixed_forager", "fixed_floor", "selected",
              "focal_aggressive_selected", "all_aggressive")
ANCHORS = CONDITIONS[:3]
WEIGHTS = (0., .05, .2)
SOURCE_NAMES = ("swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py",
                "swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/policies_need_v1.py",
                "swarm_societies/commons_v3/policies_navigation_v1.py",
                "swarm_societies/commons_v3/development_navigation_v1.py",
                "scripts/run_commons_v3_navigation_v1.py", "docs/commons-v3-foundation-protocol.md",
                "docs/commons-v3-foundation-protocol-v2.md", "docs/commons-v3-need-protocol-v1.md",
                "docs/commons-v3-navigation-protocol-v1.md")
BASE_CONFIG = {"width": 12, "height": 12, "n_agents": 24, "n_patches": 16, "sensing_radius": 1,
               "need": 1.2, "initial_inventory": 2., "inventory_capacity": 80., "patch_capacity": 40.,
               "initial_patch_stock": 40., "renewal_rate": .24, "recovery": .02, "weather_amplitude": .1,
               "max_harvest": 4., "movement_cost": .02, "harvest_cost_per_unit": .02,
               "message_byte_cost": .001, "max_message_bytes": 128, "max_messages": 1,
               "renewal_law": "logistic", "contention": "proportional", "terminal_wealth_weight": .05}
CHECKS = EXACT_CHECKS = FRAME_CHECKS = 0
MAX_ERROR = MAX_SCALED_ERROR = 0.
TOLERANCE = 2e-12


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def value_sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def raw(path):
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def number(value):
    assert type(value) in (int, float) and math.isfinite(value), value
    return value


def exact(actual, expected, context):
    global EXACT_CHECKS
    EXACT_CHECKS += 1
    assert actual == expected, (context, actual, expected)


def check(actual, expected, context):
    global CHECKS, MAX_ERROR, MAX_SCALED_ERROR
    actual, expected = number(actual), number(expected)
    error = abs(actual - expected)
    scaled = error / max(1., abs(actual), abs(expected))
    MAX_ERROR, MAX_SCALED_ERROR = max(MAX_ERROR, error), max(MAX_SCALED_ERROR, scaled)
    CHECKS += 1
    assert scaled <= TOLERANCE, (context, actual, expected, error)


def fmean(values):
    values = list(values)
    return math.fsum(values) / len(values)


def checked_mean(values, context):
    values = list(values)
    value = statistics.mean(values)
    check(value, fmean(values), context + "/fsum accumulation")
    return value


def descriptive(values):
    values = list(values)
    return {"mean": statistics.mean(values), "min": min(values), "max": max(values),
            "positive": sum(v > 1e-12 for v in values), "negative": sum(v < -1e-12 for v in values), "n": len(values)}


def compare_description(saved, values, context):
    values = list(values)
    rebuilt = descriptive(values)
    exact(set(saved), set(rebuilt), context + "/fields")
    for key in ("positive", "negative", "n"):
        exact(saved[key], rebuilt[key], context + "/" + key)
    for key in ("mean", "min", "max"):
        check(saved[key], rebuilt[key], context + "/" + key)
    check(saved["mean"], fmean(values), context + "/independent fsum mean")
    return rebuilt


def expected_candidates():
    return [{"id": f"r{reserve}-f{int(floor * 100):02d}-{route}",
             "parameters": {"reserve_ticks": reserve, "stock_floor_fraction": floor, "route_mode": route}}
            for reserve in (0, 2, 4) for floor in (0., .25, .5) for route in ("nearest", "net_yield")]


def expected_cases(seeds, sensitivities):
    cases = []
    for rate in (.12, .24, .36):
        for need in (.8, 1.2, 1.6):
            for index, seed in enumerate(seeds):
                cases.append({"id": f"grid-r{rate:.2f}-n{need:.1f}-s{seed}", "panel": "grid", "seed": seed,
                              "focal_id": index * 6, "horizon": 256,
                              "config": {**BASE_CONFIG, "renewal_rate": rate, "need": need}})
    if sensitivities:
        variants = (("long_horizon", {}, 512), ("keyed_priority", {"contention": "keyed_priority"}, 256),
                    ("lower_stock", {"initial_patch_stock": 22.}, 256),
                    ("additive", {"renewal_law": "additive"}, 256),
                    ("small_inventory", {"inventory_capacity": 8.}, 256))
        for panel, changes, horizon in variants:
            for index, seed in enumerate(seeds):
                cases.append({"id": f"{panel}-s{seed}", "panel": panel, "seed": seed, "focal_id": index * 6,
                              "horizon": horizon, "config": {**BASE_CONFIG, **changes}})
    return cases


def manifest_check(source, path, phase, paths, configurations, episodes):
    manifest = read(path)
    expected = {"version": VERSION, "phase": phase, "complete": True, "configurations": configurations,
                "episodes": episodes, "design_sha256": sha(source / "design.json"),
                "sources_sha256": sha(source / "sources.json"),
                "artifacts_sha256": {name: sha(source / name) for name in sorted(paths)}}
    exact(manifest, expected, str(path) + "/full manifest and hashes")
    return manifest


def frame_diagnostics(case, episode):
    global FRAME_CHECKS
    cfg, horizon, frames = case["config"], case["horizon"], episode["spatial_frames"]
    prefix = case["id"] + "/" + episode["condition"]
    if frames:
        exact([f["tick"] for f in frames], [0, horizon // 4, horizon // 2, horizon], prefix + "/frame ticks")
        exact(episode["checkpoint_continuation_checked"], True, prefix + "/saved checkpoint assertion")
    else:
        exact(episode["checkpoint_continuation_checked"], False, prefix + "/no checkpoint assertion")
    for frame in frames:
        agents, sites, tick = frame["agents"], frame["sites"], frame["tick"]
        exact([a["id"] for a in agents], list(range(cfg["n_agents"])), prefix + "/frame agent IDs")
        exact([p["id"] for p in sites], list(range(cfg["n_patches"])), prefix + "/frame site IDs")
        occupied = {(a["x"], a["y"]) for a in agents}
        site_cells = {(p["x"], p["y"]) for p in sites}
        exact(len(site_cells), cfg["n_patches"], prefix + "/unique resource cells")
        for item in [*agents, *sites]:
            assert 0 <= item["x"] < cfg["width"] and 0 <= item["y"] < cfg["height"]
        for agent in agents:
            assert 0 <= number(agent["inventory"]) <= cfg["inventory_capacity"]
        for site in sites:
            assert 0 <= number(site["stock"]) <= cfg["patch_capacity"]
        if tick == 0:
            for agent in agents:
                exact(agent["inventory"], cfg["initial_inventory"], prefix + "/initial inventory")
            for site in sites:
                exact(site["stock"], cfg["initial_patch_stock"], prefix + "/initial stock")
            continue
        saved = episode["trajectory"][tick - 1]
        exact(saved["off_site_agents"], sum((a["x"], a["y"]) not in site_cells for a in agents), prefix + "/frame offsite")
        exact(saved["depleted_patches"], sum(p["stock"] < .1 * cfg["patch_capacity"] for p in sites), prefix + "/frame depletion")
        check(saved["stock"], math.fsum(p["stock"] for p in sites), prefix + "/frame stock")
        check(saved["reserves"], math.fsum(a["inventory"] for a in agents), prefix + "/frame inventories")
        check(saved["unoccupied_stock_fraction"], math.fsum(p["stock"] for p in sites if (p["x"], p["y"]) not in occupied)
              / (cfg["n_patches"] * cfg["patch_capacity"]), prefix + "/frame unoccupied stock")
        if tick == horizon:
            for frame_agent, final_agent in zip(agents, episode["agents"]):
                exact(frame_agent["inventory"], final_agent["terminal_inventory"], prefix + "/final agent inventory")
        FRAME_CHECKS += 1


def episode_primitives(case, episode):
    cfg, horizon, agents, ticks = case["config"], case["horizon"], episode["agents"], episode["trajectory"]
    n, patches = cfg["n_agents"], cfg["n_patches"]
    prefix = case["id"] + "/" + episode["condition"]
    exact([a["id"] for a in agents], list(range(n)), prefix + "/agent IDs")
    exact([t["tick"] for t in ticks], list(range(1, horizon + 1)), prefix + "/ticks")
    average = lambda field: checked_mean((number(a[field]) for a in agents), prefix + "/" + field)
    consumption, shortfall = average("consumption_per_tick"), average("shortfall_per_tick")
    late, inventory = average("late_consumption_per_tick"), average("terminal_inventory")
    moves = average("movement_steps")
    check(consumption, math.fsum(t["consumption"] for t in ticks) / (horizon * n), prefix + "/consumption flow")
    check(shortfall, math.fsum(t["shortfall"] for t in ticks) / (horizon * n), prefix + "/shortfall flow")
    check(consumption + shortfall, cfg["need"], prefix + "/need identity")
    late_count = max(1, horizon // 4)
    check(late, math.fsum(t["consumption"] for t in ticks[-late_count:]) / (late_count * n), prefix + "/late flow")
    check(inventory, ticks[-1]["reserves"] / n, prefix + "/inventory endpoint")
    check(moves, math.fsum(t["moves"] for t in ticks) / n, prefix + "/movement flow")
    for field in ("movement_cost", "harvest_cost"):
        check(math.fsum(a[field] for a in agents), math.fsum(t[field] for t in ticks), prefix + "/cost flow " + field)
    for agent in agents:
        check(agent["consumption_per_tick"] + agent["shortfall_per_tick"], cfg["need"], prefix + "/agent need")
        assert 0 <= agent["terminal_inventory"] <= cfg["inventory_capacity"]
        for weight in WEIGHTS:
            # Power-of-two horizons exactly recover the recorded consumption
            # numerator, avoiding tolerance in subsequent utility sign counts.
            reconstructed = (agent["consumption_per_tick"] * horizon + weight * agent["terminal_inventory"]) / horizon
            exact(agent["utility"][str(weight)], reconstructed, prefix + "/raw utility " + str(weight))
            check(reconstructed, agent["consumption_per_tick"] + weight * agent["terminal_inventory"] / horizon,
                  prefix + "/reassociated utility diagnostic")
    for tick in ticks:
        for name, bound in (("off_site_agents", n), ("hungry_off_site_agents", n), ("moves", n), ("depleted_patches", patches)):
            assert type(tick[name]) is int and 0 <= tick[name] <= bound, (prefix, name, tick[name])
        assert tick["hungry_off_site_agents"] <= tick["off_site_agents"]
        if tick["shortfall"] == 0:
            exact(tick["hungry_off_site_agents"], 0, prefix + "/zero shortfall")
        assert 0 <= number(tick["mean_known_sites"]) <= patches
        assert 0 <= number(tick["unoccupied_stock_fraction"]) <= 1
        assert tick["unaffordable_known_returns"] == 0
    calculated = {
        "consumption_per_agent_tick": consumption, "shortfall_per_agent_tick": shortfall,
        "late_consumption_per_agent_tick": late, "terminal_inventory_per_agent": inventory,
        "terminal_stock_fraction": ticks[-1]["stock"] / (patches * cfg["patch_capacity"]),
        "depleted_patch_time_fraction": sum(t["depleted_patches"] for t in ticks) / (horizon * patches),
        "movement_steps_per_agent": moves,
        "total_movement_cost": sum(a["movement_cost"] for a in agents),
        "total_harvest_cost": sum(a["harvest_cost"] for a in agents),
        "total_waste": number(episode["summary"]["total_waste"]),
        "max_unaffordable_known_returns": max(t["unaffordable_known_returns"] for t in ticks),
        "mean_off_site_agent_fraction": checked_mean((t["off_site_agents"] / n for t in ticks), prefix + "/offsite"),
        "mean_hungry_off_site_agent_fraction": checked_mean((t["hungry_off_site_agents"] / n for t in ticks), prefix + "/hungry offsite"),
        "terminal_unoccupied_stock_fraction": ticks[-1]["unoccupied_stock_fraction"],
        "terminal_mean_known_sites": ticks[-1]["mean_known_sites"],
        "max_ledger_residual": number(episode["summary"]["max_ledger_residual"]),
        "max_relative_ledger_residual": number(episode["summary"]["max_relative_ledger_residual"]),
    }
    check(calculated["total_waste"], math.fsum(t["waste"] for t in ticks), prefix + "/waste flows")
    assert calculated["total_waste"] <= horizon * 1e-9
    assert calculated["max_ledger_residual"] + TOLERANCE >= max(abs(t["accounting_residual"]) for t in ticks)
    exact(set(episode["summary"]), set(calculated), prefix + "/summary fields")
    for field, value in calculated.items():
        check(episode["summary"][field], value, prefix + "/summary " + field)
    cohorts = {kind: [a for a in agents if a["policy"] == kind] for kind in {a["policy"] for a in agents}}
    exact(set(episode["cohorts"]), set(cohorts), prefix + "/cohort names")
    for kind, members in cohorts.items():
        exact(episode["cohorts"][kind]["n"], len(members), prefix + "/cohort size")
        for field in ("consumption_per_tick", "late_consumption_per_tick"):
            check(episode["cohorts"][kind][field], fmean(a[field] for a in members), prefix + "/cohort " + field)
    frame_diagnostics(case, episode)
    return calculated


def audit(source, root):
    design, saved, tuning_saved, selection, pins = (read(source / name) for name in (
        "design.json", "summary.json", "tuning/summary.json", "selection.json", "sources.json"))
    exact(design["version"], VERSION, "design version")
    exact(design["tuning"]["seeds"], [62001, 62002], "tuning seeds")
    exact(design["evaluation"]["seeds"], [63001, 63002, 63003, 63004], "evaluation seeds")
    assert not set(design["tuning"]["seeds"]) & set(design["evaluation"]["seeds"])
    assert not (set(design["tuning"]["seeds"]) | set(design["evaluation"]["seeds"])) & set(range(61001, 61005))
    exact(design["candidates"], expected_candidates(), "complete finite candidate registry")
    exact(design["tuning"]["cases"], expected_cases([62001, 62002], False), "complete tuning configurations")
    exact(design["evaluation"]["cases"], expected_cases([63001, 63002, 63003, 63004], True), "complete evaluation configurations")
    exact(design["evaluation"]["conditions"], list(CONDITIONS), "conditions")
    exact(design["evaluation"]["reference_frames_case"], "grid-r0.24-n1.2-s63001", "predeclared reference")
    exact(design["fixed_forager"], {"reserve_ticks": 2, "stock_floor_fraction": 0., "route_mode": "net_yield"}, "fixed forager")
    exact(design["fixed_floor"], {"reserve_ticks": 2, "stock_floor_fraction": .5, "route_mode": "net_yield"}, "fixed floor")
    exact(design["depletion_threshold_capacity_fraction"], .1, "depletion diagnostic threshold")
    exact(design["late_window_fraction"], .25, "final-quarter window")
    exact(design["selection_rule"], {
        "primary": "mean population consumption per agent-tick divided by case need, equally weighted cases",
        "secondary": "mean final-quarter population consumption divided by case need",
        "tie_break": "lexicographically smallest candidate ID; exact float comparison",
        "failure_rule": "halt and preserve the complete failed bank; never omit unsuccessful cases"}, "frozen selection rule")
    exact(design["wealth_weights"], list(WEIGHTS), "wealth weights")
    exact(design["experimental_model_calls"], 0, "model calls")
    exact(design["evolutionary_runs"], 0, "evolutionary runs")
    exact(design["numerical_selection_runs"], 1, "finite numerical selection runs")
    exact(design["qualification_data"], False, "qualification status")
    exact(set(pins), set(SOURCE_NAMES), "full source freeze")
    for name, expected in pins.items():
        exact(sha(source / "sources" / name), expected, "copied source " + name)
        exact(sha(root / name), expected, "working source " + name)
    tuning_paths = {"tuning/summary.json"} | {
        "tuning/cases/" + c["id"] + "--" + candidate["id"] + ".json.gz"
        for c in design["tuning"]["cases"] for candidate in design["candidates"]}
    all_paths = tuning_paths | {"design.json", "sources.json", "tuning/manifest.json", "selection.json", "summary.json"}
    all_paths |= {"sources/" + name for name in SOURCE_NAMES}
    all_paths |= {"evaluation/cases/" + case["id"] + ".json.gz" for case in design["evaluation"]["cases"]}
    exact({str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()}, all_paths | {"manifest.json"}, "full artifact inventory")
    manifest_check(source, source / "tuning/manifest.json", "tuning", tuning_paths, 18, 324)
    manifest_check(source, source / "manifest.json", "evaluation", all_paths, 56, 336)
    tuning_rows, tuning_primitives, weather = [], [], {}
    for case in design["tuning"]["cases"]:
        for candidate in design["candidates"]:
            path = source / "tuning/cases" / (case["id"] + "--" + candidate["id"] + ".json.gz")
            record = raw(path)
            exact(record["version"], VERSION, str(path) + "/version")
            exact(record["case"], case, str(path) + "/case")
            exact(record["candidate"], candidate, str(path) + "/candidate")
            episode = record["episode"]
            exact(episode["condition"], candidate["id"], str(path) + "/condition")
            exact({a["policy"] for a in episode["agents"]}, {candidate["id"]}, str(path) + "/population")
            exact(episode["spatial_frames"], [], str(path) + "/no tuning frames")
            primitives = episode_primitives(case, episode)
            weather.setdefault(case["id"], set()).add(episode["weather_sha256"])
            # Exact ranking uses the saved primary field after an exact raw
            # agent-mean reconstruction plus independent fsum diagnostics.
            primary = episode["summary"]["consumption_per_agent_tick"] / case["config"]["need"]
            late = episode["summary"]["late_consumption_per_agent_tick"] / case["config"]["need"]
            exact(primary, statistics.mean(a["consumption_per_tick"] for a in episode["agents"]) / case["config"]["need"], "exact primary primitive score")
            exact(late, statistics.mean(a["late_consumption_per_tick"] for a in episode["agents"]) / case["config"]["need"], "exact late primitive score")
            tuning_rows.append({"candidate_id": candidate["id"], "case_id": case["id"], "seed": case["seed"],
                                "rate": case["config"]["renewal_rate"], "need": case["config"]["need"],
                                "score": primary, "late_score": late,
                                "fsum_score": fmean(a["consumption_per_tick"] for a in episode["agents"]) / case["config"]["need"]})
            tuning_primitives.append(primitives)
    assert all(len(values) == 1 for values in weather.values())
    scores = []
    for candidate in design["candidates"]:
        rows = [r for r in tuning_rows if r["candidate_id"] == candidate["id"]]
        groups = {}
        for row in rows:
            groups.setdefault((row["rate"], row["need"]), []).append(row["score"])
        scores.append({**candidate, "episodes": len(rows), "score": statistics.mean(r["score"] for r in rows),
                       "late_score": statistics.mean(r["late_score"] for r in rows),
                       "worst_case_score": min(r["score"] for r in rows),
                       "worst_cell_score": min(statistics.mean(values) for values in groups.values())})
        check(scores[-1]["score"], fmean(r["fsum_score"] for r in rows), "candidate fsum score " + candidate["id"])
    exact(tuning_saved["candidates"], scores, "all exact tuning scores and diagnostics")
    ranked = sorted(scores, key=lambda row: (-row["score"], -row["late_score"], row["id"]))
    winner = next(c for c in design["candidates"] if c["id"] == ranked[0]["id"])
    exact(tuning_saved["selected_candidate_id"], winner["id"], "exact winner, no tolerance")
    expected_selection = {"version": "commons-v3-navigation-selection-v1", "candidate": winner,
        "selection_rule": design["selection_rule"],
        "selected_policy_sha256": value_sha({"source_sha256": pins["swarm_societies/commons_v3/policies_navigation_v1.py"],
                                               "parameters": winner["parameters"], "aggressive": False}),
        "tuning_manifest_sha256": sha(source / "tuning/manifest.json"),
        "tuning_summary_sha256": sha(source / "tuning/summary.json"),
        "evaluation_spec_sha256": value_sha(design["evaluation"]),
        "design_sha256": sha(source / "design.json"), "sources_sha256": sha(source / "sources.json")}
    exact(selection, expected_selection, "all frozen selection bindings")
    exact(saved["selected_candidate"], winner, "evaluation selected candidate")
    exact(saved["selection_sha256"], sha(source / "selection.json"), "evaluation selection pin")
    grouped, evaluation_primitives = {}, []
    for case in design["evaluation"]["cases"]:
        record = raw(source / "evaluation/cases" / (case["id"] + ".json.gz"))
        exact(record["version"], VERSION, case["id"] + "/version")
        exact(record["case"], case, case["id"] + "/case")
        exact(record["selected_candidate"], winner, case["id"] + "/selected")
        exact([e["condition"] for e in record["episodes"]], list(CONDITIONS), case["id"] + "/condition inventory")
        assert len({e["weather_sha256"] for e in record["episodes"]}) == 1
        primitives = {}
        for episode in record["episodes"]:
            condition = episode["condition"]
            expected_kinds = [condition] * case["config"]["n_agents"]
            if condition in CONDITIONS[3:]:
                expected_kinds = ["aggressive" if condition == "all_aggressive" or
                                  (condition == "focal_aggressive_selected" and i == case["focal_id"]) else "selected"
                                  for i in range(case["config"]["n_agents"])]
            exact([a["policy"] for a in episode["agents"]], expected_kinds, case["id"] + "/policy composition")
            exact(bool(episode["spatial_frames"]), case["id"] == design["evaluation"]["reference_frames_case"], case["id"] + "/reference frame selection")
            primitives[condition] = episode_primitives(case, episode)
            evaluation_primitives.append(primitives[condition])
        if case["id"] == design["evaluation"]["reference_frames_case"]:
            starts = [{"sites": e["spatial_frames"][0]["sites"],
                       "agents": [{k: v for k, v in a.items() if k != "policy"} for a in e["spatial_frames"][0]["agents"]]}
                      for e in record["episodes"]]
            exact(starts, [starts[0]] * len(CONDITIONS), "identical recorded reference starts")
        key = (case["panel"], case["config"]["renewal_rate"], case["config"]["need"])
        grouped.setdefault(key, []).append((record, primitives))
    saved_cells = {(c["panel"], c["renewal_rate"], c["need"]): c for c in saved["cells"]}
    exact(len(saved_cells), 14, "all 14 evaluation cells")
    exact(len(saved_cells), len(saved["cells"]), "unique cells")
    exact(set(saved_cells), set(grouped), "cell inventory")
    calculated_cells = []
    for key, rows in grouped.items():
        cell = saved_cells[key]
        exact(cell["paired_configurations"], len(rows), str(key) + "/paired configurations")
        exact(set(cell["conditions"]), set(CONDITIONS), str(key) + "/condition fields")
        exact(set(cell["selected_minus_fixed"]), set(ANCHORS), str(key) + "/anchor fields")
        means, anchor_effects, widespread = {}, {}, {}
        for condition in CONDITIONS:
            means[condition] = {}
            exact(set(cell["conditions"][condition]), set(rows[0][1][condition]), str(key) + "/summary field inventory")
            for field in rows[0][1][condition]:
                value = checked_mean((p[condition][field] for _, p in rows), str(key) + "/condition mean")
                check(cell["conditions"][condition][field], value, str(key) + "/" + condition + "/" + field)
                means[condition][field] = value
        for anchor in ANCHORS:
            exact(set(cell["selected_minus_fixed"][anchor]), set(rows[0][1][anchor]), str(key) + "/paired anchor metric inventory")
            anchor_effects[anchor] = {field: compare_description(cell["selected_minus_fixed"][anchor][field],
                (p["selected"][field] - p[anchor][field] for _, p in rows), str(key) + "/anchor " + anchor + "/" + field)
                for field in rows[0][1][anchor]}
        differences = {field: [] for field in ("consumption", "late_consumption", "peer_consumption", "world_consumption", "terminal_inventory",
                                              *("utility_" + str(w) for w in WEIGHTS))}
        exact(set(cell["focal_deviation"]), set(differences), str(key) + "/focal metric inventory")
        exact(set(cell["all_aggressive_minus_selected"]), set(rows[0][1]["selected"]), str(key) + "/widespread metric inventory")
        for record, primitives in rows:
            case, episodes = record["case"], {e["condition"]: e for e in record["episodes"]}
            before, after = episodes["selected"]["agents"], episodes["focal_aggressive_selected"]["agents"]
            focal, horizon = case["focal_id"], case["horizon"]
            left, right = before[focal], after[focal]
            dc = right["consumption_per_tick"] - left["consumption_per_tick"]
            di = right["terminal_inventory"] - left["terminal_inventory"]
            dp = statistics.mean(after[i]["consumption_per_tick"] - before[i]["consumption_per_tick"] for i in range(len(before)) if i != focal)
            dw = primitives["focal_aggressive_selected"]["consumption_per_agent_tick"] - primitives["selected"]["consumption_per_agent_tick"]
            check(dw, (dc + (len(before) - 1) * dp) / len(before), str(key) + "/focal peer world identity")
            differences["consumption"].append(dc)
            differences["late_consumption"].append(right["late_consumption_per_tick"] - left["late_consumption_per_tick"])
            differences["terminal_inventory"].append(di)
            differences["peer_consumption"].append(dp)
            differences["world_consumption"].append(dw)
            for weight in WEIGHTS:
                utility = lambda a: (a["consumption_per_tick"] * horizon + weight * a["terminal_inventory"]) / horizon
                du = utility(right) - utility(left)
                check(du, dc + weight * di / horizon, str(key) + "/utility decomposition")
                differences["utility_" + str(weight)].append(du)
        focal = {field: compare_description(cell["focal_deviation"][field], values, str(key) + "/focal " + field)
                 for field, values in differences.items()}
        for field in rows[0][1]["selected"]:
            widespread[field] = compare_description(cell["all_aggressive_minus_selected"][field],
                (p["all_aggressive"][field] - p["selected"][field] for _, p in rows), str(key) + "/widespread " + field)
        calculated_cells.append({"panel": key[0], "renewal_rate": key[1], "need": key[2], "paired_configurations": len(rows),
                                "conditions": means, "selected_minus_fixed": anchor_effects,
                                "focal_deviation": focal, "all_aggressive_minus_selected": widespread})
    counts = {}
    for phase, stage, multiplier, diagnostics in (("tuning", tuning_saved, 18, tuning_primitives), ("evaluation", saved, 6, evaluation_primitives)):
        cases = design[phase]["cases"]
        values = {"episodes": len(cases) * multiplier, "physical_ticks": sum(c["horizon"] for c in cases) * multiplier,
                  "agent_decisions": sum(c["horizon"] * c["config"]["n_agents"] for c in cases) * multiplier}
        exact(stage["configurations"], len(cases), phase + "/configurations")
        for name, value in values.items():
            exact(stage[name], value, phase + "/" + name)
        for name, value in (("experimental_model_calls", 0), ("evolutionary_runs", 0), ("numerical_selection_runs", 1)):
            exact(stage[name], value, phase + "/" + name)
        check(stage["max_ledger_residual"], max(p["max_ledger_residual"] for p in diagnostics), phase + "/max residual")
        counts[phase] = values
    check(saved["max_relative_ledger_residual"], max(p["max_relative_ledger_residual"] for p in evaluation_primitives), "evaluation max relative residual")
    totals = {key: counts["tuning"][key] + counts["evaluation"][key] for key in counts["tuning"]}
    exact(saved["total_tuning_and_evaluation"], totals, "combined counts")
    exact(totals, {"episodes": 660, "physical_ticks": 175104, "agent_decisions": 4202496}, "predeclared counts")
    exact(saved["qualification_status"], "not_run", "qualification not run")
    return {"version": "commons-v3-navigation-independent-primitive-audit-v1", "verified": True,
            "scope": "Independent standard-library saved-primitive and aggregate audit; no simulation, independent physics or qualification.",
            "source": str(source), "root": str(root), "qualification_status": "not_run", "experimental_model_calls": 0,
            "evolutionary_runs": 0, "numerical_selection_runs": 1, "counts": counts, "total": totals,
            "numeric_checks": CHECKS, "exact_checks": EXACT_CHECKS, "frame_diagnostic_checks": FRAME_CHECKS,
            "max_absolute_numeric_difference": MAX_ERROR, "max_scaled_numeric_difference": MAX_SCALED_ERROR,
            "tolerance_relative_to_max_one": TOLERANCE,
            "tolerance_scope": "Independent accumulation/reassociation diagnostics only; exact hashes, registries, selection ranking, winner and sign counts.",
            "selection_uses_tolerance": False, "selected_candidate": winner,
            "exact_candidate_ranking": [c["id"] for c in ranked], "candidate_scores": scores,
            "tuning_case_scores": tuning_rows, "evaluation_cells": calculated_cells,
            "manifest_sha256": sha(source / "manifest.json"), "tuning_manifest_sha256": sha(source / "tuning/manifest.json"),
            "selection_sha256": sha(source / "selection.json"), "script_sha256": sha(__file__),
            "limitations": [
                "Saved agents, trajectories and frames are trusted recorded primitives; policies and physical transitions are not independently replayed.",
                "Off-site counts, stock, unoccupied stock, depletion and inventories are cross-checked against reference frames at ticks 64, 128, 256 only.",
                "Hungry/off-site joint counts and known-site counts have bounds and aggregate checks but lack saved per-agent tick/memory primitives for independent derivation.",
                "Per-agent/per-patch ledger residual maxima are saved diagnostics; only bounds against saved whole-ledger residuals are checked.",
                "Cumulative waste uses the saved endpoint diagnostic after independent trajectory-sum comparison; per-agent waste totals were not recorded.",
                "Saved snapshot-continuation assertions are checked for declared coverage, not independently rerun by this audit."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("evidence/commons-v3-navigation-v1"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("runs/commons-v3-navigation-v1-validation/independent-audit.json"))
    args = parser.parse_args()
    assert not args.output.exists(), "audit output must be a new file"
    result = audit(args.source, args.root)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("verified", "numeric_checks", "exact_checks", "max_absolute_numeric_difference", "selected_candidate", "total")}, sort_keys=True))


if __name__ == "__main__":
    main()
