"""Independent regressions for the prospective return-fuel arithmetic repair."""
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import json
import math

import pytest

from swarm_societies.commons_v3 import development as development_v1
from swarm_societies.commons_v3 import development_v2 as dev
from swarm_societies.commons_v3.engine import (
    AgentState, Config, PatchState, WorldState, initialize, observe, observations, step,
)
from swarm_societies.commons_v3.policies import LocalPolicy as PolicyV1
from swarm_societies.commons_v3.policies_v2 import LocalPolicy


def empty_world(*, seed=17, inventory=.08, cost=.02, need=1., capacity=80.):
    cfg = Config(width=11, height=11, n_agents=1, n_patches=1,
                 initial_inventory=inventory, inventory_capacity=capacity,
                 movement_cost=cost, need=need, initial_patch_stock=0.,
                 renewal_rate=0., recovery=0., weather_amplitude=0.)
    return WorldState(cfg, seed, 0, (AgentState(0, 5, 5, inventory),),
                      (PatchState(0, 5, 5, 0.),))


def home_distance(agent, policy):
    return min(abs(agent.x - x) + abs(agent.y - y) for x, y in policy.sites.values())


@pytest.mark.parametrize("mode", ["greedy", "restraint"])
def test_historical_two_step_float_trap_is_prevented_without_free_fuel(mode):
    original = empty_world()
    old, old_policy = original, PolicyV1(mode)
    for _ in range(2):
        old = step(old, (old_policy(observe(old, 0)),)).state
    assert (old.agents[0].x, old.agents[0].y) == (5, 3)
    assert old.agents[0].inventory == .039999999999999994
    assert old.agents[0].inventory < 2 * original.config.movement_cost
    for _ in range(4):
        action = old_policy(observe(old, 0))
        assert action.move == (0, 0)
        old = step(old, (action,)).state

    state, policy = original, LocalPolicy(mode)
    positions = []
    for _ in range(12):
        action = policy(observe(state, 0))
        result = step(state, (action,))
        state = result.state
        actor = state.agents[0]
        positions.append((actor.x, actor.y))
        # Ordinary >= is deliberate: an approximate comparison hid the v1 bug.
        assert actor.inventory >= original.config.movement_cost * home_distance(actor, policy)
        assert actor.inventory + actor.movement_cost + actor.consumption == pytest.approx(.08, abs=1e-15)
        assert result.ledger.agents[0].movement_cost == (.02 if action.move != (0, 0) else 0.)
    assert positions[0] != (5, 5)
    assert (5, 5) in positions[1:]


@pytest.mark.parametrize("mode", ["greedy", "restraint"])
@pytest.mark.parametrize("seed", [0, 17, 61004])
@pytest.mark.parametrize("cost", [0., .00001, .02, .3])
def test_seeded_scouting_keeps_return_path_affordable_after_consumption(mode, seed, cost):
    cfg = replace(empty_world(inventory=max(.08, 4 * cost), cost=cost).config, n_agents=4)
    # Seed-shuffled identities begin on and beside the known site, so the
    # deterministic actor-specific navigation follows different actual paths.
    state = initialize(cfg, seed=seed)
    policies = [LocalPolicy(mode) for _ in state.agents]
    for _ in range(72):
        actions = tuple(policy(packet) for policy, packet in zip(policies, observations(state)))
        for before, policy, action in zip(state.agents, policies, actions):
            if home_distance(before, policy):
                assert action.move != (0, 0), "an actor with a protected return budget must not strand offsite"
            if action.move != (0, 0):
                assert before.inventory >= cost
            assert action.messages == action.transfers == ()
        result = step(state, actions)
        state = result.state
        for after, policy in zip(state.agents, policies):
            assert after.inventory >= cost * home_distance(after, policy)
        assert result.ledger.waste == 0.
        assert abs(result.ledger.residual) < 1e-12


@pytest.mark.parametrize("cost", [.00001, .02, .3, 2.])
@pytest.mark.parametrize("side", [-1, 0, 1])
def test_hypothetical_packet_uses_strict_prospective_budget_boundary(cost, side):
    state = empty_world(inventory=4 * cost, cost=cost)
    policy = LocalPolicy("greedy")
    policy(observe(state, 0))  # The remembered coordinate was legally observed.
    threshold = 2 * cost + 1e-9 * max(1., 2 * cost)
    budget = math.nextafter(threshold, -math.inf if side < 0 else math.inf) if side else threshold
    state = replace(state, tick=1, agents=(replace(state.agents[0], x=7, inventory=budget),))
    packet = observe(state, 0)
    assert packet["sites"] == []
    action = policy(packet)
    if side < 0:
        assert action.move == (0, 0)
    else:
        # The westward step is the only one that fits the return-fuel budget.
        assert action.move == (-1, 0)
        result = step(state, (action,))
        assert result.ledger.movement_cost == cost
        assert result.state.agents[0].inventory >= cost


def test_numerical_reserve_is_paid_through_foregone_consumption_and_capped():
    state = empty_world(inventory=2., need=10.)
    action = LocalPolicy("greedy")(observe(state, 0))
    result = step(state, (action,))
    assert action.reserve == .08 + 8e-9
    assert result.state.agents[0].inventory > .08
    assert result.ledger.consumption < 1.9
    assert result.ledger.consumption + result.ledger.movement_cost + result.ledger.inventory_after == pytest.approx(2.)
    small = empty_world(inventory=.03, capacity=.03)
    action = LocalPolicy("greedy")(observe(small, 0))
    assert action.reserve == .03
    assert step(small, (action,)).state.agents[0].inventory == .03


@pytest.mark.parametrize("mode", ["greedy", "restraint"])
@pytest.mark.parametrize("inventory", [79., 79.999991, 80.])
def test_storage_capacity_is_respected_before_this_ticks_consumption(mode, inventory):
    state = empty_world(inventory=inventory, need=0.)
    state = replace(state, patches=(replace(state.patches[0], stock=40.),))
    action = LocalPolicy(mode)(observe(state, 0))
    assert action.move == (0, 0)
    assert action.harvest == pytest.approx((80. - inventory) / .98)
    result = step(state, (action,))
    assert result.ledger.waste <= 1e-13
    assert result.state.agents[0].inventory == pytest.approx(80.)


def test_half_capacity_and_colocated_headcount_rule_is_unchanged():
    state = empty_world(inventory=2., need=0.)
    state = replace(state, config=replace(state.config, n_agents=2),
                    agents=(state.agents[0], replace(state.agents[0], id=1)),
                    patches=(replace(state.patches[0], stock=21.),))
    actions = tuple(LocalPolicy("restraint")(observe(state, i)) for i in range(2))
    assert [action.harvest for action in actions] == [.5, .5]
    assert step(state, actions).ledger.patches[0].stock_after_harvest == 20.


def test_policy_uses_only_local_packets_and_its_own_observed_history():
    state = empty_world()
    state = replace(state, config=replace(state.config, n_agents=2, n_patches=2),
                    agents=state.agents + (AgentState(1, 10, 10, 7.),),
                    patches=state.patches + (PatchState(1, 10, 10, 30.),))
    hidden_changed = replace(state, seed=908, config=replace(state.config, renewal_rate=.7, weather_amplitude=.4),
                             agents=(state.agents[0], replace(state.agents[1], inventory=69.)),
                             patches=(state.patches[0], replace(state.patches[1], stock=1.)))
    packets = [observe(world, 0) for world in (state, hidden_changed)]
    assert packets[0] == packets[1]
    before = deepcopy(packets)
    policies = [LocalPolicy("greedy"), LocalPolicy("greedy")]
    assert policies[0](packets[0]) == policies[1](packets[1])
    assert packets == before
    assert policies[0].memory() == policies[1].memory()
    assert policies[0].memory() == {"version": "commons-v3-local-policy-v2", "mode": "greedy",
                                     "sites": [[0, 5, 5]], "visits": [[5, 5, 1]]}


def tiny_design():
    specification = dev.design()
    cfg = Config(width=3, height=3, n_agents=2, n_patches=1, need=.3,
                 initial_patch_stock=30., weather_amplitude=.1)
    specification["cases"] = [{"id": "tiny", "panel": "grid", "seed": 900123,
                               "focal_id": 0, "horizon": 8, "config": asdict(cfg)}]
    specification["reference_frames_case"] = "tiny"
    return specification


@pytest.fixture
def tiny_bank(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank-v2"
    dev.prepare(output)
    dev.run(output)
    return output


def test_v2_preserves_full_v1_physical_bank_and_outcome_definitions():
    previous, current = development_v1.design(), dev.design()
    assert current["version"] != previous["version"]
    assert current["preceding_panel"] == previous["version"]
    for key in ("cases", "conditions", "wealth_weights", "depletion_threshold_capacity_fraction",
                "late_window_fraction", "ledger_relative_tolerance", "reference_frames_case",
                "experimental_model_calls", "evolutionary_runs"):
        assert dev.canonical(current[key]) == dev.canonical(previous[key])
    assert len(current["cases"]) == 56


def test_tiny_v2_bank_pins_sources_pairs_weather_and_replays_exactly(tiny_bank):
    receipt = dev.verify(tiny_bank)
    assert receipt["verified"] is receipt["semantic_replay"] is True
    assert receipt["cases"] == 1 and receipt["episodes"] == 4
    record = dev.read_case(tiny_bank / "cases/tiny.json.gz")
    assert len({row["weather_sha256"] for row in record["episodes"]}) == 1
    assert all(row["checkpoint_continuation_checked"] for row in record["episodes"])
    assert all(row["summary"]["max_unaffordable_known_returns"] == 0 for row in record["episodes"])
    assert all(tick["unaffordable_known_returns"] == 0
               for row in record["episodes"] for tick in row["trajectory"])
    assert dev.canonical(record) == dev.canonical(dev.run_case(record["case"], dev.design()))
    pins = json.loads((tiny_bank / "sources.json").read_text())
    assert "swarm_societies/commons_v3/policies_v2.py" in pins
    assert "swarm_societies/commons_v3/engine.py" in pins
    for name, digest in pins.items():
        assert dev.sha(tiny_bank / "sources" / name) == dev.sha(dev.ROOT / name) == digest
    with pytest.raises(FileExistsError, match="completed"):
        dev.run(tiny_bank)


def test_v2_episode_guard_detects_the_historical_policy_failure(monkeypatch):
    case = {"id": "fuel-trap", "panel": "grid", "seed": 17, "focal_id": 0,
            "horizon": 8, "config": asdict(empty_world().config)}
    monkeypatch.setattr(dev, "LocalPolicy", PolicyV1)
    with pytest.raises(ValueError, match="prospective return-fuel invariant"):
        dev.episode(case, "greedy")


@pytest.mark.parametrize("target", ["case", "summary", "manifest"])
def test_rehashed_boolean_tampering_fails_exact_v2_replay(tiny_bank, target):
    manifest_path = tiny_bank / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if target == "case":
        name = "cases/tiny.json.gz"
        value = dev.read_case(tiny_bank / name)
        assert value["episodes"][0]["trajectory"][0]["waste"] == 0.
        value["episodes"][0]["trajectory"][0]["waste"] = False
        with gzip.open(tiny_bank / name, "wb") as stream:
            stream.write(dev.canonical(value))
        manifest["artifacts_sha256"][name] = dev.sha(tiny_bank / name)
    elif target == "summary":
        name = "summary.json"
        value = json.loads((tiny_bank / name).read_text())
        assert value["experimental_model_calls"] == 0
        value["experimental_model_calls"] = False
        (tiny_bank / name).write_bytes(dev.canonical(value))
        manifest["artifacts_sha256"][name] = dev.sha(tiny_bank / name)
    else:
        manifest["cases"] = True
    manifest_path.write_bytes(dev.canonical(manifest))
    with pytest.raises(ValueError, match="semantic replay|aggregate differs|inventory"):
        dev.verify(tiny_bank)


def test_v2_failure_stays_retained_and_cannot_be_retried_into_completion(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank-v2"
    dev.prepare(output)
    def fail(*_):
        raise ArithmeticError("injected policy arithmetic failure")
    monkeypatch.setattr(dev, "run_case", fail)
    with pytest.raises(ArithmeticError):
        dev.run(output)
    failure = (output / "tiny-failure.json").read_bytes()
    assert not (output / "manifest.json").exists()
    with pytest.raises(FileExistsError, match="failed"):
        dev.run(output)
    assert (output / "tiny-failure.json").read_bytes() == failure
