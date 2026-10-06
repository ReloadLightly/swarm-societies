"""Independent accounting, timing and information controls for the fixed planner."""

from copy import deepcopy

import numpy as np
import pytest

from swarm_societies.world_model_v1.decision import (
    PRIOR_BOUNDS, forecast, observation, validate_observation,
)


def legal_inputs():
    institution = {
        'tick': 32, 'society_id': 0, 'n_societies': 3, 'treasury': 0,
        'infrastructure': 0, 'mean_wealth': 100,
        'members': [{'id': member, 'wealth': 100} for member in range(4)],
        'reports': [],
    }
    packet = {
        'event_id': 'development/growth:31:0', 'tick': 31, 'patch': 0,
        'phase': 'before_actions', 'stock_before': 0, 'capacity': 30,
        'own_infrastructure': 0, 'other_infrastructure': 0,
        'growth': 0, 'sensor_sigma': .05,
    }
    return institution, packet


def known_draws(b=.7, n=512, r=2.4, g=0.):
    return np.tile([r, b, g], (n, 1))


@pytest.mark.parametrize('horizon', [1, 2, 32])
@pytest.mark.parametrize('b', [.7, 2.7])
def test_uncapped_abundant_wealth_matches_analytic_investment_return(horizon, b):
    """Current allocation has zero renewal benefit; only subsequent ticks pay."""
    obs = observation(*legal_inputs())
    result = forecast(obs, known_draws(b), seed=809, horizon=horizon)
    budget = result['actions'][0]['initial_budget']
    gross_return = (.125 / 4) * b * sum(.96 ** tick for tick in range(1, horizon))
    for action, paired in zip(result['actions'], result['paired']):
        fraction = action['public_fraction']
        expected = .2 * fraction * budget * (gross_return - 1) / 4
        assert paired['minus_redistribute'] == pytest.approx(expected, abs=2e-13)
        assert action['initial_budget'] == budget
        assert action['investment'] == pytest.approx(fraction * budget)
        assert action['consumption_per_member'] == pytest.approx(horizon * .85)
        assert action['shortfall_per_member'] == pytest.approx(0.)
        assert action['utility'] == pytest.approx(
            action['consumption_per_member'] + .2 * action['terminal_wealth_per_member'])
    assert result['action'] == (1. if horizon == 32 and b == 2.7 else 0.)


def test_one_tick_consumption_preserves_scarce_harvest_distribution():
    """One winner keeps untaxed harvest; equal-splitting would overstate consumption."""
    institution, packet = legal_inputs()
    institution['members'] = [{'id': member, 'wealth': 0} for member in range(4)]
    institution['mean_wealth'] = 0
    obs = observation(institution, packet)
    result = forecast(obs, known_draws(r=2.), seed=53, horizon=1)
    redistribute = result['actions'][0]
    mean_supply = redistribute['initial_budget'] / .6
    # All supply fits one member's 2.4-unit harvest request. That member consumes
    # .85 and three other members consume only the equal .15*supply tax transfers.
    expected_consumption = (.85 + .45 * mean_supply) / 4
    assert redistribute['consumption_per_member'] == pytest.approx(expected_consumption)
    assert redistribute['consumption_per_member'] < mean_supply / 4
    assert result['action'] == 0.


def test_frozen_prior_and_known_law_use_identical_interface_without_mutation():
    institution, packet = legal_inputs()
    obs = observation(institution, packet)
    original = deepcopy(obs)
    rng = np.random.default_rng(719)
    coefficients = rng.uniform(PRIOR_BOUNDS[:, 0], PRIOR_BOUNDS[:, 1], (512, 3))
    before = coefficients.copy()
    first = forecast(obs, coefficients, seed=283)
    assert forecast(obs, coefficients, seed=283) == first
    np.testing.assert_array_equal(coefficients, before)
    assert obs == original
    assert first['n_samples'] == 512
    assert first['action'] in (0., .5, 1.)
    assert all(np.isfinite(row['utility']) and np.isfinite(row['utility_mcse'])
               for row in first['actions'])
    low = forecast(obs, known_draws(.7), seed=283)
    high = forecast(obs, known_draws(2.7), seed=283)
    assert low['action'] == 0. and high['action'] == 1.
    for result in (low, high):
        contrast = result['paired'][-1]
        assert abs(contrast['minus_redistribute']) > max(.005, 3 * contrast['paired_mcse'])


def test_lagged_noisy_stock_is_clipped_before_nominal_previous_harvest():
    institution, packet = legal_inputs()
    packet['growth'] = 1000.
    saturated = forecast(observation(institution, packet), known_draws(), seed=32, horizon=1)
    assert saturated['actions'][0]['initial_budget'] == pytest.approx(4 * 2.4 * .6)
    packet['growth'] = -1000.
    negative = forecast(observation(institution, packet), known_draws(), seed=32, horizon=1)
    packet['growth'] = 0.
    empty = forecast(observation(institution, packet), known_draws(), seed=32, horizon=1)
    assert negative == empty
    assert empty['actions'][0]['initial_budget'] < 2.


def test_current_budget_is_forecast_from_current_growth_and_treasury():
    institution, packet = legal_inputs()
    institution['treasury'] = 1.25
    institution['infrastructure'] = 1.
    packet['other_infrastructure'] = 2.
    result = forecast(observation(institution, packet), known_draws(b=.7, g=.3),
                      seed=112, horizon=1)
    weather = np.random.default_rng(112).uniform(.85, 1.15, (1, 512))[0]
    # Current own infrastructure is already decayed. The previous external
    # measurement receives one extra decay; this explicitly omits last investment.
    expected = 1.25 + .6 * np.mean(2.4 * weather + .7 * 1. + .3 * .96 * 2.)
    assert all(row['initial_budget'] == pytest.approx(expected) for row in result['actions'])


@pytest.mark.parametrize('change', [
    {'tick': 32}, {'tick': 33}, {'tick': 30}, {'patch': 1}, {'patch': False},
    {'phase': 'after_allocation'}, {'event_id': ''}, {'capacity': 0},
    {'stock_before': 31}, {'sensor_sigma': -1}, {'growth': float('nan')},
    {'weather': 1.}, {'true_parameters': {'r': 2.4}}, {'budget': 2.},
])
def test_current_foreign_hidden_and_invalid_growth_fields_are_rejected(change):
    institution, packet = legal_inputs()
    packet.update(change)
    with pytest.raises(ValueError):
        observation(institution, packet)


@pytest.mark.parametrize('field', ['current_stock', 'weather', 'rng_state', 'world_parameters'])
def test_institution_extra_fields_cannot_enter_planner(field):
    institution, packet = legal_inputs()
    institution[field] = 1
    with pytest.raises(ValueError):
        observation(institution, packet)


def test_nested_member_metadata_and_wrong_identity_are_rejected():
    institution, packet = legal_inputs()
    institution['members'][0]['productivity'] = 1.1
    with pytest.raises(ValueError):
        observation(institution, packet)
    institution, packet = legal_inputs()
    institution['members'][0]['id'] = 1
    with pytest.raises(ValueError):
        observation(institution, packet)


def test_observation_builder_severs_nested_input_references():
    institution, packet = legal_inputs()
    obs = observation(institution, packet)
    institution['members'][0]['wealth'] = 17
    packet['growth'] = 9
    assert obs['wealth'][0] == 100
    assert obs['last_growth']['growth'] == 0
    obs['current_growth'] = 2
    with pytest.raises(ValueError):
        validate_observation(obs)


@pytest.mark.parametrize('coefficients', [
    [[2.4, .7, 0.]], [[2.4, .7], [2.4, .7]],
    [[1.99, .7, 0.], [2.4, .7, 0.]],
    [[2.4, 3.01, 0.], [2.4, .7, 0.]],
    [[2.4, .7, -.01], [2.4, .7, 0.]],
    [[2.4, .7, float('nan')], [2.4, .7, 0.]],
])
def test_coefficients_require_bounded_finite_joint_draws(coefficients):
    with pytest.raises(ValueError):
        forecast(observation(*legal_inputs()), coefficients, seed=1)


@pytest.mark.parametrize('menu', [(), (.5, 1.), (0., 1., .5), (0., .5, .5), (0., 1.1)])
def test_reported_redistribution_reference_is_required(menu):
    with pytest.raises(ValueError):
        forecast(observation(*legal_inputs()), known_draws(), seed=1, menu=menu)


def test_zero_budget_ties_choose_redistribution():
    institution, packet = legal_inputs()
    # Disable tax with an empty treasury to get exactly zero spending.
    obs = observation(institution, packet, tax_rate=0.)
    result = forecast(obs, known_draws(2.7), seed=149)
    assert result['action'] == 0.
    assert len({row['utility'] for row in result['actions']}) == 1
