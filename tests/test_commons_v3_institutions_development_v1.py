"""Tiny nonpanel cases test source-bound recording, recovery and exact replay."""
from copy import deepcopy
import gzip
import json

import pytest

from swarm_societies.commons_v3 import institutions_development_v1 as runner
from swarm_societies.commons_v3 import politics_v1 as politics
from swarm_societies.commons_v3.institution_design_v1 import ARMS
from swarm_societies.commons_v3.policies_institutions_development_v1 import DevelopmentPolicy
from swarm_societies.commons_v3.policies_institutions_v1 import CoordinatingForager


def tiny_specification():
    specification = deepcopy(runner.design())
    template = specification["cases"][0]
    cases = []
    for arm in ARMS:
        case = deepcopy(template)
        case.update(id=f"tiny-s42-{arm}", seed=42, horizon=6, arm=arm,
                    stubborn_count=1, stubborn_ids=[2])
        case["config"].update(n_agents=3, n_patches=2, width=4, height=4)
        cases.append(case)
    specification.update(cases=cases, seeds=[42], horizon=6, late_window=6,
        stubborn_counts=[1], counts={"episodes": 4, "physical_ticks": 24, "agent_decisions": 72})
    return specification


@pytest.fixture
def tiny_design(monkeypatch):
    specification = tiny_specification()
    monkeypatch.setattr(runner, "design", lambda: deepcopy(specification))
    return specification


@pytest.fixture
def prepared(tmp_path, tiny_design):
    output = tmp_path / "tiny-development"
    prepared = runner.prepare(output)
    assert prepared["episodes"] == 4
    return output


@pytest.fixture
def completed(prepared):
    receipt = runner.run(prepared, workers=1)
    assert receipt["completed"] and receipt["agent_decisions"] == 72
    return prepared


def write_episode(path, saved):
    path.write_bytes(gzip.compress(runner.canonical(saved) + b"\n", mtime=0))


def test_source_closure_includes_transitive_runtime_and_prospective_design():
    pins = runner.source_pins()
    required = {
        "swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py",
        "swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/politics_v1.py",
        "swarm_societies/commons_v3/policies_navigation_v1.py",
        "swarm_societies/commons_v3/policies_institutions_v1.py",
        "swarm_societies/commons_v3/political_episode_v1.py",
        "swarm_societies/commons_v3/policies_institutions_development_v1.py",
        "swarm_societies/commons_v3/institution_design_v1.py",
        "swarm_societies/commons_v3/institution_measurement_v1.py",
        "swarm_societies/commons_v3/institutions_development_v1.py",
        "scripts/run_commons_v3_institutions_development_v1.py",
        "docs/commons-v3-institutions-development-protocol-v1.md",
        "evidence/commons-v3-navigation-v1/selection.json",
    }
    assert set(pins) == required
    assert all(len(value) == 64 for value in pins.values())
    assert pins["evidence/commons-v3-navigation-v1/selection.json"] == runner.SELECTION_SHA256


@pytest.mark.parametrize("horizon", [4, 6])
def test_exact_episode_replay_and_midpoint_regenerate_policy_decisions(horizon):
    case = tiny_specification()["cases"][-1]
    case["horizon"] = horizon
    saved = runner.record_episode(case)
    saved = json.loads(json.dumps(saved))
    pins = runner.source_pins()
    assert runner.check_episode(saved, case, pins, replay=True) == saved["summary"]
    continued = runner.restore_checkpoint(saved["midpoint_checkpoint"])
    assert continued.state.world.tick == horizon // 2
    for frame in saved["frames"][horizon // 2:]:
        assert runner._frame(continued) == frame
    assert continued.checkpoint() == saved["final_checkpoint"]
    assert saved["summary"]["cohorts"]["eligible"]["ids"] == [0, 1]
    assert saved["summary"]["cohorts"]["stubborn"]["ids"] == [2]


def test_closed_registry_rejects_subclasses_legacy_policies_and_new_memory_versions():
    case = tiny_specification()["cases"][0]
    state = runner._build(case, runner.source_pins()).state

    class UnreviewedPolicy(DevelopmentPolicy):
        pass

    for policy in (UnreviewedPolicy(), CoordinatingForager()):
        with pytest.raises(ValueError, match="audited DevelopmentPolicy"):
            runner.Episode(state, [policy] * 3)
    saved = runner._build(case, runner.source_pins()).checkpoint()
    saved["payload"]["policies"][0]["version"] = "user-authored-policy"
    saved["sha256"] = runner.digest(saved["payload"])
    with pytest.raises(ValueError, match="unsupported development policy"):
        runner.restore_checkpoint(saved)


def test_failed_round_restores_decision_memories_and_world(monkeypatch):
    case = tiny_specification()["cases"][-1]
    episode = runner._build(case, runner.source_pins())
    before = episode.checkpoint()

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic primitive failure")

    monkeypatch.setattr(politics, "step", fail)
    with pytest.raises(RuntimeError, match="synthetic primitive failure"):
        episode.advance()
    assert episode.checkpoint() == before
    assert episode.last_actions is None and episode.last_intents is None


def test_checkpoint_checksum_and_source_closure_are_both_required():
    case = tiny_specification()["cases"][0]
    original = runner._build(case, runner.source_pins()).checkpoint()
    changed = deepcopy(original)
    changed["payload"]["policies"][0]["decisions"]["none"] = 1
    with pytest.raises(ValueError, match="checksum"):
        runner.restore_checkpoint(changed)
    changed = deepcopy(original)
    key = next(iter(changed["payload"]["sources"]))
    changed["payload"]["sources"][key] = "0" * 64
    changed["sha256"] = runner.digest(changed["payload"])
    with pytest.raises(ValueError, match="source closure"):
        runner.restore_checkpoint(changed)


def test_preparation_copies_exact_sources_and_refuses_reusing_output(prepared, tiny_design):
    specification, pins = runner.check_sources(prepared)
    assert specification == tiny_design
    assert all(runner.sha(prepared / "sources" / name) == expected for name, expected in pins.items())
    with pytest.raises(FileExistsError):
        runner.prepare(prepared)


def test_completed_bank_verifies_exact_aggregate_and_refuses_run(completed):
    receipt = runner.verify(completed, workers=1, replay=True)
    assert receipt["verified"] and receipt["semantic_replay"] and receipt["midpoint_policy_continuation"]
    assert receipt["episodes"] == 4 and receipt["physical_ticks"] == 24
    summary = json.loads((completed / "summary.json").read_text())
    assert len(summary["contrasts"]) == 4
    assert all(len(row["seed_values"]) == 1 for row in summary["contrasts"])
    before = {str(p.relative_to(completed)): p.read_bytes() for p in completed.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="sealed"):
        runner.run(completed, workers=1)
    after = {str(p.relative_to(completed)): p.read_bytes() for p in completed.rglob("*") if p.is_file()}
    assert after == before


def test_recovery_replays_and_preserves_complete_episode_bytes_and_mtime(prepared, tiny_design, monkeypatch, capsys):
    first = tiny_design["cases"][0]
    path = prepared / "episodes" / (first["id"] + ".json.gz")
    write_episode(path, runner.record_episode(first))
    before, timestamp = path.read_bytes(), path.stat().st_mtime_ns
    original, newly_recorded = runner.record_episode, []

    def record(case, **kwargs):
        newly_recorded.append(case["id"])
        return original(case, **kwargs)

    monkeypatch.setattr(runner, "record_episode", record)
    receipt = runner.run(prepared, workers=1)
    assert receipt["completed"]
    assert first["id"] not in newly_recorded and len(newly_recorded) == 3
    assert path.read_bytes() == before and path.stat().st_mtime_ns == timestamp
    assert '"status": "preserved"' in capsys.readouterr().out
    assert runner.verify(prepared, workers=1, replay=True)["verified"]


def test_recovery_rejects_action_corruption_even_when_endpoint_summary_is_unchanged(prepared, tiny_design):
    first = tiny_design["cases"][0]
    saved = runner.record_episode(first)
    saved["frames"][0]["actions"][0]["harvest"] += 1.
    path = prepared / "episodes" / (first["id"] + ".json.gz")
    write_episode(path, saved)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="replay differs"):
        runner.run(prepared, workers=1)
    assert path.read_bytes() == before
    assert not (prepared / "manifest.json").exists()


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra"])
def test_seal_rejects_changed_missing_or_unexpected_artifacts(completed, mutation):
    path = next((completed / "episodes").glob("*.json.gz"))
    if mutation == "changed":
        path.write_bytes(path.read_bytes() + b"changed")
    elif mutation == "missing":
        path.unlink()
    else:
        (completed / "unexpected.json").write_text("{}\n")
    with pytest.raises(ValueError, match="manifest"):
        runner.verify(completed, workers=1, replay=False)


def test_missing_episode_is_never_generated_during_verification(completed, monkeypatch):
    path = next((completed / "episodes").glob("*.json.gz"))
    path.unlink()
    # Even a recomputed manifest cannot turn verify into an execution request.
    manifest_path = completed / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["files"][str(path.relative_to(completed))]
    manifest_path.write_bytes(runner.canonical(manifest) + b"\n")

    def forbidden(*args, **kwargs):
        pytest.fail("verification attempted to record a missing episode")

    monkeypatch.setattr(runner, "record_episode", forbidden)
    with pytest.raises((ValueError, FileNotFoundError)):
        runner.verify(completed, workers=1, replay=False)
    assert not path.exists()


def test_unexpected_episode_identity_is_rejected_before_execution(prepared):
    (prepared / "episodes" / "not-in-design.json.gz").write_bytes(b"not an episode")
    with pytest.raises(ValueError, match="unexpected episode"):
        runner.run(prepared, workers=1)
    assert not (prepared / "manifest.json").exists()


def test_changed_frozen_source_copy_cannot_be_resumed(prepared):
    copied = prepared / "sources" / "swarm_societies/commons_v3/engine.py"
    copied.write_bytes(copied.read_bytes() + b"\n# changed test copy\n")
    with pytest.raises(ValueError, match="saved frozen source"):
        runner.run(prepared, workers=1)


def test_episode_symlink_is_rejected(prepared, tiny_design, tmp_path):
    first = tiny_design["cases"][0]
    target = tmp_path / "elsewhere.json.gz"
    write_episode(target, runner.record_episode(first))
    (prepared / "episodes" / (first["id"] + ".json.gz")).symlink_to(target)
    with pytest.raises(ValueError, match="symbolic link"):
        runner.run(prepared, workers=1)


def test_verification_reconstructs_summary_beyond_recomputed_byte_manifest(completed):
    path = completed / "summary.json"
    summary = json.loads(path.read_text())
    summary["contrasts"][0]["mean"]["population"] += .1
    path.write_bytes(runner.canonical(summary) + b"\n")
    manifest_path = completed / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["summary.json"] = runner.sha(path)
    manifest_path.write_bytes(runner.canonical(manifest) + b"\n")
    with pytest.raises(ValueError, match="exact aggregate"):
        runner.verify(completed, workers=1, replay=False)
