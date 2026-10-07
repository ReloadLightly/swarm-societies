"""Capacity-injection references for the site-capacity consequence map.

These wrappers retain the frozen navigation forager's decisions and memory.
Only capacity beliefs are supplied; no learner or new navigation rule lives
here. The oracle receives privileged capacities, but discovers coordinates and
site identities only through the same local packets as the other references.
"""

from __future__ import annotations

import math
from typing import Any

from .engine import Action
from .policies_navigation_v1 import ForagerPolicy


VERSION = "commons-v3-reference-forager-sites-v1"


class ReferenceForager(ForagerPolicy):
    """Frozen reserve-2/net-yield forager with an explicit capacity reference.

For oracle and fixed references, multiplying the supplied capacity by phi/0.5
implements the requested effective floor without changing the frozen forager.
The greedy reference uses its native zero-floor branch: merely injecting zero
capacity would retain a different crowd adjustment in the positive-floor branch.

Inherited ``memory()`` records the frozen controller's full decision memory.
Construction parameters belong to the caller's case definition; this wrapper
does not introduce a checkpoint or execute a serialized policy definition.
"""

    def __init__(self, arm: str, *, phi: float = .5,
                 fixed_capacity: float | None = None,
                 true_capacities: tuple[float, ...] | None = None):
        if type(arm) is not str or arm not in ("R-oracle", "R-fixed", "R-greedy"):
            raise ValueError("unknown reference arm")
        if type(phi) not in (int, float) or phi not in (.375, .5):
            raise ValueError("phi must be 0.375 or 0.5")
        if arm == "R-oracle":
            if fixed_capacity is not None:
                raise ValueError("R-oracle does not accept a fixed capacity")
            if type(true_capacities) is not tuple or not 1 <= len(true_capacities) <= 4096:
                raise ValueError("R-oracle requires an immutable capacity tuple")
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   or not 0 < value <= 1e6 for value in true_capacities):
                raise ValueError("true capacities must be finite and positive")
        elif arm == "R-fixed":
            if true_capacities is not None:
                raise ValueError("R-fixed cannot receive true capacities")
            if type(fixed_capacity) not in (int, float) or fixed_capacity not in (20, 30, 40):
                raise ValueError("fixed capacity must be 20, 30 or 40")
        elif fixed_capacity is not None or true_capacities is not None:
            raise ValueError("R-greedy does not accept a capacity parameter")
        self.arm = arm
        self.phi = float(phi)
        self.fixed_capacity = float(fixed_capacity) if fixed_capacity is not None else None
        self.true_capacities = true_capacities
        super().__init__(reserve_ticks=2,
                         stock_floor_fraction=0. if arm == "R-greedy" else .5,
                         route_mode="net_yield", aggressive=False)

    def _capacity_for(self, site_id: int) -> float:
        if type(site_id) is not int or site_id < 0:
            raise ValueError("site IDs must be nonnegative integers")
        if self.arm == "R-greedy":
            return 40.
        if self.arm == "R-oracle":
            if site_id >= len(self.true_capacities):
                raise ValueError("observed site ID is outside oracle capacities")
            capacity = self.true_capacities[site_id]
        else:
            capacity = self.fixed_capacity
        return (self.phi / .5) * capacity

    def __call__(self, observation: dict[str, Any]) -> Action:
        # Prepare all lookups before changing remembered records. The oracle
        # never creates a record, coordinate or route for an unseen site.
        visible = observation["sites"]
        known_ids = set(self.records) | {site["id"] for site in visible}
        capacities = {site_id: self._capacity_for(site_id) for site_id in known_ids}
        packet = {**observation,
                  "sites": [{**site, "capacity": capacities[site["id"]]} for site in visible]}
        for site_id, record in self.records.items():
            record["capacity"] = capacities[site_id]
        return super().__call__(packet)
