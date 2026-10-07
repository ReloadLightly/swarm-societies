"""Asocial capacity learning behind the unchanged navigation forager.

The wrapper learns only from its own legal stock observations and clean
transitions. It supplies posterior capacity quantiles to the frozen controller;
it does not parse messages, inspect evaluator state, or change navigation.
The default quantile is an untuned implementation default, not a selection.
"""

from __future__ import annotations

from typing import Any

from .engine import Action
from .evidence_sites_v1 import LocalEvidence
from .policies_navigation_v1 import ForagerPolicy
from .posterior_sites_v1 import HIGH, LOW, RATE, RECOVERY, WHIGH, WLOW, SitePosterior


VERSION = "commons-v3-asocial-forager-sites-v1"


def _validate_ecology(observation: dict[str, Any]) -> None:
    """Check the declared model, never the world's hidden realization."""
    ecology = observation.get("ecology")
    if type(ecology) is not dict:
        raise ValueError("the known ecological law must be declared")
    for key, expected in (("renewal_law", "logistic"), ("renewal_rate", RATE), ("recovery", RECOVERY)):
        if ecology.get(key) != expected:
            raise ValueError(f"unsupported declared ecology: {key}")
    declarations = {
        "weather_multiplier": {"distribution": "uniform", "low": WLOW, "high": WHIGH},
        "capacity_prior": {"distribution": "log_uniform", "low": LOW, "high": HIGH},
        "initial_stock_fraction": {"distribution": "uniform", "low": .3, "high": .9,
                                   "independent_by_site": True},
    }
    for name, expected in declarations.items():
        actual = ecology.get(name)
        if type(actual) is not dict or any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError(f"unsupported declared ecology: {name}")


class AsocialForager(ForagerPolicy):
    """L0 with own clean evidence and a fixed posterior-quantile decision rule."""

    def __init__(self, *, phi: float = .375, q: float = .5, grid_size: int = 400):
        if type(phi) not in (int, float) or phi not in (.375, .5):
            raise ValueError("phi must be 0.375 or 0.5")
        if type(q) not in (int, float) or q not in (.25, .5):
            raise ValueError("q must be 0.25 or 0.5")
        if type(grid_size) is not int or grid_size < 16:
            raise ValueError("grid_size must be at least 16")
        super().__init__(reserve_ticks=2, stock_floor_fraction=.5,
                         route_mode="net_yield", aggressive=False)
        self.phi, self.q, self.grid_size = float(phi), float(q), grid_size
        self.posteriors: dict[int, SitePosterior] = {}
        self.evidence = LocalEvidence()
        self.last_action: Action | None = None

    def _posterior(self, site_id: int) -> SitePosterior:
        if site_id not in self.posteriors:
            self.posteriors[site_id] = SitePosterior(site_id, self.grid_size)
        return self.posteriors[site_id]

    def __call__(self, observation: dict[str, Any]) -> Action:
        if type(observation) is not dict:
            raise ValueError("expected a legal local observation")
        _validate_ecology(observation)
        batch = self.evidence.observe(observation, self.last_action)
        if batch.reason == "repeated_observation" and self.last_action is not None:
            return self.last_action
        # The likelihood includes the next-stock bound and can create an atom
        # at that stock. Consume it before applying the redundant new bound.
        for transition in batch.transitions:
            self._posterior(transition.site).update(transition)
        for bound in batch.bounds:
            self._posterior(bound.site).observe_stock(bound.stock)
        known_ids = set(self.records) | {site["id"] for site in observation["sites"]}
        capacities = {site_id: (self.phi / .5) * self.posteriors[site_id].quantile(self.q)
                      for site_id in known_ids}
        packet = {**observation,
                  "sites": [{**site, "capacity": capacities[site["id"]]}
                            for site in observation["sites"]]}
        for site_id, record in self.records.items():
            record["capacity"] = capacities[site_id]
        self.last_action = super().__call__(packet)
        return self.last_action

    def memory(self) -> dict[str, Any]:
        action = self.last_action
        last_action = None if action is None else {
            "move": list(action.move), "harvest": action.harvest,
            "transfers": [list(pair) for pair in action.transfers],
            "messages": [list(pair) for pair in action.messages], "reserve": action.reserve}
        return {"version": VERSION, "phi": self.phi, "q": self.q, "grid_size": self.grid_size,
                "forager": super().memory(), "evidence": self.evidence.memory(),
                "posteriors": [posterior.memory() for _, posterior in sorted(self.posteriors.items())],
                "last_action": last_action}
