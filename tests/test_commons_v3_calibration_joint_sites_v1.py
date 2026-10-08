"""Joint G2 engineering fixtures; never execute the fixed calibration panel."""
from copy import deepcopy
from dataclasses import asdict
import json
import math

import pytest

from swarm_societies.commons_v3 import calibration_joint_sites_v1 as calibration
from swarm_societies.commons_v3.messages_sites_v1 import GrowthEvidence


def test_joint_design_counts_independent_sequences_and_separates_correlated_site_families():
    design = calibration.criteria()
    assert design["independent_sequences"] == 512
    assert design["sites_per_sequence"] == 3
    assert design["horizon_per_site"] == 16
    assert design["checkpoints"] == [1, 8, 16]
    assert design["DKW_family_size"] == 21
    assert design["DKW_epsilon"] == pytest.approx(math.sqrt(math.log(4200.) / 1024.))
    assert design["rate_prior"]["shared_across_sites"]
    assert design["capacity_prior"]["independent_by_site"]
    assert design["initial_stock"]["independent_of_capacity_and_rate"]
    assert design["reference_CDF_absolute_tolerance"] == .002
    assert design["no_scientific_arms"]


def test_generator_is_replayable_with_one_global_rate_and_exogenous_stock():
    first, second = calibration.synthetic_sequence(42), calibration.synthetic_sequence(43)
    assert first == calibration.synthetic_sequence(42)
    assert first["rate"] != second["rate"]
    assert first["capacities"] != second["capacities"]
    assert first["initial_stock"] == second["initial_stock"] == 7.5
    assert calibration.synthetic_sequence(42, horizon=8)["transitions"] == first["transitions"][:8]
    for frame in first["transitions"]:
        assert [row[0] for row in frame] == [0, 1, 2]
        for site, z, y, weather, clipped in frame:
            expected = z + weather * (first["rate"] * z * (1. - z / first["capacities"][site]) + .02)
            assert y == min(first["capacities"][site], expected)
            assert clipped is (expected >= first["capacities"][site])
    transitions = [row for seed in range(40, 50) for frame in calibration.synthetic_sequence(seed)["transitions"]
                   for row in frame]
    assert any(row[4] for row in transitions)
    assert any(not row[4] for row in transitions)


@pytest.mark.parametrize("seed,horizon", [(-1, 16), (True, 16), (42, 0), (42, 17)])
def test_generator_rejects_invalid_requests(seed, horizon):
    with pytest.raises(ValueError):
        calibration.synthetic_sequence(seed, horizon)


def test_calibration_api_receives_events_and_bounds_without_truth_or_weather(monkeypatch):
    calls = []
    original_class, original_generator = calibration.JointPosterior, calibration.synthetic_sequence

    class Recorder(original_class):
        def update_event(self, event):
            assert type(event) is GrowthEvidence
            calls.append(asdict(event))
            return super().update_event(event)

    monkeypatch.setattr(calibration, "JointPosterior", Recorder)
    monkeypatch.setattr(calibration, "synthetic_sequence", lambda seed: original_generator(seed, horizon=2))
    monkeypatch.setattr(calibration, "CHECKPOINTS", (1, 2))
    case = calibration.run_case(42)
    assert len(calls) == 6
    assert all(set(row) == {"site", "tick", "z", "stock_next"} for row in calls)
    assert [row["site"] for row in calls] == [0, 1, 2] * 2
    assert len(case["checkpoints"]) == 2
    assert len(case["posterior_memory_sha256"]) == 64
    for point in case["checkpoints"]:
        assert 0. <= point["rate_rank"] <= 1.
        for site in point["sites"]:
            assert 0. <= site["posterior_rank"] <= 1.
            assert 0. <= site["predictive_rank"] <= 1.


def test_independent_reference_integrates_exact_capacity_atoms_and_continuous_rate():
    for rate in (.12, .16, .24, .36, .48):
        # Repeated saturation pins K but carries no information about r.
        assert calibration.reference_cdf(20., 20., rate, variable="rate") == pytest.approx(
            math.log(rate / .12) / math.log(4.), abs=1e-11)
    assert calibration.reference_cdf(20., 20., 20., left=True) == 0.
    assert calibration.reference_cdf(20., 20., 20.) == 1.
    assert calibration.reference_cdf(20., 20.027, 20.027, left=True) == 0.
    atom = calibration.reference_cdf(20., 20.027, 20.027)
    assert 0. < atom < 1.
    assert calibration.reference_cdf(20., 20.027, 100.) == 1.
    assert calibration.reference_cdf(20., 20.027, .48, variable="rate") == 1.


def test_production_joint_update_matches_independent_reference():
    checks = calibration.reference_checks()
    assert checks["passed"]
    assert checks["maximum_absolute_CDF_error"] <= .002
    assert checks["maximum_CDF_change_from_bound_only"] > .05
    assert checks["repeated_saturation_exact_atom"]


def _fake_case(seed, rank):
    summary = {"inclusive90_covered": True, "absolute_log_median_error": 0., "log_interval_width": .1}
    return {"seed": seed, "transitions": [[[0, 7.5, 8., 1., False], [1, 20., 20., 1., True]]],
        "checkpoints": [{"tick": tick, "rate_rank": rank, "rate_randomized90_covered": .05 <= rank <= .95,
            "rate": summary, "sites": [{"site": site, "posterior_rank": rank, "predictive_rank": rank,
                "randomized90_covered": .05 <= rank <= .95, "posterior": summary}
                for site in range(calibration.SITES)]} for tick in calibration.CHECKPOINTS]}


def test_gate_checks_rate_each_capacity_predictive_and_independent_reference():
    cases = [_fake_case(seed, (index + .5) / len(calibration.SEEDS))
             for index, seed in enumerate(calibration.SEEDS)]
    assert calibration.summarize(cases, {"passed": True})["G2"]["passed"]
    for field in ("rate_rank", "posterior_rank", "predictive_rank"):
        damaged = deepcopy(cases)
        for case in damaged:
            record = case["checkpoints"][1]
            if field == "rate_rank":
                record[field] = 0.
            else:
                record["sites"][2][field] = 0.
        assert not calibration.summarize(damaged, {"passed": True})["G2"]["passed"]
    assert not calibration.summarize(cases, {"passed": False})["G2"]["passed"]


def test_gate_requires_500_independent_sequences_not_just_correlated_transitions(monkeypatch):
    monkeypatch.setattr(calibration, "SEEDS", (42, 43))
    cases = [_fake_case(seed, rank) for seed, rank in ((42, .25), (43, .75))]
    for case in cases:
        case["transitions"] *= 1000
    result = calibration.summarize(cases, {"passed": True})
    assert result["transitions"] == 4000
    assert not result["G2"]["passed"]


def test_completed_calibration_is_not_reexecuted(monkeypatch, tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    monkeypatch.setattr(calibration, "_cases", lambda _: pytest.fail("completed calibration executed again"))
    with pytest.raises(ValueError, match="completed calibration"):
        calibration.run(tmp_path)


def test_progress_logging_preserves_records_order_and_criteria(monkeypatch, capsys):
    monkeypatch.setattr(calibration, "SEEDS", tuple(range(42, 77)))
    monkeypatch.setattr(calibration, "run_case", lambda seed: {"seed": seed})
    before = calibration.criteria()
    assert calibration._cases(1) == [{"seed": seed} for seed in calibration.SEEDS]
    assert calibration.criteria() == before
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.splitlines() == ["joint calibration progress 16/35 sequences",
                                      "joint calibration progress 32/35 sequences",
                                      "joint calibration progress 35/35 sequences"]


def test_saved_calibration_loader_requires_matching_complete_passing_aggregate(monkeypatch, tmp_path):
    cases = [_fake_case(seed, (index + .5) / len(calibration.SEEDS))
             for index, seed in enumerate(calibration.SEEDS)]
    monkeypatch.setattr(calibration, "_cases", lambda _: cases)
    monkeypatch.setattr(calibration, "reference_checks", lambda: {"passed": True})
    saved = calibration.run(tmp_path)
    loaded = calibration.load_passed(tmp_path)
    assert loaded["G2"]["passed"]
    assert loaded["summary_sha256"] == calibration.digest(saved)
    assert calibration.verify(tmp_path)["summary_sha256"] == loaded["summary_sha256"]
    evidence = json.loads((tmp_path / "cases.json").read_text())
    evidence["cases"][0]["checkpoints"][0]["rate_rank"] = 0.
    (tmp_path / "cases.json").write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="aggregate differs"):
        calibration.load_passed(tmp_path)
    with pytest.raises(ValueError, match="exact synthetic sequence"):
        calibration.verify(tmp_path)


def test_loader_rejects_failed_gate_even_with_self_consistent_saved_summary(monkeypatch, tmp_path):
    cases = [_fake_case(seed, 0.) for seed in calibration.SEEDS]
    monkeypatch.setattr(calibration, "_cases", lambda _: cases)
    monkeypatch.setattr(calibration, "reference_checks", lambda: {"passed": True})
    assert not calibration.run(tmp_path)["G2"]["passed"]
    with pytest.raises(ValueError, match="G2 has not passed"):
        calibration.load_passed(tmp_path)


@pytest.mark.parametrize("workers", [0, 9, True])
def test_worker_limits_are_explicit(workers):
    with pytest.raises(ValueError):
        calibration._cases(workers)
