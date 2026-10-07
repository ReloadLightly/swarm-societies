"""Approved Ticket D priors and belief fusion, extending frozen Ticket C.

The biased prior is .99 LogUniform[50,100] + .01 LogUniform[8,100].
Reported median/IQR define the contracted truncated lognormal density. Fusion
multiplies that positive density into both continuous mass and existing atoms;
zero IQR never creates an atom. Repeated reports are deliberately not deduped.

Growth events retain the exact C likelihood and physical-event deduplication.
Their canonical projection conditions on z and the next stock only. Actual
observed pre-extraction stock bounds must be supplied separately by the caller.

The 400 base log bins remain. Extra integration edges resolve the prior jump
at 50 and narrow products of reports, including tails cut by growth evidence.
These are quadrature refinements, not changes to the posterior or message width.
"""
from __future__ import annotations

from copy import deepcopy
import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtri

from . import posterior_sites_v1 as physical
from .evidence_sites_v1 import CleanTransition


VERSION = "commons-v3-social-site-posterior-v1"
MIN_LOG_SIGMA = math.log(100. / 8.) / 400
_NORMAL_QUARTILE = float(ndtri(.75))


def belief_parameters(median, iqr):
    """Validate a truthful bounded-capacity summary and reconstruct its width."""
    physical._number(median, "median")
    physical._number(iqr, "iqr")
    if not physical.LOW <= median <= physical.HIGH or not 0 <= iqr <= physical.HIGH - physical.LOW:
        raise ValueError("belief summary is outside capacity support")
    sigma = max(math.asinh(iqr / (2 * median)) / _NORMAL_QUARTILE, MIN_LOG_SIGMA)
    return math.log(median), sigma


class SocialSitePosterior(physical.SitePosterior):
    def __init__(self, site=0, *, biased=False, grid_size=400):
        if type(biased) is not bool:
            raise ValueError("biased must be boolean")
        self.biased = biased
        self._fusion_count = 0
        self._fusion_precision = 0.
        self._fusion_mu = 0.
        self.revision = 0
        super().__init__(site=site, grid_size=grid_size)

    def _logpdf(self, points):
        result = super()._logpdf(points)
        points = np.asarray(points, dtype=float)
        if self.biased:
            multiplier = np.where(points < 50., .01,
                                  .01 + .99 * math.log(100. / 8.) / math.log(2.))
            result = result + np.log(multiplier)
        if self._fusion_count:
            logs = np.log(points)
            result = (result - self._fusion_count * logs
                      - .5 * self._fusion_precision * (logs - self._fusion_mu) ** 2)
        return result

    def _log_mass_slope(self, value):
        """Derivative of log continuous mass density in log-capacity space."""
        values = np.asarray(value, dtype=float)
        capacities = np.exp(values)
        result = -self._fusion_count - self._fusion_precision * (values - self._fusion_mu)
        for z in self._terms:
            a, b = physical.RATE * z + physical.RECOVERY, physical.RATE * z * z
            result = result - b / (a * capacities - b)
        return result

    def _integration_edges(self):
        base = self._base_edges
        extra = [50.] if self.biased else []
        lower, upper = max(physical.LOW, self._lo), min(physical.HIGH, self._hi)
        if not self._fusion_count or upper <= lower:
            return np.unique(np.r_[base, extra]) if extra else base
        lo, hi = math.log(lower), math.log(upper)
        sigma = 1 / math.sqrt(self._fusion_precision)
        mode = self._fusion_mu - self._fusion_count / self._fusion_precision
        # Find any growth-adjusted interior maximum. Sampling the existing
        # log bins brackets sign changes without changing the integration law.
        probes = np.unique(np.r_[lo, np.log(base[(base > lower) & (base < upper)]),
                                 min(hi, max(lo, mode)), hi])
        slopes = self._log_mass_slope(probes)
        centers = [mode]
        for left, right, dleft, dright in zip(probes, probes[1:], slopes, slopes[1:]):
            if dleft > 0 and dright < 0:
                centers.append(brentq(lambda value: float(self._log_mass_slope(value)),
                                       left, right, xtol=1e-14))
        log_edges = [center + offset * sigma for center in centers for offset in range(-12, 13)]
        # A sharply truncated normal can be far narrower than its unconstrained
        # sigma. The boundary slope supplies the corresponding tail scale.
        boundaries = [lo, hi]
        if self.biased and lower < 50. < upper:
            boundaries.append(math.log(50.))
        for boundary in boundaries:
            scale = 1 / (1 / sigma + abs(float(self._log_mass_slope(boundary))))
            log_edges.extend(boundary + direction * multiple * scale
                             for direction in (-1, 1)
                             for multiple in (.25, .5, 1., 2., 4., 8., 16., 32.))
        extra.extend(math.exp(value) for value in log_edges if lo < value < hi)
        return np.unique(np.r_[base, extra])

    def _refresh(self):
        if not hasattr(self, "_base_edges"):
            self._base_edges = self._edges.copy()
        self._edges = self._integration_edges()
        super()._refresh()
        self.revision += 1

    def update_event(self, event):
        """Apply/deduplicate canonical (site,tick,z,next-stock) evidence only."""
        from .messages_sites_v1 import GrowthEvidence
        if type(event) is not GrowthEvidence:
            raise ValueError("event must be canonical GrowthEvidence")
        return super().update(CleanTransition(event.site, event.tick, event.z,
                                              event.stock_next, event.z, 0.))

    def fuse(self, median, iqr):
        """Multiply one report, retaining shared components intentionally.

        Lognormal truncation/scale normalizers are constant in K and cancel
        between the continuous component and atoms. Weighted Gaussian merging
        avoids storing an increasingly long product in every density evaluation.
        """
        mu, sigma = belief_parameters(median, iqr)
        precision = 1 / sigma ** 2
        backup = deepcopy(self.__dict__)
        try:
            old_precision = self._fusion_precision
            new_precision = old_precision + precision
            delta = mu - self._fusion_mu
            # Completing the square removes a constant from the fused Gaussian;
            # retain that constant in _log_scale to match atom multiplication.
            self._log_scale -= .5 * old_precision * precision / new_precision * delta ** 2
            self._fusion_mu += precision / new_precision * delta
            self._fusion_precision = new_precision
            self._fusion_count += 1
            self._atoms_log = {capacity: value - math.log(capacity)
                              - .5 * precision * (math.log(capacity) - mu) ** 2
                              for capacity, value in self._atoms_log.items()}
            self._refresh()
            self._operations.append({"kind": "fusion", "median": float(median), "iqr": float(iqr)})
        except Exception:
            self.__dict__ = backup
            raise
        return True

    def memory(self):
        return {"version": VERSION, "site": self.site, "biased": self.biased,
                "grid_size": self.grid_size, "operations": deepcopy(self._operations)}

    @classmethod
    def restore(cls, memory):
        if (type(memory) is not dict
                or set(memory) != {"version", "site", "biased", "grid_size", "operations"}
                or memory["version"] != VERSION or type(memory["operations"]) is not list):
            raise ValueError("unknown social posterior memory")
        result = cls(memory["site"], biased=memory["biased"], grid_size=memory["grid_size"])
        for operation in memory["operations"]:
            if type(operation) is not dict:
                raise ValueError("invalid social posterior operation")
            if set(operation) == {"kind", "stock"} and operation["kind"] == "bound":
                result.observe_stock(operation["stock"])
            elif set(operation) == {"kind", "event"} and operation["kind"] == "transition":
                event = operation["event"]
                if type(event) is not dict or set(event) != {"site", "tick", "z", "stock_next", "stock_before", "own_harvest"}:
                    raise ValueError("invalid social posterior transition")
                result.update(CleanTransition(**event))
            elif set(operation) == {"kind", "median", "iqr"} and operation["kind"] == "fusion":
                result.fuse(operation["median"], operation["iqr"])
            else:
                raise ValueError("unknown social posterior operation")
        if result.memory() != memory:
            raise ValueError("social posterior memory is not canonical")
        return result
