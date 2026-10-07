"""Asocial site evidence derived only from consecutive legal local packets.

The observer must occupy the site during extraction. The next observation's
headcount therefore identifies solitude after movement and before the following
movement. Adjacent empty sites are deliberately not transition evidence here.
Every visible stock can nevertheless strengthen the site's capacity bound.

No evaluator state, realized weather, capacities, ledgers or peer extraction
receipts enter this module. Saturation is a possibility in the likelihood, not
a truth-derived label available to this extractor.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .engine import Action


VERSION = "commons-v3-local-site-evidence-v1"
OBSERVATION_VERSION = "commons-v3-observation-v2"


@dataclass(frozen=True)
class StockBound:
    site: int
    tick: int
    stock: float


@dataclass(frozen=True)
class CleanTransition:
    site: int
    tick: int
    z: float
    stock_next: float
    stock_before: float
    own_harvest: float


@dataclass(frozen=True)
class EvidenceBatch:
    """One observation's evidence, to be consumed together by the learner.

Apply the transition likelihood before its redundant new stock bound, or
jointly. Truncating first can erase the prior boundary density needed for a
candidate saturation atom at K == stock_next.
    """

    bounds: tuple[StockBound, ...]
    transitions: tuple[CleanTransition, ...]
    reason: str


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer at least {minimum}")
    return value


def _number(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not 0 <= value <= 1e15 or not math.isfinite(value):
        raise ValueError(f"{name} must be finite and nonnegative")
    return float(value)


def _local_packet(observation: dict[str, Any]) -> dict[str, Any]:
    """Copy just the legal fields needed for bounds and own extraction."""
    if type(observation) is not dict or observation.get("observation_version") != OBSERVATION_VERSION:
        raise ValueError("expected observation contract v2")
    try:
        tick = _integer(observation["tick"], "tick")
        source = observation["self"]
        me = {name: _integer(source[name], name) for name in ("id", "x", "y")}
        me.update({name: _number(source[name], name)
                   for name in ("inventory", "movement_cost", "max_harvest")})
        sites = []
        for source in observation["sites"]:
            site = {name: _integer(source[name], name) for name in ("id", "x", "y", "peer_count")}
            site["stock"] = _number(source["stock"], "stock")
            sites.append(site)
        peers = [{name: _integer(source[name], name) for name in ("id", "x", "y")}
                 for source in observation["peers"]]
    except (KeyError, TypeError) as exc:
        raise ValueError("missing or invalid local observation fields") from exc
    if len({site["id"] for site in sites}) != len(sites):
        raise ValueError("duplicate observed site ID")
    if len({(site["x"], site["y"]) for site in sites}) != len(sites):
        raise ValueError("observed sites must have distinct cells")
    if len({peer["id"] for peer in peers}) != len(peers) or any(peer["id"] == me["id"] for peer in peers):
        raise ValueError("duplicate or self peer ID")
    for site in sites:
        count = int((me["x"], me["y"]) == (site["x"], site["y"]))
        count += sum((peer["x"], peer["y"]) == (site["x"], site["y"]) for peer in peers)
        if site["peer_count"] != count:
            raise ValueError("site headcount disagrees with local peer positions")
    return {"tick": tick, "self": me,
            "sites": sorted(sites, key=lambda site: site["id"]),
            "peers": sorted(peers, key=lambda peer: peer["id"])}


def _transition(previous: dict[str, Any], action: Action,
                current: dict[str, Any]) -> tuple[CleanTransition | None, str]:
    if type(action) is not Action:
        raise ValueError("previous_action must be the frozen Action type")
    if (type(action.move) is not tuple or len(action.move) != 2
            or any(type(value) is not int for value in action.move)
            or abs(action.move[0]) + abs(action.move[1]) > 1):
        raise ValueError("invalid previous movement")
    request = _number(action.harvest, "harvest")
    if request > previous["self"]["max_harvest"]:
        raise ValueError("previous harvest request exceeds the declared maximum")
    old_me, me = previous["self"], current["self"]
    position = me["x"], me["y"]
    expected = old_me["x"], old_me["y"]
    if action.move != (0, 0) and old_me["inventory"] >= old_me["movement_cost"]:
        expected = expected[0] + action.move[0], expected[1] + action.move[1]
    if position != expected:
        raise ValueError("observed position disagrees with previous movement")
    site = next((site for site in current["sites"] if (site["x"], site["y"]) == position), None)
    if site is None:
        return None, "off_site"
    old_site = next((old for old in previous["sites"] if old["id"] == site["id"]), None)
    if old_site is None:
        return None, "not_observed_before"
    if (old_site["x"], old_site["y"]) != position:
        raise ValueError("site coordinates changed between observations")
    if site["peer_count"] != 1:
        return None, "shared"
    harvest = min(request, old_site["stock"])
    z = max(0., old_site["stock"] - harvest)
    if site["stock"] < z:
        raise ValueError("stock fell after the accounted solitary harvest")
    return CleanTransition(site["id"], previous["tick"], z, site["stock"],
                           old_site["stock"], harvest), "clean"


class LocalEvidence:
    """Retain maximum stocks and deduplicated own clean physical events.

Call ``observe`` before each decision, supplying the action chosen after the
preceding observation. An initial packet or a skipped tick yields bounds only;
the current packet then becomes the new baseline. Repeated identical packets
are harmless. Historical or conflicting same-tick packets are rejected.
    """

    def __init__(self):
        self.agent_id: int | None = None
        self.max_stock: dict[int, float] = {}
        self.seen: set[tuple[int, int]] = set()
        self._previous: dict[str, Any] | None = None

    def observe(self, observation: dict[str, Any], previous_action: Action | None = None) -> EvidenceBatch:
        current = _local_packet(observation)
        if self.agent_id is not None and current["self"]["id"] != self.agent_id:
            raise ValueError("local evidence belongs to a different observer")
        previous = self._previous
        transition = None
        if previous is None:
            reason = "initial"
        elif current["tick"] < previous["tick"]:
            raise ValueError("observations must not go backwards")
        elif current["tick"] == previous["tick"]:
            if current != previous:
                raise ValueError("conflicting observations at the same tick")
            return EvidenceBatch((), (), "repeated_observation")
        elif current["tick"] != previous["tick"] + 1:
            reason = "skipped_ticks"
        elif previous_action is None:
            reason = "missing_action"
        else:
            transition, reason = _transition(previous, previous_action, current)
        if transition is not None and (transition.site, transition.tick) in self.seen:
            transition, reason = None, "duplicate_event"
        bounds = tuple(StockBound(site["id"], current["tick"], site["stock"])
                       for site in current["sites"]
                       if site["id"] not in self.max_stock or site["stock"] > self.max_stock[site["id"]])
        for bound in bounds:
            self.max_stock[bound.site] = bound.stock
        if transition is not None:
            self.seen.add((transition.site, transition.tick))
        self.agent_id = current["self"]["id"]
        self._previous = current
        return EvidenceBatch(bounds, (transition,) if transition is not None else (), reason)

    def memory(self) -> dict[str, Any]:
        # Copy nested local records so callers cannot mutate the cached packet.
        previous = None if self._previous is None else {
            "tick": self._previous["tick"], "self": dict(self._previous["self"]),
            "sites": [dict(site) for site in self._previous["sites"]],
            "peers": [dict(peer) for peer in self._previous["peers"]]}
        return {"version": VERSION, "agent_id": self.agent_id,
                "max_stock": [[site, stock] for site, stock in sorted(self.max_stock.items())],
                "seen": [list(key) for key in sorted(self.seen)], "previous": previous}
