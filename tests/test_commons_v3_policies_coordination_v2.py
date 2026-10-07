"""Synthetic local counterfactuals; these fixtures do not measure welfare."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy
from swarm_societies.commons_v3.policies_coordination_v2 import (
    COORDINATION_VERSION, REPORT_PREFIX, CoordinationPolicy,
)


def world(*, tick=1, stock=22., inventory=3., radius=1, byte_cost=.001):
    cfg = engine.Config(width=7, height=3, n_agents=3, n_patches=3,
        sensing_radius=radius, need=1.2, initial_inventory=inventory,
        renewal_rate=0., recovery=0., weather_amplitude=0., message_byte_cost=byte_cost)
    return engine.WorldState(cfg, 42, tick,
        (engine.AgentState(0, 3, 1, inventory), engine.AgentState(1, 3, 1, inventory),
         engine.AgentState(2, 6, 2, inventory)),
        (engine.PatchState(0, 2, 1, stock), engine.PatchState(1, 4, 1, stock),
         engine.PatchState(2, 6, 1, 40.)))


def message(packet, *, report=None, intention=None, sender=1):
    tick = packet["tick"]
    return {"sender": sender, "recipient": packet["self"]["id"],
            "sent_tick": tick - 1, "delivery_tick": tick,
            "text": REPORT_PREFIX + json.dumps([2, report, intention], separators=(",", ":"))}


@pytest.mark.parametrize("reserve,route", [(2, "net_yield"), (4, "nearest")])
@pytest.mark.parametrize("aggressive", [False, True])
def test_disabled_coordination_exactly_matches_frozen_navigation(reserve, route, aggressive):
    state = engine.initialize(engine.Config(n_agents=3, n_patches=3, need=1.2), seed=42)
    policies = [CoordinationPolicy(reserve, .5, route, aggressive, share=False) for _ in state.agents]
    controls = [ForagerPolicy(reserve, .5, route, aggressive) for _ in state.agents]
    for _ in range(24):
        packets = engine.observations(state)
        actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        assert actions == tuple(control(packet) for control, packet in zip(controls, packets))
        assert [p.forager.memory() for p in policies] == [p.memory() for p in controls]
        state = engine.step(state, actions).state
        for i, policy in enumerate(policies):
            policy.validate_context(state, i)


def test_no_information_or_intentions_preserves_navigation_route():
    packet = engine.observe(world(), 0)
    policy = CoordinationPolicy()
    control = ForagerPolicy(4, .5, "nearest")
    assert policy(packet) == control(packet)
    assert policy.forager.memory() == control.memory()
    assert not policy.diagnostics["route_changed"]


def test_intention_alone_changes_congested_route_with_positive_local_surplus():
    packet = engine.observe(world(), 0)
    baseline = CoordinationPolicy()
    original = baseline(packet)
    goal = baseline.forager.destination
    site = next(i for i, point in baseline.forager.sites.items() if point == goal)
    treated_packet = deepcopy(packet)
    treated_packet["messages"] = [message(packet, intention=[site, *goal])]
    treated = CoordinationPolicy()
    action = treated(treated_packet)
    assert original.move == (1, 0) and action.move == (-1, 0)
    assert treated.diagnostics["route_changed"]
    assert treated.diagnostics["estimated_surplus"] > .05 * packet["self"]["need"]
    assert treated.forager.records == baseline.forager.records
    assert all(record["peer_count"] == 0 for record in treated.forager.records.values())
    assert CoordinationPolicy.restore(treated.memory()).memory() == treated.memory()


def test_new_dated_report_redirects_a_route_without_fake_current_sensing():
    packet = engine.observe(world(stock=20.5), 0)
    baseline = CoordinationPolicy()
    original = baseline(packet)
    treated_packet = deepcopy(packet)
    treated_packet["messages"] = [message(packet, report=[0, 2, 0, 1, 40., 40., 0])]
    treated = CoordinationPolicy()
    action = treated(treated_packet)
    assert original.move == (1, 0) and action.move == (-1, 0)
    assert treated.forager.destination == (0, 1)
    assert treated.forager.records[2]["tick"] == 0
    assert treated.forager.records[2]["self_present"] is False
    assert treated.sources[2] == (1, 0)
    assert treated.diagnostics["accepted_reports"] == 1
    assert treated_packet["sites"] == packet["sites"]


def test_intentions_already_at_site_do_not_double_count_visible_agents():
    state = world()
    state = replace(state, agents=(state.agents[0], replace(state.agents[1], x=4), state.agents[2]))
    packet = engine.observe(state, 0)
    treated_packet = deepcopy(packet)
    treated_packet["messages"] = [message(packet, intention=[1, 4, 1])]
    original, treated = CoordinationPolicy(), CoordinationPolicy()
    assert original(packet) == treated(treated_packet)
    assert not treated.diagnostics["route_changed"]


def test_sufficient_current_opportunity_does_not_trigger_departure():
    state = world()
    state = replace(state, agents=(replace(state.agents[0], x=2), state.agents[1], state.agents[2]),
        patches=(replace(state.patches[0], stock=40.), *state.patches[1:]))
    packet = engine.observe(state, 0)
    packet["messages"] = [message(packet, report=[0, 2, 6, 1, 40., 40., 0])]
    policy = CoordinationPolicy()
    assert policy(packet).move == (0, 0)
    assert not policy.diagnostics["route_changed"]


def test_paid_route_intention_without_stock_novelty_has_real_delayed_accounting():
    state = world(tick=0)
    packet = engine.observe(state, 0)
    policy = CoordinationPolicy()
    action = policy(packet)
    assert len(action.messages) == 1
    recipient, text = action.messages[0]
    payload = json.loads(text[len(REPORT_PREFIX):])
    assert recipient == 1 and payload[1] is None and payload[2] is not None
    result = engine.step(state, (action, engine.Action(), engine.Action()))
    no_message = engine.step(state, (replace(action, messages=()), engine.Action(), engine.Action()))
    expected = len(text.encode("utf-8")) * state.config.message_byte_cost
    assert result.ledger.messages[0].delivered
    assert result.ledger.message_cost == expected
    assert result.state.agents[0].inventory == pytest.approx(no_message.state.agents[0].inventory - expected)
    assert abs(result.ledger.residual) < 1e-12
    assert not packet["messages"]
    assert engine.observe(result.state, recipient)["messages"][0]["text"] == text
    policy.validate_context(result.state, 0)


def test_recipient_departure_can_fail_delivery_without_an_imaginary_fee():
    state = world(tick=0)
    policy = CoordinationPolicy()
    action = policy(engine.observe(state, 0))
    # Sender heads east. The recipient moves west, out of post-move reach.
    assert action.move == (1, 0)
    result = engine.step(state, (action, engine.Action(move=(-1, 0)), engine.Action()))
    assert not result.ledger.messages[0].delivered
    assert result.ledger.messages[0].reason == "out_of_range"
    assert result.ledger.message_cost == 0.
    assert not result.state.messages
    assert result.ledger.agents[0].waste == 0.
    assert abs(result.ledger.residual) < 1e-12


def test_paid_delayed_intention_changes_receiver_route_and_realized_physical_outcomes():
    cfg = engine.Config(width=7, height=3, n_agents=3, n_patches=2,
        sensing_radius=2, need=1.2, initial_inventory=3., renewal_rate=0.,
        recovery=0., weather_amplitude=0.)
    initial = engine.WorldState(cfg, 42, 0,
        tuple(engine.AgentState(i, 3, 1, 3.) for i in range(3)),
        (engine.PatchState(0, 1, 1, 22.), engine.PatchState(1, 5, 1, 22.)))
    sender = CoordinationPolicy()
    outgoing = sender(engine.observe(initial, 0))
    sent = engine.step(initial, (outgoing, engine.Action(), engine.Action()))
    assert sent.ledger.messages[0].delivered
    assert sent.ledger.message_cost == len(outgoing.messages[0][1].encode()) * cfg.message_byte_cost
    assert (sent.state.agents[0].x, sent.state.agents[0].y) == (2, 1)
    # The sender has not reached its declared x=1 destination. Both branches
    # retain its real payment; only delivered information is removed here.
    untreated_state = replace(sent.state, messages=())
    treated_state = sent.state
    original, informed = CoordinationPolicy(), CoordinationPolicy()
    original_action = original(engine.observe(untreated_state, 1))
    informed_action = informed(engine.observe(treated_state, 1))
    assert original_action.move == (-1, 0)
    assert informed_action.move == (1, 0)
    # A scripted sender completes the previously announced trip and extracts
    # two units. This finite fixture is not an inferred benefit in a bank.
    complete_arrival = engine.Action(move=(-1, 0), harvest=2.)
    untreated = engine.step(untreated_state, (complete_arrival, original_action, engine.Action()))
    treated = engine.step(treated_state, (complete_arrival, informed_action, engine.Action()))
    original_action = original(engine.observe(untreated.state, 1))
    informed_action = informed(engine.observe(treated.state, 1))
    untreated = engine.step(untreated.state, (engine.Action(), original_action, engine.Action()))
    treated = engine.step(treated.state, (engine.Action(), informed_action, engine.Action()))
    assert treated.ledger.agents[1].harvested == 2.
    assert untreated.ledger.agents[1].harvested == 0.
    assert treated.ledger.agents[1].consumption == 1.2
    assert untreated.ledger.agents[1].consumption < 1.2
    for result in (sent, untreated, treated):
        assert abs(result.ledger.residual) < 1e-12
        assert result.ledger.movement_cost > 0.


def test_fresh_remembered_site_can_be_sent_after_leaving_sensing_range():
    state = world(tick=0, inventory=8.)
    state = replace(state, agents=(replace(state.agents[0], x=6), replace(state.agents[1], y=2), state.agents[2]))
    policy = CoordinationPolicy(report_period=1)
    for step in range(3):
        policy(engine.observe(state, 0))
        peer = engine.Action(move=(0, -1)) if step == 2 else engine.Action()
        state = engine.step(state, (engine.Action(move=(-1, 0)), peer, engine.Action())).state
    packet = engine.observe(state, 0)
    assert {site["id"] for site in packet["sites"]} == {0, 1}
    assert all(abs(site["x"] - 3) + abs(site["y"] - 1) <= 1 for site in packet["sites"])
    action = policy(packet)
    assert action.messages
    payload = json.loads(action.messages[0][1][len(REPORT_PREFIX):])
    assert payload[1][1] == 2 and payload[1][0] == 1
    assert payload[1][0] < packet["tick"]
    assert policy.direct[2]["tick"] == 1


def test_received_assertion_is_not_rebroadcast_as_a_direct_report():
    packet = engine.observe(world(tick=4), 0)
    packet["messages"] = [message(packet, report=[3, 2, 0, 1, 40., 40., 0])]
    policy = CoordinationPolicy()
    action = policy(packet)
    assert 2 in policy.sources and 2 not in policy.direct
    if action.messages:
        payload = json.loads(action.messages[0][1][len(REPORT_PREFIX):])
        assert payload[1] is None or payload[1][1] != 2


@pytest.mark.parametrize("change", [
    lambda m: m.update(sender=0),
    lambda m: m.update(recipient=2),
    lambda m: m.update(recipient=False),
    lambda m: m.update(sent_tick=1),
    lambda m: m.update(sent_tick=False),
    lambda m: m.update(delivery_tick=0),
    lambda m: m.update(delivery_tick=True),
    lambda m: m.update(text=REPORT_PREFIX + "not json"),
    lambda m: m.update(text=REPORT_PREFIX + '[2,[0,2,6,1,NaN,40,0],null]'),
    lambda m: m.update(text=REPORT_PREFIX + '[2,[0,2,99,1,40,40,0],null]'),
    lambda m: m.update(text=REPORT_PREFIX + '[2,[1,2,6,1,40,40,0],null]'),
    lambda m: m.update(text=REPORT_PREFIX + '[2,[0,2,6,1,41,40,0],null]'),
    lambda m: m.update(text=REPORT_PREFIX + '[2,[0,2,6,1,40,40,true],null]'),
    lambda m: m.update(text=REPORT_PREFIX + '[2,[0,0,6,1,40,40,0],[0,2,1]]'),
])
def test_malformed_reports_are_ignored_without_changing_decisions(change):
    packet = engine.observe(world(), 0)
    damaged = message(packet, report=[0, 2, 6, 1, 40., 40., 0])
    change(damaged)
    noisy = deepcopy(packet)
    noisy["messages"] = [damaged]
    original, treated = CoordinationPolicy(), CoordinationPolicy()
    assert treated(noisy) == original(packet)
    assert treated.memory() == original.memory()


def test_stale_stock_report_is_rejected_and_arrival_intentions_expire():
    packet = engine.observe(world(tick=10), 0)
    packet["messages"] = [message(packet, report=[1, 2, 6, 1, 40., 40., 0])]
    policy = CoordinationPolicy(report_ttl=8)
    policy(packet)
    assert 2 not in policy.forager.records
    packet = engine.observe(world(), 0)
    packet["messages"] = [message(packet, intention=[1, 4, 1])]
    policy = CoordinationPolicy(intention_ttl=1)
    policy(packet)
    assert policy.intentions
    next_packet = engine.observe(world(tick=2), 0)
    policy(next_packet)
    assert not policy.intentions


def test_excessively_nested_message_is_ignored_within_larger_engine_byte_limit():
    state = world()
    state = replace(state, config=replace(state.config, max_message_bytes=4096))
    packet = engine.observe(state, 0)
    damaged = message(packet, intention=[1, 4, 1])
    damaged["text"] = REPORT_PREFIX + "[" * 1200 + "0" + "]" * 1200
    noisy = deepcopy(packet)
    noisy["messages"] = [damaged]
    original, treated = CoordinationPolicy(), CoordinationPolicy()
    assert original(packet) == treated(noisy)
    assert original.memory() == treated.memory()


def test_current_direct_sensing_overrides_conflicting_report():
    packet = engine.observe(world(), 0)
    packet["messages"] = [message(packet, report=[0, 1, 4, 1, 40., 40., 0])]
    policy = CoordinationPolicy()
    policy(packet)
    assert policy.forager.records[1]["stock"] == 22.
    assert policy.forager.records[1]["tick"] == 1
    assert 1 not in policy.sources
    CoordinationPolicy.restore(policy.memory())


def test_well_formed_false_identity_and_crowd_remain_bounded_unverified_beliefs():
    state = world()
    false = message(engine.observe(state, 0), report=[0, 999, 0, 1, 40., 40., 4096],
                    intention=[999, 0, 1])
    # The engine authenticates sender/recipient and pays delivery; it does
    # not interpret or authenticate the payload's claimed site and crowd.
    state = replace(state, messages=(engine.Message(**false),))
    policy = CoordinationPolicy()
    action = policy(engine.observe(state, 0))
    assert policy.forager.records[999]["peer_count"] == 4096
    restored = CoordinationPolicy.restore(json.loads(json.dumps(policy.memory())))
    result = engine.step(state, (action, engine.Action(), engine.Action()))
    restored.validate_context(result.state, 0)
    assert restored.memory() == policy.memory()
    assert restored(engine.observe(result.state, 0)) == policy(engine.observe(result.state, 0))


@pytest.mark.parametrize("inventory,byte_cost", [(1.2, .001), (3., 1.)])
def test_message_cost_gate_preserves_consumption_and_route_fuel(inventory, byte_cost):
    state = world(tick=0, inventory=inventory, byte_cost=byte_cost)
    action = CoordinationPolicy()(engine.observe(state, 0))
    assert not action.messages


def test_unaffordable_reported_destination_does_not_create_an_unsafe_route():
    state = world(inventory=.03, stock=20.)
    packet = engine.observe(state, 0)
    packet["messages"] = [message(packet, report=[0, 2, 0, 1, 40., 40., 0])]
    policy = CoordinationPolicy()
    action = policy(packet)
    assert policy.forager.destination != (0, 1)
    assert not policy.diagnostics["route_changed"]
    if action.move != (0, 0):
        destination = packet["self"]["x"] + action.move[0], packet["self"]["y"] + action.move[1]
        assert destination in policy.forager.sites.values()


def test_asserted_adjacent_site_is_not_a_proven_return_anchor():
    state = world(inventory=.03, stock=20.)
    packet = engine.observe(state, 0)
    packet["messages"] = [message(packet, report=[0, 999, 3, 0, 40., 40., 0])]
    policy = CoordinationPolicy()
    action = policy(packet)
    me = packet["self"]
    assert policy.forager._home_distance((3, 0)) == 2
    assert not policy.forager._feasible_goal(me, (3, 1), (3, 0))
    assert not policy.forager._safe_step(me, (3, 0))
    assert action.move != (0, -1)
    restored = CoordinationPolicy.restore(policy.memory())
    assert not restored.forager._safe_step(me, (3, 0))
    assert restored.forager.memory() == policy.forager.memory()


def test_hidden_remote_stock_other_inventory_and_feedback_do_not_change_action():
    original = world(tick=0)
    hidden = replace(original, agents=(*original.agents[:2], replace(original.agents[2], inventory=70.)),
                     patches=(*original.patches[:2], replace(original.patches[2], stock=1.)))
    left, right = engine.observe(original, 0), engine.observe(hidden, 0)
    assert left == right
    right["private_feedback"] = {"arbitrary": "unused by coordination"}
    a, b = CoordinationPolicy(), CoordinationPolicy()
    saved = deepcopy(left)
    assert a(left) == b(right)
    assert a.memory() == b.memory()
    assert left == saved


def test_json_checkpoint_restores_policy_memory_and_future_physical_actions():
    state = world(tick=0)
    policies = [CoordinationPolicy(report_period=1) for _ in state.agents]
    for _ in range(6):
        actions = tuple(p(o) for p, o in zip(policies, engine.observations(state)))
        state = engine.step(state, actions).state
    restored = [CoordinationPolicy.restore(json.loads(json.dumps(p.memory()))) for p in policies]
    for _ in range(12):
        packets = engine.observations(state)
        actions = tuple(p(o) for p, o in zip(policies, packets))
        assert actions == tuple(p(o) for p, o in zip(restored, packets))
        assert [p.memory() for p in policies] == [p.memory() for p in restored]
        state = engine.step(state, actions).state
        for i, policy in enumerate(restored):
            policy.validate_context(state, i)


@pytest.mark.parametrize("change", [
    lambda m: m.update(version="arbitrary code"),
    lambda m: m.update(extra="unknown"),
    lambda m: m.update(share=1),
    lambda m: m.update(last_tick=True),
    lambda m: m.update(owner=None),
    lambda m: m.update(report_ttl=0),
    lambda m: m.update(minimum_route_surplus=float("nan")),
    lambda m: m["direct"][0].update(tick=999),
    lambda m: m["direct"][0].update(stock=-1),
    lambda m: m["direct"].reverse(),
    lambda m: m["forager"]["records"][0].update(stock=1.),
    lambda m: m["sources"].append([0, 1, 0]),
    lambda m: m["intentions"].append([1, 1, 4, 1, 1]),
    lambda m: m["sent"].append([1, -1, -1, -1, 1]),
])
def test_malformed_or_inconsistent_memories_are_rejected(change):
    policy = CoordinationPolicy()
    policy(engine.observe(world(), 0))
    memory = policy.memory()
    change(memory)
    with pytest.raises(ValueError):
        CoordinationPolicy.restore(memory)


def test_context_rejects_wrong_owner_clock_and_grid_but_allows_fresh_start():
    state = world(tick=10)
    fresh = CoordinationPolicy()
    fresh.validate_context(state, 0)
    fresh(engine.observe(state, 0))
    next_state = replace(state, tick=11)
    fresh.validate_context(next_state, 0)
    with pytest.raises(ValueError):
        fresh.validate_context(next_state, 1)
    with pytest.raises(ValueError):
        fresh.validate_context(state, 0)
    with pytest.raises(ValueError):
        fresh(engine.observe(state, 0))
    with pytest.raises(ValueError):
        fresh.validate_context(replace(next_state, config=replace(state.config, width=4)), 0)
    assert fresh.memory()["version"] == COORDINATION_VERSION


def test_mutating_exported_memory_does_not_change_live_state():
    policy = CoordinationPolicy()
    policy(engine.observe(world(), 0))
    before = policy.memory()
    exported = policy.memory()
    exported["direct"][0]["stock"] = -1
    exported["forager"]["records"][0]["stock"] = -1
    assert policy.memory() == before
