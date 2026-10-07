"""Entry, refusal, responsive exit and custody timing from legal private input."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine, politics_v1 as politics
from swarm_societies.commons_v3.policies_coordination_v2 import CoordinationPolicy
from swarm_societies.commons_v3.policies_membership_v2 import MembershipPolicy
from swarm_societies.commons_v3.political_episode_v1 import ScriptedPolicy
from swarm_societies.commons_v3.political_episode_v2 import Episode, restore_checkpoint


def local_world(*, stock=80., inventory=12., members=(), quota=2., remote=False):
    cfg = engine.Config(width=5 if remote else 1, height=1, n_agents=3, n_patches=1,
                        need=1.2, initial_inventory=inventory, initial_patch_stock=stock, patch_capacity=80.,
                        weather_amplitude=0., renewal_rate=0., recovery=0.)
    world = engine.WorldState(cfg, 42, 0,
        tuple(engine.AgentState(i, 4 if remote and i == 2 else 0, 0, inventory) for i in range(3)),
        (engine.PatchState(0, 0, 0, stock),))
    institutions = () if not members else (politics.Institution(0, 0, politics.Charter(quota=quota), members,
        tuple(politics.Bond(i, 1.) for i in members)),)
    return politics.State(world, politics.PoliticalConfig(), institutions,
                          next_id=1 if members else 0)


def member_policy(**kwargs):
    return MembershipPolicy(coordinator=CoordinationPolicy(share=False), **kwargs)


def inert():
    return ScriptedPolicy({tick: (engine.Action(), politics.Intent()) for tick in range(64)})


def test_favorable_entry_preserves_liquidity_and_locks_real_bond_before_consumption():
    state = local_world(members=(0, 1))
    episode = Episode(state, [inert(), inert(), member_policy()])
    result = episode.advance()
    assert episode.last_intents[2] == politics.Intent("join", 0)
    assert episode.last_actions[2].move == (0, 0)
    assert episode.policies[2].diagnostics["member_rate"] == state.world.config.need
    assert episode.policies[2].diagnostics["outside_rate"] == state.world.config.need
    assert episode.state.institutions[0].members == (0, 1, 2)
    assert result.physical.ledger.agents[2].inventory_before == 11.
    assert episode.state.world.agents[2].inventory == pytest.approx(9.8)
    assert result.ledger.political_cost == 0., "bond locking is not a material fee"
    assert abs(result.ledger.residual) < 1e-12


@pytest.mark.parametrize("inventory,quota", [(2., 2.), (12., .5)])
def test_local_offer_is_refused_when_liquidity_or_service_is_inadequate(inventory, quota):
    state = local_world(inventory=inventory)
    state = replace(state, proposals=(politics.Proposal(0, "found", 0, 0,
        charter=politics.Charter(quota=quota), created_tick=0, expires_tick=8),), next_id=1)
    policy = member_policy()
    action, intent = policy(politics.observe(state, 1))
    assert intent == politics.Intent("refuse", 0)
    assert policy.diagnostics["reason"] == "outside_or_liquidity_preferred"
    assert policy.diagnostics["planned_private_debit"] == 0.
    assert not action.messages


def test_good_equivalent_opportunities_allow_local_formation_without_schedule():
    episode = Episode(local_world(), [member_policy() for _ in range(3)])
    episode.advance()
    assert [i.kind for i in episode.last_intents] == ["propose", "none", "none"]
    episode.advance()
    assert [i.kind for i in episode.last_intents] == ["endorse"] * 3
    assert episode.state.institutions[0].members == (0, 1, 2)
    assert all(row["consumption"] == 1.2 for row in episode.private_feedback)
    assert all(row["political_fee_private"] == 0. for row in episode.private_feedback)


def test_unchanged_good_terms_can_exit_after_own_shortfall_and_refund_only_later():
    episode = Episode(local_world(stock=0., inventory=2., members=(0, 1, 2)),
                      [member_policy(), inert(), inert()])
    initial_charter = episode.state.institutions[0].charter
    events = []
    checkpoints = []
    for _ in range(8):
        checkpoints.append(json.loads(json.dumps(episode.checkpoint())))
        result = episode.advance()
        events.append((result.ledger.tick, episode.last_intents[0], result))
    exits = [(tick, result) for tick, intent, result in events if intent.kind == "exit"]
    assert len(exits) == 1 and exits[0][0] == 4
    exit_tick, exited = exits[0]
    assert exited.state.institutions[0].charter == initial_charter
    assert exited.state.world.agents[0].inventory == exited.physical.ledger.agents[0].inventory_after, "exit is not an instant refund"
    bond = next(b for b in exited.state.institutions[0].bonds if b.owner == 0)
    assert bond.release_tick == exit_tick + 2 and bond.amount == 1.
    withdrew = [(tick, result) for tick, intent, result in events if intent.kind == "withdraw"]
    assert len(withdrew) == 1 and withdrew[0][0] == 6
    assert withdrew[0][1].physical.ledger.agents[0].consumption == 0.
    assert withdrew[0][1].state.world.agents[0].inventory == pytest.approx(
        withdrew[0][1].physical.ledger.agents[0].inventory_after + 1.)
    assert all(intent.kind not in ("join", "endorse", "propose") for tick, intent, _ in events if tick > exit_tick)
    # Restore a checkpoint containing adverse private feedback and reproduce
    # the actual exit, cooldown and delayed claim retrieval.
    resumed = restore_checkpoint(checkpoints[3])
    for tick, intent, expected in events[3:]:
        assert resumed.advance() == expected
        assert resumed.last_intents[0] == intent


def test_shortfall_from_before_entry_is_not_counted_as_membership_outcome():
    from swarm_societies.commons_v3.own_feedback_v2 import VERSION, PHYSICAL_FIELDS, POLITICAL_FIELDS
    state = local_world(members=(0, 1, 2))
    state = replace(state, world=replace(state.world, tick=4))
    packet = politics.observe(state, 0)
    packet["private_feedback"] = {"version": VERSION, "tick": 3, "agent": 0,
        **{k: 0. for k in (*PHYSICAL_FIELDS, *POLITICAL_FIELDS)}, "shortfall": 1.2}
    policy = member_policy()
    policy(packet)
    assert policy.bad_streak == 0
    assert policy.diagnostics["own_shortfall"] == 0.


def test_mature_zero_claim_is_cleared_before_rejoining_active_institution():
    state = local_world(members=(0, 1))
    state = replace(state, world=replace(state.world, tick=2),
        institutions=(replace(state.institutions[0], charter=politics.Charter(bond=0.),
            bonds=(politics.Bond(0, 0.), politics.Bond(1, 0.), politics.Bond(2, 0., 2))),))
    episode = Episode(state, [inert(), inert(), member_policy()])
    episode.advance()
    assert episode.last_intents[2] == politics.Intent("withdraw", 0, amount=0.)
    assert all(b.owner != 2 for b in episode.state.institutions[0].bonds)
    episode.advance()
    assert episode.last_intents[2] == politics.Intent("join", 0)
    assert episode.state.institutions[0].members == (0, 1, 2)


def test_remote_exit_uses_own_receipt_without_remote_treasury_or_quota_forecast():
    episode = Episode(local_world(stock=0., inventory=0., members=(0, 1, 2), remote=True),
                      [inert(), inert(), member_policy()])
    for _ in range(5):
        packet = politics.observe(episode.state, 2)
        assert not packet["politics"]["institutions"]
        episode.advance()
        assert episode.policies[2].diagnostics["member_rate"] is None
    assert episode.last_intents[2].kind == "exit"
    assert episode.state.world.agents[2].inventory == 0.
    assert any(b.owner == 2 and b.release_tick is not None for b in episode.state.institutions[0].bonds)


def test_decentralized_and_nonjoining_charter_modes_share_identical_coordination():
    # No founding partner: enabling optional institutions grants no free
    # material, report or observation advantage and makes no paid political act.
    state = local_world(remote=True)
    left, right = member_policy(organization=False), member_policy(organization=True)
    for _ in range(5):
        packet = politics.observe(state, 2)
        a, b = left(packet), right(packet)
        assert a == b and a[1] == politics.Intent()
        assert left.coordinator.memory() == right.coordinator.memory()
        state = politics.step(state, (engine.Action(), engine.Action(), a[0])).state


def test_sustained_local_outside_advantage_can_end_a_costly_quota_promise():
    episode = Episode(local_world(members=(0, 1, 2), quota=.5), [member_policy(), inert(), inert()])
    for _ in range(5):
        episode.advance()
        assert episode.last_actions[0].harvest <= .5
    assert episode.last_intents[0].kind == "exit"
    assert episode.policies[0].diagnostics["outside_rate"] > episode.policies[0].diagnostics["member_rate"]
    assert episode.policies[0].diagnostics["own_shortfall"] == 0., "forecast and realized dissatisfaction are distinct"


def test_remembered_own_charter_applies_on_arrival_without_a_remote_board():
    state = local_world(inventory=3., members=(0, 1, 2), quota=.5)
    state = replace(state, world=replace(state.world, config=replace(state.world.config, width=2)))
    policy = member_policy()
    policy(politics.observe(state, 0))  # Legally learn the own institution's site.
    # A declared physical branch places the remembered member one step away.
    state = politics.step(state, (engine.Action(move=(1, 0)), engine.Action(), engine.Action())).state
    packet = politics.observe(state, 0)
    assert not packet["politics"]["institutions"]
    action, _ = policy(packet)
    assert action.move == (-1, 0) and 0. < action.harvest <= .5
    assert policy.diagnostics["member_rate"] is None, "no fabricated remote service forecast"
    assert MembershipPolicy.restore(json.loads(json.dumps(policy.memory()))).memory() == policy.memory()


def test_changing_hidden_remote_information_cannot_change_local_decision():
    state = local_world(members=(0, 1), remote=True)
    changed = replace(state, institutions=(replace(state.institutions[0], treasury=5.),),
        world=replace(state.world, agents=(replace(state.world.agents[0], inventory=70.), *state.world.agents[1:])))
    a, b = politics.observe(state, 2), politics.observe(changed, 2)
    assert a == b
    p, q = member_policy(), member_policy()
    assert p(a) == q(b) and p.memory() == q.memory()


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(owner=1),
    lambda m: m.update(last_tick=5),
    lambda m: m.update(member_site=0),
    lambda m: m.update(organization="yes"),
    lambda m: m.update(entry_reserve_ticks=float("nan")),
    lambda m: m.update(bad_streak=True),
    lambda m: m.update(source="arbitrary_code.py"),
    lambda m: m.update(diagnostics={"tick": 0}),
])
def test_restore_rejects_malformed_or_inconsistent_history(mutate):
    memory = member_policy().memory()
    mutate(memory)
    with pytest.raises(ValueError):
        MembershipPolicy.restore(memory)


def test_observations_are_not_mutated_and_duplicate_decision_time_is_rejected():
    packet = politics.observe(local_world(), 0)
    before = deepcopy(packet)
    policy = member_policy()
    policy(packet)
    assert packet == before
    assert MembershipPolicy.restore(json.loads(json.dumps(policy.memory()))).memory() == policy.memory()
    with pytest.raises(ValueError, match="consecutive"):
        policy(packet)
