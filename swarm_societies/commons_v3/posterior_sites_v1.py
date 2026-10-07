"""Site-capacity inference with the contracted mixed growth likelihood.

The continuous log-uniform prior is integrated on 400 logarithmic bins;
eight-point quadrature integrates the smooth density within the analytically
intersected support. Observation-generated capacity atoms remain off-grid.
Thus the likelihood is exact; continuous posterior integration is numerical.
There is no clipping flag, sensor noise, snapped observation or particle filter.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math

import numpy as np
from scipy.special import logsumexp

from .evidence_sites_v1 import CleanTransition

VERSION = "commons-v3-site-posterior-v1"
LOW, HIGH, RATE, RECOVERY = 8., 100., .24, .02
WLOW, WHIGH = .9, 1.1
WIDTH = WHIGH - WLOW
_NODES, _WEIGHTS = np.polynomial.legendre.leggauss(8)


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _same(a, b):
    # Only floating-point representation error, not measurement uncertainty.
    return abs(a - b) <= 8 * math.ulp(max(1., abs(a), abs(b)))


def potential(z, capacity):
    return RATE * z * (1. - z / capacity) + RECOVERY


def clipping_probability(z, capacity):
    return min(1., max(0., (WHIGH - (capacity - z) / potential(z, capacity)) / WIDTH))


def _continuous_limits(z, y):
    """Invert the two uniform-weather inequalities; no grid-point rejection."""
    growth = y - z
    a, b = RATE * z + RECOVERY, RATE * z * z
    if b == 0:
        if WLOW * a <= growth <= WHIGH * a:
            return y, math.inf
        return math.inf, -math.inf
    p_low, p_high = growth / WHIGH, growth / WLOW
    if p_low >= a:
        return math.inf, -math.inf
    lower = max(y, b / (a - p_low))
    upper = b / (a - p_high) if p_high < a else math.inf
    return lower, upper


class SitePosterior:
    def __init__(self, site=0, grid_size=400):
        if type(site) is not int or site < 0:
            raise ValueError("site must be a nonnegative integer")
        if type(grid_size) is not int or grid_size < 16:
            raise ValueError("grid_size must be at least 16")
        self.site, self.grid_size = site, grid_size
        self._edges = np.geomspace(LOW, HIGH, grid_size + 1)
        self._lo, self._hi = LOW, HIGH
        self._bound = 0.
        self._terms = []
        self._log_scale = 0.
        self._atoms_log = {}
        self._seen = {}
        self._operations = []
        self._refresh()

    def _logpdf(self, points):
        points = np.asarray(points, dtype=float)
        result = -np.log(points) - math.log(math.log(HIGH / LOW)) + self._log_scale
        for z in self._terms:
            result = result - np.log(WIDTH * (RATE * z * (1. - z / points) + RECOVERY))
        return result

    def _density(self, value):
        if self._lo <= value <= self._hi and self._hi > self._lo:
            return float(self._logpdf([value])[0])
        return -math.inf

    def _quadrature(self, left, right):
        left, right = np.asarray(left), np.asarray(right)
        half = (right - left) / 2
        points = (left + half)[:, None] + half[:, None] * _NODES
        logs = self._logpdf(points) + np.log(half[:, None] * _WEIGHTS)
        return points, logs

    def _refresh(self):
        self._quantile_cache = {}
        left = np.maximum(self._edges[:-1], self._lo)
        right = np.minimum(self._edges[1:], self._hi)
        valid = right > left
        self._left, self._right = left[valid], right[valid]
        if self._left.size:
            _, logs = self._quadrature(self._left, self._right)
            bin_logs = logsumexp(logs, axis=1)
        else:
            bin_logs = np.array([])
        total = float(logsumexp([*bin_logs, *self._atoms_log.values()]))
        if not math.isfinite(total):
            raise ValueError("evidence has zero posterior probability")
        self._log_scale -= total
        self._atoms_log = {k: value - total for k, value in self._atoms_log.items()}
        self._mass = np.exp(bin_logs - total)
        self._prefix = np.r_[0., np.cumsum(self._mass)]

    @property
    def atoms(self):
        return {k: math.exp(v) for k, v in self._atoms_log.items()}

    @property
    def continuous_mass(self):
        return float(self._mass.sum())

    def _integral(self, lower, upper):
        if upper <= lower or not self._left.size:
            return 0.
        left, right = np.maximum(self._left, lower), np.minimum(self._right, upper)
        use = right > left
        if not use.any():
            return 0.
        _, logs = self._quadrature(left[use], right[use])
        return float(np.exp(logsumexp(logs)))

    def observe_stock(self, stock):
        _number(stock, "stock")
        if not 0 <= stock <= HIGH:
            raise ValueError("stock is outside prior capacity support")
        if stock <= self._bound:
            return False
        backup = deepcopy(self.__dict__)
        try:
            self._bound = float(stock)
            self._lo = max(self._lo, stock)
            self._atoms_log = {k: v for k, v in self._atoms_log.items() if k >= stock or _same(k, stock)}
            self._refresh()
            self._operations.append({"kind": "bound", "stock": stock})
        except Exception:
            self.__dict__ = backup
            raise
        return True

    def update(self, transition):
        if (not isinstance(transition, CleanTransition) or type(transition.site) is not int
                or transition.site != self.site):
            raise ValueError("transition must belong to this site")
        event = asdict(transition)
        if type(transition.tick) is not int or transition.tick < 0:
            raise ValueError("invalid transition tick")
        for key in ("z", "stock_next", "stock_before", "own_harvest"):
            _number(event[key], key)
        z, y, before, harvested = (event[k] for k in ("z", "stock_next", "stock_before", "own_harvest"))
        if (not 0 <= z <= before <= HIGH or not 0 <= harvested <= before
                or not _same(z, before - harvested) or not z <= y <= HIGH):
            raise ValueError("invalid clean transition values")
        key = (transition.site, transition.tick)
        if key in self._seen:
            if self._seen[key] != event:
                raise ValueError("conflicting duplicate physical event")
            return False
        backup = deepcopy(self.__dict__)
        try:
            # The old observed stock is a legal capacity bound. The new stock
            # bound is already included by the likelihood; apply it afterward.
            self.observe_stock(before)
            repeated = [k for k in self._atoms_log if _same(k, y) and clipping_probability(z, k) > 0]
            if repeated:
                # An existing predictive atom dominates all continuous densities.
                k = repeated[0]
                self._atoms_log = {k: 0.}
                self._lo, self._hi = HIGH, LOW
            else:
                atom_logs = {}
                for k, value in self._atoms_log.items():
                    if k <= y:
                        continue
                    p = potential(z, k)
                    g = y - z
                    tolerance = 8 * math.ulp(max(1., abs(y), abs(z)))
                    if WLOW * p - tolerance <= g <= WHIGH * p + tolerance:
                        atom_logs[k] = value - math.log(WIDTH * p)
                density = self._density(y)
                clip = clipping_probability(z, y) if math.isfinite(density) else 0.
                if clip > 0 and math.isfinite(density):
                    atom_logs[float(y)] = density + math.log(clip)
                lower, upper = _continuous_limits(z, y)
                self._lo, self._hi = max(self._lo, lower), min(self._hi, upper)
                self._terms.append(float(z))
                self._atoms_log = atom_logs
            self._refresh()
            self._bound = max(self._bound, y)
            self._seen[key] = event
            self._operations.append({"kind": "transition", "event": event})
        except Exception:
            self.__dict__ = backup
            raise
        return True

    def cdf(self, value, left=False):
        _number(value, "value")
        count = int(np.searchsorted(self._right, value, side="right"))
        total = float(self._prefix[count])
        if count < len(self._left) and value > self._left[count]:
            _, logs = self._quadrature([self._left[count]], [value])
            total += float(np.exp(logsumexp(logs)))
        for k, mass in self.atoms.items():
            if (k < value and not _same(k, value)) or (not left and _same(k, value)):
                total += mass
        return min(1., max(0., total))

    def quantile(self, q):
        _number(q, "q")
        if not 0 < q < 1:
            raise ValueError("quantile must be strictly between zero and one")
        if q in self._quantile_cache:
            return self._quantile_cache[q]
        for k in sorted(self._atoms_log):
            if self.cdf(k, left=True) <= q <= self.cdf(k):
                self._quantile_cache[q] = k
                return k
        lo, hi = LOW, HIGH
        for _ in range(48):
            middle = (lo + hi) / 2
            if self.cdf(middle) >= q:
                hi = middle
            else:
                lo = middle
        value = (lo + hi) / 2
        self._quantile_cache[q] = value
        return value

    def interval(self, level=.9):
        _number(level, "level")
        if not 0 < level < 1:
            raise ValueError("interval level must be between zero and one")
        return self.quantile((1 - level) / 2), self.quantile((1 + level) / 2)

    def predictive_cdf(self, y, z, left=False):
        _number(y, "y")
        _number(z, "z")
        if z < 0 or z > HIGH or z > self._bound:
            raise ValueError("prediction requires a legally bounded nonnegative stock")
        # Split quadrature at all changes in the clipped-uniform CDF formula.
        limits = _continuous_limits(z, y)
        cuts = sorted({LOW, HIGH, min(HIGH, max(LOW, y)),
                       *(v for v in limits if math.isfinite(v) and LOW < v < HIGH)})
        total = 0.
        for lo, hi in zip(cuts, cuts[1:]):
            lower, upper = np.maximum(self._left, lo), np.minimum(self._right, hi)
            valid = upper > lower
            if not valid.any():
                continue
            points, logs = self._quadrature(lower[valid], upper[valid])
            p = RATE * z * (1. - z / points) + RECOVERY
            probabilities = np.where(points <= y, 1., np.clip(((y - z) / p - WLOW) / WIDTH, 0., 1.))
            total += float(np.sum(np.exp(logs) * probabilities))
        for k, mass in self.atoms.items():
            if k < y and not _same(k, y):
                probability = 1.
            elif _same(k, y):
                probability = 1. - clipping_probability(z, k) if left else 1.
            else:
                probability = min(1., max(0., ((y - z) / potential(z, k) - WLOW) / WIDTH))
            total += mass * probability
        return min(1., max(0., total))

    def memory(self):
        return {"version": VERSION, "site": self.site, "grid_size": self.grid_size,
                "operations": deepcopy(self._operations)}

    @classmethod
    def restore(cls, memory):
        if set(memory) != {"version", "site", "grid_size", "operations"} or memory["version"] != VERSION:
            raise ValueError("unknown site posterior memory")
        result = cls(memory["site"], memory["grid_size"])
        for operation in memory["operations"]:
            if operation["kind"] == "bound" and set(operation) == {"kind", "stock"}:
                result.observe_stock(operation["stock"])
            elif operation["kind"] == "transition" and set(operation) == {"kind", "event"}:
                result.update(CleanTransition(**operation["event"]))
            else:
                raise ValueError("unknown posterior operation")
        return result
