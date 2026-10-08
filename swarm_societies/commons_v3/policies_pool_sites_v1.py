"""A1's instantaneous pooled-evidence reference, with local navigation.

The coordinator joins the union of legal stock observations at successive
ticks. Only total extraction is privileged: no unobserved stock, capacity or
weather enters inference. A physical (site, tick) transition is applied once,
even when several observers report it. The resulting beliefs are shared for
free, but each frozen forager retains only its own observed route map.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math

from . import engine_sites_v1 as engine
from .evidence_sites_v1 import _local_packet
from .messages_sites_v1 import GrowthEvidence
from .policies_learning_sites_v1 import _validate_ecology
from .policies_navigation_v1 import ForagerPolicy
from .policies_sharing_sites_v1 import COUNTERS, new_prior


VERSION = "commons-v3-pooled-evidence-forager-sites-v1"


class PoolCoordinator:
    """Prepare one shared posterior update before any individual decides.

    ``prepare(packets, previous_result)`` receives all current legal packets
    and the preceding physical result. The only result fields read are
    ``ledger.tick``, patch IDs and total ``harvested`` for paired visible sites.
    A transition can join different observers' consecutive observations; sites
    absent from either union contribute no transition. Bounds also pool.
    """

    def __init__(self):
        self.posteriors = {}
        self.counters = dict.fromkeys(COUNTERS, 0)
        self.last_updates = []
        self.tick = None
        self._packets = None
        self._stocks = {}
        self._last_extraction = {}
        self._transition_sites = ()

    def _posterior(self, site):
        if site not in self.posteriors:
            self.posteriors[site] = new_prior(site=site, biased=False)
        return self.posteriors[site]

    @staticmethod
    def _extraction(previous_result, tick, sites):
        if (type(previous_result) is not engine.StepResult
                or previous_result.ledger.tick != tick - 1):
            raise ValueError("expected the immediately preceding physical result")
        rows = {}
        wanted = set(sites)
        for row in previous_result.ledger.patches:
            if row.id in wanted:
                if row.id in rows:
                    raise ValueError("duplicate pooled extraction site")
                amount = row.harvested
                if (type(amount) not in (int, float) or not math.isfinite(amount)
                        or amount < 0):
                    raise ValueError("invalid pooled total extraction")
                rows[row.id] = float(amount)
        if set(rows) != wanted:
            raise ValueError("missing pooled total extraction")
        return rows

    def prepare(self, packets, previous_result=None):
        if type(packets) not in (tuple, list) or not packets:
            raise ValueError("one legal observation per individual is required")
        current, visible = [], {}
        for identity, packet in enumerate(packets):
            _validate_ecology(packet)
            local = _local_packet(packet)
            if local["self"]["id"] != identity:
                raise ValueError("pool packets must be in individual order")
            current.append(local)
            for site in local["sites"]:
                projection = (site["x"], site["y"], site["stock"])
                if site["id"] in visible and visible[site["id"]] != projection:
                    raise ValueError("conflicting simultaneous site observations")
                visible[site["id"]] = projection
        tick = current[0]["tick"]
        if any(packet["tick"] != tick for packet in current):
            raise ValueError("pool observations must share one tick")
        stocks = {site: values[2] for site, values in visible.items()}
        if self.tick is not None:
            if len(current) != len(self._packets):
                raise ValueError("pooled population cannot change")
            if tick == self.tick:
                if current != self._packets:
                    raise ValueError("conflicting repeated pool observations")
                extraction = ({} if tick == 0 else
                              self._extraction(previous_result, tick, self._transition_sites))
                if extraction != self._last_extraction:
                    raise ValueError("conflicting repeated total extraction")
                return
            if tick != self.tick + 1:
                raise ValueError("pool observations must be consecutive")
        if tick == 0:
            if previous_result is not None:
                raise ValueError("initial observations have no preceding result")
            sites, extraction = (), {}
        else:
            sites = tuple(sorted(set(stocks) & set(self._stocks)))
            extraction = self._extraction(previous_result, tick, sites)
        growth = []
        for site in sites:
            old, harvested = self._stocks[site], extraction[site]
            # Match the engine's subtraction and roundoff clamp exactly.
            if harvested > old + 8 * math.ulp(max(1., old)):
                raise ValueError("total extraction exceeds observed site stock")
            z = max(0., old - harvested)
            if stocks[site] < z:
                raise ValueError("observed growth is negative after total extraction")
            growth.append(GrowthEvidence(site, tick - 1, z, stocks[site]))
        updates = []
        # The likelihood can create a saturation atom at the current stock.
        # Applying that bound first would erase its prior boundary density.
        for event in growth:
            if self._posterior(event.site).update_event(event):
                updates.append({"kind": "growth", **asdict(event)})
                self.counters["eligible"] += 1
                self.counters["clean_receipts"] += 1
        for site, stock in sorted(stocks.items()):
            if self._posterior(site).observe_stock(stock):
                updates.append({"kind": "bound", "site": site, "tick": tick, "stock": stock})
        self.last_updates = updates
        self.tick, self._packets, self._stocks = tick, current, stocks
        self._last_extraction, self._transition_sites = extraction, sites

    def memory(self):
        return {"version": VERSION, "tick": self.tick,
                "posteriors": [p.memory() for _, p in sorted(self.posteriors.items())],
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "packets": deepcopy(self._packets),
                "stocks": [[site, stock] for site, stock in sorted(self._stocks.items())],
                "last_extraction": [[site, value] for site, value in sorted(self._last_extraction.items())],
                "transition_sites": list(self._transition_sites)}


class PoolForager(ForagerPolicy):
    """The fixed L0 decision wrapper using the instantaneous pooled beliefs."""

    def __init__(self, coordinator, agent_id, *, phi=.375, q=.25):
        if not isinstance(coordinator, PoolCoordinator):
            raise ValueError("a PoolCoordinator is required")
        if type(agent_id) is not int or agent_id < 0:
            raise ValueError("agent_id must be a nonnegative integer")
        if type(phi) not in (int, float) or phi != .375:
            raise ValueError("A1 fixes phi=0.375")
        if type(q) not in (int, float) or q != .25:
            raise ValueError("A1 fixes q=0.25")
        super().__init__(reserve_ticks=2, stock_floor_fraction=.5,
                         route_mode="net_yield", aggressive=False)
        self.coordinator, self.agent_id = coordinator, agent_id
        self.arm, self.phi, self.q, self.biased = "R-pool", float(phi), float(q), False
        self.posteriors = coordinator.posteriors
        self.counters = dict.fromkeys(COUNTERS, 0)
        self.last_updates = []
        self.last_action = None
        self._observed_tick = self._acted_tick = None

    def observe(self, observation):
        _validate_ecology(observation)
        local = _local_packet(observation)
        pool = self.coordinator
        if (pool._packets is None or self.agent_id >= len(pool._packets)
                or local != pool._packets[self.agent_id]):
            raise ValueError("prepare the matching pool observation before deciding")
        if self._observed_tick == local["tick"]:
            return
        self.last_updates = deepcopy(pool.last_updates)
        self.counters = dict(pool.counters)
        self._observed_tick = local["tick"]

    def __call__(self, observation):
        self.observe(observation)
        if self._acted_tick == observation["tick"]:
            return self.last_action
        known_ids = set(self.records) | {site["id"] for site in observation["sites"]}
        capacities = {site: (self.phi / .5) * self.posteriors[site].quantile(self.q)
                      for site in known_ids}
        packet = {**observation, "sites": [{**site, "capacity": capacities[site["id"]]}
                                          for site in observation["sites"]]}
        for site, record in self.records.items():
            record["capacity"] = capacities[site]
        self.last_action = super().__call__(packet)
        if self.last_action.messages:
            raise RuntimeError("R-pool must never generate message traffic")
        self._acted_tick = observation["tick"]
        return self.last_action

    def memory(self):
        return {"version": VERSION, "arm": self.arm, "agent_id": self.agent_id,
                "phi": self.phi, "q": self.q, "biased": False,
                "forager": super().memory(),
                "posteriors": [p.memory() for _, p in sorted(self.posteriors.items())],
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "last_action": None if self.last_action is None else asdict(self.last_action),
                "observed_tick": self._observed_tick, "acted_tick": self._acted_tick}
