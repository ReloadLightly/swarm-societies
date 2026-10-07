"""Independent evidence-lifecycle and contrast tests for need-targeted development."""
from copy import deepcopy
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import subprocess
import sys

import pytest

from swarm_societies.commons_v3 import development_need_v1 as dev
from swarm_societies.commons_v3 import development_v2 as previous
from swarm_societies.commons_v3.engine import Config


def tiny_design():
    specification = dev.design()
    cfg = Config(width=3, height=3, n_agents=2, n_patches=1, need=.3,
                 initial_patch_stock=30., weather_amplitude=.1)
    specification["cases"] = [
        {"id": "tiny", "panel": "grid", "seed": 900123, "focal_id": 0,
         "horizon": 8, "config": asdict(cfg)},
        {"id": "tiny-second", "panel": "grid", "seed": 900124, "focal_id": 1,
         "horizon": 8, "config": asdict(cfg)},
    ]
    specification["reference_frames_case"] = "tiny"
    return specification


@pytest.fixture
def specification(monkeypatch):
    value = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: deepcopy(value))
    return value


@pytest.fixture
def tiny_bank(tmp_path, specification):
    output = tmp_path / "need-bank"
    dev.prepare(output)
    dev.run(output)
    return output


def test_design_preserves_development_cases_and_declares_distinct_estimands():
    old, new = previous.design(), dev.design()
    assert dev.canonical(old["cases"]) == dev.canonical(new["cases"])
    assert new["conditions"] == ["need_0", "need_2", "focal_greedy_need_0", "focal_greedy_need_2"]
    assert new["reused_cases"] is True and new["qualification_data"] is False
    assert new["baseline_reserve_ticks"] == {"need_0": 0, "need_2": 2}
    assert len(new["cases"]) == 56
    assert {case["config"]["inventory_capacity"] for case in new["cases"] if case["panel"] != "small_inventory"} == {80.}
    for key in ("wealth_weights", "depletion_threshold_capacity_fraction", "late_window_fraction",
                "ledger_relative_tolerance", "reference_frames_case", "experimental_model_calls", "evolutionary_runs"):
        assert dev.canonical(old[key]) == dev.canonical(new[key])
    assert dev.modes("focal_greedy_need_2", 4, 2) == ("need_2", "need_2", "greedy", "need_2")
    with pytest.raises(ValueError, match="two agents"):
        dev.modes("need_0", 1, 0)


def test_complete_bank_pairs_weather_replays_exactly_and_freezes_all_sources(tiny_bank):
    receipt = dev.verify(tiny_bank)
    assert receipt["verified"] is receipt["semantic_replay"] is True
    assert receipt["cases"] == 2 and receipt["episodes"] == 8
    record = dev.read_case(tiny_bank / "cases/tiny.json.gz")
    assert len({row["weather_sha256"] for row in record["episodes"]}) == 1
    assert all(row["checkpoint_continuation_checked"] for row in record["episodes"])
    assert all(row["summary"]["max_unaffordable_known_returns"] == 0 for row in record["episodes"])
    assert dev.canonical(record) == dev.canonical(dev.run_case(record["case"], dev.design()))
    pins = json.loads((tiny_bank / "sources.json").read_text())
    assert set(pins) == set(dev.SOURCES)
    for name, digest in pins.items():
        assert dev.sha(tiny_bank / "sources" / name) == dev.sha(dev.ROOT / name) == digest
    with pytest.raises(FileExistsError, match="completed"):
        dev.run(tiny_bank)
    with pytest.raises(FileExistsError):
        dev.prepare(tiny_bank)


def test_aggregate_focal_comparisons_use_their_own_baseline(specification):
    # Hand-written primitives intentionally make the two focal contrasts and
    # reserve comparison differ, catching accidental reuse of need_0 controls.
    records = []
    for case in specification["cases"]:
        episodes = []
        focal = case["focal_id"]
        for condition, consumption, inventory in (
            ("need_0", (1., 3.), (2., 2.)),
            ("need_2", (5., 7.), (4., 4.)),
            ("focal_greedy_need_0", (2., 1.), (10., 2.)),
            ("focal_greedy_need_2", (8., 6.), (20., 4.)),
        ):
            # Values are ordered focal then peer regardless of identity.
            ordered = consumption if focal == 0 else consumption[::-1]
            reserves = inventory if focal == 0 else inventory[::-1]
            agents = [{"id": i, "consumption_per_tick": ordered[i],
                       "late_consumption_per_tick": ordered[i] / 2,
                       "terminal_inventory": reserves[i],
                       "utility": {str(w): ordered[i] + w * reserves[i] / case["horizon"] for w in dev.WEIGHTS}}
                      for i in range(2)]
            episodes.append({"condition": condition, "agents": agents,
                             "summary": {"consumption_per_agent_tick": sum(consumption) / 2,
                                         "max_ledger_residual": 0., "max_relative_ledger_residual": 0.}})
        records.append({"case": case, "episodes": episodes})
    result = dev.aggregate(records, specification)
    cell = result["cells"][0]
    assert cell["focal_deviation"]["need_0"]["consumption"]["mean"] == 1.
    assert cell["focal_deviation"]["need_2"]["consumption"]["mean"] == 3.
    assert cell["focal_deviation"]["need_0"]["peer_consumption"]["mean"] == -2.
    assert cell["focal_deviation"]["need_2"]["peer_consumption"]["mean"] == -1.
    assert cell["focal_deviation"]["need_0"]["terminal_inventory"]["mean"] == 8.
    assert cell["focal_deviation"]["need_2"]["utility_0.05"]["mean"] == pytest.approx(3.1)
    assert cell["reserve_comparison"]["consumption_per_agent_tick"]["mean"] == 4.
    assert result["physical_ticks"] == 64 and result["agent_decisions"] == 128
    assert result["qualification_status"] == "not_run"


def test_interruption_resumes_by_replay_without_rewriting_completed_case(tmp_path, specification, monkeypatch):
    output = tmp_path / "interrupted"
    dev.prepare(output)
    original = dev.run_case
    seen = []

    def interrupted(case, design):
        seen.append(case["id"])
        if case["id"] == "tiny-second":
            raise KeyboardInterrupt("external stop")
        return original(case, design)

    monkeypatch.setattr(dev, "run_case", interrupted)
    with pytest.raises(KeyboardInterrupt):
        dev.run(output)
    saved = output / "cases/tiny.json.gz"
    before = saved.read_bytes(), saved.stat().st_mtime_ns
    assert not list(output.glob("*-failure.json"))
    monkeypatch.setattr(dev, "run_case", original)
    dev.run(output)
    assert (saved.read_bytes(), saved.stat().st_mtime_ns) == before
    assert dev.verify(output)["episodes"] == 8


def rehash(bank, name):
    manifest = json.loads((bank / "manifest.json").read_text())
    manifest["artifacts_sha256"][name] = dev.sha(bank / name)
    (bank / "manifest.json").write_bytes(dev.canonical(manifest))


@pytest.mark.parametrize("target", ["case", "summary", "manifest"])
def test_rehashed_boolean_numeric_tampering_fails_strict_verification(tiny_bank, target):
    if target == "case":
        name = "cases/tiny.json.gz"
        value = dev.read_case(tiny_bank / name)
        assert value["episodes"][0]["trajectory"][0]["waste"] == 0.
        value["episodes"][0]["trajectory"][0]["waste"] = False
        with gzip.open(tiny_bank / name, "wb") as stream:
            stream.write(dev.canonical(value))
        rehash(tiny_bank, name)
    elif target == "summary":
        name = "summary.json"
        value = json.loads((tiny_bank / name).read_text())
        value["experimental_model_calls"] = False
        (tiny_bank / name).write_bytes(dev.canonical(value))
        rehash(tiny_bank, name)
    else:
        value = json.loads((tiny_bank / "manifest.json").read_text())
        value["cases"] = True
        (tiny_bank / "manifest.json").write_bytes(dev.canonical(value))
    with pytest.raises(ValueError, match="semantic replay|aggregate differs|inventory"):
        dev.verify(tiny_bank)


@pytest.mark.parametrize("damage", ["missing", "extra", "source", "design"])
def test_missing_extra_or_changed_inputs_are_rejected(tiny_bank, damage):
    if damage == "missing":
        (tiny_bank / "cases/tiny.json.gz").unlink()
    elif damage == "extra":
        (tiny_bank / "unrecorded.json").write_text("{}")
    elif damage == "source":
        (tiny_bank / "sources" / dev.SOURCES[0]).write_text("changed")
    else:
        value = json.loads((tiny_bank / "design.json").read_text())
        value["cases"][0]["horizon"] += 1
        (tiny_bank / "design.json").write_bytes(dev.canonical(value))
    with pytest.raises(ValueError, match="inventory|source changed|design changed"):
        dev.verify(tiny_bank)


def test_recovery_rejects_modified_existing_case_and_preserves_failure(tmp_path, specification):
    output = tmp_path / "bad-recovery"
    dev.prepare(output)
    case = specification["cases"][0]
    record = dev.run_case(case, specification)
    record["episodes"][0]["trajectory"][0]["consumption"] += 1.
    with gzip.open(output / "cases/tiny.json.gz", "wb") as stream:
        stream.write(dev.canonical(record))
    with pytest.raises(ValueError, match="existing case differs"):
        dev.run(output)
    failure = (output / "tiny-failure.json").read_bytes()
    with pytest.raises(FileExistsError, match="failed"):
        dev.run(output)
    assert (output / "tiny-failure.json").read_bytes() == failure
    assert not (output / "manifest.json").exists()


def test_weather_mismatch_fails_before_recording(specification, monkeypatch):
    original = dev.episode
    def mismatch(case, condition, **kwargs):
        result = original(case, condition, **kwargs)
        if condition == "need_2":
            result["weather_sha256"] = "changed"
        return result
    monkeypatch.setattr(dev, "episode", mismatch)
    with pytest.raises(ValueError, match="paired weather"):
        dev.run_case(specification["cases"][0], specification)


def test_cli_help_requires_no_evidence_download():
    result = subprocess.run([sys.executable, str(dev.ROOT / "scripts/run_commons_v3_need_v1.py"), "--help"],
                            text=True, capture_output=True, check=True)
    assert "prepare,run,verify" in result.stdout
