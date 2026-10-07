"""Physical and local-information checks for the need-target baseline bundle."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from swarm_societies.commons_v3.engine import (
    AgentState, Config, PatchState, WorldState, initialize, observe, observations,
    snapshot, step,
)
from swarm_societies.commons_v3.policies_need_v1 import NeedTargetPolicy


def world(*, inventory=0., stock=30., cost=.02, need=1., capacity=80., **changes):
    values = dict(width=11, height=11, n_agents=1, n_patches=1,
                  initial_inventory=inventory, inventory_capacity=capacity,
                  movement_cost=cost, need=need, initial_patch_stock=stock,
                  renewal_rate=0., recovery=0., weather_amplitude=0.,
                  max_harvest=10.)
    values.update(changes)
    cfg = Config(**values)
    return WorldState(cfg, 17, 0, (AgentState(0, 5, 5, inventory),),
                      (PatchState(0, 5, 5, stock),))


def home_distance(agent, policy):
    return min(abs(agent.x - x) + abs(agent.y - y) for x, y in policy.sites.values())


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_gross_harvest_pays_cost_and_meets_need_with_only_fuel_withheld(reserve_ticks):
    state = world(harvest_cost_per_unit=.25)
    action = NeedTargetPolicy(reserve_ticks)(observe(state, 0))
    fuel = .08 + 8e-9
    assert state.config.inventory_capacity == 80.
    assert action.move == (0, 0)
    assert action.reserve == fuel
    assert action.harvest == pytest.approx((1. + reserve_ticks + fuel) / .75)
    result = step(state, (action,))
    assert result.ledger.harvest_cost == pytest.approx(.25 * action.harvest)
    assert result.ledger.consumption == pytest.approx(1.)
    assert result.state.agents[0].inventory == pytest.approx(reserve_ticks + fuel)
    assert result.ledger.waste == 0.
    assert abs(result.ledger.residual) < 1e-12


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_inventory_at_target_waits_even_beside_richer_site(reserve_ticks):
    inventory = 1. + reserve_ticks + .08 + 8e-9
    state = world(inventory=inventory)
    state = replace(state, config=replace(state.config, n_patches=2),
                    patches=state.patches + (PatchState(1, 6, 5, 40.),))
    action = NeedTargetPolicy(reserve_ticks)(observe(state, 0))
    assert action.move == (0, 0)
    assert action.harvest == 0.
    assert step(state, (action,)).ledger.consumption == pytest.approx(1.)


def test_partial_need_coverage_accepts_small_topup_instead_of_scouting():
    state = world(inventory=.875, stock=.125, cost=0., harvest_cost_per_unit=0.)
    action = NeedTargetPolicy(0)(observe(state, 0))
    assert action.harvest == .125  # Below v2's fixed half-need acceptance.
    assert action.move == (0, 0)
    assert action.reserve == 0.
    result = step(state, (action,))
    assert result.ledger.consumption == 1.
    assert result.state.agents[0].inventory == 0.


def test_small_buffer_topup_is_taken_when_current_need_already_covered():
    state = world(inventory=2.875, stock=.125, cost=0., harvest_cost_per_unit=0.)
    action = NeedTargetPolicy(2)(observe(state, 0))
    assert action.move == (0, 0)
    assert action.harvest == .125
    result = step(state, (action,))
    assert result.ledger.consumption == 1.
    assert result.state.agents[0].inventory == 2.


def test_two_tick_buffer_is_consumed_on_poor_harvest_ticks():
    state = world(inventory=2.25, stock=0., cost=0.)
    policy = NeedTargetPolicy(2)
    for inventory_after in (1.25, .25):
        action = policy(observe(state, 0))
        assert action.move == (0, 0)
        assert action.reserve == action.harvest == 0.
        result = step(state, (action,))
        assert result.ledger.consumption == 1.
        assert result.state.agents[0].inventory == inventory_after
        state = result.state


@pytest.mark.parametrize("reserve_ticks", [0, 2])
@pytest.mark.parametrize("inventory", [0., 79., 79.999991, 80.])
def test_target_and_gross_harvest_respect_preconsumption_capacity(reserve_ticks, inventory):
    state = world(inventory=inventory, need=100., stock=40., max_harvest=100.,
                  harvest_cost_per_unit=.25)
    action = NeedTargetPolicy(reserve_ticks)(observe(state, 0))
    assert action.move == (0, 0)
    assert action.harvest == min(40., (80. - inventory) / .75)
    result = step(state, (action,))
    assert result.ledger.waste <= 1e-13
    assert result.state.agents[0].inventory >= 0.
    assert abs(result.ledger.residual) < 1e-12


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_max_harvest_limits_gross_request(reserve_ticks):
    state = world(need=10., max_harvest=2., harvest_cost_per_unit=.25,
                  width=1, height=1)
    state = replace(state, agents=(replace(state.agents[0], x=0, y=0),),
                    patches=(replace(state.patches[0], x=0, y=0),))
    action = NeedTargetPolicy(reserve_ticks)(observe(state, 0))
    assert action.harvest == 2.
    result = step(state, (action,))
    assert result.ledger.harvest_cost == .5
    assert result.ledger.consumption == pytest.approx(1.5 - action.reserve)


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_partial_stock_is_harvested_when_unaffordable_scouting_leaves_fallback(reserve_ticks):
    state = world(inventory=0., stock=.125, cost=.02, harvest_cost_per_unit=0.)
    action = NeedTargetPolicy(reserve_ticks)(observe(state, 0))
    assert action.move == (0, 0)
    assert action.harvest == .125
    result = step(state, (action,))
    assert result.ledger.consumption == pytest.approx(.125 - action.reserve)
    assert result.state.patches[0].stock == 0.


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_move_toward_accepted_visible_site_preserves_v2_no_simultaneous_harvest(reserve_ticks):
    state = world(inventory=.5)
    state = replace(state, agents=(replace(state.agents[0], x=4),))
    action = NeedTargetPolicy(reserve_ticks)(observe(state, 0))
    assert action.move == (1, 0)
    assert action.harvest == 0.
    result = step(state, (action,))
    assert result.ledger.movement_cost == .02
    assert result.ledger.agents[0].harvested == 0.


@pytest.mark.parametrize("reserve_ticks", [0, 2])
@pytest.mark.parametrize("cost", [.00001, .02, .3, 2.])
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_scouting_preserves_strict_prospective_return_fuel_boundary(reserve_ticks, cost, side):
    state = world(inventory=4 * cost, stock=0., cost=cost, need=10.)
    policy = NeedTargetPolicy(reserve_ticks)
    policy(observe(state, 0))
    threshold = 2 * cost + 1e-9 * max(1., 2 * cost)
    budget = math.nextafter(threshold, -math.inf if side < 0 else math.inf) if side else threshold
    state = replace(state, tick=1, agents=(replace(state.agents[0], x=7, inventory=budget),))
    assert observe(state, 0)["sites"] == []
    action = policy(observe(state, 0))
    if side < 0:
        assert action.move == (0, 0)
    else:
        assert action.move == (-1, 0)
        result = step(state, (action,))
        assert result.ledger.movement_cost == cost
        assert result.state.agents[0].inventory >= cost


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_historical_float_return_trap_stays_repaired(reserve_ticks):
    state = world(inventory=.08, stock=0.)
    policy = NeedTargetPolicy(reserve_ticks)
    positions = []
    for _ in range(12):
        action = policy(observe(state, 0))
        result = step(state, (action,))
        state = result.state
        actor = state.agents[0]
        positions.append((actor.x, actor.y))
        assert actor.inventory >= state.config.movement_cost * home_distance(actor, policy)
        assert actor.inventory + actor.movement_cost + actor.consumption == pytest.approx(.08, abs=1e-15)
        assert abs(result.ledger.residual) < 1e-12
    assert positions[0] != (5, 5)
    assert (5, 5) in positions[1:]


def test_fuel_reserve_is_capacity_capped_without_resource_buffer_withholding():
    state = world(inventory=.03, stock=0., capacity=.03)
    action = NeedTargetPolicy(2)(observe(state, 0))
    assert action.reserve == .03
    assert action.move == (0, 0)
    result = step(state, (action,))
    assert result.ledger.consumption == 0.
    assert result.state.agents[0].inventory == .03


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_memory_contains_only_legal_observed_history_and_packet_is_unmodified(reserve_ticks):
    state = world(inventory=.08, stock=0.)
    state = replace(state, config=replace(state.config, n_agents=2, n_patches=2),
                    agents=state.agents + (AgentState(1, 10, 10, 7.),),
                    patches=state.patches + (PatchState(1, 10, 10, 30.),))
    hidden_changed = replace(state, seed=908, config=replace(state.config, renewal_rate=.7, weather_amplitude=.4),
                             agents=(state.agents[0], replace(state.agents[1], inventory=69.)),
                             patches=(state.patches[0], replace(state.patches[1], stock=1.)))
    packets = [observe(s, 0) for s in (state, hidden_changed)]
    before = deepcopy(packets)
    policies = [NeedTargetPolicy(reserve_ticks), NeedTargetPolicy(reserve_ticks)]
    assert packets[0] == packets[1]
    assert policies[0](packets[0]) == policies[1](packets[1])
    assert packets == before
    assert policies[0].memory() == policies[1].memory()
    assert policies[0].memory() == {
        "version": "commons-v3-need-target-policy-v1", "mode": "need_target",
        "reserve_ticks": reserve_ticks, "sites": [[0, 5, 5]], "visits": [[5, 5, 1]],
    }
    assert json.loads(json.dumps(policies[0].memory())) == policies[0].memory()


@pytest.mark.parametrize("reserve_ticks", [0, 2])
def test_repeat_is_deterministic_with_equal_packet_history(reserve_ticks):
    original = initialize(Config(width=3, height=3, n_agents=2, n_patches=1), seed=712)
    runs = []
    for _ in range(2):
        state = original
        policies = [NeedTargetPolicy(reserve_ticks) for _ in state.agents]
        frames = []
        for _ in range(12):
            actions = tuple(policy(packet) for policy, packet in zip(policies, observations(state)))
            assert all(action.messages == action.transfers == () for action in actions)
            result = step(state, actions)
            assert result.ledger.waste <= 1e-13
            state = result.state
            frames.append((actions, snapshot(state), [policy.memory() for policy in policies]))
        runs.append(frames)
    assert runs[0] == runs[1]


@pytest.mark.parametrize("value", [-1, 1, 3, 2., True, None, "2"])
def test_unsupported_or_ambiguous_buffer_values_are_rejected(value):
    with pytest.raises(ValueError, match="zero or two"):
        NeedTargetPolicy(value)
