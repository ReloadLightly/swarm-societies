"""Small synthetic recorder checks; no prospective qualification seeds run."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import statistics

import pytest

from swarm_societies.commons_v3 import qualification_episode_v1 as recorder
from swarm_societies.commons_v3.engine import Config, initialize, observations, restore, step
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy


def synthetic_case(horizon=16, **changes):
    cfg = Config(width=4, height=4, n_agents=4, n_patches=2,
                 need=1.4, initial_patch_stock=40., renewal_rate=.12)
    cfg = replace(cfg, **changes)
    return {"id": "synthetic-recorder", "seed": 17, "horizon": horizon, "config": asdict(cfg)}


def control():
    return {"id": "selected", "parameters": {"reserve_ticks": 4, "stock_floor_fraction": .5, "route_mode": "nearest"}}


@pytest.mark.parametrize("aggressive_ids", [[], [1], [0, 2], [0, 1, 2, 3]])
def test_raw_columns_reconstruct_population_cohorts_and_local_access(aggressive_ids):
    case = synthetic_case()
    record = recorder.record_episode(case, control(), aggressive_ids, spatial=True)
    cfg, ticks = case["config"], record["trajectory"]
    assert record["aggressive_count"] == len(aggressive_ids)
    assert record["aggressive_ids"] == aggressive_ids
    sites = [(row["x"], row["y"]) for row in record["site_layout"]]
    site_cells = set(sites)
    cohort_ids = {"normal": [i for i in range(cfg["n_agents"]) if i not in aggressive_ids],
                  "aggressive": aggressive_ids}
    for row in ticks:
        positions = [tuple(position) for position in row["agent_positions"]]
        assert all(len(row["agent_" + field]) == cfg["n_agents"] for field in recorder.AGENT_TICK_FIELDS)
        assert row["consumption"] == pytest.approx(sum(row["agent_consumption"]), abs=1e-12)
        assert row["shortfall"] == pytest.approx(sum(row["agent_shortfall"]), abs=1e-12)
        assert row["reserves"] == pytest.approx(sum(row["agent_inventory"]), abs=1e-12)
        assert row["stock"] == pytest.approx(sum(row["site_stock"]), abs=1e-12)
        off_site = [i for i, position in enumerate(positions) if position not in site_cells]
        assert row["off_site_agents"] == len(off_site)
        assert row["hungry_off_site_agents"] == sum(row["agent_shortfall"][i] > 0 for i in off_site)
        assert row["mean_known_sites"] == statistics.mean(row["agent_known_sites"])
        assert row["depleted_patches"] == sum(stock < .1 * cfg["patch_capacity"] for stock in row["site_stock"])
        unoccupied = sum(stock for point, stock in zip(sites, row["site_stock"]) if point not in positions)
        assert row["unoccupied_stock_fraction"] == pytest.approx(unoccupied / (cfg["n_patches"] * cfg["patch_capacity"]), abs=1e-12)
        for kind, ids in cohort_ids.items():
            cohort = row["cohorts"][kind]
            assert cohort["n"] == len(ids)
            for field in ("consumption", "shortfall", "inventory"):
                assert cohort[field] == sum(row["agent_" + field][i] for i in ids)
        assert row["consumption"] == pytest.approx(sum(row["cohorts"][kind]["consumption"] for kind in recorder.COHORTS), abs=1e-12)
    for agent in record["agents"]:
        identity = agent["id"]
        for field in ("consumption", "shortfall", "waste"):
            # Match the actual chronological accumulation; Python's sum may
            # use compensated accumulation rather than sequential float adds.
            accumulated = 0.
            for tick in ticks:
                accumulated += tick["agent_" + field][identity]
            assert agent[field] == accumulated
        assert agent["terminal_inventory"] == ticks[-1]["agent_inventory"][identity]
        assert agent["terminal_known_sites"] == ticks[-1]["agent_known_sites"][identity]
        for weight in recorder.WEIGHTS:
            assert agent["utility"][str(weight)] == (agent["consumption"] + weight * agent["terminal_inventory"]) / case["horizon"]
    for kind, ids in cohort_ids.items():
        cohort = record["cohorts"][kind]
        assert cohort["n"] == len(ids)
        assert cohort["consumption"] == sum(record["agents"][i]["consumption"] for i in ids)
        if ids:
            assert cohort["consumption_per_tick"] == statistics.mean(record["agents"][i]["consumption_per_tick"] for i in ids)
        else:
            assert cohort["consumption_per_tick"] is None
            assert cohort["terminal_inventory"] is None
            assert all(value is None for value in cohort["utility"].values())
    late = ticks[-max(1, case["horizon"] // 4):]
    assert record["summary"]["late_stock_fraction"] == statistics.mean(t["stock"] / (cfg["n_patches"] * cfg["patch_capacity"]) for t in late)
    assert record["summary"]["late_depleted_patch_time_fraction"] == sum(t["depleted_patches"] for t in late) / (len(late) * cfg["n_patches"])
    assert record["summary"]["late_consumption_per_agent_tick"] == pytest.approx(
        sum(t["consumption"] for t in late) / (len(late) * cfg["n_agents"]), abs=1e-12)
    quarter3 = ticks[case["horizon"] // 2:-len(late)]
    assert record["summary"]["quarter3_consumption_per_agent_tick"] == pytest.approx(
        sum(t["consumption"] for t in quarter3) / (len(quarter3) * cfg["n_agents"]), abs=1e-12)
    assert record["summary"]["max_unaffordable_known_returns"] == 0
    assert record["summary"]["max_tick_waste"] <= recorder.WASTE_ABSOLUTE_TOLERANCE
    assert record["summary"]["max_relative_ledger_residual"] <= recorder.LEDGER_RELATIVE_TOLERANCE


def test_deterministic_bindings_canonical_mask_and_input_independence():
    case, selected = synthetic_case(), control()
    original = deepcopy((case, selected))
    first = recorder.record_episode(case, selected, [3, 1], spatial=True)
    second = recorder.record_episode(case, selected, [1, 3], spatial=True)
    assert recorder.canonical(first) == recorder.canonical(second)
    assert (case, selected) == original
    bindings = {key: first[key] for key in ("case", "control", "aggressive_ids")}
    assert first["input_sha256"] == hashlib.sha256(recorder.canonical(bindings)).hexdigest()
    first["case"]["config"]["need"] = 999
    first["control"]["parameters"]["reserve_ticks"] = 0
    assert (case, selected) == original
    assert second["case"] == case


def test_only_engine_observations_reach_policies_and_physics_matches_manual_rollout(monkeypatch):
    case, selected, aggressive_ids = synthetic_case(horizon=9), control(), {1, 3}
    cfg = Config(**case["config"])
    manual = initialize(cfg, case["seed"])
    policies = [ForagerPolicy(**selected["parameters"], aggressive=i in aggressive_ids) for i in range(cfg.n_agents)]
    expected_packets, expected_states = [], []
    for _ in range(case["horizon"]):
        packets = observations(manual)
        expected_packets.extend(deepcopy(packets))
        actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        result = step(manual, actions)
        manual = result.state
        expected_states.append(manual)
    observed_packets, constructor_parameters = [], []
    class ObservingPolicy:
        def __init__(self, **parameters):
            constructor_parameters.append(deepcopy(parameters))
            self.inner = ForagerPolicy(**parameters)

        @property
        def sites(self):
            return self.inner.sites

        def __call__(self, packet):
            observed_packets.append(deepcopy(packet))
            return self.inner(packet)

    monkeypatch.setattr(recorder, "ForagerPolicy", ObservingPolicy)
    saved = recorder.record_episode(case, selected, aggressive_ids)
    assert observed_packets == expected_packets
    assert constructor_parameters == [{**selected["parameters"], "aggressive": i in aggressive_ids} for i in range(cfg.n_agents)]
    for tick, state in zip(saved["trajectory"], expected_states):
        assert tick["agent_positions"] == [[a.x, a.y] for a in state.agents]
        assert tick["agent_inventory"] == [a.inventory for a in state.agents]
        assert tick["site_stock"] == [p.stock for p in state.patches]
    assert len(observed_packets) == case["horizon"] * cfg.n_agents


@pytest.mark.parametrize("horizon,expected_ticks", [(1, [0, 1]), (2, [0, 1, 2]), (9, [0, 2, 4, 9])])
def test_snapshot_continuation_has_real_future_steps_and_spatial_sampling_is_passive(horizon, expected_ticks):
    case = synthetic_case(horizon=horizon)
    ordinary = recorder.record_episode(case, control(), [1])
    spatial = recorder.record_episode(case, control(), [1], spatial=True)
    assert ordinary["spatial_frames"] == []
    assert [frame["tick"] for frame in spatial["spatial_frames"]] == expected_ticks
    assert ordinary["final_state_sha256"] == spatial["final_state_sha256"]
    assert ordinary["weather_sha256"] == spatial["weather_sha256"]
    assert ordinary["trajectory"] == spatial["trajectory"]
    assert ordinary["checkpoint_continuation_checked"] is False
    assert ordinary["checkpoint_continuation"]["verified"] is False
    assert ordinary["checkpoint_continuation"]["checkpoint_tick"] is None
    assert ordinary["checkpoint_continuation"]["future_ticks_checked"] == 0
    assert spatial["checkpoint_continuation_checked"] is True
    assert spatial["checkpoint_continuation"]["verified"] is True
    assert spatial["checkpoint_continuation"]["checkpoint_tick"] == horizon // 2
    assert spatial["checkpoint_continuation"]["future_ticks_checked"] == horizon - horizon // 2
    assert ordinary["late_window"] == {"start_tick": horizon - max(1, horizon // 4) + 1,
                                       "end_tick": horizon, "ticks": max(1, horizon // 4)}
    if horizon < 4:
        assert ordinary["quarter3_window"]["ticks"] == 0
        assert ordinary["summary"]["quarter3_consumption_per_agent_tick"] is None


def test_snapshot_continuation_checks_ledgers_as_well_as_states(monkeypatch):
    restored_states = []
    def remember_restore(checkpoint):
        state = restore(checkpoint)
        restored_states.append(state)
        return state

    def changed_replay_ledger(state, actions):
        result = step(state, actions)
        if any(state is saved for saved in restored_states):
            restored_states.append(result.state)
            return replace(result, ledger=replace(result.ledger, residual=result.ledger.residual + 1.))
        return result

    monkeypatch.setattr(recorder, "restore", remember_restore)
    monkeypatch.setattr(recorder, "step", changed_replay_ledger)
    with pytest.raises(ValueError, match="same committed actions"):
        recorder.record_episode(synthetic_case(horizon=6), control(), [], spatial=True)


def test_nonspatial_episode_executes_only_the_declared_physical_ticks(monkeypatch):
    calls = []
    def counted_step(state, actions):
        calls.append(state.tick)
        return step(state, actions)

    monkeypatch.setattr(recorder, "step", counted_step)
    recorder.record_episode(synthetic_case(horizon=9), control(), [1])
    assert calls == list(range(9))


@pytest.mark.parametrize("ids", [[], list(range(24))])
def test_full_population_endpoint_masks(ids):
    saved = recorder.record_episode(synthetic_case(horizon=4, n_agents=24, n_patches=4), control(), ids)
    assert len(saved["agents"]) == 24
    assert saved["cohorts"]["aggressive"]["n"] == len(ids)
    assert saved["cohorts"]["normal"]["n"] == 24 - len(ids)


def test_latter_half_persistent_depletion_and_prefix_256_scalars():
    depleted = recorder.record_episode(synthetic_case(horizon=8, initial_patch_stock=.1,
        renewal_rate=0., recovery=0.), control(), [0, 1, 2, 3])
    assert depleted["summary"]["persistent_depletion_longest_ticks"] == 4
    assert depleted["summary"]["persistent_depletion_threshold_ticks"] == 1
    assert all(depleted["summary"][key] is None for key in (
        "prefix256_consumption_per_agent_tick", "prefix256_late_consumption_per_agent_tick",
        "prefix256_terminal_stock_fraction"))
    case = synthetic_case(horizon=260, n_agents=2, n_patches=1, initial_patch_stock=12., need=.8)
    saved = recorder.record_episode(case, control(), [1])
    rows = saved["trajectory"]
    summary = saved["summary"]
    assert summary["prefix256_consumption_per_agent_tick"] == pytest.approx(
        sum(row["consumption"] for row in rows[:256]) / (256 * 2), abs=1e-12)
    assert summary["prefix256_late_consumption_per_agent_tick"] == pytest.approx(
        sum(row["consumption"] for row in rows[192:256]) / (64 * 2), abs=1e-12)
    assert summary["prefix256_terminal_stock_fraction"] == rows[255]["stock"] / case["config"]["patch_capacity"]
    runs, length = [], 0
    for row in rows[130:]:
        length = length + 1 if 2 * row["depleted_patches"] >= case["config"]["n_patches"] else 0
        runs.append(length)
    assert summary["persistent_depletion_longest_ticks"] == max(runs)


def test_control_identity_is_bound_without_changing_the_given_policy_parameters():
    selected = control()
    fixed = {**selected, "id": "fixed_floor"}
    left = recorder.record_episode(synthetic_case(), selected, [1])
    right = recorder.record_episode(synthetic_case(), fixed, [1])
    assert left["input_sha256"] != right["input_sha256"]
    assert left["trajectory"] == right["trajectory"]
    assert left["final_state_sha256"] == right["final_state_sha256"]


@pytest.mark.parametrize("field,match", [("residual", "accounting failed"), ("waste", "wasted extracted")])
def test_material_invariant_failure_stops_recording(monkeypatch, field, match):
    def changed_ledger(state, actions):
        result = step(state, actions)
        return replace(result, ledger=replace(result.ledger, **{field: 1.}))

    monkeypatch.setattr(recorder, "step", changed_ledger)
    with pytest.raises(ValueError, match=match):
        recorder.record_episode(synthetic_case(horizon=2), control(), [])


@pytest.mark.parametrize("ids", [[0, 0], [-1], [4], [True], [1.0], None])
def test_invalid_masks_fail_before_physics(monkeypatch, ids):
    def no_initialization(*args, **kwargs):
        pytest.fail("invalid input reached the physical initializer")

    monkeypatch.setattr(recorder, "initialize", no_initialization)
    with pytest.raises(ValueError, match="aggressive_ids"):
        recorder.record_episode(synthetic_case(), control(), ids)


def test_invalid_control_and_case_fail_before_physics(monkeypatch):
    def no_initialization(*args, **kwargs):
        pytest.fail("invalid input reached the physical initializer")

    monkeypatch.setattr(recorder, "initialize", no_initialization)
    invalid_controls = [{"id": "untrusted", "parameters": control()["parameters"]},
                        {**control(), "source": "arbitrary code"},
                        {"id": "selected", "parameters": {**control()["parameters"], "seed": 1}},
                        {"id": "selected", "parameters": {**control()["parameters"], "reserve_ticks": 3}}]
    for value in invalid_controls:
        with pytest.raises(ValueError):
            recorder.record_episode(synthetic_case(), value, [])
    for patch in ({"horizon": 0}, {"horizon": True}, {"seed": False}, {"id": ""}):
        with pytest.raises(ValueError):
            recorder.record_episode({**synthetic_case(), **patch}, control(), [])
