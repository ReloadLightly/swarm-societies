"""Independent distribution checks for the approved Ticket D extension."""
from copy import deepcopy
from dataclasses import replace
import json
import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ndtri
from scipy.stats import truncnorm

from swarm_societies.commons_v3.evidence_sites_v1 import CleanTransition
from swarm_societies.commons_v3.messages_sites_v1 import GrowthEvidence
from swarm_societies.commons_v3.posterior_sites_v1 import SitePosterior
from swarm_societies.commons_v3.posterior_social_sites_v1 import (
    MIN_LOG_SIGMA, SocialSitePosterior, belief_parameters,
)


def pure_report_reference(reports, *, biased=False, lower=8.):
    """Closed-form distribution in log K, independent of engine quadrature.

    A log-uniform prior times n lognormal densities is a truncated normal
    in log K with mean (sum(mu/sigma²)-n)/sum(1/sigma²). The biased prior
    simply reweights its two pieces at 50.
    """
    parameters = [(math.log(m), max(math.asinh(d / (2 * m)) / ndtri(.75),
                                   math.log(12.5) / 400)) for m, d in reports]
    precision = math.fsum(1 / sigma ** 2 for _, sigma in parameters)
    mean = (math.fsum(mu / sigma ** 2 for mu, sigma in parameters) - len(reports)) / precision
    sigma = 1 / math.sqrt(precision)
    normal = truncnorm((math.log(lower) - mean) / sigma,
                       (math.log(100.) - mean) / sigma, loc=mean, scale=sigma)
    split = normal.cdf(math.log(50.))
    low_weight = .01 if biased else 1.
    high_weight = .01 + .99 * math.log(12.5) / math.log(2.) if biased else 1.
    normalization = low_weight * split + high_weight * (1 - split)

    def cdf(k):
        u = normal.cdf(math.log(k))
        return (low_weight * min(u, split) + high_weight * max(0., u - split)) / normalization

    def quantile(q):
        split_mass = low_weight * split / normalization
        u = q * normalization / low_weight if q <= split_mass else (
            split + (q * normalization - low_weight * split) / high_weight)
        return math.exp(normal.ppf(u))

    return cdf, quantile


def test_biased_prior_matches_analytic_mixture_including_density_jump():
    posterior = SocialSitePosterior(biased=True)
    split = .01 * math.log(50. / 8.) / math.log(12.5)
    for k in (8., 12.3, 49.999, 50., 61.25, 100.):
        expected = .01 * math.log(k / 8.) / math.log(12.5)
        if k > 50.:
            expected += .99 * math.log(k / 50.) / math.log(2.)
        assert posterior.cdf(k) == pytest.approx(expected, abs=2e-13)
    for q in (.001, split, .01, .25, .5, .95):
        expected = (8. * math.exp(q * math.log(12.5) / .01) if q <= split else
                    math.exp((q + .01 * math.log(8.) / math.log(12.5)
                              + .99 * math.log(50.) / math.log(2.))
                             / (.01 / math.log(12.5) + .99 / math.log(2.))))
        assert posterior.quantile(q) == pytest.approx(expected, abs=3e-10)
    assert posterior.atoms == {}
    assert posterior.continuous_mass == pytest.approx(1., abs=2e-13)


@pytest.mark.parametrize("events", [
    [(4., 4.8), (4., 4.79)], [(20., 24.), (20., 24.01)],
    [(99.95, 99.976), (98.976, 99.23)],
])
def test_common_prior_without_fusion_is_exactly_frozen_c(events):
    original, social = SitePosterior(), SocialSitePosterior()
    for tick, (z, y) in enumerate(events):
        original.update(CleanTransition(0, tick, z, y, z, 0.))
        social.update_event(GrowthEvidence(0, tick, z, y))
        assert original.atoms == social.atoms
        assert original.continuous_mass == social.continuous_mass
        assert original.memory()["operations"] == social.memory()["operations"]
        for q in (.05, .25, .5, .75, .95):
            assert original.quantile(q) == social.quantile(q)
        for x in (y, 25., 60., 99.99):
            assert original.cdf(x) == social.cdf(x)
            assert original.predictive_cdf(x, z) == social.predictive_cdf(x, z)


def test_biased_prior_can_recover_below_fifty_from_exact_growth():
    common, biased = SocialSitePosterior(), SocialSitePosterior(biased=True)
    first = GrowthEvidence(0, 0, 20., 20.027)
    for posterior in (common, biased):
        posterior.update_event(first)
        assert posterior.cdf(50.) == pytest.approx(1., abs=1e-12)
        assert posterior.quantile(.95) < 20.1
    assert biased.atoms == pytest.approx(common.atoms, abs=1e-11)
    assert biased.interval() == pytest.approx(common.interval(), abs=1e-10)
    biased.update_event(GrowthEvidence(0, 1, first.stock_next, first.stock_next))
    assert biased.atoms == {first.stock_next: 1.}


@pytest.mark.parametrize("biased,reports", [
    (False, [(35., 20.)]),
    (True, [(35., 20.), (60., 10.), (32., 8.)]),
    (True, [(50., 0.)] * 64),
    (False, [(37.1234, 0.)] * 128),
    (True, [(35., 0.), (65., 0.)] * 64),
])
def test_report_products_match_closed_form_even_below_original_bin_width(biased, reports):
    posterior = SocialSitePosterior(biased=biased)
    for median, iqr in reports:
        posterior.fuse(median, iqr)
    cdf, quantile = pure_report_reference(reports, biased=biased)
    for q in (.01, .05, .25, .5, .75, .95, .99):
        expected = quantile(q)
        assert posterior.quantile(q) == pytest.approx(expected, abs=2e-8)
        assert posterior.cdf(expected) == pytest.approx(cdf(expected), abs=1e-8)
    assert posterior.atoms == {}
    assert posterior.continuous_mass == pytest.approx(1., abs=2e-11)


def test_zero_iqr_reports_retain_fixed_positive_width_and_repeated_reports_count():
    assert belief_parameters(40., 0.) == (math.log(40.), math.log(12.5) / 400)
    assert MIN_LOG_SIGMA == math.log(12.5) / 400
    posterior = SocialSitePosterior()
    posterior.fuse(40., 0.)
    first_width = posterior.quantile(.75) - posterior.quantile(.25)
    first_revision = posterior.revision
    posterior.fuse(40., 0.)
    assert posterior.quantile(.75) - posterior.quantile(.25) < first_width
    assert posterior.atoms == {}
    assert posterior.revision > first_revision
    assert sum(op["kind"] == "fusion" for op in posterior.memory()["operations"]) == 2


@pytest.mark.parametrize("lower,median", [(60., 40.), (99.9, 8.)])
def test_narrow_report_tail_truncated_by_legal_stock_bound_is_resolved(lower, median):
    reports = [(median, 0.)] * 64
    posterior = SocialSitePosterior()
    posterior.observe_stock(lower)
    for report in reports:
        posterior.fuse(*report)
    cdf, quantile = pure_report_reference(reports, lower=lower)
    for q in (.05, .25, .5, .75, .95):
        expected = quantile(q)
        assert posterior.quantile(q) == pytest.approx(expected, abs=2e-8)
        assert posterior.cdf(expected) == pytest.approx(cdf(expected), abs=3e-7)
    assert posterior.cdf(lower) == 0.
    assert posterior.quantile(.5) > lower


@pytest.mark.parametrize("reports", [[(99.98, 0.)], [(80., 20.), (99.985, 0.)] * 16])
def test_existing_mixed_atom_is_reweighted_by_same_density_as_continuum(reports):
    z, y = 99.95, 99.976
    a, b = .24 * z + .02, .24 * z * z
    g, width = y - z, 1.1 - .9
    lo = max(y, b / (a - g / 1.1))
    hi = min(100., b / (a - g / .9))
    p_at_y = .24 * z * (1. - z / y) + .02
    atom = min(1., max(0., (1.1 - g / p_at_y) / width)) / y

    def log_report_density(k):
        return math.fsum(-math.log(k) - .5 * ((math.log(k / m)) / max(
            math.asinh(d / (2 * m)) / ndtri(.75), math.log(12.5) / 400)) ** 2
                         for m, d in reports)

    offset = log_report_density(y)

    def density(k):
        return math.exp(log_report_density(k) - offset) / (width * (a * k - b))

    mass = quad(density, lo, hi, epsabs=1e-11, epsrel=1e-11)[0]
    normalization = atom + mass
    posterior = SocialSitePosterior()
    posterior.update_event(GrowthEvidence(0, 0, z, y))
    for report in reports:
        posterior.fuse(*report)
    assert posterior.atoms == pytest.approx({y: atom / normalization}, abs=2e-9)
    assert posterior.continuous_mass == pytest.approx(mass / normalization, abs=2e-9)
    for x in (y, (lo + hi) / 2, hi):
        expected = (atom + quad(density, lo, max(lo, x), epsabs=1e-11)[0]) / normalization
        assert posterior.cdf(x) == pytest.approx(expected, abs=2e-9)
    assert posterior.cdf(y, left=True) == 0.


def test_canonical_event_duplicate_and_conflict_have_distinct_semantics():
    posterior = SocialSitePosterior()
    event = GrowthEvidence(0, 3, 99.95, 99.976)
    assert posterior.update_event(event)
    saved, revision = posterior.memory(), posterior.revision
    assert posterior.update_event(event) is False
    assert posterior.memory() == saved
    assert posterior.revision == revision
    with pytest.raises(ValueError, match="conflicting"):
        posterior.update_event(replace(event, stock_next=99.977))
    assert posterior.memory() == saved
    assert posterior.revision == revision
    posterior.update_event(GrowthEvidence(0, 4, event.stock_next, event.stock_next))
    assert posterior.atoms == {event.stock_next: 1.}
    posterior.fuse(8., 0.)
    assert posterior.atoms == {event.stock_next: 1.}


@pytest.mark.parametrize("event", [
    GrowthEvidence(1, 0, 4., 4.8), GrowthEvidence(False, 0, 4., 4.8),
    GrowthEvidence(0, True, 4., 4.8), GrowthEvidence(0, 0, float("nan"), 4.8),
    GrowthEvidence(0, 0, 4., 50.), {"site": 0, "tick": 0, "z": 4., "stock_next": 4.8},
])
def test_invalid_event_does_not_change_posterior_or_revision(event):
    posterior = SocialSitePosterior(biased=True)
    saved, revision = posterior.memory(), posterior.revision
    with pytest.raises(ValueError):
        posterior.update_event(event)
    assert posterior.memory() == saved
    assert posterior.revision == revision


@pytest.mark.parametrize("median,iqr", [
    (7., 1.), (101., 1.), (40., -1.), (40., 93.),
    (True, 0.), (40., False), (float("nan"), 0.), (40., float("inf")),
])
def test_invalid_report_does_not_change_posterior_or_revision(median, iqr):
    posterior = SocialSitePosterior()
    saved, revision = posterior.memory(), posterior.revision
    with pytest.raises(ValueError):
        posterior.fuse(median, iqr)
    assert posterior.memory() == saved
    assert posterior.revision == revision


def test_serialization_replays_prior_growth_fusion_and_continuation_exactly():
    posterior = SocialSitePosterior(site=2, biased=True)
    posterior.observe_stock(99.96)
    posterior.update_event(GrowthEvidence(2, 0, 99.95, 99.976))
    posterior.fuse(90., 10.)
    posterior.fuse(99.98, 0.)
    saved = json.loads(json.dumps(posterior.memory(), allow_nan=False))
    restored = SocialSitePosterior.restore(saved)
    assert restored.memory() == saved
    assert restored.revision == posterior.revision
    for model in (posterior, restored):
        model.update_event(GrowthEvidence(2, 1, 98.976, 99.23))
        model.fuse(98., 3.)
    assert restored.memory() == posterior.memory()
    assert restored.atoms == posterior.atoms
    assert restored.continuous_mass == posterior.continuous_mass
    assert restored.interval() == posterior.interval()
    assert restored.revision == posterior.revision
    saved["operations"].clear()
    assert restored.memory() == posterior.memory()


def test_restore_rejects_noncanonical_operation_history():
    posterior = SocialSitePosterior()
    posterior.observe_stock(40.)
    saved = posterior.memory()
    duplicate = deepcopy(saved)
    duplicate["operations"].append(deepcopy(duplicate["operations"][0]))
    for invalid in (duplicate, {**saved, "biased": 1},
                    {**saved, "version": "unknown"}, {**saved, "operations": [{}]}):
        with pytest.raises(ValueError):
            SocialSitePosterior.restore(invalid)


@pytest.mark.parametrize("count", [100, 300, 500])
@pytest.mark.parametrize("mixed", [False, True])
def test_long_synthetic_density_history_is_bit_identical_to_frozen_c(count, mixed):
    """Synthetic likelihood stress check, without simulating an arena.

    Extend an admissible support with repeated smooth likelihood factors. This
    directly exercises long history arithmetic, including a surviving off-grid
    atom, without spending hundreds of physical experimental transitions.
    """
    original, social = SitePosterior(), SocialSitePosterior()
    z, y = (99.95, 99.976) if mixed else (20., 22.42)
    repeated_z = 98.976 if mixed else 20.
    for posterior in (original, social):
        posterior.update(CleanTransition(0, 0, z, y, z, 0.))
        posterior._terms.extend([repeated_z] * (count - 1))
        for capacity in posterior._atoms_log:
            increment = math.log((1.1 - .9) * (.24 * repeated_z * (1. - repeated_z / capacity) + .02))
            for _ in range(count - 1):
                posterior._atoms_log[capacity] -= increment
        posterior._refresh()
    assert original._log_scale == social._log_scale
    assert np.array_equal(original._mass, social._mass)
    assert original.atoms == social.atoms
    assert original.continuous_mass == social.continuous_mass
    for shape in ((8,), (1, 8), (20, 8), (400, 8)):
        points = np.linspace(original._lo, original._hi, math.prod(shape)).reshape(shape)
        assert np.array_equal(original._logpdf(points), social._logpdf(points))
    span = original._hi - original._lo
    probes = [8., y, 100., original._lo, original._hi,
              *(original._lo + fraction * span for fraction in (1e-6, .001, .01, .1, .5, .9))]
    for value in probes:
        for left in (False, True):
            assert original.cdf(value, left=left) == social.cdf(value, left=left)
    for q in (.001, .05, .25, .5, .75, .95, .999):
        assert original.quantile(q) == social.quantile(q)


@pytest.mark.parametrize("biased", [False, True])
def test_ordered_vectorization_preserves_preoptimization_fused_density_bits(biased):
    posterior = SocialSitePosterior(biased=biased)
    posterior.update_event(GrowthEvidence(0, 0, 99.95, 99.976))
    posterior._terms.extend([98.976] * 299)
    posterior.fuse(80., 20.)
    posterior.fuse(99.985, 0.)
    points = np.linspace(posterior._lo, posterior._hi, 160).reshape(20, 8)
    # This is the former implementation: frozen C first, then the unchanged
    # biased-prior and completed-square fusion factors.
    expected = SitePosterior._logpdf(posterior, points)
    if biased:
        expected += np.log(np.where(points < 50., .01,
                                    .01 + .99 * math.log(12.5) / math.log(2.)))
    expected = (expected - posterior._fusion_count * np.log(points)
                - .5 * posterior._fusion_precision * (np.log(points) - posterior._fusion_mu) ** 2)
    assert np.array_equal(expected, posterior._logpdf(points))


def test_cdf_memoization_uses_exact_frozen_results_and_is_revision_private(monkeypatch):
    posterior = SocialSitePosterior()
    saved = posterior.memory()
    frozen_cdf = SitePosterior.cdf
    calls = []

    def counted(self, value, left=False):
        calls.append((value, left))
        return frozen_cdf(self, value, left=left)

    monkeypatch.setattr(SitePosterior, "cdf", counted)
    expected = frozen_cdf(posterior, 50.)
    assert posterior.cdf(50.) == posterior.cdf(50.) == expected
    assert calls == [(50., False)]
    assert posterior.cdf(50., left=True) == expected
    assert calls == [(50., False), (50., True)]
    assert posterior.memory() == saved
    posterior.observe_stock(40.)
    assert posterior.cdf(50.) == frozen_cdf(posterior, 50.)
    assert len(calls) == 3
    with pytest.raises(ValueError):
        posterior.cdf(True)
