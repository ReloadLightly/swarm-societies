"""Local, paid remembered reports and declared-arrival routing controls.

Reports are one-hop assertions of a sender's directly sensed, dated record.
Intentions are revocable assertions, not reservations or verified commitments.
The frozen forager remains the navigation and extraction foundation. A separate
conservative arrival estimate can redirect it only for a declared positive
local surplus; observed headcounts are never replaced with invented sensing.
This is supplied engineering, not evidence of welfare or an optimal policy.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math

from .engine import Action
from .policies_navigation_v1 import ForagerPolicy
from .policies_institutions_v1 import restore_forager


COORDINATION_VERSION = "commons-v3-coordination-policy-v2"
REPORT_PREFIX = "v3c2:"


def _integer(value, name, low=0, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"invalid {name}")
    return value


def _number(value, name, low=0., high=1e15):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"invalid {name}")
    return value


def _distance(left, right):
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _record(record):
    expected = {"stock", "capacity", "peer_count", "tick", "self_present"}
    if type(record) is not dict or set(record) != expected:
        raise ValueError("invalid direct observation record")
    _number(record["capacity"], "site capacity", 1e-300, 1e6)
    _number(record["stock"], "site stock", high=record["capacity"])
    _integer(record["peer_count"], "peer count", high=4096)
    _integer(record["tick"], "record tick")
    if type(record["self_present"]) is not bool:
        raise ValueError("invalid self presence")


class _DirectReturnForager(ForagerPolicy):
    """New shared-navigation adapter: assertions are never return anchors.

    The inherited serialized navigation state is unchanged. Anchor coordinates
    are reconstructed exclusively from the coordinator's direct observations.
    Before any direct site has been encountered there is no known return route;
    the inherited exploration rule still has that explicit limitation.
    """

    @classmethod
    def from_forager(cls, forager, anchors):
        result = cls(forager.reserve_ticks, forager.stock_floor_fraction,
                     forager.route_mode, forager.aggressive)
        result.__dict__.update(forager.__dict__)
        result.return_anchors = tuple(sorted(set(anchors)))
        return result

    def _home_distance(self, point):
        return min((_distance(point, site) for site in self.return_anchors), default=0)

    def _feasible_goal(self, me, position, goal):
        distance = _distance(position, goal)
        if distance == 0:
            return False
        cost = me["movement_cost"]
        if distance == 1 and goal in self.return_anchors:
            return me["inventory"] >= cost
        required = cost * (distance + self._home_distance(goal))
        return me["inventory"] >= required + self._margin(required, cost)

    def _safe_step(self, me, point):
        cost = me["movement_cost"]
        if me["inventory"] < cost:
            return False
        if point in self.return_anchors:
            return True
        required = cost * (1 + self._home_distance(point))
        return me["inventory"] >= required + self._margin(required, cost)


class CoordinationPolicy:
    """Frozen navigation plus bounded reports and local congestion estimates.

    ``share=False`` is exact frozen-forager behavior. With sharing enabled,
    information reports may update dated route memory; only direct records
    can be transmitted. A moving sender may additionally declare its target
    to a visible peer, even when it has no novel stock observation to report.
    Unknown arrivals conservatively add to remembered headcounts; currently
    visible agents already at the target are not counted twice. This estimate
    does not claim that unseen agents stayed, traveled, or will honor a plan.

    The sender budgets the serialized byte charge before replanning. If byte
    length grows after replanning, the budget grows monotonically (at most to
    the engine's byte limit). Realized charges remain solely engine receipts.
    ``diagnostics`` describes only the last decision and is not decision state.
    """

    def __init__(self, reserve_ticks=4, stock_floor_fraction=.5,
                 route_mode="nearest", aggressive=False, *, share=True,
                 report_period=4, report_ttl=8, intention_ttl=4,
                 minimum_route_surplus=.05):
        self.forager = ForagerPolicy(reserve_ticks, stock_floor_fraction, route_mode, aggressive)
        if type(share) is not bool:
            raise ValueError("share must be boolean")
        self.share = share
        self.report_period = _integer(report_period, "report period", 1, 1024)
        self.report_ttl = _integer(report_ttl, "report TTL", 1, 1024)
        self.intention_ttl = _integer(intention_ttl, "intention TTL", 1, 1024)
        self.minimum_route_surplus = float(_number(minimum_route_surplus, "minimum route surplus", 0., 10.))
        self.owner = None
        self.last_tick = -1
        self.direct = {}
        self.sources = {}
        self.intentions = {}
        self.sent = {}
        self.diagnostics = {}

    def memory(self):
        return {"version": COORDINATION_VERSION, "share": self.share,
                "report_period": self.report_period, "report_ttl": self.report_ttl,
                "intention_ttl": self.intention_ttl,
                "minimum_route_surplus": self.minimum_route_surplus,
                "owner": self.owner, "last_tick": self.last_tick,
                "forager": self.forager.memory(),
                "direct": [{"id": site, **deepcopy(record)} for site, record in sorted(self.direct.items())],
                "sources": [[site, sender, tick] for site, (sender, tick) in sorted(self.sources.items())],
                "intentions": [[sender, *row] for sender, row in sorted(self.intentions.items())],
                "sent": [[peer, *row] for peer, row in sorted(self.sent.items())]}

    @classmethod
    def restore(cls, memory):
        expected = {"version", "share", "report_period", "report_ttl", "intention_ttl",
                    "minimum_route_surplus", "owner", "last_tick", "forager", "direct",
                    "sources", "intentions", "sent"}
        if type(memory) is not dict or set(memory) != expected or memory["version"] != COORDINATION_VERSION:
            raise ValueError("unsupported coordination memory")
        result = cls(**{key: memory[key] for key in ("share", "report_period", "report_ttl",
                        "intention_ttl", "minimum_route_surplus")})
        result.forager = restore_forager(memory["forager"])
        result.last_tick = _integer(memory["last_tick"], "last tick", -1)
        result.owner = None if memory["owner"] is None else _integer(memory["owner"], "owner", high=4095)
        if (result.owner is None) != (result.last_tick == -1):
            raise ValueError("owner and decision history disagree")
        for name in ("direct", "sources", "intentions", "sent"):
            if type(memory[name]) is not list:
                raise ValueError(f"{name} must be a list")
        for row in memory["direct"]:
            if type(row) is not dict or set(row) != {"id", "stock", "capacity", "peer_count", "tick", "self_present"}:
                raise ValueError("invalid direct record")
            site = _integer(row["id"], "site ID", high=4095)
            record = {key: value for key, value in row.items() if key != "id"}
            _record(record)
            if site in result.direct or site not in result.forager.sites:
                raise ValueError("direct record lacks unique site")
            if record["tick"] > result.forager.records[site]["tick"]:
                raise ValueError("direct record newer than route memory")
            result.direct[site] = record
        for name, length in (("sources", 3), ("intentions", 5), ("sent", 5)):
            target = getattr(result, name)
            for row in memory[name]:
                if type(row) is not list or len(row) != length:
                    raise ValueError(f"invalid {name} row")
                identity = _integer(row[0], "identity", high=4095)
                if identity in target:
                    raise ValueError(f"duplicate {name} row")
                if name == "sources":
                    sender = _integer(row[1], "sender", high=4095)
                    tick = _integer(row[2], "source tick", high=result.last_tick)
                    if (sender == result.owner or identity not in result.forager.records
                            or result.forager.records[identity]["tick"] != tick
                            or result.forager.records[identity]["self_present"]):
                        raise ValueError("report source disagrees with route record")
                elif name == "intentions":
                    _integer(row[1], "intended site", high=4095)
                    _integer(row[2], "intended x", high=1023)
                    _integer(row[3], "intended y", high=1023)
                    _integer(row[4], "intention tick", high=result.last_tick - 1)
                    if identity == result.owner or result.last_tick - row[4] > result.intention_ttl:
                        raise ValueError("stale or self intention")
                    if row[1] in result.forager.sites and result.forager.sites[row[1]] != tuple(row[2:4]):
                        raise ValueError("intention coordinates disagree with known site")
                else:
                    _integer(row[1], "reported site", -1, 4095)
                    _integer(row[2], "reported tick", -1, result.last_tick)
                    _integer(row[3], "reported goal", -1, 4095)
                    _integer(row[4], "send tick", high=result.last_tick)
                    if identity == result.owner or (row[1] == -1) != (row[2] == -1):
                        raise ValueError("invalid send record")
                    if row[1] == row[3] == -1 or row[2] > row[4]:
                        raise ValueError("empty or future send record")
                    if row[1] != -1 and row[1] not in result.direct:
                        raise ValueError("sent report was not directly observed")
                    if row[3] != -1 and row[3] not in result.forager.sites:
                        raise ValueError("sent intention lacks known site")
                target[identity] = tuple(row[1:])
        for site, record in result.forager.records.items():
            if record["tick"] > result.last_tick:
                raise ValueError("future route record")
            direct = result.direct.get(site)
            if result.share and site not in result.sources and (direct is None or direct != record):
                raise ValueError("route memory lacks direct or report provenance")
            if direct is not None and direct["tick"] == record["tick"] and direct != record:
                raise ValueError("same-tick direct record disagrees")
        if not result.share and any((result.direct, result.sources, result.intentions, result.sent)):
            raise ValueError("disabled coordination has reporting state")
        if result.owner is None and (result.forager.memory() != ForagerPolicy(
                result.forager.reserve_ticks, result.forager.stock_floor_fraction,
                result.forager.route_mode, result.forager.aggressive).memory()
                or any((result.direct, result.sources, result.intentions, result.sent))):
            raise ValueError("fresh policy has decision history")
        if result.memory() != memory:
            raise ValueError("coordination memory must be canonical")
        if result.share:
            result.forager = _DirectReturnForager.from_forager(result.forager,
                (result.forager.sites[site] for site in result.direct))
        return result

    def validate_context(self, state, agent_id):
        """Check checkpoint bounds without consulting hidden stocks or peers."""
        world = getattr(state, "world", state)
        cfg, tick = world.config, world.tick
        _integer(agent_id, "agent ID", high=cfg.n_agents - 1)
        # Restore also checks that an explicitly fresh policy has no history.
        self.restore(self.memory())
        if self.owner is not None and (self.owner != agent_id or self.last_tick != tick - 1):
            raise ValueError("policy owner or clock disagrees with episode")
        for site, point in self.forager.sites.items():
            if ((site in self.direct or not self.share) and site >= cfg.n_patches
                    or not (0 <= point[0] < cfg.width and 0 <= point[1] < cfg.height)):
                raise ValueError("known site outside episode")
        points = set(self.forager.seen) | set(self.forager.visits)
        if self.forager.destination is not None:
            points.add(self.forager.destination)
        if any(not (0 <= x < cfg.width and 0 <= y < cfg.height) for x, y in points):
            raise ValueError("route coordinate outside episode")
        # Asserted sites and crowds are bounded beliefs, not authenticated
        # world identities. The local observation contract supplies no global
        # population/site counts with which a receiver could reject such lies.
        if any(record["peer_count"] > cfg.n_agents for site, record in self.forager.records.items()
               if site not in self.sources):
            raise ValueError("route headcount outside episode")
        if any(record["peer_count"] > cfg.n_agents for record in self.direct.values()):
            raise ValueError("direct headcount outside episode")
        if any(sender >= cfg.n_agents for sender, _ in self.sources.values()):
            raise ValueError("report sender outside episode")
        if any(peer >= cfg.n_agents for peer in self.sent):
            raise ValueError("report recipient outside episode")
        for sender, (site, x, y, _) in self.intentions.items():
            if sender >= cfg.n_agents or x >= cfg.width or y >= cfg.height:
                raise ValueError("intention outside episode")

    def _receive(self, observation):
        me, tick = observation["self"], observation["tick"]
        accepted = 0
        self.intentions = {sender: row for sender, row in self.intentions.items()
                           if tick - row[-1] <= self.intention_ttl}
        for message in observation["messages"]:
            try:
                text = message["text"]
                if type(text) is not str or not text.startswith(REPORT_PREFIX):
                    continue
                if len(text.encode("utf-8")) > me["max_message_bytes"]:
                    continue
                sender = _integer(message["sender"], "sender", high=4095)
                _integer(message["recipient"], "recipient", high=4095)
                _integer(message["sent_tick"], "sent tick")
                _integer(message["delivery_tick"], "delivery tick")
                if (sender == me["id"] or message["recipient"] != me["id"]
                        or message["sent_tick"] != tick - 1 or message["delivery_tick"] != tick):
                    continue
                payload = json.loads(text[len(REPORT_PREFIX):])
                if type(payload) is not list or len(payload) != 3 or type(payload[0]) is not int or payload[0] != 2:
                    continue
                report, intention = payload[1:]
                if report is None and intention is None:
                    continue
                if report is not None:
                    if type(report) is not list or len(report) != 7:
                        continue
                    observed, site, x, y, stock, capacity, crowd = report
                    _integer(observed, "observation tick", max(0, tick - self.report_ttl), tick - 1)
                    _integer(site, "site", high=4095)
                    _integer(x, "site x", high=me["width"] - 1)
                    _integer(y, "site y", high=me["height"] - 1)
                    _number(capacity, "capacity", 1e-300, 1e6)
                    _number(stock, "stock", high=capacity)
                    _integer(crowd, "crowd", high=4096)
                    if site in self.forager.sites and self.forager.sites[site] != (x, y):
                        continue
                if intention is not None:
                    if type(intention) is not list or len(intention) != 3:
                        continue
                    goal, gx, gy = intention
                    _integer(goal, "goal site", high=4095)
                    _integer(gx, "goal x", high=me["width"] - 1)
                    _integer(gy, "goal y", high=me["height"] - 1)
                    if goal in self.forager.sites and self.forager.sites[goal] != (gx, gy):
                        continue
                    if report is not None and goal == site and (gx, gy) != (x, y):
                        continue
            except (KeyError, ValueError, TypeError, OverflowError, RecursionError):
                continue
            if report is not None:
                previous = self.forager.records.get(site)
                if previous is None or previous["tick"] < observed:
                    self.forager.sites[site] = x, y
                    self.forager.records[site] = {"stock": stock, "capacity": capacity,
                        "peer_count": crowd, "tick": observed, "self_present": False}
                    self.sources[site] = sender, observed
                    accepted += 1
            if intention is not None:
                self.intentions[sender] = goal, gx, gy, tick - 1
        return accepted

    def _arrival_service(self, forager, observation, site):
        me, tick = observation["self"], observation["tick"]
        point = forager.sites[site]
        visible = {peer["id"]: (peer["x"], peer["y"]) for peer in observation["peers"]}
        extra = sum(goal == site and (x, y) == point and visible.get(sender) != point
                    and tick - announced <= self.intention_ttl
                    for sender, (goal, x, y, announced) in self.intentions.items())
        amount = min(me["max_harvest"], forager._available(site) / (forager._crowd(site) + extra))
        age = tick - forager.records[site]["tick"]
        return amount * (1 - me["harvest_cost_per_unit"]) / (1 + age / 8), extra

    def _plan(self, base_memory, observation, message_budget):
        packet = deepcopy(observation)
        packet["self"]["inventory"] -= message_budget
        base_forager = restore_forager(base_memory)
        anchors = {site: base_forager.sites[site] for site in self.direct
                   if site in base_forager.sites}
        anchors.update({site["id"]: (site["x"], site["y"]) for site in observation["sites"]})
        forager = _DirectReturnForager.from_forager(base_forager, anchors.values())
        action = forager(packet)
        me, tick = packet["self"], packet["tick"]
        position = me["x"], me["y"]
        lookup = {point: site for site, point in forager.sites.items()}
        planned = lookup.get(forager.destination) if forager.destination is not None else lookup.get(position)
        scores = {}
        for site, point in forager.sites.items():
            if tick - forager.records[site]["tick"] > self.report_ttl:
                continue
            if point != position and not forager._feasible_goal(me, position, point):
                continue
            service, arrivals = self._arrival_service(forager, packet, site)
            distance = _distance(position, point)
            value = (service - distance * me["movement_cost"]) / (distance + 1)
            scores[site] = value, service, arrivals
        old_value = scores.get(planned, (0., 0., 0))[0]
        diagnostic = {"route_changed": False, "from_site": planned,
                      "to_site": planned, "estimated_surplus": 0., "additional_arrivals": 0}
        if scores:
            best = min(scores, key=lambda site: (-scores[site][0],
                _distance(position, forager.sites[site]), site))
            value, service, arrivals = scores[best]
            surplus = value - old_value
            # Satisfactory current service needs no costly departure. A new
            # route requires a strict surplus over the declared baseline.
            current = lookup.get(position)
            stay_sufficient = current in scores and scores[current][1] >= me["need"]
            if (best != planned and surplus > self.minimum_route_surplus * me["need"]
                    and value > 0 and not stay_sufficient
                    and (scores.get(planned, (0., 0., 0))[2] > 0 or best in self.sources)):
                goal = forager.sites[best]
                if goal == position:
                    forager._clear()
                    action = Action(harvest=forager._request(me, best, me["inventory"], position),
                                    reserve=forager._fuel(me, position))
                else:
                    remaining = _distance(position, goal)
                    moves = []
                    for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                        point = position[0] + dx, position[1] + dy
                        if (0 <= point[0] < me["width"] and 0 <= point[1] < me["height"]
                                and _distance(point, goal) == remaining - 1 and forager._safe_step(me, point)):
                            moves.append((-forager._novelty(me, point), forager.visits.get(point, 0),
                                forager._tie(me, "step", point), (dx, dy), point))
                    if not moves:
                        return forager, action, diagnostic
                    _, _, _, move, point = min(moves)
                    forager.destination, forager.destination_kind = goal, "site"
                    action = Action(move=move,
                        harvest=forager._request(me, lookup.get(point), me["inventory"] - me["movement_cost"], point, goal),
                        reserve=forager._fuel(me, point, goal))
                diagnostic = {"route_changed": True, "from_site": planned, "to_site": best,
                              "estimated_surplus": surplus, "additional_arrivals": arrivals}
        return forager, action, diagnostic

    def _report(self, observation, forager, action):
        me, tick = observation["self"], observation["tick"]
        if tick % self.report_period or not me["max_messages"]:
            return None
        position = me["x"], me["y"]
        goal = next((site for site, point in forager.sites.items()
                     if point == forager.destination and point != position), None)
        # A stationary provisioner has not begun an arrival; do not announce
        # a route that may remain unaffordable after paying for the message.
        intention = [goal, *forager.sites[goal]] if goal is not None and action.move != (0, 0) else None
        candidates = []
        for peer in observation["peers"]:
            old = self.sent.get(peer["id"], (-1, -1, -1, -self.report_period))
            if tick - old[3] < self.report_period:
                continue
            report_choices = []
            for site, record in self.direct.items():
                point = forager.sites[site]
                if (tick - record["tick"] > self.report_ttl
                        or _distance((peer["x"], peer["y"]), point) <= me["sensing_radius"]
                        or (old[0] == site and old[1] >= record["tick"])):
                    continue
                report_choices.append((-record["tick"], -record["stock"], site,
                    [record["tick"], site, *point, record["stock"], record["capacity"], record["peer_count"]]))
            report = min(report_choices)[-1] if report_choices else None
            if report is None and intention is None:
                continue
            text = REPORT_PREFIX + json.dumps([2, report, intention], separators=(",", ":"), allow_nan=False)
            size = len(text.encode("utf-8"))
            if size > me["max_message_bytes"] and report is not None and intention is not None:
                report = None
                text = REPORT_PREFIX + json.dumps([2, None, intention], separators=(",", ":"), allow_nan=False)
                size = len(text.encode("utf-8"))
            charge = size * me["message_byte_cost"]
            point = position[0] + action.move[0], position[1] + action.move[1]
            # Keep current consumption and frozen route fuel, without relying
            # on an incoming transfer, future harvest, or message delivery.
            move_cost = me["movement_cost"] if action.move != (0, 0) else 0.
            reserve = max(action.reserve, forager._fuel(me, point, forager.destination))
            if size > me["max_message_bytes"] or me["inventory"] < charge + me["need"] + move_cost + reserve:
                continue
            candidates.append((old[3], peer["id"], text, charge,
                -1 if report is None else report[1], -1 if report is None else report[0],
                -1 if intention is None else intention[0]))
        return min(candidates) if candidates else None

    def __call__(self, observation):
        me, tick = observation["self"], observation["tick"]
        _integer(tick, "decision tick")
        _integer(me["id"], "owner", high=4095)
        if self.owner is not None and (self.owner != me["id"] or tick != self.last_tick + 1):
            raise ValueError("coordination policy owner or clock changed")
        self.owner, self.last_tick = me["id"], tick
        if not self.share:
            self.diagnostics = {"route_changed": False, "accepted_reports": 0, "message_budget": 0.}
            return self.forager(observation)
        accepted = self._receive(observation)
        position = me["x"], me["y"]
        for site in observation["sites"]:
            self.direct[site["id"]] = {"stock": site["stock"], "capacity": site["capacity"],
                "peer_count": site["peer_count"], "tick": tick,
                "self_present": position == (site["x"], site["y"])}
            self.sources.pop(site["id"], None)
        base = self.forager.memory()
        budget = 0.
        for attempt in range(5):
            forager, action, diagnostic = self._plan(base, observation, budget)
            report = self._report(observation, forager, action)
            if report is None:
                if budget:
                    forager, action, diagnostic = self._plan(base, observation, 0.)
                budget = 0.
                break
            if report[3] <= budget:
                break
            next_budget = report[3] if attempt < 3 else me["max_message_bytes"] * me["message_byte_cost"]
            if next_budget > me["inventory"] - me["need"] - 4 * me["movement_cost"]:
                report, budget = None, 0.
                forager, action, diagnostic = self._plan(base, observation, budget)
                break
            budget = next_budget
        self.forager = forager
        # Current direct records override a contradictory received assertion,
        # and later sensing may invalidate an old asserted target coordinate.
        self.intentions = {sender: row for sender, row in self.intentions.items()
            if row[0] not in self.forager.sites or self.forager.sites[row[0]] == tuple(row[1:3])}
        self.diagnostics = {**diagnostic, "accepted_reports": accepted,
                            "message_budget": budget, "message_attempted": report is not None}
        if report is None:
            return action
        _, peer, text, charge, site, observed, goal = report
        self.sent[peer] = site, observed, goal, tick
        # If post-move reach fails, no fee is paid. Limit requested extraction
        # against that larger possible inventory as well as the budgeted one.
        after_move = me["inventory"] - (me["movement_cost"] if action.move != (0, 0) else 0.)
        headroom = max(0., me["inventory_capacity"] - after_move) / (1 - me["harvest_cost_per_unit"])
        return replace(action, harvest=min(action.harvest, headroom), messages=((peer, text),))
