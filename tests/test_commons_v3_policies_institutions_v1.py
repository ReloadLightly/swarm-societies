"""Decision regeneration, paid reports, and legal information boundaries."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3.engine import (
    Action, AgentState, Config, Message, PatchState, WorldState, initialize,
    observe, observations, step,
)
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy
from swarm_societies.commons_v3.policies_institutions_v1 import (
    CoordinatingForager, VoluntaryCharterPolicy, restore_forager,
)


def report_world(**changes):
    values = dict(width=4, height=1, n_agents=2, n_patches=2, sensing_radius=1,
                  initial_inventory=3., initial_patch_stock=40., need=1.,
                  weather_amplitude=0., renewal_rate=0., recovery=0.)
    values.update(changes)
    cfg = Config(**values)
    return WorldState(cfg, 12, 0, (AgentState(0, 1, 0, cfg.initial_inventory),
                                AgentState(1, 0, 0, cfg.initial_inventory)),
                      (PatchState(0, 1, 0, 40.), PatchState(1, 2, 0, 40.)))


def test_forager_restoration_regenerates_actions_and_every_memory_field():
    state = initialize(Config(n_agents=2, need=1.2), 10293)
    originals = [ForagerPolicy(4, .5, "nearest") for _ in state.agents]
    for _ in range(20):
        state = step(state, tuple(p(o) for p, o in zip(originals, observations(state)))).state
    restored = [restore_forager(json.loads(json.dumps(p.memory()))) for p in originals]
    for _ in range(30):
        packets = observations(state)
        left = tuple(p(o) for p, o in zip(originals, packets))
        right = tuple(p(o) for p, o in zip(restored, packets))
        assert left == right
        assert [p.memory() for p in originals] == [p.memory() for p in restored]
        state = step(state, left).state


@pytest.mark.parametrize("change", [
    lambda m: m.update(version="made-up-policy"),
    lambda m: m.update(destination=[1, 1]),
    lambda m: m["visits"].append([0, 0, True]),
    lambda m: m["sites"].append([0, 0, 0]),
    lambda m: m.update(unexpected="hidden source"),
])
def test_restore_rejects_ambiguous_or_unsupported_memory(change):
    memory = ForagerPolicy().memory()
    change(memory)
    with pytest.raises(ValueError):
        restore_forager(memory)


def test_disabling_coordination_preserves_frozen_forager_actions_and_memory():
    state = initialize(Config(n_agents=3), 8262)
    originals = [ForagerPolicy(4, .5, "nearest") for _ in state.agents]
    controls = [CoordinatingForager(share=False) for _ in state.agents]
    for _ in range(30):
        packets = observations(state)
        expected = tuple(p(o) for p, o in zip(originals, packets))
        actual = tuple(p(o) for p, o in zip(controls, packets))
        assert actual == expected
        assert [p.forager.memory() for p in controls] == [p.memory() for p in originals]
        state = step(state, expected).state


def test_report_is_paid_delayed_and_remains_dated_peer_evidence():
    state = report_world()
    sender, recipient = CoordinatingForager(), CoordinatingForager()
    packet = observe(state, 0)
    before = deepcopy(packet)
    action = sender(packet)
    assert packet == before
    assert action.messages and action.move == (0, 0)
    assert 1 not in recipient.forager.sites
    result = step(state, (action, Action()))
    assert result.ledger.message_cost == len(action.messages[0][1].encode()) * state.config.message_byte_cost
    assert result.ledger.agents[0].message_cost > 0.
    assert abs(result.ledger.residual) < 1e-12
    received = observe(result.state, 1)
    assert all(p["id"] != 1 for p in received["sites"])
    recipient(received)
    assert recipient.forager.sites[1] == (2, 0)
    assert recipient.forager.records[1]["tick"] == 0
    assert recipient.sources[1] == (0, 0)
    assert (2, 0) not in recipient.forager.seen
    assert CoordinatingForager.restore(recipient.memory()).memory() == recipient.memory()


def test_message_budget_does_not_create_waste_when_reach_fails():
    state = report_world(initial_inventory=79.9, max_harvest=10., inventory_capacity=80.)
    # Reporter stays on the first site; its peer moves from 0 to -1 would be
    # illegal, so move reporter/peer/site arrangement one cell right first.
    state = replace(state, config=replace(state.config, width=5),
                    agents=tuple(replace(a, x=a.x + 1) for a in state.agents),
                    patches=tuple(replace(p, x=p.x + 1) for p in state.patches))
    sender = CoordinatingForager(aggressive=True)
    action = sender(observe(state, 0))
    assert action.messages and action.move == (0, 0)
    result = step(state, (action, Action(move=(-1, 0))))
    assert result.ledger.messages[0].reason == "out_of_range"
    assert result.ledger.message_cost == 0.
    assert result.ledger.waste <= 1e-12


def test_unaffordable_reports_and_remote_private_state_do_not_leak():
    state = report_world(initial_inventory=.1)
    assert not CoordinatingForager()(observe(state, 0)).messages
    state = report_world()
    policies = [CoordinatingForager(), CoordinatingForager()]
    remote = replace(state, patches=(state.patches[0], replace(state.patches[1], stock=.01)))
    packets = (observe(state, 1), observe(remote, 1))
    assert packets[0] == packets[1]
    assert policies[0](packets[0]) == policies[1](packets[1])
    assert policies[0].memory() == policies[1].memory()


@pytest.mark.parametrize("text", [
    'v3s:[1,9,1,2,0,40,40,0]',
    'v3s:[1,0,1,200,0,40,40,0]',
    'v3s:[1,0,1,2,0,41,40,0]',
    'v3s:[1,0,1,2,0,NaN,40,0]',
    'v3s:{"source":"executable.py"}',
    'hello',
])
def test_malformed_reports_are_ignored(text):
    state = report_world()
    state = replace(state, tick=1, messages=(Message(0, 1, 0, 1, text),))
    policy = CoordinatingForager()
    policy(observe(state, 1))
    assert 1 not in policy.forager.sites


def test_coordinator_checkpoint_preserves_reporting_and_navigation_decisions():
    state = report_world()
    original = [CoordinatingForager(report_period=1) for _ in state.agents]
    for _ in range(3):
        state = step(state, tuple(p(o) for p, o in zip(original, observations(state)))).state
    resumed = [CoordinatingForager.restore(json.loads(json.dumps(p.memory()))) for p in original]
    for _ in range(12):
        packets = observations(state)
        actions = tuple(p(o) for p, o in zip(original, packets))
        assert actions == tuple(p(o) for p, o in zip(resumed, packets))
        assert [p.memory() for p in original] == [p.memory() for p in resumed]
        state = step(state, actions).state


def institutional_world(*, treasury=1., quota=3.9, dues=.1):
    from swarm_societies.commons_v3 import politics_v1 as politics
    physical = report_world(initial_inventory=3.)
    physical = replace(physical, agents=tuple(replace(a, x=1) for a in physical.agents))
    charter = politics.Charter(quota=quota, dues=dues)
    institution = politics.Institution(0, 0, charter, (0, 1),
                                      (politics.Bond(0, 1.), politics.Bond(1, 1.)), treasury)
    return politics.State(physical, politics.PoliticalConfig(), (institution,), next_id=1)


def test_supplied_responsive_choice_changes_with_local_funded_collateral_risk():
    from swarm_societies.commons_v3 import politics_v1 as politics
    policy = lambda: VoluntaryCharterPolicy(coordinator=CoordinatingForager(aggressive=True))
    funded, unfunded = institutional_world(), institutional_world(treasury=0.)
    restrained, _ = policy()(politics.observe(funded, 1))
    violation, _ = policy()(politics.observe(unfunded, 1))
    assert restrained.harvest == 3.9
    assert violation.harvest == 4.
    # This is a deterministic supplied rule fixture, not evidence that real
    # monitoring probabilities or behavioral deterrence have been estimated.
    cooperative = VoluntaryCharterPolicy(behavior="cooperative", coordinator=CoordinatingForager(aggressive=True))
    assert cooperative(politics.observe(unfunded, 1))[0].harvest == 3.9


def test_member_roster_does_not_make_a_remote_monitor_locally_available():
    from swarm_societies.commons_v3 import politics_v1 as politics
    state = institutional_world()
    state = replace(state, world=replace(state.world,
        agents=(replace(state.world.agents[0], x=3), state.world.agents[1])))
    packet = politics.observe(state, 1)
    assert packet["politics"]["institutions"][0]["members"] == [0, 1]
    assert not packet["peers"]
    policy = VoluntaryCharterPolicy(coordinator=CoordinatingForager(aggressive=True))
    assert policy(packet)[0].harvest == 4.


def test_voluntary_member_can_exit_terms_it_rejects_and_stubborn_outsider_does_not_join():
    from swarm_societies.commons_v3 import politics_v1 as politics
    costly = institutional_world(dues=1.)
    _, exit_intent = VoluntaryCharterPolicy()(politics.observe(costly, 1))
    assert exit_intent == politics.Intent("exit", 0)
    physical = report_world()
    outsider = politics.State(physical, politics.PoliticalConfig())
    policy = VoluntaryCharterPolicy(behavior="stubborn")
    _, intent = policy(politics.observe(outsider, 0))
    assert intent.kind == "none" and policy.coordinator.forager.aggressive


def test_supplied_optional_founder_and_endorsers_can_form_from_no_organizations():
    from swarm_societies.commons_v3 import politics_v1 as politics
    from swarm_societies.commons_v3.political_episode_v1 import Episode
    physical = report_world(initial_inventory=10.)
    physical = replace(physical, agents=tuple(replace(a, x=1) for a in physical.agents))
    episode = Episode(politics.State(physical, politics.PoliticalConfig()),
                      [VoluntaryCharterPolicy() for _ in physical.agents])
    assert not episode.state.institutions
    episode.advance()
    assert episode.last_intents[0].kind == "propose"
    assert len(episode.state.proposals) == 1
    episode.advance()
    assert [intent.kind for intent in episode.last_intents] == ["endorse", "endorse"]
    assert len(episode.state.institutions) == 1
    assert episode.state.institutions[0].members == (0, 1)
    assert all(agent.inventory < 10. for agent in episode.state.world.agents)


def test_unaffiliated_policy_collects_mature_local_claim_before_new_membership():
    from swarm_societies.commons_v3 import politics_v1 as politics
    state = institutional_world()
    old = replace(state.institutions[0], active=False, members=(), treasury=0.,
                  bonds=(politics.Bond(0, 1., 2), politics.Bond(1, 1., 2)))
    state = replace(state, world=replace(state.world, tick=2), institutions=(old,))
    policy = VoluntaryCharterPolicy()
    action, intent = policy(politics.observe(state, 1))
    assert action.move == (0, 0)
    assert intent == politics.Intent("withdraw", 0, amount=1.)
    assert VoluntaryCharterPolicy.restore(policy.memory()).memory() == policy.memory()
    result = politics.step(state, (Action(), action), (politics.Intent(), intent))
    assert result.events[0]["ok"]
    assert all(b.owner != 1 for b in result.state.institutions[0].bonds)
