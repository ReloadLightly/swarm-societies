"""Scientific controls for the numerical renewal learner, independent of ecology."""

import json
import math

import numpy as np
import pytest
from scipy.integrate import quad

from swarm_societies.world_model_v1 import RenewalSMC, empirical_crps
from swarm_societies.world_model_v1.learner import _log_likelihood


def packet(event_id, growth, own=0.0, other=0.0, headroom=80.0):
    return {"event_id": str(event_id), "growth": growth, "capacity": 80.0,
            "stock_before": 80.0 - headroom, "own_infrastructure": own,
            "other_infrastructure": other, "sensor_sigma": 0.05}


@pytest.mark.parametrize("headroom,observed", [(20.0, 7.7), (7.9, 7.91), (7.3, 7.28), (0.0, -0.03)])
def test_density_matches_numerical_weather_integration(headroom, observed):
    parameters = np.array([[4.8, 1.6, 0.4]])
    sigma, own, other = 0.05, 1.5, 2.0
    def integrand(weather):
        true_growth = min(headroom, 4.8 * weather + 1.6 * own + 0.4 * other)
        z = (observed - true_growth) / sigma
        return math.exp(-0.5 * z*z) / (0.3 * sigma * math.sqrt(2*math.pi))
    cap_weather = (headroom - 1.6 * own - 0.4 * other) / 4.8
    points = [cap_weather] if 0.85 < cap_weather < 1.15 else None
    reference, _ = quad(integrand, 0.85, 1.15, points=points, epsabs=1e-12)
    actual = math.exp(_log_likelihood(parameters, headroom, own, other, observed, sigma)[0])
    assert actual == pytest.approx(reference, rel=1e-9, abs=1e-12)


def test_density_remains_finite_in_extreme_gaussian_tails():
    parameters = np.array([[4.8, 1.6, 0.4], [3.0, 2.1, 0.7]])
    for observed in (-100.0, 100.0):
        likelihood = _log_likelihood(parameters, 80.0, 1.0, 2.0, observed, 0.05)
        assert np.all(np.isfinite(likelihood))


def test_identifiable_stream_recovers_planted_parameters_and_generalizes():
    rng = np.random.default_rng(314)
    learner = RenewalSMC(seed=82, n_particles=1024, rejuvenation_steps=3)
    initial = learner.summary()
    for tick in range(160):
        own, other = rng.uniform(0.0, 6.0, 2)
        growth = (4.8 * rng.uniform(0.85, 1.15) + 1.6 * own + 0.4 * other
                  + rng.normal(0.0, 0.05))
        assert learner.update(packet(tick, growth, own, other))["status"] == "updated"
    result = learner.summary()
    truth = {"r": 4.8, "b": 1.6, "g": 0.4}
    for index, name in enumerate(truth):
        assert result["mean"][name] == pytest.approx(truth[name], abs=0.12)
        low, high = result["intervals"][name]
        assert low < truth[name] < high
        low_90, high_90 = result["intervals_90"][name]
        assert low <= low_90 <= high_90 <= high
        assert result["covariance"][index][index] < initial["covariance"][index][index] / 15
    samples = learner.predict(packet("held-out", 0, own=2.0, other=4.0), n_samples=10000, seed=519)
    assert np.mean(samples) == pytest.approx(4.8 + 1.6*2 + 0.4*4, abs=0.12)
    assert result["diagnostics"]["resampling_events"] > 0
    assert result["diagnostics"]["rejuvenation_accepts"] > 0


def test_confounded_features_retain_uncertainty_along_parameter_ridge():
    rng = np.random.default_rng(27)
    learner = RenewalSMC(seed=98, n_particles=1024, rejuvenation_steps=3)
    for tick in range(100):
        shared_feature = rng.uniform(0.0, 6.0)
        growth = 4.8*rng.uniform(0.85, 1.15) + 2.0*shared_feature + rng.normal(0, 0.05)
        learner.update(packet(tick, growth, shared_feature, shared_feature))
    result = learner.summary()
    covariance = np.asarray(result["covariance"])
    correlation = covariance[1, 2] / math.sqrt(covariance[1, 1] * covariance[2, 2])
    assert correlation < -0.9
    assert result["mean"]["b"] + result["mean"]["g"] == pytest.approx(2.0, abs=0.08)
    assert result["intervals"]["g"][1] - result["intervals"]["g"][0] > 0.5


def test_fully_saturated_evidence_is_accepted_but_cannot_identify_parameters():
    learner = RenewalSMC(seed=17, n_particles=512)
    initial_particles = learner.particles.copy()
    initial_summary = learner.summary()
    for tick in range(20):
        assert learner.update(packet(tick, 0.01, own=4, other=3, headroom=0))["status"] == "updated"
    assert np.array_equal(learner.particles, initial_particles)
    assert learner.summary()["mean"] == pytest.approx(initial_summary["mean"])
    assert learner.summary()["n_observations"] == 20
    assert learner.summary()["diagnostics"]["resampling_events"] == 0


def test_prediction_is_read_only_and_snapshot_reproduces_future_learning():
    learner = RenewalSMC(seed=71, n_particles=128)
    learner.update(packet("first", 7.0, 1, 2))
    snapshot = json.loads(json.dumps(learner.snapshot(), allow_nan=False))
    restored = RenewalSMC.from_snapshot(snapshot)
    query = packet("probe", 0, 2, 1)
    first_prediction = learner.predict(query, seed=912)
    assert first_prediction == restored.predict(query, seed=912)
    assert learner.snapshot() == snapshot
    assert restored.snapshot() == snapshot
    next_observation = packet("second", 10.0, 2, 3)
    assert learner.update(next_observation) == restored.update(next_observation)
    assert learner.snapshot() == restored.snapshot()
    learner.restore(snapshot)
    assert learner.snapshot() == snapshot


def test_rejuvenated_particles_retain_full_static_parameter_likelihood():
    learner = RenewalSMC(seed=514, n_particles=64, ess_fraction=1.0)
    evidence = [packet("a", 5.0, 0, 0), packet("b", 10.0, 3, 1), packet("c", 7.8, 1, 4)]
    for observation in evidence:
        learner.update(observation)
    expected = np.zeros(learner.n_particles)
    for observation in evidence:
        expected += _log_likelihood(learner.particles, 80.0,
                                    observation["own_infrastructure"],
                                    observation["other_infrastructure"], observation["growth"], 0.05)
    assert learner.summary()["diagnostics"]["rejuvenation_accepts"] > 0
    np.testing.assert_allclose(learner.log_likelihood, expected, rtol=1e-12, atol=1e-12)


def test_duplicate_evidence_does_not_change_posterior_and_conflicts_are_rejected():
    learner = RenewalSMC(seed=6, n_particles=128)
    observation = packet("physical-event", 6.0, 0.5, 1)
    learner.update(observation)
    before = learner.snapshot()
    assert learner.update({**observation, "reporter": "different-member"})["status"] == "duplicate"
    after = learner.snapshot()
    assert before["particles"] == after["particles"]
    assert before["log_weights"] == after["log_weights"]
    assert len(after["evidence"]) == 1
    with pytest.raises(ValueError, match="event_id reused"):
        learner.update({**observation, "growth": 7.0})
    assert learner.summary()["diagnostics"]["failed_updates"] == 1


@pytest.mark.parametrize("change", [
    {"growth": float("nan")}, {"stock_before": -1}, {"other_infrastructure": None},
    {"sensor_sigma": 0.1}, {"event_id": ""},
])
def test_invalid_observations_never_become_evidence(change):
    learner = RenewalSMC(seed=0, n_particles=32)
    with pytest.raises(ValueError):
        learner.update({**packet("bad", 4.8), **change})
    assert learner.summary()["n_observations"] == 0
    assert learner.summary()["diagnostics"]["failed_updates"] == 1


def test_empirical_crps_matches_pairwise_definition_and_point_forecast():
    samples, target = np.array([-1.0, 0.0, 0.5, 3.0]), 1.25
    expected = np.mean(abs(samples-target)) - 0.5*np.mean(abs(samples[:, None]-samples[None, :]))
    assert empirical_crps(samples, target) == pytest.approx(expected)
    assert empirical_crps([2.0], 0.5) == 1.5
    with pytest.raises(ValueError):
        empirical_crps([], target)
