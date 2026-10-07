"""Analytic and synthetic-record checks; no qualification simulations run."""
from copy import deepcopy
import math
import statistics

import pytest

from swarm_societies.commons_v3 import qualification_analysis_v1 as analysis
from swarm_societies.commons_v3.qualification_design_v1 import design, conditions, focal_and_peers


def synthetic_design(stage):
    value = deepcopy(design(stage))
    chosen = {(.24, 1.2), (.36, 1.2), (.36, 1.6)}
    cases = [case for case in value["cases"] if case["panel"] != "grid"
             or (case["config"]["renewal_rate"], case["config"]["need"]) in chosen]
    old_seeds = value["seeds"]
    seed_map = {seed: (100 if stage == "ecology" else 200) + index for index, seed in enumerate(old_seeds)}
    for case in cases:
        old_seed = case["seed"]
        case["seed"] = seed_map[old_seed]
        case["id"] = case["id"].rsplit("-s", 1)[0] + "-s" + str(case["seed"])
        case["focal_id"], case["peer_order"] = focal_and_peers(case["seed"], old_seeds.index(old_seed))
    value["seeds"] = sorted(seed_map.values())
    value["cases"] = cases
    value["condition_registry"] = {case["id"]: conditions(stage, case) for case in cases}
    return value


def synthetic_episode(case, control, arm):
    n, need, horizon = case["config"]["n_agents"], case["config"]["need"], case["horizon"]
    agents = []
    for identity in range(n):
        aggressive = identity in arm["aggressive_ids"]
        consumption = need * (.98 - .65 * arm["peer_count"] / (n - 1)
                              + (.018 if identity == case["focal_id"] and aggressive else 0))
        inventory = 11. if aggressive else 1.
        agents.append({"id": identity, "policy": "aggressive" if aggressive else "normal",
                       "consumption_per_tick": consumption, "late_consumption_per_tick": consumption,
                       "shortfall_per_tick": need - consumption, "late_shortfall_per_tick": need - consumption,
                       "terminal_inventory": inventory,
                       "utility": {str(weight): consumption + weight * inventory / horizon for weight in (0., .05, .2)}})
    mean = statistics.mean(agent["consumption_per_tick"] for agent in agents)
    all_aggressive = len(arm["aggressive_ids"]) == n
    stock = max(.005, .6 - .02 * len(arm["aggressive_ids"]))
    summary = {"consumption_per_agent_tick": mean, "late_consumption_per_agent_tick": mean,
               "quarter3_consumption_per_agent_tick": mean, "late_stock_fraction": stock,
               "terminal_stock_fraction": stock, "depleted_patch_time_fraction": .9 if all_aggressive else 0.,
               "late_depleted_patch_time_fraction": .9 if all_aggressive else 0.,
               "persistent_depletion_longest_ticks": horizon // 4 if all_aggressive else 0,
               "persistent_depletion_threshold_ticks": horizon // 8,
               "prefix256_consumption_per_agent_tick": mean,
               "prefix256_late_consumption_per_agent_tick": mean,
               "prefix256_terminal_stock_fraction": stock,
               "max_ledger_residual": 1e-14, "max_relative_ledger_residual": 1e-16}
    cohorts = {}
    for kind in ("normal", "aggressive"):
        members = [agent for agent in agents if agent["policy"] == kind]
        cohorts[kind] = {"n": len(members), **{field: statistics.mean(agent[field] for agent in members)
                                              if members else None for field in analysis.AGENT_FIELDS},
                         "utility": {str(weight): statistics.mean(agent["utility"][str(weight)] for agent in members)
                                     if members else None for weight in (0., .05, .2)}}
    return {"case": deepcopy(case), "control": deepcopy(control), "condition": arm["id"],
            "intervention": deepcopy(arm), "aggressive_ids": list(arm["aggressive_ids"]),
            "aggressive_count": len(arm["aggressive_ids"]), "summary": summary,
            "agents": agents, "cohorts": cohorts, "weather_sha256": f"weather-{case['seed']}-{horizon}",
            "initial_state_sha256": f"initial-{case['seed']}",
            "trajectory": [{"large_record": 17}], "spatial_frames": [{"tick": 0}], "site_layout": []}


def synthetic_records(specification):
    return [{"case": deepcopy(case), "episodes": [synthetic_episode(case, control, arm)
             for control in specification["controls"] for arm in specification["condition_registry"][case["id"]]],
             "feasibility_certificates": []} for case in specification["cases"]]


@pytest.fixture(scope="module")
def bank():
    ecology_design, incentive_design = synthetic_design("ecology"), synthetic_design("incentive")
    ecological_records, incentive_records = synthetic_records(ecology_design), synthetic_records(incentive_design)
    ecology = analysis.aggregate_ecology(ecological_records, ecology_design)
    incentives = analysis.aggregate_incentives(incentive_records, incentive_design, ecology)
    return ecology_design, incentive_design, ecological_records, incentive_records, ecology, incentives


def test_seed_interval_matches_manual_arithmetic_and_fixed_constants():
    specification = design("ecology")
    values, seeds = list(range(16)), specification["seeds"]
    result = analysis.interval(values, seeds, specification, simultaneous=True)
    se = math.sqrt(sum((value - 7.5) ** 2 for value in values) / 15) / 4
    assert result["mean"] == 7.5
    assert result["standard_error"] == se
    assert result["lower"] == 7.5 - 4.750567324005865 * se
    assert result["upper"] == 7.5 + 4.750567324005865 * se
    assert result["family_size"] == 194
    assert result["values"] == values and result["seeds"] == seeds
    descriptive = analysis.interval(values, seeds, specification)
    assert descriptive["lower"] > result["lower"]
    assert descriptive["critical"] == 2.131449545559776
    assert descriptive["family_size"] is None


@pytest.mark.parametrize("direction,value,threshold,status", [
    ("lower", .95, .95, "pass"), ("lower", .949, .95, "fail"),
    ("upper", .10, .10, "pass"), ("upper", .101, .10, "fail"),
    ("lower", -.02, -.02, "pass"), ("lower", -.021, -.02, "fail")])
def test_exact_zero_variance_boundary_decisions(direction, value, threshold, status):
    specification = design("ecology")
    result = analysis.criterion([value] * 16, specification["seeds"], specification, threshold, direction=direction)
    assert result["status"] == status
    assert result["lower"] == result["upper"] == value


def test_uncertainty_and_minuscule_nonzero_signs_are_retained():
    specification = design("ecology")
    row = analysis.criterion([0.] * 8 + [2.] * 8, specification["seeds"], specification, 1.)
    assert row["status"] == "unresolved"
    tiny = analysis.interval([-1e-16] * 4 + [0.] * 8 + [1e-16] * 4, specification["seeds"], specification)
    assert (tiny["negative"], tiny["zero"], tiny["positive"]) == (4, 8, 4)


@pytest.mark.parametrize("bad", [[0.] * 15, [0.] * 17, [0.] * 15 + [float("nan")],
                                  [0.] * 15 + [float("inf")], [0.] * 15 + [True]])
def test_invalid_interval_data_never_produce_a_verdict(bad):
    specification = design("ecology")
    with pytest.raises(ValueError):
        analysis.interval(bad, specification["seeds"], specification)


def test_duplicate_seed_is_not_an_independent_replicate():
    specification = design("ecology")
    with pytest.raises(ValueError, match="seed inventory"):
        analysis.interval([0.] * 16, [17] * 16, specification)


def test_scalar_projection_preserves_bindings_and_never_mutates_inputs(bank):
    source = bank[2][0]
    projected = analysis.scalar_record(source)
    for field in ("trajectory", "spatial_frames", "site_layout"):
        assert field not in projected["episodes"][0]
        assert field in source["episodes"][0]
    assert projected["episodes"][0]["case"] == source["episodes"][0]["case"]
    projected["episodes"][0]["agents"][0]["terminal_inventory"] = 99
    projected["case"]["seed"] = 999
    assert source["episodes"][0]["agents"][0]["terminal_inventory"] == 1.
    assert source["case"]["seed"] != 999


def test_ecology_measures_are_seed_level_and_all_required_margins_pass(bank):
    summary = bank[4]
    assert summary["episodes"] == 3 * 16 * 2
    assert summary["physical_ticks"] == summary["episodes"] * 512
    assert summary["simultaneous_scalar_intervals"] == 3 * 2 * 5
    assert summary["ecological_adjacent_pairs"]["status"] == "pass"
    assert len(summary["ecological_adjacent_pairs"]["pairs"]) == 1
    assert len(summary["ecological_adjacent_pairs"]["pairs"][0]["requirements"]) == 4
    for cell in summary["cells"]:
        assert cell["status"] == "pass" and cell["feasibility"] == "witnessed_viable"
        for control in cell["controls"].values():
            assert set(control["criteria"]) == set(bank[0]["ecology_thresholds"])
            assert all(row["n"] == 16 for row in control["criteria"].values())
            assert control["criteria"]["consumption_fraction"]["mean"] == pytest.approx(.98)
            assert control["criteria"]["late_minus_third_quarter_fraction"]["mean"] == 0
            assert control["criteria"]["late_depleted_patch_time_fraction_max"]["direction"] == "upper"


def test_primary_pair_uses_reference_shared_backgrounds_and_no_diagonals(bank):
    summary = bank[5]
    assert summary["primary_gate"]["status"] == "pass"
    assert len(summary["primary_gate"]["pairs"]) == 1
    pair = summary["primary_gate"]["pairs"][0]
    assert set(pair["cells"]) == {"grid-r0.24-n1.2", "grid-r0.36-n1.2"}
    assert len(pair["requirements"]) == 8
    assert summary["qualification_status"] == "pass"
    assert summary["simultaneous_scalar_intervals"] == {"primary": 3 * 2 * 3, "reference_robustness": 5 * 2 * 5}


def test_full_primary_design_has_exact_194_family_inventory_without_running_physics():
    ecology, incentive = design("ecology"), design("incentive")
    assert 9 * len(ecology["controls"]) * len(ecology["ecology_thresholds"]) == 90
    assert 9 * len(incentive["controls"]) * 3 == 54
    assert len(incentive["robustness_panels"]) * len(incentive["controls"]) * 5 == 50
    assert 90 + 54 + 50 == incentive["statistics"]["simultaneous_family_size"]


def test_paired_focal_curves_hold_peers_fixed_and_decompose_wealth(bank):
    cell = next(cell for cell in bank[5]["cells"] if cell["id"] == "grid-r0.24-n1.2")
    control = cell["controls"]["selected"]
    assert [row["peer_count"] for row in control["paired_focal"]] == [0, 6, 12, 18, 23]
    for paired in control["paired_focal"]:
        differences = paired["differences"]
        assert differences["consumption_per_tick"]["mean"] == pytest.approx(.018 * 1.2)
        assert differences["peer_consumption_per_tick"]["values"] == [0.] * 16
        assert differences["world_consumption_per_agent_tick"]["mean"] == pytest.approx(.018 * 1.2 / 24)
        assert differences["terminal_wealth_contribution_0.05"]["mean"] == .05 * 10 / 256
        assert differences["utility_0.05"]["mean"] == pytest.approx(
            differences["consumption_per_tick"]["mean"] + differences["terminal_wealth_contribution_0.05"]["mean"])
    assert control["paired_focal"][0]["differences"]["aggressive_peer_consumption_per_tick"] is None
    assert control["paired_focal"][-1]["differences"]["normal_peer_consumption_per_tick"] is None
    assert control["conditions"]["peers23-focalA"]["cohorts"]["normal"]["endpoints"]["consumption_per_tick"] is None
    identities = control["conditions"]["peers00-focalA"]["identities_by_seed"]
    assert all(row["aggressive_ids"] == [row["focal_id"]] for row in identities)
    assert len({row["focal_id"] for row in identities}) > 1


def test_widespread_harm_orientation_and_separate_additive_scope(bank):
    cell = next(cell for cell in bank[5]["cells"] if cell["id"] == "grid-r0.24-n1.2")
    control = cell["controls"]["fixed_floor"]
    descriptive = control["all_aggressive_minus_all_restrained"]["consumption_per_agent_tick"]
    criterion = control["criteria"]["population_consumption_loss_fraction"]
    assert descriptive["mean"] < 0 and criterion["mean"] > 0
    assert criterion["mean"] == pytest.approx(-descriptive["mean"] / 1.2)
    additive = next(cell for cell in bank[5]["cells"] if cell["panel"] == "additive")
    assert additive["status"] == "not_primary"
    assert all(not row["criteria"] and not row["robustness_criteria"] for row in additive["controls"].values())
    assert all("additive" not in key for gate in bank[5]["reference_robustness_by_weight"].values() for key in gate["requirements"])


def test_one_background_ecology_failure_blocks_the_common_pair(bank):
    ecology = deepcopy(bank[4])
    reference = next(cell for cell in ecology["cells"] if cell["id"] == "grid-r0.24-n1.2")
    reference["controls"]["fixed_floor"]["status"] = "fail"
    result = analysis.aggregate_incentives(bank[3], bank[1], ecology)
    assert result["primary_gate"]["status"] == "fail"
    assert result["reference_robustness_by_weight"]["0.05"]["status"] == "pass"
    assert result["qualification_status"] == "fail"


def test_robustness_failure_cannot_be_hidden_by_primary_success(bank):
    records = deepcopy(bank[3])
    for record in records:
        if record["case"]["panel"] == "small_inventory":
            for episode in record["episodes"]:
                if episode["aggressive_count"] == 24:
                    episode["summary"]["consumption_per_agent_tick"] = record["case"]["config"]["need"]
    result = analysis.aggregate_incentives(records, bank[1], bank[4])
    assert result["primary_gate"]["status"] == "pass"
    assert result["qualification_status"] == "fail"
    assert result["reference_robustness_by_weight"]["0.05"]["status"] == "fail"


def test_controller_failure_without_certificate_does_not_mean_physical_infeasibility(bank):
    records = deepcopy(bank[2])
    for record in records:
        for episode in record["episodes"]:
            episode["summary"]["consumption_per_agent_tick"] = .5 * record["case"]["config"]["need"]
    unresolved = analysis.aggregate_ecology(records, bank[0])
    assert all(cell["status"] == "fail" and cell["feasibility"] == "feasibility_unresolved" for cell in unresolved["cells"])
    for record in records:
        record["feasibility_certificates"] = [{"horizon": 512, "window_start": 0,
                                               "target_fraction": .95, "status": "proven_insufficient"}]
    certified = analysis.aggregate_ecology(records, bank[0])
    assert all(cell["feasibility"] == "certified_insufficient" for cell in certified["cells"])


def test_record_reordering_is_deterministic_and_scalar_projection_is_lossless(bank):
    reordered = [analysis.scalar_record(record) for record in reversed(bank[2])]
    for record in reordered:
        record["episodes"].reverse()
    assert analysis.aggregate_ecology(reordered, bank[0]) == bank[4]


@pytest.mark.parametrize("mutation,match", [
    ("missing_case", "case inventory"), ("duplicate_case", "case inventory"),
    ("missing_episode", "condition inventory"), ("duplicate_episode", "condition inventory"),
    ("weather", "paired weather"), ("initial", "paired weather"),
    ("binding", "input binding"), ("mask", "intervention binding"),
    ("policy", "policy mask"), ("agent", "agent identity")])
def test_case_and_intervention_integrity_fail_closed(bank, mutation, match):
    records = deepcopy(bank[2])
    if mutation == "missing_case":
        records.pop()
    elif mutation == "duplicate_case":
        records[-1] = records[0]
    elif mutation == "missing_episode":
        records[0]["episodes"].pop()
    elif mutation == "duplicate_episode":
        records[0]["episodes"].append(records[0]["episodes"][0])
    else:
        episode = records[0]["episodes"][0]
        if mutation == "weather": episode["weather_sha256"] = "different"
        if mutation == "initial": episode["initial_state_sha256"] = "different"
        if mutation == "binding": episode["case"]["horizon"] += 1
        if mutation == "mask": episode["aggressive_ids"] = [0]
        if mutation == "policy": episode["agents"][0]["policy"] = "aggressive"
        if mutation == "agent": episode["agents"][0]["id"] = 99
    with pytest.raises(ValueError, match=match):
        analysis.aggregate_ecology(records, bank[0])


def test_ecology_and_incentive_evidence_must_use_disjoint_seeds(bank):
    ecology = deepcopy(bank[4])
    ecology["independent_environment_seeds"] = list(bank[1]["seeds"])
    with pytest.raises(ValueError, match="disjoint"):
        analysis.aggregate_incentives(bank[3], bank[1], ecology)


def test_incompatible_ecology_statistics_are_rejected(bank):
    ecology = deepcopy(bank[4])
    ecology["statistics"]["simultaneous_t_critical"] = 1.
    with pytest.raises(ValueError, match="different analysis"):
        analysis.aggregate_incentives(bank[3], bank[1], ecology)


def test_changed_peer_is_not_mistaken_for_a_focal_intervention(bank):
    specification, records = deepcopy(bank[1]), deepcopy(bank[3])
    case = records[0]["case"]
    arm = next(row for row in specification["condition_registry"][case["id"]] if row["id"] == "peers06-focalA")
    arm["aggressive_ids"] = sorted([case["focal_id"], *case["peer_order"][1:7]])
    for episode in records[0]["episodes"]:
        if episode["condition"] == arm["id"]:
            episode["intervention"] = deepcopy(arm)
            episode["aggressive_ids"] = list(arm["aggressive_ids"])
            for agent in episode["agents"]:
                agent["policy"] = "aggressive" if agent["id"] in arm["aggressive_ids"] else "normal"
    with pytest.raises(ValueError, match="changes peers"):
        analysis.aggregate_incentives(records, specification, bank[4])


def test_resource_certificate_cannot_contradict_a_witnessed_policy(bank):
    records = deepcopy(bank[2])
    for record in records:
        record["feasibility_certificates"] = [{"horizon": 512, "window_start": 0,
                                               "target_fraction": .95, "status": "proven_insufficient"}]
    with pytest.raises(ValueError, match="contradicts"):
        analysis.aggregate_ecology(records, bank[0])


def test_actual_recorder_schema_survives_projection_and_aggregation():
    from dataclasses import asdict
    from swarm_societies.commons_v3.engine import Config
    from swarm_societies.commons_v3.qualification_episode_v1 import record_episode

    specification = synthetic_design("ecology")
    cfg = asdict(Config(width=4, height=4, n_agents=4, n_patches=2, need=1.2, initial_patch_stock=40.))
    cases = []
    for index, seed in enumerate(range(901, 917)):
        focal, peers = focal_and_peers(seed, index, 4)
        cases.append({"id": f"synthetic-interface-{seed}", "panel": "grid", "seed": seed,
                      "focal_id": focal, "peer_order": peers, "horizon": 8, "config": cfg})
    specification["cases"], specification["seeds"] = cases, list(range(901, 917))
    specification["condition_registry"] = {case["id"]: conditions("ecology", case) for case in cases}
    records = []
    for case in cases:
        arm = specification["condition_registry"][case["id"]][0]
        episodes = [{**record_episode(case, control, []), "condition": arm["id"], "intervention": arm}
                    for control in specification["controls"]]
        records.append({"case": case, "episodes": episodes})
    full = analysis.aggregate_ecology(records, specification)
    assert analysis.aggregate_ecology([analysis.scalar_record(record) for record in records], specification) == full
    assert full["episodes"] == 32
    assert full["physical_ticks"] == 256
    assert full["agent_decisions"] == 1024
    for control in full["cells"][0]["controls"].values():
        assert control["summary"]["prefix256_consumption_per_agent_tick"] is None


@pytest.mark.parametrize("field", ["case", "control", "intervention", "count", "agent"])
def test_numeric_and_boolean_aliases_cannot_change_bound_input_types(bank, field):
    records = deepcopy(bank[2])
    episode = records[0]["episodes"][0]
    if field == "case": episode["case"]["config"]["n_agents"] = 24.0
    if field == "control": episode["control"]["parameters"]["reserve_ticks"] = 2.0
    if field == "intervention": episode["intervention"]["peer_count"] = False
    if field == "count": episode["aggressive_count"] = False
    if field == "agent": episode["agents"][0]["id"] = False
    with pytest.raises(ValueError):
        analysis.aggregate_ecology(records, bank[0])


def test_statistics_binding_retains_numeric_types(bank):
    ecology = deepcopy(bank[4])
    ecology["statistics"]["degrees_of_freedom"] = 15.0
    with pytest.raises(ValueError, match="different analysis"):
        analysis.aggregate_incentives(bank[3], bank[1], ecology)
