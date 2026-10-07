"""Fixed seed-level qualification analysis; no policies or simulations execute.

Intervals are the prospective approximate Student-t procedure, not exact
finite-sample coverage. Every decision uses the stored simultaneous critical
constant and exact comparisons. Descriptive intervals never admit a regime.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import statistics


VERSION = "commons-v3-qualification-analysis-v1"
AGENT_FIELDS = ("consumption_per_tick", "shortfall_per_tick", "late_consumption_per_tick",
                "late_shortfall_per_tick", "terminal_inventory")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def scalar_record(record):
    """Detach a case projection, retaining bindings, scalars and agent endpoints."""
    result = {key: deepcopy(value) for key, value in record.items() if key != "episodes"}
    result["episodes"] = [{key: deepcopy(value) for key, value in episode.items()
                           if key not in ("trajectory", "site_layout", "spatial_frames")}
                          for episode in record["episodes"]]
    return result


def interval(values, seeds, specification, *, simultaneous=False):
    """One number per independent seed; retain observations behind the interval."""
    values, seeds = list(values), list(seeds)
    settings = specification["statistics"]
    if (len(values) != settings["seed_count"] or len(seeds) != len(values)
            or len(set(seeds)) != len(seeds) or len(values) < 2
            or settings["degrees_of_freedom"] != len(values) - 1):
        raise ValueError("interval requires the complete independent seed inventory")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("interval observations must be finite numbers")
    critical = settings["simultaneous_t_critical" if simultaneous else "descriptive_t_critical"]
    if type(critical) not in (int, float) or not math.isfinite(critical) or critical <= 0:
        raise ValueError("invalid frozen interval critical constant")
    mean = statistics.mean(values)
    standard_error = statistics.stdev(values) / math.sqrt(len(values))
    radius = critical * standard_error
    return {"mean": mean, "lower": mean - radius, "upper": mean + radius,
            "standard_error": standard_error, "critical": critical, "n": len(values),
            "min": min(values), "max": max(values), "seeds": seeds, "values": values,
            "positive": sum(value > 0 for value in values), "negative": sum(value < 0 for value in values),
            "zero": sum(value == 0 for value in values), "sign_count_threshold": 0.,
            "interval_kind": "simultaneous" if simultaneous else "descriptive",
            "family_size": settings["simultaneous_family_size"] if simultaneous else None}


def criterion(values, seeds, specification, threshold, *, direction="lower"):
    row = interval(values, seeds, specification, simultaneous=True)
    if direction == "lower":
        status = "pass" if row["lower"] >= threshold else "fail" if row["upper"] < threshold else "unresolved"
    elif direction == "upper":
        status = "pass" if row["upper"] <= threshold else "fail" if row["lower"] > threshold else "unresolved"
    else:
        raise ValueError("unknown criterion direction")
    return {**row, "threshold": threshold, "direction": direction, "status": status}


def conjunction(statuses):
    statuses = list(statuses)
    if not statuses or any(status not in ("pass", "fail", "unresolved") for status in statuses):
        raise ValueError("a gate requires nonempty valid statuses")
    return "fail" if "fail" in statuses else "unresolved" if "unresolved" in statuses else "pass"


def _disjunction(statuses):
    statuses = list(statuses)
    return "pass" if "pass" in statuses else "unresolved" if "unresolved" in statuses else "fail"


def _key(case):
    return case["panel"], case["config"]["renewal_rate"], case["config"]["need"]


def _cell_fields(key):
    panel, rate, need = key
    return {"id": f"{panel}-r{rate:.2f}-n{need:.1f}", "panel": panel,
            "renewal_rate": rate, "need": need}


def _validated_groups(records, specification, stage):
    if specification["stage"] != stage:
        raise ValueError("wrong qualification stage")
    expected = {case["id"]: case for case in specification["cases"]}
    records = list(records)
    if len(records) != len(expected) or {record["case"]["id"] for record in records} != set(expected):
        raise ValueError("qualification case inventory differs")
    controls = {control["id"]: control for control in specification["controls"]}
    if len(controls) != len(specification["controls"]):
        raise ValueError("duplicate controls")
    groups = {}
    for record in records:
        case = record["case"]
        if _canonical(case) != _canonical(expected[case["id"]]):
            raise ValueError("case binding differs from the frozen design")
        registry = {row["id"]: row for row in specification["condition_registry"][case["id"]]}
        expected_arms = {(control, arm) for control in controls for arm in registry}
        observed, weather, initial = {}, set(), set()
        for episode in record["episodes"]:
            control, arm = episode["control"]["id"], episode["condition"]
            pair = control, arm
            if pair in observed or pair not in expected_arms:
                raise ValueError("episode condition inventory differs")
            if (_canonical(episode["control"]) != _canonical(controls[control])
                    or _canonical(episode["case"]) != _canonical(case)):
                raise ValueError("episode input binding differs")
            intervention = registry[arm]
            if (_canonical(episode["intervention"]) != _canonical(intervention)
                    or _canonical(episode["aggressive_ids"]) != _canonical(intervention["aggressive_ids"])
                    or _canonical(episode["aggressive_count"]) != _canonical(len(intervention["aggressive_ids"]))):
                raise ValueError("aggressive intervention binding differs")
            if (len(set(episode["aggressive_ids"]) - {case["focal_id"]}) != intervention["peer_count"]
                    or (case["focal_id"] in episode["aggressive_ids"]) != intervention["focal_aggressive"]):
                raise ValueError("focal/peer intervention roles differ")
            agents = episode["agents"]
            if _canonical([agent["id"] for agent in agents]) != _canonical(list(range(case["config"]["n_agents"]))):
                raise ValueError("agent identity inventory differs")
            if any(agent["policy"] != ("aggressive" if agent["id"] in episode["aggressive_ids"] else "normal")
                   for agent in agents):
                raise ValueError("agent policy mask differs")
            observed[pair] = episode
            weather.add(episode["weather_sha256"])
            initial.add(episode["initial_state_sha256"])
        if set(observed) != expected_arms:
            raise ValueError("episode condition inventory differs")
        if len(weather) != 1 or len(initial) != 1:
            raise ValueError("paired weather or initial state differs")
        groups.setdefault(_key(case), []).append((record, observed))
    for rows in groups.values():
        rows.sort(key=lambda row: row[0]["case"]["seed"])
        if [row[0]["case"]["seed"] for row in rows] != sorted(specification["seeds"]):
            raise ValueError("cell seed inventory differs")
    return groups


def _numeric_columns(rows, seeds, specification):
    keys = set(rows[0])
    if any(set(row) != keys for row in rows):
        raise ValueError("scalar endpoint columns differ")
    result = {}
    for key in sorted(keys):
        values = [row[key] for row in rows]
        if all(value is None for value in values):
            result[key] = None
        elif any(value is None for value in values):
            raise ValueError("partially missing scalar endpoint")
        else:
            result[key] = interval(values, seeds, specification)
    return result


def _agent_columns(agent, weights):
    return {**{field: agent[field] for field in AGENT_FIELDS},
            **{"utility_" + str(weight): agent["utility"][str(weight)] for weight in weights}}


def _condition(episodes, cases, specification):
    seeds = [case["seed"] for case in cases]
    weights = specification["wealth_weights"]
    return {
        "condition": episodes[0]["condition"],
        "intervention": {key: episodes[0]["intervention"][key] for key in ("peer_count", "focal_aggressive")},
        "identities_by_seed": [{"seed": case["seed"], "focal_id": case["focal_id"],
                                "aggressive_ids": list(episode["aggressive_ids"])} for case, episode in zip(cases, episodes)],
        "aggressive_count": episodes[0]["aggressive_count"],
        "aggressive_fraction": episodes[0]["aggressive_count"] / cases[0]["config"]["n_agents"],
        "summary": _numeric_columns([episode["summary"] for episode in episodes], seeds, specification),
        "focal": _numeric_columns([_agent_columns(episode["agents"][case["focal_id"]], weights)
                                    for episode, case in zip(episodes, cases)], seeds, specification),
        "cohorts": {kind: {"n": episodes[0]["cohorts"][kind]["n"],
                            "endpoints": _numeric_columns([_agent_columns(episode["cohorts"][kind], weights)
                                                           for episode in episodes], seeds, specification)}
                    for kind in ("normal", "aggressive")},
        "persistent_depletion_seed_count": sum(episode["summary"]["persistent_depletion_longest_ticks"]
                                               >= episode["summary"]["persistent_depletion_threshold_ticks"]
                                               for episode in episodes),
    }


def _base_summary(records, specification, phase):
    episodes = [episode for record in records for episode in record["episodes"]]
    return {"version": VERSION, "phase": phase, "scope": specification["scope"],
            "statistics": deepcopy(specification["statistics"]),
            "configurations": len(records), "episodes": len(episodes),
            "physical_ticks": sum(record["case"]["horizon"] * len(record["episodes"]) for record in records),
            "agent_decisions": sum(record["case"]["horizon"] * record["case"]["config"]["n_agents"]
                                   * len(record["episodes"]) for record in records),
            "independent_environment_seeds": list(specification["seeds"]),
            "max_ledger_residual": max(episode["summary"]["max_ledger_residual"] for episode in episodes),
            "max_relative_ledger_residual": max(episode["summary"]["max_relative_ledger_residual"] for episode in episodes),
            "experimental_model_calls": 0, "evolutionary_runs": 0, "new_numerical_selection_runs": 0}


def _ecology_classification(status, certificates):
    # The exact certificate schema is retained intact. Only its explicit
    # insufficiency verdict can establish the physical claim.
    relevant = [certificate for certificate in certificates
                if certificate.get("horizon") == 512 and certificate.get("window_start") == 0
                and certificate.get("target_fraction") == .95]
    certified = relevant and all(certificate.get("status") == "proven_insufficient" for certificate in relevant)
    if status == "pass":
        if certified:
            raise ValueError("witnessed viability contradicts the saved resource certificate")
        return "witnessed_viable"
    if certified:
        return "certified_insufficient"
    return "feasibility_unresolved"


def _eligible_pairs(grid, design):
    reference = (design["reference"]["renewal_rate"], design["reference"]["need"])
    for left in sorted(grid):
        for right in sorted(grid):
            if left >= right:
                continue
            distance = abs(design["rates"].index(left[0]) - design["rates"].index(right[0])) + abs(
                design["needs"].index(left[1]) - design["needs"].index(right[1]))
            if distance == 1 and (not design["adjacency"]["must_include_reference"] or reference in (left, right)):
                yield left, right


def _ecological_pairs(cells, design):
    grid = {(cell["renewal_rate"], cell["need"]): cell for cell in cells if cell["panel"] == "grid"}
    pairs = []
    for left, right in _eligible_pairs(grid, design):
        requirements = {f"{grid[key]['id']}/{control['id']}": grid[key]["controls"][control["id"]]["status"]
                        for key in (left, right) for control in design["controls"]}
        pairs.append({"cells": [grid[key]["id"] for key in (left, right)], "requirements": requirements,
                      "status": conjunction(requirements.values())})
    return {"status": _disjunction(pair["status"] for pair in pairs), "pairs": pairs,
            "scope": "Ecological criteria only; incentive qualification remains separate.",
            "rule": deepcopy(design["adjacency"])}


def aggregate_ecology(records, design):
    """Analyze both frozen controls on the complete independent ecology panel."""
    records = list(records)
    groups = _validated_groups(records, design, "ecology")
    cells = []
    thresholds = design["ecology_thresholds"]
    for key, rows in sorted(groups.items()):
        cases = [row[0]["case"] for row in rows]
        seeds = [case["seed"] for case in cases]
        need = key[2]
        controls = {}
        for control in design["controls"]:
            episodes = [arms[(control["id"], "all_restrained")] for _, arms in rows]
            summaries = [episode["summary"] for episode in episodes]
            values = {
                "consumption_fraction": [row["consumption_per_agent_tick"] / need for row in summaries],
                "late_consumption_fraction": [row["late_consumption_per_agent_tick"] / need for row in summaries],
                "late_minus_third_quarter_fraction": [(row["late_consumption_per_agent_tick"]
                                                       - row["quarter3_consumption_per_agent_tick"]) / need
                                                      for row in summaries],
                "late_stock_fraction": [row["late_stock_fraction"] for row in summaries],
                "late_depleted_patch_time_fraction_max": [row["late_depleted_patch_time_fraction"] for row in summaries],
            }
            criteria = {name: criterion(value, seeds, design, thresholds[name],
                                        direction="upper" if name.endswith("_max") else "lower")
                        for name, value in values.items()}
            controls[control["id"]] = {**_condition(episodes, cases, design), "criteria": criteria,
                                       "status": conjunction(row["status"] for row in criteria.values())}
        certificates = [{"seed": record["case"]["seed"], "certificates": deepcopy(record.get("feasibility_certificates", []))}
                        for record, _ in rows]
        status = conjunction(row["status"] for row in controls.values())
        # One witnessed legal policy establishes feasibility, whereas the
        # qualification gate deliberately requires both frozen backgrounds.
        witnessed = any(row["status"] == "pass" for row in controls.values())
        classification = _ecology_classification("pass" if witnessed else status,
                                                [certificate for row in certificates for certificate in row["certificates"]])
        cells.append({**_cell_fields(key), "horizon": cases[0]["horizon"], "controls": controls,
                      "status": status, "feasibility": classification, "feasibility_certificates": certificates})
    return {**_base_summary(records, design, "ecology"), "cells": cells,
            "ecological_adjacent_pairs": _ecological_pairs(cells, design),
            "simultaneous_scalar_intervals": sum(len(row["criteria"]) for cell in cells for row in cell["controls"].values()),
            "qualification_status": "ecology_only", "note": "Both-control cell gates are finite-horizon evidence; incentive qualification is separate. A failed controller is not proof of physical infeasibility."}


def _focal_difference(before, after, case, weights):
    focal = case["focal_id"]
    left, right = before["agents"][focal], after["agents"][focal]
    row = {field: right[field] - left[field] for field in AGENT_FIELDS}
    row["peer_consumption_per_tick"] = statistics.mean(
        after["agents"][i]["consumption_per_tick"] - before["agents"][i]["consumption_per_tick"]
        for i in range(len(before["agents"])) if i != focal)
    row["peer_late_consumption_per_tick"] = statistics.mean(
        after["agents"][i]["late_consumption_per_tick"] - before["agents"][i]["late_consumption_per_tick"]
        for i in range(len(before["agents"])) if i != focal)
    for kind in ("normal", "aggressive"):
        identities = [agent["id"] for agent in before["agents"] if agent["id"] != focal and agent["policy"] == kind]
        for metric in ("consumption_per_tick", "late_consumption_per_tick"):
            row[kind + "_peer_" + metric] = statistics.mean(
                after["agents"][i][metric] - before["agents"][i][metric] for i in identities) if identities else None
    for metric in ("consumption_per_agent_tick", "late_consumption_per_agent_tick", "terminal_stock_fraction",
                   "depleted_patch_time_fraction", "late_stock_fraction", "late_depleted_patch_time_fraction"):
        row["world_" + metric] = after["summary"][metric] - before["summary"][metric]
    for weight in weights:
        row["utility_" + str(weight)] = right["utility"][str(weight)] - left["utility"][str(weight)]
        row["terminal_wealth_contribution_" + str(weight)] = weight * row["terminal_inventory"] / case["horizon"]
    return row


def _reference(cell, design):
    return all(cell[key] == value for key, value in design["reference"].items())


def _adjacent_pairs(cells, ecology, design):
    grid = {(cell["renewal_rate"], cell["need"]): cell for cell in cells if cell["panel"] == "grid"}
    eco = {(cell["renewal_rate"], cell["need"]): cell for cell in ecology["cells"] if cell["panel"] == "grid"}
    if set(grid) != set(eco):
        raise ValueError("ecology and incentive grids differ")
    pairs = []
    for left, right in _eligible_pairs(grid, design):
        requirements = {f"{grid[key]['id']}/{control['id']}/{stage}": source[key]["controls"][control['id']]["status"]
                        for key in (left, right) for control in design["controls"]
                        for stage, source in (("ecology", eco), ("incentive", grid))}
        pairs.append({"cells": [grid[key]["id"] for key in (left, right)],
                      "requirements": requirements, "status": conjunction(requirements.values())})
    return {"status": _disjunction(pair["status"] for pair in pairs), "pairs": pairs,
            "rule": deepcopy(design["adjacency"])}


def aggregate_incentives(records, design, ecology_summary):
    """Matched focal interventions and separate primary/robustness verdicts."""
    if (ecology_summary.get("version") != VERSION or ecology_summary.get("phase") != "ecology"
            or _canonical(ecology_summary.get("statistics")) != _canonical(design["statistics"])):
        raise ValueError("ecology summary uses a different analysis specification")
    if set(ecology_summary["independent_environment_seeds"]) & set(design["seeds"]):
        raise ValueError("ecology and incentive seeds must be disjoint")
    records = list(records)
    groups = _validated_groups(records, design, "incentive")
    thresholds = design["incentive_thresholds"]
    weights = design["wealth_weights"]
    primary_weight = str(thresholds["primary_wealth_weight"])
    cells = []
    for key, rows in sorted(groups.items()):
        cases = [row[0]["case"] for row in rows]
        seeds = [case["seed"] for case in cases]
        need = key[2]
        controls = {}
        reference = _reference(_cell_fields(key), design)
        robust = reference and key[0] in design["robustness_panels"]
        for control in design["controls"]:
            control_id = control["id"]
            registry = design["condition_registry"][cases[0]["id"]]
            conditions = {arm["id"]: _condition([arms[(control_id, arm["id"])] for _, arms in rows], cases, design)
                          for arm in registry}
            by_role = {(arm["peer_count"], arm["focal_aggressive"]): arm["id"] for arm in registry}
            paired = []
            for count in sorted({count for count, focal in by_role if not focal}):
                if (count, True) not in by_role:
                    continue
                left_id, right_id = by_role[(count, False)], by_role[(count, True)]
                differences = []
                for (record, arms), case in zip(rows, cases):
                    before, after = arms[(control_id, left_id)], arms[(control_id, right_id)]
                    if set(after["aggressive_ids"]) != set(before["aggressive_ids"]) | {case["focal_id"]}:
                        raise ValueError("focal intervention changes peers")
                    differences.append(_focal_difference(before, after, case, weights))
                paired.append({"peer_count": count, "peer_fraction": count / (cases[0]["config"]["n_agents"] - 1),
                               "before_condition": left_id, "after_condition": right_id,
                               "differences": _numeric_columns(differences, seeds, design)})
            focal = next(row["differences"] for row in paired if row["peer_count"] == 0)
            normal_id = by_role[(0, False)]
            aggressive_id = by_role[(cases[0]["config"]["n_agents"] - 1, True)]
            widespread_rows = [{name: arms[(control_id, aggressive_id)]["summary"][name]
                                - arms[(control_id, normal_id)]["summary"][name]
                                for name in arms[(control_id, normal_id)]["summary"]
                                if arms[(control_id, normal_id)]["summary"][name] is not None}
                               for _, arms in rows]
            widespread = _numeric_columns(widespread_rows, seeds, design)
            margins = {"focal_utility_gain_fraction": [value / need for value in focal["utility_" + primary_weight]["values"]],
                       "population_consumption_loss_fraction": [-value / need for value in widespread["consumption_per_agent_tick"]["values"]],
                       "population_late_consumption_loss_fraction": [-value / need for value in widespread["late_consumption_per_agent_tick"]["values"]]}
            criteria = {name: criterion(values, seeds, design, thresholds[name]) for name, values in margins.items()} if key[0] == "grid" else {}
            robustness_criteria = {}
            if robust:
                for weight in weights:
                    robustness_criteria["focal_utility_gain_fraction_" + str(weight)] = criterion(
                        [value / need for value in focal["utility_" + str(weight)]["values"]], seeds, design,
                        thresholds["focal_utility_gain_fraction"])
                for name in ("population_consumption_loss_fraction", "population_late_consumption_loss_fraction"):
                    robustness_criteria[name] = criterion(margins[name], seeds, design, thresholds[name])
            controls[control_id] = {"conditions": conditions, "paired_focal": paired,
                                    "all_aggressive_minus_all_restrained": widespread, "criteria": criteria,
                                    "status": conjunction(row["status"] for row in criteria.values()) if criteria else "not_primary",
                                    "robustness_criteria": robustness_criteria}
        cells.append({**_cell_fields(key), "horizon": cases[0]["horizon"], "controls": controls,
                      "status": conjunction(row["status"] for row in controls.values()) if key[0] == "grid" else "not_primary"})
    primary_gate = _adjacent_pairs(cells, ecology_summary, design)
    robust_cells = [cell for cell in cells if _reference(cell, design) and cell["panel"] in design["robustness_panels"]]
    if {cell["panel"] for cell in robust_cells} != set(design["robustness_panels"]):
        raise ValueError("reference robustness panel inventory differs")
    robustness = {}
    for weight in weights:
        required = {f"{cell['panel']}/{control_id}/{name}": row["robustness_criteria"][name]["status"]
                    for cell in robust_cells for control_id, row in cell["controls"].items()
                    for name in ("focal_utility_gain_fraction_" + str(weight),
                                 "population_consumption_loss_fraction", "population_late_consumption_loss_fraction")}
        robustness[str(weight)] = {"status": conjunction(required.values()), "requirements": required}
    overall = conjunction([primary_gate["status"], robustness[primary_weight]["status"]])
    return {**_base_summary(records, design, "incentive"), "cells": cells,
            "primary_gate": primary_gate, "reference_robustness_by_weight": robustness,
            "qualification_status": overall, "primary_wealth_weight": thresholds["primary_wealth_weight"],
            "simultaneous_scalar_intervals": {
                "primary": sum(len(row["criteria"]) for cell in cells for row in cell["controls"].values()),
                "reference_robustness": sum(len(row["robustness_criteria"]) for cell in cells for row in cell["controls"].values())},
            "note": "Overall requires the common adjacent primary pair and reference robustness at the canonical weight. Other weights are separate reference sensitivity verdicts. Additive renewal and intermediate peer-prevalence curves are descriptive, never alternative acceptance paths."}
