"""Independent analytic/integration checks, not the G2 calibration bank."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest
from scipy.integrate import quad

from swarm_societies.commons_v3.evidence_sites_v1 import CleanTransition
from swarm_societies.commons_v3.posterior_sites_v1 import SitePosterior


def transition(z, y, *, tick=0, before=None, site=0):
    before = z if before is None else before
    return CleanTransition(site, tick, z, y, before, before - z)


def one_step_reference(event, prior_low=8.):
    """Closed-form continuous integral plus the off-grid saturation atom.

    The prior normalization cancels. Its density is proportional to 1/K, so
    integrating 1/[K*.2*P(K)] gives log(a*K-b)/(.2*a).
    """
    z, y = event.z, event.stock_next
    prior_low = max(prior_low, event.stock_before)
    a, b, width = .24 * z + .02, .24 * z * z, 1.1 - .9
    g = y - z
    if b == 0:
        lower, upper = (max(prior_low, y), 100.) if .9 * a <= g <= 1.1 * a else (100., 8.)
    elif g / 1.1 >= a:
        lower, upper = 100., 8.
    else:
        lower = max(prior_low, y, b / (a - g / 1.1))
        upper = min(100., b / (a - g / .9) if g / .9 < a else math.inf)

    def integral(left, right):
        if right <= left:
            return 0.
        return math.log((a * right - b) / (a * left - b)) / (width * a)

    raw_atom = 0.
    if prior_low <= y <= 100.:
        p = .24 * z * (1. - z / y) + .02
        clip = min(1., max(0., (1.1 - g / p) / width))
        raw_atom = clip / y
    raw_continuous = integral(lower, upper)
    normalizer = raw_atom + raw_continuous
    assert normalizer > 0

    def cdf(x, left=False):
        atom = raw_atom if x > y or (x == y and not left) else 0.
        return (atom + integral(lower, min(x, upper))) / normalizer

    def density(k):
        if not lower < k < upper:
            return 0.
        return 1. / (width * (a * k - b) * normalizer)

    return {"atom": raw_atom / normalizer, "continuous": raw_continuous / normalizer,
            "lower": lower, "upper": upper, "cdf": cdf, "density": density}


def conditional_cdf(y, z, capacity, left=False):
    """Direct conditional observation CDF; no posterior implementation helpers."""
    p = .24 * z * (1 - z / capacity) + .02
    if y > capacity or (y == capacity and not left):
        return 1.
    return min(1., max(0., ((y - z) / p - .9) / (1.1 - .9)))


def integration_cuts(z, y, low, high):
    a, b = .24 * z + .02, .24 * z * z
    cuts = [low, high, y]
    for weather in (.9, 1.1):
        denominator = a - (y - z) / weather
        if denominator > 0:
            cuts.append(b / denominator)
    return sorted({min(high, max(low, point)) for point in cuts})


def integrate_pieces(function, cuts, upper=math.inf):
    return math.fsum(quad(function, left, min(right, upper), epsabs=1e-12,
                          epsrel=1e-11, limit=100)[0]
                     for left, right in zip(cuts, cuts[1:]) if left < min(right, upper))


def test_initial_prior_quantiles_cdf_and_interval_are_continuous_log_uniform():
    posterior = SitePosterior()
    assert posterior.atoms == {}
    assert posterior.continuous_mass == pytest.approx(1., abs=1e-13)
    for q in (.001, .05, .25, .5, .75, .95, .999):
        expected = 8. * (100. / 8.) ** q
        assert posterior.quantile(q) == pytest.approx(expected, abs=1e-10)
        assert posterior.cdf(expected) == pytest.approx(q, abs=1e-12)
        assert posterior.cdf(expected, left=True) == posterior.cdf(expected)
    assert posterior.interval() == pytest.approx((8. * 12.5 ** .05, 8. * 12.5 ** .95), abs=1e-10)
    assert posterior.cdf(0.) == 0.
    assert posterior.cdf(200.) == pytest.approx(1., abs=1e-13)


def test_stock_bound_truncates_prior_and_weaker_bound_does_not_change_memory():
    posterior = SitePosterior()
    posterior.observe_stock(40.013)
    assert posterior.cdf(40.013) == 0.
    assert posterior.quantile(.5) == pytest.approx(math.sqrt(40.013 * 100.), abs=1e-10)
    assert posterior.cdf(60.) == pytest.approx(math.log(60. / 40.013) / math.log(100. / 40.013), abs=1e-12)
    before = posterior.memory()
    posterior.observe_stock(30.)
    posterior.observe_stock(40.013)
    assert posterior.memory() == before


@pytest.mark.parametrize("z,y", [(0., .02), (4., 4.8), (20., 24.),
                                (99.95, 99.976), (99.98, 99.99)])
def test_one_step_likelihood_matches_closed_form_integral_and_off_grid_atom(z, y):
    event = transition(z, y)
    reference = one_step_reference(event)
    posterior = SitePosterior()
    posterior.update(event)
    assert posterior.continuous_mass == pytest.approx(reference["continuous"], abs=2e-9)
    assert posterior.atoms.get(y, 0.) == pytest.approx(reference["atom"], abs=2e-9)
    probes = [0., 8., 25., 70., 100., y,
              (reference["lower"] + reference["upper"]) / 2]
    for x in probes:
        assert posterior.cdf(x) == pytest.approx(reference["cdf"](x), abs=2e-9)
        assert posterior.cdf(x, left=True) == pytest.approx(reference["cdf"](x, left=True), abs=2e-9)
    assert posterior.continuous_mass + sum(posterior.atoms.values()) == pytest.approx(1., abs=2e-12)


def test_off_grid_mixed_observation_does_not_claim_certain_saturation():
    posterior = SitePosterior()
    event = transition(99.95, 99.976)
    posterior.update(event)
    mass = posterior.atoms[event.stock_next]
    assert .2 < mass < .23
    assert .77 < posterior.continuous_mass < .8
    assert posterior.cdf(event.stock_next, left=True) == 0.
    assert posterior.cdf(event.stock_next) == pytest.approx(mass)
    assert posterior.quantile(mass / 2) == event.stock_next
    assert posterior.quantile(.75) > event.stock_next


def test_duplicate_event_cannot_turn_ambiguous_saturation_into_certainty():
    posterior = SitePosterior()
    event = transition(99.95, 99.976)
    posterior.update(event)
    before = posterior.memory()
    mass = posterior.atoms[event.stock_next]
    posterior.update(event)
    assert posterior.memory() == before
    assert posterior.atoms[event.stock_next] == mass < 1.
    assert posterior.continuous_mass > 0
    posterior.update(transition(event.stock_next, event.stock_next, tick=1))
    assert posterior.atoms == {event.stock_next: 1.}
    assert posterior.continuous_mass == 0.
    assert posterior.interval() == (event.stock_next, event.stock_next)


def test_capacity_atom_survives_a_later_unclipped_transition_and_restoration():
    posterior = SitePosterior()
    first = transition(99.95, 99.976)
    posterior.update(first)
    second = transition(98.976, 99.23, tick=1, before=99.976)
    posterior.update(second)
    assert 0 < posterior.atoms[first.stock_next] < 1
    assert second.stock_next not in posterior.atoms
    assert posterior.continuous_mass > 0
    saved = json.loads(json.dumps(posterior.memory(), allow_nan=False))
    restored = SitePosterior.restore(saved)
    assert restored.memory() == posterior.memory()
    assert restored.atoms == posterior.atoms
    assert restored.continuous_mass == posterior.continuous_mass
    third = transition(99.23, 99.43, tick=2)
    posterior.update(third)
    restored.update(third)
    assert restored.memory() == posterior.memory()
    assert restored.atoms == posterior.atoms
    for q in (.05, .5, .95):
        assert restored.quantile(q) == posterior.quantile(q)
    # Returned memories cannot mutate either posterior.
    saved["operations"][0]["stock"] = 0.
    assert restored.memory() == posterior.memory()


def test_sub_bin_off_grid_support_stays_nonempty_and_matches_analytic_cdf():
    # No point of the original 400-point log grid lies in this posterior's
    # continuous interval. Integrating the bin fragment retains its mass.
    event = transition(99.95, 99.976)
    reference = one_step_reference(event)
    grid = [8. * (100. / 8.) ** (i / 399) for i in range(400)]
    assert not any(reference["lower"] < k < reference["upper"] for k in grid)
    posterior = SitePosterior()
    posterior.update(event)
    middle = (reference["lower"] + reference["upper"]) / 2
    assert posterior.continuous_mass > .7
    assert posterior.cdf(middle) == pytest.approx(reference["cdf"](middle), abs=2e-9)


@pytest.mark.parametrize("invalid", [
    transition(20., 50.),  # More renewal than any K in the prior can supply.
    transition(0., 0.),  # Positive recovery makes zero growth impossible.
    transition(4., 3.),
    CleanTransition(0, 0, 3., 4., 4., 0.),
    CleanTransition(0, 0, -1., 1., 0., 1.),
    CleanTransition(0, -1, 4., 4.8, 4., 0.),
    CleanTransition(0, True, 4., 4.8, 4., 0.),
    CleanTransition(False, 0, 4., 4.8, 4., 0.),
    CleanTransition(1, 0, 4., 4.8, 4., 0.),
    CleanTransition(0, 0, float("nan"), 4.8, 4., 0.),
    CleanTransition(0, 0, 4., float("inf"), 4., 0.),
])
def test_impossible_or_malformed_evidence_is_rejected_without_mutation(invalid):
    posterior = SitePosterior()
    before = posterior.memory()
    with pytest.raises(ValueError):
        posterior.update(invalid)
    assert posterior.memory() == before
    assert posterior.quantile(.5) == pytest.approx(math.sqrt(800.), abs=1e-10)


def test_conflicting_duplicate_event_is_rejected_without_mutation():
    posterior = SitePosterior()
    event = transition(4., 4.8)
    posterior.update(event)
    before = posterior.memory()
    with pytest.raises(ValueError):
        posterior.update(replace(event, stock_next=4.81))
    assert posterior.memory() == before


@pytest.mark.parametrize("stock", [-1., 101., float("nan"), float("inf"), True])
def test_invalid_stock_bound_is_atomic(stock):
    posterior = SitePosterior()
    before = posterior.memory()
    with pytest.raises(ValueError):
        posterior.observe_stock(stock)
    assert posterior.memory() == before


def test_bound_incompatible_with_existing_capacity_atom_is_atomic():
    posterior = SitePosterior()
    posterior.update(transition(99.98, 99.99))
    assert posterior.atoms == {99.99: 1.}
    before = posterior.memory()
    with pytest.raises(ValueError):
        posterior.observe_stock(99.995)
    assert posterior.memory() == before


@pytest.mark.parametrize("z,y,prior_low", [(0., .019, 8.), (4., 4.8, 8.),
                                           (99.95, 99.976, 99.95)])
def test_prior_predictive_cdf_matches_independent_integration_without_a_clip_label(z, y, prior_low):
    posterior = SitePosterior()
    posterior.observe_stock(max(z, prior_low))
    cuts = integration_cuts(z, y, prior_low, 100.)
    expected = integrate_pieces(lambda k: conditional_cdf(y, z, k) / (k * math.log(100. / prior_low)), cuts)
    assert posterior.predictive_cdf(y, z) == pytest.approx(expected, abs=2e-9)
    # Continuous capacity prior has a continuous predictive distribution even
    # though conditional Y|K can be clipped. There is no predictive atom yet.
    assert posterior.predictive_cdf(y, z, left=True) == posterior.predictive_cdf(y, z)


def test_mixed_posterior_predictive_cdf_has_jump_only_from_existing_capacity_atom():
    first = transition(99.95, 99.976)
    reference = one_step_reference(first)
    posterior = SitePosterior()
    posterior.update(first)
    z, y = first.z, first.stock_next
    cuts = integration_cuts(z, y, reference["lower"], reference["upper"])
    continuous = integrate_pieces(lambda k: conditional_cdf(y, z, k) * reference["density"](k), cuts)
    for left in (False, True):
        expected = continuous + reference["atom"] * conditional_cdf(y, z, y, left=left)
        assert posterior.predictive_cdf(y, z, left=left) == pytest.approx(expected, abs=2e-9)
    clipping = 1. - conditional_cdf(y, z, y, left=True)
    assert posterior.predictive_cdf(y, z) - posterior.predictive_cdf(y, z, left=True) == pytest.approx(
        posterior.atoms[y] * clipping, abs=2e-9)


def test_three_transition_posterior_matches_independent_adaptive_quadrature():
    events = [transition(20., 24., tick=0),
              transition(22., 26., tick=1, before=24.),
              transition(16., 19.3, tick=2, before=26.)]
    posterior = SitePosterior()
    for event in events:
        posterior.update(event)
    low = max(8., *(e.stock_before for e in events), *(e.stock_next for e in events))
    cuts = sorted({point for event in events for point in integration_cuts(event.z, event.stock_next, low, 100.)})
    def density(k):
        value = 1. / k
        for event in events:
            p = .24 * event.z * (1. - event.z / k) + .02
            g = event.stock_next - event.z
            if not k > event.stock_next or not .9 * p <= g <= 1.1 * p:
                return 0.
            value /= (1.1 - .9) * p
        return value
    norm = integrate_pieces(density, cuts)
    assert norm > 0.
    assert posterior.atoms == {}
    for x in (80., 82., 85., 90., 95., 99., 100.):
        expected = integrate_pieces(density, cuts, upper=x) / norm
        assert posterior.cdf(x) == pytest.approx(expected, abs=2e-9)
    restored = SitePosterior.restore(json.loads(json.dumps(posterior.memory())))
    assert restored.memory() == posterior.memory()
    assert restored.interval() == posterior.interval()


@pytest.mark.parametrize("mutation", ["version", "unknown_operation", "nonfinite", "conflicting_event"])
def test_serialization_rejects_invalid_or_conflicting_evidence(mutation):
    posterior = SitePosterior()
    posterior.update(transition(4., 4.8))
    memory = deepcopy(posterior.memory())
    if mutation == "version":
        memory["version"] = "unknown"
    elif mutation == "unknown_operation":
        memory["operations"].append({"kind": "clip_label", "known_capacity": 40.})
    elif mutation == "nonfinite":
        memory["operations"][0]["stock"] = float("nan")
    else:
        event = deepcopy(memory["operations"][-1])
        event["event"]["stock_next"] = 4.81
        memory["operations"].append(event)
    with pytest.raises(ValueError):
        SitePosterior.restore(memory)
