"""Independent likelihood and numerical-reference acceptance tests."""

import copy
import json
import math
import unittest
from itertools import product

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
from numpy.polynomial.legendre import leggauss
from scipy.integrate import quad
from scipy.special import logsumexp, ndtri
from scipy.stats import norm, rankdata

from swarm_societies.world_model_v1.learner import _log_likelihood
from swarm_societies.world_model_v1.reference import (
    chain_diagnostics,
    fit_reference,
    posterior_cdf,
    reference_log_likelihood,
)


def observation(index=0, headroom=30.0, own=0.8, other=0.3, growth=5.0):
    return dict(event_id=str(index), stock_before=30.0 - headroom, capacity=30.0,
                own_infrastructure=own, other_infrastructure=other, growth=growth)


def informative_stream(n=96, seed=54, truth=(4.2, 1.6, 0.35)):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        own, other = rng.uniform(0, 2, 2)
        cap = (30.0, 30.0, 6.0, 0.0)[i % 4]
        growth = min(cap, truth[0] * rng.uniform(.85, 1.15) + truth[1] * own + truth[2] * other)
        rows.append(observation(i, cap, own, other, growth + rng.normal(0, .05)))
    return rows


class LikelihoodTests(unittest.TestCase):
    def test_independent_density_matches_direct_weather_quadrature_and_frozen_code(self):
        theta = np.array([4.0, 1.5, 0.3])
        # Includes an interior cap, fully capped, uncapped, and noisy tail data.
        cases = [(30, 5.2), (5.4, 5.38), (0, -.04), (4.0, 4.12), (30, 4.3), (5.4, 5.8)]
        for cap, measured in cases:
            with self.subTest(cap=cap, measured=measured):
                row = observation(headroom=cap, growth=measured)
                crossing = (cap - theta[1] * .8 - theta[2] * .3) / theta[0]
                points = [crossing] if .85 < crossing < 1.15 else None
                numerical = quad(lambda weather: norm.pdf(measured, min(cap, theta[0] * weather +
                                      theta[1] * .8 + theta[2] * .3), .05) / .3,
                                 .85, 1.15, points=points, epsabs=1e-28, epsrel=1e-10)[0]
                independent = reference_log_likelihood(theta, [row])
                self.assertAlmostEqual(independent, math.log(numerical), places=8)
                frozen = _log_likelihood(theta[None, :], cap, .8, .3, measured, .05)[0]
                self.assertAlmostEqual(independent, frozen, places=10)

    def test_batched_shape_and_sum(self):
        rows = informative_stream(8)
        parameters = np.array([[[4.2, 1.6, .35], [3.0, 2.0, .4]], [[5.0, 1.0, .2], [6., 2., .6]]])
        result = reference_log_likelihood(parameters, rows)
        self.assertEqual(result.shape, (2, 2))
        for i in range(2):
            for j in range(2):
                self.assertAlmostEqual(result[i, j], sum(reference_log_likelihood(parameters[i, j], [row])
                                                        for row in rows), places=10)

    def test_cap_atom_retained_and_tail_finite(self):
        row = observation(headroom=0, growth=.03)
        params = [[2, .5, 0], [8, 3, .8]]
        assert_allclose(reference_log_likelihood(params, [row]), norm.logpdf(.03, 0, .05))
        self.assertTrue(np.isfinite(reference_log_likelihood([4, 1, .2], [observation(growth=-10)])))

    def test_semantic_deduplication_and_conflict(self):
        row = observation()
        self.assertEqual(reference_log_likelihood([4, 1, .2], [row]),
                         reference_log_likelihood([4, 1, .2], [row, copy.deepcopy(row)]))
        with self.assertRaises(ValueError):
            reference_log_likelihood([4, 1, .2], [row, dict(row, growth=6)])

    def test_invalid_input_rejected(self):
        cases = [dict(observation(), growth=float('nan')), dict(observation(), capacity=-1),
                 dict(observation(), stock_before=31), dict(observation(), own_infrastructure=-1),
                 dict(observation(), event_id=''), dict(observation(), sensor_sigma=.1)]
        for row in cases:
            with self.subTest(row=row), self.assertRaises(ValueError):
                reference_log_likelihood([4, 1, .2], [row])
        for theta in ([0, 1, .2], [4, -1, .2], [4, 1, float('inf')], [4, 1]):
            with self.subTest(theta=theta), self.assertRaises(ValueError):
                reference_log_likelihood(theta, [observation()])


class DiagnosticTests(unittest.TestCase):
    def test_independent_chains_pass(self):
        values = np.random.default_rng(5).normal(size=(4, 3000, 3))
        result = chain_diagnostics(values)
        self.assertTrue(result['passed'])
        self.assertTrue(all(ess > 9000 for ess in result['bulk_ess']))
        self.assertTrue(all(ess > 8500 for ess in result['tail_ess']))

    def test_offset_and_scale_mismatches_fail(self):
        values = np.random.default_rng(5).normal(size=(4, 2000))
        offset = values + np.arange(4)[:, None] * 2
        scale = values * np.array([1, 1, 4, 4])[:, None]
        self.assertFalse(chain_diagnostics(offset)['passed'])
        self.assertFalse(chain_diagnostics(scale)['passed'])

    def test_constants_fail_and_output_is_strict_json(self):
        result = chain_diagnostics(np.ones((4, 1000, 3)))
        self.assertFalse(result['passed'])
        self.assertEqual(result['bulk_ess'], [0, 0, 0])
        json.dumps(result, allow_nan=False)

    def test_autocorrelation_reduces_effective_size(self):
        rng = np.random.default_rng(23)
        trace = rng.normal(size=(4, 10000))
        for j in range(1, trace.shape[1]):
            trace[:, j] = .9 * trace[:, j - 1] + math.sqrt(1 - .9**2) * trace[:, j]
        result = chain_diagnostics(trace)
        # AR(1)'s analytic integrated correlation time is (1+rho)/(1-rho)=19.
        self.assertGreater(result['bulk_ess'][0], trace.size / 30)
        self.assertLess(result['bulk_ess'][0], trace.size / 12)

    def test_rank_split_rhat_matches_direct_formula(self):
        values = np.random.default_rng(42).normal(size=(4, 2001))
        split = np.concatenate([values[:, :1000], values[:, -1000:]])
        def direct(x):
            z = ndtri((rankdata(x.ravel()) - .375) / (x.size + .25)).reshape(x.shape)
            within = np.var(z, axis=1, ddof=1).mean()
            return np.sqrt((999 / 1000 * within + np.var(z.mean(axis=1), ddof=1)) / within)
        expected = max(direct(split), direct(abs(split - np.median(split))))
        self.assertAlmostEqual(chain_diagnostics(values)['rhat'][0], expected, places=13)


class BatchFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = informative_stream()
        cls.fit = fit_reference(cls.rows, seed=75)

    def test_identifiable_posterior_and_diagnostics(self):
        self.assertEqual(self.fit['status'], 'passed')
        mean = list(self.fit['summary']['mean'].values())
        assert_allclose(mean, [4.2, 1.6, .35], atol=.2)
        self.assertEqual(self.fit['draws'].shape, (4, 4000, 3))
        self.assertTrue(self.fit['diagnostics']['log_likelihood']['passed'])
        json.dumps(self.fit['diagnostics'], allow_nan=False)
        json.dumps(self.fit['summary'], allow_nan=False)

    def test_retained_likelihood_matches_actual_draws(self):
        selected = self.fit['draws'][:, ::503, :]
        actual = reference_log_likelihood(selected, self.rows)
        assert_allclose(actual, self.fit['draw_log_likelihood'][:, ::503], rtol=0, atol=1e-10)

    def test_no_truth_access_and_reproducible(self):
        class ForbiddenTruth:
            def __float__(self):
                raise AssertionError('fitter accessed truth')
        rows = [dict(row, true_parameters=ForbiddenTruth(), weather=ForbiddenTruth(),
                     true_growth=ForbiddenTruth()) for row in self.rows[:8]]
        before = [dict(row) for row in rows]
        first = fit_reference(rows, seed=73, warmup=100, draws=64)
        second = fit_reference(rows, seed=73, warmup=100, draws=64)
        assert_array_equal(first['draws'], second['draws'])
        assert_array_equal(first['draw_log_likelihood'], second['draw_log_likelihood'])
        self.assertEqual(rows, before)

    def test_short_chains_fail_instead_of_claiming_reference(self):
        result = fit_reference(self.rows[:8], seed=20, warmup=0, draws=16)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['draws'].shape, (4, 16, 3))
        self.assertFalse(result['diagnostics']['passed'])

    def test_fully_capped_data_leave_the_bounded_prior(self):
        rows = [observation(i, headroom=0, growth=.03) for i in range(6)]
        result = fit_reference(rows, seed=88, warmup=500, draws=4000)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['diagnostics']['flat_log_likelihood'])
        self.assertIsNone(result['diagnostics']['log_likelihood'])
        assert_allclose(list(result['summary']['mean'].values()), [5, 1.75, .4], atol=.08)
        expected_widths = [.9 * 6, .9 * 2.5, .9 * .8]
        widths = [hi - lo for lo, hi in result['summary']['intervals_90'].values()]
        assert_allclose(widths, expected_widths, rtol=.05)

    def test_posterior_moments_match_independent_three_dimensional_quadrature(self):
        rows = [dict(observation(i, own=own, other=other, growth=y), sensor_sigma=.5)
                for i, (own, other, y) in enumerate([(.2, 1., 7.), (1.5, .2, 8.1), (.8, .7, 7.6)])]
        x, w = leggauss(35)
        indices = np.array(list(product(range(35), repeat=3)))
        parameters = np.array([2, .5, 0]) + ((x + 1) / 2)[indices] * np.array([6, 2.5, .8])
        log_weights = np.log(np.prod((w / 2)[indices], axis=1))
        log_weights += reference_log_likelihood(parameters, rows, sensor_sigma=.5)
        weights = np.exp(log_weights - logsumexp(log_weights))
        expected_mean = weights @ parameters
        expected_cov = (parameters - expected_mean).T @ ((parameters - expected_mean) * weights[:, None])
        result = fit_reference(rows, seed=44, sensor_sigma=.5)
        self.assertEqual(result['status'], 'passed')
        actual_mean = np.array(list(result['summary']['mean'].values()))
        # Agreement to 0.1 posterior SD checks the distribution, not truth recovery.
        assert_allclose((actual_mean - expected_mean) / np.sqrt(expected_cov.diagonal()), 0, atol=.1)
        assert_allclose(np.sqrt(np.diag(result['summary']['covariance'])),
                        np.sqrt(expected_cov.diagonal()), rtol=.06)

    def test_posterior_cdf_is_post_fit_probability(self):
        draws = np.array([[[2, 1, .1], [4, 2, .3]], [[6, 1, .5], [8, 3, .7]]])
        self.assertEqual(posterior_cdf(draws, [5, 1, .5]), {'r': .5, 'b': .5, 'g': .75})
        self.assertEqual(posterior_cdf(draws, dict(r=5, b=1, g=.5)), {'r': .5, 'b': .5, 'g': .75})

    def test_no_observations_and_invalid_fit_configuration(self):
        self.assertEqual(reference_log_likelihood([4, 1, .2], []), 0)
        for kwargs in ({'n_chains': 2}, {'warmup': -1}, {'draws': 7}, {'sensor_sigma': 0},
                       {'prior': {'r': [0, 8], 'b': [.5, 3], 'g': [0, .8]}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                fit_reference([], **kwargs)


if __name__ == '__main__':
    unittest.main()
