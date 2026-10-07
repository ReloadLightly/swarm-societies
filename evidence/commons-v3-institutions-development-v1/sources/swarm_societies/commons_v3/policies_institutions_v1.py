"""Audited local controllers for the separately versioned political extension.

The decentralized reporting controller retains the frozen strong forager and
uses ordinary, paid, delayed physical messages. Reports are attributed peer
assertions, not privileged observations or verified truth. Every policy in this
module is supplied code; there is no generated-code or dynamic import pathway.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math
from typing import Any

from .engine import Action
from .policies_navigation_v1 import ForagerPolicy


COORDINATOR_VERSION = "commons-v3-coordinating-forager-v1"
REPORT_PREFIX = "v3s:"
CHARTER_POLICY_VERSION = "commons-v3-voluntary-charter-policy-v1"


def _int(value, name, minimum=0, maximum=2**31 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def _number(value, name, minimum=0., maximum=1e15):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be a finite number in [{minimum}, {maximum}]")
    return value


def _point(value):
    if type(value) is not list or len(value) != 2:
        raise ValueError("coordinate must be a two-item list")
    return tuple(_int(v, "coordinate", maximum=1023) for v in value)


def restore_forager(memory: dict[str, Any]) -> ForagerPolicy:
    """Restore every deterministic field without changing the frozen policy.

    This checks the representation and internal consistency. A checkpoint hash
    detects changed bytes; neither it nor this decoder authenticates a supplied
    history as a history that really occurred.
    """
    expected = {"version", "mode", "reserve_ticks", "stock_floor_fraction", "route_mode", "aggressive",
                "sites", "records", "seen", "visits", "destination", "destination_kind"}
    if (type(memory) is not dict or set(memory) != expected
            or memory["version"] != "commons-v3-forager-policy-v1"
            or memory["mode"] != "observed_map_forager"):
        raise ValueError("unsupported forager memory")
    policy = ForagerPolicy(**{name: memory[name] for name in
                            ("reserve_ticks", "stock_floor_fraction", "route_mode", "aggressive")})
    for field in ("sites", "records", "seen", "visits"):
        if type(memory[field]) is not list:
            raise ValueError(f"{field} must be a list")
    for row in memory["sites"]:
        if type(row) is not list or len(row) != 3:
            raise ValueError("invalid known site")
        identity = _int(row[0], "site ID", maximum=4095)
        if identity in policy.sites:
            raise ValueError("duplicate known site")
        policy.sites[identity] = _point(row[1:])
    record_keys = {"id", "stock", "capacity", "peer_count", "tick", "self_present"}
    for row in memory["records"]:
        if type(row) is not dict or set(row) != record_keys:
            raise ValueError("invalid site record")
        identity = _int(row["id"], "record site ID", maximum=4095)
        if identity not in policy.sites or identity in policy.records:
            raise ValueError("site record is missing or duplicated")
        _number(row["capacity"], "capacity", minimum=1e-300, maximum=1e6)
        _number(row["stock"], "stock", maximum=row["capacity"])
        _int(row["peer_count"], "peer count", maximum=4096)
        _int(row["tick"], "observation tick")
        if type(row["self_present"]) is not bool:
            raise ValueError("self_present must be boolean")
        policy.records[identity] = {key: value for key, value in row.items() if key != "id"}
    if set(policy.sites) != set(policy.records):
        raise ValueError("every site needs its dated record")
    for row in memory["seen"]:
        point = _point(row)
        if point in policy.seen:
            raise ValueError("duplicate seen coordinate")
        policy.seen.add(point)
    for row in memory["visits"]:
        if type(row) is not list or len(row) != 3:
            raise ValueError("invalid visit record")
        point = _point(row[:2])
        if point in policy.visits:
            raise ValueError("duplicate visit coordinate")
        policy.visits[point] = _int(row[2], "visit count", minimum=1)
    destination, kind = memory["destination"], memory["destination_kind"]
    if (destination is None) != (kind is None):
        raise ValueError("destination and destination_kind must be present together")
    if kind not in (None, "site", "frontier", "revisit", "return"):
        raise ValueError("unknown destination kind")
    policy.destination = None if destination is None else _point(destination)
    policy.destination_kind = kind
    if policy.memory() != memory:
        raise ValueError("forager memory must use canonical ordered records")
    return policy


class CoordinatingForager:
    """Strong local-forager foundation with optional bounded peer reporting.

    Reports communicate only a sender's current local sensing packet. They
    retain their original observation tick when incorporated into route memory.
    A report is sent only when the peer cannot currently sense that site, and
    at most once per report period. Sending is optional and pays the unchanged
    engine's byte cost. This comparator is executable, not yet empirically
    qualified as the strongest available decentralized coordination policy.
    """

    def __init__(self, reserve_ticks=4, stock_floor_fraction=.5, route_mode="nearest",
                 aggressive=False, share=True, report_period=4):
        self.forager = ForagerPolicy(reserve_ticks, stock_floor_fraction, route_mode, aggressive)
        if type(share) is not bool:
            raise ValueError("share must be boolean")
        _int(report_period, "report_period", minimum=1, maximum=1024)
        self.share, self.report_period = share, report_period
        self.sent: dict[tuple[int, int], int] = {}
        self.sources: dict[int, tuple[int, int]] = {}

    def memory(self):
        return {"version": COORDINATOR_VERSION, "share": self.share, "report_period": self.report_period,
                "forager": self.forager.memory(),
                "sent": [[peer, site, tick] for (peer, site), tick in sorted(self.sent.items())],
                "sources": [[site, sender, tick] for site, (sender, tick) in sorted(self.sources.items())]}

    @classmethod
    def restore(cls, memory):
        if (type(memory) is not dict
                or set(memory) != {"version", "share", "report_period", "forager", "sent", "sources"}
                or memory["version"] != COORDINATOR_VERSION):
            raise ValueError("unsupported coordinator memory")
        policy = cls(share=memory["share"], report_period=memory["report_period"])
        policy.forager = restore_forager(memory["forager"])
        for name in ("sent", "sources"):
            if type(memory[name]) is not list:
                raise ValueError(f"{name} must be a list")
            for row in memory[name]:
                if type(row) is not list or len(row) != 3:
                    raise ValueError(f"invalid {name} row")
                left, right = (_int(value, "identity", maximum=4095) for value in row[:2])
                tick = _int(row[2], "report tick")
                target, key, value = (policy.sent, (left, right), tick) if name == "sent" else (policy.sources, left, (right, tick))
                if key in target:
                    raise ValueError(f"duplicate {name} row")
                target[key] = value
        if any(site not in policy.forager.records or policy.forager.records[site]["tick"] != tick
               for site, (_, tick) in policy.sources.items()):
            raise ValueError("report provenance does not match site memory")
        if policy.memory() != memory:
            raise ValueError("coordinator memory must use canonical ordered records")
        return policy

    def _receive(self, observation):
        me, tick = observation["self"], observation["tick"]
        for message in observation["messages"]:
            if not message["text"].startswith(REPORT_PREFIX):
                continue
            try:
                row = json.loads(message["text"][len(REPORT_PREFIX):])
                if type(row) is not list or len(row) != 8 or row[0] != 1:
                    continue
                _, observed, identity, x, y, stock, capacity, crowd = row
                _int(observed, "observed tick", maximum=message["sent_tick"])
                _int(identity, "site ID", maximum=4095)
                _int(x, "site x", maximum=me["width"] - 1)
                _int(y, "site y", maximum=me["height"] - 1)
                _number(capacity, "capacity", minimum=1e-300, maximum=1e6)
                _number(stock, "stock", maximum=capacity)
                _int(crowd, "peer count", maximum=4096)
                if (message["recipient"] != me["id"] or message["sender"] == me["id"]
                        or message["delivery_tick"] != tick or not observed < tick):
                    continue
                if identity in self.forager.sites and self.forager.sites[identity] != (x, y):
                    continue
                previous = self.forager.records.get(identity)
                if previous is not None and previous["tick"] >= observed:
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            self.forager.sites[identity] = (x, y)
            self.forager.records[identity] = {"stock": stock, "capacity": capacity,
                "peer_count": crowd, "tick": observed, "self_present": False}
            self.sources[identity] = (message["sender"], observed)
        for site in observation["sites"]:
            self.sources.pop(site["id"], None)

    def _report(self, observation):
        me, tick = observation["self"], observation["tick"]
        if not self.share or tick % self.report_period or not me["max_messages"]:
            return None
        candidates = []
        for peer in observation["peers"]:
            for site in observation["sites"]:
                if abs(peer["x"] - site["x"]) + abs(peer["y"] - site["y"]) <= me["sensing_radius"]:
                    continue
                payload = [1, tick, site["id"], site["x"], site["y"], site["stock"], site["capacity"], site["peer_count"]]
                text = REPORT_PREFIX + json.dumps(payload, separators=(",", ":"), allow_nan=False)
                size = len(text.encode("utf-8"))
                charge = size * me["message_byte_cost"]
                # Reporting cannot spend this tick's need or a basic fuel
                # reserve. The forager plans against the remaining inventory.
                if (size > me["max_message_bytes"]
                        or me["inventory"] < charge + me["need"] + 4 * me["movement_cost"]):
                    continue
                candidates.append((self.sent.get((peer["id"], site["id"]), -1), -site["stock"],
                                   peer["id"], site["id"], text, charge))
        return min(candidates) if candidates else None

    def __call__(self, observation):
        if self.share:
            self._receive(observation)
        report = self._report(observation)
        packet = deepcopy(observation)
        if report is not None:
            packet["self"]["inventory"] -= report[-1]
        action = self.forager(packet)
        if report is None:
            return action
        _, _, recipient, site, text, _ = report
        self.sent[recipient, site] = observation["tick"]
        me = observation["self"]
        # Reach can fail if the recipient moves. Bound extraction using the
        # original inventory so an unpaid message cannot cause overflow.
        after_move = me["inventory"] - (me["movement_cost"] if action.move != (0, 0) else 0.)
        headroom = max(0., me["inventory_capacity"] - after_move) / (1 - me["harvest_cost_per_unit"])
        return replace(action, harvest=min(action.harvest, headroom), messages=((recipient, text),))


class VoluntaryCharterPolicy:
    """Explicit local heuristics for optional membership and costly action.

    This supplies a finite response rule, not a private optimum or an estimate
    of actual detection probabilities. A responsive member compares additional
    attainable harvest against an assumed, bounded collateral loss when a
    funded local monitoring opportunity exists. Cooperative members voluntarily
    respect the quota; stubborn outsiders never join or change their harvest.
    All three use the same paid reporting/navigation implementation.
    """

    def __init__(self, *, behavior="responsive", charter=None, coordinator=None,
                 max_dues_need_fraction=.1, max_bond_need_ticks=2.,
                 anticipated_monitoring_probability=.5):
        from .politics_v1 import Charter
        if behavior not in ("responsive", "cooperative", "stubborn"):
            raise ValueError("unknown supplied behavior")
        if charter is None:
            charter = Charter()
        if type(charter) is not Charter:
            raise ValueError("charter must be the supplied Charter record")
        if coordinator is None:
            coordinator = CoordinatingForager(aggressive=behavior == "stubborn")
        if type(coordinator) is not CoordinatingForager:
            raise ValueError("coordinator must be an audited CoordinatingForager")
        _number(max_dues_need_fraction, "max_dues_need_fraction", maximum=100.)
        _number(max_bond_need_ticks, "max_bond_need_ticks", maximum=1e6)
        _number(anticipated_monitoring_probability, "anticipated_monitoring_probability", maximum=1.)
        self.behavior, self.charter, self.coordinator = behavior, charter, coordinator
        self.max_dues_need_fraction = max_dues_need_fraction
        self.max_bond_need_ticks = max_bond_need_ticks
        self.anticipated_monitoring_probability = anticipated_monitoring_probability
        self.decisions: dict[str, int] = {}

    def memory(self):
        from dataclasses import asdict
        return {"version": CHARTER_POLICY_VERSION, "behavior": self.behavior,
                "charter": asdict(self.charter), "coordinator": self.coordinator.memory(),
                "max_dues_need_fraction": self.max_dues_need_fraction,
                "max_bond_need_ticks": self.max_bond_need_ticks,
                "anticipated_monitoring_probability": self.anticipated_monitoring_probability,
                "decisions": dict(sorted(self.decisions.items()))}

    @classmethod
    def restore(cls, memory):
        from .politics_v1 import Charter
        keys = {"version", "behavior", "charter", "coordinator", "max_dues_need_fraction",
                "max_bond_need_ticks", "anticipated_monitoring_probability", "decisions"}
        if type(memory) is not dict or set(memory) != keys or memory["version"] != CHARTER_POLICY_VERSION:
            raise ValueError("unsupported charter policy memory")
        try:
            policy = cls(**{key: memory[key] for key in ("behavior", "max_dues_need_fraction", "max_bond_need_ticks",
                                                         "anticipated_monitoring_probability")},
                         charter=Charter(**memory["charter"]),
                         coordinator=CoordinatingForager.restore(memory["coordinator"]))
        except TypeError as error:
            raise ValueError("invalid charter policy configuration") from error
        if type(memory["decisions"]) is not dict:
            raise ValueError("decisions must be a dictionary")
        for key, count in memory["decisions"].items():
            if key not in ("none", "propose", "endorse", "refuse", "join", "exit", "pay", "monitor", "sanction", "withdraw"):
                raise ValueError("unknown decision counter")
            policy.decisions[key] = _int(count, "decision count")
        if policy.memory() != memory:
            raise ValueError("charter memory is not canonical")
        return policy

    def _acceptable(self, charter, me):
        return (charter["dues"] <= self.max_dues_need_fraction * me["need"]
                and charter["bond"] <= self.max_bond_need_ticks * me["need"]
                and charter["quota"] >= min(me["max_harvest"], me["need"] / (1 - me["harvest_cost_per_unit"])))

    def __call__(self, observation):
        from dataclasses import asdict
        from .politics_v1 import Intent
        action = self.coordinator(observation)
        political, me = observation["politics"], observation["self"]
        intent = Intent()
        if self.behavior == "stubborn":
            self.decisions["none"] = self.decisions.get("none", 0) + 1
            return action, intent
        member = political["membership"]
        institution = next((row for row in political["institutions"] if row["id"] == member), None)
        accepted = political["accepted_charter"]
        planned_messages = sum(len(text.encode("utf-8")) * me["message_byte_cost"] for _, text in action.messages)
        spare = max(0., me["inventory"] - me["need"] - action.reserve - planned_messages)
        local_site = next((site for site in observation["sites"] if (site["x"], site["y"]) == (me["x"], me["y"])), None)
        claims = [row for row in political["institutions"]
                  if row["own_bond"] is not None and row["own_bond"]["amount"] > 0.
                  and row["own_bond"]["release_tick"] is not None
                  and row["own_bond"]["release_tick"] <= observation["tick"]]
        if member is None and claims and (me["inventory"] < me["inventory_capacity"] or me["need"] > 0.):
            claim = min(claims, key=lambda row: row["id"])
            if action.move != (0, 0):
                # Stay at the physical vault to collect the matured claim.
                # A request planned for a different destination is discarded.
                action = replace(action, move=(0, 0), harvest=0.)
            intent = Intent("withdraw", claim["id"], amount=claim["own_bond"]["amount"])
        elif member is not None and accepted is not None and not self._acceptable(accepted, me):
            intent = Intent("exit", member)
        elif action.move == (0, 0) and member is not None and institution is not None:
            charter = institution["charter"]
            # A rule changes the member's chosen request, never the engine's
            # feasible action set. The next condition can retain a violation.
            if local_site is not None and action.harvest > charter["quota"]:
                attainable = local_site["stock"] / max(1, local_site["peer_count"])
                gain = (min(action.harvest, attainable) - min(charter["quota"], attainable)) * (1 - me["harvest_cost_per_unit"])
                bond = institution["own_bond"]
                held = 0. if bond is None else bond["amount"]
                local_other_member = any(peer["id"] in institution["members"]
                    and (peer["x"], peer["y"]) == (me["x"], me["y"]) for peer in observation["peers"])
                funded = (institution["treasury"] >= political["config"]["monitoring_cost"] + political["config"]["settlement_cost"]
                          and local_other_member)
                anticipated = self.anticipated_monitoring_probability * min(held, charter["fine"]) if funded else 0.
                if self.behavior == "cooperative" or gain <= anticipated:
                    action = replace(action, harvest=min(action.harvest, charter["quota"]))
            evidence = next((row for row in political["evidence"]
                             if row["institution"] == member and not row["used"] and row["subject"] != me["id"]
                             and row["harvested"] > row["quota"]), None)
            if evidence is not None and institution["treasury"] >= political["config"]["settlement_cost"]:
                intent = Intent("sanction", evidence["id"], funding="treasury")
            elif (institution["members"] and me["id"] == min(institution["members"])
                  and len(institution["members"]) > 1
                  and institution["treasury"] >= political["config"]["monitoring_cost"]):
                intent = Intent("monitor", institution["site_id"], funding="treasury")
            elif (spare >= charter["dues"] > 0.
                  and institution["treasury"] < 2 * len(institution["members"]) *
                      (political["config"]["monitoring_cost"] + political["config"]["settlement_cost"])):
                intent = Intent("pay", member, amount=charter["dues"])
        elif action.move == (0, 0) and member is None and local_site is not None:
            proposals = [row for row in political["proposals"] if row["kind"] == "found"]
            if proposals:
                proposal = min(proposals, key=lambda row: row["id"])
                agreeable = self._acceptable(proposal["charter"], me) and spare >= proposal["charter"]["bond"]
                intent = Intent("endorse" if agreeable else "refuse", proposal["id"])
            else:
                eligible = [row for row in political["institutions"] if row["active"]
                            and self._acceptable(row["charter"], me) and spare >= row["charter"]["bond"]]
                if eligible:
                    intent = Intent("join", min(eligible, key=lambda row: row["id"])["id"])
                else:
                    colocated = [peer["id"] for peer in observation["peers"] if (peer["x"], peer["y"]) == (me["x"], me["y"])]
                    terms = asdict(self.charter)
                    if (colocated and me["id"] == min([me["id"], *colocated])
                            and not political["proposals"] and not any(row["active"] for row in political["institutions"])
                            and self._acceptable(terms, me)
                            and spare >= terms["bond"] + political["config"]["founding_cost"]):
                        intent = Intent("propose", local_site["id"], self.charter)
        self.decisions[intent.kind] = self.decisions.get(intent.kind, 0) + 1
        return action, intent
