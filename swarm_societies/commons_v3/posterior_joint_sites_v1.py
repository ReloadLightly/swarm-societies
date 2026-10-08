"""A2: one unknown growth rate coupled to all private site capacities.

The joint density factorizes as p(r) product_j L_j(r, K_j) p(K_j).
Conditional K support is exact: in coordinates (r, r/K), each uniform-weather
transition is a linear band. Polygon clipping therefore retains arbitrarily
narrow feasible rate intervals instead of rejecting a fixed parameter grid.
Capacity saturation contributes explicit K atoms, with rate-dependent weights.

Smooth densities are integrated numerically with Gauss-Legendre quadrature:
400 log capacity bins and rate bins split additionally at every feasible
polygon vertex and atom-support endpoint. The numerical settings do not change
the declared priors. No physical true-rate value is used by this module.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from functools import wraps
import math

import numpy as np
from scipy.special import logsumexp, ndtri
from scipy.optimize import brentq

from .messages_sites_v1 import GrowthEvidence


VERSION = "commons-v3-joint-rate-capacity-posterior-v1"
LOW, HIGH, RATE_LOW, RATE_HIGH = 8., 100., .12, .48
RECOVERY, WLOW, WHIGH = .02, .9, 1.1
WIDTH = WHIGH - WLOW
_KNODES, _KWEIGHTS = np.polynomial.legendre.leggauss(8)


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _same(a, b):
    return abs(a - b) <= 8 * math.ulp(max(1., abs(a), abs(b)))


def _clip(polygon, a, b, c):
    """Intersect a convex polygon with a*r+b*(r/K)+c >= 0."""
    if not polygon:
        return []
    output = []
    old = polygon[-1]
    old_value = a * old[0] + b * old[1] + c
    for point in polygon:
        value = a * point[0] + b * point[1] + c
        if (value >= 0) != (old_value >= 0):
            fraction = old_value / (old_value - value)
            crossing = (old[0] + fraction * (point[0] - old[0]),
                        old[1] + fraction * (point[1] - old[1]))
            output.append(crossing)
        if value >= 0:
            output.append(point)
        old, old_value = point, value
    return output


def _interval_clip(interval, coefficient, constant):
    """Intersect a rate interval with coefficient*r+constant >= 0."""
    if interval is None:
        return None
    lo, hi = interval
    if coefficient > 0:
        lo = max(lo, -constant / coefficient)
    elif coefficient < 0:
        hi = min(hi, -constant / coefficient)
    elif constant < 0:
        return None
    return (lo, hi) if hi > lo else None


def _intersect_unions(left, right):
    intersections = sorted((max(a, c), min(b, d)) for a, b in left for c, d in right
                           if min(b, d) > max(a, c))
    merged = []
    for lo, hi in intersections:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return merged


def _transaction(method):
    """Reject impossible evidence without damaging an existing joint belief."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        names = ("_polygon", "_constraints", "_bound", "_terms", "_atom", "_seen",
                 "_operations", "_local_revision", "_fusion_count", "_fusion_precision", "_fusion_mu")
        backup = {name: (getattr(self, name).copy() if isinstance(getattr(self, name), (list, dict))
                         else getattr(self, name)) for name in names}
        owner_revision, length = self.owner.revision, len(self.owner._operations)
        try:
            return method(self, *args, **kwargs)
        except Exception:
            self.__dict__.update(backup)
            self._eval_cache.clear()
            self._full_eval_key = self._full_eval = None
            self._query_cache.clear()
            self._weights_revision = -1
            self.owner.revision = owner_revision
            del self.owner._operations[length:]
            self.owner._refreshed = -1
            raise
    return wrapped


class JointSitePosterior:
    """A marginal-capacity view of its owner's coupled joint posterior."""

    def __init__(self, owner, site):
        self.owner, self.site, self.biased = owner, site, owner.biased
        self.grid_size = owner.grid_size
        self._polygon = [(RATE_LOW, RATE_LOW / HIGH), (RATE_HIGH, RATE_HIGH / HIGH),
                         (RATE_HIGH, RATE_HIGH / LOW), (RATE_LOW, RATE_LOW / LOW)]
        self._constraints = [(1 / LOW, -1., 0.), (-1 / HIGH, 1., 0.)]
        self._bound = 0.
        self._terms = []
        self._atom = None
        self._seen = {}
        self._operations = []
        self._fusion_count = 0
        self._fusion_precision = self._fusion_mu = 0.
        self._local_revision = 0
        self._eval_cache = {}
        self._full_eval_key = self._full_eval = None
        self._query_cache = {}
        self._weights_revision = -1

    @property
    def revision(self):
        return self.owner.revision

    def _touch(self, operation):
        self._local_revision += 1
        self._eval_cache.clear()
        self._full_eval_key = self._full_eval = None
        self._operations.append(operation)
        self.owner._operations.append({"site": self.site, **deepcopy(operation)})
        self.owner._touch()

    def _prior_logdensity(self, capacities):
        result = -np.log(capacities) - math.log(math.log(HIGH / LOW))
        if self.biased:
            result = result + np.log(np.where(np.asarray(capacities) < 50., .01,
                                   .01 + .99 * math.log(HIGH / LOW) / math.log(2.)))
        if self._fusion_count:
            logs = np.log(capacities)
            result = result - self._fusion_count * logs - .5 * self._fusion_precision * (logs - self._fusion_mu) ** 2
        return result

    def _logdensity(self, rates, capacities, terms):
        rates, capacities = np.broadcast_arrays(rates, capacities)
        result = self._prior_logdensity(capacities)
        block = max(1, 65536 // max(1, capacities.size))
        for start in range(0, len(terms), block):
            z = np.asarray(terms[start:start + block]).reshape((-1,) + (1,) * capacities.ndim)
            potentials = rates * z * (1. - z / capacities) + RECOVERY
            result = result - np.log(WIDTH * potentials).sum(axis=0)
        return result

    def _rate_support(self):
        intervals = []
        if self._polygon:
            lo, hi = min(p[0] for p in self._polygon), max(p[0] for p in self._polygon)
            if hi > lo:
                intervals.append((lo, hi))
        if self._atom is not None:
            intervals.append(self._atom["support"])
        return _intersect_unions([(RATE_LOW, RATE_HIGH)], intervals)

    def _capacity_limits(self, rates):
        lower_t = np.full(len(rates), np.inf)
        upper_t = np.full(len(rates), -np.inf)
        for left, right in zip(self._polygon, self._polygon[1:] + self._polygon[:1]):
            if left[0] == right[0]:
                continue
            valid = (rates >= min(left[0], right[0])) & (rates <= max(left[0], right[0]))
            value = left[1] + (rates - left[0]) * (right[1] - left[1]) / (right[0] - left[0])
            lower_t = np.where(valid, np.minimum(lower_t, value), lower_t)
            upper_t = np.where(valid, np.maximum(upper_t, value), upper_t)
        with np.errstate(divide="ignore", invalid="ignore"):
            lower = np.maximum(max(LOW, self._bound), rates / upper_t)
            upper = np.minimum(HIGH, rates / lower_t)
        valid = (upper_t > lower_t) & (lower_t > 0) & (upper > lower)
        return np.where(valid, lower, HIGH), np.where(valid, upper, LOW)

    def _evaluate(self, rates):
        key = rates.tobytes()
        full_grid = rates is self.owner._rates or rates is getattr(self.owner, "_building_rate_grid", None)
        cached = (self._full_eval if full_grid and key == self._full_eval_key
                  else self._eval_cache.get(key))
        if cached is not None:
            if not full_grid:
                # Dictionary insertion order gives a bounded two-query LRU.
                self._eval_cache.pop(key)
                self._eval_cache[key] = cached
            return cached
        lower, upper = self._capacity_limits(rates)
        edges = self.owner._capacity_edges
        if self._fusion_count:
            # Resolve the finite-width reconstructed beliefs and tails cut by
            # each rate's hard K support; narrow fusion is never snapped to a
            # grid point or converted into certainty.
            sigma = 1 / math.sqrt(self._fusion_precision)
            mode = self._fusion_mu - self._fusion_count / self._fusion_precision
            extra = np.exp(np.clip(mode + np.arange(-12, 13) * sigma, math.log(LOW), math.log(HIGH)))
            rows = np.broadcast_to(np.r_[edges, extra], (len(rates), len(edges) + len(extra)))
            tails = []
            for capacities in (lower, upper):
                capacities = np.clip(capacities, LOW, HIGH)
                slope = -self._fusion_count - self._fusion_precision * (np.log(capacities) - self._fusion_mu)
                for z in self._terms:
                    potential = rates * z * (1 - z / capacities) + RECOVERY
                    slope -= rates * z * z / (capacities * potential)
                scale = 1 / (1 / sigma + abs(slope))
                offsets = np.asarray([-.25, -.5, -1., -2., -4., -8., -16., -32.,
                                      .25, .5, 1., 2., 4., 8., 16., 32.])
                tails.append(np.exp(np.clip(np.log(capacities)[:, None] + scale[:, None] * offsets,
                                             math.log(LOW), math.log(HIGH))))
            edges = np.sort(np.concatenate((rows, *tails), axis=1), axis=1)
        else:
            edges = edges[None, :]
        left = np.maximum(edges[:, :-1], lower[:, None])
        right = np.minimum(edges[:, 1:], upper[:, None])
        rows, columns = np.nonzero(right > left)
        half = (right[rows, columns] - left[rows, columns]) / 2
        points = left[rows, columns, None] + half[:, None] * (1 + _KNODES)
        if len(rows):
            logs = self._logdensity(rates[rows, None], points, self._terms)
            logs = logs + np.log(half[:, None] * _KWEIGHTS)
            binlogs = logsumexp(logs, axis=1)
        else:
            logs, binlogs = np.empty((0, 8)), np.empty(0)
        log_mass = np.full(len(rates), -np.inf)
        np.logaddexp.at(log_mass, rows, binlogs)
        atom_logs = np.full(len(rates), -np.inf)
        if self._atom is not None:
            atom = self._atom
            valid = (rates > atom["support"][0]) & (rates < atom["support"][1])
            selected = rates[valid]
            capacity = atom["capacity"]
            values = self._logdensity(selected, capacity, atom["terms"])
            for z in atom["clips"]:
                potential = selected * z * (1 - z / capacity) + RECOVERY
                probability = np.clip((WHIGH - (capacity - z) / potential) / WIDTH, 0., 1.)
                with np.errstate(divide="ignore"):
                    values = values + np.log(probability)
            atom_logs[valid] = values
        normalizer = np.logaddexp(log_mass, atom_logs)
        cached = {"log_z": normalizer, "rows": rows, "points": points, "logs": logs,
                  "left": left[rows, columns], "right": right[rows, columns], "atom_logs": atom_logs}
        # Marginal-CDF refinements repeatedly query small rate arrays. Pin the
        # current full rate grid so they cannot evict its expensive integral;
        # retain just the two most recent refinement arrays alongside it.
        # This changes only cache lifetime, never arithmetic or quadrature.
        if full_grid:
            self._full_eval_key, self._full_eval = key, cached
        else:
            if len(self._eval_cache) >= 2:
                self._eval_cache.pop(next(iter(self._eval_cache)))
            self._eval_cache[key] = cached
        return cached

    @_transaction
    def observe_stock(self, stock):
        _number(stock, "stock")
        if not 0 <= stock <= HIGH:
            raise ValueError("stock is outside prior capacity support")
        if stock <= self._bound:
            return False
        self._bound = float(stock)
        if stock > 0:
            self._polygon = _clip(self._polygon, 1 / stock, -1., 0.)
            self._constraints.append((1 / stock, -1., 0.))
        if self._atom is not None and self._atom["capacity"] < stock and not _same(self._atom["capacity"], stock):
            self._atom = None
        self._touch({"kind": "bound", "stock": float(stock)})
        self.owner._assert_support()
        return True

    @_transaction
    def update_event(self, event):
        if type(event) is not GrowthEvidence or event.site != self.site:
            raise ValueError("canonical growth event must belong to this site")
        if type(event.tick) is not int or event.tick < 0:
            raise ValueError("invalid physical event tick")
        for name in ("z", "stock_next"):
            _number(getattr(event, name), name)
        z, y = event.z, event.stock_next
        if not 0 <= z <= y <= HIGH:
            raise ValueError("invalid clean growth stocks")
        key = (event.site, event.tick)
        if key in self._seen:
            if self._seen[key] != asdict(event):
                raise ValueError("conflicting duplicate physical event")
            return False
        growth = y - z
        band = [(z, -z * z, RECOVERY - growth / WHIGH),
                (-z, z * z, growth / WLOW - RECOVERY)]
        atom = self._atom
        repeated = atom is not None and _same(atom["capacity"], y)
        if repeated:
            capacity = atom["capacity"]
            interval = _interval_clip(atom["support"], z * (1 - z / capacity), RECOVERY - (capacity - z) / WHIGH)
            possible = [(RATE_LOW, RATE_HIGH)]
            for other in self.owner._sites.values():
                if other is not self:
                    possible = _intersect_unions(possible, other._rate_support())
            if interval is not None and _intersect_unions(possible, [interval]):
                atom = deepcopy(atom)
                atom["support"] = interval
                atom["clips"].append(z)
                self._polygon = []
            else:
                atom = None
                repeated = False
        elif atom is not None:
            if atom["capacity"] < y:
                atom = None
            else:
                atom = deepcopy(atom)
                for a, b, c in band:
                    atom["support"] = _interval_clip(atom["support"], a + b / atom["capacity"], c)
                if atom["support"] is None:
                    atom = None
                else:
                    atom["terms"].append(z)
        if not repeated and LOW <= y <= HIGH and y >= self._bound and self._polygon:
            interval = (RATE_LOW, RATE_HIGH)
            for a, b, c in self._constraints:
                interval = _interval_clip(interval, a + b / y, c)
            interval = _interval_clip(interval, z * (1 - z / y), RECOVERY - growth / WHIGH)
            if interval is not None:
                atom = {"capacity": float(y), "support": interval,
                        "terms": list(self._terms), "clips": [float(z)]}
        self._atom = atom
        if not repeated:
            for a, b, c in band:
                self._polygon = _clip(self._polygon, a, b, c)
                self._constraints.append((a, b, c))
            self._terms.append(float(z))
        if y > 0:
            self._polygon = _clip(self._polygon, 1 / y, -1., 0.)
            self._constraints.append((1 / y, -1., 0.))
        self._bound = max(self._bound, float(y))
        self._seen[key] = asdict(event)
        self._touch({"kind": "transition", "event": asdict(event)})
        self.owner._assert_support()
        return True

    @_transaction
    def fuse(self, median, iqr):
        for value, name in ((median, "median"), (iqr, "iqr")):
            _number(value, name)
        if not LOW <= median <= HIGH or not 0 <= iqr <= HIGH - LOW:
            raise ValueError("belief summary is outside capacity support")
        sigma = max(math.asinh(iqr / (2 * median)) / float(ndtri(.75)), math.log(HIGH / LOW) / 400)
        precision = 1 / sigma ** 2
        new_precision = self._fusion_precision + precision
        self._fusion_mu += precision * (math.log(median) - self._fusion_mu) / new_precision
        self._fusion_precision = new_precision
        self._fusion_count += 1
        self._touch({"kind": "fusion", "median": float(median), "iqr": float(iqr)})
        return True

    def _joint_weights(self):
        if self._weights_revision == self.revision:
            return self._weights_cache
        self.owner._refresh()
        evaluation = self._evaluate(self.owner._rates)
        rows = evaluation["rows"]
        with np.errstate(invalid="ignore"):
            log_factor = self.owner._log_weights - evaluation["log_z"]
        log_factor = np.where(np.isfinite(self.owner._log_weights), log_factor, -np.inf)
        weights = np.exp(evaluation["logs"] + log_factor[rows, None])
        atom_weights = np.exp(evaluation["atom_logs"] + log_factor)
        self._weights_revision = self.revision
        self._weights_cache = evaluation, weights, atom_weights
        return self._weights_cache

    @property
    def atoms(self):
        if self._atom is None:
            return {}
        _, _, weights = self._joint_weights()
        return {self._atom["capacity"]: min(1., max(0., float(weights.sum())))}

    @property
    def continuous_mass(self):
        _, weights, _ = self._joint_weights()
        return float(weights.sum())

    def _cdf_logmass(self, rates, value, left):
        """Unnormalised conditional K mass below a capacity, for each r."""
        evaluation = self._evaluate(rates)
        selected = evaluation["right"] <= value
        total = np.full(len(rates), -np.inf)
        np.logaddexp.at(total, evaluation["rows"][selected],
                       logsumexp(evaluation["logs"][selected], axis=1))
        partial = (evaluation["left"] < value) & (evaluation["right"] > value)
        if partial.any():
            lo = evaluation["left"][partial]
            half = (value - lo) / 2
            points = lo[:, None] + half[:, None] * (1 + _KNODES)
            rows = evaluation["rows"][partial]
            logs = self._logdensity(rates[rows, None], points, self._terms)
            logs = logs + np.log(half[:, None] * _KWEIGHTS)
            np.logaddexp.at(total, rows, logsumexp(logs, axis=1))
        if self._atom is not None:
            capacity = self._atom["capacity"]
            if ((capacity < value and not _same(capacity, value)) or (not left and _same(capacity, value))):
                total = np.logaddexp(total, evaluation["atom_logs"])
        return total

    def _cdf_rate_cuts(self, value):
        """Where a queried K crosses a conditional-support boundary."""
        if value <= 0:
            return []
        cuts = []
        for a, b in zip(self._polygon, self._polygon[1:] + self._polygon[:1]):
            fa, fb = a[1] - a[0] / value, b[1] - b[0] / value
            if (fa < 0) != (fb < 0) and fa != fb:
                cuts.append(a[0] + fa / (fa - fb) * (b[0] - a[0]))
        return cuts

    def _bound_only(self):
        return not any(self._terms) and self._atom is None and not self._fusion_count

    def _bound_prior(self, value=None, q=None):
        lower = max(LOW, self._bound)
        first = (.01 if self.biased else 1.) / math.log(HIGH / LOW)
        second = .99 / math.log(2.) if self.biased else 0.
        split = max(lower, 50.)
        low_mass = first * math.log(split / lower)
        total = first * math.log(HIGH / lower) + second * math.log(HIGH / split)
        if q is not None:
            target = q * total
            return (lower * math.exp(target / first) if target <= low_mass
                    else split * math.exp((target - low_mass) / (first + second)))
        upper = min(HIGH, max(lower, value))
        mass = first * math.log(upper / lower)
        if upper > split:
            mass += second * math.log(upper / split)
        return min(1., max(0., mass / total))

    def _capacity_support(self):
        values = []
        for lo, hi in self.owner._support():
            polygon = _clip(_clip(self._polygon, 1., 0., -lo), -1., 0., hi)
            values.extend(r / t for r, t in polygon if t > 0)
            if self._atom is not None and _intersect_unions([(lo, hi)], [self._atom["support"]]):
                values.append(self._atom["capacity"])
        if not values:
            raise ValueError("empty marginal capacity support")
        lo, hi = min(values), max(values)
        return max(LOW, lo - 16 * math.ulp(max(1., lo))), min(HIGH, hi + 16 * math.ulp(max(1., hi)))

    def cdf(self, value, left=False):
        _number(value, "value")
        if type(left) is not bool:
            raise ValueError("left must be boolean")
        if self._bound_only():
            return self._bound_prior(value=value)
        key = (self.revision, "cdf", value, left)
        if key in self._query_cache:
            return self._query_cache[key]
        self.owner._refresh()
        evaluation = self._evaluate(self.owner._rates)
        with np.errstate(invalid="ignore"):
            per_rate = np.exp(self.owner._log_weights - evaluation["log_z"]
                              + self._cdf_logmass(self.owner._rates, value, left))
        per_rate = np.where(np.isfinite(per_rate), per_rate, 0.)
        total = float(per_rate.sum())
        cuts = self._cdf_rate_cuts(value)
        # Conditional CDFs gain two additional rate kinks when the queried
        # capacity crosses their feasible polygon. Split only those intervals;
        # using a node indicator here can bias narrow-posterior rank checks.
        for index, (lo, hi) in enumerate(self.owner._rate_intervals):
            interior = sorted({point for point in cuts if lo < point < hi})
            if not interior:
                continue
            bounds = [lo, *interior, hi]
            for a, b in zip(bounds[:-1], bounds[1:]):
                half = (math.log(b) - math.log(a)) / 2
                if half <= 0:
                    continue
                rates = np.exp(math.log(a) + half * (1 + self.owner._rnodes))
                logs = np.log(half * self.owner._rweights / math.log(RATE_HIGH / RATE_LOW))
                logs += self._cdf_logmass(rates, value, left)
                for site in self.owner._sites.values():
                    if site is not self:
                        logs += site._evaluate(rates)["log_z"]
                total += float(np.exp(logsumexp(logs) - self.owner._log_normalizer))
            total -= float(per_rate[index * self.owner.rate_order:(index + 1) * self.owner.rate_order].sum())
        answer = min(1., max(0., total))
        if len(self._query_cache) > 256:
            self._query_cache.clear()
        self._query_cache[key] = answer
        return answer

    def quantile(self, q):
        _number(q, "q")
        if not 0 < q < 1:
            raise ValueError("q must be strictly between zero and one")
        if self._bound_only():
            return self._bound_prior(q=q)
        key = (self.revision, "quantile", q)
        if key in self._query_cache:
            return self._query_cache[key]
        if self._atom is not None:
            capacity = self._atom["capacity"]
            if self.cdf(capacity, left=True) <= q <= self.cdf(capacity):
                self._query_cache[key] = capacity
                return capacity
        lo, hi = self._capacity_support()
        result = brentq(lambda value: self.cdf(value) - q, lo, hi, xtol=1e-10, rtol=1e-12)
        self._query_cache[key] = result
        return result

    def interval(self, level=.9):
        _number(level, "level")
        if not 0 < level < 1:
            raise ValueError("level must be strictly between zero and one")
        return self.quantile((1 - level) / 2), self.quantile((1 + level) / 2)

    def predictive_cdf(self, y, z, left=False):
        _number(y, "y")
        _number(z, "z")
        if not 0 <= z <= self._bound or type(left) is not bool:
            raise ValueError("prediction requires a legally bounded stock and boolean left")
        evaluation, weights, atom_weights = self._joint_weights()
        points = evaluation["points"]
        rates = self.owner._rates[evaluation["rows"], None]
        potential = rates * z * (1 - z / points) + RECOVERY
        probabilities = np.where(points <= y, 1., np.clip(((y - z) / potential - WLOW) / WIDTH, 0., 1.))
        total = float((weights * probabilities).sum())
        if self._atom is not None:
            capacity = self._atom["capacity"]
            potential = self.owner._rates * z * (1 - z / capacity) + RECOVERY
            if capacity < y and not _same(capacity, y):
                probabilities = 1.
            elif _same(capacity, y):
                probabilities = (np.clip(((capacity - z) / potential - WLOW) / WIDTH, 0., 1.) if left else 1.)
            else:
                probabilities = np.clip(((y - z) / potential - WLOW) / WIDTH, 0., 1.)
            total += float((atom_weights * probabilities).sum())
        return min(1., max(0., total))

    def memory(self):
        return {"version": VERSION, "site": self.site, "biased": self.biased,
                "grid_size": self.grid_size, "joint_revision": self.revision,
                "operations": deepcopy(self._operations)}


class JointPosterior:
    """One private global rate, with conditionally independent site factors."""

    def __init__(self, *, biased=False, grid_size=400, rate_bins=32, rate_order=8):
        if type(biased) is not bool:
            raise ValueError("biased must be boolean")
        if type(grid_size) is not int or grid_size < 16:
            raise ValueError("grid_size must be at least 16")
        if type(rate_bins) is not int or rate_bins < 4:
            raise ValueError("rate_bins must be at least four")
        if type(rate_order) is not int or rate_order not in (4, 8, 16):
            raise ValueError("rate_order must be four, eight or sixteen")
        self.biased, self.grid_size, self.rate_bins, self.rate_order = biased, grid_size, rate_bins, rate_order
        self._capacity_edges = np.geomspace(LOW, HIGH, grid_size + 1)
        if biased:
            self._capacity_edges = np.unique(np.r_[self._capacity_edges, 50.])
        self._rate_edges = np.geomspace(RATE_LOW, RATE_HIGH, rate_bins + 1)
        self._rnodes, self._rweights = np.polynomial.legendre.leggauss(rate_order)
        self._sites = {}
        self.revision = 0
        self._refreshed = -1
        self._operations = []
        self._rates = self._log_weights = None

    def site(self, site, biased=None):
        if type(site) is not int or site < 0:
            raise ValueError("site must be a nonnegative integer")
        if biased is not None and (type(biased) is not bool or biased != self.biased):
            raise ValueError("site bias must match its owner's declared prior")
        if site not in self._sites:
            self._sites[site] = JointSitePosterior(self, site)
            self._refreshed = -1
        return self._sites[site]

    view = site

    def observe_stock(self, site, stock):
        return self.site(site).observe_stock(stock)

    def update_event(self, event):
        return self.site(event.site).update_event(event)

    def _touch(self):
        self.revision += 1
        self._refreshed = -1

    def _support(self):
        intervals = [(RATE_LOW, RATE_HIGH)]
        for site in self._sites.values():
            intervals = _intersect_unions(intervals, site._rate_support())
        return intervals

    def _assert_support(self):
        if not self._support():
            raise ValueError("evidence has zero joint posterior probability")

    def _refresh(self):
        if self._refreshed == self.revision:
            return
        support = self._support()
        if not support:
            raise ValueError("evidence has zero joint posterior probability")
        edges = list(self._rate_edges)
        for site in self._sites.values():
            edges.extend(point[0] for point in site._polygon)
            if site._atom is not None:
                edges.extend(site._atom["support"])
        intervals = []
        for lo, hi in support:
            cuts = sorted({lo, hi, *(value for value in edges if lo < value < hi)})
            intervals.extend(zip(cuts[:-1], cuts[1:]))
        left = np.asarray([math.log(a) for a, b in intervals])
        right = np.asarray([math.log(b) for a, b in intervals])
        half = (right - left) / 2
        rates = np.exp(left[:, None] + half[:, None] * (1 + self._rnodes)).ravel()
        logs = np.log(half[:, None] * self._rweights / math.log(RATE_HIGH / RATE_LOW)).ravel()
        self._building_rate_grid = rates
        for site in self._sites.values():
            logs = logs + site._evaluate(rates)["log_z"]
        total = float(logsumexp(logs))
        if not math.isfinite(total):
            raise ValueError("numerical quadrature lost joint support")
        self._rates, self._log_weights = rates, logs - total
        self._building_rate_grid = None
        self._log_normalizer = total
        self._rate_intervals = intervals
        self._refreshed = self.revision

    def rate_cdf(self, value, left=False):
        _number(value, "value")
        if type(left) is not bool:
            raise ValueError("left must be boolean")
        if not any(any(site._terms) or site._atom is not None for site in self._sites.values()):
            return math.log(min(RATE_HIGH, max(RATE_LOW, value)) / RATE_LOW) / math.log(RATE_HIGH / RATE_LOW)
        self._refresh()
        # Reintegrate the one partially covered rate interval, keeping every
        # site's factor. Summing quadrature-node indicators would make an
        # artificial discrete rate posterior and biased calibration ranks.
        weights = np.exp(self._log_weights).reshape((-1, self.rate_order))
        total = sum(float(row.sum()) for row, (_, hi) in zip(weights, self._rate_intervals) if hi <= value)
        for lo, hi in self._rate_intervals:
            if lo < value < hi:
                log_lo, log_hi = math.log(lo), math.log(value)
                half = (log_hi - log_lo) / 2
                rates = np.exp(log_lo + half * (1 + self._rnodes))
                logs = np.log(half * self._rweights / math.log(RATE_HIGH / RATE_LOW))
                for site in self._sites.values():
                    logs += site._evaluate(rates)["log_z"]
                total += float(np.exp(logsumexp(logs) - self._log_normalizer))
                break
        return min(1., max(0., total))

    def rate_quantile(self, q):
        _number(q, "q")
        if not 0 < q < 1:
            raise ValueError("q must be strictly between zero and one")
        if not any(any(site._terms) or site._atom is not None for site in self._sites.values()):
            return RATE_LOW * math.exp(q * math.log(RATE_HIGH / RATE_LOW))
        lo, hi = RATE_LOW, RATE_HIGH
        for _ in range(38):
            middle = (lo + hi) / 2
            if self.rate_cdf(middle) >= q:
                hi = middle
            else:
                lo = middle
        return (lo + hi) / 2

    def rate_interval(self, level=.9):
        _number(level, "level")
        if not 0 < level < 1:
            raise ValueError("level must be strictly between zero and one")
        return self.rate_quantile((1 - level) / 2), self.rate_quantile((1 + level) / 2)

    def memory(self):
        return {"version": VERSION, "biased": self.biased, "grid_size": self.grid_size,
                "rate_bins": self.rate_bins, "rate_order": self.rate_order,
                "sites": sorted(self._sites), "operations": deepcopy(self._operations)}

    @classmethod
    def restore(cls, memory):
        if memory.get("version") != VERSION:
            raise ValueError("unknown joint posterior memory")
        result = cls(**{name: memory[name] for name in ("biased", "grid_size", "rate_bins", "rate_order")})
        for site in memory["sites"]:
            result.site(site)
        for operation in memory["operations"]:
            site = result.site(operation["site"])
            if operation["kind"] == "bound":
                site.observe_stock(operation["stock"])
            elif operation["kind"] == "transition":
                site.update_event(GrowthEvidence(**operation["event"]))
            elif operation["kind"] == "fusion":
                site.fuse(operation["median"], operation["iqr"])
            else:
                raise ValueError("unknown joint posterior operation")
        if result.memory() != memory:
            raise ValueError("joint posterior memory is not canonical")
        return result
