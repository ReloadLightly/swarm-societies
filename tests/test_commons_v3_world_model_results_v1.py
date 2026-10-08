"""Recorded-results fixtures; no scientific development or evaluation runs."""
from copy import deepcopy
from dataclasses import replace
import csv
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from swarm_societies.commons_v3 import development_learning_sites_v1 as base
from swarm_societies.commons_v3 import development_pool_sites_v1 as pool
from swarm_societies.commons_v3 import development_joint_sites_v1 as joint
from swarm_societies.commons_v3 import development_joint_sharing_sites_v1 as sharing
from swarm_societies.commons_v3.development_navigation_v1 import _save_record as _save_new_record


STAGES = ("known-rate-pooling", "unknown-rate-pooling", "unknown-rate-sharing")


def _save_json(path, value):
    """Replace only this test's temporary synthetic fixture."""
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _save_record(path, value):
    path.unlink(missing_ok=True)
    _save_new_record(path, value)


@pytest.fixture
def results():
    return importlib.import_module("scripts.visualize_commons_v3_world_models_v1")


def recorded(job, *, version=joint.VERSION, share=None):
    """Compact saved measurements, deliberately not simulated trajectories."""
    arm = job["arm"]
    shares = {"L0": .8, "R-pool": .81, "L1": .82, "L2": .84,
              "L3": .85, "L2-biased": .76, "L3-biased": .73,
              "R-oracle": .9, "R-fixed": .78, "R-greedy": .6}
    errors = {"L0": .5, "R-pool": .2, "L1": .4, "L2": .3,
              "L3": .25, "L2-biased": .4, "L3-biased": .6}
    error = errors.get(arm, .2)
    summary = dict.fromkeys(sharing.SUMMARY_FIELDS, .2)
    summary.update(share_of_need=shares[arm] if share is None else share,
                   final_quarter_share_of_need=.7, first64_share_of_need=.6,
                   time_mean_capacity_absolute_log_error=error,
                   terminal_capacity_absolute_log_error=error / 2,
                   terminal_seen_only_absolute_log_error=error / 3,
                   time_mean_coverage90=.95 if arm == "L3" else .9,
                   terminal_coverage90=.85 if arm == "L3" else .9)
    beliefs = [{"tick": tick, "capacity_absolute_log_error": error,
                "seen_only_absolute_log_error": error / 2,
                "clean_eligible_fraction": .2,
                "coverage90": summary["time_mean_coverage90"]}
               for tick in range(joint.HORIZON + 1)]
    return {"job": deepcopy(job), "version": version, "horizon": joint.HORIZON,
            "rate_known": version in (base.VERSION, pool.VERSION), "rate_prior": dict(joint.RATE_PRIOR),
            "summary": summary, "belief_ticks": beliefs, "complete_fixture": True}


@pytest.fixture
def banks(monkeypatch, tmp_path, results):
    """Keep real pairing statistics/gates; stub already-tested older closures."""
    roots = {name + "_root": tmp_path / name for name in
             ("pool", "baseline", "reference", "calibration", "fallback", "sharing")}
    for root in roots.values():
        root.mkdir()
        _save_json(root / "summary.json", {"fixture": root.name})
    references = [recorded({**job, "arm": arm, "fixed_capacity": 40. if arm == "R-fixed" else None})
                  for job in base.candidate_jobs(.25)
                  for arm in ("R-oracle", "R-fixed", "R-greedy")]
    l0 = [recorded(job, version=base.VERSION) for job in base.candidate_jobs(.25)]
    # Older bank loaders are stubbed below: these files only exercise source
    # inventories and hashing, so they do not need duplicated belief arrays.
    for job in base.candidate_jobs():
        _save_record(base._path(roots["baseline_root"], job), {"fixture_job": job})
    for row in references:
        _save_record(base.consequence._path(roots["reference_root"], row["job"]), {"fixture_job": row["job"]})
    _save_json(roots["calibration_root"] / "cases.json", {"fixture": "calibration"})
    baseline_record = {"preserved_G3": {"trivial": True}}
    monkeypatch.setattr(pool, "load_baseline", lambda *_: (l0, references, baseline_record))
    monkeypatch.setattr(base, "_paired_worlds", lambda *_: None)
    checked = []

    def require_complete(row, job, version):
        checked.append((deepcopy(job), version))
        if (row.get("complete_fixture") is not True or row["job"] != job
                or row["version"] != version or row["horizon"] != joint.HORIZON
                or len(row["belief_ticks"]) != joint.HORIZON + 1):
            raise ValueError("incomplete or mismatched synthetic record")

    monkeypatch.setattr(sharing, "_require_complete", require_complete)
    known_validator = results._require_known_complete

    def require_known_fixture(row, job, version):
        if (row.get("complete_fixture") is not True or row["job"] != job
                or row["version"] != version or row["horizon"] != joint.HORIZON):
            raise ValueError("incomplete or mismatched synthetic known-rate record")

    monkeypatch.setattr(results, "_require_known_complete", require_known_fixture)

    def forbidden(*_, **__):
        pytest.fail("rendering recorded evidence invoked a simulation or replay runner")

    for module, names in ((base, ("run_episode", "_run_jobs", "run", "verify")),
                          (base.consequence, ("run_episode", "run", "verify")),
                          (pool, ("run_pool_episode", "_run_jobs", "run_pool", "verify_pool", "run_sharing")),
                          (joint, ("run_episode", "_record_unknown_episode", "run")),
                          (sharing, ("run_episode", "run"))):
        for name in names:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(joint.engine, "step", forbidden)

    known_rows = [recorded(job, version=pool.VERSION) for job in pool.pool_jobs()]
    for row in known_rows:
        _save_record(base._path(roots["pool_root"], row["job"]), row)
    known_summary = pool.summarize_pool(known_rows, l0, references, baseline_record)
    _save_json(roots["pool_root"] / "summary.json", known_summary)
    calibration = {"G2": {"passed": True}}
    monkeypatch.setattr(joint, "_load_prerequisites", lambda *_: (references, known_summary, calibration))

    def fallback(*, passed=False):
        rows = [recorded(job, share=(.83 if passed else .81) if job["arm"] == "R-pool" else .8)
                for job in joint.fallback_jobs()]
        for row in rows:
            _save_record(base._path(roots["fallback_root"], row["job"]), row)
        summary = joint.summarize(rows, references, known_summary, calibration)
        _save_json(roots["fallback_root"] / "summary.json", summary)
        return rows, summary

    fallback_rows, fallback_summary = fallback()

    def sharing_bank(*, passed=True):
        rows, summary = fallback(passed=passed)
        alone = [row for row in rows if row["job"]["arm"] == "L0"]
        shared = [recorded(job, version=sharing.VERSION) for job in sharing.sharing_jobs()]
        for row in shared:
            _save_record(base._path(roots["sharing_root"], row["job"]), row)
        if passed:
            shared_summary = sharing.summarize(shared, alone, references, summary)
            _save_json(roots["sharing_root"] / "summary.json", shared_summary)
        return shared

    return {"roots": roots, "fallback": fallback, "sharing": sharing_bank,
            "known_summary": known_summary, "fallback_summary": fallback_summary,
            "fallback_rows": fallback_rows, "checked": checked, "references": references,
            "l0": l0, "known_rows": known_rows, "known_validator": known_validator}


def test_failed_unknown_rate_gate_is_reportable_without_authorizing_sharing(results, banks):
    data = results.load("unknown-rate-pooling", **banks["roots"])
    assert data["stage"] == "unknown-rate-pooling"
    assert data["summary"] == banks["fallback_summary"]
    assert data["summary"]["G3_prime"]["passed"] is False
    assert "stop the contracted design" in data["summary"]["decision"]
    assert len(data["rows"]) == 32
    assert data["references"] == banks["references"]
    assert len(banks["checked"]) == 32
    assert all(isinstance(path, Path) and path.is_file() for path in data["sources"])


def test_known_rate_loader_keeps_the_known_baseline_and_failed_gate(results, banks):
    data = results.load("known-rate-pooling", **banks["roots"])
    assert data["summary"] == banks["known_summary"]
    assert data["summary"]["rate_known"] is True
    assert data["summary"]["G3_prime"]["passed"] is False
    assert {row["job"]["arm"] for row in data["rows"]} == {"L0", "R-pool"}
    assert banks["checked"] == []


@pytest.mark.parametrize("damage", ["case", "summary", "terminal", "stage"])
def test_partial_or_mismatched_fallback_refused_before_output(results, banks, tmp_path, damage):
    root = banks["roots"]["fallback_root"]
    row = deepcopy(banks["fallback_rows"][0])
    if damage == "case":
        base._path(root, row["job"]).unlink()
    elif damage == "summary":
        saved = deepcopy(banks["fallback_summary"])
        saved["G3_prime"]["passed"] = True
        _save_json(root / "summary.json", saved)
    elif damage == "terminal":
        row["belief_ticks"].pop()
        _save_record(base._path(root, row["job"]), row)
    else:
        row["version"] = pool.VERSION
        _save_record(base._path(root, row["job"]), row)
    output = tmp_path / "refused"
    with pytest.raises(ValueError):
        results.render("unknown-rate-pooling", output, **banks["roots"])
    assert not output.exists()


def test_missing_completed_summary_is_not_treated_as_live_partial_results(results, banks, tmp_path):
    (banks["roots"]["fallback_root"] / "summary.json").unlink()
    output = tmp_path / "refused"
    with pytest.raises((OSError, ValueError)):
        results.render("unknown-rate-pooling", output, **banks["roots"])
    assert not output.exists()


def test_sharing_loader_requires_the_actual_reconstructed_passed_fallback(results, banks):
    banks["sharing"](passed=False)
    with pytest.raises(ValueError, match="G3-prime failed"):
        results.load("unknown-rate-sharing", **banks["roots"])
    banks["sharing"](passed=True)
    data = results.load("unknown-rate-sharing", **banks["roots"])
    assert data["summary"]["rate_known"] is False
    assert data["summary"]["G3_prime"]["passed"] is True
    assert data["summary"]["episodes"] == 80
    assert len(data["rows"]) == 96
    assert {row["job"]["arm"] for row in data["rows"]} == set(base.ARMS)
    contrasts = data["summary"]["development_contrasts"]["contrasts"]
    assert contrasts["P4"]["statistics"]["mean"] == pytest.approx(-.03)
    assert contrasts["P5"]["time_mean_ticks1_to512"]["statistics"]["mean"] == pytest.approx(.05)
    assert contrasts["P5"]["terminal_tick512"]["statistics"]["mean"] == pytest.approx(-.05)


@pytest.mark.parametrize("stage", ["pooling", "unknown-rate", "sharing", "A2", ""])
def test_stage_is_explicit_and_rejects_ambiguous_aliases(results, stage):
    with pytest.raises(ValueError):
        results.load(stage)


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def test_exports_retain_paired_direction_and_both_descriptive_p5_endpoints(results, banks, tmp_path):
    banks["sharing"]()
    data = results.load("unknown-rate-sharing", **banks["roots"])
    output = tmp_path / "tables"
    output.mkdir()
    files = results.export_tables(data, output)
    assert {path.name for path in files} >= {
        "condition-means.csv", "learning-trajectories.csv",
        "paired-effects.csv", "development-contrasts.csv"}
    pairs = read_csv(output / "paired-effects.csv")
    consumption = [row for row in pairs if row["contrast"] == "L2_minus_L0"
                   and row["metric"] == "share_of_need"]
    assert len(consumption) == 16
    assert all(float(row["difference"]) == pytest.approx(.04) for row in consumption)
    error = [row for row in pairs if row["contrast"] == "L2_minus_L0"
             and row["metric"] == "time_mean_capacity_absolute_log_error"]
    assert len(error) == 16
    assert all(float(row["difference"]) == pytest.approx(-.2) for row in error)
    development = read_csv(output / "development-contrasts.csv")
    p4 = [row for row in development if row["contrast"] == "P4"]
    assert [int(row["seed"]) for row in p4] == list(base.SEEDS)
    assert all(float(row["difference"]) == pytest.approx(-.03) for row in p4)
    p5 = [row for row in development if row["contrast"] == "P5"]
    assert len(p5) == 8
    assert {row["endpoint"] for row in p5} == {"time_mean_ticks1_to512", "terminal_tick512"}
    for row in p5:
        expected = .05 if row["endpoint"] == "time_mean_ticks1_to512" else -.05
        assert float(row["difference"]) == pytest.approx(expected)


def fake_figures(data, output):
    files = []
    for suffix in ("svg", "pdf", "png"):
        path = output / ("fixture." + suffix)
        path.write_bytes((data["stage"] + ":" + suffix).encode())
        files.append(path)
    return [{"id": "fixture", "caption": "Synthetic figure for manifest verification.", "files": files}]


@pytest.mark.parametrize("stage", STAGES)
def test_render_manifest_hashes_sources_and_outputs_deterministically(results, banks, tmp_path, monkeypatch, stage):
    if stage == "unknown-rate-sharing":
        banks["sharing"]()
    monkeypatch.setattr(results, "render_figures", fake_figures)
    output = tmp_path / "gallery"
    manifest = results.render(stage, output, **banks["roots"])
    assert manifest["style"] == "Chromatic Field v1"
    assert manifest["stage"] == stage
    assert manifest["rendering_runs_simulation"] is False
    assert json.loads((output / "manifest.json").read_text()) == manifest
    assert manifest["figures"][0]["files"] == ["fixture.svg", "fixture.pdf", "fixture.png"]
    for key in ("sources", "outputs"):
        paths = [row["path"] for row in manifest[key]]
        assert paths == sorted(set(paths))
        for row in manifest[key]:
            path = Path(row["path"]) if key == "sources" else output / row["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    names = {row["path"] for row in manifest["outputs"]}
    assert "README.md" in names
    assert ("development-contrasts.csv" in names) == (stage == "unknown-rate-sharing")
    text = (output / "README.md").read_text()
    assert "descriptive" in text.lower()
    if stage == "unknown-rate-pooling":
        assert "stop the contracted design" in text.lower()


def test_completed_gallery_is_preserved_on_rerender(results, banks, tmp_path, monkeypatch):
    monkeypatch.setattr(results, "render_figures", fake_figures)
    output = tmp_path / "gallery"
    results.render("unknown-rate-pooling", output, **banks["roots"])
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(ValueError):
        results.render("unknown-rate-pooling", output, **banks["roots"])
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}


@pytest.mark.parametrize("damage", ["case", "summary"])
def test_sharing_case_or_aggregate_damage_is_rejected(results, banks, damage):
    rows = banks["sharing"]()
    root = banks["roots"]["sharing_root"]
    if damage == "case":
        base._path(root, rows[0]["job"]).unlink()
    else:
        path = root / "summary.json"
        saved = json.loads(path.read_text())
        saved["development_contrasts"]["contrasts"]["P4"]["statistics"]["mean"] = 10
        _save_json(path, saved)
    with pytest.raises(ValueError):
        results.load("unknown-rate-sharing", **banks["roots"])


@pytest.mark.parametrize("stage", STAGES)
def test_real_plotting_smoke_on_synthetic_recorded_summaries(results, banks, tmp_path, stage):
    if stage == "unknown-rate-sharing":
        banks["sharing"]()
    output = tmp_path / "real-figures"
    manifest = results.render(stage, output, **banks["roots"])
    assert len(manifest["figures"]) == (3 if stage == "unknown-rate-sharing" else 2)
    for figure in manifest["figures"]:
        assert {Path(name).suffix for name in figure["files"]} == {".svg", ".pdf", ".png"}
        assert figure["caption"]
        for name in figure["files"]:
            contents = (output / name).read_bytes()
            assert len(contents) > 1000
            if name.endswith(".pdf"):
                assert contents.startswith(b"%PDF")
            elif name.endswith(".png"):
                assert contents.startswith(b"\x89PNG\r\n\x1a\n")
            else:
                assert b"<svg" in contents


def complete_known_record(job, version):
    """Create terminal topology, with no engine steps or policy execution."""
    row = recorded(job, version=version)
    state = joint.worlds.initialize(job["condition"], job["need"], job["seed"])
    state = replace(state, config=replace(state.config, max_messages=4))
    pairs = [[agent.id, site.id] for agent in state.agents for site in state.patches]
    row.update(initial_snapshot=joint.engine.snapshot(state),
               final_snapshot=joint.engine.snapshot(replace(state, tick=joint.HORIZON)),
               trajectory_sha256="0" * 64, weather_sha256="1" * 64,
               final_policy_memory_sha256=["2" * 64] * len(state.agents),
               ticks=[{**dict.fromkeys(sharing.MATERIAL_FIELDS, 0), "tick": tick}
                      for tick in range(1, joint.HORIZON + 1)],
               belief_pair_columns=list(base.PAIR_COLUMNS),
               belief_checkpoints=[{"tick": tick, "pairs": [pair + [0] * 7 for pair in pairs]}
                                   for tick in base.BELIEF_CHECKPOINTS],
               agents=[{"id": agent.id} for agent in state.agents],
               first_within10_columns=["agent", "site", "first_tick_or_null"],
               first_within10=[pair + [None] for pair in pairs])
    row["initial_physical_sha256"] = base.physical_initial_digest(row["initial_snapshot"])
    row["belief_ticks"] = [{**dict.fromkeys(sharing.BELIEF_FIELDS, .2), **frame}
                           for frame in row["belief_ticks"]]
    if job["arm"] == "R-pool":
        row["final_pool_memory_sha256"] = "3" * 64
    row.pop("rate_known")
    row.pop("rate_prior")
    return row


@pytest.mark.parametrize("arm,version", [("L0", base.VERSION), ("R-pool", pool.VERSION)])
def test_known_terminal_guard_accepts_complete_synthetic_topology(results, arm, version):
    job = (base.candidate_jobs(.25) if arm == "L0" else pool.pool_jobs())[0]
    row = complete_known_record(job, version)
    results._require_known_complete(row, job, version)


@pytest.mark.parametrize("damage", ["material_tick", "terminal_tick", "belief_tick"])
def test_known_truncated_record_cannot_produce_gallery(results, banks, monkeypatch, tmp_path, damage):
    row = complete_known_record(banks["l0"][0]["job"], base.VERSION)
    if damage == "material_tick":
        row["ticks"].pop()
    elif damage == "terminal_tick":
        state = joint.engine.restore(row["final_snapshot"])
        row["final_snapshot"] = joint.engine.snapshot(replace(state, tick=joint.HORIZON - 1))
    else:
        row["belief_ticks"].pop()
    banks["l0"][0] = row
    monkeypatch.setattr(results, "_require_known_complete", banks["known_validator"])
    # Isolate the added terminal guard from already-covered aggregate checks.
    monkeypatch.setattr(pool, "_load_pool", lambda *_: (banks["known_rows"], banks["known_summary"]))
    output = tmp_path / "refused"
    with pytest.raises(ValueError, match="incomplete or mismatched known-rate"):
        results.render("known-rate-pooling", output, **banks["roots"])
    assert not output.exists()


@pytest.mark.parametrize("loader", ["load_baseline", "_load_pool"])
def test_truncated_known_aggregate_is_reported_as_invalid_input(results, banks, monkeypatch, tmp_path, loader):
    def truncated(*_):
        raise IndexError("truncated belief checkpoint array")

    monkeypatch.setattr(pool, loader, truncated)
    output = tmp_path / "refused"
    with pytest.raises(ValueError):
        results.render("known-rate-pooling", output, **banks["roots"])
    assert not output.exists()
