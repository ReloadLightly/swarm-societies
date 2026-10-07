"""Exact physical and information fixtures for purposeful observed-map foraging."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from swarm_societies.commons_v3.engine import (
    AgentState, Config, PatchState, WorldState, observe, observations, snapshot, step,
)
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy, REVISIT_TICKS


def world(*, inventory=0., sites=((2, 2, 30.),), position=(2, 2), **changes):
    values = dict(width=12, height=5, n_agents=1, n_patches=len(sites),
                  need=1., initial_inventory=inventory, inventory_capacity=80.,
                  movement_cost=.02, harvest_cost_per_unit=.02, max_harvest=10.,
                  initial_patch_stock=0., renewal_rate=0., recovery=0., weather_amplitude=0.)
    values.update(changes)
    cfg = Config(**values)
    return WorldState(cfg, 17, 0, (AgentState(0, *position, inventory),),
                      tuple(PatchState(i, x, y, stock) for i, (x, y, stock) in enumerate(sites)))


def remember(policy, state, site_id, *, tick=0):
    """Seed a hypothetical continuation with an earlier legal on-site packet."""
    site = state.patches[site_id]
    earlier = replace(state, tick=tick,
                      agents=(replace(state.agents[0], x=site.x, y=site.y),))
    policy(observe(earlier, 0))
    policy.destination = policy.destination_kind = None


def assert_return_affordable(state, policy):
    actor = state.agents[0]
    if policy.sites:
        distance = min(abs(actor.x - x) + abs(actor.y - y) for x, y in policy.sites.values())
        assert actor.inventory >= state.config.movement_cost * distance


@pytest.mark.parametrize("reserve_ticks", [0, 2, 4])
def test_move_and_harvest_cover_gross_cost_and_preserve_only_fuel(reserve_ticks):
    state = world(inventory=.5, position=(1, 2), harvest_cost_per_unit=.25)
    action = ForagerPolicy(reserve_ticks)(observe(state, 0))
    assert action.move == (1, 0)
    fuel = .08 + 8e-9
    assert action.reserve == fuel
    assert action.harvest == pytest.approx((1. + reserve_ticks + fuel - .48) / .75)
    result = step(state, (action,))
    assert result.ledger.movement_cost == .02
    assert result.ledger.harvest_cost == pytest.approx(action.harvest * .25)
    assert result.ledger.consumption == pytest.approx(1.)
    assert result.state.agents[0].inventory == pytest.approx(reserve_ticks + fuel)
    assert result.ledger.waste == 0.
    assert abs(result.ledger.residual) < 1e-12


def test_adjacent_known_site_can_be_reached_with_exact_single_step_fuel():
    state = world(inventory=.02, position=(1, 2))
    action = ForagerPolicy()(observe(state, 0))
    assert action.move == (1, 0) and action.harvest > 0.
    result = step(state, (action,))
    assert result.ledger.movement_cost == .02
    assert result.ledger.consumption == 1.


@pytest.mark.parametrize("aggressive", [False, True])
@pytest.mark.parametrize("inventory", [79., 79.99999, 80.])
def test_headroom_is_physical_and_precedes_consumption(aggressive, inventory):
    state = world(inventory=inventory, need=100., harvest_cost_per_unit=.25,
                  width=1, height=1, sites=((0, 0, 30.),), position=(0, 0))
    action = ForagerPolicy(4, .5, aggressive=aggressive)(observe(state, 0))
    assert action.harvest == pytest.approx((80. - inventory) / .75)
    result = step(state, (action,))
    assert result.ledger.waste <= 1e-13
    assert result.ledger.consumption == pytest.approx(inventory + .75 * action.harvest - action.reserve)


def test_soft_food_buffer_can_be_consumed_and_does_not_mask_depleted_site():
    state = world(inventory=2.5, sites=((2, 2, 0.),))
    policy = ForagerPolicy(2)
    action = policy(observe(state, 0))
    assert action.move != (0, 0), "under-yield starts exploration while some food remains"
    result = step(state, (action,))
    assert result.ledger.consumption == 1.
    assert action.reserve < .2
    assert result.state.agents[0].inventory == pytest.approx(1.48)
    assert_return_affordable(result.state, policy)


def test_full_target_waits_without_scattering_to_frontiers():
    state = world(inventory=3.080000008, sites=((2, 2, 0.),))
    action = ForagerPolicy(2)(observe(state, 0))
    assert action.move == (0, 0) and action.harvest == 0.
    assert step(state, (action,)).ledger.consumption == 1.


def test_stock_floor_is_an_individual_share_and_aggressive_mode_removes_it():
    state = world(inventory=0., sites=((2, 2, 24.),))
    state = replace(state, config=replace(state.config, n_agents=2),
                    agents=state.agents + (replace(state.agents[0], id=1),))
    policies = [ForagerPolicy(4, .5) for _ in range(2)]
    actions = tuple(policy(packet) for policy, packet in zip(policies, observations(state)))
    assert [action.harvest for action in actions] == [2., 2.]
    assert step(state, actions).state.patches[0].stock == 20.
    aggressive = ForagerPolicy(4, .5, aggressive=True)(observe(state, 0))
    assert aggressive.harvest == 10.


@pytest.mark.parametrize("route_mode", ["nearest", "net_yield"])
def test_remote_observed_site_route_spends_real_fuel_without_oscillation(route_mode):
    state = world(inventory=.9, position=(1, 0), sites=((1, 0, 0.), (7, 0, 40.)),
                  width=10, height=1, need=2., movement_cost=.1, max_harvest=4.)
    policy = ForagerPolicy(2, route_mode=route_mode)
    remember(policy, state, 1)
    state = replace(state, tick=1)
    positions = []
    for _ in range(6):
        action = policy(observe(state, 0))
        assert action.move == (1, 0)
        result = step(state, (action,))
        assert result.ledger.movement_cost == .1
        assert abs(result.ledger.residual) < 1e-12
        state = result.state
        positions.append(state.agents[0].x)
        assert_return_affordable(state, policy)
    assert positions == [2, 3, 4, 5, 6, 7]
    assert result.ledger.agents[0].harvested > 0.
    assert result.ledger.consumption == pytest.approx(2.)


def test_route_reserve_protects_trip_fuel_but_not_a_food_buffer():
    state = world(inventory=2.5, position=(1, 0), sites=((1, 0, 0.), (9, 0, 40.)),
                  width=11, height=1, need=1., movement_cost=.1)
    policy = ForagerPolicy(4)
    remember(policy, state, 1)
    state = replace(state, tick=1)
    action = policy(observe(state, 0))
    assert action.move == (1, 0)
    assert action.reserve == pytest.approx(.8 + 8e-9)
    result = step(state, (action,))
    assert result.ledger.consumption == 1.
    assert result.state.agents[0].inventory == pytest.approx(1.4)


def test_small_local_harvest_can_pay_for_a_known_route_longer_than_base_fuel():
    state = world(inventory=.08, position=(0, 0), sites=((0, 0, .02), (5, 0, 30.)),
                  width=6, height=1, recovery=.02)
    policy = ForagerPolicy(2)
    # The hypothetical prior sensing history contains the whole corridor.
    for tick, x in enumerate(range(5, -1, -1)):
        past = replace(state, tick=tick, agents=(replace(state.agents[0], x=x),))
        policy(observe(past, 0))
    policy.destination = policy.destination_kind = None
    state = replace(state, tick=6)
    action = policy(observe(state, 0))
    assert policy.destination == (5, 0) and policy.destination_kind == "site"
    assert action.move == (0, 0)
    assert action.harvest == .02
    assert action.reserve == pytest.approx(.12 + 8e-9)
    first = step(state, (action,))
    assert first.ledger.consumption == 0.
    assert first.state.agents[0].inventory == pytest.approx(.0996)
    state = first.state
    for _ in range(8):
        action = policy(observe(state, 0))
        result = step(state, (action,))
        state = result.state
        assert_return_affordable(state, policy)
        assert abs(result.ledger.residual) < 1e-12
    assert state.agents[0].x == 5
    assert state.agents[0].movement_cost == pytest.approx(.1)
    assert result.ledger.consumption == pytest.approx(1.)


@pytest.mark.parametrize("route_mode, expected", [("nearest", (3, 0)), ("net_yield", (6, 0))])
def test_declared_route_rules_choose_different_observed_opportunities(route_mode, expected):
    state = world(inventory=.5, position=(2, 0), sites=((2, 0, 0.), (3, 0, .6), (6, 0, 4.)),
                  width=8, height=1, harvest_cost_per_unit=0., max_harvest=4.)
    policy = ForagerPolicy(2, route_mode=route_mode)
    remember(policy, state, 2)
    state = replace(state, tick=1)
    policy(observe(state, 0))
    assert policy.destination == expected
    assert policy.destination_kind == "site"


def test_newly_visible_empty_destination_cancels_stale_productive_route():
    state = world(inventory=1., position=(1, 0), sites=((1, 0, 0.), (5, 0, 30.)),
                  width=8, height=1, need=2.)
    policy = ForagerPolicy(2)
    remember(policy, state, 1)
    state = replace(state, tick=1, patches=(state.patches[0], replace(state.patches[1], stock=0.)))
    for _ in range(3):
        action = policy(observe(state, 0))
        state = step(state, (action,)).state
    assert state.agents[0].x == 4
    policy(observe(state, 0))
    assert policy.records[1]["stock"] == 0.
    assert not (policy.destination_kind == "site" and policy.destination == (5, 0))


def test_depleted_site_is_reinspected_after_full_map_exploration():
    state = world(inventory=.4, position=(0, 0), sites=((0, 0, 0.), (4, 0, 0.)),
                  width=5, height=1, need=1.)
    policy = ForagerPolicy(2)
    # Every stored cell/site is provided through a legal local packet.
    for tick, x in enumerate((4, 3, 2, 1, 0)):
        past = replace(state, tick=tick, agents=(replace(state.agents[0], x=x),))
        policy(observe(past, 0))
    policy.destination = policy.destination_kind = None
    assert policy.seen == {(x, 0) for x in range(5)}
    state = replace(state, tick=REVISIT_TICKS + 5)
    action = policy(observe(state, 0))
    assert policy.destination == (4, 0) and policy.destination_kind == "revisit"
    assert action.move == (1, 0)
    # The depleted site can recover out of sight. The actor learns the new
    # stock only when its actual local packet reaches that location.
    state = replace(state, patches=(state.patches[0], replace(state.patches[1], stock=30.)))
    for _ in range(4):
        action = policy(observe(state, 0))
        result = step(state, (action,))
        state = result.state
        assert_return_affordable(state, policy)
    assert state.agents[0].x == 4
    assert result.ledger.consumption == pytest.approx(1.)


def test_empty_fully_mapped_sites_do_not_create_immediate_return_oscillation():
    state = world(inventory=.1, position=(0, 0), sites=((0, 0, 0.), (1, 0, 0.)),
                  width=2, height=1)
    policy = ForagerPolicy(2)
    for _ in range(4):
        action = policy(observe(state, 0))
        assert action.move == (0, 0)
        state = step(state, (action,)).state


@pytest.mark.parametrize("cost", [0., .00001, .02, .3])
def test_empty_world_exploration_preserves_return_fuel_and_accounting(cost):
    state = world(inventory=max(.08, 4 * cost + 8e-9), sites=((2, 2, 0.),),
                  movement_cost=cost)
    policy = ForagerPolicy(2)
    for _ in range(48):
        action = policy(observe(state, 0))
        result = step(state, (action,))
        assert result.ledger.movement_cost == (cost if action.move != (0, 0) else 0.)
        assert abs(result.ledger.residual) < 1e-12
        state = result.state
        assert_return_affordable(state, policy)


@pytest.mark.parametrize("side", [-1, 0, 1])
def test_prospective_return_boundary_is_strict(side):
    state = world(inventory=.1, position=(2, 0), sites=((0, 0, 0.),), width=5, height=1)
    policy = ForagerPolicy(2)
    remember(policy, state, 0)
    threshold = .04 + 1e-9
    budget = math.nextafter(threshold, -math.inf if side < 0 else math.inf) if side else threshold
    state = replace(state, tick=1, agents=(replace(state.agents[0], inventory=budget),))
    action = policy(observe(state, 0))
    if side < 0:
        assert action.move == (0, 0)
    else:
        assert action.move == (-1, 0)
        result = step(state, (action,))
        assert_return_affordable(result.state, policy)


def test_policy_memory_and_actions_do_not_reveal_hidden_environment_changes():
    state = world(inventory=.1, sites=((2, 2, 0.), (11, 4, 30.)))
    hidden = replace(state, seed=918, config=replace(state.config, renewal_rate=.7, weather_amplitude=.9),
                     patches=(state.patches[0], replace(state.patches[1], stock=0.)))
    packets = [observe(s, 0) for s in (state, hidden)]
    before = deepcopy(packets)
    policies = [ForagerPolicy(), ForagerPolicy()]
    assert packets[0] == packets[1]
    assert policies[0](packets[0]) == policies[1](packets[1])
    assert policies[0].memory() == policies[1].memory()
    assert packets == before
    memory = policies[0].memory()
    assert memory["sites"] == [[0, 2, 2]]
    assert memory["seen"] == [[1, 2], [2, 1], [2, 2], [2, 3], [3, 2]]
    assert memory["records"] == [{"id": 0, "stock": 0., "capacity": 40., "peer_count": 1,
                                   "tick": 0, "self_present": True}]
    assert json.loads(json.dumps(memory)) == memory


def test_equal_histories_are_deterministic_and_zero_cost_is_supported():
    original = world(inventory=2., movement_cost=0., sites=((2, 2, 2.), (7, 2, 30.)))
    runs = []
    for _ in range(2):
        state, policy, frames = original, ForagerPolicy(), []
        for _ in range(32):
            action = policy(observe(state, 0))
            assert action.messages == action.transfers == ()
            result = step(state, (action,))
            state = result.state
            assert result.ledger.movement_cost == 0.
            assert abs(result.ledger.residual) < 1e-12
            frames.append((action, snapshot(state), policy.memory()))
        runs.append(frames)
    assert runs[0] == runs[1]


def test_unseen_site_is_discovered_only_through_actual_sensing_coverage():
    state = world(inventory=1., sites=((2, 0, 0.), (5, 0, 30.)),
                  position=(2, 0), width=8, height=1, need=.2)
    policy = ForagerPolicy(4)
    first = policy(observe(state, 0))
    assert policy.sites == {0: (2, 0)}
    assert policy.destination_kind == "frontier"
    assert first.harvest == 0.
    discovered = False
    for _ in range(12):
        before = observe(state, 0)
        visible = {site["id"] for site in before["sites"]}
        action = policy(before)
        if 1 in policy.sites:
            assert 1 in visible or discovered
            discovered = True
        result = step(state, (action,))
        state = result.state
        assert_return_affordable(state, policy)
    assert discovered
    assert state.agents[0].consumption > 0.


@pytest.mark.parametrize("kwargs", [dict(reserve_ticks=1), dict(reserve_ticks=True), dict(reserve_ticks=2.),
    dict(stock_floor_fraction=.2), dict(stock_floor_fraction=True), dict(route_mode="hidden_law"), dict(aggressive=1)])
def test_only_declared_parameter_types_are_accepted(kwargs):
    with pytest.raises(ValueError):
        ForagerPolicy(**kwargs)
