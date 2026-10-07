"""Need-targeted local baselines with zero or two ticks of resource buffer.

These prospective development policies share v2's observed-site memory,
return-fuel arithmetic, candidate ranking and scouting. They change requested
yield, the candidate acceptance threshold and the decision to wait when fed.
They are therefore policy-bundle comparisons, not pure extraction interventions
or claims of strong navigation. No ecological law or remote stock is known.

The target includes this tick's need, an optional resource buffer, and fuel.
Only fuel is withheld from consumption: unmet need may consume the entire
resource buffer. As in v2, moving toward a visible site does not also harvest
on the movement tick, although candidate ranking uses its anticipated yield.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .engine import Action


class NeedTargetPolicy:
    def __init__(self, reserve_ticks: int = 0):
        if type(reserve_ticks) is not int or reserve_ticks not in (0, 2):
            raise ValueError("reserve_ticks must be zero or two")
        self.reserve_ticks = reserve_ticks
        self.mode = "need_target"
        self.sites: dict[int, tuple[int, int]] = {}
        self.visits: dict[tuple[int, int], int] = {}

    def memory(self) -> dict[str, Any]:
        return {"version": "commons-v3-need-target-policy-v1", "mode": self.mode,
                "reserve_ticks": self.reserve_ticks,
                "sites": [[key, *value] for key, value in sorted(self.sites.items())],
                "visits": [[*key, value] for key, value in sorted(self.visits.items())]}

    def __call__(self, observation: dict[str, Any]) -> Action:
        me = observation["self"]
        position = me["x"], me["y"]
        self.visits[position] = self.visits.get(position, 0) + 1
        for site in observation["sites"]:
            self.sites[site["id"]] = site["x"], site["y"]
        cost = me["movement_cost"]
        conversion = 1 - me["harvest_cost_per_unit"]

        def distance(left, right):
            return abs(left[0] - right[0]) + abs(left[1] - right[1])

        def home_distance(point):
            return min((distance(point, p) for p in self.sites.values()), default=0)

        def reserve(point):
            # Exactly v2's paid return/scouting reserve and prospective margin.
            required = cost * max(4, home_distance(point) + 1)
            margin = 1e-9 * max(1., required) if cost else 0.
            return min(me["inventory_capacity"], required + 8 * margin)

        def target(point):
            return min(me["inventory_capacity"],
                       me["need"] * (1 + self.reserve_ticks) + reserve(point))

        def request(site, inventory):
            desired = target((site["x"], site["y"]))
            deficit = max(0., desired - inventory)
            # Overflow occurs before consumption. Both the target and gross
            # request honor physical storage; the target does not change it.
            headroom = max(0., me["inventory_capacity"] - inventory)
            return min(me["max_harvest"], site["stock"],
                       deficit / conversion, headroom / conversion)

        current = next((p for p in observation["sites"]
                        if (p["x"], p["y"]) == position), None)
        fuel = reserve(position)
        if me["inventory"] >= target(position):
            return Action(reserve=fuel)

        # Inventory that already covers part of today's need makes a small
        # positive top-up useful. The buffer is not a consumption withholding.
        consumable = max(0., me["inventory"] - fuel)
        threshold = min(.5 * me["need"], max(0., me["need"] - consumable),
                        max(0., target(position) - me["inventory"]))
        candidates = []
        for site in observation["sites"]:
            destination = site["x"], site["y"]
            dist = distance(position, destination)
            if dist > 1 or (dist and me["inventory"] < cost):
                continue
            amount = request(site, me["inventory"] - cost * dist)
            expected = min(amount, site["stock"] / max(1, site["peer_count"])) * conversion
            candidates.append((expected - cost * dist, -dist, -site["id"], site))
        if candidates:
            score, _, _, chosen = max(candidates, key=lambda row: row[:3])
            if score >= threshold and score > 0:
                destination = chosen["x"], chosen["y"]
                if destination == position:
                    return Action(harvest=request(chosen, me["inventory"]), reserve=fuel)
                return Action(move=(destination[0] - position[0], destination[1] - position[1]),
                              reserve=reserve(destination))

        # Draw down an available resource buffer on a poor harvest tick before
        # scouting. In particular, being below the optional buffer target does
        # not force a fully fed actor to leave its current site.
        if consumable >= me["need"]:
            return Action(harvest=request(current, me["inventory"]) if current else 0.,
                          reserve=fuel)

        # v2's least-visited feasible local scouting and deterministic tie break.
        moves = []
        if me["inventory"] >= cost:
            for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                destination = position[0] + dx, position[1] + dy
                if not (0 <= destination[0] < me["width"] and 0 <= destination[1] < me["height"]):
                    continue
                required = cost * (1 + home_distance(destination))
                margin = 1e-9 * max(1., required) if cost else 0.
                if required + margin > me["inventory"]:
                    continue
                tie = hashlib.sha256(f"{me['id']}:{observation['tick']}:{destination}".encode()).hexdigest()
                moves.append((self.visits.get(destination, 0), tie, (dx, dy), destination))
        if moves:
            _, _, move, destination = min(moves)
            return Action(move=move, reserve=reserve(destination))
        return Action(harvest=request(current, me["inventory"]) if current else 0.,
                      reserve=fuel)
