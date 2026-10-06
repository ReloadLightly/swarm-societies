"""A static-parameter SMC learner for instrumented resource renewal.

The supplied mechanism is X = min(headroom, r*W + b*I + g*J), with
W ~ Uniform(.85, 1.15), followed by the declared measurement Y=X+N(0,sigma).
The learner estimates r, b and g; it does not discover that mechanism.
Observations are full-feature measurements, not privileged weather draws.
No simulator imports or ground-truth parameter access occur in this module.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import Any

import numpy as np
from scipy.special import log_ndtr, logsumexp


PARAMETERS = ("r", "b", "g")
DEFAULT_PRIOR = {"r": (2.0, 8.0), "b": (0.5, 3.0), "g": (0.0, 0.8)}
SNAPSHOT_VERSION = "renewal-smc-v1"


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _integer(value: Any, name: str, minimum: int) -> int:
    number = _finite(value, name)
    if number != int(number) or number < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(number)


def _features(query: Mapping[str, Any]) -> tuple[float, float, float]:
    if not isinstance(query, Mapping):
        raise ValueError("query must be a mapping")
    try:
        before = _finite(query["stock_before"], "stock_before")
        capacity = _finite(query["capacity"], "capacity")
        own = _finite(query["own_infrastructure"], "own_infrastructure")
        other = _finite(query["other_infrastructure"], "other_infrastructure")
    except KeyError as exc:
        raise ValueError(f"missing required feature: {exc.args[0]}") from exc
    if capacity <= 0 or not 0 <= before <= capacity or own < 0 or other < 0:
        raise ValueError("stocks must lie within capacity and infrastructure must be nonnegative")
    return capacity - before, own, other


def _normal_interval_log_probability(lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Stable log(P(lower < Z < upper)); callers provide positive-width intervals."""
    # Positive tails are evaluated by symmetry, avoiding subtraction from 1.
    positive = lower >= 0
    log_high = log_ndtr(np.where(positive, -lower, upper))
    log_low = log_ndtr(np.where(positive, -upper, lower))
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return log_high + np.log(-np.expm1(np.minimum(0.0, log_low - log_high)))


def _log_likelihood(
    particles: np.ndarray,
    headroom: float,
    own: float,
    other: float,
    observed: float,
    sigma: float,
) -> np.ndarray:
    """Exact density of capped uniform renewal convolved with Gaussian noise."""
    base = particles[:, 0]
    lower = 0.85 * base + particles[:, 1] * own + particles[:, 2] * other
    upper = 1.15 * base + particles[:, 1] * own + particles[:, 2] * other
    width = 0.30 * base
    cap_mass = np.clip((upper - headroom) / width, 0.0, 1.0)
    log_continuous = np.full(len(particles), -np.inf)
    continuous = lower < headroom
    if np.any(continuous):
        top = np.minimum(upper[continuous], headroom)
        lo = (lower[continuous] - observed) / sigma
        hi = (top - observed) / sigma
        log_continuous[continuous] = (
            _normal_interval_log_probability(lo, hi) - np.log(width[continuous])
        )
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        log_atom = (
            np.log(cap_mass)
            - 0.5 * ((observed - headroom) / sigma) ** 2
            - math.log(sigma)
            - 0.5 * math.log(2.0 * math.pi)
        )
    return np.logaddexp(log_continuous, log_atom)


def empirical_crps(samples: Any, target: float) -> float:
    """CRPS of the equally weighted empirical forecast, including diagonal pairs.

    Use the same predictive sample count across comparisons. This scores the
    empirical distribution, not an unbiased estimate for an underlying sampler.
    """
    values = np.asarray(samples, dtype=float)
    y = _finite(target, "target")
    if values.ndim != 1 or not len(values) or not np.all(np.isfinite(values)):
        raise ValueError("samples must be a nonempty finite one-dimensional array")
    ordered = np.sort(values)
    count = len(ordered)
    ranks = np.arange(1, count + 1, dtype=float)
    half_pair_mean = np.dot(2 * ranks - count - 1, ordered) / count**2
    return float(np.mean(np.abs(ordered - y)) - half_pair_mean)


class RenewalSMC:
    """Bounded uniform prior, sequential importance weights, and resample-move.

    Rejuvenation uses symmetric random-walk Metropolis proposals and the FULL
    accepted evidence likelihood. Parameters are static: jitter is never accepted
    without a posterior-invariant acceptance test. Adaptation chooses a proposal
    covariance before each move sweep; it remains fixed throughout that sweep.
    """

    def __init__(
        self,
        seed: int = 0,
        n_particles: int = 1024,
        prior: Mapping[str, Any] | None = None,
        sensor_sigma: float = 0.05,
        ess_fraction: float = 0.5,
        rejuvenation_steps: int = 4,
    ) -> None:
        self.n_particles = _integer(n_particles, "n_particles", 8)
        self.sensor_sigma = _finite(sensor_sigma, "sensor_sigma")
        self.ess_fraction = _finite(ess_fraction, "ess_fraction")
        self.rejuvenation_steps = _integer(rejuvenation_steps, "rejuvenation_steps", 0)
        if self.sensor_sigma <= 0 or not 0 < self.ess_fraction <= 1:
            raise ValueError("sensor_sigma must be positive and 0 < ess_fraction <= 1")
        supplied = DEFAULT_PRIOR if prior is None else prior
        if set(supplied) != set(PARAMETERS):
            raise ValueError("prior must specify exactly r, b and g bounds")
        bounds = []
        for name in PARAMETERS:
            pair = supplied[name]
            if len(pair) != 2:
                raise ValueError(f"{name} prior must contain two bounds")
            low, high = (_finite(pair[0], name), _finite(pair[1], name))
            if low >= high or low < 0 or (name == "r" and low <= 0):
                raise ValueError("prior bounds must increase, with r strictly positive")
            bounds.append((low, high))
        self.bounds = np.asarray(bounds, dtype=float)
        self.rng = np.random.default_rng(seed)
        self.particles = self.rng.uniform(self.bounds[:, 0], self.bounds[:, 1], (self.n_particles, 3))
        self.log_weights = np.full(self.n_particles, -math.log(self.n_particles))
        self.log_likelihood = np.zeros(self.n_particles)
        self.evidence: list[dict[str, Any]] = []
        self._events: dict[str, dict[str, Any]] = {}
        self.log_evidence = 0.0
        self.diagnostics = {
            "accepted_observations": 0,
            "duplicate_events": 0,
            "failed_updates": 0,
            "resampling_events": 0,
            "rejuvenation_proposals": 0,
            "rejuvenation_accepts": 0,
            "likelihood_evaluations": 0,
        }

    def _observation(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        headroom, own, other = _features(observation)
        try:
            event_id = observation["event_id"]
            growth = _finite(observation["growth"], "growth")
        except KeyError as exc:
            raise ValueError(f"missing observation field: {exc.args[0]}") from exc
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id must be a nonempty string")
        sigma = _finite(observation.get("sensor_sigma", self.sensor_sigma), "sensor_sigma")
        if sigma != self.sensor_sigma:
            raise ValueError("observation sensor_sigma differs from the declared measurement model")
        return {"event_id": event_id, "headroom": headroom,
                "own_infrastructure": own, "other_infrastructure": other, "growth": growth}

    def _likelihood(self, particles: np.ndarray, observation: Mapping[str, Any]) -> np.ndarray:
        self.diagnostics["likelihood_evaluations"] += len(particles)
        return _log_likelihood(particles, observation["headroom"],
                               observation["own_infrastructure"], observation["other_infrastructure"],
                               observation["growth"], self.sensor_sigma)

    def _joint_likelihood(self, particles: np.ndarray) -> np.ndarray:
        result = np.zeros(len(particles))
        for observation in self.evidence:
            result += self._likelihood(particles, observation)
        return result

    @property
    def weights(self) -> np.ndarray:
        return np.exp(self.log_weights)

    @property
    def effective_sample_size(self) -> float:
        return float(1.0 / np.sum(self.weights**2))

    def update(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        try:
            record = self._observation(observation)
            previous = self._events.get(record["event_id"])
            if previous is not None:
                if previous != record:
                    raise ValueError("event_id reused with different measurement contents")
                self.diagnostics["duplicate_events"] += 1
                return {"status": "duplicate", "event_id": record["event_id"]}
        except (ValueError, TypeError) as exc:
            self.diagnostics["failed_updates"] += 1
            raise ValueError(str(exc)) from exc
        likelihood = self._likelihood(self.particles, record)
        updated = self.log_weights + likelihood
        normalizer = float(logsumexp(updated))
        if not math.isfinite(normalizer) or not np.all(np.isfinite(likelihood)):
            self.diagnostics["failed_updates"] += 1
            return {"status": "failed", "reason": "nonfinite_likelihood", "event_id": record["event_id"]}
        self.log_weights = updated - normalizer
        self.log_likelihood += likelihood
        self.log_evidence += normalizer
        self.evidence.append(record)
        self._events[record["event_id"]] = record
        self.diagnostics["accepted_observations"] += 1
        before_resample = self.effective_sample_size
        resampled = before_resample < self.ess_fraction * self.n_particles
        if resampled:
            self._resample_move()
        return {"status": "updated", "event_id": record["event_id"],
                "ess_before_resample": before_resample, "resampled": resampled,
                "log_predictive_density": normalizer}

    def _resample_move(self) -> None:
        weights = self.weights
        center = np.sum(weights[:, None] * self.particles, axis=0)
        residual = self.particles - center
        covariance = (residual * weights[:, None]).T @ residual
        # A small fixed floor allows movement after severe importance collapse.
        prior_width = self.bounds[:, 1] - self.bounds[:, 0]
        covariance += np.diag((0.005 * prior_width) ** 2)
        covariance *= 2.38**2 / 3
        cumulative = np.cumsum(weights)
        cumulative[-1] = 1.0
        positions = (np.arange(self.n_particles) + self.rng.random()) / self.n_particles
        indices = np.searchsorted(cumulative, positions)
        self.particles = self.particles[indices].copy()
        self.log_likelihood = self.log_likelihood[indices].copy()
        self.log_weights.fill(-math.log(self.n_particles))
        self.diagnostics["resampling_events"] += 1
        for _ in range(self.rejuvenation_steps):
            proposal = self.particles + self.rng.multivariate_normal(np.zeros(3), covariance, self.n_particles)
            inside = np.all((proposal >= self.bounds[:, 0]) & (proposal <= self.bounds[:, 1]), axis=1)
            proposed_likelihood = np.full(self.n_particles, -np.inf)
            if np.any(inside):
                proposed_likelihood[inside] = self._joint_likelihood(proposal[inside])
            log_uniform = np.log(self.rng.random(self.n_particles))
            accepted = inside & (log_uniform < proposed_likelihood - self.log_likelihood)
            self.particles[accepted] = proposal[accepted]
            self.log_likelihood[accepted] = proposed_likelihood[accepted]
            self.diagnostics["rejuvenation_proposals"] += self.n_particles
            self.diagnostics["rejuvenation_accepts"] += int(np.sum(accepted))

    def predict(self, query: Mapping[str, Any], n_samples: int = 256, seed: int = 0) -> list[float]:
        """Sample future noisy measurements using an independent, caller-seeded RNG."""
        headroom, own, other = _features(query)
        count = _integer(n_samples, "n_samples", 1)
        rng = np.random.default_rng(seed)
        indices = rng.choice(self.n_particles, size=count, p=self.weights)
        parameters = self.particles[indices]
        latent_growth = (parameters[:, 0] * rng.uniform(0.85, 1.15, count)
                         + parameters[:, 1] * own + parameters[:, 2] * other)
        observed = np.minimum(headroom, latent_growth) + rng.normal(0.0, self.sensor_sigma, count)
        if not np.all(np.isfinite(observed)):
            raise ValueError("query produced nonfinite predictive samples")
        return observed.tolist()

    def summary(self) -> dict[str, Any]:
        weights = self.weights
        mean = np.sum(self.particles * weights[:, None], axis=0)
        residual = self.particles - mean
        covariance = (residual * weights[:, None]).T @ residual
        intervals = {}
        intervals_90 = {}
        for index, name in enumerate(PARAMETERS):
            order = np.argsort(self.particles[:, index])
            mass = np.cumsum(weights[order])
            intervals[name] = np.interp([0.025, 0.975], mass, self.particles[order, index]).tolist()
            intervals_90[name] = np.interp([0.05, 0.95], mass, self.particles[order, index]).tolist()
        return {"mean": dict(zip(PARAMETERS, map(float, mean))),
                "covariance": covariance.tolist(), "intervals": intervals,
                "intervals_90": intervals_90,
                "effective_sample_size": self.effective_sample_size,
                "n_observations": len(self.evidence), "n_particles": self.n_particles,
                "log_evidence": self.log_evidence, "diagnostics": dict(self.diagnostics)}

    def snapshot(self) -> dict[str, Any]:
        return {"version": SNAPSHOT_VERSION, "n_particles": self.n_particles,
                "prior": {name: self.bounds[i].tolist() for i, name in enumerate(PARAMETERS)},
                "sensor_sigma": self.sensor_sigma, "ess_fraction": self.ess_fraction,
                "rejuvenation_steps": self.rejuvenation_steps,
                "particles": self.particles.tolist(), "log_weights": self.log_weights.tolist(),
                "log_likelihood": self.log_likelihood.tolist(), "log_evidence": self.log_evidence,
                "evidence": copy.deepcopy(self.evidence), "diagnostics": dict(self.diagnostics),
                "rng_state": copy.deepcopy(self.rng.bit_generator.state)}

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any]) -> "RenewalSMC":
        if snapshot.get("version") != SNAPSHOT_VERSION:
            raise ValueError("unsupported learner snapshot version")
        model = cls(n_particles=snapshot["n_particles"], prior=snapshot["prior"],
                    sensor_sigma=snapshot["sensor_sigma"], ess_fraction=snapshot["ess_fraction"],
                    rejuvenation_steps=snapshot["rejuvenation_steps"])
        model.particles = np.asarray(snapshot["particles"], dtype=float)
        model.log_weights = np.asarray(snapshot["log_weights"], dtype=float)
        model.log_likelihood = np.asarray(snapshot["log_likelihood"], dtype=float)
        if (model.particles.shape != (model.n_particles, 3)
                or model.log_weights.shape != (model.n_particles,)
                or model.log_likelihood.shape != (model.n_particles,)
                or not np.all(np.isfinite(model.particles))
                or not np.all(np.isfinite(model.log_weights))
                or not np.all(np.isfinite(model.log_likelihood))
                or np.any(model.particles < model.bounds[:, 0])
                or np.any(model.particles > model.bounds[:, 1])
                or not np.isclose(logsumexp(model.log_weights), 0.0, atol=1e-9)):
            raise ValueError("invalid posterior arrays in snapshot")
        model.log_evidence = _finite(snapshot["log_evidence"], "log_evidence")
        model.evidence = copy.deepcopy(snapshot["evidence"])
        model._events = {record["event_id"]: record for record in model.evidence}
        if len(model._events) != len(model.evidence):
            raise ValueError("duplicate evidence in snapshot")
        model.diagnostics = dict(snapshot["diagnostics"])
        model.rng.bit_generator.state = copy.deepcopy(snapshot["rng_state"])
        return model

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        replacement = self.from_snapshot(snapshot)
        self.__dict__.clear()
        self.__dict__.update(replacement.__dict__)
