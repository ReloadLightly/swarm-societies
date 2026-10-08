"""A2 asocial and perfectly pooled learning with an unknown global growth rate.

Each asocial agent owns one joint posterior over its shared rate and site
capacities. The pooled reference shares one such posterior, while navigation
continues to use only each individual's local site map. Physical dynamics and
the frozen forager are unchanged. No policy receives the true growth rate.
"""
from copy import deepcopy
from dataclasses import asdict
import math

from .evidence_sites_v1 import LocalEvidence, _local_packet
from .messages_sites_v1 import GrowthEvidence
from .observations_joint_sites_v1 import validate_ecology
from .policies_navigation_v1 import ForagerPolicy
from .policies_pool_sites_v1 import PoolCoordinator, PoolForager
from .policies_sharing_sites_v1 import COUNTERS
from .posterior_joint_sites_v1 import JointPosterior


VERSION = "commons-v3-unknown-rate-foragers-v1"


def _decision_parameters(phi, q):
    if type(phi) not in (int, float) or phi != .375:
        raise ValueError("A2 fixes phi=0.375")
    if type(q) not in (int, float) or q != .25:
        raise ValueError("A2 fixes q=0.25")


def new_prior(site=0, biased=False, *, grid_size=400, rate_bins=32, rate_order=8):
    """Standalone site marginal for evaluator-only unseen-site measurements."""
    return JointPosterior(biased=biased, grid_size=grid_size,
                          rate_bins=rate_bins, rate_order=rate_order).site(site)


class UnknownForager(ForagerPolicy):
    """L0's own evidence with capacity marginals coupled through one rate."""

    def __init__(self, arm="L0", *, phi=.375, q=.25, grid_size=400, rate_bins=32, rate_order=8):
        if arm != "L0":
            raise ValueError("this fallback stage implements L0 only")
        _decision_parameters(phi, q)
        super().__init__(reserve_ticks=2, stock_floor_fraction=.5,
                         route_mode="net_yield", aggressive=False)
        self.arm, self.phi, self.q, self.biased = arm, float(phi), float(q), False
        self.joint = JointPosterior(biased=False, grid_size=grid_size,
                                    rate_bins=rate_bins, rate_order=rate_order)
        self.posteriors = {}
        self.evidence = LocalEvidence()
        self.events = {}
        self.counters = dict.fromkeys(COUNTERS, 0)
        self.last_updates = []
        self.last_action = None
        self._observed_tick = self._acted_tick = None

    def _posterior(self, site):
        if site not in self.posteriors:
            self.posteriors[site] = self.joint.site(site)
        return self.posteriors[site]

    def observe(self, observation):
        validate_ecology(observation)
        tick = observation["tick"]
        if tick == self._observed_tick:
            self.evidence.observe(observation, self.last_action)
            return
        batch = self.evidence.observe(observation, self.last_action)
        self.last_updates = []
        if batch.reason in ("clean", "shared"):
            self.counters["eligible"] += 1
        self.counters["confounded"] += int(batch.reason == "shared")
        growth = tuple(GrowthEvidence(t.site, t.tick, t.z, t.stock_next)
                       for t in batch.transitions)
        self.counters["clean_own"] += len(growth)
        # Preserve D's evidence ordering: clipping atoms precede stock bounds.
        for event in growth:
            if self._posterior(event.site).update_event(event):
                self.events[(event.site, event.tick)] = event
                self.last_updates.append({"kind": "growth", **asdict(event)})
        for bound in batch.bounds:
            if self._posterior(bound.site).observe_stock(bound.stock):
                self.last_updates.append({"kind": "bound", **asdict(bound)})
        self._observed_tick = tick

    def __call__(self, observation):
        self.observe(observation)
        if self._acted_tick == observation["tick"]:
            return self.last_action
        known_ids = set(self.records) | {site["id"] for site in observation["sites"]}
        capacities = {site: (self.phi / .5) * self.posteriors[site].quantile(self.q)
                      for site in known_ids}
        packet = {**observation,
                  "sites": [{**site, "capacity": capacities[site["id"]]}
                            for site in observation["sites"]]}
        for site, record in self.records.items():
            record["capacity"] = capacities[site]
        self.last_action = super().__call__(packet)
        if self.last_action.messages:
            raise RuntimeError("fallback L0 must not generate message traffic")
        self._acted_tick = observation["tick"]
        return self.last_action

    def memory(self):
        return {"version": VERSION, "arm": self.arm, "phi": self.phi, "q": self.q,
                "biased": self.biased, "joint": self.joint.memory(),
                "forager": super().memory(), "evidence": self.evidence.memory(),
                "posterior_sites": sorted(self.posteriors),
                "events": [asdict(event) for _, event in sorted(self.events.items())],
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "last_action": None if self.last_action is None else asdict(self.last_action),
                "observed_tick": self._observed_tick, "acted_tick": self._acted_tick}


class UnknownPoolCoordinator(PoolCoordinator):
    """A1's same observed-endpoint union, updated with a joint unknown-rate law.

The inherited extraction projection reads only the preceding tick and total
site harvest. All site stocks come from legal packets; site capacities and
weather never enter the posterior. The shared rate is inferred, not supplied.
    """

    def __init__(self, *, grid_size=400, rate_bins=32, rate_order=8):
        super().__init__()
        self.joint = JointPosterior(biased=False, grid_size=grid_size,
                                    rate_bins=rate_bins, rate_order=rate_order)

    def _posterior(self, site):
        if site not in self.posteriors:
            self.posteriors[site] = self.joint.site(site)
        return self.posteriors[site]

    def prepare(self, packets, previous_result=None):
        if type(packets) not in (tuple, list) or not packets:
            raise ValueError("one legal observation per individual is required")
        current, visible = [], {}
        for identity, packet in enumerate(packets):
            validate_ecology(packet)
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
            if harvested > old + 8 * math.ulp(max(1., old)):
                raise ValueError("total extraction exceeds observed site stock")
            z = max(0., old - harvested)
            if stocks[site] < z:
                raise ValueError("observed growth is negative after total extraction")
            growth.append(GrowthEvidence(site, tick - 1, z, stocks[site]))
        updates = []
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
        return {"version": VERSION, "role": "pooled_joint", "tick": self.tick,
                "joint": self.joint.memory(), "posterior_sites": sorted(self.posteriors),
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "packets": deepcopy(self._packets),
                "stocks": [[site, stock] for site, stock in sorted(self._stocks.items())],
                "last_extraction": [[site, value] for site, value in sorted(self._last_extraction.items())],
                "transition_sites": list(self._transition_sites)}


class UnknownPoolForager(PoolForager):
    """Unchanged capacity-injection decision rule with shared joint beliefs."""

    def __init__(self, coordinator, agent_id, *, phi=.375, q=.25):
        if not isinstance(coordinator, UnknownPoolCoordinator):
            raise ValueError("an UnknownPoolCoordinator is required")
        _decision_parameters(phi, q)
        super().__init__(coordinator, agent_id, phi=phi, q=q)
        self.joint = coordinator.joint

    def observe(self, observation):
        validate_ecology(observation)
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

    def memory(self):
        return {"version": VERSION, "arm": self.arm, "agent_id": self.agent_id,
                "phi": self.phi, "q": self.q, "biased": False,
                "joint": self.joint.memory(), "posterior_sites": sorted(self.posteriors),
                "forager": ForagerPolicy.memory(self),
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "last_action": None if self.last_action is None else asdict(self.last_action),
                "observed_tick": self._observed_tick, "acted_tick": self._acted_tick}
