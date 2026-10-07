"""Cohort accounting and deliberately arranged exclusion consequences."""
from dataclasses import replace

import pytest

from scripts.demo_commons_v3_exclusion_v1 import local_state, run_demo
from swarm_societies.commons_v3 import engine, politics_v1 as politics
from swarm_societies.commons_v3 import exclusion_v1 as exclusion
from swarm_societies.commons_v3.exclusion_measurement_v1 import summarize_step


def transition():
    state = local_state()
    result = exclusion.step(state, tuple(engine.Action(harvest=4.) for _ in range(3)),
        forces=(exclusion.Force(guard=1.), exclusion.Force(), exclusion.Force(resist=1.)))
    return state, result


def test_both_partitions_reconcile_and_costs_are_not_deducted_again():
    state, result = transition()
    summary = summarize_step(state, result, (0, 1))
    cohorts = summary["cohorts"]
    for left, right in (("original_members", "original_outsiders"),
                        ("opening_members", "opening_outsiders")):
        for field in cohorts["population"]:
            assert cohorts[left][field] + cohorts[right][field] == pytest.approx(cohorts["population"][field])
    assert cohorts["population"]["consumption"] == result.political.physical.ledger.consumption
    assert cohorts["original_members"]["guard_cost"] == .1
    assert cohorts["original_outsiders"]["resistance_cost"] == .1


def test_fixed_reference_group_retains_exiters():
    state = local_state(20., (3., 3., 3.))
    actions = (engine.Action(),) * 3
    exited = exclusion.step(state, actions,
        intents=(politics.Intent(kind="exit"), politics.Intent(), politics.Intent()))
    following = exclusion.step(exited.state, actions)
    summary = summarize_step(exited.state, following, (0, 1))
    assert summary["original_member_ids"] == [0, 1]
    assert summary["opening_member_ids"] == [1]
    assert summary["cohorts"]["original_members"]["count"] == 2
    assert summary["cohorts"]["opening_members"]["count"] == 1


def test_guard_and_private_monitor_costs_are_attributed_without_double_subtraction():
    state = local_state(20., (.4, .4, .4))
    result = exclusion.step(state, (engine.Action(),) * 3,
        intents=(politics.Intent("monitor", target=0), politics.Intent(), politics.Intent()),
        forces=(exclusion.Force(guard=1.), exclusion.Force(), exclusion.Force()))
    group = summarize_step(state, result, (0,))["cohorts"]["original_members"]
    assert group["guard_cost"] == .1
    assert group["political_fee_private"] == .05
    assert group["consumption"] == pytest.approx(.25)


def test_absent_reference_group_is_empty_without_imputed_welfare():
    state, result = transition()
    group = summarize_step(state, result, ())["cohorts"]["original_members"]
    assert group["count"] == 0
    assert all(value == 0 for value in group.values())


@pytest.mark.parametrize("ids", [(True,), (-1,), (3,), (0, 0), (1.,)])
def test_invalid_reference_group_rejected(ids):
    state, result = transition()
    with pytest.raises(ValueError, match="cohort"):
        summarize_step(state, result, ids)


def test_wrong_boundary_is_rejected():
    state, result = transition()
    with pytest.raises(ValueError, match="boundary"):
        summarize_step(result.state, result, (0, 1))
    other_seed = replace(state, political=replace(state.political,
        world=replace(state.political.world, seed=99)))
    with pytest.raises(ValueError, match="boundary"):
        summarize_step(other_seed, result, (0, 1))


def test_constructed_demo_retains_both_member_gain_and_loss_and_outsider_harm():
    report = run_demo()
    scarcity = report["scarce_site"]["force_minus_no_force"]
    assert scarcity["original_members"]["consumption"] > 0
    assert scarcity["original_outsiders"]["consumption"] < 0
    assert report["abundant_site"]["force_minus_no_force"]["original_members"]["consumption"] < 0
    assert report["rival_claims"]["force_minus_no_force"]["population"]["consumption"] < 0
    assert report["continued_physical_ticks"] == 4
    assert report["sampled_development_episodes"] == report["model_calls"] == 0
