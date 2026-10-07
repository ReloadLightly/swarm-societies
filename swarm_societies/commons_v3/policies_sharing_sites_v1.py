"""Ticket D learning regimes behind the frozen reserve-2 navigation rule.

Only paid engine messages transfer peer information. Private feedback contains
the observer's own harvest; L0 deliberately retains its solitary-transition
rule. Capacity priors and fusion follow the approved contract section 17.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace

from .evidence_sites_v1 import LocalEvidence
from .evidence_receipts_sites_v1 import ReceiptEvidence
from .messages_sites_v1 import (BeliefSummary, GrowthEvidence, schedule_messages,
                                social_recipient)
from .policies_learning_sites_v1 import _validate_ecology
from .policies_navigation_v1 import ForagerPolicy
from .posterior_social_sites_v1 import SocialSitePosterior

VERSION = "commons-v3-sharing-forager-sites-v1"
COUNTERS = ("eligible", "clean_own", "clean_receipts", "new_relay", "duplicates",
            "confounded", "belief_messages", "attempted_messages", "attempted_bytes")


def new_prior(site=0, biased=False):
    """Also usable by the evaluator for untouched, unseen-site priors."""
    return SocialSitePosterior(site=site, biased=biased, grid_size=400)


class LearningForager(ForagerPolicy):
    def __init__(self, arm, *, q=.5, phi=.375, biased=False):
        if arm not in ("L0", "L1", "L2", "L3"):
            raise ValueError("unknown learning regime")
        if type(q) not in (int, float) or q not in (.25, .5):
            raise ValueError("q must be 0.25 or 0.5")
        if type(phi) not in (int, float) or phi != .375:
            raise ValueError("Ticket B selected phi=0.375")
        if type(biased) is not bool or (biased and arm not in ("L2", "L3")):
            raise ValueError("biased agents belong only to L2/L3 variants")
        super().__init__(reserve_ticks=2, stock_floor_fraction=.5, route_mode="net_yield", aggressive=False)
        self.arm, self.q, self.phi, self.biased = arm, float(q), float(phi), biased
        self.posteriors = {}
        self.evidence = (LocalEvidence() if arm == "L0" else
                         ReceiptEvidence(accept_relay=arm == "L2", accept_beliefs=arm == "L3"))
        self.events = {}
        self.counters = dict.fromkeys(COUNTERS, 0)
        self.last_updates = []
        self.last_action = None
        self._observed_tick = self._acted_tick = None
        self._sent_events = set()
        self._belief_cursor = {}

    def _posterior(self, site):
        if site not in self.posteriors:
            self.posteriors[site] = new_prior(site, self.biased)
        return self.posteriors[site]

    def observe(self, observation):
        """Ingest evidence without taking a decision (including final tick512)."""
        if type(observation) is not dict:
            raise ValueError("expected a legal local observation")
        _validate_ecology(observation)
        tick = observation["tick"]
        if tick == self._observed_tick:
            # Retain the extractor's conflicting-local-packet checks while
            # leaving the already counted inference and decision unchanged.
            self.evidence.observe(observation, self.last_action)
            return
        batch = self.evidence.observe(observation, self.last_action)
        self.last_updates = []
        if self.arm == "L0":
            if batch.reason in ("clean", "shared"):
                self.counters["eligible"] += 1
            self.counters["confounded"] += int(batch.reason == "shared")
            growth = tuple(GrowthEvidence(t.site, t.tick, t.z, t.stock_next) for t in batch.transitions)
            self.counters["clean_own"] += len(growth)
            beliefs = ()
        else:
            growth, beliefs = batch.growth, batch.beliefs
            for key, value in self.evidence.counters.items():
                self.counters[key] = value
        for event in growth:
            if self._posterior(event.site).update_event(event):
                self.events[(event.site, event.tick)] = event
                self.last_updates.append({"kind": "growth", **asdict(event)})
        # Clean likelihood first, then the redundant current-stock bounds.
        for bound in batch.bounds:
            if self._posterior(bound.site).observe_stock(bound.stock):
                self.last_updates.append({"kind": "bound", **asdict(bound)})
        if self.arm == "L3":
            for sender, summary in beliefs:
                self._posterior(summary.site).fuse(summary.median, summary.iqr)
                self.last_updates.append({"kind": "belief", "sender": sender, **asdict(summary)})
        self._observed_tick = tick

    def _social_content(self, observation, recipient):
        if recipient is None:
            return None
        if self.arm == "L2":
            available = [event for key, event in self.events.items()
                         if (recipient, *key) not in self._sent_events]
            return min(available, key=lambda e: (e.tick, e.site)) if available else None
        if self.arm == "L3" and self.posteriors:
            sites = sorted(self.posteriors)
            site = sites[self._belief_cursor.get(recipient, 0) % len(sites)]
            posterior = self.posteriors[site]
            return BeliefSummary(site, posterior.quantile(.5),
                                 posterior.quantile(.75) - posterior.quantile(.25))
        return None

    def __call__(self, observation):
        self.observe(observation)
        if self._acted_tick == observation["tick"]:
            return self.last_action
        known_ids = set(self.records) | {site["id"] for site in observation["sites"]}
        capacities = {site: (self.phi / .5) * self.posteriors[site].quantile(self.q) for site in known_ids}
        packet = {**observation, "sites": [{**site, "capacity": capacities[site["id"]]}
                                          for site in observation["sites"]]}
        for site, record in self.records.items():
            record["capacity"] = capacities[site]
        action = super().__call__(packet)
        if self.arm != "L0":
            recipient = social_recipient(observation) if self.arm in ("L2", "L3") else None
            social = self._social_content(observation, recipient)
            messages = schedule_messages(observation, arm=self.arm,
                                         receipt=self.evidence.own_receipt,
                                         cohort=self.evidence.cohort, social=social)
            action = replace(action, messages=messages)
            self.counters["attempted_messages"] += len(messages)
            self.counters["attempted_bytes"] += sum(len(text.encode("utf-8")) for _, text in messages)
            if recipient is not None and any(peer == recipient for peer, _ in messages):
                if self.arm == "L2" and social is not None:
                    self._sent_events.add((recipient, social.site, social.tick))
                elif self.arm == "L3" and social is not None:
                    self._belief_cursor[recipient] = self._belief_cursor.get(recipient, 0) + 1
        self.last_action = action
        self._acted_tick = observation["tick"]
        return action

    def memory(self):
        return {"version": VERSION, "arm": self.arm, "phi": self.phi, "q": self.q,
                "biased": self.biased, "forager": super().memory(), "evidence": self.evidence.memory(),
                "posteriors": [p.memory() for _, p in sorted(self.posteriors.items())],
                "events": [asdict(event) for _, event in sorted(self.events.items())],
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "last_action": None if self.last_action is None else asdict(self.last_action),
                "observed_tick": self._observed_tick, "acted_tick": self._acted_tick,
                "sent_events": [list(key) for key in sorted(self._sent_events)],
                "belief_cursor": sorted(self._belief_cursor.items())}
