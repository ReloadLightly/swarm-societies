"""Independent physical-contract checks; these do not qualify an incentive regime."""
from copy import deepcopy
from collections import Counter
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
import random

import pytest

from swarm_societies.commons_v3.engine import (
    Action, Config, VERSION, SNAPSHOT_VERSION, initialize, observe, observations,
    restore, snapshot, step,
)


def world(agent_rows=((0, 0, 2.),), patch_rows=((0, 0, 4.),), *, seed=17, **changes):
    """Small exact states use no weather, need, growth or costs unless requested."""
    values = dict(width=5, height=5, n_agents=len(agent_rows), n_patches=len(patch_rows),
        sensing_radius=1, need=0., initial_inventory=2., inventory_capacity=20.,
        patch_capacity=10., initial_patch_stock=4., renewal_rate=0., recovery=0.,
        weather_amplitude=0., max_harvest=10., movement_cost=0.,
        harvest_cost_per_unit=0., message_byte_cost=0.)
    values.update(changes)
    state = initialize(Config(**values), seed=seed)
    return replace(state,
        agents=tuple(replace(agent, x=x, y=y, inventory=inventory)
                     for agent, (x, y, inventory) in zip(state.agents, agent_rows)),
        patches=tuple(replace(patch, x=x, y=y, stock=stock)
                      for patch, (x, y, stock) in zip(state.patches, patch_rows)))


def idle(state):
    return tuple(Action() for _ in state.agents)


def test_default_starting_slots_spread_extra_agents_across_both_grid_axes():
    # Sixteen occupied sites plus eight east-adjacent positions. The explicit
    # site list guards against accidentally concentrating all extras in rows0/1.
    expected_sites = [(x, y) for y in (1, 4, 7, 10) for x in (1, 4, 7, 10)]
    extra_site_ids = (0, 2, 5, 7, 8, 10, 13, 15)
    expected_slots = Counter(expected_sites + [
        (expected_sites[i][0] + 1, expected_sites[i][1]) for i in extra_site_ids])
    assignments = []
    for seed in (0, 61001, 61002, 61003, 61004):
        state = initialize(Config(), seed=seed)
        assert [(p.x, p.y) for p in state.patches] == expected_sites
        actual = [(a.x, a.y) for a in state.agents]
        assert Counter(actual) == expected_slots
        assert all(expected_slots[position] == 1 for position in actual)
        assignments.append(tuple(actual))
    # Only actor identity assignment changes with the seed, not the geometry.
    assert len(set(assignments)) == len(assignments)


def assert_conserved(result):
    ledger = result.ledger
    lhs = ledger.inventory_before + ledger.stock_before + ledger.growth
    rhs = (ledger.inventory_after + ledger.stock_after + ledger.consumption +
           ledger.movement_cost + ledger.message_cost + ledger.harvest_cost + ledger.waste)
    scale = max(1., abs(lhs), abs(rhs))
    assert lhs == pytest.approx(rhs, rel=0., abs=1e-10 * scale)
    assert abs(ledger.residual) <= 1e-10 * scale
    for entry in ledger.agents:
        before = entry.inventory_before + entry.transfer_in + entry.harvested
        after = (entry.inventory_after + entry.transfer_out + entry.movement_cost +
                 entry.message_cost + entry.harvest_cost + entry.consumption + entry.waste)
        assert before == pytest.approx(after, rel=0., abs=1e-10 * max(1., before, after))
    for entry in ledger.patches:
        assert entry.stock_before - entry.harvested + entry.growth == pytest.approx(entry.stock_after)


def test_exact_harvest_consumption_and_end_of_tick_logistic_growth():
    state = world(need=1., renewal_rate=.5)
    saved = snapshot(state)
    result = step(state, (Action(harvest=3.),))
    # Start6 material units; extract3 from stock4, consume1, then grow
    # .5 * remaining1 * (1 - 1/10) = .45, giving inventory4 and stock1.45.
    assert result.state.agents[0].inventory == 4.
    assert result.state.patches[0].stock == pytest.approx(1.45)
    assert result.ledger.patches[0].stock_after_harvest == 1.
    assert result.ledger.patches[0].growth == pytest.approx(.45)
    assert result.ledger.agents[0].consumption == 1.
    assert result.ledger.agents[0].shortfall == 0.
    assert result.state.tick == state.tick + 1
    assert snapshot(state) == saved
    assert_conserved(result)


def test_no_harvest_growth_and_stock_cap_account_for_actual_material_only():
    state = world(renewal_rate=.5, recovery=.2)
    result = step(state, idle(state))
    assert result.ledger.patches[0].growth == pytest.approx(1.4)
    assert result.state.patches[0].stock == pytest.approx(5.4)
    saturated = world(patch_rows=((0, 0, 10.),), renewal_rate=.5, recovery=.2)
    capped = step(saturated, idle(saturated))
    assert capped.state.patches[0].stock == 10.
    assert capped.ledger.patches[0].growth == 0.
    assert capped.ledger.patches[0].growth_waste == pytest.approx(.2)
    assert_conserved(result)
    assert_conserved(capped)


def test_recovery_prevents_empty_stock_from_being_permanently_absorbing():
    state = world(patch_rows=((0, 0, 0.),), renewal_rate=.5, recovery=.2)
    result = step(state, idle(state))
    assert result.state.patches[0].stock == pytest.approx(.2)
    following = step(result.state, idle(result.state))
    assert following.state.patches[0].stock == pytest.approx(.498)
    assert_conserved(following)


def test_logistic_and_additive_control_have_distinct_hand_calculated_returns():
    logistic = world(renewal_rate=.5)
    additive = replace(logistic, config=replace(logistic.config, renewal_law='additive'))
    a = step(logistic, (Action(harvest=3.),))
    b = step(additive, (Action(harvest=3.),))
    assert a.state.patches[0].stock == pytest.approx(1.45)
    # The additive control returns r*K/4 regardless of the residual stock.
    assert b.state.patches[0].stock == pytest.approx(2.25)
    assert a.ledger.agents == b.ledger.agents
    assert_conserved(a)
    assert_conserved(b)


def test_zero_start_inventory_can_pay_harvest_cost_from_gross_yield():
    state = world(agent_rows=((0, 0, 0.),), need=1., harvest_cost_per_unit=.25)
    result = step(state, (Action(harvest=2.),))
    assert result.ledger.agents[0].harvested == 2.
    assert result.ledger.agents[0].harvest_cost == .5
    assert result.ledger.agents[0].consumption == 1.
    assert result.state.agents[0].inventory == .5
    assert result.state.patches[0].stock == 2.
    assert_conserved(result)


def test_horizon_metrics_accumulate_consumption_and_cost_without_double_charging_utility():
    state = world(agent_rows=((0, 0, 0.),), need=1., harvest_cost_per_unit=.25,
                  terminal_wealth_weight=.05)
    first = step(state, (Action(harvest=2.),))
    second = step(first.state, (Action(harvest=2.),))
    assert second.ledger.agents[0].harvested == 2.
    assert second.state.agents[0].harvested == 4.
    assert second.state.patches[0].cumulative_harvest == 4.
    assert second.metrics.consumption == 2.
    assert second.metrics.harvest_cost == 1.
    assert second.metrics.reserves == 1.
    assert second.metrics.stocks == 0.
    assert second.metrics.private_utility == (2.05,)
    assert_conserved(second)


def test_consumption_shortfall_and_private_reserves_are_distinct():
    state = world(agent_rows=((0, 0, .25), (1, 0, 2.)), need=1.)
    result = step(state, idle(state))
    assert [row.consumption for row in result.ledger.agents] == [.25, 1.]
    assert [row.shortfall for row in result.ledger.agents] == [.75, 0.]
    assert [agent.inventory for agent in result.state.agents] == [0., 1.]
    assert result.metrics.consumption == 1.25
    assert result.metrics.shortfall == .75
    assert_conserved(result)


def test_voluntary_reserve_preserves_material_and_records_foregone_consumption():
    state = world(agent_rows=((0, 0, .75),), need=1., terminal_wealth_weight=.05)
    result = step(state, (Action(reserve=.25),))
    assert result.ledger.agents[0].consumption == .5
    assert result.ledger.agents[0].shortfall == .5
    assert result.state.agents[0].inventory == .25
    assert result.metrics.private_utility == (.5125,)
    assert_conserved(result)


def test_local_move_cost_and_harvest_use_the_real_postmove_cell():
    state = world(agent_rows=((0, 0, 2.),), patch_rows=((1, 0, 4.),), movement_cost=.25)
    stayed = step(state, (Action(harvest=2.),))
    assert stayed.ledger.agents[0].harvested == 0.
    result = step(state, (Action(move=(1, 0), harvest=2.),))
    assert (result.state.agents[0].x, result.state.agents[0].y) == (1, 0)
    assert result.ledger.agents[0].movement_cost == .25
    assert result.ledger.agents[0].harvested == 2.
    assert result.state.agents[0].inventory == 3.75
    assert_conserved(result)


def test_unaffordable_movement_does_not_create_credit_or_teleport():
    state = world(agent_rows=((0, 0, .1),), patch_rows=((1, 0, 4.),), movement_cost=.25)
    result = step(state, (Action(move=(1, 0), harvest=2.),))
    assert (result.state.agents[0].x, result.state.agents[0].y) == (0, 0)
    assert result.ledger.agents[0].movement_cost == 0.
    assert result.ledger.agents[0].harvested == 0.
    assert result.state.agents[0].inventory == .1
    assert_conserved(result)


@pytest.mark.parametrize('move', [(2, 0), (1, 1), (-1, 0), (0, -1), (0, 2)])
def test_movement_bounds_and_single_step_contract_reject_whole_joint_action(move):
    state = world(agent_rows=((0, 0, 2.), (1, 0, 2.)))
    before = snapshot(state)
    with pytest.raises(ValueError):
        step(state, (Action(move=move), Action(harvest=2.)))
    assert snapshot(state) == before


def test_proportional_contention_allocates_initial_stock_not_future_growth():
    state = world(agent_rows=((0, 0, 0.), (0, 0, 0.)), renewal_rate=.5, recovery=.2)
    result = step(state, (Action(harvest=1.), Action(harvest=3.)))
    assert [row.harvested for row in result.ledger.agents] == [1., 3.]
    assert result.state.patches[0].stock == pytest.approx(.2)
    over = step(state, (Action(harvest=2.), Action(harvest=6.)))
    assert [row.harvested for row in over.ledger.agents] == [1., 3.]
    assert over.state.patches[0].stock == pytest.approx(.2)
    assert_conserved(over)


def test_priority_contention_has_exhaustive_allocation_and_stable_actor_identity():
    state = world(agent_rows=((0, 0, 0.), (0, 0, 0.)), contention='keyed_priority')
    result = step(state, {0: Action(harvest=3.), 1: Action(harvest=3.)})
    assert sorted(row.harvested for row in result.ledger.agents) == [1., 3.]
    reordered = step(state, {1: Action(harvest=3.), 0: Action(harvest=3.)})
    assert reordered == result
    assert_conserved(result)


def test_deliberate_overflow_harvest_is_explicit_material_waste():
    state = world(agent_rows=((0, 0, 20.),), inventory_capacity=20.)
    result = step(state, (Action(harvest=4.),))
    assert result.ledger.agents[0].harvested == 4.
    assert result.state.patches[0].stock == 0.
    assert result.state.agents[0].inventory == 20.
    assert result.ledger.waste == 4.
    assert_conserved(result)


def test_transfer_chain_cannot_respend_simultaneously_incoming_material():
    state = world(agent_rows=((0, 0, 3.), (1, 0, 0.), (2, 0, 0.)))
    result = step(state, (Action(transfers=((1, 2.),)), Action(transfers=((2, 2.),)), Action()))
    assert [agent.inventory for agent in result.state.agents] == [1., 2., 0.]
    assert [row.transfer_out for row in result.ledger.agents] == [2., 0., 0.]
    assert [row.transfer_in for row in result.ledger.agents] == [0., 2., 0.]
    assert_conserved(result)


def test_incoming_transfer_cannot_pay_for_same_tick_move_or_message():
    state = world(agent_rows=((0, 0, 3.), (1, 0, 0.)), movement_cost=1., message_byte_cost=1.)
    result = step(state, (Action(transfers=((1, 2.),)),
                          Action(move=(1, 0), messages=((0, 'a'),))))
    assert (result.state.agents[1].x, result.state.agents[1].y) == (1, 0)
    assert result.ledger.agents[1].movement_cost == result.ledger.agents[1].message_cost == 0.
    assert result.state.agents[1].inventory == 2.
    assert observe(result.state, 0)['messages'] == []
    assert_conserved(result)


def test_multiple_outgoing_transfers_share_only_own_budget_proportionally():
    state = world(agent_rows=((1, 1, 3.), (0, 1, 0.), (2, 1, 0.)))
    result = step(state, (Action(transfers=((1, 2.), (2, 4.))), Action(), Action()))
    assert [agent.inventory for agent in result.state.agents] == [0., 1., 2.]
    assert result.ledger.agents[0].transfer_out == 3.
    assert_conserved(result)


def test_reordered_joint_actions_transfers_and_messages_have_identical_result():
    state = world(agent_rows=((1, 1, 3.), (0, 1, 0.), (2, 1, 0.)), max_messages=2)
    a = Action(transfers=((1, 1.), (2, 2.)), messages=((1, 'one'), (2, 'two')))
    b = Action(transfers=((2, 2.), (1, 1.)), messages=((2, 'two'), (1, 'one')))
    assert step(state, {0: a, 1: Action(), 2: Action()}) == step(
        state, {2: Action(), 1: Action(), 0: b})


def test_transfer_reach_uses_committed_visibility_and_postmovement_distance():
    state = world(agent_rows=((1, 1, 3.), (2, 1, 0.)))
    result = step(state, (Action(transfers=((1, 2.),)), Action(move=(1, 0))))
    assert [agent.inventory for agent in result.state.agents] == [3., 0.]
    assert result.ledger.agents[0].transfer_out == 0.
    remote = world(agent_rows=((0, 0, 3.), (4, 4, 0.)))
    with pytest.raises(ValueError):
        step(remote, (Action(transfers=((1, 2.),)), Action()))


def test_utf8_message_cost_precedes_transfers_and_delivery_has_engine_provenance():
    state = world(agent_rows=((0, 0, 2.), (1, 0, 0.)), message_byte_cost=.1)
    assert observe(state, 1)['messages'] == []
    result = step(state, (Action(messages=((1, 'é!'),), transfers=((1, 2.),)), Action()))
    assert result.ledger.agents[0].message_bytes == 3
    assert result.ledger.agents[0].message_cost == pytest.approx(.3)
    assert result.ledger.agents[0].transfer_out == pytest.approx(1.7)
    assert result.state.agents[1].inventory == pytest.approx(1.7)
    assert observe(result.state, 1)['messages'] == [
        {'sender': 0, 'recipient': 1, 'sent_tick': 0, 'delivery_tick': 1, 'text': 'é!'}]
    assert observe(result.state, 0)['messages'] == []
    following = step(result.state, idle(result.state))
    assert observe(following.state, 1)['messages'] == []
    assert_conserved(result)


def test_unaffordable_and_out_of_range_messages_are_not_charged_or_delivered():
    state = world(agent_rows=((1, 1, .1), (2, 1, 0.)), message_byte_cost=.2)
    poor = step(state, (Action(messages=((1, 'a'),)), Action()))
    assert poor.ledger.agents[0].message_cost == 0.
    assert observe(poor.state, 1)['messages'] == []
    funded = replace(state, agents=(replace(state.agents[0], inventory=2.), state.agents[1]))
    apart = step(funded, (Action(messages=((1, 'a'),)), Action(move=(1, 0))))
    assert apart.ledger.agents[0].message_cost == 0.
    assert observe(apart.state, 1)['messages'] == []
    assert [row.reason for row in poor.ledger.messages] == ['insufficient_inventory']
    assert [row.reason for row in apart.ledger.messages] == ['out_of_range']


@pytest.mark.parametrize('messages', [((1, ''),), ((1, 'éé'),), ((1, '\ud800'),),
                                    ((1, 'a'), (2, 'b'))])
def test_message_payload_byte_and_count_caps_reject_before_any_transition(messages):
    state = world(agent_rows=((1, 1, 2.), (0, 1, 2.), (2, 1, 2.)),
                  max_message_bytes=3, max_messages=1)
    before = snapshot(state)
    with pytest.raises(ValueError):
        step(state, (Action(messages=messages), Action(), Action()))
    assert snapshot(state) == before


def test_joint_commit_does_not_expose_another_actors_selected_action():
    state = world(agent_rows=((1, 1, 2.), (2, 1, 2.)))
    before = observe(state, 0)
    chosen = {0: Action(harvest=1.), 1: Action(move=(1, 0))}
    step(state, chosen)
    assert observe(state, 0) == before
    assert chosen == {0: Action(harvest=1.), 1: Action(move=(1, 0))}
    with pytest.raises(FrozenInstanceError):
        state.tick = 10


def test_local_observation_ignores_remote_and_private_evaluator_state():
    state = world(agent_rows=((0, 0, 2.), (1, 0, 3.), (4, 4, 4.)),
                  patch_rows=((0, 0, 4.), (4, 4, 6.)), seed=17)
    baseline = observe(state, 0)
    altered = replace(state, seed=8091,
        config=replace(state.config, renewal_rate=.7, weather_amplitude=.3),
        agents=(state.agents[0], replace(state.agents[1], inventory=19.),
                replace(state.agents[2], inventory=17., x=4, y=3)),
        patches=(state.patches[0], replace(state.patches[1], stock=9.)))
    assert observe(altered, 0) == baseline
    assert [peer['id'] for peer in baseline['peers']] == [1]
    assert [site['id'] for site in baseline['sites']] == [0]
    assert set(baseline) == {'version', 'tick', 'self', 'sites', 'peers', 'messages'}
    assert all(set(peer) == {'id', 'x', 'y'} for peer in baseline['peers'])
    assert baseline['sites'][0]['peer_count'] == 1
    # Returned observations are detached; callers cannot mutate the world.
    baseline['self']['inventory'] = 999.
    baseline['sites'][0]['stock'] = 999.
    assert observe(state, 0)['self']['inventory'] == 2.
    assert state.patches[0].stock == 4.


def test_colocated_peer_count_includes_self_without_revealing_peer_reserves():
    state = world(agent_rows=((0, 0, 2.), (0, 0, 5.), (1, 0, 7.)))
    observation = observe(state, 0)
    assert observation['sites'][0]['peer_count'] == 2
    assert all('inventory' not in peer for peer in observation['peers'])


def test_bulk_observations_match_single_packets_and_have_independent_mutable_copies():
    state = world(agent_rows=((0, 0, 2.), (0, 0, 5.)))
    packets = observations(state)
    assert packets == tuple(observe(state, i) for i in range(2))
    packets[0]['sites'][0]['stock'] = 999.
    assert packets[1]['sites'][0]['stock'] == 4.
    assert observe(state, 0)['sites'][0]['stock'] == 4.


def test_extra_message_does_not_shift_weather_or_contention_random_events():
    state = world(agent_rows=((0, 0, 3.), (0, 0, 3.)), contention='keyed_priority',
                  patch_rows=((0, 0, 4.), (4, 4, 6.)), renewal_rate=.2, recovery=.1,
                  weather_amplitude=.2, message_byte_cost=.01)
    normal = (Action(harvest=3.), Action(harvest=3.))
    sending = (replace(normal[0], messages=((1, 'hello'),)), normal[1])
    left, right = state, state
    for tick in range(8):
        a = step(left, normal)
        b = step(right, sending if tick == 0 else normal)
        assert [p.weather for p in a.ledger.patches] == [p.weather for p in b.ledger.patches]
        assert [p.weather_event_id for p in a.ledger.patches] == [p.weather_event_id for p in b.ledger.patches]
        assert all(.8 <= p.weather <= 1.2 for p in a.ledger.patches)
        assert [p.stock for p in a.state.patches] == [p.stock for p in b.state.patches]
        assert [r.harvested for r in a.ledger.agents] == [r.harvested for r in b.ledger.agents]
        left, right = a.state, b.state


@pytest.mark.parametrize('change', [
    {'width': True}, {'height': 0}, {'n_agents': 0}, {'n_patches': 0},
    {'sensing_radius': -1}, {'need': -1.}, {'initial_inventory': float('nan')},
    {'inventory_capacity': float('inf')}, {'patch_capacity': 0.},
    {'initial_patch_stock': 11.}, {'renewal_rate': -1.}, {'recovery': -1.},
    {'weather_amplitude': float('nan')}, {'max_harvest': -1.},
    {'movement_cost': -1.}, {'harvest_cost_per_unit': float('inf')},
    {'message_byte_cost': True}, {'max_message_bytes': False}, {'max_messages': -1},
    {'renewal_law': 'unknown'}, {'contention': 'unknown'},
    {'terminal_wealth_weight': float('nan')},
])
def test_config_validation_rejects_invalid_nonfinite_and_boolean_numbers(change):
    with pytest.raises(ValueError):
        world(**change)


@pytest.mark.parametrize('action', [
    Action(move=(True, 0)), Action(move=(0.5, 0)), Action(harvest=True),
    Action(harvest=-1.), Action(harvest=11.), Action(harvest=float('nan')), Action(harvest=float('inf')),
    Action(reserve=-1.), Action(reserve=True), Action(reserve=21.), Action(reserve=float('nan')),
    Action(transfers=((1, -1.),)), Action(transfers=((1, float('nan')),)),
    Action(transfers=((1, True),)), Action(transfers=((1, 1.), (1, 2.))),
    Action(transfers=((99, 1.),)), Action(transfers=((0, 1.),)),
    Action(messages=((1, 12),)), Action(messages=((1, 'a'), (1, 'b'))),
    Action(messages=((99, 'a'),)), Action(messages=((0, 'a'),)),
])
def test_malformed_joint_action_is_atomically_rejected(action):
    state = world(agent_rows=((0, 0, 2.), (1, 0, 2.)), max_messages=2)
    before = snapshot(state)
    with pytest.raises(ValueError):
        step(state, (action, Action(harvest=2.)))
    assert snapshot(state) == before


def test_joint_action_requires_exact_actor_coverage():
    state = world(agent_rows=((0, 0, 2.), (1, 0, 2.)))
    for actions in ((Action(),), (Action(), Action(), Action()), {0: Action()},
                    {0: Action(), 2: Action()}, {False: Action(), 1: Action()}):
        with pytest.raises(ValueError):
            step(state, actions)


def test_snapshot_json_roundtrip_and_exact_continuation_with_pending_message():
    state = world(agent_rows=((0, 0, 3.), (1, 0, 3.)), renewal_rate=.2,
                  recovery=.02, weather_amplitude=.15, message_byte_cost=.01)
    state = step(state, (Action(harvest=1., messages=((1, 'remember'),)), Action())).state
    encoded = json.loads(json.dumps(snapshot(state)))
    restored = restore(encoded)
    assert restored == state
    actions = (Action(harvest=1.), Action(move=(-1, 0)))
    for _ in range(5):
        a, b = step(state, actions), step(restored, actions)
        assert a == b
        state, restored = a.state, b.state
        actions = idle(state)


def test_snapshot_digest_version_and_missing_fields_are_strict():
    state = world()
    good = snapshot(state)
    assert VERSION == good['engine_version'] == 'commons-v3-physical-v1'
    assert SNAPSHOT_VERSION == good['version'] == 'commons-v3-snapshot-v1'
    for mutation in ('digest', 'version', 'payload'):
        bad = deepcopy(good)
        if mutation == 'digest': bad['sha256'] = '0' * 64
        elif mutation == 'version': bad['version'] = 'foreign-version'
        else: bad['state'].pop(next(iter(bad['state'])))
        with pytest.raises(ValueError):
            restore(bad)
    assert restore(good) == state


@pytest.mark.parametrize('change', ['boolean_id', 'duplicate_id', 'missing_agent', 'extra_agent_field',
    'off_grid', 'negative_inventory', 'over_capacity', 'negative_stock', 'boolean_seed', 'boolean_tick'])
def test_snapshot_semantic_validation_survives_recomputed_digest(change):
    state = world(agent_rows=((0, 0, 2.), (1, 0, 2.)))
    bad = snapshot(state)
    payload = bad['state']
    if change == 'boolean_id': payload['agents'][0]['id'] = False
    if change == 'duplicate_id': payload['agents'][1]['id'] = 0
    if change == 'missing_agent': payload['agents'].pop()
    if change == 'extra_agent_field': payload['agents'][0]['privileged'] = True
    if change == 'off_grid': payload['agents'][0]['x'] = state.config.width
    if change == 'negative_inventory': payload['agents'][0]['inventory'] = -.1
    if change == 'over_capacity': payload['agents'][0]['inventory'] = 21.
    if change == 'negative_stock': payload['patches'][0]['stock'] = -.1
    if change == 'boolean_seed': payload['seed'] = True
    if change == 'boolean_tick': payload['tick'] = False
    signed = {key: bad[key] for key in ('version', 'engine_version', 'state')}
    bad['sha256'] = hashlib.sha256(json.dumps(signed, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    with pytest.raises(ValueError):
        restore(bad)


@pytest.mark.parametrize('contention', ['proportional', 'keyed_priority'])
@pytest.mark.parametrize('seed', [0, 42, 1907])
def test_random_local_trajectories_conserve_material_and_remain_nonnegative(contention, seed):
    rng = random.Random(8017)
    state = initialize(Config(width=5, height=5, n_agents=8, n_patches=8,
        initial_inventory=2., inventory_capacity=12., patch_capacity=20.,
        initial_patch_stock=12., renewal_rate=.3, recovery=.02,
        weather_amplitude=.15, max_messages=1, contention=contention), seed=seed)
    for _ in range(80):
        actions = []
        for actor in state.agents:
            legal = [(0, 0)] + [(dx, dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= actor.x + dx < state.config.width and 0 <= actor.y + dy < state.config.height]
            peers = observe(state, actor.id)['peers']
            recipient = rng.choice(peers)['id'] if peers else None
            transfers = ((recipient, rng.random()),) if recipient is not None and rng.random() < .25 else ()
            messages = ((recipient, 'ping'),) if recipient is not None and rng.random() < .25 else ()
            actions.append(Action(move=rng.choice(legal), harvest=rng.random()*state.config.max_harvest,
                                  transfers=transfers, messages=messages))
        result = step(state, actions)
        assert_conserved(result)
        assert all(math.isfinite(a.inventory) and 0. <= a.inventory <= state.config.inventory_capacity
                   for a in result.state.agents)
        assert all(math.isfinite(p.stock) and 0. <= p.stock <= state.config.patch_capacity
                   for p in result.state.patches)
        state = result.state
