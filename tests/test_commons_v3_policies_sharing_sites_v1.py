"""Small engineering fixtures, never Ticket D development/evaluation seeds."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import observations_messages_sites_v1 as adapter
from swarm_societies.commons_v3.messages_sites_v1 import BeliefSummary, decode
from swarm_societies.commons_v3.policies_learning_sites_v1 import AsocialForager
from swarm_societies.commons_v3.policies_sharing_sites_v1 import LearningForager


def fixture_world():
    capacities = (12., 40., 70.)
    config = engine.Config(width=7, height=3, n_agents=4, n_patches=3,
                           sensing_radius=2, need=1.2, max_messages=4,
                           site_capacities=capacities,
                           initial_site_stocks=tuple(.6 * k for k in capacities))
    state = engine.initialize(config, seed=17)
    return replace(state,
                   agents=tuple(replace(agent, x=x, y=1)
                                for agent, x in zip(state.agents, (1, 1, 3, 5))),
                   patches=tuple(replace(site, x=x, y=1)
                                 for site, x in zip(state.patches, (1, 3, 5))))


@pytest.mark.parametrize("q", [.25, .5])
def test_l0_actions_and_navigation_match_frozen_c_without_fusion(q):
    state, previous = fixture_world(), None
    frozen = [AsocialForager(q=q) for _ in state.agents]
    current = [LearningForager("L0", q=q) for _ in state.agents]
    clean = 0
    for _ in range(16):
        packets = adapter.observations(state, previous)
        actions = []
        for original, social, packet in zip(frozen, current, packets):
            old_action, new_action = original(packet), social(packet)
            assert old_action == new_action
            assert original.memory()["forager"] == social.memory()["forager"]
            assert original.evidence.memory() == social.evidence.memory()
            assert original.posteriors.keys() == social.posteriors.keys()
            for site in original.posteriors:
                before, after = original.posteriors[site], social.posteriors[site]
                assert before.atoms == after.atoms
                assert before.continuous_mass == after.continuous_mass
                assert before.interval() == after.interval()
            assert new_action.messages == ()
            clean += len(social.last_updates)
            actions.append(new_action)
        previous = engine.step(state, actions)
        state = previous.state
    assert clean > 0


@pytest.mark.parametrize("arm,biased", [
    ("L0", False), ("L1", False), ("L2", False), ("L3", False),
    ("L2", True), ("L3", True),
])
def test_short_paid_message_fixture_and_exact_checkpoint_continuation(arm, biased):
    state, previous = fixture_world(), None
    policies = [LearningForager(arm, biased=biased and agent.id == 2) for agent in state.agents]
    resumed_state = resumed_policies = resumed_feedback = None
    paid = received_beliefs = 0
    for tick in range(16):
        packets = adapter.observations(state, previous)
        originals = deepcopy(packets)
        actions = []
        for policy, packet in zip(policies, packets):
            action = policy(packet)
            before = deepcopy(policy.memory())
            assert policy(deepcopy(packet)) is action
            assert policy.memory() == before
            json.dumps(before, allow_nan=False)
            assert type(action) is engine.Action
            actions.append(action)
        assert packets == originals
        result = engine.step(state, actions)
        paid += sum(message.cost > 0. for message in result.ledger.messages)
        if resumed_state is not None:
            resumed_packets = adapter.observations(resumed_state, resumed_feedback)
            resumed_actions = [policy(packet) for policy, packet in zip(resumed_policies, resumed_packets)]
            assert resumed_packets == packets
            assert resumed_actions == actions
            resumed_result = engine.step(resumed_state, resumed_actions)
            assert resumed_result == result
            assert [policy.memory() for policy in resumed_policies] == [policy.memory() for policy in policies]
            resumed_state, resumed_feedback = resumed_result.state, resumed_result
        state, previous = result.state, result
        if tick == 7:
            resumed_state = engine.restore(json.loads(json.dumps(engine.snapshot(state))))
            resumed_policies = deepcopy(policies)
            resumed_feedback = adapter.private_harvest_receipts(result)
    assert paid == 0 if arm == "L0" else paid > 0
    assert sum(policy.counters["clean_own"] + policy.counters["clean_receipts"]
               for policy in policies) > 0
    if arm == "L3":
        received_beliefs = sum(policy.counters["belief_messages"] for policy in policies)
        assert received_beliefs > 0
    # Final observation is an inference operation, with no extra navigation,
    # message attempt, or unexecuted decision at the terminal boundary.
    for policy, packet in zip(policies, adapter.observations(state, previous)):
        old = deepcopy(policy.memory())
        policy.observe(packet)
        terminal = deepcopy(policy.memory())
        assert terminal["forager"] == old["forager"]
        assert terminal["last_action"] == old["last_action"]
        assert terminal["acted_tick"] == 15
        assert terminal["observed_tick"] == 16
        assert terminal["counters"]["attempted_messages"] == old["counters"]["attempted_messages"]
        assert terminal["counters"]["attempted_bytes"] == old["counters"]["attempted_bytes"]
        policy.observe(deepcopy(packet))
        assert policy.memory() == terminal


def test_biased_flag_is_external_to_agent_identity_and_truthful_belief_report():
    state = fixture_world()
    packets = adapter.observations(state)
    for identity in (0, 2):
        common = LearningForager("L3")
        biased = LearningForager("L3", biased=True)
        common(packets[identity])
        action = biased(packets[identity])
        assert all(p.biased for p in biased.posteriors.values())
        assert all(not p.biased for p in common.posteriors.values())
        assert any(biased.posteriors[site].quantile(.5) > common.posteriors[site].quantile(.5)
                   for site in common.posteriors)
        summaries = [social for _, text in action.messages for _, social in [decode(text)]
                     if type(social) is BeliefSummary]
        assert len(summaries) == 1
        summary = summaries[0]
        posterior = biased.posteriors[summary.site]
        assert summary.median == posterior.quantile(.5)
        assert summary.iqr == posterior.quantile(.75) - posterior.quantile(.25)


def test_terminal_first_observation_has_no_navigation_or_transmission():
    packet = adapter.observations(fixture_world())[0]
    policy = LearningForager("L3")
    before = policy.memory()
    policy.observe(packet)
    after = policy.memory()
    assert after["posteriors"]
    assert after["forager"] == before["forager"]
    assert after["acted_tick"] is None and after["last_action"] is None
    assert after["counters"]["attempted_messages"] == 0
    # Observing first and acting later at the same tick must still make exactly
    # the same one decision as the normal call path.
    direct = LearningForager("L3")
    assert policy(packet) == direct(packet)
    assert policy.memory() == direct.memory()


@pytest.mark.parametrize("arm", ["L0", "L1", "L2", "L3"])
def test_conflicting_same_tick_local_packet_is_rejected_and_memory_is_detached(arm):
    packet = adapter.observations(fixture_world())[0]
    policy = LearningForager(arm)
    policy(packet)
    expected = deepcopy(policy.memory())
    detached = policy.memory()
    detached["last_updates"][0]["stock"] = -1.
    assert policy.memory() == expected
    conflicting = deepcopy(packet)
    conflicting["sites"][0]["stock"] += .1
    with pytest.raises(ValueError, match="conflicting"):
        policy(conflicting)
    assert policy.memory() == expected


@pytest.mark.parametrize("kwargs", [
    {"arm": "unknown"}, {"arm": "L0", "biased": True},
    {"arm": "L1", "biased": True}, {"arm": "L3", "biased": 1},
    {"arm": "L2", "q": .375}, {"arm": "L2", "q": True},
    {"arm": "L2", "phi": .5},
])
def test_constructor_rejects_out_of_contract_variants(kwargs):
    with pytest.raises(ValueError):
        LearningForager(**kwargs)
