"""Ticket C's fixed synthetic site-posterior calibration, before any L0 arena.

Truth and weather exist only in this generator/evaluator. The posterior sees
ordinary clean transitions and stock bounds, never the clipping classification.
The 1,024 independent sequences, not their 65,536 transitions, are replication
units. This is calibration under a declared prior, not an ecological arm run.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import json
import math
from pathlib import Path
import random
import statistics as st

from scipy.integrate import quad

from .development_navigation_v1 import canonical, digest, _save_json
from .evidence_sites_v1 import CleanTransition
from .posterior_sites_v1 import SitePosterior


VERSION = "commons-v3-site-calibration-v1"
SEEDS = tuple(range(91001, 92025))
HORIZON = 64
CHECKPOINTS = (1, 16, 32, 64)
ALPHA = .01
FAMILY_SIZE = 2 * len(CHECKPOINTS)
REFERENCE_TOLERANCE = .002


def criteria():
    return {"version": VERSION, "seeds": list(SEEDS), "independent_sequences": len(SEEDS),
            "horizon": HORIZON, "checkpoints": list(CHECKPOINTS),
            "prior": {"distribution": "log_uniform", "low": 8., "high": 100.},
            "initial_stock": {"value": 1., "independent_of_capacity": True,
                              "learner_information": "stock lower bound only; not the arena initial-stock likelihood"},
            "harvest": 0., "renewal_rate": .24, "recovery": .02,
            "weather": {"distribution": "uniform", "low": .9, "high": 1.1},
            "grid_size": 400, "alpha": ALPHA, "DKW_family_size": FAMILY_SIZE,
            "DKW_epsilon": math.sqrt(math.log(2 * FAMILY_SIZE / ALPHA) / (2 * len(SEEDS))),
            "reference_CDF_absolute_tolerance": REFERENCE_TOLERANCE,
            "reference_evidence_use_minimum_CDF_change": .05,
            "G2_requires": ["all eight rank/PIT empirical CDF distances at most the DKW bound",
                            "finite nonempty updates and at least 500 transitions",
                            "both clipped and unclipped generated transitions",
                            "independent numerical reference and evidence-use checks"],
            "coverage_role": "inclusive and randomized 90% coverage are descriptive, not additional tests",
            "no_scientific_arms": True}


def synthetic_sequence(seed, horizon=HORIZON):
    """An exogenous initial stock avoids selecting a transition with true K."""
    if type(seed) is not int or seed < 0 or type(horizon) is not int or not 1 <= horizon <= HORIZON:
        raise ValueError("invalid synthetic sequence seed or horizon")
    truth_rng = random.Random(f"{VERSION}/capacity/{seed}")
    weather_rng = random.Random(f"{VERSION}/weather/{seed}")
    capacity = math.exp(math.log(8.) + truth_rng.random() * math.log(100. / 8.))
    stock, rows = 1., []
    for tick in range(horizon):
        weather = .9 + .2 * weather_rng.random()
        potential = .24 * stock * (1 - stock / capacity) + .02
        unbounded = stock + weather * potential
        next_stock = min(capacity, unbounded)
        # Compact positional records: z, next stock, weather, clipped.
        rows.append([stock, next_stock, weather, unbounded >= capacity])
        stock = next_stock
    return {"seed": seed, "capacity": capacity, "initial_stock": 1., "transitions": rows}


def _uniform(seed, kind, tick):
    return random.Random(f"{VERSION}/rank/{kind}/{seed}/{tick}").random()


def _cdf_pair(posterior, value, *, z=None):
    if z is None:
        pair = posterior.cdf(value, left=True), posterior.cdf(value)
    else:
        pair = posterior.predictive_cdf(value, z, left=True), posterior.predictive_cdf(value, z)
    if any(not math.isfinite(v) or not -1e-12 <= v <= 1 + 1e-12 for v in pair) or pair[0] > pair[1] + 1e-12:
        raise ArithmeticError("invalid posterior or predictive CDF")
    return tuple(min(1., max(0., v)) for v in pair)


def _posterior_summary(posterior, truth):
    median = posterior.quantile(.5)
    interval = list(posterior.interval(level=.9))
    if (not all(math.isfinite(value) and 8. <= value <= 100. for value in [median, *interval])
            or len(interval) != 2 or interval[0] > interval[1]):
        raise ArithmeticError("invalid posterior summary")
    return {"median": median, "interval90": interval,
            "inclusive90_covered": interval[0] <= truth <= interval[1],
            "absolute_log_median_error": abs(math.log(median / truth)),
            "log_interval_width": math.log(interval[1] / interval[0])}


def run_case(seed):
    case = synthetic_sequence(seed)
    posterior, bound_only = SitePosterior(site=0, grid_size=400), SitePosterior(site=0, grid_size=400)
    posterior.observe_stock(case["initial_stock"])
    bound_only.observe_stock(case["initial_stock"])
    checkpoints = []
    for tick, (z, next_stock, _weather, _clipped) in enumerate(case["transitions"]):
        number = tick + 1
        predictive = _cdf_pair(posterior, next_stock, z=z) if number in CHECKPOINTS else None
        # No evaluator-only truth, weather, or clipping flag enters this API.
        posterior.update(CleanTransition(site=0, tick=tick, z=z, stock_next=next_stock,
                                         stock_before=z, own_harvest=0.))
        posterior.observe_stock(next_stock)
        bound_only.observe_stock(next_stock)
        if number in CHECKPOINTS:
            left, right = _cdf_pair(posterior, case["capacity"])
            rank = left + _uniform(seed, "posterior", number) * (right - left)
            pit = predictive[0] + _uniform(seed, "predictive", number) * (predictive[1] - predictive[0])
            checkpoints.append({"tick": number, "posterior_CDF": [left, right], "posterior_rank": rank,
                                "predictive_CDF": list(predictive), "predictive_rank": pit,
                                "randomized90_covered": .05 <= rank <= .95,
                                "posterior": _posterior_summary(posterior, case["capacity"]),
                                "bound_only": _posterior_summary(bound_only, case["capacity"])})
    return {**case, "checkpoints": checkpoints,
            "posterior_memory_sha256": digest(posterior.memory()),
            "bound_only_memory_sha256": digest(bound_only.memory())}


def empirical_uniform_distance(values):
    values = sorted(values)
    if not values or any(not math.isfinite(v) or not 0. <= v <= 1. for v in values):
        raise ValueError("ranks must be a nonempty finite sample in [0,1]")
    n = len(values)
    return max(max((i + 1) / n - v, v - i / n) for i, v in enumerate(values))


def reference_cdf(z, y, x, *, left=False):
    """Independent single-transition integral under the continuous log prior.

    This uses scalar quadrature on analytically located uniform-likelihood
    boundaries, not the production posterior's bins, update code or densities.
    A clipping contribution is a parameter atom at K=y; its weight contains
    the prior density at y and the clipping probability, before normalization.
    """
    if not 0. <= z <= y <= 100.:
        raise ValueError("reference requires feasible ordered stocks")
    a, b, growth = .24 * z + .02, .24 * z * z, y - z
    lo, hi = max(8., z, y), 100.
    if b:
        if growth / 1.1 >= a:
            lo = math.inf
        else:
            lo = max(lo, b / (a - growth / 1.1))
        if growth / .9 < a:
            hi = min(hi, b / (a - growth / .9))
    elif not .9 * a <= growth <= 1.1 * a:
        lo = math.inf

    def integrate(upper):
        upper = min(hi, upper)
        return 0. if upper <= lo else quad(lambda k: 1. / (k * .2 * (a - b / k)),
                                           lo, upper, epsabs=1e-12, epsrel=1e-12)[0]

    atom = 0.
    if max(8., z) <= y <= 100.:
        potential = a - b / y
        atom = min(1., max(0., (1.1 * potential - growth) / (.2 * potential))) / y
    total = integrate(hi) + atom
    if not math.isfinite(total) or total <= 0.:
        raise ValueError("reference observation has zero marginal density")
    return (integrate(x) + (atom if x > y or x == y and not left else 0.)) / total


def reference_checks():
    rows = []
    max_error, max_change = 0., 0.
    for z, y in ((1., 1.25), (20., 22.42), (20., 20.027)):
        posterior = SitePosterior(site=0, grid_size=400)
        posterior.observe_stock(z)
        posterior.update(CleanTransition(site=0, tick=0, z=z, stock_next=y,
                                         stock_before=z, own_harvest=0.))
        posterior.observe_stock(y)
        points = sorted({8., z, y, y * 1.0001, y * 1.01, 20., 40., 80., 100.})
        errors, changes = [], []
        for value in points:
            for left in (False, True):
                actual = posterior.cdf(value, left=left)
                reference = reference_cdf(z, y, value, left=left)
                errors.append(abs(actual - reference))
                bound = max(8., y)
                no_update = 0. if value <= bound else min(1., math.log(value / bound) / math.log(100. / bound))
                changes.append(abs(actual - no_update))
        max_error, max_change = max(max_error, *errors), max(max_change, *changes)
        rows.append({"z": z, "stock_next": y, "maximum_absolute_CDF_error": max(errors),
                     "maximum_CDF_change_from_bound_only": max(changes)})
    # Repeating a saturated observation leaves only its exact capacity atom.
    posterior = SitePosterior(site=0, grid_size=400)
    posterior.observe_stock(20.)
    for tick, (z, y) in enumerate(((20., 20.027), (20.027, 20.027))):
        posterior.update(CleanTransition(site=0, tick=tick, z=z, stock_next=y,
                                         stock_before=z, own_harvest=0.))
        posterior.observe_stock(y)
    atom_collapse = (posterior.cdf(20.027, left=True) <= 1e-12
                     and posterior.cdf(20.027) >= 1. - 1e-12
                     and posterior.interval(level=.9) == (20.027, 20.027))
    return {"single_transition_cases": rows, "maximum_absolute_CDF_error": max_error,
            "reference_tolerance": REFERENCE_TOLERANCE,
            "maximum_CDF_change_from_bound_only": max_change,
            "repeated_saturation_exact_atom": atom_collapse,
            "passed": max_error <= REFERENCE_TOLERANCE and max_change > .05 and atom_collapse}


def summarize(cases, checks):
    if [row["seed"] for row in cases] != list(SEEDS):
        raise ValueError("calibration cases differ from the fixed sequence panel")
    epsilon = criteria()["DKW_epsilon"]
    checkpoints = []
    for tick in CHECKPOINTS:
        rows = [next(row for row in case["checkpoints"] if row["tick"] == tick) for case in cases]
        posterior_d = empirical_uniform_distance([row["posterior_rank"] for row in rows])
        predictive_d = empirical_uniform_distance([row["predictive_rank"] for row in rows])
        summaries = {}
        for name in ("posterior", "bound_only"):
            summaries[name] = {field: st.mean(row[name][field] for row in rows)
                               for field in ("inclusive90_covered", "absolute_log_median_error", "log_interval_width")}
        checkpoints.append({"tick": tick, "posterior_rank_D": posterior_d, "predictive_PIT_D": predictive_d,
                            "posterior_rank_mean": st.mean(row["posterior_rank"] for row in rows),
                            "predictive_PIT_mean": st.mean(row["predictive_rank"] for row in rows),
                            "randomized90_coverage": st.mean(row["randomized90_covered"] for row in rows),
                            **summaries, "passed": posterior_d <= epsilon and predictive_d <= epsilon})
    transitions = sum(len(case["transitions"]) for case in cases)
    clipped = sum(row[3] for case in cases for row in case["transitions"])
    prior_ranks = [math.log(case["capacity"] / 8.) / math.log(100. / 8.) for case in cases]
    return {"version": VERSION, "independent_sequences": len(cases), "transitions": transitions,
            "clipped_transitions": clipped, "unclipped_transitions": transitions - clipped,
            "criteria": criteria(), "checkpoints": checkpoints, "independent_reference_checks": checks,
            "prior_no_update_control": {"rank_D": empirical_uniform_distance(prior_ranks),
                "mean_absolute_log_median_error": st.mean(abs(math.log(math.sqrt(800.) / case["capacity"])) for case in cases),
                "interpretation": "prior ranks can be calibrated without using evidence; reference and evidence-use checks are also required"},
            "G2": {"passed": bool(transitions >= 500 and 0 < clipped < transitions
                                    and checks["passed"] and all(row["passed"] for row in checkpoints))},
            "scientific_arena_episodes": 0, "experimental_model_calls": 0}


def _cases(workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("workers must be between one and eight")
    if workers == 1:
        return [run_case(seed) for seed in SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run_case, SEEDS))


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
    return {"version": VERSION, "exact_sequences": len(cases), "exact_transitions": len(cases) * HORIZON,
            "summary_sha256": digest(summary), "G2": summary["G2"]}
