"""Numerical-selection separation, replay and artifact-preservation regressions."""
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import json
import subprocess
import sys

import pytest

from swarm_societies.commons_v3 import development_navigation_v1 as dev
from swarm_societies.commons_v3 import development_need_v1 as previous
from swarm_societies.commons_v3.engine import Config


def tiny_design():
    specification = dev.design()
    specification["candidates"] = [specification["candidates"][0], specification["candidates"][-1]]
    cfg = Config(width=3, height=3, n_agents=2, n_patches=1, need=.3, initial_patch_stock=30.)
    for phase, seeds in (("tuning", [900101, 900102]), ("evaluation", [901101, 901102])):
        specification[phase]["seeds"] = seeds
        specification[phase]["cases"] = [{"id": f"{phase}-{index}", "panel": "grid", "seed": seed,
                                           "focal_id": index, "horizon": 8, "config": asdict(cfg)}
                                          for index, seed in enumerate(seeds)]
    specification["evaluation"]["reference_frames_case"] = "evaluation-0"
    return specification


@pytest.fixture
def specification(monkeypatch):
    value = tiny_design()
    monkeypatch.setattr(dev, "design", lambda: deepcopy(value))
    return value


@pytest.fixture
def tuned(tmp_path, specification):
    output = tmp_path / "navigation"
    dev.prepare(output)
    dev.tune(output)
    return output


@pytest.fixture
def complete(tuned):
    dev.evaluate(tuned)
    return tuned


def test_declared_budget_and_disjoint_seeds_preserve_physical_case_templates():
    design = dev.design()
    assert len(design["candidates"]) == 18
    assert len({row["id"] for row in design["candidates"]}) == 18
    assert len(design["tuning"]["cases"]) == 18
    assert len(design["evaluation"]["cases"]) == 56
    assert set(design["tuning"]["seeds"]).isdisjoint(design["evaluation"]["seeds"])
    assert set(design["evaluation"]["seeds"]).isdisjoint({61001, 61002, 61003, 61004})
    assert dev.CONDITIONS == ("legacy_need2", "fixed_forager", "fixed_floor", "selected", "focal_aggressive_selected", "all_aggressive")
    assert 18 * len(design["tuning"]["cases"]) + 6 * len(design["evaluation"]["cases"]) == 660
    ticks = 18 * sum(case["horizon"] for case in design["tuning"]["cases"]) + 6 * sum(case["horizon"] for case in design["evaluation"]["cases"])
    assert ticks == 175104 and ticks * 24 == 4202496
    for old, new in zip(previous.design()["cases"], design["evaluation"]["cases"]):
        for field in ("panel", "horizon", "config", "focal_id"):
            assert dev.canonical(old[field]) == dev.canonical(new[field])
    assert design["qualification_data"] is False
    assert design["experimental_model_calls"] == design["evolutionary_runs"] == 0


def test_population_aggressive_bundle_matches_selected_navigation_and_peers():
    selected = dev.candidates()[-1]
    kinds, policies = dev.population("focal_aggressive_selected", 4, 1, selected=selected)
    assert kinds == ("selected", "aggressive", "selected", "selected")
    for index, policy in enumerate(policies):
        assert policy.aggressive is (index == 1)
        assert policy.reserve_ticks == selected["parameters"]["reserve_ticks"]
        assert policy.stock_floor_fraction == selected["parameters"]["stock_floor_fraction"]
        assert policy.route_mode == selected["parameters"]["route_mode"]
    with pytest.raises(ValueError, match="missing selected"):
        dev.population("selected", 4, 1)
    with pytest.raises(ValueError, match="two agents"):
        dev.population("fixed_forager", 1, 0)


def test_tuning_selection_is_normalized_uses_late_then_stable_ties(specification):
    # Candidate A wins raw consumption, B wins consumption divided by need.
    a, b = specification["candidates"]
    cases = deepcopy(specification["tuning"]["cases"])
    cases[0]["config"]["need"], cases[1]["config"]["need"] = 1., 10.
    specification["tuning"]["cases"] = cases
    def records(values, late):
        return [{"case": case, "candidate": candidate, "episode": {
            "weather_sha256": str(case["seed"]), "summary": {
                "consumption_per_agent_tick": values[index][candidate["id"]],
                "late_consumption_per_agent_tick": late[index][candidate["id"]], "max_ledger_residual": 0.}}}
                for index, case in enumerate(cases) for candidate in (a, b)]
    values = [{a["id"]: 0., b["id"]: 1.}, {a["id"]: 10., b["id"]: 2.}]
    assert dev.tuning_summary(records(values, values), specification)["selected_candidate_id"] == b["id"]
    tie = [{a["id"]: 1., b["id"]: 1.}, {a["id"]: 10., b["id"]: 10.}]
    late = [{a["id"]: 0., b["id"]: 1.}, {a["id"]: 10., b["id"]: 10.}]
    assert dev.tuning_summary(records(tie, late), specification)["selected_candidate_id"] == b["id"]
    assert dev.tuning_summary(records(tie, tie), specification)["selected_candidate_id"] == min(a["id"], b["id"])
    with pytest.raises(ValueError, match="inventory"):
        dev.tuning_summary(records(tie, tie)[:-1], specification)
    broken = records(tie, tie)
    broken[0]["episode"]["weather_sha256"] = "different"
    with pytest.raises(ValueError, match="weather"):
        dev.tuning_summary(broken, specification)


def test_tuning_seals_binding_without_executing_evaluation(tuned, specification, monkeypatch):
    assert not list((tuned / "evaluation/cases").iterdir())
    assert not (tuned / "manifest.json").exists()
    selection = json.loads((tuned / "selection.json").read_text())
    assert selection["tuning_manifest_sha256"] == dev.sha(tuned / "tuning/manifest.json")
    assert selection["evaluation_spec_sha256"] == dev.digest(specification["evaluation"])
    assert selection["design_sha256"] == dev.sha(tuned / "design.json")
    assert selection["sources_sha256"] == dev.sha(tuned / "sources.json")
    pins = json.loads((tuned / "sources.json").read_text())
    assert selection["selected_policy_sha256"] == dev.digest({"source_sha256": pins[dev.POLICY_SOURCE],
               "parameters": selection["candidate"]["parameters"], "aggressive": False})
    monkeypatch.setattr(dev, "evaluation_record", lambda *args: pytest.fail("tuning verifier reached holdout"))
    assert dev.verify(tuned, phase="tuning")["tuning_semantic_replay"] is True
    with pytest.raises(FileExistsError, match="completed tuning"):
        dev.tune(tuned)


def test_evaluate_requires_sealed_tuning(tmp_path, specification):
    output = tmp_path / "unfitted"
    dev.prepare(output)
    with pytest.raises(FileNotFoundError):
        dev.evaluate(output)
    assert not list((output / "evaluation/cases").iterdir())


def test_complete_bank_replays_both_phases_and_preserves_all_artifacts(complete):
    receipt = dev.verify(complete)
    assert receipt["verified"] is receipt["tuning_semantic_replay"] is receipt["evaluation_semantic_replay"] is True
    assert receipt["tuning_episodes"] == 4 and receipt["evaluation_episodes"] == 12
    assert receipt["episodes"] == 16 and receipt["physical_ticks"] == 128 and receipt["agent_decisions"] == 256
    manifest = json.loads((complete / "manifest.json").read_text())
    assert set(manifest["artifacts_sha256"]) == dev.expected_artifacts(dev.design())
    record = dev.read_case(complete / "evaluation/cases/evaluation-0.json.gz")
    assert len({row["weather_sha256"] for row in record["episodes"]}) == 1
    assert all(row["checkpoint_continuation_checked"] for row in record["episodes"])
    for episode in record["episodes"]:
        for row in episode["trajectory"]:
            assert 0 <= row["hungry_off_site_agents"] <= row["off_site_agents"] <= 2
            assert 0 <= row["unoccupied_stock_fraction"] <= 1
            assert 0 <= row["mean_known_sites"] <= 1
        assert episode["summary"]["max_unaffordable_known_returns"] == 0
    for operation in (dev.tune, dev.evaluate):
        with pytest.raises(FileExistsError, match="completed"):
            operation(complete)


def test_evaluation_verifier_never_replays_tuning(complete, monkeypatch):
    monkeypatch.setattr(dev, "tuning_record", lambda *args: pytest.fail("unexpected tuning simulation"))
    receipt = dev.verify(complete, phase="evaluation")
    assert receipt["tuning_semantic_replay"] is False and receipt["evaluation_semantic_replay"] is True


def test_aggregate_paired_focal_and_selected_contrasts(specification):
    selected = specification["candidates"][0]
    records = [dev.evaluation_record(case, specification, selected) for case in specification["evaluation"]["cases"]]
    # Replace outcomes with independent arithmetic fixtures, keeping the
    # agent identity rotation explicit across the two cases.
    assigned = {"legacy_need2": (1., 3.), "fixed_forager": (2., 4.), "fixed_floor": (3., 5.),
                "selected": (4., 6.), "focal_aggressive_selected": (7., 2.), "all_aggressive": (1., 1.)}
    for record in records:
        focal = record["case"]["focal_id"]
        for episode in record["episodes"]:
            first, other = assigned[episode["condition"]]
            episode["summary"]["consumption_per_agent_tick"] = (first + other) / 2
            for agent in episode["agents"]:
                value = first if agent["id"] == focal else other
                agent["consumption_per_tick"] = value
                agent["late_consumption_per_tick"] = value / 2
                agent["terminal_inventory"] = value
                agent["utility"] = {str(w): value + w * value / record["case"]["horizon"] for w in dev.WEIGHTS}
    cell = dev.aggregate(records, specification)["cells"][0]
    assert cell["selected_minus_fixed"]["legacy_need2"]["consumption_per_agent_tick"]["mean"] == 3.
    assert cell["selected_minus_fixed"]["fixed_floor"]["consumption_per_agent_tick"]["mean"] == 1.
    assert cell["focal_deviation"]["consumption"]["mean"] == 3.
    assert cell["focal_deviation"]["peer_consumption"]["mean"] == -4.
    assert cell["focal_deviation"]["world_consumption"]["mean"] == -.5
    assert cell["focal_deviation"]["utility_0.05"]["mean"] == pytest.approx(3.01875)
    assert cell["all_aggressive_minus_selected"]["consumption_per_agent_tick"]["mean"] == -4.


@pytest.mark.parametrize("phase", ["tuning", "evaluation"])
def test_interrupted_phases_replay_existing_cases_without_rewriting(tmp_path, specification, monkeypatch, phase):
    output = tmp_path / "interrupted"
    dev.prepare(output)
    if phase == "evaluation":
        dev.tune(output)
    function_name = "tuning_record" if phase == "tuning" else "evaluation_record"
    original = getattr(dev, function_name)
    calls = 0
    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("external stop")
        return original(*args)
    monkeypatch.setattr(dev, function_name, interrupted)
    operation = dev.tune if phase == "tuning" else dev.evaluate
    with pytest.raises(KeyboardInterrupt):
        operation(output)
    files = list((output / phase / "cases").glob("*.json.gz"))
    assert len(files) == 1
    saved = files[0]
    before = saved.read_bytes(), saved.stat().st_mtime_ns
    assert not list(output.glob("*-failure.json"))
    monkeypatch.setattr(dev, function_name, original)
    operation(output)
    assert (saved.read_bytes(), saved.stat().st_mtime_ns) == before
    assert dev.verify(output, phase=phase)["verified"] is True


def test_interrupted_selection_publication_recovers_without_changing_tuning(tuned):
    manifest = (tuned / "tuning/manifest.json").read_bytes()
    before = (tuned / "selection.json").read_bytes()
    (tuned / "selection.json").unlink()
    dev.tune(tuned)
    assert (tuned / "selection.json").read_bytes() == before
    assert (tuned / "tuning/manifest.json").read_bytes() == manifest


def rehash(bank, phase, relative):
    path = bank / ("tuning/manifest.json" if phase == "tuning" else "manifest.json")
    value = json.loads(path.read_text())
    value["artifacts_sha256"][relative] = dev.sha(bank / relative)
    path.write_bytes(dev.canonical(value) + b"\n")


@pytest.mark.parametrize("target", ["tuning_case", "evaluation_case", "tuning_summary", "summary", "tuning_manifest", "manifest", "selection"])
def test_rehashed_boolean_number_and_selection_tampering_is_detected(complete, target):
    phase = "tuning" if target.startswith("tuning") else "evaluation"
    if target.endswith("case"):
        path = next((complete / phase / "cases").glob("*.json.gz"))
        value = dev.read_case(path)
        episode = value["episode"] if phase == "tuning" else value["episodes"][0]
        assert episode["trajectory"][0]["waste"] == 0.
        episode["trajectory"][0]["waste"] = False
        with gzip.open(path, "wb") as stream:
            stream.write(dev.canonical(value))
        rehash(complete, phase, str(path.relative_to(complete)))
    elif target.endswith("summary"):
        relative = "tuning/summary.json" if phase == "tuning" else "summary.json"
        value = json.loads((complete / relative).read_text())
        value["experimental_model_calls"] = False
        (complete / relative).write_bytes(dev.canonical(value) + b"\n")
        rehash(complete, phase, relative)
    elif target.endswith("manifest"):
        path = complete / ("tuning/manifest.json" if phase == "tuning" else "manifest.json")
        value = json.loads(path.read_text())
        value["complete"] = 1
        path.write_bytes(dev.canonical(value) + b"\n")
    else:
        path = complete / "selection.json"
        value = json.loads(path.read_text())
        value["candidate"]["parameters"]["reserve_ticks"] = 2
        value["evaluation_spec_sha256"] = "0" * 64
        path.write_bytes(dev.canonical(value) + b"\n")
        rehash(complete, "evaluation", "selection.json")
    with pytest.raises(ValueError, match="replay|aggregate|manifest|selection"):
        dev.verify(complete, phase=phase)


@pytest.mark.parametrize("damage", ["missing", "extra", "source", "design"])
def test_missing_extra_or_changed_inputs_fail(complete, damage):
    if damage == "missing":
        (complete / "evaluation/cases/evaluation-0.json.gz").unlink()
    elif damage == "extra":
        (complete / "unexpected.json").write_text("{}")
    elif damage == "source":
        (complete / "sources" / dev.SOURCES[0]).write_text("changed")
    else:
        value = json.loads((complete / "design.json").read_text())
        value["evaluation"]["cases"][0]["seed"] += 1
        (complete / "design.json").write_bytes(dev.canonical(value))
    with pytest.raises(ValueError, match="inventory|source changed|design changed"):
        dev.verify(complete, phase="evaluation")


@pytest.mark.parametrize("phase", ["tuning", "evaluation"])
def test_failures_preserve_receipts_and_forbid_retry_into_completion(tmp_path, specification, monkeypatch, phase):
    output = tmp_path / "failed"
    dev.prepare(output)
    if phase == "evaluation":
        dev.tune(output)
    def fail(*args):
        raise ArithmeticError("injected accounting failure")
    monkeypatch.setattr(dev, "tuning_record" if phase == "tuning" else "evaluation_record", fail)
    operation = dev.tune if phase == "tuning" else dev.evaluate
    with pytest.raises(ArithmeticError):
        operation(output)
    path = next(output.glob("*-failure.json"))
    before = path.read_bytes()
    with pytest.raises(FileExistsError, match="failed"):
        operation(output)
    assert path.read_bytes() == before
    assert not (output / "manifest.json").exists()


def test_holdout_cannot_rebind_a_modified_selection(tuned, monkeypatch):
    path = tuned / "selection.json"
    value = json.loads(path.read_text())
    value["evaluation_spec_sha256"] = "0" * 64
    path.write_bytes(dev.canonical(value) + b"\n")
    monkeypatch.setattr(dev, "evaluation_record", lambda *args: pytest.fail("modified selection reached evaluation"))
    with pytest.raises(ValueError, match="existing JSON differs"):
        dev.evaluate(tuned)
    assert not list((tuned / "evaluation/cases").iterdir())


def test_cli_exposes_staged_work_without_data_download():
    result = subprocess.run([sys.executable, str(dev.ROOT / "scripts/run_commons_v3_navigation_v1.py"), "--help"],
                            text=True, capture_output=True, check=True)
    assert "prepare,tune,evaluate,verify" in result.stdout
    assert "--phase" in result.stdout
