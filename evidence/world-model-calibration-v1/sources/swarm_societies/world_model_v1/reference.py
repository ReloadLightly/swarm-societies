"""Independent batch posterior check for the frozen renewal SMC.

This module imports neither the simulator nor the online learner. Its target is
the bounded-prior *conditional* likelihood of the supplied features and noisy
renewal measurements. It is not a joint posterior for endogenous ecology data.
Four Metropolis chains use evidence-only initialization and warmup adaptation;
all retained transitions use a fixed symmetric proposal. A failed convergence
gate is an exposed failure, not an authoritative posterior reference.

Diagnostics follow Vehtari et al. (2021), doi:10.1214/20-BA1221: rank-normalized
split/folded R-hat, bulk ESS, and 5%/95% indicator tail ESS. Diagnostics cannot
prove global convergence. Retained MCMC draws are correlated and must not be
treated as independent exact posterior draws in simulation-based calibration.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import time
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import log_ndtr, ndtri
from scipy.stats import rankdata


PARAMETERS = ("r", "b", "g")
DEFAULT_PRIOR = {"r": (2.0, 8.0), "b": (0.5, 3.0), "g": (0.0, 0.8)}
REFERENCE_VERSION = "renewal-batch-mcmc-v1"


def _positive_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite and positive")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _bounds(prior: Mapping[str, Any] | None) -> np.ndarray:
    supplied = DEFAULT_PRIOR if prior is None else prior
    if set(supplied) != set(PARAMETERS):
        raise ValueError("prior must contain exactly r, b and g")
    result = np.asarray([supplied[name] for name in PARAMETERS], dtype=float)
    if (result.shape != (3, 2) or not np.isfinite(result).all()
            or (result[:, 0] < 0).any() or result[0, 0] <= 0
            or (result[:, 0] >= result[:, 1]).any()):
        raise ValueError("prior bounds must increase, be nonnegative, and have r > 0")
    return result


def _observations(observations: Sequence[Mapping[str, Any]], sigma: float) -> tuple[np.ndarray, int]:
    rows: list[tuple[float, float, float, float]] = []
    events: dict[str, tuple[float, float, float, float]] = {}
    duplicates = 0
    for item in observations:
        if not isinstance(item, Mapping):
            raise ValueError("each observation must be a mapping")
        try:
            event = item["event_id"]
            before, capacity, own, other, growth = (
                float(item[key]) for key in ("stock_before", "capacity", "own_infrastructure",
                                            "other_infrastructure", "growth")
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("observation has missing or invalid required fields") from exc
        if not isinstance(event, str) or not event:
            raise ValueError("event_id must be a nonempty string")
        if (not np.isfinite([before, capacity, own, other, growth]).all()
                or capacity <= 0 or not 0 <= before <= capacity or own < 0 or other < 0):
            raise ValueError("invalid stock, capacity, infrastructure or measurement")
        if float(item.get("sensor_sigma", sigma)) != sigma:
            raise ValueError("observation sensor_sigma differs from the declared model")
        row = (capacity - before, own, other, growth)
        if event in events:
            if events[event] != row:
                raise ValueError("event_id reused with different measurement contents")
            duplicates += 1
            continue
        events[event] = row
        rows.append(row)
    return np.asarray(rows, dtype=float).reshape((-1, 4)), duplicates


def _batch_log_likelihood(theta: np.ndarray, rows: np.ndarray, sigma: float) -> np.ndarray:
    """Integrate uniform weather analytically, retaining the clipping atom.

    Unlike the online implementation's particle-by-observation evaluator, this
    evaluates a candidate-by-observation matrix and reduces only at the end.
    Gaussian CDF subtraction switches to survival probabilities in the upper
    tail. No measurement is dropped because clipping occurred.
    """
    if not len(rows):
        return np.zeros(len(theta))
    cap, own, other, measured = rows.T
    location = theta[:, 1, None] * own + theta[:, 2, None] * other
    left = location + 0.85 * theta[:, 0, None]
    right = location + 1.15 * theta[:, 0, None]
    width = 0.30 * theta[:, 0, None]
    stop = np.minimum(right, cap)
    # For the continuous component, integrate N(measured; x,sigma) from left
    # to min(right, cap), divided by the *unclipped* uniform interval width.
    z0, z1 = (left - measured) / sigma, (stop - measured) / sigma
    positive = z0 > 0
    cdf_high = log_ndtr(np.where(positive, -z0, z1))
    cdf_low = log_ndtr(np.where(positive, -z1, z0))
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        continuous = cdf_high + np.log(-np.expm1(np.minimum(cdf_low - cdf_high, 0.0)))
        continuous -= np.log(width)
        continuous = np.where(stop > left, continuous, -np.inf)
        atom_weight = np.clip((right - cap) / width, 0.0, 1.0)
        atom = (np.log(atom_weight) - math.log(sigma * math.sqrt(2 * math.pi))
                - 0.5 * ((measured - cap) / sigma) ** 2)
    return np.logaddexp(continuous, atom).sum(axis=1)


def reference_log_likelihood(
    theta: Any,
    observations: Sequence[Mapping[str, Any]],
    sensor_sigma: float = 0.05,
) -> np.ndarray | float:
    """Independent conditional log likelihood, with no prior or truth access.

    ``theta`` has final axis (r,b,g). Leading dimensions are preserved. This
    public evaluator also supports post-fit, data-dependent calibration scores.
    Bounds are intentionally not applied to a likelihood; r must be positive,
    and infrastructure returns must be nonnegative.
    """
    sigma = _positive_float(sensor_sigma, "sensor_sigma")
    values = np.asarray(theta, dtype=float)
    if (values.ndim < 1 or values.shape[-1] != 3 or not np.isfinite(values).all()
            or (values[..., 0] <= 0).any() or (values[..., 1:] < 0).any()):
        raise ValueError("theta must be finite (..., 3), with r > 0 and b,g >= 0")
    rows, _ = _observations(observations, sigma)
    flat = values.reshape((-1, 3))
    # Bound temporary memory for post-fit evaluation of thousands of draws.
    pieces = [_batch_log_likelihood(flat[start:start + 256], rows, sigma)
              for start in range(0, len(flat), 256)]
    result = np.concatenate(pieces).reshape(values.shape[:-1]) if pieces else np.empty(values.shape[:-1])
    return float(result) if result.ndim == 0 else result


def _split(values: np.ndarray) -> np.ndarray:
    half = values.shape[1] // 2
    return np.concatenate((values[:, :half], values[:, -half:]), axis=0)


def _rank_normalize(values: np.ndarray) -> np.ndarray:
    ranks = rankdata(values.ravel(), method="average")
    return ndtri((ranks - 0.375) / (values.size + 0.25)).reshape(values.shape)


def _rhat(values: np.ndarray) -> float:
    n = values.shape[1]
    within = np.var(values, axis=1, ddof=1).mean()
    if within <= 0 or not math.isfinite(float(within)):
        return math.inf
    between = np.var(np.mean(values, axis=1), ddof=1)
    return float(np.sqrt(((n - 1) / n * within + between) / within))


def _ess(values: np.ndarray) -> float:
    """Multi-chain ESS with Geyer's initial positive/monotone paired sequence."""
    m, n = values.shape
    centered = values - values.mean(axis=1, keepdims=True)
    fft_size = 1 << (2 * n - 1).bit_length()
    transform = np.fft.rfft(centered, n=fft_size, axis=1)
    autocov = np.fft.irfft(transform * transform.conjugate(), n=fft_size, axis=1)[:, :n] / n
    within = autocov[:, 0].mean() * n / (n - 1)
    variance = within * (n - 1) / n + np.var(values.mean(axis=1), ddof=1)
    if within <= 0 or variance <= 0 or not np.isfinite(variance):
        return 0.0
    rho = 1 - (within - autocov.mean(axis=0)) / variance
    rho[0] = 1.0
    paired = rho[:2 * (n // 2)].reshape((-1, 2)).sum(axis=1)
    negative = np.flatnonzero(paired <= 0)
    if len(negative):
        paired = paired[:negative[0]]
    if not len(paired):
        return float(m * n)
    paired = np.minimum.accumulate(paired)
    tau = max(1.0, -1 + 2 * paired.sum())
    return float(min(m * n, m * n / tau))


def chain_diagnostics(draws: Any, rhat_limit: float = 1.01, min_ess: float = 400.0) -> dict[str, Any]:
    """Rank/folded R-hat and bulk/tail ESS for chains × draws × quantities.

    Constant chains fail: an unchanging trace is not evidence of convergence.
    Tail ESS measures the two interval endpoints, not independence of draws.
    """
    values = np.asarray(draws, dtype=float)
    if values.ndim == 2:
        values = values[..., None]
    if (values.ndim != 3 or values.shape[0] < 2 or values.shape[1] < 8
            or not np.isfinite(values).all()):
        raise ValueError("draws must be finite chains x draws x quantities, with >=2 chains and >=8 draws")
    if not math.isfinite(rhat_limit) or rhat_limit <= 1 or not math.isfinite(min_ess) or min_ess <= 0:
        raise ValueError("diagnostic limits require rhat_limit > 1 and min_ess > 0")
    rhats, bulk, tails = [], [], []
    for k in range(values.shape[2]):
        split = _split(values[:, :, k])
        normalized = _rank_normalize(split)
        folded = _rank_normalize(np.abs(split - np.median(split)))
        rhats.append(max(_rhat(normalized), _rhat(folded)))
        bulk.append(_ess(normalized))
        q05, q95 = np.quantile(split, [0.05, 0.95])
        tails.append(min(_ess((split <= q05).astype(float)), _ess((split <= q95).astype(float))))
    passed = all(r < rhat_limit and b >= min_ess and t >= min_ess
                 for r, b, t in zip(rhats, bulk, tails))
    return {"passed": passed, "rhat": [r if math.isfinite(r) else None for r in rhats],
            "bulk_ess": bulk, "tail_ess": tails, "rhat_limit": float(rhat_limit),
            "min_ess": float(min_ess), "split_chains": 2 * values.shape[0],
            "draws_per_split_chain": values.shape[1] // 2}


def _covariance_from_curvature(function: Any, point: np.ndarray) -> tuple[np.ndarray, list[float]]:
    step = 2e-4
    # Curvature is only a proposal heuristic. Evaluate its stencil inside the
    # public bounds even when the mode itself is on a prior boundary.
    point = np.clip(point, step + 1e-10, 1 - step - 1e-10)
    center = float(function(point))
    hessian = np.empty((3, 3))
    for i in range(3):
        ei = np.eye(3)[i] * step
        hessian[i, i] = (function(point + ei) - 2 * center + function(point - ei)) / step**2
        for j in range(i):
            ej = np.eye(3)[j] * step
            hessian[i, j] = hessian[j, i] = (
                function(point + ei + ej) - function(point + ei - ej)
                - function(point - ei + ej) + function(point - ei - ej)
            ) / (4 * step**2)
    eigenvalues, eigenvectors = np.linalg.eigh(hessian)
    # A flat direction begins at prior scale, and remains free to explore.
    covariance = (eigenvectors * (1 / np.clip(eigenvalues, 12.0, 1e12))) @ eigenvectors.T
    return covariance, eigenvalues.tolist()


def fit_reference(
    observations: Sequence[Mapping[str, Any]],
    seed: int = 0,
    prior: Mapping[str, Any] | None = None,
    sensor_sigma: float = 0.05,
    n_chains: int = 4,
    warmup: int = 1000,
    draws: int = 4000,
    rhat_limit: float = 1.01,
    min_ess: float = 400.0,
) -> dict[str, Any]:
    """Fit the independent batch conditional posterior and expose diagnostics.

    Initialization: bounded MAP searches start at the prior center and at one
    prior draw per chain. Chains start around their own evidence-fitted mode,
    with overdispersed curvature-scaled noise. Warmup adapts scale/covariance;
    retained sampling freezes both. No truth, online particles, or evaluation
    scores enter fitting. Only a caller's predeclared retry rule may extend it.

    Return ``draws`` (chains x draws x 3), ``draw_log_likelihood`` (chains x
    draws), ``summary``, and JSON-compatible ``diagnostics``. Failed gates keep
    their full results and status="failed"; they are not silently discarded.
    """
    started = time.perf_counter()
    for value, name, minimum in ((n_chains, "n_chains", 4), (warmup, "warmup", 0), (draws, "draws", 8)):
        if isinstance(value, bool) or int(value) != value or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    n_chains, warmup, draws = int(n_chains), int(warmup), int(draws)
    sigma = _positive_float(sensor_sigma, "sensor_sigma")
    bounds = _bounds(prior)
    low, width = bounds[:, 0], np.diff(bounds, axis=1).ravel()
    rows, duplicates = _observations(observations, sigma)
    rng = np.random.default_rng(seed)
    calls = 0

    def batch(unit: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += len(unit)
        return _batch_log_likelihood(low + unit * width, rows, sigma)

    def objective(unit: np.ndarray) -> float:
        return -float(batch(np.asarray(unit)[None, :])[0])

    starts = np.vstack((np.full(3, 0.5), rng.uniform(0, 1, (n_chains, 3))))
    modes = [minimize(objective, start, method="L-BFGS-B", bounds=[(0, 1)] * 3,
                      options={"maxiter": 500, "ftol": 1e-12, "gtol": 1e-6}) for start in starts]
    finite_modes = [mode for mode in modes if np.isfinite(mode.fun)]
    if not finite_modes:
        raise ArithmeticError("all evidence-only mode searches produced nonfinite likelihoods")
    best = min(finite_modes, key=lambda mode: mode.fun)
    covariance, curvature = _covariance_from_curvature(objective, best.x)
    chol = np.linalg.cholesky(covariance + np.eye(3) * 1e-12)
    current = np.empty((n_chains, 3))
    initialization_fallbacks = 0
    for chain in range(n_chains):
        mode = modes[chain + 1].x if np.isfinite(modes[chain + 1].fun) else best.x
        for _ in range(10000):
            proposed = mode + 2.0 * (chol @ rng.normal(size=3))
            if ((proposed >= 0) & (proposed <= 1)).all():
                current[chain] = proposed
                break
        else:
            # Numerical boundary fallback remains evidence-only and is exposed.
            current[chain] = np.clip(mode, 1e-8, 1 - 1e-8)
            initialization_fallbacks += 1
    initial = (low + current * width).tolist()
    current_log = batch(current)
    if not np.isfinite(current_log).all():
        raise ArithmeticError("initial chain state has a nonfinite likelihood")
    scale = 2.38 / math.sqrt(3)
    samples = np.empty((n_chains, draws, 3))
    log_samples = np.empty((n_chains, draws))
    warm_history: list[np.ndarray] = []
    accepted = np.zeros(n_chains, dtype=int)
    warm_accepted = np.zeros(n_chains, dtype=int)
    block_accepts = 0
    proposal_chol = chol * scale
    for iteration in range(warmup + draws):
        proposal = current + rng.normal(size=(n_chains, 3)) @ proposal_chol.T
        inside = ((proposal >= 0) & (proposal <= 1)).all(axis=1)
        proposed_log = np.full(n_chains, -np.inf)
        if inside.any():
            proposed_log[inside] = batch(proposal[inside])
        accept = np.log(rng.uniform(size=n_chains)) < proposed_log - current_log
        current[accept] = proposal[accept]
        current_log[accept] = proposed_log[accept]
        if iteration < warmup:
            warm_accepted += accept
            block_accepts += int(accept.sum())
            warm_history.append(current.copy())
            if (iteration + 1) % 100 == 0:
                block = (iteration + 1) // 100
                scale *= math.exp(min(0.5, 1 / math.sqrt(block)) * (block_accepts / (100 * n_chains) - 0.234))
                block_accepts = 0
                if iteration >= 199:
                    history = np.asarray(warm_history[max(0, len(warm_history) // 2):]).reshape((-1, 3))
                    empirical = np.cov(history, rowvar=False)
                    # Curvature regularization prevents a short stuck warmup
                    # from making an unexplored direction effectively immobile.
                    adapted = 0.90 * empirical + 0.10 * covariance + np.eye(3) * 1e-12
                    chol = np.linalg.cholesky(adapted)
                proposal_chol = chol * scale
        else:
            index = iteration - warmup
            accepted += accept
            samples[:, index, :] = low + current * width
            log_samples[:, index] = current_log
    diagnostics = chain_diagnostics(samples, rhat_limit=rhat_limit, min_ess=min_ess)
    # A flat likelihood has no log-density mixing information; coefficient
    # diagnostics still govern the gate in this explicitly recorded case.
    flat_log_likelihood = bool(np.ptp(log_samples) < 1e-10)
    log_diagnostics = (None if flat_log_likelihood else
                       chain_diagnostics(log_samples, rhat_limit=rhat_limit, min_ess=min_ess))
    passed = diagnostics["passed"] and (log_diagnostics is None or log_diagnostics["passed"])
    flat = samples.reshape((-1, 3))
    raw_ess = [_ess(_split(samples[:, :, k])) for k in range(3)]
    intervals = np.quantile(flat, [0.05, 0.95], axis=0)
    summary = {"mean": dict(zip(PARAMETERS, flat.mean(axis=0).tolist())),
               "covariance": np.cov(flat, rowvar=False).tolist(),
               "intervals_90": {name: intervals[:, k].tolist() for k, name in enumerate(PARAMETERS)},
               "n_observations": len(rows)}
    diagnostics.update({
        "passed": bool(passed), "log_likelihood": log_diagnostics,
        "flat_log_likelihood": flat_log_likelihood,
        "acceptance_rate": (accepted / draws).tolist(),
        "warmup_acceptance_rate": (warm_accepted / max(1, warmup)).tolist(),
        "initial_states": initial, "initialization": "independent prior starts; bounded MAP; overdispersed curvature noise",
        "initialization_boundary_fallbacks": initialization_fallbacks,
        "mean_ess": raw_ess,
        "mean_mcse": [float(np.std(flat[:, k], ddof=1) / math.sqrt(ess)) if ess > 0 else None
                      for k, ess in enumerate(raw_ess)],
        "map_log_likelihood": [-float(mode.fun) if np.isfinite(mode.fun) else None for mode in modes],
        "map_success": [bool(mode.success) for mode in modes],
        "curvature_eigenvalues": curvature,
        "proposal_covariance_unit_coordinates": (proposal_chol @ proposal_chol.T).tolist(),
        "likelihood_candidate_evaluations": calls,
        "unique_observations": len(rows), "duplicate_events": duplicates,
        "warmup": warmup, "draws_per_chain": draws, "n_chains": n_chains,
        "elapsed_seconds": time.perf_counter() - started,
    })
    return {"version": REFERENCE_VERSION, "status": "passed" if passed else "failed",
            "draws": samples, "draw_log_likelihood": log_samples,
            "summary": summary, "diagnostics": diagnostics}


def posterior_cdf(draws: Any, values: Any) -> dict[str, float]:
    """Empirical marginal CDFs at evaluator-supplied values, after fitting.

    These are posterior-probability estimates from correlated MCMC draws, not
    exchangeable finite-sample SBC ranks. No evaluator value enters the fitter.
    """
    samples = np.asarray(draws, dtype=float)
    point = np.asarray([values[name] for name in PARAMETERS] if isinstance(values, Mapping) else values, dtype=float)
    if (samples.ndim < 2 or samples.shape[-1] != 3 or samples.size == 0
            or point.shape != (3,) or not np.isfinite(samples).all() or not np.isfinite(point).all()):
        raise ValueError("draws must end in three finite parameters and values must contain r,b,g")
    cdf = (samples.reshape((-1, 3)) <= point).mean(axis=0)
    return dict(zip(PARAMETERS, cdf.tolist()))
