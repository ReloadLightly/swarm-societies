"""Declared controls preserve navigation, actual costs, and legal information."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine, politics_v1 as politics
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy
from swarm_societies.commons_v3.policies_institutions_development_v1 import (
    ARMS, DevelopmentPolicy,
)


def fixture(*, inventory=10., treasury=None, quota=2., stock=40., remote_leader=False):
    cfg = engine.Config(width=4, height=1, n_agents=3, n_patches=1,
        need=1.2, initial_inventory=inventory, initial_patch_stock=stock,
        weather_amplitude=0., renewal_rate=0., recovery=0.)
    world = engine.WorldState(cfg, 476, 0,
        tuple(engine.AgentState(i, 3 if remote_leader and i == 0 else 1, 0, inventory)
              for i in range(3)), (engine.PatchState(0, 1, 0, stock),))
    institutions = () if treasury is None else (
        politics.Institution(0, 0, politics.Charter(quota=quota), (0, 1, 2),
            tuple(politics.Bond(i, 1.) for i in range(3)), treasury),)
    return politics.State(world, politics.PoliticalConfig(), institutions,
                          next_id=0 if treasury is None else 1)


@pytest.mark.parametrize("reserve,route", [(2, "net_yield"), (4, "nearest")])
@pytest.mark.parametrize("behavior", ["responsive", "stubborn"])
def test_frozen_arm_exactly_preserves_both_navigation_backgrounds(reserve, route, behavior):
    state = politics.initialize(engine.Config(n_agents=3, need=1.2), seed=4730)
    policies = [DevelopmentPolicy("frozen", behavior=behavior, reserve_ticks=reserve,
                                 route_mode=route) for _ in state.world.agents]
    controls = [ForagerPolicy(reserve, .5, route, aggressive=behavior == "stubborn")
                for _ in state.world.agents]
    for _ in range(24):
        packets = politics.observations(state)
        decisions = [policy(packet) for policy, packet in zip(policies, packets)]
        actions = tuple(control(packet) for control, packet in zip(controls, packets))
        assert tuple(row[0] for row in decisions) == actions
        assert all(row[1] == politics.Intent() for row in decisions)
        assert [p.coordinator.forager.memory() for p in policies] == [p.memory() for p in controls]
        state = politics.step(state, actions).state


def test_stubborn_role_has_identical_physical_response_across_all_arms():
    state = fixture(treasury=1.)
    packet = politics.observe(state, 1)
    policies = [DevelopmentPolicy(arm, behavior="stubborn") for arm in ARMS]
    decisions = [policy(packet) for policy in policies]
    assert all(decision == decisions[0] for decision in decisions)
    assert decisions[0][1] == politics.Intent()
    assert all(not p.coordinator.share and p.coordinator.forager.aggressive for p in policies)


def test_nonstubborn_navigation_remains_restrained_in_every_arm():
    for arm in ARMS:
        policy = DevelopmentPolicy(arm)
        assert not policy.coordinator.forager.aggressive
        assert policy.coordinator.share == (arm != "frozen")


def test_common_cache_rule_preserves_need_reserve_and_uses_same_private_capacity():
    state = fixture(treasury=1.)
    packet = politics.observe(state, 2)
    decisions = [DevelopmentPolicy(arm)(packet) for arm in ARMS[1:]]
    assert all(intent.kind == "cache" for _, intent in decisions)
    assert all(intent.amount == pytest.approx(2.4) for _, intent in decisions)
    for action, intent in decisions:
        assert packet["self"]["inventory"] - intent.amount >= 6 * packet["self"]["need"] + action.reserve
    result = politics.step(state, (engine.Action(), engine.Action(), decisions[0][0]),
        (politics.Intent(), politics.Intent(), decisions[0][1]))
    assert result.state.caches == (politics.Cache(2, 0, 2.4),)
    assert abs(result.ledger.residual) < 1e-12


def test_cache_retrieval_does_not_fund_current_consumption():
    state = fixture(inventory=.5, stock=0.)
    # The one-cell grid removes any useful move from the synthetic fixture.
    state = replace(state, world=replace(state.world,
        config=replace(state.world.config, width=1),
        agents=tuple(replace(a, x=0) for a in state.world.agents),
        patches=(replace(state.world.patches[0], x=0),)),
        caches=(politics.Cache(1, 0, 2.4),))
    action, intent = DevelopmentPolicy("decentralized")(politics.observe(state, 1))
    assert action.move == (0, 0) and intent.kind == "retrieve"
    actions = (engine.Action(), action, engine.Action())
    untreated = politics.step(state, actions)
    retrieved = politics.step(state, actions, (politics.Intent(), intent, politics.Intent()))
    assert retrieved.physical.ledger.agents[1].consumption == untreated.physical.ledger.agents[1].consumption
    assert retrieved.state.world.agents[1].inventory > untreated.state.world.agents[1].inventory


@pytest.mark.parametrize("arm", ["charter_unmonitored", "charter_enforced"])
def test_declared_local_rules_can_found_without_scripted_future_actions(arm):
    state = fixture()
    policies = [DevelopmentPolicy(arm) for _ in state.world.agents]
    decisions = [p(o) for p, o in zip(policies, politics.observations(state))]
    assert decisions[0][1].kind == "propose"
    state = politics.step(state, tuple(d[0] for d in decisions), tuple(d[1] for d in decisions)).state
    decisions = [p(o) for p, o in zip(policies, politics.observations(state))]
    assert [d[1].kind for d in decisions] == ["endorse"] * 3
    state = politics.step(state, tuple(d[0] for d in decisions), tuple(d[1] for d in decisions)).state
    assert state.institutions[0].members == (0, 1, 2)
    assert state.institutions[0].charter == politics.Charter()


def test_unmonitored_charter_withholds_dues_and_purchases_no_operations():
    state = fixture(inventory=3., treasury=0.)
    packet = politics.observe(state, 1)
    assert DevelopmentPolicy("charter_unmonitored")(packet)[1].kind == "none"
    assert DevelopmentPolicy("charter_enforced")(packet)[1].kind == "pay"
    funded = fixture(inventory=3., treasury=1.)
    packet = politics.observe(funded, 0)
    assert DevelopmentPolicy("charter_unmonitored")(packet)[1].kind == "none"
    action, intent = DevelopmentPolicy("charter_enforced")(packet)
    assert intent == politics.Intent("monitor", 0, funding="treasury")
    result = politics.step(funded, (action, engine.Action(), engine.Action()),
        (intent, politics.Intent(), politics.Intent()))
    assert result.state.political_cost == funded.config.monitoring_cost


def test_current_local_selector_does_not_wait_for_remote_lowest_member():
    state = fixture(inventory=3., treasury=1., remote_leader=True)
    assert DevelopmentPolicy("charter_enforced")(politics.observe(state, 1))[1] == (
        politics.Intent("monitor", 0, funding="treasury"))
    assert DevelopmentPolicy("charter_enforced")(politics.observe(state, 2))[1].kind == "none"


def test_response_requires_other_designated_local_monitor_and_actual_funding():
    # quota=3.9 is only a response-rule fixture, not a development charter.
    state = fixture(inventory=1., treasury=1., quota=3.9, remote_leader=True)
    packet = politics.observe(state, 2)
    assert DevelopmentPolicy("charter_enforced")(packet)[0].harvest == 3.9
    assert DevelopmentPolicy("charter_unmonitored")(packet)[0].harvest == 4.
    assert DevelopmentPolicy("charter_enforced")(politics.observe(state, 1))[0].harvest == 4.
    unfunded = replace(state, institutions=(replace(state.institutions[0], treasury=0.),))
    assert DevelopmentPolicy("charter_enforced")(politics.observe(unfunded, 2))[0].harvest == 4.
    alone = replace(state, world=replace(state.world,
        agents=(state.world.agents[0], replace(state.world.agents[1], x=3), state.world.agents[2])))
    assert DevelopmentPolicy("charter_enforced")(politics.observe(alone, 2))[0].harvest == 4.


def test_enforced_rule_settles_paid_receipt_and_unmonitored_rule_does_not():
    state = fixture(inventory=3., treasury=1.)
    monitored = politics.step(state, (engine.Action(), engine.Action(harvest=4.), engine.Action()),
        (politics.Intent("monitor", 0, funding="treasury"), politics.Intent(), politics.Intent())).state
    packet = politics.observe(monitored, 0)
    before = deepcopy(packet)
    action, intent = DevelopmentPolicy("charter_enforced")(packet)
    assert packet == before and intent.kind == "sanction"
    assert DevelopmentPolicy("charter_unmonitored")(packet)[1].kind not in ("monitor", "sanction", "pay")
    result = politics.step(monitored, (action, engine.Action(), engine.Action()),
        (intent, politics.Intent(), politics.Intent()))
    assert result.state.forfeited == .5
    assert result.state.political_cost == pytest.approx(.07)


@pytest.mark.parametrize("arm", ARMS[1:])
def test_all_nonfrozen_arms_collect_mature_local_claim(arm):
    state = fixture(inventory=3., treasury=0.)
    institution = replace(state.institutions[0], members=(), active=False,
        bonds=tuple(politics.Bond(i, 1., 2) for i in range(3)))
    state = replace(state, world=replace(state.world, tick=2), institutions=(institution,))
    action, intent = DevelopmentPolicy(arm)(politics.observe(state, 1))
    assert action.move == (0, 0) and intent == politics.Intent("withdraw", 0, amount=1.)


def test_json_memory_continuation_regenerates_all_decisions():
    state = fixture()
    policies = [DevelopmentPolicy("charter_enforced") for _ in state.world.agents]
    for _ in range(5):
        decisions = [p(o) for p, o in zip(policies, politics.observations(state))]
        state = politics.step(state, tuple(d[0] for d in decisions), tuple(d[1] for d in decisions)).state
    restored = [DevelopmentPolicy.restore(json.loads(json.dumps(p.memory()))) for p in policies]
    for _ in range(12):
        packets = politics.observations(state)
        decisions = [p(o) for p, o in zip(policies, packets)]
        assert decisions == [p(o) for p, o in zip(restored, packets)]
        assert [p.memory() for p in policies] == [p.memory() for p in restored]
        state = politics.step(state, tuple(d[0] for d in decisions), tuple(d[1] for d in decisions)).state


@pytest.mark.parametrize("change", [
    lambda m: m.update(version="not-an-audited-policy"),
    lambda m: m["coordinator"].update(share=False),
    lambda m: m["coordinator"]["forager"].update(aggressive=True),
    lambda m: m["decisions"].update(none=True),
    lambda m: m.update(cache_need_ticks=float("nan")),
    lambda m: m.update(cache_deposit_above_need_ticks=1.),
    lambda m: m.update(source="arbitrary_import.py"),
])
def test_restoration_rejects_changed_affordances_and_invalid_memories(change):
    memory = DevelopmentPolicy().memory()
    change(memory)
    with pytest.raises(ValueError):
        DevelopmentPolicy.restore(memory)


def test_hidden_remote_changes_cannot_change_decisions_or_memories():
    state = fixture(inventory=3., treasury=1., remote_leader=True)
    changed = replace(state, world=replace(state.world,
        agents=(replace(state.world.agents[0], inventory=79.), *state.world.agents[1:])))
    left, right = politics.observe(state, 1), politics.observe(changed, 1)
    assert left == right
    a, b = DevelopmentPolicy("charter_enforced"), DevelopmentPolicy("charter_enforced")
    assert a(left) == b(right)
    assert a.memory() == b.memory()
