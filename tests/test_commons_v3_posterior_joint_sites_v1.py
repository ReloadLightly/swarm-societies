"""Joint-inference engineering checks, separate from synthetic Gate G2."""
from copy import deepcopy
import math
import random

import numpy as np

import pytest

from swarm_societies.commons_v3.messages_sites_v1 import GrowthEvidence
from swarm_societies.commons_v3.posterior_joint_sites_v1 import JointPosterior


def test_declared_priors_and_stock_bounds_leave_rate_independent():
    joint = JointPosterior(grid_size=32, rate_bins=8)
    first, second = joint.site(0), joint.site(1)
    for rate in (.13, .2, .24, .4):
        assert joint.rate_cdf(rate) == pytest.approx(math.log(rate / .12) / math.log(4), abs=1e-12)
    assert first.quantile(.5) == pytest.approx(math.sqrt(800), abs=1e-9)
    first.observe_stock(30.)
    assert first.quantile(.5) == pytest.approx(math.sqrt(3000), abs=1e-9)
    assert second.quantile(.5) == pytest.approx(math.sqrt(800), abs=1e-9)
    assert joint.rate_cdf(.24) == pytest.approx(.5, abs=1e-12)


def test_information_at_one_site_changes_another_capacity_through_shared_rate():
    joint = JointPosterior(grid_size=64, rate_bins=16)
    ambiguous = joint.site(1)
    ambiguous.observe_stock(20.)
    ambiguous.update_event(GrowthEvidence(1, 0, 20., 22.42))
    before, revision = ambiguous.quantile(.5), ambiguous.revision
    local_memory = deepcopy(ambiguous.memory()["operations"])
    rate_informative = joint.site(0)
    rate_informative.observe_stock(1.)
    rate_informative.update_event(GrowthEvidence(0, 0, 1., 1.254))
    assert ambiguous.revision > revision
    assert ambiguous.memory()["operations"] == local_memory
    assert ambiguous.quantile(.5) < before - 5.
    assert joint.rate_interval()[0] < .24 < joint.rate_interval()[1]


def test_single_transition_against_independent_scalar_integrals():
    from swarm_societies.commons_v3.calibration_joint_sites_v1 import reference_cdf
    for z, y in ((1., 1.25), (20., 22.42), (20., 20.027)):
        joint = JointPosterior()
        site = joint.site(0)
        site.observe_stock(z)
        site.update_event(GrowthEvidence(0, 0, z, y))
        for capacity in (y, 25., 40., 70.):
            for left in (False, True):
                assert site.cdf(capacity, left=left) == pytest.approx(
                    reference_cdf(z, y, capacity, left=left), abs=.0002)
        for rate in (.15, .24, .4):
            assert joint.rate_cdf(rate) == pytest.approx(
                reference_cdf(z, y, rate, variable="rate"), abs=.0002)


def test_repeated_saturation_makes_exact_capacity_but_not_exact_rate():
    joint = JointPosterior(grid_size=64, rate_bins=16)
    site = joint.site(0)
    site.observe_stock(19.973)
    site.update_event(GrowthEvidence(0, 0, 19.973, 20.))
    assert 0 < site.atoms[20.] < 1
    site.update_event(GrowthEvidence(0, 1, 20., 20.))
    assert site.atoms[20.] == pytest.approx(1., abs=1e-12)
    assert site.cdf(20., left=True) == 0
    assert site.quantile(.05) == site.quantile(.95) == 20.
    assert joint.rate_interval()[1] > joint.rate_interval()[0]
    # Subsequent extraction makes this atom contribute the ordinary
    # continuous weather density, while retaining its exact capacity.
    site.update_event(GrowthEvidence(0, 2, 10., 11.2))
    assert site.atoms[20.] == pytest.approx(1., abs=1e-12)
    assert site.quantile(.5) == 20.


def test_events_are_deduplicated_and_conflicting_replays_rejected():
    joint = JointPosterior(grid_size=32, rate_bins=8)
    event = GrowthEvidence(0, 3, 20., 22.42)
    joint.update_event(event)
    before = joint.memory()
    revision = joint.revision
    assert not joint.update_event(event)
    assert joint.memory() == before and joint.revision == revision
    with pytest.raises(ValueError, match="conflicting"):
        joint.update_event(GrowthEvidence(0, 3, 20., 22.43))
    assert joint.memory() == before


def test_impossible_evidence_rolls_back_the_coupled_state():
    joint = JointPosterior(grid_size=32, rate_bins=8)
    joint.update_event(GrowthEvidence(0, 0, 20., 22.42))
    before = joint.memory()
    cdf = joint.rate_cdf(.24)
    with pytest.raises(ValueError, match="zero joint"):
        joint.update_event(GrowthEvidence(0, 1, 20., 80.))
    assert joint.memory() == before
    assert joint.rate_cdf(.24) == cdf


def test_memory_restores_shared_evidence_exactly_and_is_detached():
    joint = JointPosterior(grid_size=32, rate_bins=8)
    joint.update_event(GrowthEvidence(0, 0, 20., 22.42))
    joint.update_event(GrowthEvidence(1, 0, 1., 1.254))
    memory = joint.memory()
    restored = JointPosterior.restore(memory)
    assert restored.memory() == memory
    assert restored.rate_cdf(.24) == joint.rate_cdf(.24)
    for site in (0, 1):
        assert restored.site(site).interval() == joint.site(site).interval()
    memory["operations"][0]["event"]["z"] = 0.
    assert joint.memory() == restored.memory()


def test_full_grid_is_pinned_against_bounded_query_cache_eviction():
    joint = JointPosterior(grid_size=32, rate_bins=8)
    view = joint.site(0)
    view.update_event(GrowthEvidence(0, 0, 20., 22.42))
    joint._refresh()
    full = view._evaluate(joint._rates)
    for shift in (.001, .002, .003, .004):
        view._evaluate(np.array([.23 + shift, .24 + shift]))
        assert view._evaluate(joint._rates) is full
        assert len(view._eval_cache) <= 2
    view.observe_stock(23.)
    assert view._full_eval is None


def test_pinned_cache_preserves_synthetic_record_bit_for_bit():
    from types import MethodType
    cached = JointPosterior(grid_size=32, rate_bins=8)
    uncached = JointPosterior(grid_size=32, rate_bins=8)
    for site in (0, 1):
        view = uncached.site(site)
        original = view._evaluate
        def force_recompute(self, rates, original=original):
            self._eval_cache.clear()
            self._full_eval_key = self._full_eval = None
            return original(rates)
        view._evaluate = MethodType(force_recompute, view)
    records = []
    for joint in (cached, uncached):
        frames = []
        for tick, pair in enumerate((((20., 22.42), (1., 1.254)),
                                     ((18., 20.37), (2., 2.476)))):
            for site, (z, y) in enumerate(pair):
                joint.update_event(GrowthEvidence(site, tick, z, y))
            frames.append({"rate": joint.rate_cdf(.24),
                           "sites": [[joint.site(site).quantile(q) for q in (.05, .25, .5, .95)]
                                     for site in (0, 1)]})
        records.append({"frames": frames, "memory": joint.memory()})
    assert records[0] == records[1]


@pytest.mark.parametrize("biased", [False, True])
@pytest.mark.parametrize("bound", [0., 8., 19.973, 49.99999999999999, 50.00000000000001, 80., 99.99999999999999])
def test_bound_only_log_evidence_preserves_every_bit(biased, bound):
    joint = JointPosterior(biased=biased)
    view = joint.site(0)
    if bound:
        view.observe_stock(bound)
    grids = [np.geomspace(.12, .48, 65), np.geomspace(.197, .19700000000001, 64),
             np.array([.48, .12, .24, .24000000000000002, .24]),
             np.array([.11, .12, .4800000000000001, .49]), np.array([])]
    for rates in grids:
        expected = view._evaluate(rates)["log_z"]
        actual = view._log_evidence(rates)
        assert np.array_equal(expected.view(np.uint64), actual.view(np.uint64))


@pytest.mark.parametrize("zeros", [1, 7, 64, 512])
def test_zero_stock_transitions_keep_full_normalizer_arithmetic(zeros):
    joint = JointPosterior(grid_size=32)
    view = joint.site(0)
    for tick in range(zeros):
        view.update_event(GrowthEvidence(0, tick, 0., .02))
    rates = np.geomspace(.12, .48, 37)
    expected = view._evaluate(rates)["log_z"]
    assert view._log_evidence(rates) is expected


@pytest.mark.parametrize("kind", ["learned", "atom", "fused"])
def test_informative_log_evidence_delegates_to_full_evaluation(kind):
    joint = JointPosterior(grid_size=32)
    view = joint.site(0)
    if kind == "learned":
        view.update_event(GrowthEvidence(0, 0, 20., 22.42))
    elif kind == "atom":
        view.update_event(GrowthEvidence(0, 0, 19.99, 20.))
        view.update_event(GrowthEvidence(0, 1, 20., 20.))
    else:
        view.fuse(40., 0.)
    rates = np.geomspace(.12, .48, 37)
    expected = view._evaluate(rates)["log_z"]
    assert view._log_evidence(rates) is expected


def test_bound_only_normalizer_preserves_full_payload_cache_and_detaches_output():
    joint = JointPosterior(grid_size=32)
    view = joint.site(0)
    rates = np.geomspace(.12, .48, 64)
    joint._rates = rates
    full = view._evaluate(rates)
    for query in (np.array([.15, .2]), np.array([.3, .4])):
        view._evaluate(query)
    cached = dict(view._eval_cache)
    output = view._log_evidence(rates)
    assert view._evaluate(rates) is full
    assert view._eval_cache.keys() == cached.keys()
    assert all(view._eval_cache[key] is entry for key, entry in cached.items())
    assert np.array_equal(output.view(np.uint64), full["log_z"].view(np.uint64))
    output[0] = 999.
    assert full["log_z"][0] != 999.
    assert len(full["log_z"]) == len(rates)


def test_normalizer_only_callers_preserve_mixed_synthetic_record_bit_for_bit():
    from types import MethodType
    reference = JointPosterior(grid_size=32, rate_bins=8)
    optimized = JointPosterior(grid_size=32, rate_bins=8)
    for joint in (reference, optimized):
        for site, bound in enumerate((20., 1., 30., 70.)):
            joint.observe_stock(site, bound)
            if joint is reference:
                def original_normalizer(self, rates):
                    return self._evaluate(rates)["log_z"]
                joint.site(site)._log_evidence = MethodType(original_normalizer, joint.site(site))
    records = []
    for joint in (reference, optimized):
        joint.update_event(GrowthEvidence(0, 0, 20., 22.42))
        joint.update_event(GrowthEvidence(1, 0, 1., 1.254))
        record = {"rate_cdfs": [joint.rate_cdf(rate) for rate in (.16, .24, .36)],
                  "rate_quantiles": [joint.rate_quantile(q) for q in (.05, .5, .95)],
                  "site_quantiles": [[joint.site(site).quantile(q) for q in (.05, .25, .5, .95)]
                                     for site in range(4)],
                  "predictive": [joint.site(site).predictive_cdf(1.25, 1.) for site in range(3)],
                  "rate_nodes": joint._rates.tolist(), "rate_log_weights": joint._log_weights.tolist(),
                  "memory": joint.memory()}
        records.append(record)
    assert records[0] == records[1]


def _uncached_complete_bin_cdf(self, rates, value, left):
    """The pre-cache CDF arithmetic, retained as an exact parity reference."""
    from swarm_societies.commons_v3 import posterior_joint_sites_v1 as module
    evaluation = self._evaluate(rates)
    selected = evaluation["right"] <= value
    total = np.full(len(rates), -np.inf)
    np.logaddexp.at(total, evaluation["rows"][selected],
                   module.logsumexp(evaluation["logs"][selected], axis=1))
    partial = (evaluation["left"] < value) & (evaluation["right"] > value)
    if partial.any():
        lo = evaluation["left"][partial]
        half = (value - lo) / 2
        points = lo[:, None] + half[:, None] * (1 + module._KNODES)
        rows = evaluation["rows"][partial]
        logs = self._logdensity(rates[rows, None], points, self._terms)
        logs = logs + np.log(half[:, None] * module._KWEIGHTS)
        np.logaddexp.at(total, rows, module.logsumexp(logs, axis=1))
    if self._atom is not None:
        capacity = self._atom["capacity"]
        if ((capacity < value and not module._same(capacity, value))
                or (not left and module._same(capacity, value))):
            total = np.logaddexp(total, evaluation["atom_logs"])
    return total


@pytest.mark.parametrize("biased", [False, True])
@pytest.mark.parametrize("kind", ["bound", "learned", "mixed_atom", "pure_atom", "fused"])
def test_cached_complete_bins_preserve_cdf_bits_including_partial_bins(biased, kind):
    joint = JointPosterior(biased=biased, grid_size=32, rate_bins=8)
    site = joint.site(0)
    site.observe_stock(19.973)
    if kind in ("learned", "fused"):
        site.update_event(GrowthEvidence(0, 0, 20., 22.42))
    elif kind in ("mixed_atom", "pure_atom"):
        site.update_event(GrowthEvidence(0, 0, 19.973, 20.))
        if kind == "pure_atom":
            site.update_event(GrowthEvidence(0, 1, 20., 20.))
    if kind == "fused":
        site.fuse(40., 0.)
    joint._refresh()
    grids = [joint._rates, np.array([.37, .24, .14, .24]), np.array([])]
    for rates in grids:
        evaluation = site._evaluate(rates)
        values = [8., 20., 22.42, 30., 40., 50., 100.]
        if len(evaluation["left"]):
            index = len(evaluation["left"]) // 2
            lo, hi = evaluation["left"][index], evaluation["right"][index]
            values.extend((hi, (lo + hi) / 2))
        for value in values:
            for left in (False, True):
                expected = _uncached_complete_bin_cdf(site, rates, value, left)
                actual = site._cdf_logmass(rates, value, left)
                assert np.array_equal(expected.view(np.uint64), actual.view(np.uint64))


def test_complete_bin_cdf_uses_cached_reductions_and_invalidates_on_local_update(monkeypatch):
    from swarm_societies.commons_v3 import posterior_joint_sites_v1 as module
    joint = JointPosterior(grid_size=32, rate_bins=8)
    site = joint.site(0)
    site.update_event(GrowthEvidence(0, 0, 20., 22.42))
    joint._refresh()
    rates = joint._rates
    evaluation = site._evaluate(rates)
    expected = _uncached_complete_bin_cdf(site, rates, 100., False)
    with monkeypatch.context() as patch:
        def unexpected_reduction(*args, **kwargs):
            raise AssertionError("complete bins must reuse their existing reduction")
        patch.setattr(module, "logsumexp", unexpected_reduction)
        actual = site._cdf_logmass(rates, 100., False)
    assert np.array_equal(expected.view(np.uint64), actual.view(np.uint64))
    site.observe_stock(23.)
    assert site._full_eval is None
    refreshed = site._evaluate(rates)
    assert refreshed is not evaluation
    assert refreshed["bin_logs"] is not evaluation["bin_logs"]


@pytest.mark.parametrize("biased", [False, True])
def test_complete_bin_cache_preserves_joint_updates_and_full_marginal_records(biased):
    from types import MethodType
    records = []
    for reference in (True, False):
        joint = JointPosterior(biased=biased, grid_size=32, rate_bins=8)
        for identity in range(4):
            site = joint.site(identity)
            site.observe_stock(1.)
            if reference:
                site._cdf_logmass = MethodType(_uncached_complete_bin_cdf, site)
        joint.update_event(GrowthEvidence(0, 0, 20., 22.42))
        joint.update_event(GrowthEvidence(1, 0, 19.973, 20.))
        joint.site(2).fuse(40., .7)
        frames = []
        for step in range(4):
            if step == 1:
                joint.update_event(GrowthEvidence(3, 0, 1., 1.254))
            elif step == 2:
                joint.update_event(GrowthEvidence(1, 1, 20., 20.))
            elif step == 3:
                joint.observe_stock(0, 23.)
            frames.append({
                "rate_cdf": joint.rate_cdf(.24),
                "sites": [{"quantiles": [site.quantile(q) for q in (.05, .25, .5, .95)],
                           "cdf": [site.cdf(20., left=left) for left in (False, True)],
                           "interval": site.interval(), "predictive": site.predictive_cdf(1.25, 1.)}
                          for site in joint._sites.values()],
                "rate_nodes": joint._rates.tolist(), "rate_weights": joint._log_weights.tolist(),
                "memory": joint.memory()})
        records.append(frames)
    assert records[0] == records[1]


def test_biased_prior_is_approved_mixture_with_nonzero_low_capacity_support():
    joint = JointPosterior(biased=True, grid_size=64, rate_bins=16)
    site = joint.site(0)
    expected = .01 * math.log(40 / 8) / math.log(100 / 8)
    assert site.cdf(40.) == pytest.approx(expected, abs=1e-10)
    site.observe_stock(19.99)
    site.update_event(GrowthEvidence(0, 0, 19.99, 20.))
    site.update_event(GrowthEvidence(0, 1, 20., 20.))
    assert site.quantile(.5) == 20.


def test_predictive_cdf_keeps_capacity_saturation_jump():
    joint = JointPosterior(grid_size=32, rate_bins=8)
    site = joint.site(0)
    site.observe_stock(19.99)
    site.update_event(GrowthEvidence(0, 0, 19.99, 20.))
    site.update_event(GrowthEvidence(0, 1, 20., 20.))
    assert site.predictive_cdf(20., 20., left=True) == 0.
    assert site.predictive_cdf(20., 20.) == pytest.approx(1.)
    with pytest.raises(ValueError, match="bounded"):
        site.predictive_cdf(30., 30.)


@pytest.mark.parametrize("count", [1, 20, 200])
def test_repeated_zero_iqr_fusion_retains_finite_accurate_width(count):
    from scipy.special import ndtr
    joint = JointPosterior(grid_size=64, rate_bins=8)
    site = joint.site(0)
    for _ in range(count):
        site.fuse(40., 0.)
    sigma0 = math.log(100 / 8) / 400
    sigma = sigma0 / math.sqrt(count)
    mu = math.log(40.) - sigma0 * sigma0
    for offset in (-1., 0., 1.):
        value = math.exp(mu + offset * sigma)
        assert site.cdf(value) == pytest.approx(float(ndtr(offset)), abs=1e-8)
    assert site.interval()[1] > site.interval()[0]
    assert site.atoms == {}
    assert joint.rate_cdf(.24) == pytest.approx(.5, abs=1e-12)


def test_adaptive_support_survives_long_history_and_resolution_doubling():
    rng = random.Random(137)
    capacities, rate = (12., 37., 89.), .197
    stocks = [.6 * k for k in capacities]
    ordinary = JointPosterior(grid_size=64, rate_bins=16)
    finer = JointPosterior(grid_size=128, rate_bins=32, rate_order=16)
    for posterior in (ordinary, finer):
        for site, stock in enumerate(stocks):
            posterior.observe_stock(site, stock)
    for tick in range(128):
        for site, capacity in enumerate(capacities):
            z = max(0., stocks[site] - (.2 if tick % 3 == 0 else .02) * capacity)
            y = min(capacity, z + (.9 + .2 * rng.random()) * (rate * z * (1 - z / capacity) + .02))
            event = GrowthEvidence(site, tick, z, y)
            for posterior in (ordinary, finer):
                posterior.update_event(event)
                posterior.observe_stock(site, y)
            stocks[site] = y
    assert ordinary.rate_cdf(rate) == pytest.approx(finer.rate_cdf(rate), abs=.002)
    assert len(ordinary._rates) > 0
    for site, capacity in enumerate(capacities):
        assert ordinary.site(site).cdf(capacity) == pytest.approx(finer.site(site).cdf(capacity), abs=.002)
        assert ordinary.site(site).quantile(.5) == pytest.approx(finer.site(site).quantile(.5), rel=.001)


@pytest.mark.parametrize("kwargs", [{"biased": 1}, {"grid_size": 4}, {"rate_bins": 0}, {"rate_order": 3}])
def test_reject_invalid_resolution_and_prior_parameters(kwargs):
    with pytest.raises(ValueError):
        JointPosterior(**kwargs)
