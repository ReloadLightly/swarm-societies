"""Local diagnostic policies v2: preserve a numerical return-fuel margin.

Memory contains only visited cells and site coordinates actually observed.
The two modes share navigation and budget rules. Neither is claimed to be an
optimal controller or the strong baseline matrix required before evolution.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .engine import Action


class LocalPolicy:
    def __init__(self, mode: str):
        if mode not in ("greedy", "restraint"):
            raise ValueError("unknown local policy")
        self.mode = mode
        self.sites: dict[int, tuple[int, int]] = {}
        self.visits: dict[tuple[int, int], int] = {}

    def memory(self) -> dict[str, Any]:
        return {"version": "commons-v3-local-policy-v2", "mode": self.mode,
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
            # Pay for the path back to a known resource, plus a small scouting
            # buffer. Withholding is costly when it creates unmet need.
            required = cost * max(4, home_distance(point) + 1)
            # The v1 exact-budget boundary could become unaffordable after
            # repeated floating subtraction. Retain a prospective numerical
            # buffer; the engine still charges every movement in full.
            margin = 1e-9 * max(1., required) if cost else 0.
            return min(me["inventory_capacity"], required + 8 * margin)

        def request(site, inventory):
            available = site["stock"]
            if self.mode == "restraint":
                available = max(0., available - .5 * site["capacity"]) / max(1, site["peer_count"])
            # Overflow precedes consumption, so do not count this tick's need
            # as already free storage. The engine still permits deliberate waste.
            headroom = max(0., me["inventory_capacity"] - inventory)
            return min(me["max_harvest"], available, headroom / conversion)

        current = next((p for p in observation["sites"] if (p["x"], p["y"]) == position), None)
        if me["inventory"] >= me["inventory_capacity"] - 1e-12:
            return Action(reserve=reserve(position))

        candidates = []
        for site in observation["sites"]:
            target = site["x"], site["y"]
            dist = distance(position, target)
            if dist > 1 or (dist and me["inventory"] < cost):
                continue
            amount = request(site, me["inventory"] - cost * dist)
            expected = min(amount, site["stock"] / max(1, site["peer_count"])) * conversion
            candidates.append((expected - cost * dist, -dist, -site["id"], site))
        if candidates:
            score, _, _, target = max(candidates, key=lambda row: row[:3])
            if score >= .5 * me["need"] and score > 0:
                destination = target["x"], target["y"]
                if destination == position:
                    return Action(harvest=request(target, me["inventory"]), reserve=reserve(position))
                return Action(move=(destination[0] - position[0], destination[1] - position[1]),
                              reserve=reserve(destination))

        # Scout less-visited local cells. Never knowingly spend the fuel needed
        # to return to the nearest previously observed site. No remote stock
        # estimate or hidden layout enters this choice.
        moves = []
        if me["inventory"] >= cost:
            for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                target = position[0] + dx, position[1] + dy
                if not (0 <= target[0] < me["width"] and 0 <= target[1] < me["height"]):
                    continue
                required = cost * (1 + home_distance(target))
                margin = 1e-9 * max(1., required) if cost else 0.
                if required + margin > me["inventory"]:
                    continue
                tie = hashlib.sha256(f"{me['id']}:{observation['tick']}:{target}".encode()).hexdigest()
                moves.append((self.visits.get(target, 0), tie, (dx, dy), target))
        if moves:
            _, _, move, target = min(moves)
            return Action(move=move, reserve=reserve(target))
        return Action(harvest=request(current, me["inventory"]) if current else 0.,
                      reserve=reserve(position))
