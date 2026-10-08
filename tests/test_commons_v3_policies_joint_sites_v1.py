"""A2 policy and information-flow fixtures, never the scientific seed panel."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import observations_joint_sites_v1 as adapter
from swarm_societies.commons_v3 import observations_messages_sites_v1 as known_adapter
from swarm_societies.commons_v3.messages_sites_v1 import GrowthEvidence
from swarm_societies.commons_v3.policies_joint_sites_v1 import (
    UnknownForager, UnknownPoolCoordinator, UnknownPoolForager,
)


NUMERICS = {"grid_size": 32, "rate_bins": 8}


def fixture_world():
    config = engine.Config(width=10, height=3, n_agents=4, n_patches=3,
                           sensing_radius=1, max_messages=4,
                           site_capacities=(20., 40., 80.),
                           initial_site_stocks=(12., 24., 48.))
    state = engine.initialize(config, seed=37)
    return replace(state,
                   agents=tuple(replace(a, x=x, y=1)
                                for a, x in zip(state.agents, (1, 1, 4, 6))),
                   patches=tuple(replace(p, x=x, y=1)
                                 for p, x in zip(state.patches, (1, 4, 8))))


def test_l0_keeps_shared_harvest_confounded_and_agents_have_private_rates():
    state = fixture_world()
    policies = [UnknownForager(**NUMERICS) for _ in state.agents]
    packets = adapter.observations(state)
    for policy, packet in zip(policies, packets):
        policy.observe(packet)
        policy.last_action = engine.Action(harvest=1.)
    assert len({id(policy.joint) for policy in policies}) == 4
    result = engine.step(state, [policy.last_action for policy in policies])
    for policy, packet in zip(policies, adapter.observations(result.state, result)):
        policy.observe(packet)
    assert policies[0].counters["confounded"] == policies[1].counters["confounded"] == 1
    assert policies[0].counters["clean_own"] == policies[1].counters["clean_own"] == 0
    assert policies[2].counters["clean_own"] == 1
    assert policies[3].posteriors == {}
    assert not policies[0].events and not policies[1].events


def test_evidence_at_one_site_changes_another_capacity_marginal_through_shared_rate():
    policy = UnknownForager(**NUMERICS)
    remote = policy._posterior(1)
    remote.update_event(GrowthEvidence(1, 0, 20., 22.42))
    before, revision = remote.quantile(.5), remote.revision
    isolated = UnknownForager(**NUMERICS)
    isolated._posterior(1).update_event(GrowthEvidence(1, 0, 20., 22.42))
    independent_memory = isolated.memory()
    policy._posterior(0).update_event(GrowthEvidence(0, 0, 1., 1.254))
    after = remote.quantile(.5)
    assert abs(before - after) > .01
    assert remote.revision > revision  # Evaluator cache must invalidate too.
    assert policy.posteriors[1] is remote
    assert policy.joint.site(1) is remote
    assert isolated.posteriors[1].quantile(.5) == before
    assert isolated.memory() == independent_memory


def test_pool_reuses_union_events_but_keeps_navigation_and_sightings_local():
    state = fixture_world()
    pool = UnknownPoolCoordinator(**NUMERICS)
    policies = [UnknownPoolForager(pool, a.id) for a in state.agents]
    packets = adapter.observations(state)
    pool.prepare(packets)
    actions = [policy(packet) for policy, packet in zip(policies, packets)]
    assert set(pool.posteriors) == {0, 1}
    assert all(policy.joint is pool.joint and policy.posteriors is pool.posteriors for policy in policies)
    assert set(policies[0].records) == {0}
    assert set(policies[2].records) == {1}
    assert policies[3].records == {} and policies[3].sites == {}
    assert all(not action.messages for action in actions)
    result = engine.step(state, actions)
    pool.prepare(adapter.observations(result.state, result), result)
    events = [update for update in pool.last_updates if update["kind"] == "growth"]
    assert [(event["site"], event["tick"]) for event in events] == [(0, 0), (1, 0)]
    assert events[0]["z"] == 12. - result.ledger.patches[0].harvested
    assert pool.counters["eligible"] == pool.counters["clean_receipts"] == 2


def test_pool_ignores_true_rate_capacity_weather_and_unobserved_extraction():
    state = fixture_world()
    result = engine.step(state, [engine.Action(harvest=2.) for _ in state.agents])
    original, altered = UnknownPoolCoordinator(**NUMERICS), UnknownPoolCoordinator(**NUMERICS)
    for pool in (original, altered):
        pool.prepare(adapter.observations(state))
    changed_state = replace(result.state,
        config=replace(result.state.config, renewal_rate=.48, site_capacities=(30., 50., 90.)),
        patches=tuple(replace(p, stock=999.) for p in result.state.patches))
    changed_rows = tuple(replace(row, stock_before=999., stock_after_harvest=999.,
                                stock_after=999., weather=999., growth=999.,
                                potential_growth=999.) for row in result.ledger.patches)
    changed_rows = changed_rows[:2] + (replace(changed_rows[2], harvested=999.),)
    changed = replace(result, state=changed_state,
                      ledger=replace(result.ledger, patches=changed_rows))
    packets = adapter.observations(result.state, result)
    original.prepare(packets, result)
    altered.prepare(packets, changed)
    assert original.memory() == altered.memory()
    assert set(original.posteriors) == {0, 1}


@pytest.mark.parametrize("kind", ["L0", "R-pool"])
def test_repeat_terminal_assimilation_and_deepcopy_preserve_exact_state(kind):
    state = fixture_world()
    pool = UnknownPoolCoordinator(**NUMERICS) if kind == "R-pool" else None
    policies = ([UnknownPoolForager(pool, a.id) for a in state.agents] if pool else
                [UnknownForager(**NUMERICS) for _ in state.agents])
    packets = adapter.observations(state)
    if pool:
        pool.prepare(packets)
    actions = [policy(packet) for policy, packet in zip(policies, packets)]
    for policy, packet, action in zip(policies, packets, actions):
        before = policy.memory()
        assert policy(packet) is action
        assert policy.memory() == before
        json.dumps(before, allow_nan=False)
    copied_pool, copied_policies = deepcopy((pool, policies))
    if pool:
        assert all(policy.joint is copied_pool.joint for policy in copied_policies)
    result = engine.step(state, actions)
    assert result.ledger.message_cost == 0 and result.ledger.messages == ()
    following = adapter.observations(result.state, result)
    for coordinator, members in ((pool, policies), (copied_pool, copied_policies)):
        if coordinator:
            coordinator.prepare(following, result)
        for policy, packet in zip(members, following):
            before = policy.memory()
            policy.observe(packet)
            after = policy.memory()
            assert after["forager"] == before["forager"]
            assert after["last_action"] == before["last_action"]
            assert after["observed_tick"] == 1 and after["acted_tick"] == 0
    assert [policy.memory() for policy in policies] == [policy.memory() for policy in copied_policies]


def test_known_rate_validator_is_never_called_or_reinjected(monkeypatch):
    from swarm_societies.commons_v3 import policies_learning_sites_v1 as known
    from swarm_societies.commons_v3 import policies_pool_sites_v1 as known_pool

    def forbidden(_):
        raise AssertionError("known-rate validation was called")

    monkeypatch.setattr(known, "_validate_ecology", forbidden)
    monkeypatch.setattr(known_pool, "_validate_ecology", forbidden)
    state = fixture_world()
    packets = adapter.observations(state)
    forager = UnknownForager(**NUMERICS)
    forager(packets[0])
    pool = UnknownPoolCoordinator(**NUMERICS)
    pool.prepare(packets)
    UnknownPoolForager(pool, 0)(packets[0])
    assert all("renewal_rate" not in packet["ecology"] for packet in packets)
    with pytest.raises(ValueError, match="unknown-rate observation"):
        forager(known_adapter.observations(state)[0])


@pytest.mark.parametrize("kwargs", [{"arm": "L1"}, {"phi": .5}, {"q": .5}, {"q": True}])
def test_l0_rejects_changes_outside_the_approved_fallback(kwargs):
    with pytest.raises(ValueError):
        UnknownForager(**kwargs)


def test_pool_rejects_unprepared_or_known_rate_packets():
    state = fixture_world()
    pool = UnknownPoolCoordinator(**NUMERICS)
    policy = UnknownPoolForager(pool, 0)
    with pytest.raises(ValueError, match="prepare"):
        policy(adapter.observations(state)[0])
    with pytest.raises(ValueError, match="unknown-rate observation"):
        pool.prepare(known_adapter.observations(state))
