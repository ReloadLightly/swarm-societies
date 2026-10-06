"""Independent controls for the acquisition proxy and exact-budget schedules."""
from copy import deepcopy
import pickle
import random

import numpy as np
import pytest
from scipy.integrate import quad

from swarm_societies.world_model_v1.decision import observation
from swarm_societies.world_model_v1.experimentation import (
    PROBE_TICKS, SCHEDULES, capped_uniform_moments, score_schedule, select_experiment,
)


def legal_observation(*, escrow=4., infrastructure=0., other=0.):
    institution = {
        'tick': 8, 'society_id': 0, 'n_societies': 3, 'treasury': escrow,
        'infrastructure': infrastructure, 'mean_wealth': 4.,
        'members': [{'id': member, 'wealth': 4.} for member in range(4)], 'reports': [],
    }
    packet = {
        'event_id': 'synthetic/growth:7:0', 'tick': 7, 'patch': 0,
        'phase': 'before_actions', 'stock_before': 0., 'capacity': 30.,
        'own_infrastructure': infrastructure, 'other_infrastructure': other,
        'growth': 0., 'sensor_sigma': .05,
    }
    return observation(institution, packet)


def b_only_draws(n=512):
    coordinate = (np.arange(n) + .5) / n
    return np.column_stack((np.full(n, 4.6), .5 + 2.5 * coordinate, np.full(n, .3)))


@pytest.mark.parametrize('headroom', [0., 2., 6.6, 7.1, 30.])
def test_capped_uniform_moments_match_independent_quadrature(headroom):
    coefficients = np.array([[4.6, 1.7, .3]])
    own, other = 1.1, .6
    threshold = (headroom - 1.7 * own - .3 * other) / 4.6
    points = [threshold] if .85 < threshold < 1.15 else None
    mean, variance = capped_uniform_moments(coefficients, headroom, own, other)
    first = quad(lambda weather: min(headroom, 4.6 * weather + 1.7 * own + .3 * other) / .3,
                 .85, 1.15, points=points, epsabs=1e-12)[0]
    second = quad(lambda weather: min(headroom, 4.6 * weather + 1.7 * own + .3 * other) ** 2 / .3,
                  .85, 1.15, points=points, epsabs=1e-12)[0]
    assert mean[0] == pytest.approx(first, abs=1e-12)
    assert variance[0] == pytest.approx(second - first ** 2, abs=1e-11)


@pytest.mark.parametrize('schedule', list(SCHEDULES))
def test_all_schedules_spend_identical_escrow_after_growth_at_prescribed_offsets(schedule):
    obs = legal_observation(escrow=7.25, other=2.)
    result = score_schedule(obs, b_only_draws(), schedule)
    assert PROBE_TICKS == 8
    assert sum(SCHEDULES[schedule]) == 1.
    assert result['total_investment'] == 7.25
    assert sum(result['investment_tranches']) == 7.25
    for offset, row in enumerate(result['features']):
        # Each tranche starts contributing only on later renewal opportunities.
        expected = sum(7.25 * fraction * .125 / 4 * .96 ** (offset - origin)
                       for origin, fraction in enumerate(SCHEDULES[schedule]) if origin < offset)
        assert row['own_infrastructure'] == pytest.approx(expected)
        assert row['other_infrastructure'] == pytest.approx(2 * .96 ** (offset + 1))
        assert row['investment_after_harvest'] == 7.25 * SCHEDULES[schedule][offset]


def test_rank_one_uncapped_joint_proxy_matches_matrix_determinant_lemma():
    obs, draws = legal_observation(), b_only_draws()
    result = score_schedule(obs, draws, 'early')
    features = np.array([0., *[4 * .125 / 4 * .96 ** tick for tick in range(1, 8)]])
    residual = (4.6 * .3) ** 2 / 12 + .05 ** 2
    expected = .5 * np.log1p(np.var(draws[:, 1]) * np.sum(features ** 2) / residual)
    assert result['score'] == pytest.approx(expected, rel=1e-12, abs=1e-14)
    assert result['score'] < result['marginal_score_sum']
    # Shared uncertainty is rank one even though there are eight readings.
    assert np.linalg.matrix_rank(result['coefficient_mean_covariance'], tol=1e-12) == 1


def test_fully_capped_design_has_no_coefficient_disagreement():
    obs = legal_observation(infrastructure=100.)
    draws = np.random.default_rng(101).uniform([2., .5, 0.], [8., 3., .8], (512, 3))
    result = select_experiment(obs, draws)
    assert all(item['score'] == 0. for item in result['scores'])
    assert all(np.array_equal(item['coefficient_mean_covariance'], np.zeros((8, 8)))
               for item in result['scores'])
    assert result['schedule'] == 'early'


def test_point_beliefs_have_zero_score_despite_hidden_weather():
    draws = np.tile([4.6, 1.7, .3], (512, 1))
    result = select_experiment(legal_observation(), draws)
    assert all(row['score'] == 0 for row in result['scores'])
    assert all(min(row['residual_variances']) > .05 ** 2 for row in result['scores'])


def test_joint_belief_uncertainty_changes_selected_schedule_on_same_legal_state():
    """Synthetic design check, independent of all development/evaluation arenas."""
    obs = legal_observation()
    joint = np.random.default_rng(77).uniform([2., .5, 0.], [8., 3., .8], (512, 3))
    one_parameter = select_experiment(obs, b_only_draws())
    three_parameters = select_experiment(obs, joint)
    assert one_parameter['schedule'] == 'early'
    assert three_parameters['schedule'] == 'late'
    for result in (one_parameter, three_parameters):
        scores = sorted((row['score'] for row in result['scores']), reverse=True)
        assert scores[0] - scores[1] > .01
    assert 'not exact expected information gain' in three_parameters['score_kind']
    assert 'temporal noise dependence' in three_parameters['assumptions']


def test_fixed_and_random_controls_do_not_select_from_beliefs():
    obs = legal_observation()
    first = b_only_draws()
    second = np.random.default_rng(77).uniform([2., .5, 0.], [8., 3., .8], (512, 3))
    assert select_experiment(obs, first, strategy='fixed')['schedule'] == 'split'
    assert select_experiment(obs, second, strategy='fixed')['schedule'] == 'split'
    chosen = set()
    for seed in range(12):
        left = select_experiment(obs, first, strategy='random', seed=seed)
        right = select_experiment(obs, second, strategy='random', seed=seed)
        assert left['schedule'] == right['schedule']
        chosen.add(left['schedule'])
    assert chosen == set(SCHEDULES)


def test_scoring_preserves_inputs_and_all_external_random_streams():
    obs, draws = legal_observation(), b_only_draws()
    original, original_draws = deepcopy(obs), draws.copy()
    numpy_state, python_state = pickle.dumps(np.random.get_state()), random.getstate()
    first = select_experiment(obs, draws, strategy='random', seed=308)
    assert first == select_experiment(obs, draws, strategy='random', seed=308)
    assert obs == original
    np.testing.assert_array_equal(draws, original_draws)
    assert pickle.dumps(np.random.get_state()) == numpy_state
    assert random.getstate() == python_state
    permutation = np.random.default_rng(18).permutation(len(draws))
    permuted = select_experiment(obs, draws[permutation])
    reference = select_experiment(obs, draws)
    assert permuted['schedule'] == reference['schedule']
    np.testing.assert_allclose([row['score'] for row in permuted['scores']],
                               [row['score'] for row in reference['scores']], atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize('change', [
    {'treasury': 0.}, {'treasury': -1.}, {'current_stock': 10.}, {'weather': 1.},
    {'world_parameters': {'r': 4.6}}, {'infrastructure': float('nan')},
])
def test_acquisition_rejects_missing_budget_and_privileged_fields(change):
    obs = legal_observation()
    obs.update(change)
    with pytest.raises(ValueError):
        select_experiment(obs, b_only_draws())


@pytest.mark.parametrize('change', [{'tick': 8}, {'patch': 1}, {'sensor_sigma': 0.}, {'growth': float('nan')}])
def test_acquisition_enforces_lagged_home_sensor_contract(change):
    obs = legal_observation()
    obs['last_growth'].update(change)
    with pytest.raises(ValueError):
        select_experiment(obs, b_only_draws())


@pytest.mark.parametrize('draws', [
    [[4.6, 1.7, .3]], [[1., 1.7, .3], [4.6, 1.7, .3]],
    [[4.6, 1.7, 1.], [4.6, 1.7, .3]], [[4.6, np.nan, .3], [4.6, 1.7, .3]],
])
def test_acquisition_rejects_unbounded_or_degenerate_particle_arrays(draws):
    with pytest.raises(ValueError):
        select_experiment(legal_observation(), draws)


@pytest.mark.parametrize('strategy,seed', [('unknown', 0), ('active', -1), ('random', True)])
def test_invalid_selection_controls_fail_explicitly(strategy, seed):
    with pytest.raises(ValueError):
        select_experiment(legal_observation(), b_only_draws(), strategy=strategy, seed=seed)
