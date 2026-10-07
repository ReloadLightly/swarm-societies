"""Independent evaluator accounting, cohort, and local-obligation checks."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from swarm_societies.commons_v3 import engine as physical
from swarm_societies.commons_v3 import politics_v1 as politics
from swarm_societies.commons_v3.institution_measurement_v1 import record_tick, summarize


def fixture(*, need=0., inventories=(8., 8., 8.), stock=20., institution=True):
    config = physical.Config(width=4, height=4, n_agents=len(inventories), n_patches=1,
        sensing_radius=1, need=need, initial_inventory=8., inventory_capacity=20.,
        patch_capacity=20., initial_patch_stock=stock, renewal_rate=0., recovery=0.,
        weather_amplitude=0., max_harvest=10., movement_cost=0., harvest_cost_per_unit=0.,
        message_byte_cost=0.)
    state = politics.initialize(config, 24)
    world = replace(state.world,
        agents=tuple(replace(agent, x=0, y=0, inventory=amount)
                     for agent, amount in zip(state.world.agents, inventories)),
        patches=(replace(state.world.patches[0], x=0, y=0),))
    state = replace(state, world=world)
    if institution:
        institution = politics.Institution(0, 0, politics.Charter(quota=1., bond=1., dues=.1, fine=.5),
            (0, 1), (politics.Bond(0, 1.), politics.Bond(1, 1.)))
        state = replace(state, institutions=(institution,), next_id=1)
    politics.snapshot(state)
    return state


def advance(state, intents=None, actions=None):
    intents = tuple((intents or {}).get(agent.id, politics.Intent()) for agent in state.world.agents)
    actions = tuple((actions or {}).get(agent.id, physical.Action()) for agent in state.world.agents)
    result = politics.step(state, actions, intents)
    return result, record_tick(state, result, actions, intents)


def test_terminal_book_ownership_allocates_custody_once_without_liquidation():
    initial = fixture()
    deposited, row1 = advance(initial, {0: politics.Intent("pay", 0, amount=3.),
                                      2: politics.Intent("cache", 0, amount=2.)})
    exited, row2 = advance(deposited.state, {1: politics.Intent("exit", 0)})
    before_summary = politics.snapshot(exited.state)
    result = summarize(initial, exited.state, [row1, row2], cohorts={"eligible": [0, 1], "stubborn": [2]})
    end = result["terminal"]
    assert end["cache"] == 2.
    assert end["active_bond"] == 1.
    assert end["released_claim"] == 1.
    assert end["mature_claim"] == 0.
    assert end["pooled_treasury"] == 3.
    assert end["custody_total"] == 7.
    assert end["book_wealth"] == pytest.approx(end["inventory"] + end["custody_total"])
    owners = [agent["terminal_wealth"] for agent in result["agents"]]
    assert owners[0]["pooled_treasury_share"] == 3.
    assert owners[1]["pooled_treasury_share"] == 0.
    assert owners[1]["released_claim"] == 1.
    assert result["agents"][0]["carried_utility"]["0.05"] == pytest.approx(.05 * 5. / 2)
    assert result["agents"][0]["book_utility"]["0.05"] == pytest.approx(.05 * 9. / 2)
    assert all(agent["carried_utility"]["0.0"] == agent["book_utility"]["0.0"] for agent in result["agents"])
    assert result["initial"]["book_wealth"] == 26.
    assert politics.snapshot(exited.state) == before_summary
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_unmonitored_and_observed_violations_use_actual_local_allocation():
    initial = fixture()
    unobserved, row1 = advance(initial, actions={1: physical.Action(harvest=3.)})
    assert row1["agents"][1]["actual_violation"]
    assert not row1["agents"][1]["observed_violation"]
    observed, row2 = advance(unobserved.state,
        {0: politics.Intent("monitor", 0), 1: politics.Intent("monitor", 0)},
        {1: physical.Action(harvest=3.), 2: physical.Action(harvest=3.)})
    assert len([receipt for receipt in observed.state.evidence if receipt.subject == 1]) == 2
    assert row2["agents"][1]["actual_violation"]
    assert row2["agents"][1]["observed_violation"]
    outsider = row2["agents"][2]
    assert outsider["extraction_observed"]
    assert outsider["nonmember_at_institutional_site"]
    assert outsider["bound_quota"] is None
    assert not outsider["actual_violation"] and not outsider["observed_violation"]
    result = summarize(initial, observed.state, [row1, row2], cohorts={"eligible": [0, 1], "stubborn": [2]})
    assert result["cohorts"]["population"]["actual_violations"] == 2
    assert result["cohorts"]["population"]["observed_violations"] == 1


def test_overquota_request_is_not_a_violation_when_contention_limits_allocation():
    initial = fixture(stock=2.)
    _, row = advance(initial, {0: politics.Intent("monitor", 0)},
                     {0: physical.Action(harvest=4.), 1: physical.Action(harvest=4.)})
    assert row["agents"][1]["requested_harvest"] == 4.
    assert row["agents"][1]["harvested"] == 1.
    assert not row["agents"][1]["actual_violation"]
    assert not row["agents"][1]["observed_violation"]


def test_opening_membership_binds_exiters_but_does_not_retroactively_bind_joiners():
    initial = fixture()
    _, row = advance(initial, {0: politics.Intent("monitor", 0), 1: politics.Intent("exit", 0),
                              2: politics.Intent("join", 0)},
                     {1: physical.Action(harvest=3.), 2: physical.Action(harvest=3.)})
    leaver, entrant = row["agents"][1:]
    assert leaver["membership_after"] is None
    assert leaver["actual_violation"] and leaver["observed_violation"]
    assert entrant["membership_after"] == 0
    assert entrant["bound_quota"] is None and not entrant["actual_violation"]


def test_offsite_members_are_not_bound_to_a_remote_quota():
    initial = fixture()
    _, row = advance(initial, actions={1: physical.Action(move=(1, 0), harvest=4.)})
    away = row["agents"][1]
    assert away["membership_before"] == 0
    assert away["at_affiliated_site_before"] and not away["at_affiliated_site_after"]
    assert away["off_site"] and away["bound_quota"] is None
    assert not away["actual_violation"]


def test_pooled_costs_attribute_operator_without_charging_private_inventory_again():
    initial = fixture()
    funded, row1 = advance(initial, {1: politics.Intent("pay", 0, amount=.4)})
    detected, row2 = advance(funded.state, {0: politics.Intent("monitor", 0, funding="treasury")},
                             {1: physical.Action(harvest=3.)})
    receipt = next(receipt for receipt in detected.state.evidence if receipt.subject == 1)
    settled, row3 = advance(detected.state, {0: politics.Intent("sanction", receipt.id, funding="treasury")})
    result = summarize(initial, settled.state, [row1, row2, row3], cohorts={"eligible": [0, 1], "stubborn": [2]})
    operator, subject = result["agents"][:2]
    assert operator["political_fee_private"] == 0.
    assert operator["political_fee_treasury_operator"] == pytest.approx(.07)
    assert subject["dues_contribution"] == .4
    assert subject["collateral_forfeited"] == .5
    assert operator["collateral_forfeited"] == 0.
    assert result["political_cost"] == pytest.approx(.07)
    assert result["forfeited"] == .5
    assert result["terminal"]["book_wealth"] == pytest.approx(result["initial"]["book_wealth"] + 3. - .07 - .5)


def test_primary_consumption_already_pays_operating_costs_and_empty_membership_is_valid():
    initial = fixture(need=1., inventories=(1.02,), institution=False)
    result, row = advance(initial, {0: politics.Intent("monitor", 0)})
    summary = summarize(initial, result.state, [row], cohorts={"eligible": [0], "stubborn": []})
    population = summary["cohorts"]["population"]
    assert population["consumption_per_tick"] == pytest.approx(.97)
    assert population["consumption_need_fraction"] == pytest.approx(.97)
    assert population["shortfall_per_tick"] == pytest.approx(.03)
    assert summary["political_cost"] == .05
    assert summary["dynamic_membership_diagnostics"]["member"]["agent_ticks"] == 0
    assert summary["dynamic_membership_diagnostics"]["member"]["consumption_per_agent_tick"] is None
    assert summary["institution_free_ticks"] == 1
    assert summary["cohorts"]["stubborn"]["consumption"] == 0.
    assert summary["cohorts"]["stubborn"]["consumption_per_tick"] is None
    assert summary["cohorts"]["stubborn"]["shortfall_gini"] is None
    assert summary["cohorts"]["stubborn"]["book_utility"]["0.05"] is None


def test_original_cohorts_keep_exiters_when_current_member_denominator_changes():
    initial = fixture(need=1., inventories=(3., .5, 0.))
    exited, row1 = advance(initial, {1: politics.Intent("exit", 0)})
    final, row2 = advance(exited.state)
    summary = summarize(initial, final.state, [row1, row2], cohorts={"eligible": [0, 1], "stubborn": [2]}, late_window=1)
    eligible = summary["cohorts"]["eligible"]
    assert eligible["ids"] == [0, 1] and eligible["n"] == 2
    assert eligible["terminal_members"] == 1 and eligible["exit_count"] == 1
    assert eligible["consumption_per_tick"] == .625
    assert eligible["late_consumption_per_tick"] == .5
    assert summary["dynamic_membership_diagnostics"]["member"]["consumption_per_agent_tick"] == pytest.approx(2.5 / 3)
    assert summary["agents"][1]["shortfall"] == 1.5
    assert eligible["shortfall_gini"] == .5
    assert eligible["shortfall_per_tick_p90"] == pytest.approx(.675)


def test_summary_rejects_missing_ticks_duplicate_original_ids_and_lost_population():
    initial = fixture()
    next_, row1 = advance(initial)
    final, row2 = advance(next_.state)
    with pytest.raises(ValueError, match="complete trajectory"):
        summarize(initial, final.state, [row1], cohorts={})
    with pytest.raises(ValueError, match="incomplete"):
        summarize(initial, final.state, [row2, row1], cohorts={})
    with pytest.raises(ValueError, match="unique"):
        summarize(initial, final.state, [row1, row2], cohorts={"eligible": [0, 0]})
    with pytest.raises(ValueError, match="every original"):
        summarize(initial, final.state, [row1, row2], cohorts={"population": [0, 1]})
    bad = deepcopy(row1)
    bad["agents"].reverse()
    with pytest.raises(ValueError, match="agent order"):
        summarize(initial, final.state, [bad, row2], cohorts={})


def test_book_shares_conserve_fractional_pool_and_mature_claim_is_only_a_subset():
    initial = fixture()
    initial = replace(initial, institutions=(replace(initial.institutions[0], treasury=.1),),
                      caches=(politics.Cache(2, 0, .3),))
    exited, row1 = advance(initial, {1: politics.Intent("exit", 0)})
    mature, row2 = advance(exited.state)
    result = summarize(initial, mature.state, [row1, row2], cohorts={})
    assert result["initial"]["pooled_treasury_share"] == .1
    assert result["terminal"]["mature_claim"] == result["terminal"]["released_claim"] == 1.
    assert result["terminal"]["book_wealth"] == pytest.approx(result["terminal"]["inventory"] + result["terminal"]["custody_total"])
    assert math.fsum(agent["terminal_wealth"]["pooled_treasury_share"] for agent in result["agents"]) == .1
    assert result["cohorts"]["population"]["consumption_need_fraction"] is None


def test_summary_rejects_changed_consumption_or_misattributed_political_cost():
    initial = fixture(need=1.)
    final, row = advance(initial, {0: politics.Intent("monitor", 0)})
    changed = deepcopy(row)
    changed["agents"][0]["consumption"] += .01
    with pytest.raises(ValueError, match="physical totals"):
        summarize(initial, final.state, [changed], cohorts={})
    changed = deepcopy(row)
    changed["agents"][0]["political_fee_private"] = 0.
    with pytest.raises(ValueError, match="political costs"):
        summarize(initial, final.state, [changed], cohorts={})


def test_utility_need_normalization_preserves_both_weight_conventions_and_empty_cohorts():
    initial = fixture(need=1.2)
    final, row = advance(initial)
    result = summarize(initial, final.state, [row], cohorts={"eligible": [0, 1], "stubborn": []})
    for agent in result["agents"]:
        for name in ("carried_utility", "book_utility"):
            for weight, value in agent[name].items():
                assert agent[name + "_need_fraction"][weight] == pytest.approx(value / 1.2)
    for name in ("carried_utility", "book_utility"):
        for weight, value in result["cohorts"]["eligible"][name].items():
            assert result["cohorts"]["eligible"][name + "_need_fraction"][weight] == pytest.approx(value / 1.2)
            assert result["cohorts"]["stubborn"][name + "_need_fraction"][weight] is None
    initial = fixture()
    final, row = advance(initial)
    result = summarize(initial, final.state, [row], cohorts={})
    assert all(value is None for value in result["agents"][0]["book_utility_need_fraction"].values())
    assert all(value is None for value in result["cohorts"]["population"]["carried_utility_need_fraction"].values())


def test_depletion_fraction_uses_strict_tenth_capacity_and_final_physical_stock():
    initial = fixture(stock=2.)
    boundary, row1 = advance(initial)
    depleted, row2 = advance(boundary.state, actions={0: physical.Action(harvest=.01)})
    assert row1["depleted_patch_fraction"] == 0.
    assert row2["depleted_patch_fraction"] == 1.
    result = summarize(initial, depleted.state, [row1, row2], cohorts={}, late_window=1)
    assert result["mean_depleted_patch_fraction"] == .5
    assert result["late_mean_depleted_patch_fraction"] == 1.
    assert result["terminal"]["depleted_patch_fraction"] == 1.
    assert result["mean_stock_fraction"] == pytest.approx((2. + 1.99) / 40.)
    assert result["late_mean_stock_fraction"] == pytest.approx(1.99 / 20.)
