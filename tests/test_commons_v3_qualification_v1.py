"""Recovery and frozen-design checks using a separate miniature seed registry."""

from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
from pathlib import Path

import pytest

from swarm_societies.commons_v3.engine import Config
from swarm_societies.commons_v3 import qualification_design_v1 as registry
from swarm_societies.commons_v3 import qualification_v1 as runner


SELECTION = "evidence/commons-v3-navigation-v1/selection.json"
REAL_ROOT = runner.ROOT
REAL_SOURCES = runner.SOURCES


def tiny_design(stage):
    """Two adjacent synthetic cells, two seeds, and a smaller peer mixture."""
    specification = deepcopy(registry.design(stage))
    seeds = [900101, 900102] if stage == "ecology" else [901101, 901102]
    cases, conditions = [], {}
    for rate in (.12, .24):
        cfg = Config(width=4, height=4, n_agents=4, n_patches=2, need=.3,
                     initial_patch_stock=40., renewal_rate=rate)
        for index, seed in enumerate(seeds):
            focal, peers = registry.focal_and_peers(seed, index, n=4)
            case = {"id": f"synthetic-r{rate:.2f}-s{seed}", "panel": "grid",
                    "seed": seed, "focal_id": focal, "peer_order": peers,
                    "horizon": 8, "config": asdict(cfg)}
            cases.append(case)
            pairs = [(0, False)] if stage == "ecology" else [(k, focal_a) for k in (0, 1, 3) for focal_a in (False, True)]
            conditions[case["id"]] = [
                {"id": f"peers{k:02d}-focal{'A' if focal_a else 'R'}" if stage == "incentive" else "all_restrained",
                 "peer_count": k, "focal_aggressive": focal_a,
                 "aggressive_ids": sorted(peers[:k] + ([focal] if focal_a else []))}
                for k, focal_a in pairs]
    episodes = sum(len(specification["controls"]) * len(conditions[case["id"]]) for case in cases)
    specification.update({"cases": cases, "seeds": seeds, "rates": [.12, .24], "needs": [.3],
                          "reference": {"renewal_rate": .24, "need": .3}, "peer_counts": [0, 1, 3],
                          "condition_registry": conditions, "robustness_panels": ["grid"],
                          "reference_frames_case": cases[-2]["id"],
                          "counts": {"configurations": len(cases), "episodes": episodes,
                                     "physical_ticks": episodes * 8, "agent_decisions": episodes * 8 * 4}})
    specification["statistics"].update({"seed_count": 2, "degrees_of_freedom": 1})
    return specification


@pytest.fixture
def miniature(tmp_path, monkeypatch):
    root = tmp_path / "source-root"
    (root / SELECTION).parent.mkdir(parents=True)
    (root / SELECTION).write_bytes((REAL_ROOT / SELECTION).read_bytes())
    (root / "synthetic-source.txt").write_text("fixed synthetic source\n")
    designs = {stage: tiny_design(stage) for stage in ("ecology", "incentive")}
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "SOURCES", ("synthetic-source.txt", SELECTION))
    monkeypatch.setattr(runner, "design", lambda stage: deepcopy(designs[stage]))
    return designs


@pytest.fixture
def prepared(tmp_path, miniature):
    output = tmp_path / "ecology"
    runner.prepare(output, "ecology")
    return output


@pytest.fixture
def complete(prepared):
    runner.run(prepared)
    return prepared


@pytest.fixture
def incentive(tmp_path, complete):
    output = tmp_path / "incentive"
    runner.prepare(output, "incentive")
    runner.run(output, ecology=complete)
    return output, complete


def write_json(path, value):
    path.write_bytes(runner.canonical(value) + b"\n")


def reseal(output):
    write_json(output / "manifest.json", runner._manifest(output, runner.read_json(output / "design.json")))


def tree_bytes(output):
    return {str(path.relative_to(output)): path.read_bytes() for path in output.rglob("*") if path.is_file()}


def case_path(output, case):
    return output / "cases" / (case["id"] + ".json.gz")


def write_case(path, value):
    path.write_bytes(gzip.compress(runner.canonical(value), mtime=0))


def test_prospective_registry_counts_seed_separation_and_focal_pairing():
    ecology, incentive = registry.design("ecology"), registry.design("incentive")
    assert ecology["counts"] == {"configurations": 144, "episodes": 288,
                                 "physical_ticks": 147456, "agent_decisions": 3538944}
    assert incentive["counts"]["configurations"] == 224
    assert incentive["counts"]["episodes"] == 3360
    assert ecology["counts"]["episodes"] + incentive["counts"]["episodes"] == 3648
    earlier = {61001, 61002, 61003, 61004, 62001, 62002, 63001, 63002, 63003, 63004}
    assert set(ecology["seeds"]).isdisjoint(incentive["seeds"])
    assert set(ecology["seeds"] + incentive["seeds"]).isdisjoint(earlier)
    for specification in (ecology, incentive):
        assert specification["experimental_model_calls"] == specification["evolutionary_runs"] == 0
        assert specification["new_numerical_selection_runs"] == 0
        for case in specification["cases"]:
            focal, peers = case["focal_id"], case["peer_order"]
            assert set(peers) == set(range(24)) - {focal}
            assert len(peers) == len(set(peers)) == 23
            assert 0 <= focal < 24
            arms = specification["condition_registry"][case["id"]]
            masks = {(arm["peer_count"], arm["focal_aggressive"]): set(arm["aggressive_ids"]) for arm in arms}
            for arm in arms:
                expected = set(peers[:arm["peer_count"]]) | ({focal} if arm["focal_aggressive"] else set())
                assert set(arm["aggressive_ids"]) == expected
                assert len(arm["aggressive_ids"]) == len(expected)
            for (k, aggressive), mask in masks.items():
                if not aggressive and (k, True) in masks:
                    assert masks[k, True] - mask == {focal}
                    assert mask == masks[k, True] - {focal}
            normal_masks = [masks[key] for key in sorted(masks) if not key[1]]
            assert all(left <= right for left, right in zip(normal_masks, normal_masks[1:]))
    # Each cell rotates focal identity independently of environmental outcomes.
    reference = [case["focal_id"] for case in incentive["cases"] if case["panel"] == "grid"
                 and case["config"]["renewal_rate"] == .24 and case["config"]["need"] == 1.2]
    assert len(reference) == len(set(reference)) == 16


def test_source_closure_keeps_engine_policy_certificates_protocols_and_selection():
    required = {"swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/policies_navigation_v1.py",
                "swarm_societies/commons_v3/qualification_design_v1.py", "swarm_societies/commons_v3/qualification_episode_v1.py",
                "swarm_societies/commons_v3/qualification_analysis_v1.py", "swarm_societies/commons_v3/qualification_v1.py",
                "swarm_societies/commons_v3/feasibility_v1.py", "docs/commons-v3-feasibility-v1.md",
                "docs/commons-v3-ecology-qualification-protocol-v1.md", "docs/commons-v3-incentive-qualification-protocol-v1.md",
                "scripts/run_commons_v3_qualification_v1.py", "swarm_societies/__init__.py",
                "swarm_societies/commons_v3/__init__.py", SELECTION}
    assert required <= set(REAL_SOURCES)
    assert len(REAL_SOURCES) == len(set(REAL_SOURCES))


def test_returned_registry_cannot_mutate_frozen_control_constants():
    expected = registry.design("ecology")
    changed = registry.design("ecology")
    changed["controls"][1]["parameters"]["reserve_ticks"] = 0
    changed["reference"]["need"] = 99
    changed["cases"][0]["config"]["need"] = 99
    assert registry.design("ecology") == expected


def test_prepare_pins_exact_prior_selection_and_refuses_existing_path(prepared, miniature):
    pins = runner.read_json(prepared / "sources.json")
    assert pins[SELECTION] == registry.SELECTION_SHA256
    assert runner.check_sources(prepared) == miniature["ecology"]
    assert not list((prepared / "cases").iterdir())
    with pytest.raises(FileExistsError):
        runner.prepare(prepared, "ecology")


def test_prepare_rejects_changed_prior_selection_before_creating_output(tmp_path, miniature):
    (runner.ROOT / SELECTION).write_text("{}\n")
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="prior selected-policy"):
        runner.prepare(output, "ecology")
    assert not output.exists()


def test_prepare_rejects_registry_selected_parameters(tmp_path, miniature):
    miniature["ecology"]["controls"][1]["parameters"]["reserve_ticks"] = 2
    output = tmp_path / "rejected"
    with pytest.raises(ValueError, match="selected parameters"):
        runner.prepare(output, "ecology")
    assert not output.exists()


@pytest.mark.parametrize("location", ["current", "copy", "design", "inventory"])
def test_source_or_design_tampering_is_rejected(prepared, location):
    if location == "current":
        (runner.ROOT / "synthetic-source.txt").write_text("changed\n")
    elif location == "copy":
        (prepared / "sources/synthetic-source.txt").write_text("changed\n")
    elif location == "design":
        design = runner.read_json(prepared / "design.json")
        design["cases"][0]["focal_id"] = False
        write_json(prepared / "design.json", design)
    else:
        pins = runner.read_json(prepared / "sources.json")
        pins.pop("synthetic-source.txt")
        write_json(prepared / "sources.json", pins)
    with pytest.raises(ValueError, match="differs"):
        runner.run(prepared)
    assert not list((prepared / "cases").iterdir())


def test_selection_binding_cannot_be_replaced_by_rehashing_all_source_pins(prepared):
    altered = (runner.ROOT / SELECTION).read_bytes() + b"\n"
    (runner.ROOT / SELECTION).write_bytes(altered)
    (prepared / "sources" / SELECTION).write_bytes(altered)
    pins = runner.read_json(prepared / "sources.json")
    pins[SELECTION] = hashlib.sha256(altered).hexdigest()
    write_json(prepared / "sources.json", pins)
    with pytest.raises(ValueError, match="prior selection binding"):
        runner.check_sources(prepared)


def test_completed_bank_exact_replay_and_refusal_preserve_every_byte(complete):
    before = tree_bytes(complete)
    times = {path: (complete / path).stat().st_mtime_ns for path in before}
    receipt = runner.verify(complete)
    assert receipt["verified"] is receipt["semantic_replay"] is True
    assert receipt["episodes"] == 8 and receipt["physical_ticks"] == 64
    with pytest.raises(FileExistsError, match="completed qualification"):
        runner.run(complete)
    assert tree_bytes(complete) == before
    assert {path: (complete / path).stat().st_mtime_ns for path in before} == times


def test_interrupted_bank_reuses_complete_case_bytes_and_mtime(prepared, miniature):
    specification = miniature["ecology"]
    first = specification["cases"][0]
    path = case_path(prepared, first)
    payload = runner._packed_case(first, specification)
    runner._publish_bytes(path, payload)
    before_time = path.stat().st_mtime_ns
    result = runner.run(prepared)
    assert path.read_bytes() == payload and path.stat().st_mtime_ns == before_time
    assert result["episodes"] == 8
    assert runner.verify(prepared, replay=False)["verified"] is True


def test_failed_case_is_preserved_and_blocks_restart(prepared, miniature, monkeypatch):
    original = runner._packed_case
    second = miniature["ecology"]["cases"][1]["id"]
    def fail_second(case, specification):
        if case["id"] == second:
            raise RuntimeError("synthetic engineering failure")
        return original(case, specification)
    monkeypatch.setattr(runner, "_packed_case", fail_second)
    with pytest.raises(RuntimeError, match="synthetic engineering failure"):
        runner.run(prepared)
    failure = prepared / (second + "-failure.json")
    assert runner.read_json(failure)["error"] == "RuntimeError"
    assert len(list((prepared / "cases").glob("*.json.gz"))) == 1
    before = tree_bytes(prepared)
    monkeypatch.setattr(runner, "_packed_case", original)
    with pytest.raises(FileExistsError, match="failed qualification bank"):
        runner.run(prepared)
    assert tree_bytes(prepared) == before


def test_changed_incomplete_case_is_not_overwritten(prepared, miniature):
    specification = miniature["ecology"]
    first = specification["cases"][0]
    record = runner.case_record(first, specification)
    record["episodes"][0]["trajectory"][0]["agent_consumption"][0] += .01
    path = case_path(prepared, first)
    write_case(path, record)
    before, modified = path.read_bytes(), path.stat().st_mtime_ns
    with pytest.raises(ValueError, match="exact semantic replay differs"):
        runner.run(prepared)
    assert path.read_bytes() == before and path.stat().st_mtime_ns == modified
    assert (prepared / (first["id"] + "-failure.json")).exists()


def test_aggregation_failure_preserves_complete_raw_cases(prepared, monkeypatch):
    def fail(*args):
        raise ValueError("synthetic aggregate failure")
    monkeypatch.setattr(runner, "aggregate_ecology", fail)
    with pytest.raises(ValueError, match="synthetic aggregate failure"):
        runner.run(prepared)
    assert len(list((prepared / "cases").glob("*.json.gz"))) == 4
    assert (prepared / "completion-failure.json").exists()
    assert not (prepared / "manifest.json").exists()


def test_source_drift_during_execution_prevents_completion(prepared, monkeypatch):
    original = runner._packed_case
    changed = False
    def drift(case, specification):
        nonlocal changed
        result = original(case, specification)
        if not changed:
            (runner.ROOT / "synthetic-source.txt").write_text("changed while executing\n")
            changed = True
        return result
    monkeypatch.setattr(runner, "_packed_case", drift)
    with pytest.raises(ValueError, match="frozen source differs"):
        runner.run(prepared)
    assert len(list((prepared / "cases").glob("*.json.gz"))) == 4
    assert (prepared / "completion-failure.json").exists()
    assert not (prepared / "manifest.json").exists()


@pytest.mark.parametrize("field", ["weather_sha256", "initial_state_sha256"])
def test_condition_pairing_rejects_changed_weather_or_initial_state(miniature, monkeypatch, field):
    original = runner.record_episode
    def mismatched(case, control, aggressive_ids, *, spatial):
        episode = original(case, control, aggressive_ids, spatial=spatial)
        if control["id"] == "selected":
            episode[field] = "changed paired input"
        return episode
    monkeypatch.setattr(runner, "record_episode", mismatched)
    specification = miniature["ecology"]
    with pytest.raises(ValueError, match="paired"):
        runner.case_record(specification["cases"][0], specification)


def test_physical_certificates_are_retained_and_check_exact_ledger_sum(miniature, monkeypatch):
    specification = miniature["ecology"]
    case = specification["cases"][0]
    record = runner.case_record(case, specification)
    assert [(row["horizon"], row["window_start"], row["target_fraction"])
            for row in record["feasibility_certificates"]] == [
                (256, 0, 1.), (256, 0, .95), (512, 0, 1.), (512, 0, .95),
                (512, 384, 1.), (512, 384, .95)]
    certificate = runner.consumption_certificate(Config(**case["config"]), case["horizon"])
    monkeypatch.setattr(runner, "_certificates", lambda saved_case: [deepcopy(certificate)])
    assert runner.case_record(case, specification)["feasibility_certificates"] == [certificate]
    certificate["bounds"]["consumption_total"] = {"numerator": 0, "denominator": 1, "upper_float": 0.}
    with pytest.raises(ValueError, match="exceeds physical certificate"):
        runner.case_record(case, specification)


@pytest.mark.parametrize("mutation", ["verdict", "boolean_zero"])
def test_rehashed_summary_or_verdict_change_fails_reaggregation(complete, mutation):
    summary = runner.read_json(complete / "summary.json")
    if mutation == "verdict":
        summary["qualification_status"] = "manufactured_pass"
    else:
        summary["experimental_model_calls"] = False
    write_json(complete / "summary.json", summary)
    reseal(complete)
    with pytest.raises(ValueError, match="exact aggregate or qualification verdict"):
        runner.verify(complete, replay=False)


def test_rehashed_false_zero_case_binding_still_fails(complete):
    specification = runner.read_json(complete / "design.json")
    path = case_path(complete, specification["cases"][0])
    record = runner.read_case(path)
    record["case"]["focal_id"] = False
    write_case(path, record)
    reseal(complete)
    with pytest.raises(ValueError, match="case binding"):
        runner.verify(complete, replay=False)


def test_rehashed_boolean_number_intervention_alias_still_fails(complete):
    specification = runner.read_json(complete / "design.json")
    path = case_path(complete, specification["cases"][0])
    record = runner.read_case(path)
    record["episodes"][0]["intervention"]["focal_aggressive"] = 0
    write_case(path, record)
    reseal(complete)
    with pytest.raises(ValueError, match="episode binding"):
        runner.verify(complete, replay=False)


def test_rehashed_physical_certificate_is_not_accepted(complete):
    specification = runner.read_json(complete / "design.json")
    path = case_path(complete, specification["cases"][0])
    record = runner.read_case(path)
    record["feasibility_certificates"][0]["bounds"]["consumption_total"]["numerator"] += 1
    write_case(path, record)
    reseal(complete)
    with pytest.raises(ValueError, match="physical certificate differs"):
        runner.verify(complete, replay=False)


def test_rehashed_trajectory_change_fails_semantic_replay(complete):
    specification = runner.read_json(complete / "design.json")
    path = case_path(complete, specification["cases"][0])
    record = runner.read_case(path)
    record["episodes"][0]["trajectory"][0]["agent_consumption"][0] += .01
    write_case(path, record)
    reseal(complete)
    with pytest.raises(ValueError, match="exact semantic replay"):
        runner.verify(complete, replay=True)
    assert not list(complete.glob("*-failure.json"))


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_complete_inventory_must_be_exact(complete, mutation):
    if mutation == "missing":
        next((complete / "cases").glob("*.json.gz")).unlink()
    else:
        (complete / "unregistered.txt").write_text("unexpected")
    with pytest.raises(ValueError, match="inventory"):
        runner.verify(complete, replay=False)


def test_incentive_requires_ecology_and_supports_bound_standalone_verification(incentive):
    output, ecology = incentive
    standalone = runner.verify(output, replay=False)
    linked = runner.verify(output, replay=False, ecology=ecology)
    assert standalone["ecology_original_verified"] is False
    assert linked["ecology_original_verified"] is True
    assert linked["episodes"] == 48
    assert runner.read_json(output / "ecology-input.json")["summary"] == runner.read_json(ecology / "summary.json")
    with pytest.raises(ValueError, match="dependency is not ecology"):
        runner._ecology_input(output, verify_dependency=True)


def test_incentive_refuses_missing_ecology_before_cases(tmp_path, miniature):
    output = tmp_path / "incentive"
    runner.prepare(output, "incentive")
    with pytest.raises(ValueError, match="separately completed ecology"):
        runner.run(output)
    assert not list((output / "cases").iterdir())


def test_copied_ecology_summary_hash_is_checked_even_without_original(incentive):
    output, _ = incentive
    dependency = runner.read_json(output / "ecology-input.json")
    dependency["summary"]["qualification_status"] = "invented"
    write_json(output / "ecology-input.json", dependency)
    reseal(output)
    with pytest.raises(ValueError, match="copied ecology summary binding"):
        runner.verify(output, replay=False)


def test_parallel_and_serial_synthetic_banks_are_byte_identical(tmp_path, miniature):
    serial, parallel = tmp_path / "serial", tmp_path / "parallel"
    runner.prepare(serial, "ecology")
    runner.prepare(parallel, "ecology")
    runner.run(serial, workers=1)
    runner.run(parallel, workers=2)
    assert tree_bytes(serial) == tree_bytes(parallel)
    assert runner.verify(parallel, workers=2)["semantic_replay"] is True


@pytest.mark.parametrize("workers", [False, 0, 17, 1.0])
def test_invalid_worker_counts_do_not_begin_cases(prepared, workers):
    with pytest.raises(ValueError, match="workers"):
        runner.run(prepared, workers=workers)
    assert not list((prepared / "cases").iterdir())
