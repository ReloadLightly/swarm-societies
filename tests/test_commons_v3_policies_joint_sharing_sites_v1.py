"""Synthetic integration fixtures, never the contracted development panel."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import observations_joint_sites_v1 as adapter
from swarm_societies.commons_v3 import observations_messages_sites_v1 as known_adapter
from swarm_societies.commons_v3.messages_sites_v1 import (
    BeliefSummary, GrowthEvidence, HarvestReceipt, decode, encode,
)
from swarm_societies.commons_v3.policies_joint_sharing_sites_v1 import UnknownSharingForager
from swarm_societies.commons_v3.posterior_joint_sites_v1 import JointPosterior


NUMERICS = {"grid_size": 32, "rate_bins": 4, "rate_order": 4}


def fixture_world():
    config = engine.Config(width=7, height=3, n_agents=4, n_patches=3,
                           sensing_radius=2, need=1.2, max_messages=4,
                           site_capacities=(20., 40., 80.),
                           initial_site_stocks=(12., 24., 48.))
    state = engine.initialize(config, seed=37)
    return replace(state,
                   agents=tuple(replace(a, x=x, y=1)
                                for a, x in zip(state.agents, (1, 1, 3, 5))),
                   patches=tuple(replace(p, x=x, y=1)
                                 for p, x in zip(state.patches, (1, 3, 5))))


def message(sender, social, tick, recipient=0):
    return {"sender": sender, "recipient": recipient, "sent_tick": tick - 1,
            "delivery_tick": tick, "text": encode(social)}


@pytest.mark.parametrize("arm,biased", [
    ("L1", False), ("L2", False), ("L3", False), ("L2", True), ("L3", True),
])
def test_paid_engine_messages_and_exact_continuation_with_private_joint_owners(arm, biased):
    state, feedback = fixture_world(), None
    policies = [UnknownSharingForager(arm, biased=biased and a.id == 1, **NUMERICS)
                for a in state.agents]
    assert len({id(p.joint) for p in policies}) == len(policies)
    resumed = None
    paid = 0
    for tick in range(8):
        packets = adapter.observations(state, feedback)
        original_packets = deepcopy(packets)
        actions = []
        for policy, packet in zip(policies, packets):
            action = policy(packet)
            memory = deepcopy(policy.memory())
            assert policy(deepcopy(packet)) is action
            assert policy.memory() == memory
            json.dumps(memory, allow_nan=False)
            assert all(p.owner is policy.joint for p in policy.posteriors.values())
            assert type(action) is engine.Action
            actions.append(action)
        assert packets == original_packets
        result = engine.step(state, actions)
        paid += sum(row.cost > 0. for row in result.ledger.messages)
        if resumed is not None:
            copied_state, copied_feedback, copied_policies = resumed
            copied_packets = adapter.observations(copied_state, copied_feedback)
            copied_actions = [p(o) for p, o in zip(copied_policies, copied_packets)]
            assert copied_packets == packets and copied_actions == actions
            copied_result = engine.step(copied_state, copied_actions)
            assert copied_result == result
            assert [p.memory() for p in copied_policies] == [p.memory() for p in policies]
            assert all(view.owner is p.joint for p in copied_policies
                       for view in p.posteriors.values())
            resumed = copied_result.state, copied_result, copied_policies
        state, feedback = result.state, result
        if tick == 3:
            resumed = (engine.restore(json.loads(json.dumps(engine.snapshot(state)))),
                       known_adapter.private_harvest_receipts(result), deepcopy(policies))
    assert paid > 0
    assert sum(p.counters["clean_receipts"] for p in policies) > 0
    if arm == "L3":
        assert sum(p.counters["belief_messages"] for p in policies) > 0
    for policy, packet in zip(policies, adapter.observations(state, feedback)):
        old = policy.memory()
        policy.observe(packet)
        terminal = deepcopy(policy.memory())
        assert terminal["forager"] == old["forager"]
        assert terminal["last_action"] == old["last_action"]
        assert terminal["observed_tick"] == 8 and terminal["acted_tick"] == 7
        for key in ("attempted_messages", "attempted_bytes"):
            assert terminal["counters"][key] == old["counters"][key]
        policy.observe(deepcopy(packet))
        assert policy.memory() == terminal


def test_real_receipts_and_same_event_relay_update_once_even_after_newer_bounds():
    state = fixture_world()
    policy = UnknownSharingForager("L2", **NUMERICS)
    policy.observe(adapter.observations(state)[0])
    harvest = (engine.Action(harvest=1.), engine.Action(harvest=2.),
               engine.Action(harvest=1.), engine.Action())
    policy.last_action = harvest[0]
    first = engine.step(state, harvest)
    policy.observe(adapter.observations(first.state, first)[0])
    assert not policy.events and policy.counters["confounded"] == 1
    row = first.ledger.patches[0]
    event = GrowthEvidence(0, 0, row.stock_after_harvest, row.stock_after)
    receipt = HarvestReceipt(0, 0, first.ledger.agents[1].harvested)
    sending = (engine.Action(), engine.Action(messages=((0, encode(receipt) + encode(event)),)),
               engine.Action(), engine.Action())
    policy.last_action = sending[0]
    second = engine.step(first.state, sending)
    packet = adapter.observations(second.state, second)[0]
    # The event arrives after the endpoint's stock bound was already seen.
    assert second.ledger.message_cost == pytest.approx(.126)
    policy.observe(packet)
    assert policy.events == {(0, 0): event}
    assert policy.counters["clean_receipts"] == 1
    assert policy.counters["duplicates"] == 1
    transitions = [op for op in policy.joint.memory()["operations"] if op["kind"] == "transition"]
    assert len(transitions) == 1
    assert transitions[0]["event"]["z"] == row.stock_before - 3.
    assert [u["kind"] for u in policy.last_updates][0] == "growth"
    third = engine.step(second.state, (engine.Action(), engine.Action(),
                        engine.Action(messages=((0, encode(event)),)), engine.Action()))
    assert third.ledger.message_cost == pytest.approx(.096)
    policy.last_action = engine.Action()
    policy.observe(adapter.observations(third.state, third)[0])
    assert policy.counters["duplicates"] == 2
    assert [op for op in policy.joint.memory()["operations"]
            if op["kind"] == "transition"] == transitions


def test_remote_relay_updates_shared_rate_and_remembered_site_capacity():
    state = fixture_world()
    policy = UnknownSharingForager("L2", **NUMERICS)
    packet = adapter.observations(state)[0]
    policy(packet)
    remote = policy._posterior(1)
    remote.update_event(GrowthEvidence(1, 0, 20., 22.42))
    before, rate_before = remote.quantile(.25), policy.joint.rate_quantile(.5)
    prior_navigation = deepcopy(policy.records)
    # Legal older evidence from a distinct site changes the common rate and
    # therefore the remembered site's marginal, without another site-1 event.
    delayed = deepcopy(packet)
    delayed["tick"] = 2
    delayed["sites"] = [site for site in delayed["sites"] if site["id"] != 1]
    delayed["private_harvest"] = {"version": known_adapter.RECEIPT_VERSION,
                                  "tick": 1, "agent": 0, "harvested": 0.}
    delayed["messages"] = [message(1, GrowthEvidence(0, 0, 1., 1.254), 2)]
    policy(delayed)
    assert abs(policy.joint.rate_quantile(.5) - rate_before) > .001
    assert abs(remote.quantile(.25) - before) > .01
    assert policy.posteriors[1] is remote and remote.owner is policy.joint
    assert 1 in prior_navigation and 1 in policy.records
    assert policy.records[1]["capacity"] == .75 * remote.quantile(.25)
    assert policy.counters["new_relay"] == 1


def test_l3_naively_multiplies_shared_beliefs_after_stock_bounds():
    packet = adapter.observations(replace(fixture_world(), tick=2))[0]
    summary = BeliefSummary(0, 60., 10.)
    packet["messages"] = [message(1, summary, 2), message(2, summary, 2)]
    single = deepcopy(packet)
    single["messages"] = single["messages"][:1]
    policy, once = (UnknownSharingForager("L3", **NUMERICS) for _ in range(2))
    policy.observe(packet)
    once.observe(single)
    operations = policy.joint.memory()["operations"]
    assert [op["kind"] for op in operations] == ["bound", "bound", "fusion", "fusion"]
    assert policy.counters["belief_messages"] == 2
    lower, upper = policy.posteriors[0].interval()
    single_lower, single_upper = once.posteriors[0].interval()
    assert upper - lower < single_upper - single_lower
    assert JointPosterior.restore(policy.joint.memory()).memory() == policy.joint.memory()
    # A repeated observation is not another exchange. Distinct messages above
    # deliberately double-count the common evidence within those beliefs.
    before = deepcopy(policy.memory())
    policy.observe(deepcopy(packet))
    assert policy.memory() == before


@pytest.mark.parametrize("arm,social", [
    ("L2", GrowthEvidence(2, 0, 20., 23.62)),
    ("L3", BeliefSummary(2, 70., 15.)),
])
def test_shared_unseen_site_belief_does_not_reveal_coordinates_or_navigation(arm, social):
    packet = adapter.observations(replace(fixture_world(), tick=2))[0]
    assert 2 not in {site["id"] for site in packet["sites"]}
    packet["messages"] = [message(1, social, 2)]
    policy = UnknownSharingForager(arm, **NUMERICS)
    policy(packet)
    assert 2 in policy.posteriors
    assert policy.posteriors[2].owner is policy.joint
    assert 2 not in policy.records and 2 not in policy.sites


@pytest.mark.parametrize("arm", ["L2", "L3"])
def test_bias_changes_only_capacity_prior_and_truthfully_reports_joint_marginals(arm):
    common = UnknownSharingForager(arm, **NUMERICS)
    biased = UnknownSharingForager(arm, biased=True, **NUMERICS)
    for policy in (common, biased):
        policy._posterior(0)
        assert policy.joint.rate_cdf(.24) == pytest.approx(.5)
    # Below 50, only the one-percent common component contributes.
    assert biased.posteriors[0].cdf(40.) == pytest.approx(.01 * common.posteriors[0].cdf(40.))
    packet = adapter.observations(fixture_world())[0]
    common(packet)
    action = biased(packet)
    assert all(p.biased and p.owner is biased.joint for p in biased.posteriors.values())
    assert biased.posteriors[0].quantile(.5) > common.posteriors[0].quantile(.5)
    summaries = [social for _, text in action.messages for _, social in [decode(text)]
                 if type(social) is BeliefSummary]
    if arm == "L3":
        assert len(summaries) == 1
        summary = summaries[0]
        posterior = biased.posteriors[summary.site]
        assert summary.median == posterior.quantile(.5)
        assert summary.iqr == posterior.quantile(.75) - posterior.quantile(.25)
    else:
        assert summaries == []


def test_l2_l3_use_identical_paid_schedule_and_bytes_for_identical_local_histories():
    state = fixture_world()
    left, right = (UnknownSharingForager(arm, **NUMERICS) for arm in ("L2", "L3"))
    feedback = None
    for tick in range(6):
        packet = adapter.observations(state, feedback)[0]
        l_action, r_action = left(packet), right(packet)
        assert [(peer, len(text)) for peer, text in l_action.messages] == [
            (peer, len(text)) for peer, text in r_action.messages]
        assert len(l_action.messages) <= 4
        assert all(len(text) in (30, 96, 126) for _, text in l_action.messages)
        assert sum(len(text) >= 96 for _, text in l_action.messages) == int(tick % 4 == 0)
        feedback = engine.step(state, [l_action, engine.Action(), engine.Action(), engine.Action()])
        state = feedback.state
    assert left.counters["attempted_bytes"] == right.counters["attempted_bytes"]


@pytest.mark.parametrize("arm", ["L1", "L2", "L3"])
def test_hidden_rate_validation_conflicting_observation_and_detached_memory(arm, monkeypatch):
    from swarm_societies.commons_v3 import policies_sharing_sites_v1 as known_policy

    def forbidden(_):
        raise AssertionError("known-rate validator must never be called")

    monkeypatch.setattr(known_policy, "_validate_ecology", forbidden)
    state = fixture_world()
    policy = UnknownSharingForager(arm, **NUMERICS)
    packet = adapter.observations(state)[0]
    policy(packet)
    expected = deepcopy(policy.memory())
    detached = policy.memory()
    detached["joint"]["operations"][0]["stock"] = -1.
    detached["last_updates"][0]["stock"] = -1.
    assert policy.memory() == expected
    assert "renewal_rate" not in packet["ecology"]
    leaked = deepcopy(packet)
    leaked["ecology"]["renewal_rate"] = .24
    with pytest.raises(ValueError, match="unknown-rate ecological"):
        policy(leaked)
    with pytest.raises(ValueError, match="unknown-rate observation"):
        policy(known_adapter.observations(state)[0])
    changed = deepcopy(packet)
    changed["sites"][0]["stock"] += .1
    with pytest.raises(ValueError, match="conflicting"):
        policy(changed)
    assert policy.memory() == expected


@pytest.mark.parametrize("kwargs", [
    {"arm": "L0"}, {"arm": "R-pool"}, {"arm": "L1", "biased": True},
    {"arm": "L3", "biased": 1}, {"arm": "L2", "q": .5},
    {"arm": "L2", "q": True}, {"arm": "L2", "phi": .5},
])
def test_constructor_keeps_the_approved_a2_decision_rule(kwargs):
    with pytest.raises(ValueError):
        UnknownSharingForager(**kwargs, **NUMERICS)
