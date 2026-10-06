"""One-shot, exact-escrow experiment selection from legally available beliefs.

The acquisition score is a joint Gaussian moment proxy, not exact expected
information gain. It propagates nominal stock, integrates capped uniform
weather at each tick, and approximates remaining observation noise by a diagonal
covariance. It never queries the physical simulator or realized future data.
"""
from __future__ import annotations

import math

import numpy as np

from .decision import PRIOR_BOUNDS, PUBLIC_CONSTANTS, validate_observation

VERSION = 'escrow-experiment-selection-v1'
PROBE_TICKS = 8
SCHEDULES = {
    'early': (1., 0., 0., 0., 0., 0., 0., 0.),
    'late': (0., 0., 0., 0., 1., 0., 0., 0.),
    'split': (.5, 0., 0., 0., .5, 0., 0., 0.),
}
SCORE_KIND = 'joint Gaussian moment proxy; not exact expected information gain'
ASSUMPTIONS = (
    'Same nominal stock path for all coefficient draws within each schedule; '
    'home-only full-effort harvest at unit productivity; supplied rho/eta/h; '
    'decay-only external infrastructure; no current taxes or other transfers; '
    'capped-uniform weather moments plus Gaussian sensor variance; diagonal '
    'weather/sensor residual covariance omits stock-mediated temporal noise dependence.'
)


def capped_uniform_moments(coefficients, headroom, own_infrastructure, other_infrastructure):
    """Exact conditional mean/variance of capped renewal before sensor noise."""
    coefficients = np.asarray(coefficients, dtype=float)
    if (coefficients.ndim != 2 or coefficients.shape[1] != 3
            or not np.isfinite(coefficients).all() or np.any(coefficients[:, 0] <= 0)):
        raise ValueError('Expected finite r/b/g rows with strictly positive r')
    for value in (headroom, own_infrastructure, other_infrastructure):
        if isinstance(value, bool) or not math.isfinite(float(value)) or value < 0:
            raise ValueError('Moment features must be finite and nonnegative')
    r, b, g = coefficients.T
    lower = .85 * r + b * own_infrastructure + g * other_infrastructure
    upper = 1.15 * r + b * own_infrastructure + g * other_infrastructure
    width = upper - lower
    fraction = np.clip((headroom - lower) / width, 0., 1.)
    mean = np.where(headroom >= upper, (lower + upper) / 2,
                    headroom - width * fraction ** 2 / 2)
    # The capped distribution's deficit below its cap has an atom at zero
    # and a uniform component. This expression avoids subtracting large moments.
    variance = width ** 2 * (fraction ** 3 / 3 - fraction ** 4 / 4)
    return mean, variance


def _validate(obs, coefficients):
    validate_observation(obs)
    coefficients = np.asarray(coefficients, dtype=float)
    if (coefficients.ndim != 2 or coefficients.shape[1] != 3 or len(coefficients) < 2
            or not np.isfinite(coefficients).all()
            or np.any(coefficients < PRIOR_BOUNDS[:, 0])
            or np.any(coefficients > PRIOR_BOUNDS[:, 1])):
        raise ValueError('Expected at least two bounded finite coefficient draws')
    if obs['treasury'] <= 0:
        raise ValueError('An experiment requires positive legally observed escrow')
    if obs['last_growth']['sensor_sigma'] <= 0:
        raise ValueError('The declared experiment sensor must have positive noise variance')
    return coefficients


def score_schedule(obs, coefficient_draws, schedule):
    """Score all eight future readings on a nominal path without sampling them.

    Row draws are equally weighted coefficient beliefs. Their conditional mean
    covariance retains shared parameter uncertainty across ticks; the score
    does not sum eight independent one-step information scores.
    """
    coefficients = _validate(obs, coefficient_draws)
    if schedule not in SCHEDULES:
        raise ValueError('Unknown escrow experiment schedule')
    packet = obs['last_growth']
    rho, eta, h = (PUBLIC_CONSTANTS[name] for name in ('rho', 'eta', 'h'))
    members = len(obs['wealth'])
    escrow = float(obs['treasury'])
    stock = max(0., min(packet['capacity'], packet['stock_before'] + packet['growth']) - members * h)
    own = float(obs['infrastructure'])
    other = float(packet['other_infrastructure']) * rho
    means, residual_variances, feature_rows = [], [], []
    tranches = [escrow * fraction for fraction in SCHEDULES[schedule]]
    for offset, tranche in enumerate(tranches):
        if offset:
            own *= rho
            other *= rho
        headroom = max(0., packet['capacity'] - stock)
        conditional_mean, conditional_variance = capped_uniform_moments(
            coefficients, headroom, own, other)
        means.append(conditional_mean)
        residual_variances.append(float(np.mean(conditional_variance) + packet['sensor_sigma'] ** 2))
        feature_rows.append({'offset': offset, 'stock_before': float(stock),
                             'headroom': float(headroom), 'own_infrastructure': float(own),
                             'other_infrastructure': float(other), 'investment_after_harvest': tranche})
        stock = max(0., min(packet['capacity'], stock + float(np.mean(conditional_mean))) - members * h)
        own += tranche * eta / members
    matrix = np.asarray(means).T
    # Center around one row first: a point belief then has exactly zero between-
    # coefficient covariance rather than floating-point mean-subtraction noise.
    centered = matrix - matrix[0]
    centered -= centered.mean(axis=0)
    between = centered.T @ centered / len(coefficients)
    residual = np.asarray(residual_variances)
    standardized = between / np.sqrt(residual[:, None] * residual[None, :])
    eigenvalues = np.linalg.eigvalsh((standardized + standardized.T) / 2)
    if eigenvalues.min() < -1e-8:
        raise ArithmeticError('Acquisition covariance lost positive semidefiniteness')
    score = float(.5 * np.log1p(np.maximum(eigenvalues, 0.)).sum())
    marginal_sum = float(.5 * np.log1p(np.diag(between) / residual).sum())
    return {'schedule': schedule, 'score': score, 'score_kind': SCORE_KIND,
            'marginal_score_sum': marginal_sum,
            'forecast_growth_mean': matrix.mean(axis=0).tolist(),
            'coefficient_mean_covariance': between.tolist(),
            'residual_variances': residual.tolist(), 'features': feature_rows,
            'investment_tranches': tranches, 'total_investment': float(sum(tranches)),
            'nominal_terminal_stock': float(stock)}


def select_experiment(obs, coefficient_draws, *, strategy='active', seed=0):
    """Commit one cost-matched schedule; fixed and random controls see no future.

    Scores are deterministic. Only the random-control schedule uses ``seed``;
    its RNG is private to this call. All strategies record the same candidate
    diagnostics, and all spend the initial escrow exactly by the fixed deadline.
    """
    if strategy not in ('active', 'fixed', 'random'):
        raise ValueError('Unknown experiment selection strategy')
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError('Selection seed must be a nonnegative integer')
    coefficients = _validate(obs, coefficient_draws)
    scores = [score_schedule(obs, coefficients, name) for name in SCHEDULES]
    names = list(SCHEDULES)
    if strategy == 'active':
        chosen = names[int(np.argmax([row['score'] for row in scores]))]
    elif strategy == 'fixed':
        chosen = 'split'
    else:
        chosen = names[int(np.random.default_rng(seed).integers(len(names)))]
    return {'version': VERSION, 'strategy': strategy, 'schedule': chosen,
            'escrow': float(obs['treasury']), 'probe_ticks': PROBE_TICKS,
            'n_samples': len(coefficients), 'scores': scores,
            'score_kind': SCORE_KIND, 'assumptions': ASSUMPTIONS,
            'random_seed': int(seed), 'tie_break': 'first maximum in early/late/split order'}
