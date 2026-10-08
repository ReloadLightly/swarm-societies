"""Engineering fixtures for A1; no development or fresh evaluation seeds."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import observations_messages_sites_v1 as adapter
from swarm_societies.commons_v3.development_learning_sites_v1 import BeliefMetrics
from swarm_societies.commons_v3.messages_sites_v1 import GrowthEvidence
from swarm_societies.commons_v3.policies_pool_sites_v1 import PoolCoordinator, PoolForager
from swarm_societies.commons_v3.policies_sharing_sites_v1 import LearningForager, new_prior


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


def test_shared_extraction_is_clean_and_each_physical_event_is_applied_once():
    state = fixture_world()
    pool = PoolCoordinator()
    packets = adapter.observations(state)
    pool.prepare(packets)
    l0 = LearningForager("L0", q=.25)
    l0.observe(packets[0])
    actions = [engine.Action(harvest=3.) for _ in state.agents]
    l0.last_action = actions[0]
    result = engine.step(state, actions)
    packets_next = adapter.observations(result.state, result)
    l0.observe(packets_next[0])
    assert l0.counters["confounded"] == 1
    assert l0.counters["clean_own"] == 0
    pool.prepare(packets_next, result)
    events = [row for row in pool.last_updates if row["kind"] == "growth"]
    assert [(row["site"], row["tick"]) for row in events] == [(0, 0), (1, 0)]
    assert events[0]["z"] == 12. - result.ledger.patches[0].harvested == 6.
    expected = new_prior(site=0)
    expected.observe_stock(12.)
    expected.update_event(GrowthEvidence(0, 0, 6., result.state.patches[0].stock))
    expected.observe_stock(result.state.patches[0].stock)
    assert pool.posteriors[0].memory() == expected.memory()
    assert pool.posteriors[0].quantile(.25) == expected.quantile(.25)
    assert pool.counters["eligible"] == pool.counters["clean_receipts"] == 2
    assert 2 not in pool.posteriors


def test_only_total_extraction_comes_from_privileged_result():
    state = fixture_world()
    actions = [engine.Action(harvest=2.) for _ in state.agents]
    result = engine.step(state, actions)
    original = PoolCoordinator()
    altered = PoolCoordinator()
    for pool in (original, altered):
        pool.prepare(adapter.observations(state))
    # Change all forbidden privileged values without changing observed packets
    # or total extraction. None may enter the reference's posterior.
    changed_state = replace(result.state,
                            config=replace(result.state.config, site_capacities=(30., 50., 90.)),
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
    assert 2 not in original.posteriors


def test_union_transition_can_join_different_observers_without_harvest():
    config = engine.Config(width=5, height=3, n_agents=2, n_patches=1,
                           sensing_radius=1, site_capacities=(40.,),
                           initial_site_stocks=(24.,))
    state = engine.initialize(config, seed=19)
    state = replace(state,
                    agents=(replace(state.agents[0], x=0, y=1),
                            replace(state.agents[1], x=3, y=1)),
                    patches=(replace(state.patches[0], x=1, y=1),))
    pool = PoolCoordinator()
    packets = adapter.observations(state)
    assert len(packets[0]["sites"]) == 1 and not packets[1]["sites"]
    pool.prepare(packets)
    result = engine.step(state, [engine.Action(move=(0, -1)), engine.Action(move=(-1, 0))])
    packets = adapter.observations(result.state, result)
    assert not packets[0]["sites"] and len(packets[1]["sites"]) == 1
    pool.prepare(packets, result)
    growth = [row for row in pool.last_updates if row["kind"] == "growth"]
    assert growth == [{"kind": "growth", "site": 0, "tick": 0,
                       "z": 24., "stock_next": result.state.patches[0].stock}]


def test_no_transition_when_stock_is_missing_from_either_union():
    state = fixture_world()
    pool = PoolCoordinator()
    pool.prepare(adapter.observations(state))
    result = engine.step(state, [engine.Action(), engine.Action(),
                                 engine.Action(), engine.Action(move=(1, 0))])
    packets = adapter.observations(result.state, result)
    assert [site["id"] for site in packets[3]["sites"]] == [2]
    pool.prepare(packets, result)
    assert 2 in pool.posteriors  # New observation gives a bound, not a transition.
    assert not any(row["kind"] == "growth" and row["site"] == 2 for row in pool.last_updates)
    # Remove every observer from site 0's sensing footprint in this fixture.
    result2 = engine.step(result.state, [engine.Action(), engine.Action(), engine.Action(), engine.Action()])
    sparse_state = replace(result2.state,
                           agents=tuple(replace(a, x=8, y=1) for a in result2.state.agents))
    sparse_result = replace(result2, state=sparse_state)
    pool.prepare(adapter.observations(sparse_state, sparse_result), sparse_result)
    assert not any(row["kind"] == "growth" and row["site"] == 0 for row in pool.last_updates)


def test_pool_updates_never_add_remote_sites_to_individual_navigation():
    state = fixture_world()
    pool = PoolCoordinator()
    policies = [PoolForager(pool, a.id) for a in state.agents]
    packets = adapter.observations(state)
    pool.prepare(packets)
    actions = [policy(packet) for policy, packet in zip(policies, packets)]
    assert all(policy.posteriors is pool.posteriors for policy in policies)
    assert set(pool.posteriors) == {0, 1}
    assert set(policies[0].sites) == set(policies[0].records) == {0}
    assert not policies[3].sites and not policies[3].records
    assert all(not action.messages for action in actions)
    measure = BeliefMetrics(state.config.site_capacities, len(policies))
    measure.observe_sites(packets)
    frame, _ = measure.measure(policies, 0)
    assert frame["between_agent_log_median_dispersion"] == 0.
    assert frame["directly_seen_pairs"] == 3
    assert frame["pairs_with_posterior"] == 8


def test_remembered_capacity_refreshes_without_remote_stock_or_route_updates():
    state = fixture_world()
    pool = PoolCoordinator()
    policy = PoolForager(pool, 0)
    packets = adapter.observations(state)
    pool.prepare(packets)
    policy(packets[0])
    for move in ((-1, 0), (0, -1)):
        actions = [engine.Action(move=move)] + [engine.Action() for _ in state.agents[1:]]
        result = engine.step(state, actions)
        state = result.state
        packets = adapter.observations(state, result)
        pool.prepare(packets, result)
        previous = deepcopy(policy.records[0])
        policy(packets[0])
    assert not packets[0]["sites"]
    assert policy.records[0]["capacity"] == .75 * pool.posteriors[0].quantile(.25)
    assert policy.records[0]["capacity"] != previous["capacity"]
    assert {k: v for k, v in policy.records[0].items() if k != "capacity"} == {
        k: v for k, v in previous.items() if k != "capacity"}
    assert set(policy.records) == {0}


def test_exact_repeat_terminal_observation_and_deepcopy_continuation():
    state, previous = fixture_world(), None
    pool = PoolCoordinator()
    policies = [PoolForager(pool, a.id) for a in state.agents]
    for tick in range(8):
        packets = adapter.observations(state, previous)
        pool.prepare(packets, previous)
        before = pool.memory()
        pool.prepare(deepcopy(packets), previous)
        assert pool.memory() == before
        original_packets = deepcopy(packets)
        actions = [policy(packet) for policy, packet in zip(policies, packets)]
        assert packets == original_packets
        for policy, packet, action in zip(policies, packets, actions):
            memory = policy.memory()
            assert policy(packet) is action
            assert policy.memory() == memory
            json.dumps(memory, allow_nan=False)
        copied_pool, copied_policies = deepcopy((pool, policies))
        assert all(policy.posteriors is copied_pool.posteriors for policy in copied_policies)
        previous = engine.step(state, actions)
        assert previous.ledger.message_cost == 0 and previous.ledger.messages == ()
        state = previous.state
        next_packets = adapter.observations(state, previous)
        copied_pool.prepare(next_packets, previous)
        copied_actions = [policy(packet) for policy, packet in zip(copied_policies, next_packets)]
        if tick == 7:
            old_memories = [policy.memory() for policy in policies]
            pool.prepare(next_packets, previous)
            for policy, packet, before in zip(policies, next_packets, old_memories):
                policy.observe(packet)
                after = policy.memory()
                assert after["forager"] == before["forager"]
                assert after["last_action"] == before["last_action"]
                assert after["observed_tick"] == 8 and after["acted_tick"] == 7
                assert policy(packet) == copied_actions[policy.agent_id]
            assert [p.memory() for p in policies] == [p.memory() for p in copied_policies]


def test_saturation_likelihood_precedes_current_stock_bound():
    state = fixture_world()
    state = replace(state, patches=(replace(state.patches[0], stock=19.99), *state.patches[1:]))
    pool = PoolCoordinator()
    pool.prepare(adapter.observations(state))
    result = engine.step(state, [engine.Action() for _ in state.agents])
    assert result.state.patches[0].stock == 20.
    pool.prepare(adapter.observations(result.state, result), result)
    assert pool.posteriors[0].atoms[20.] > 0.


@pytest.mark.parametrize("kwargs", [{"agent_id": True}, {"agent_id": -1},
                                    {"q": .5}, {"q": True}, {"phi": .5}])
def test_reject_unapproved_controller_variants(kwargs):
    with pytest.raises(ValueError):
        PoolForager(PoolCoordinator(), **({"agent_id": 0} | kwargs))


def test_reject_unprepared_conflicting_and_nonconsecutive_packets():
    state = fixture_world()
    pool, policy = PoolCoordinator(), None
    policy = PoolForager(pool, 0)
    packets = adapter.observations(state)
    with pytest.raises(ValueError, match="prepare"):
        policy(packets[0])
    pool.prepare(packets)
    bad = deepcopy(packets)
    bad[0]["sites"][0]["stock"] += 1.
    with pytest.raises(ValueError, match="conflicting"):
        pool.prepare(bad)
    bad = deepcopy(packets)
    for packet in bad:
        packet["tick"] += 2
    with pytest.raises(ValueError, match="consecutive"):
        pool.prepare(bad)
    result = engine.step(state, [engine.Action() for _ in state.agents])
    with pytest.raises(ValueError, match="preceding"):
        pool.prepare(adapter.observations(result.state, result))
