from dataclasses import asdict, replace
import gzip
import json

import pytest

from swarm_societies.commons_v3 import development as dev
from swarm_societies.commons_v3.engine import AgentState, Config, PatchState, WorldState, observe, step
from swarm_societies.commons_v3.policies import LocalPolicy


def local_world(**changes):
    cfg = replace(Config(width=3, height=1, n_agents=1, n_patches=1,
                         need=.5, initial_inventory=2., initial_patch_stock=30.,
                         weather_amplitude=0.), **changes)
    return WorldState(cfg, 9, 0, (AgentState(0, 1, 0, cfg.initial_inventory),),
                      (PatchState(0, 1, 0, cfg.initial_patch_stock),))


def test_greedy_is_capacity_aware_before_consumption():
    state = local_world(initial_inventory=79.)
    action = LocalPolicy("greedy")(observe(state, 0))
    assert action.harvest == pytest.approx(1 / .98)
    result = step(state, (action,))
    assert result.ledger.waste == pytest.approx(0, abs=1e-12)
    assert result.state.agents[0].inventory == pytest.approx(79.5)


def test_restraint_uses_observed_headcount_and_half_capacity():
    state = local_world(n_agents=2, initial_patch_stock=21.)
    state = replace(state, agents=(AgentState(0, 1, 0, 2.), AgentState(1, 1, 0, 2.)))
    actions = tuple(LocalPolicy("restraint")(observe(state, i)) for i in range(2))
    assert [a.harvest for a in actions] == [.5, .5]
    result = step(state, actions)
    assert result.ledger.patches[0].stock_after_harvest == 20.


def test_seen_coordinates_only_and_packets_are_unchanged():
    state = local_world()
    packet = observe(state, 0)
    before = json.dumps(packet, sort_keys=True)
    policy = LocalPolicy("greedy")
    policy(packet)
    assert json.dumps(packet, sort_keys=True) == before
    assert policy.memory()["sites"] == [[0, 1, 0]]
    assert policy.memory()["visits"] == [[1, 0, 1]]


def test_scouting_preserves_path_to_known_site():
    state = local_world(initial_inventory=.08, initial_patch_stock=.01, need=1.)
    policy = LocalPolicy("greedy")
    for _ in range(20):
        action = policy(observe(state, 0))
        if action.move != (0, 0):
            destination = state.agents[0].x + action.move[0], state.agents[0].y + action.move[1]
            home = min(abs(destination[0] - x) + abs(destination[1] - y) for x, y in policy.sites.values())
            assert state.agents[0].inventory >= state.config.movement_cost * (1 + home)
            assert action.harvest == 0
        state = step(state, (action,)).state


def tiny_design():
    specification = dev.design()
    cfg = Config(width=3, height=3, n_agents=2, n_patches=1, need=.3,
                 initial_patch_stock=30., weather_amplitude=.1)
    specification["cases"] = [{"id": "tiny", "panel": "grid", "seed": 900123,
                               "focal_id": 0, "horizon": 8, "config": asdict(cfg)}]
    specification["reference_frames_case"] = "tiny"
    return specification


def test_episode_determinism_weather_pairing_and_checkpoint():
    specification = tiny_design()
    case = specification["cases"][0]
    record = dev.run_case(case, specification)
    assert record == dev.run_case(case, specification)
    assert len({e["weather_sha256"] for e in record["episodes"]}) == 1
    assert all(e["checkpoint_continuation_checked"] for e in record["episodes"])
    for episode in record["episodes"]:
        for agent in episode["agents"]:
            assert agent["utility"]["0.0"] == agent["consumption_per_tick"]
            assert agent["utility"]["0.2"] - agent["utility"]["0.0"] == pytest.approx(.2 * agent["terminal_inventory"] / 8)


def test_complete_panel_retains_declared_sensitivities_and_focal_roles():
    cases = dev.design()["cases"]
    assert len(cases) == len({c["id"] for c in cases}) == 56
    assert {c["focal_id"] for c in cases} == {0, 6, 12, 18}
    assert {c["panel"] for c in cases} == {"grid", "long_horizon", "keyed_priority", "lower_stock", "additive", "small_inventory"}
    assert sum(c["panel"] == "grid" for c in cases) == 36


def test_frozen_bank_replay_tamper_and_overwrite_protection(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank"
    dev.prepare(output)
    with pytest.raises(FileExistsError):
        dev.prepare(output)
    result = dev.run(output)
    assert result["episodes"] == 4
    assert dev.verify(output)["semantic_replay"] is True
    with pytest.raises(FileExistsError):
        dev.run(output)
    summary = json.loads((output / "summary.json").read_text())
    summary["episodes"] = 999
    (output / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="artifact changed"):
        dev.verify(output, replay=False)


def test_failure_is_recorded_and_cannot_complete(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank"
    dev.prepare(output)
    def failed(*_):
        raise ArithmeticError("injected accounting failure")
    monkeypatch.setattr(dev, "run_case", failed)
    with pytest.raises(ArithmeticError):
        dev.run(output)
    assert not (output / "manifest.json").exists()
    assert json.loads((output / "tiny-failure.json").read_text())["error"] == "ArithmeticError"
    with pytest.raises(FileExistsError, match="failed development bank"):
        dev.run(output)


def test_unexpected_files_cannot_enter_completion_inventory(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank"
    dev.prepare(output)
    (output / "unrelated.json").write_text("{}")
    with pytest.raises(ValueError, match="unexpected artifacts"):
        dev.run(output)
    assert not (output / "manifest.json").exists()


def test_rehashed_boolean_cannot_impersonate_numeric_replay(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank"
    dev.prepare(output)
    dev.run(output)
    path = output / "cases/tiny.json.gz"
    saved = dev.read_case(path)
    assert saved["episodes"][0]["trajectory"][0]["waste"] == 0.0
    saved["episodes"][0]["trajectory"][0]["waste"] = False
    with gzip.open(path, "wb") as stream:
        stream.write(dev.canonical(saved))
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["artifacts_sha256"]["cases/tiny.json.gz"] = dev.sha(path)
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="semantic replay differs"):
        dev.verify(output, replay=True)


def test_rehashed_boolean_cannot_impersonate_design_or_manifest_count(tmp_path, monkeypatch):
    specification = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: specification)
    output = tmp_path / "bank"
    dev.prepare(output)
    dev.run(output)
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["cases"] = True
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="inventory"):
        dev.verify(output)
    saved = json.loads((output / "design.json").read_text())
    saved["cases"][0]["focal_id"] = False
    (output / "design.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="design changed"):
        dev.check_sources(output)
