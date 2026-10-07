"""Ticket A: physical parity and the hidden-capacity observation contract.

The four stored probe seeds below are engineering regressions, not fresh
development/evaluation evidence. Capacity injection exists only in the parity
test oracle so the unchanged frozen forager receives its old input contract.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json

import pytest

from swarm_societies.commons_v3 import engine as frozen
from swarm_societies.commons_v3 import engine_sites_v1 as sites
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy


G4_SEEDS = (90001, 90002, 90003, 90004)
# Generated from the unchanged frozen engine with the full row format below.
# These are regression constants, not new scientific bank identities.
G4_TRAJECTORY_SHA256 = {
    90001: "cb499ecdb1844d8e4e1597245671664de141e41911a357878c5bec6a4de14ff0",
    90002: "07d1d50ce7470016443df64e5d02d53b6e75d5573a0c67cf88c59a0e6d426116",
    90003: "02c878a8a692a32b20e165b1d8fa169e7af0a1d73991b905bd5526a9aaa128c9",
    90004: "bca758717ec39001e2bd27b7d3b21c1e90da5a234dcddc25034f28fc8a8e5ee0",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def common_state(state):
    """Normalize only the two new configuration fields, never physical state."""
    payload = asdict(state)
    payload["config"].pop("site_capacities", None)
    payload["config"].pop("initial_site_stocks", None)
    return payload


def trajectory_row(result, actions, memories):
    return {"state": common_state(result.state),
            "actions": [asdict(action) for action in actions],
            "memories": memories, "ledger": asdict(result.ledger),
            "metrics": asdict(result.metrics)}


def update_digest(digest, row):
    digest.update(canonical(row) + b"\n")


def world(agent_rows=((0, 0, 2.),), patch_rows=((0, 0, 4.),), **changes):
    values = dict(width=5, height=5, n_agents=len(agent_rows), n_patches=len(patch_rows),
                  sensing_radius=1, need=0., initial_inventory=2., inventory_capacity=20.,
                  patch_capacity=40., initial_patch_stock=4., renewal_rate=.24,
                  recovery=.02, weather_amplitude=0., max_harvest=10.,
                  movement_cost=.02, harvest_cost_per_unit=.02, message_byte_cost=.01)
    values.update(changes)
    state = sites.initialize(sites.Config(**values), seed=17)
    return replace(state,
                   agents=tuple(replace(agent, x=x, y=y, inventory=inventory)
                                for agent, (x, y, inventory) in zip(state.agents, agent_rows)),
                   patches=tuple(replace(patch, x=x, y=y, stock=stock)
                                 for patch, (x, y, stock) in zip(state.patches, patch_rows)))


def assert_conserved(result):
    ledger = result.ledger
    before = ledger.inventory_before + ledger.stock_before + ledger.growth
    after = (ledger.inventory_after + ledger.stock_after + ledger.consumption
             + ledger.movement_cost + ledger.message_cost + ledger.harvest_cost + ledger.waste)
    assert before == pytest.approx(after, rel=0., abs=1e-10 * max(1., before, after))
    assert abs(ledger.residual) <= 1e-10 * max(1., before, after)


@pytest.mark.parametrize("seed", G4_SEEDS)
def test_g4_frozen_forager_exact_512_tick_trajectory_and_pinned_digest(seed):
    old = frozen.initialize(frozen.Config(need=1.2), seed)
    new = sites.initialize(sites.Config(**asdict(old.config),
                                       site_capacities=(40.,) * 16,
                                       initial_site_stocks=(30.,) * 16), seed)
    controls = [ForagerPolicy(2, .5, "net_yield") for _ in old.agents]
    candidates = [ForagerPolicy(2, .5, "net_yield") for _ in new.agents]
    old_digest, new_digest = hashlib.sha256(), hashlib.sha256()
    assert common_state(old) == common_state(new)
    update_digest(old_digest, common_state(old))
    update_digest(new_digest, common_state(new))
    for tick in range(512):
        old_packets = frozen.observations(old)
        legal_packets = sites.observations(new)
        oracle_packets = deepcopy(legal_packets)
        for legal, oracle, old_packet in zip(legal_packets, oracle_packets, old_packets):
            assert all("capacity" not in site for site in legal["sites"])
            for site in oracle["sites"]:
                site["capacity"] = 40.
            assert oracle["sites"] == old_packet["sites"]
            for key in ("tick", "self", "peers", "messages"):
                assert oracle[key] == old_packet[key]
        old_actions = tuple(policy(packet) for policy, packet in zip(controls, old_packets))
        new_actions = tuple(policy(packet) for policy, packet in zip(candidates, oracle_packets))
        assert old_actions == new_actions, (seed, tick)
        old_memories = [policy.memory() for policy in controls]
        new_memories = [policy.memory() for policy in candidates]
        assert old_memories == new_memories, (seed, tick)
        old_result, new_result = frozen.step(old, old_actions), sites.step(new, new_actions)
        assert asdict(old_result.ledger) == asdict(new_result.ledger), (seed, tick)
        assert asdict(old_result.metrics) == asdict(new_result.metrics), (seed, tick)
        assert common_state(old_result.state) == common_state(new_result.state), (seed, tick)
        update_digest(old_digest, trajectory_row(old_result, old_actions, old_memories))
        update_digest(new_digest, trajectory_row(new_result, new_actions, new_memories))
        old, new = old_result.state, new_result.state
    assert old_digest.hexdigest() == new_digest.hexdigest() == G4_TRAJECTORY_SHA256[seed]


def test_new_snapshot_identity_preserves_normalized_v1_payload_digest():
    old = frozen.initialize(seed=90001)
    new = sites.initialize(sites.Config(site_capacities=(40.,) * 16,
                                        initial_site_stocks=(30.,) * 16), seed=90001)
    before, after = frozen.snapshot(old), sites.snapshot(new)
    assert sites.VERSION == after["engine_version"] == "commons-v3-physical-sites-v1"
    assert sites.SNAPSHOT_VERSION == after["version"] == "commons-v3-snapshot-sites-v1"
    assert before["sha256"] != after["sha256"]
    projected = deepcopy(after["state"])
    del projected["config"]["site_capacities"]
    del projected["config"]["initial_site_stocks"]
    assert projected == before["state"]
    assert hashlib.sha256(canonical(projected)).digest() == hashlib.sha256(canonical(before["state"])).digest()
    with pytest.raises(ValueError):
        sites.restore(before)
    with pytest.raises(ValueError):
        frozen.restore(after)


@pytest.mark.parametrize("renewal_law", ["logistic", "additive"])
@pytest.mark.parametrize("contention", ["proportional", "keyed_priority"])
def test_costs_messages_transfers_and_keyed_events_retain_frozen_physics(renewal_law, contention):
    new = world(agent_rows=((0, 0, 8.), (0, 0, 8.), (1, 0, 8.)),
                patch_rows=((0, 0, 4.), (1, 0, 4.)), patch_capacity=10.,
                site_capacities=(10., 10.), initial_site_stocks=(4., 4.),
                weather_amplitude=.1, renewal_law=renewal_law, contention=contention, need=1.)
    old = frozen.WorldState(frozen.Config(**common_state(new)["config"]), new.seed, new.tick,
                            tuple(frozen.AgentState(**asdict(a)) for a in new.agents),
                            tuple(frozen.PatchState(**asdict(p)) for p in new.patches))
    assert sites.Action is frozen.Action
    actions = (frozen.Action(move=(1, 0), harvest=3., transfers=((1, .4),),
                             messages=((1, "paid λ"),), reserve=.1),
               frozen.Action(harvest=3.), frozen.Action(move=(-1, 0), harvest=3.))
    for _ in range(8):
        before, after = frozen.step(old, actions), sites.step(new, actions)
        assert common_state(before.state) == common_state(after.state)
        assert asdict(before.ledger) == asdict(after.ledger)
        assert asdict(before.metrics) == asdict(after.metrics)
        assert all(row.weather_event_id.startswith("commons-v3-physical-v1/")
                   for row in after.ledger.patches)
        assert_conserved(after)
        old, new = before.state, after.state
        actions = (frozen.Action(harvest=3., messages=((1, "paid λ"),), reserve=.1),
                   frozen.Action(harvest=3.), frozen.Action(harvest=3.))


def test_per_site_initial_stocks_override_scalars_without_changing_geometry():
    config = sites.Config(n_patches=3, site_capacities=(10., 20., 80.),
                          initial_site_stocks=(3., 15., 72.))
    state = sites.initialize(config, 90001)
    assert [p.stock for p in state.patches] == [3., 15., 72.]
    assert [sites.site_capacity(config, i) for i in range(3)] == [10., 20., 80.]
    assert [sites.initial_site_stock(config, i) for i in range(3)] == [3., 15., 72.]
    baseline = sites.initialize(sites.Config(n_patches=3), 90001)
    assert [(p.x, p.y) for p in state.patches] == [(p.x, p.y) for p in baseline.patches]
    assert [(a.x, a.y) for a in state.agents] == [(a.x, a.y) for a in baseline.agents]


def test_empty_arrays_use_scalar_fallbacks_and_explicit_stocks_can_use_scalar_capacity():
    config = sites.Config(n_patches=2)
    assert [sites.site_capacity(config, i) for i in range(2)] == [40., 40.]
    assert [sites.initial_site_stock(config, i) for i in range(2)] == [30., 30.]
    explicit = replace(config, initial_site_stocks=(0., 39.))
    assert [p.stock for p in sites.initialize(explicit).patches] == [0., 39.]


def test_heterogeneous_growth_uses_local_capacity_and_clips_above_global_scalar():
    state = world(patch_rows=((0, 0, 4.), (2, 2, 4.), (4, 4, 79.99)),
                  site_capacities=(10., 20., 80.), initial_site_stocks=(4., 4., 79.99))
    result = sites.step(state, (sites.Action(),))
    rows = result.ledger.patches
    assert rows[0].growth == pytest.approx(.24 * 4. * (1. - 4. / 10.) + .02)
    assert rows[1].growth == pytest.approx(.24 * 4. * (1. - 4. / 20.) + .02)
    assert rows[0].growth < rows[1].growth
    assert rows[2].stock_after == 80.
    assert rows[2].growth == pytest.approx(80. - 79.99)
    assert rows[2].growth_waste > 0.
    assert all(0 <= p.stock <= sites.site_capacity(state.config, p.id) for p in result.state.patches)
    assert_conserved(result)


def test_growth_follows_extraction_at_each_sites_capacity_and_empty_site_recovers():
    state = world(agent_rows=((0, 0, 2.), (2, 2, 2.)),
                  patch_rows=((0, 0, 4.), (2, 2, 4.), (4, 4, 0.)),
                  site_capacities=(10., 20., 80.), initial_site_stocks=(4., 4., 0.))
    result = sites.step(state, (sites.Action(harvest=2.), sites.Action(harvest=2.)))
    assert [p.stock_after_harvest for p in result.ledger.patches] == [2., 2., 0.]
    assert [p.growth for p in result.ledger.patches] == pytest.approx([.404, .452, .02])
    assert_conserved(result)


@pytest.mark.parametrize("site_id", [-1, 2, True, .5])
def test_capacity_and_initial_stock_helpers_require_canonical_site_ids(site_id):
    config = sites.Config(n_patches=2)
    for helper in (sites.site_capacity, sites.initial_site_stock):
        with pytest.raises(ValueError):
            helper(config, site_id)


@pytest.mark.parametrize("change", [
    {"site_capacities": []}, {"site_capacities": [10., 20.]},
    {"initial_site_stocks": []}, {"initial_site_stocks": [3., 4.]},
    {"site_capacities": (10.,)}, {"site_capacities": (10., 20., 30.)},
    {"initial_site_stocks": (3.,)}, {"initial_site_stocks": (3., 4., 5.)},
    {"site_capacities": (0., 20.)}, {"site_capacities": (-1., 20.)},
    {"site_capacities": (True, 20.)}, {"site_capacities": (float("nan"), 20.)},
    {"site_capacities": (float("inf"), 20.)}, {"site_capacities": (1e6 + 1, 20.)},
    {"initial_site_stocks": (-1., 4.)}, {"initial_site_stocks": (True, 4.)},
    {"initial_site_stocks": (float("nan"), 4.)},
    {"initial_site_stocks": (float("inf"), 4.)},
    {"initial_site_stocks": (1e6 + 1, 4.)},
    {"site_capacities": (3., 20.)},
    {"site_capacities": (10., 20.), "initial_site_stocks": (4., 20.1)},
    {"need": float("nan")}, {"weather_amplitude": float("inf")},
])
def test_config_rejects_mutable_wrong_length_nonfinite_or_out_of_bounds_arrays(change):
    with pytest.raises(ValueError):
        sites.Config(n_patches=2, initial_patch_stock=4., **change)


def test_state_bounds_use_each_sites_capacity_not_scalar_capacity():
    state = world(patch_rows=((0, 0, 4.), (4, 4, 60.)),
                  site_capacities=(10., 80.), initial_site_stocks=(4., 60.))
    sites.snapshot(state)
    invalid = replace(state, patches=(replace(state.patches[0], stock=10.1), state.patches[1]))
    for call in (lambda: sites.observe(invalid, 0), lambda: sites.snapshot(invalid),
                 lambda: sites.step(invalid, (sites.Action(),))):
        with pytest.raises(ValueError):
            call()


def test_json_roundtrip_and_exact_continuation_preserve_heterogeneity_and_pending_messages():
    state = world(agent_rows=((0, 0, 8.), (1, 0, 8.)),
                  patch_rows=((0, 0, 4.), (4, 4, 60.)),
                  site_capacities=(10., 80.), initial_site_stocks=(4., 60.),
                  weather_amplitude=.1, need=1.)
    state = sites.step(state, (sites.Action(harvest=1., messages=((1, "remember λ"),)),
                               sites.Action())).state
    encoded = json.loads(json.dumps(sites.snapshot(state)))
    assert encoded["state"]["config"]["site_capacities"] == [10., 80.]
    assert encoded["state"]["config"]["initial_site_stocks"] == [4., 60.]
    assert encoded["state"]["messages"][0]["text"] == "remember λ"
    restored = sites.restore(encoded)
    assert restored == state
    assert type(restored.config.site_capacities) is tuple
    assert type(restored.config.initial_site_stocks) is tuple
    assert sites.observe(restored, 1)["messages"][0]["text"] == "remember λ"
    for tick in range(8):
        actions = (sites.Action(harvest=1., messages=((1, "next"),)),
                   sites.Action(move=(-1, 0) if tick == 0 else (0, 0), harvest=1.))
        left, right = sites.step(state, actions), sites.step(restored, actions)
        assert left == right
        assert sites.snapshot(left.state) == sites.snapshot(right.state)
        state, restored = left.state, right.state


@pytest.mark.parametrize("mutation", ["digest", "version", "engine", "missing_array", "tuple_array",
                                     "wrong_length", "nonfinite", "capacity_below_stock", "extra_field"])
def test_snapshot_rejects_wrong_schema_and_resigned_invalid_site_state(mutation):
    state = world(patch_rows=((0, 0, 4.), (4, 4, 60.)),
                  site_capacities=(10., 80.), initial_site_stocks=(4., 60.))
    bad = sites.snapshot(state)
    config = bad["state"]["config"]
    if mutation == "digest":
        bad["sha256"] = "0" * 64
    elif mutation == "version":
        bad["version"] = frozen.SNAPSHOT_VERSION
    elif mutation == "engine":
        bad["engine_version"] = frozen.VERSION
    elif mutation == "missing_array":
        del config["site_capacities"]
    elif mutation == "tuple_array":
        config["site_capacities"] = (10., 80.)
    elif mutation == "wrong_length":
        config["site_capacities"] = [10.]
    elif mutation == "nonfinite":
        config["site_capacities"][0] = float("nan")
    elif mutation == "capacity_below_stock":
        config["site_capacities"][1] = 50.
    else:
        config["evaluator_condition"] = "wide"
    if mutation not in ("digest", "nonfinite"):
        bad["sha256"] = hashlib.sha256(canonical({key: bad[key]
                                                  for key in ("version", "engine_version", "state")})).hexdigest()
    with pytest.raises(ValueError):
        sites.restore(bad)


def test_observation_contract_declares_law_and_prior_but_no_realized_hidden_state():
    state = world(agent_rows=((0, 0, 2.), (0, 0, 5.), (1, 0, 7.), (4, 4, 9.)),
                  patch_rows=((0, 0, 4.), (4, 4, 60.)),
                  site_capacities=(10., 80.), initial_site_stocks=(4., 60.), weather_amplitude=.1)
    packet = sites.observe(state, 0)
    assert set(packet) == {"version", "observation_version", "tick", "self", "ecology", "sites", "peers", "messages"}
    assert packet["observation_version"] == "commons-v3-observation-v2"
    assert packet["ecology"] == {
        "renewal_law": "logistic", "renewal_rate": .24, "recovery": .02,
        "weather_multiplier": {"distribution": "uniform", "low": .9, "high": 1.1},
        "initial_stock_fraction": {"distribution": "uniform", "low": .3, "high": .9,
                                   "independent_by_site": True},
        "capacity_prior": {"distribution": "log_uniform", "low": 8., "high": 100.},
    }
    assert packet["sites"] == [{"id": 0, "x": 0, "y": 0, "stock": 4., "peer_count": 2}]
    assert packet["peers"] == [{"id": 1, "x": 0, "y": 0}, {"id": 2, "x": 1, "y": 0}]
    assert packet["self"]["inventory"] == 2.
    assert set(packet["self"]) == {"id", "x", "y", "inventory", "width", "height", "need",
                                   "inventory_capacity", "max_harvest", "sensing_radius", "movement_cost",
                                   "harvest_cost_per_unit", "message_byte_cost", "max_message_bytes", "max_messages"}


def test_hidden_capacity_peer_inventory_seed_remote_stock_and_ledgers_do_not_change_packet():
    state = world(agent_rows=((0, 0, 2.), (1, 0, 3.), (4, 4, 4.)),
                  patch_rows=((0, 0, 4.), (4, 4, 60.)),
                  site_capacities=(10., 80.), initial_site_stocks=(4., 60.), weather_amplitude=.1)
    packet = sites.observe(state, 0)
    other = replace(state, seed=8091,
                    config=replace(state.config, site_capacities=(20., 90.), initial_site_stocks=(5., 70.),
                                   patch_capacity=100., initial_patch_stock=12., terminal_wealth_weight=.2),
                    agents=(replace(state.agents[0], consumption=123., harvested=99., shortfall=30.),
                            replace(state.agents[1], inventory=19., harvested=90.),
                            replace(state.agents[2], inventory=17., x=4, y=3)),
                    patches=(replace(state.patches[0], cumulative_growth=80., cumulative_harvest=30.),
                             replace(state.patches[1], stock=85.)))
    assert sites.observe(other, 0) == packet
    # Declared laws remain observable even while their realizations stay hidden.
    changed_law = replace(state, config=replace(state.config, renewal_rate=.3))
    assert sites.observe(changed_law, 0)["ecology"]["renewal_rate"] == .3


def test_bulk_observations_are_equivalent_detached_and_do_not_share_ecology_or_site_dicts():
    state = world(agent_rows=((0, 0, 2.), (0, 0, 3.)), site_capacities=(10.,))
    packets = sites.observations(state)
    assert packets == tuple(sites.observe(state, i) for i in range(2))
    originals = deepcopy(packets)
    packets[0]["ecology"]["capacity_prior"]["low"] = 999.
    packets[0]["sites"][0]["stock"] = 999.
    packets[0]["self"]["inventory"] = 999.
    assert packets[1] == originals[1]
    assert sites.observations(state) == originals
