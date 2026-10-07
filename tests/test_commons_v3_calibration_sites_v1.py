"""Small synthetic fixtures only; the fixed G2 sequence panel is not a test."""
from copy import deepcopy
from dataclasses import asdict
import json
import math

import pytest

from swarm_societies.commons_v3 import calibration_sites_v1 as calibration
from swarm_societies.commons_v3.evidence_sites_v1 import CleanTransition


def test_fixed_simultaneous_design_counts_sequences_not_correlated_transitions():
    design = calibration.criteria()
    assert design["independent_sequences"] == 1024
    assert design["horizon"] == 64
    assert design["checkpoints"] == [1, 16, 32, 64]
    assert design["DKW_family_size"] == 8
    assert design["DKW_epsilon"] == pytest.approx(math.sqrt(math.log(1600.) / 2048.))
    assert design["initial_stock"]["independent_of_capacity"]
    assert design["no_scientific_arms"]


def test_generator_is_replayable_and_exogenous_initial_stock_is_not_capacity_scaled():
    first, second = calibration.synthetic_sequence(42), calibration.synthetic_sequence(43)
    assert first == calibration.synthetic_sequence(42)
    assert first["capacity"] != second["capacity"]
    assert first["initial_stock"] == second["initial_stock"] == 1.
    assert first["initial_stock"] < 8.
    assert calibration.synthetic_sequence(42, horizon=16)["transitions"] == first["transitions"][:16]
    assert any(row[3] for row in first["transitions"])
    assert any(not row[3] for row in first["transitions"])
    for z, y, weather, clipped in first["transitions"]:
        expected = z + weather * (.24 * z * (1 - z / first["capacity"]) + .02)
        assert y == min(first["capacity"], expected)
        assert clipped is (expected >= first["capacity"])


def test_calibration_passes_only_ordinary_clean_evidence_to_posterior(monkeypatch):
    calls = []
    original = calibration.SitePosterior

    class Recorder(original):
        def update(self, event):
            assert type(event) is CleanTransition
            calls.append(asdict(event))
            return super().update(event)

    monkeypatch.setattr(calibration, "SitePosterior", Recorder)
    case = calibration.run_case(42)
    assert len(calls) == 64
    assert all(set(row) == {"site", "tick", "z", "stock_next", "stock_before", "own_harvest"}
               for row in calls)
    assert all(row["z"] == row["stock_before"] and row["own_harvest"] == 0 for row in calls)
    saturated = case["checkpoints"][-1]
    assert saturated["posterior_CDF"] == [0., 1.]
    assert 0. < saturated["posterior_rank"] < 1.
    assert saturated["posterior"]["inclusive90_covered"]
    assert saturated["posterior"]["log_interval_width"] == 0.
    assert saturated["bound_only"]["log_interval_width"] > 0.


def test_independent_reference_has_continuous_and_off_grid_atom_components():
    z, y = 20., 20.027
    assert calibration.reference_cdf(z, y, y, left=True) == 0.
    atom = calibration.reference_cdf(z, y, y)
    assert 0. < atom < 1.
    assert calibration.reference_cdf(z, y, 100.) == pytest.approx(1.)
    assert calibration.reference_cdf(y, y, y, left=True) == 0.
    assert calibration.reference_cdf(y, y, y) == 1.


def test_production_update_agrees_with_independent_reference_and_uses_evidence():
    checks = calibration.reference_checks()
    assert checks["passed"]
    assert checks["maximum_absolute_CDF_error"] <= calibration.REFERENCE_TOLERANCE
    assert checks["maximum_CDF_change_from_bound_only"] > .05
    assert checks["repeated_saturation_exact_atom"]


def test_empirical_distance_checks_both_sides_of_each_observed_rank():
    assert calibration.empirical_uniform_distance([.125, .375, .625, .875]) == .125
    assert calibration.empirical_uniform_distance([0., 0., 0.]) == 1.
    assert calibration.empirical_uniform_distance([1., 1., 1.]) == 1.
    for invalid in ([], [-.1], [1.1], [math.nan]):
        with pytest.raises(ValueError):
            calibration.empirical_uniform_distance(invalid)


def _fake_case(seed, rank):
    posterior = {"median": 20., "interval90": [15., 25.], "inclusive90_covered": True,
                 "absolute_log_median_error": 0., "log_interval_width": math.log(25. / 15.)}
    return {"seed": seed, "capacity": 20., "transitions": [[1., 1.2, 1., False], [20., 20., 1., True]] * 32,
            "checkpoints": [{"tick": tick, "posterior_rank": rank, "predictive_rank": rank,
                "randomized90_covered": .05 <= rank <= .95,
                "posterior": posterior, "bound_only": posterior} for tick in calibration.CHECKPOINTS]}


def test_gate_requires_every_posterior_and_predictive_checkpoint_and_reference():
    cases = [_fake_case(seed, (index + .5) / len(calibration.SEEDS))
             for index, seed in enumerate(calibration.SEEDS)]
    assert calibration.summarize(cases, {"passed": True})["G2"]["passed"]
    for field in ("posterior_rank", "predictive_rank"):
        damaged = deepcopy(cases)
        for case in damaged:
            case["checkpoints"][2][field] = 0.
        assert not calibration.summarize(damaged, {"passed": True})["G2"]["passed"]
    assert not calibration.summarize(cases, {"passed": False})["G2"]["passed"]


def test_run_refuses_completed_output_without_reexecuting(monkeypatch, tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    monkeypatch.setattr(calibration, "_cases", lambda _: pytest.fail("completed calibration executed again"))
    with pytest.raises(ValueError, match="completed calibration"):
        calibration.run(tmp_path)


def test_small_fixture_exact_replay_and_changed_evidence_detection(monkeypatch, tmp_path):
    # These two synthetic unit seeds are outside the fixed G2 panel.
    monkeypatch.setattr(calibration, "SEEDS", (42, 43))
    saved = calibration.run(tmp_path, workers=1)
    assert not saved["G2"]["passed"]  # Only 128 transitions; never a G2 pass.
    replay = calibration.verify(tmp_path, workers=1)
    assert replay["exact_sequences"] == 2
    path = tmp_path / "cases.json"
    case_bytes = path.read_bytes()
    evidence = json.loads(case_bytes)
    evidence["cases"][0]["transitions"][0][2] += .001
    path.write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="exact synthetic sequence"):
        calibration.verify(tmp_path, workers=1)


@pytest.mark.parametrize("workers", [0, 9, True])
def test_worker_limits_are_explicit(workers):
    with pytest.raises(ValueError):
        calibration._cases(workers)
