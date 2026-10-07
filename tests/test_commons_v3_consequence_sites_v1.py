"""Ticket B selection/gate checks use synthetic rows, not a development bank."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import math
import statistics as st

import pytest

from swarm_societies.commons_v3 import consequence_sites_v1 as consequence
from swarm_societies.commons_v3 import engine_sites_v1 as engine


def synthetic_rows(phi=.375):
    jobs = (consequence.candidate_jobs("R-oracle")
            + consequence.candidate_jobs("R-fixed", phi)
            + consequence.candidate_jobs("R-greedy", phi))
    rows = []
    for job in jobs:
        if job["arm"] == "R-oracle":
            score = .8 if job["phi"] == phi else .7
        elif job["arm"] == "R-fixed":
            score = {20.: .7, 30.: .6, 40.: .5}[job["fixed_capacity"]]
        else:
            score = .4
        identity = f"{job['condition']}|{job['need']}|{job['seed']}"
        rows.append({"version": consequence.VERSION, "job": job, "horizon": 512,
                     "initial_snapshot": {"sha256": hashlib.sha256(identity.encode()).hexdigest()},
                     "weather_sha256": hashlib.sha256(f"weather|{job['seed']}".encode()).hexdigest(),
                     "summary": {"share_of_need": score, "final_quarter_share_of_need": score,
                                 "starvation_next_to_food_share_of_need": 0.,
                                 "starvation_next_to_food_agent_tick_fraction": 0.,
                                 "local_collapse_site_tick_fraction": 0.,
                                 "message_bytes": 0, "message_cost": 0.,
                                 "agent_consumption_share_min": score,
                                 "agent_consumption_share_max": score,
                                 "agent_consumption_share_sd": 0., "max_ledger_residual": 0.}})
    return rows


def set_scores(row, whole, late=None):
    row["summary"]["share_of_need"] = whole
    row["summary"]["final_quarter_share_of_need"] = whole if late is None else late


def gate_rows(differences, fixed_shares=(0., 0., 0., 0.)):
    rows = synthetic_rows()
    for row in rows:
        job = row["job"]
        if job["arm"] == "R-oracle":
            set_scores(row, .9 if job["phi"] == .375 else .1)
        elif job["arm"] == "R-fixed":
            set_scores(row, {20.: .6, 30.: .1, 40.: .05}[job["fixed_capacity"]])
        if (job["condition"], job["need"]) == ("wide", 1.6):
            index = consequence.SEEDS.index(job["seed"])
            if job["arm"] == "R-oracle" and job["phi"] == .375:
                set_scores(row, fixed_shares[index] + differences[index])
            if job["arm"] == "R-fixed" and job["fixed_capacity"] == 20.:
                set_scores(row, fixed_shares[index])
    return rows


def test_exact_candidate_inventory_is_96_episodes_on_four_reused_development_seeds():
    oracle = consequence.candidate_jobs("R-oracle")
    fixed = consequence.candidate_jobs("R-fixed", .375)
    greedy = consequence.candidate_jobs("R-greedy", .375)
    assert (len(oracle), len(fixed), len(greedy)) == (32, 48, 16)
    assert consequence.SEEDS == (90001, 90002, 90003, 90004)
    assert consequence.HORIZON == 512
    assert {job["phi"] for job in oracle} == {.375, .5}
    assert {job["fixed_capacity"] for job in fixed} == {20., 30., 40.}
    for arm_rows in (oracle, fixed, greedy):
        assert {job["seed"] for job in arm_rows} == set(consequence.SEEDS)
        assert {(job["condition"], job["need"]) for job in arm_rows} == {
            ("moderate", 1.2), ("moderate", 1.6), ("wide", 1.2), ("wide", 1.6)}
    assert len({consequence.case_id(job) for job in oracle + fixed + greedy}) == 96


@pytest.mark.parametrize("arm,phi", [("R-oracle", .375), ("R-fixed", None),
                                     ("R-greedy", None), ("R-fixed", .25), ("L0", .5)])
def test_candidate_jobs_rejects_uncontracted_arms_and_floor_settings(arm, phi):
    with pytest.raises(ValueError):
        consequence.candidate_jobs(arm, phi)


def test_global_selection_does_not_pick_the_best_setting_separately_in_the_gate_cell():
    rows = synthetic_rows()
    for row in rows:
        job = row["job"]
        gate_cell = (job["condition"], job["need"]) == ("wide", 1.6)
        if job["arm"] == "R-oracle":
            set_scores(row, .75 if job["phi"] == .375 else (.95 if gate_cell else .65))
        elif job["arm"] == "R-fixed":
            set_scores(row, {20.: .7, 30.: .82 if gate_cell else .65, 40.: .6}[job["fixed_capacity"]])
    summary = consequence.summarize(rows)
    assert summary["oracle_selection"]["selected"] == .375
    assert summary["fixed_selection"]["selected"] == 20.
    assert summary["G1"]["contrast"]["mean"] == pytest.approx(.05)
    assert not summary["G1"]["passed"]
    assert summary["episodes"] == 96
    assert summary["selected_episodes"] == 48
    assert len(summary["cells"]) == 4
    for selection in (summary["oracle_selection"], summary["fixed_selection"]):
        assert all(candidate["episodes"] == 16 for candidate in selection["candidates"])


def test_selection_weights_share_of_need_equally_across_demand_levels():
    rows = synthetic_rows()
    for row in rows:
        job = row["job"]
        if job["arm"] == "R-oracle":
            score = ({1.2: .9, 1.6: .5} if job["phi"] == .375 else {1.2: .6, 1.6: .75})[job["need"]]
            set_scores(row, score)
    selection = consequence.select_oracle(rows)
    # Weighting by raw consumption would incorrectly prefer phi=.5.
    assert .9 * 1.2 + .5 * 1.6 < .6 * 1.2 + .75 * 1.6
    assert selection["selected"] == .375
    assert [c["share_of_need"] for c in selection["candidates"]] == pytest.approx([.7, .675])


@pytest.mark.parametrize("late_breaks_tie", [False, True])
def test_oracle_exact_ties_use_final_quarter_then_smaller_phi(late_breaks_tie):
    rows = synthetic_rows()
    for row in rows:
        if row["job"]["arm"] == "R-oracle":
            set_scores(row, .75, .9 if late_breaks_tie and row["job"]["phi"] == .5 else .7)
    expected = .5 if late_breaks_tie else .375
    assert consequence.select_oracle(rows)["selected"] == expected
    assert consequence.select_oracle(list(reversed(rows)))["selected"] == expected


@pytest.mark.parametrize("late_breaks_tie", [False, True])
def test_fixed_exact_ties_use_final_quarter_then_smaller_capacity(late_breaks_tie):
    rows = synthetic_rows()
    for row in rows:
        if row["job"]["arm"] == "R-fixed":
            set_scores(row, .75, .9 if late_breaks_tie and row["job"]["fixed_capacity"] == 30. else .7)
    expected = 30. if late_breaks_tie else 20.
    assert consequence.select_fixed(rows, .375)["selected"] == expected
    assert consequence.select_fixed(list(reversed(rows)), .375)["selected"] == expected


@pytest.mark.parametrize("mean,passed", [(math.nextafter(.08, 0.), False),
                                       (.08, True), (math.nextafter(.08, math.inf), True)])
def test_g1_uses_mean_threshold_inclusively_without_a_confidence_interval_requirement(mean, passed):
    rows = gate_rows((0., 0., 0., 4 * mean))
    result = consequence.summarize(rows)["G1"]
    assert result["threshold"] == .08
    assert result["contrast"]["mean"] == mean
    assert result["contrast"]["n"] == 4
    assert result["contrast"]["ci95"][0] < 0 < result["contrast"]["ci95"][1]
    assert result["passed"] is passed


def test_gate_pairs_by_seed_and_uses_variability_of_differences_not_unpaired_arms():
    differences = (-.05, .03, .2, .3)
    rows = gate_rows(differences, fixed_shares=(.2, .3, .4, .5))
    summary = consequence.summarize(rows)
    assert consequence.summarize(list(reversed(rows))) == summary
    gate_cell = next(c for c in summary["cells"] if (c["condition"], c["need"]) == ("wide", 1.6))
    assert [d["seed"] for d in gate_cell["paired_differences"]] == list(consequence.SEEDS)
    assert [d["share_of_need"] for d in gate_cell["paired_differences"]] == pytest.approx(differences)
    half = 3.182446305284263 * st.stdev(differences) / math.sqrt(4)
    assert summary["G1"]["contrast"]["ci95"] == pytest.approx([st.mean(differences) - half,
                                                              st.mean(differences) + half])
    assert summary["experimental_model_calls"] == summary["evolutionary_runs"] == 0
    assert "development" in summary["scope"] and "reused" in summary["scope"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_phi", "extra_arm", "extra_seed"])
def test_complete_inventory_rejects_missing_duplicate_and_uncontracted_rows(mutation):
    rows = synthetic_rows()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif mutation == "wrong_phi":
        next(row for row in rows if row["job"]["arm"] == "R-fixed")["job"]["phi"] = .5
    elif mutation == "extra_arm":
        rows[-1]["job"]["arm"] = "L0"
    else:
        rows[-1]["job"]["seed"] = 90005
    with pytest.raises(ValueError):
        consequence.summarize(rows)


def test_selection_requires_all_candidates_before_choosing_one():
    rows = synthetic_rows()
    one_oracle = [row for row in rows if row["job"]["arm"] == "R-oracle" and row["job"]["phi"] == .375]
    one_fixed = [row for row in rows if row["job"]["arm"] == "R-fixed" and row["job"]["fixed_capacity"] == 20.]
    with pytest.raises(ValueError):
        consequence.select_oracle(one_oracle)
    with pytest.raises(ValueError):
        consequence.select_fixed(one_fixed, .375)
    with pytest.raises(ValueError):
        consequence.select_fixed(rows, .5)


@pytest.mark.parametrize("field", ["initial_snapshot", "weather_sha256"])
def test_pairing_checks_include_unselected_candidates_in_every_case(field):
    rows = synthetic_rows()
    row = next(r for r in rows if r["job"]["arm"] == "R-oracle" and r["job"]["phi"] == .5)
    if field == "initial_snapshot":
        row[field]["sha256"] = "0" * 64
    else:
        row[field] = "0" * 64
    with pytest.raises(ValueError, match="paired"):
        consequence.summarize(rows)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "0.8"])
def test_selection_rejects_nonfinite_and_nonnumeric_scores(value):
    rows = synthetic_rows()
    rows[0]["summary"]["share_of_need"] = value
    with pytest.raises(ValueError):
        consequence.select_oracle(rows)


@pytest.mark.parametrize("field", ["final_quarter_share_of_need", "message_cost", "max_ledger_residual"])
def test_summarize_rejects_nonfinite_diagnostics_before_reporting_them(field):
    rows = synthetic_rows()
    rows[-1]["summary"][field] = float("nan")
    with pytest.raises(ValueError):
        consequence.summarize(rows)


@pytest.mark.parametrize("arm", ["R-oracle", "R-fixed", "R-greedy"])
def test_short_episode_exact_replay_and_consumption_timing(monkeypatch, arm):
    monkeypatch.setattr(consequence, "HORIZON", 8)
    job = consequence.candidate_jobs(arm, None if arm == "R-oracle" else .375)[0]
    original = deepcopy(job)
    result = consequence.run_episode(job)
    assert consequence.run_episode(job) == result
    assert job == original
    assert result["horizon"] == 8
    assert result["initial_snapshot"]["engine_version"] == engine.VERSION
    initial = engine.restore(result["initial_snapshot"])
    final = engine.restore(result["final_snapshot"])
    assert initial.tick == 0 and final.tick == 8
    assert [frame["tick"] for frame in result["ticks"]] == list(range(1, 9))
    assert len(result["agents"]) == 24
    n, need = initial.config.n_agents, job["need"]
    assert result["summary"]["share_of_need"] == pytest.approx(
        math.fsum(frame["consumption"] for frame in result["ticks"]) / (8 * n * need))
    assert result["summary"]["final_quarter_share_of_need"] == pytest.approx(
        math.fsum(frame["consumption"] for frame in result["ticks"][-2:]) / (2 * n * need))
    assert result["summary"]["share_of_need"] == pytest.approx(st.mean(a["share_of_need"] for a in result["agents"]))
    assert result["summary"]["message_bytes"] == result["summary"]["message_cost"] == 0
    assert result["summary"]["max_ledger_residual"] < 1e-10
    assert asdict(initial.config)["site_capacities"] == asdict(final.config)["site_capacities"]


@pytest.mark.parametrize("field,value", [("seed", 90005), ("need", 2.), ("condition", "uniform"),
                                       ("phi", .25), ("fixed_capacity", 25.)])
def test_runner_rejects_jobs_outside_the_contract_before_initializing(monkeypatch, field, value):
    job = consequence.candidate_jobs("R-fixed", .375)[0]
    job[field] = value
    def forbidden(*args, **kwargs):
        pytest.fail("an invalid job reached physical initialization")
    monkeypatch.setattr(consequence.worlds, "initialize", forbidden)
    with pytest.raises(ValueError):
        consequence.run_episode(job)
