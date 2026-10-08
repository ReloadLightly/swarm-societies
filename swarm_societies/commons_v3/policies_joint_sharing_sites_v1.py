"""A2 local sharing with one unknown rate shared by each agent's site beliefs.

The frozen Ticket D controller supplies navigation, truthful message contents,
receipt timing and matched L2/L3 byte schedules. Only its inference owner and
ecological declaration change: each individual has one private JointPosterior,
and site beliefs are marginal views of that joint law. No true rate is supplied.
"""
from copy import deepcopy
from dataclasses import asdict

from .observations_joint_sites_v1 import validate_ecology
from .policies_joint_sites_v1 import _decision_parameters
from .policies_navigation_v1 import ForagerPolicy
from .policies_sharing_sites_v1 import LearningForager
from .posterior_joint_sites_v1 import JointPosterior


VERSION = "commons-v3-unknown-rate-sharing-forager-v1"


class UnknownSharingForager(LearningForager):
    """L1 receipts, L2 event relay, or L3 naive marginal-belief multiplication.

Biased L2/L3 members use the approved capacity-prior mixture at every site;
their shared rate keeps the same LogUniform[.12,.48] prior as other members.
"""

    def __init__(self, arm, *, phi=.375, q=.25, biased=False,
                 grid_size=400, rate_bins=32, rate_order=8):
        if arm not in ("L1", "L2", "L3"):
            raise ValueError("unknown-rate sharing requires L1, L2 or L3")
        _decision_parameters(phi, q)
        super().__init__(arm, phi=phi, q=q, biased=biased)
        self.joint = JointPosterior(biased=biased, grid_size=grid_size,
                                    rate_bins=rate_bins, rate_order=rate_order)

    def _posterior(self, site):
        if site not in self.posteriors:
            self.posteriors[site] = self.joint.site(site)
        return self.posteriors[site]

    def observe(self, observation):
        """Apply each physical event once, then bounds, then naive L3 fusion."""
        validate_ecology(observation)
        tick = observation["tick"]
        if tick == self._observed_tick:
            # Retain conflicting-packet checks without replaying inference.
            self.evidence.observe(observation, self.last_action)
            return
        batch = self.evidence.observe(observation, self.last_action)
        self.last_updates = []
        for key, value in self.evidence.counters.items():
            self.counters[key] = value
        for event in batch.growth:
            if self._posterior(event.site).update_event(event):
                self.events[(event.site, event.tick)] = event
                self.last_updates.append({"kind": "growth", **asdict(event)})
        # Clipping creates capacity atoms, so likelihoods precede redundant
        # endpoint bounds. Every factor updates the same shared-rate belief.
        for bound in batch.bounds:
            if self._posterior(bound.site).observe_stock(bound.stock):
                self.last_updates.append({"kind": "bound", **asdict(bound)})
        if self.arm == "L3":
            for sender, summary in batch.beliefs:
                self._posterior(summary.site).fuse(summary.median, summary.iqr)
                self.last_updates.append({"kind": "belief", "sender": sender,
                                          **asdict(summary)})
        self._observed_tick = tick

    def memory(self):
        """Canonical detached state, storing the joint law only once."""
        return {"version": VERSION, "arm": self.arm, "phi": self.phi, "q": self.q,
                "biased": self.biased, "joint": self.joint.memory(),
                "forager": ForagerPolicy.memory(self), "evidence": self.evidence.memory(),
                "posterior_sites": sorted(self.posteriors),
                "events": [asdict(event) for _, event in sorted(self.events.items())],
                "counters": dict(self.counters), "last_updates": deepcopy(self.last_updates),
                "last_action": None if self.last_action is None else asdict(self.last_action),
                "observed_tick": self._observed_tick, "acted_tick": self._acted_tick,
                "sent_events": [list(key) for key in sorted(self._sent_events)],
                "belief_cursor": sorted(self._belief_cursor.items())}
