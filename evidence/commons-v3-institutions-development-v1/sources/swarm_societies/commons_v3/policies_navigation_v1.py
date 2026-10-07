"""Observed-map foraging controls, separately versioned from frozen baselines.

This deterministic heuristic uses remembered observations, purposeful routes,
new sensing coverage and periodic reinspection. It does not know renewal,
weather, remote changes, initialization geometry or other agents' intentions.
Its stock floor restrains individual requests; it cannot guarantee a global
floor when unobserved agents arrive simultaneously. Aggressive comparisons
change both the inventory target and that request restraint, so are bundles.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .engine import Action


REVISIT_TICKS = 8
FRESHNESS_TICKS = 8


def _distance(left, right):
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


class ForagerPolicy:
    def __init__(self, reserve_ticks: int = 2, stock_floor_fraction: float = 0.,
                 route_mode: str = "net_yield", aggressive: bool = False):
        if type(reserve_ticks) is not int or reserve_ticks not in (0, 2, 4):
            raise ValueError("reserve_ticks must be zero, two or four")
        if type(stock_floor_fraction) not in (int, float) or stock_floor_fraction not in (0., .25, .5):
            raise ValueError("stock_floor_fraction must be zero, one-quarter or one-half")
        if route_mode not in ("nearest", "net_yield"):
            raise ValueError("route_mode must be nearest or net_yield")
        if type(aggressive) is not bool:
            raise ValueError("aggressive must be boolean")
        self.reserve_ticks = reserve_ticks
        self.stock_floor_fraction = float(stock_floor_fraction)
        self.route_mode = route_mode
        self.aggressive = aggressive
        self.sites: dict[int, tuple[int, int]] = {}
        self.records: dict[int, dict[str, Any]] = {}
        self.seen: set[tuple[int, int]] = set()
        self.visits: dict[tuple[int, int], int] = {}
        self.destination: tuple[int, int] | None = None
        self.destination_kind: str | None = None

    def memory(self) -> dict[str, Any]:
        return {"version": "commons-v3-forager-policy-v1", "mode": "observed_map_forager",
                "reserve_ticks": self.reserve_ticks, "stock_floor_fraction": self.stock_floor_fraction,
                "route_mode": self.route_mode, "aggressive": self.aggressive,
                "sites": [[i, *point] for i, point in sorted(self.sites.items())],
                "records": [{"id": i, **record} for i, record in sorted(self.records.items())],
                "seen": [list(point) for point in sorted(self.seen)],
                "visits": [[*point, count] for point, count in sorted(self.visits.items())],
                "destination": list(self.destination) if self.destination is not None else None,
                "destination_kind": self.destination_kind}

    @staticmethod
    def _footprint(me, point):
        radius = me["sensing_radius"]
        for x in range(max(0, point[0] - radius), min(me["width"], point[0] + radius + 1)):
            reach = radius - abs(x - point[0])
            for y in range(max(0, point[1] - reach), min(me["height"], point[1] + reach + 1)):
                yield x, y

    def _home_distance(self, point):
        return min((_distance(point, site) for site in self.sites.values()), default=0)

    @staticmethod
    def _margin(required, cost):
        return 1e-9 * max(1., required) if cost else 0.

    def _fuel(self, me, point, goal=None):
        steps = max(4, self._home_distance(point) + 1)
        if goal is not None:
            steps = max(steps, _distance(point, goal) + self._home_distance(goal) + 1)
        required = me["movement_cost"] * steps
        return min(me["inventory_capacity"], required + 8 * self._margin(required, me["movement_cost"]))

    def _target(self, me, point, goal=None):
        if self.aggressive:
            return me["inventory_capacity"]
        return min(me["inventory_capacity"], me["need"] * (1 + self.reserve_ticks) + self._fuel(me, point, goal))

    def _crowd(self, site_id):
        record = self.records[site_id]
        # The last headcount includes this observer only when it was on-site.
        # Other agents' future positions and requests remain unknown.
        return max(1, record["peer_count"] - int(record["self_present"]) + 1)

    def _available(self, site_id):
        record = self.records[site_id]
        floor = 0. if self.aggressive else self.stock_floor_fraction
        return max(0., record["stock"] - floor * record["capacity"])

    def _service(self, me, site_id, tick, *, discount=False):
        amount = min(me["max_harvest"], self._available(site_id) / self._crowd(site_id))
        net = amount * (1 - me["harvest_cost_per_unit"])
        if discount:
            net /= 1 + (tick - self.records[site_id]["tick"]) / FRESHNESS_TICKS
        return net

    def _request(self, me, site_id, inventory, point, goal=None):
        if site_id is None:
            return 0.
        available = self._available(site_id)
        if self.stock_floor_fraction and not self.aggressive:
            available /= self._crowd(site_id)
        conversion = 1 - me["harvest_cost_per_unit"]
        deficit = max(0., self._target(me, point, goal) - inventory)
        headroom = max(0., me["inventory_capacity"] - inventory)
        return min(me["max_harvest"], available, deficit / conversion, headroom / conversion)

    def _novelty(self, me, point):
        return sum(cell not in self.seen for cell in self._footprint(me, point))

    @staticmethod
    def _tie(me, kind, point):
        # No tick in a committed route's tie: equal paths do not alternate.
        return hashlib.sha256(f"{me['id']}:{kind}:{point}".encode()).hexdigest()

    def _feasible_goal(self, me, position, goal):
        distance = _distance(position, goal)
        if distance == 0:
            return False
        cost = me["movement_cost"]
        if distance == 1 and goal in self.sites.values():
            return me["inventory"] >= cost
        required = cost * (distance + self._home_distance(goal))
        return me["inventory"] >= required + self._margin(required, cost)

    def _safe_step(self, me, point):
        cost = me["movement_cost"]
        if me["inventory"] < cost:
            return False
        if point in self.sites.values():
            return True
        required = cost * (1 + self._home_distance(point))
        return me["inventory"] >= required + self._margin(required, cost)

    def _can_provision_goal(self, me, position, goal):
        if position not in self.sites.values() or goal not in self.sites.values() or goal == position:
            return False
        required = me["movement_cost"] * (_distance(position, goal) + self._home_distance(goal))
        return me["inventory_capacity"] >= required + self._margin(required, me["movement_cost"])

    def _clear(self):
        self.destination = self.destination_kind = None

    def _choose_goal(self, me, tick, position, current_service):
        routes = []
        for site_id, point in self.sites.items():
            if not (self._feasible_goal(me, position, point) or self._can_provision_goal(me, position, point)):
                continue
            service = self._service(me, site_id, tick, discount=True)
            if service <= current_service:
                continue
            distance = _distance(position, point)
            score = (service - me["movement_cost"] * distance) / (distance + 1)
            key = (distance, -service) if self.route_mode == "nearest" else (-score, distance)
            routes.append((*key, self._tie(me, "site", point), point))
        if routes:
            return min(routes)[-1], "site"

        # A frontier is defined solely by observed coverage. Candidate cells
        # are observed cells and their immediate neighbors, not inferred sites.
        frontier_cells = set(self.seen)
        for x, y in self.seen:
            for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                if 0 <= x + dx < me["width"] and 0 <= y + dy < me["height"]:
                    frontier_cells.add((x + dx, y + dy))
        frontiers = []
        for point in frontier_cells:
            if not self._feasible_goal(me, position, point):
                continue
            information = self._novelty(me, point)
            if information:
                distance = _distance(position, point)
                frontiers.append((-information / distance, distance, self.visits.get(point, 0),
                                  self._tie(me, "frontier", point), point))
        if frontiers:
            return min(frontiers)[-1], "frontier"

        revisits = []
        for site_id, point in self.sites.items():
            age = tick - self.records[site_id]["tick"]
            if age >= REVISIT_TICKS and self._feasible_goal(me, position, point):
                revisits.append((-age, _distance(position, point), self._tie(me, "revisit", point), point))
        if revisits:
            return min(revisits)[-1], "revisit"
        returns = [(_distance(position, point), self._tie(me, "return", point), point)
                   for point in self.sites.values() if self._feasible_goal(me, position, point)]
        if position not in self.sites.values() and returns:
            return min(returns)[-1], "return"
        return None, None

    def __call__(self, observation: dict[str, Any]) -> Action:
        me, tick = observation["self"], observation["tick"]
        position = me["x"], me["y"]
        self.visits[position] = self.visits.get(position, 0) + 1
        self.seen.update(self._footprint(me, position))
        for site in observation["sites"]:
            point = site["x"], site["y"]
            self.sites[site["id"]] = point
            self.records[site["id"]] = {"stock": site["stock"], "capacity": site["capacity"],
                "peer_count": site["peer_count"], "tick": tick, "self_present": position == point}
        site_at = {point: site_id for site_id, point in self.sites.items()}
        current = site_at.get(position)
        current_service = self._service(me, current, tick) if current is not None else 0.

        if self.destination == position:
            self._clear()
        if self.destination is not None:
            target_id = site_at.get(self.destination)
            newly_inspected = target_id is not None and self.records[target_id]["tick"] == tick
            if (self.destination_kind == "frontier" and self._novelty(me, self.destination) == 0
                    or self.destination_kind == "revisit" and newly_inspected
                    or self.destination_kind == "site" and newly_inspected
                       and self._service(me, target_id, tick) <= current_service
                    or not (self._feasible_goal(me, position, self.destination)
                            or self.destination_kind == "site"
                               and self._can_provision_goal(me, position, self.destination))):
                self._clear()

        # A replenishable-looking current opportunity needs no travel. The
        # one-tick opportunity is a heuristic, not a learned sustainable yield.
        if current is not None and current_service > 0 and current_service >= me["need"]:
            self._clear()
            return Action(harvest=self._request(me, current, me["inventory"], position),
                          reserve=self._fuel(me, position))
        if self.destination is None and me["inventory"] >= self._target(me, position):
            return Action(reserve=self._fuel(me, position))

        if self.destination is None:
            self.destination, self.destination_kind = self._choose_goal(me, tick, position, current_service)
        if self.destination is not None:
            if not self._feasible_goal(me, position, self.destination):
                # A known better site may need more than the four-step base
                # reserve. Pay for that route from current harvest before
                # leaving; only route fuel is withheld, with any resulting
                # consumption shortfall recorded by the unchanged engine.
                return Action(harvest=self._request(me, current, me["inventory"], position, self.destination),
                              reserve=self._fuel(me, position, self.destination))
            remaining = _distance(position, self.destination)
            moves = []
            for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                point = position[0] + dx, position[1] + dy
                if (not 0 <= point[0] < me["width"] or not 0 <= point[1] < me["height"]
                        or _distance(point, self.destination) != remaining - 1 or not self._safe_step(me, point)):
                    continue
                moves.append((-self._novelty(me, point), self.visits.get(point, 0),
                              self._tie(me, "step", point), (dx, dy), point))
            if moves:
                _, _, _, move, point = min(moves)
                after_move = me["inventory"] - me["movement_cost"]
                return Action(move=move,
                              harvest=self._request(me, site_at.get(point), after_move, point, self.destination),
                              reserve=self._fuel(me, point, self.destination))
            self._clear()
        return Action(harvest=self._request(me, current, me["inventory"], position),
                      reserve=self._fuel(me, position))
