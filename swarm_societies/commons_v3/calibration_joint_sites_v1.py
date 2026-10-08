"""A2 joint-rate G2 calibration on independent, prior-drawn multisite sequences.

Each sequence has one rate shared by three independently drawn capacities.
Replication is across 512 sequences, never across correlated sites or ticks.
Truth, weather and clipping labels remain exclusively in this generator and
evaluator. The learner receives ordinary clean events and stock bounds only.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import json
import math
from pathlib import Path
import random
import statistics as st
import sys

from scipy.integrate import quad

from .calibration_sites_v1 import empirical_uniform_distance
from .development_navigation_v1 import canonical, digest, _save_json
from .messages_sites_v1 import GrowthEvidence
from .posterior_joint_sites_v1 import JointPosterior, VERSION as POSTERIOR_VERSION


VERSION = "commons-v3-joint-site-calibration-v1"
SEEDS = tuple(range(94001, 94513))
SITES = 3
HORIZON = 16
CHECKPOINTS = (1, 8, 16)
ALPHA = .01
FAMILY_SIZE = (1 + 2 * SITES) * len(CHECKPOINTS)
REFERENCE_TOLERANCE = .002
RESOLUTION = {"grid_size": 400, "rate_bins": 32, "rate_order": 8}


def criteria():
    return {"version": VERSION, "seeds": list(SEEDS), "independent_sequences": len(SEEDS),
            "sites_per_sequence": SITES, "horizon_per_site": HORIZON,
            "checkpoints": list(CHECKPOINTS),
            "rate_prior": {"distribution": "log_uniform", "low": .12, "high": .48,
                           "shared_across_sites": True},
            "capacity_prior": {"distribution": "log_uniform", "low": 8., "high": 100.,
                               "independent_by_site": True},
            "initial_stock": {"value": 7.5, "independent_of_capacity_and_rate": True,
                              "learner_information": "stock lower bound only"},
            "harvest": 0., "recovery": .02,
            "weather": {"distribution": "uniform", "low": .9, "high": 1.1},
            "posterior_version": POSTERIOR_VERSION, "resolution": dict(RESOLUTION), "alpha": ALPHA,
            "DKW_family_size": FAMILY_SIZE,
            "DKW_epsilon": math.sqrt(math.log(2 * FAMILY_SIZE / ALPHA) / (2 * len(SEEDS))),
            "reference_CDF_absolute_tolerance": REFERENCE_TOLERANCE,
            "reference_evidence_use_minimum_CDF_change": .05,
            "G2_requires": ["all rate, capacity and predictive rank CDF distances at most the DKW bound",
                            "finite nonempty updates and at least 500 independent sequences and transitions",
                            "both clipped and unclipped generated transitions",
                            "independent numerical reference and evidence-use checks"],
            "coverage_role": "inclusive and randomized 90% coverage descriptive, not additional tests",
            "replication": "independent sequences; site-specific rank samples are tested separately",
            "no_scientific_arms": True}


def synthetic_sequence(seed, horizon=HORIZON):
    if type(seed) is not int or seed < 0 or type(horizon) is not int or not 1 <= horizon <= HORIZON:
        raise ValueError("invalid synthetic sequence seed or horizon")
    rate_rng = random.Random(f"{VERSION}/rate/{seed}")
    capacity_rng = random.Random(f"{VERSION}/capacity/{seed}")
    weather_rng = random.Random(f"{VERSION}/weather/{seed}")
    rate = math.exp(math.log(.12) + rate_rng.random() * math.log(4.))
    capacities = [math.exp(math.log(8.) + capacity_rng.random() * math.log(100. / 8.))
                  for _ in range(SITES)]
    stocks, frames = [7.5] * SITES, []
    for tick in range(horizon):
        rows = []
        for site, capacity in enumerate(capacities):
            z = stocks[site]
            weather = .9 + .2 * weather_rng.random()
            unbounded = z + weather * (rate * z * (1. - z / capacity) + .02)
            next_stock = min(capacity, unbounded)
            rows.append([site, z, next_stock, weather, unbounded >= capacity])
            stocks[site] = next_stock
        frames.append(rows)
    return {"seed": seed, "rate": rate, "capacities": capacities,
            "initial_stock": 7.5, "transitions": frames}


def _uniform(seed, kind, tick, site=None):
    return random.Random(f"{VERSION}/rank/{kind}/{seed}/{tick}/{site}").random()


def _pair(left, right):
    if any(not math.isfinite(v) or not -1e-12 <= v <= 1. + 1e-12 for v in (left, right)) or left > right + 1e-12:
        raise ArithmeticError("invalid posterior or predictive CDF")
    return min(1., max(0., left)), min(1., max(0., right))


def _summary(median, interval, truth, low, high):
    interval = list(interval)
    if (len(interval) != 2 or not all(math.isfinite(v) and low <= v <= high for v in (median, *interval))
            or interval[0] > interval[1]):
        raise ArithmeticError("invalid posterior summary")
    return {"median": median, "interval90": interval,
            "inclusive90_covered": interval[0] <= truth <= interval[1],
            "absolute_log_median_error": abs(math.log(median / truth)),
            "log_interval_width": math.log(interval[1] / interval[0])}


def run_case(seed):
    case = synthetic_sequence(seed)
    posterior = JointPosterior(**RESOLUTION)
    for site in range(SITES):
        posterior.observe_stock(site, case["initial_stock"])
    checkpoints = []
    for tick, frame in enumerate(case["transitions"]):
        number = tick + 1
        predictive = {}
        if number in CHECKPOINTS:
            # All simultaneous forecasts precede every site's current update.
            for site, z, y, _weather, _clipped in frame:
                view = posterior.site(site)
                predictive[site] = _pair(view.predictive_cdf(y, z, left=True),
                                         view.predictive_cdf(y, z))
        for site, z, y, _weather, _clipped in frame:
            posterior.update_event(GrowthEvidence(site, tick, z, y))
            posterior.observe_stock(site, y)
        if number in CHECKPOINTS:
            rate_cdf = posterior.rate_cdf(case["rate"])
            _pair(rate_cdf, rate_cdf)
            sites = []
            for site, truth in enumerate(case["capacities"]):
                view = posterior.site(site)
                left, right = _pair(view.cdf(truth, left=True), view.cdf(truth))
                rank = left + _uniform(seed, "capacity", number, site) * (right - left)
                lo, hi = predictive[site]
                pit = lo + _uniform(seed, "predictive", number, site) * (hi - lo)
                sites.append({"site": site, "posterior_CDF": [left, right],
                    "posterior_rank": rank, "predictive_CDF": [lo, hi], "predictive_rank": pit,
                    "randomized90_covered": .05 <= rank <= .95,
                    "posterior": _summary(view.quantile(.5), view.interval(level=.9), truth, 8., 100.)})
            checkpoints.append({"tick": number, "rate_rank": rate_cdf,
                "rate_randomized90_covered": .05 <= rate_cdf <= .95,
                "rate": _summary(posterior.rate_quantile(.5), posterior.rate_interval(level=.9),
                                 case["rate"], .12, .48), "sites": sites})
    return {**case, "checkpoints": checkpoints, "posterior_memory_sha256": digest(posterior.memory())}


def _conditional_mass(z, y, rate, upper=100., *, include_atom=True):
    """Independent analytic K integral at fixed r, omitting prior constants."""
    growth = y - z
    a, b = rate * z + .02, rate * z * z
    lo, hi = max(8., z, y), min(100., upper)
    if b:
        if growth / 1.1 >= a:
            lo = math.inf
        else:
            lo = max(lo, b / (a - growth / 1.1))
        if growth / .9 < a:
            hi = min(hi, b / (a - growth / .9))
    elif not .9 * a <= growth <= 1.1 * a:
        lo = math.inf
    continuous = (math.log1p(a * (hi - lo) / (a * lo - b)) / (.2 * a)
                  if hi > lo else 0.)
    atom = 0.
    if include_atom and max(8., z) <= y <= min(100., upper):
        potential = a - b / y
        atom = min(1., max(0., (1.1 * potential - growth) / (.2 * potential))) / y
    return continuous + atom


def reference_cdf(z, y, value, *, variable="capacity", left=False):
    """Scalar log-r quadrature and analytic K integrals, independent of learner.

    For K=y the clipping component is a parameter atom with weight equal to
    prior density at y times the clipping probability. Its rate dependence is
    integrated rather than assigning the atom a single rate.
    """
    if not 0. <= z <= y <= 100. or variable not in ("capacity", "rate"):
        raise ValueError("invalid independent reference request")
    cuts = [math.log(.12), math.log(.48)]
    capacities = {max(8., z, y), 100., value} if variable == "capacity" else {max(8., z, y), 100.}
    for capacity in capacities:
        if capacity < max(8., z, y) or capacity > 100.:
            continue
        coefficient = z * (1. - z / capacity)
        if coefficient:
            for weather in (.9, 1.1):
                rate = ((y - z) / weather - .02) / coefficient
                if .12 < rate < .48:
                    cuts.append(math.log(rate))
    cuts = sorted(set(cuts))

    def integrate(rate_upper=.48, capacity_upper=100., include_atom=True):
        high = min(math.log(.48), math.log(rate_upper)) if rate_upper > 0. else -math.inf
        if high <= cuts[0]:
            return 0.
        bounds = sorted({cuts[0], high, *(point for point in cuts if cuts[0] < point < high)})
        return math.fsum(quad(lambda log_r: _conditional_mass(z, y, math.exp(log_r), capacity_upper,
                                                              include_atom=include_atom),
                              lo, hi, epsabs=1e-11, epsrel=1e-11)[0]
                         for lo, hi in zip(bounds, bounds[1:]))

    total = integrate()
    if not math.isfinite(total) or total <= 0.:
        raise ValueError("reference observation has zero marginal density")
    numerator = (integrate(rate_upper=value) if variable == "rate" else
                 integrate(capacity_upper=value, include_atom=not (left and value == y)))
    return min(1., max(0., numerator / total))


def reference_checks():
    rows, max_error, max_change = [], 0., 0.
    for z, y in ((1., 1.25), (20., 22.42), (20., 20.027)):
        posterior = JointPosterior(**RESOLUTION)
        posterior.observe_stock(0, z)
        posterior.update_event(GrowthEvidence(0, 0, z, y))
        posterior.observe_stock(0, y)
        view = posterior.site(0)
        errors, changes = [], []
        for value in sorted({8., z, y, y * 1.0001, y * 1.01, 30., 60., 100.}):
            for left in (False, True):
                actual = view.cdf(value, left=left)
                errors.append(abs(actual - reference_cdf(z, y, value, left=left)))
                bound = max(8., y)
                no_update = 0. if value <= bound else min(1., math.log(value / bound) / math.log(100. / bound))
                changes.append(abs(actual - no_update))
        for value in (.12, .16, .24, .36, .48):
            actual = posterior.rate_cdf(value)
            errors.append(abs(actual - reference_cdf(z, y, value, variable="rate")))
            changes.append(abs(actual - math.log(value / .12) / math.log(4.)))
        max_error, max_change = max(max_error, *errors), max(max_change, *changes)
        rows.append({"z": z, "stock_next": y, "maximum_absolute_CDF_error": max(errors),
                     "maximum_CDF_change_from_bound_only": max(changes)})
    posterior = JointPosterior(**RESOLUTION)
    posterior.observe_stock(0, 20.)
    for tick, (z, y) in enumerate(((20., 20.027), (20.027, 20.027))):
        posterior.update_event(GrowthEvidence(0, tick, z, y))
        posterior.observe_stock(0, y)
    view = posterior.site(0)
    atom_collapse = (view.cdf(20.027, left=True) <= 1e-12 and view.cdf(20.027) >= 1. - 1e-12
                     and view.interval(level=.9) == (20.027, 20.027))
    return {"single_transition_cases": rows, "maximum_absolute_CDF_error": max_error,
            "reference_tolerance": REFERENCE_TOLERANCE,
            "maximum_CDF_change_from_bound_only": max_change,
            "repeated_saturation_exact_atom": atom_collapse,
            "passed": max_error <= REFERENCE_TOLERANCE and max_change > .05 and atom_collapse}


def summarize(cases, checks):
    if [case["seed"] for case in cases] != list(SEEDS):
        raise ValueError("calibration cases differ from the fixed sequence panel")
    epsilon = criteria()["DKW_epsilon"]
    checkpoints = []
    for tick in CHECKPOINTS:
        selected = [next(row for row in case["checkpoints"] if row["tick"] == tick) for case in cases]
        rate_d = empirical_uniform_distance([row["rate_rank"] for row in selected])
        sites = []
        for site in range(SITES):
            rows = [next(value for value in row["sites"] if value["site"] == site) for row in selected]
            posterior_d = empirical_uniform_distance([row["posterior_rank"] for row in rows])
            predictive_d = empirical_uniform_distance([row["predictive_rank"] for row in rows])
            sites.append({"site": site, "posterior_rank_D": posterior_d, "predictive_PIT_D": predictive_d,
                "posterior_rank_mean": st.mean(row["posterior_rank"] for row in rows),
                "predictive_PIT_mean": st.mean(row["predictive_rank"] for row in rows),
                "randomized90_coverage": st.mean(row["randomized90_covered"] for row in rows),
                "posterior": {key: st.mean(row["posterior"][key] for row in rows)
                    for key in ("inclusive90_covered", "absolute_log_median_error", "log_interval_width")},
                "passed": posterior_d <= epsilon and predictive_d <= epsilon})
        checkpoints.append({"tick": tick, "rate_rank_D": rate_d,
            "rate_rank_mean": st.mean(row["rate_rank"] for row in selected),
            "rate_randomized90_coverage": st.mean(row["rate_randomized90_covered"] for row in selected),
            "rate": {key: st.mean(row["rate"][key] for row in selected)
                     for key in ("inclusive90_covered", "absolute_log_median_error", "log_interval_width")},
            "sites": sites, "passed": rate_d <= epsilon and all(row["passed"] for row in sites)})
    transitions = sum(len(frame) for case in cases for frame in case["transitions"])
    clipped = sum(row[4] for case in cases for frame in case["transitions"] for row in frame)
    return {"version": VERSION, "independent_sequences": len(cases), "transitions": transitions,
            "clipped_transitions": clipped, "unclipped_transitions": transitions - clipped,
            "criteria": criteria(), "checkpoints": checkpoints, "independent_reference_checks": checks,
            "G2": {"passed": bool(len(cases) >= 500 and transitions >= 500 and 0 < clipped < transitions
                                    and checks["passed"] and all(row["passed"] for row in checkpoints))},
            "scientific_arena_episodes": 0, "experimental_model_calls": 0}


def _cases(workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("workers must be between one and eight")
    def collect(results):
        cases = []
        for index, case in enumerate(results, 1):
            cases.append(case)
            if index % 16 == 0 or index == len(SEEDS):
                print(f"joint calibration progress {index}/{len(SEEDS)} sequences",
                      file=sys.stderr, flush=True)
        return cases
    if workers == 1:
        return collect(map(run_case, SEEDS))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return collect(pool.map(run_case, SEEDS))


def run(output, workers=2):
    output = Path(output)
    if (output / "summary.json").exists():
        raise ValueError("completed calibration; use verify")
    output.mkdir(parents=True, exist_ok=True)
    checks = reference_checks()
    if not checks["passed"]:
        raise ArithmeticError("independent posterior reference checks fail before calibration")
    cases = _cases(workers)
    summary = summarize(cases, checks)
    _save_json(output / "cases.json", {"version": VERSION, "cases": cases})
    _save_json(output / "summary.json", summary)
    return summary


def verify(output, workers=2):
    output = Path(output)
    saved = json.loads((output / "cases.json").read_text())
    cases = _cases(workers)
    if canonical(saved) != canonical({"version": VERSION, "cases": cases}):
        raise ValueError("exact synthetic sequence or posterior replay differs")
    summary = summarize(cases, reference_checks())
    if canonical(summary) != canonical(json.loads((output / "summary.json").read_text())):
        raise ValueError("calibration summary differs on replay")
    return {"version": VERSION, "exact_sequences": len(cases), "exact_transitions": len(cases) * HORIZON * SITES,
            "summary_sha256": digest(summary), "G2": summary["G2"]}


def load_passed(output):
    """Require the complete matching saved G2 before a scientific arm runs.

    This rebuilds the aggregate from saved calibration records. The separate
    verify command performs the full numerical replay; loading never reruns
    the calibration or starts a new one implicitly.
    """
    output = Path(output)
    saved_cases = json.loads((output / "cases.json").read_text())
    saved = json.loads((output / "summary.json").read_text())
    if saved_cases["version"] != VERSION or saved["version"] != VERSION:
        raise ValueError("joint calibration version differs")
    if canonical(saved["criteria"]) != canonical(criteria()):
        raise ValueError("joint calibration criteria differ")
    reconstructed = summarize(saved_cases["cases"], saved["independent_reference_checks"])
    if canonical(reconstructed) != canonical(saved):
        raise ValueError("joint calibration aggregate differs from saved cases")
    if not reconstructed["G2"]["passed"]:
        raise ValueError("joint calibration G2 has not passed")
    return {"version": VERSION, "summary_sha256": digest(saved),
            "criteria_sha256": digest(saved["criteria"]),
            "posterior_version": saved["criteria"]["posterior_version"],
            "resolution": saved["criteria"]["resolution"],
            "independent_sequences": saved["independent_sequences"],
            "transitions": saved["transitions"], "G2": saved["G2"]}
