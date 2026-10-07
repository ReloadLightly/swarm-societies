"""Complete tick-boundary checkpoints for audited political controllers.

Only the fixed registry below can be resumed. Checkpoints contain physical and
political state, every policy memory, and complete future fixture schedules.
Continuation regenerates decisions from observations; it does not reuse saved
actions. There is no import string, executable source, or candidate loader.
"""
from __future__ import annotations

from dataclasses import asdict, fields
import hashlib
import json
from pathlib import Path

from .engine import Action
from . import politics_v1 as politics
from .policies_institutions_v1 import (
    CHARTER_POLICY_VERSION, COORDINATOR_VERSION, CoordinatingForager,
    VoluntaryCharterPolicy,
)


VERSION = "commons-v3-political-episode-checkpoint-v1"
SCRIPT_VERSION = "commons-v3-scripted-lifecycle-fixture-policy-v1"
SOURCE_FILES = ("../__init__.py", "__init__.py", "engine.py", "policies_navigation_v1.py", "politics_v1.py",
                "policies_institutions_v1.py", "political_episode_v1.py")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sources():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def _action(value):
    if type(value) is not dict or set(value) != {field.name for field in fields(Action)}:
        raise ValueError("invalid serialized physical action")
    try:
        return Action(move=tuple(value["move"]), harvest=value["harvest"],
                      transfers=tuple(tuple(pair) for pair in value["transfers"]),
                      messages=tuple(tuple(pair) for pair in value["messages"]), reserve=value["reserve"])
    except TypeError as error:
        raise ValueError("invalid physical action collections") from error


def _intent(value):
    if type(value) is not dict or set(value) != {field.name for field in fields(politics.Intent)}:
        raise ValueError("invalid serialized political intent")
    try:
        return politics.Intent(**{**value, "charter": None if value["charter"] is None else politics.Charter(**value["charter"])})
    except TypeError as error:
        raise ValueError("invalid intent/charter fields") from error


class ScriptedPolicy:
    """Dated development fixture; never evidence of endogenous formation.

    A schedule maps ticks to ``(physical override or None, political intent)``.
    The audited coordinator continues observing on every tick, including ticks
    with a physical override. Its full memory and every future scheduled action
    are bound in the checkpoint, so continuation cannot silently swap a script.
    """

    def __init__(self, schedule=None, *, coordinator=None):
        if coordinator is None:
            coordinator = CoordinatingForager(share=False)
        if type(coordinator) is not CoordinatingForager:
            raise ValueError("fixture requires an audited coordinator")
        if schedule is None:
            schedule = {}
        if type(schedule) is not dict:
            raise ValueError("fixture schedule must be a dictionary")
        self.coordinator = coordinator
        self.schedule = {}
        for tick, decision in schedule.items():
            if type(tick) is not int or not 0 <= tick < 2**31:
                raise ValueError("fixture tick must be a nonnegative integer")
            if (type(decision) is not tuple or len(decision) != 2
                    or decision[0] is not None and type(decision[0]) is not Action
                    or type(decision[1]) is not politics.Intent):
                raise ValueError("fixture decision must be (Action or None, Intent)")
            self.schedule[tick] = decision

    def memory(self):
        return {"version": SCRIPT_VERSION, "coordinator": self.coordinator.memory(),
                "schedule": [{"tick": tick, "physical": None if action is None else asdict(action),
                              "political": asdict(intent)}
                             for tick, (action, intent) in sorted(self.schedule.items())]}

    @classmethod
    def restore(cls, memory):
        if (type(memory) is not dict or set(memory) != {"version", "coordinator", "schedule"}
                or memory["version"] != SCRIPT_VERSION or type(memory["schedule"]) is not list):
            raise ValueError("unsupported fixture policy memory")
        schedule = {}
        for row in memory["schedule"]:
            if type(row) is not dict or set(row) != {"tick", "physical", "political"}:
                raise ValueError("invalid fixture schedule row")
            tick = row["tick"]
            if type(tick) is not int or tick in schedule:
                raise ValueError("invalid or duplicate fixture tick")
            schedule[tick] = (None if row["physical"] is None else _action(row["physical"]), _intent(row["political"]))
        policy = cls(schedule, coordinator=CoordinatingForager.restore(memory["coordinator"]))
        if _canonical(policy.memory()) != _canonical(memory):
            raise ValueError("fixture schedule must use canonical ordered records")
        return policy

    def __call__(self, observation):
        physical = self.coordinator(observation)
        override, intent = self.schedule.get(observation["tick"], (None, politics.Intent()))
        return physical if override is None else override, intent


def restore_policy(memory):
    if type(memory) is not dict:
        raise ValueError("policy memory must be a dictionary")
    versions = {COORDINATOR_VERSION: CoordinatingForager,
                CHARTER_POLICY_VERSION: VoluntaryCharterPolicy,
                SCRIPT_VERSION: ScriptedPolicy}
    policy_type = versions.get(memory.get("version"))
    if policy_type is None:
        raise ValueError("checkpoint policy is outside the audited registry")
    return policy_type.restore(memory)


def _validate_context(state, policy):
    cfg, tick = state.world.config, state.world.tick
    coordinator = policy if type(policy) is CoordinatingForager else policy.coordinator
    forager = coordinator.forager
    coordinates = [*forager.sites.values(), *forager.seen, *forager.visits]
    if forager.destination is not None:
        coordinates.append(forager.destination)
    if any(not 0 <= x < cfg.width or not 0 <= y < cfg.height for x, y in coordinates):
        raise ValueError("policy memory coordinates exceed the physical grid")
    if any(identity >= cfg.n_patches or row["tick"] >= tick for identity, row in forager.records.items()):
        raise ValueError("policy site identity or time exceeds the checkpoint")
    if any(peer >= cfg.n_agents or site >= cfg.n_patches or observed >= tick
           for (peer, site), observed in coordinator.sent.items()):
        raise ValueError("sent-report memory exceeds the checkpoint")
    if any(sender >= cfg.n_agents or observed >= tick for sender, observed in coordinator.sources.values()):
        raise ValueError("report provenance exceeds the checkpoint")
    if sum(forager.visits.values()) > tick:
        raise ValueError("policy has observed more decisions than the checkpoint tick")


class Episode:
    """Owned political state and audited controller instances at tick boundaries."""

    def __init__(self, state, policies):
        politics.snapshot(state)  # Full core state validation before ownership.
        if type(policies) not in (list, tuple) or len(policies) != state.world.config.n_agents:
            raise ValueError("one audited policy is required per individual")
        allowed = (CoordinatingForager, VoluntaryCharterPolicy, ScriptedPolicy)
        if any(type(policy) not in allowed for policy in policies):
            raise ValueError("only explicitly audited built-in policy classes may execute")
        self.state = state
        # Detach memories and complete fixture schedules from caller objects.
        self.policies = tuple(restore_policy(policy.memory()) for policy in policies)
        for policy in self.policies:
            _validate_context(state, policy)
        self.last_actions = self.last_intents = None

    def advance(self):
        """Recompute one complete decision round from legal local packets."""
        previous = tuple(policy.memory() for policy in self.policies)
        try:
            decisions = [policy(packet) for policy, packet in zip(self.policies, politics.observations(self.state))]
            actions = tuple(decision if type(decision) is Action else decision[0] for decision in decisions)
            intents = tuple(politics.Intent() if type(decision) is Action else decision[1] for decision in decisions)
            result = politics.step(self.state, actions, intents)
        except Exception:
            self.policies = tuple(restore_policy(memory) for memory in previous)
            raise
        self.state, self.last_actions, self.last_intents = result.state, actions, intents
        return result

    def checkpoint(self):
        payload = {"version": VERSION, "sources": _sources(), "state": politics.snapshot(self.state),
                   "policies": [policy.memory() for policy in self.policies]}
        detached = json.loads(_canonical(payload))
        return {"payload": detached, "sha256": hashlib.sha256(_canonical(detached)).hexdigest()}


def restore_checkpoint(checkpoint):
    if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
        raise ValueError("invalid episode checkpoint envelope")
    payload = checkpoint["payload"]
    if hashlib.sha256(_canonical(payload)).hexdigest() != checkpoint["sha256"]:
        raise ValueError("episode checkpoint checksum differs")
    if (type(payload) is not dict or set(payload) != {"version", "sources", "state", "policies"}
            or payload["version"] != VERSION or payload["sources"] != _sources()):
        raise ValueError("episode checkpoint version or audited source closure differs")
    if type(payload["policies"]) is not list:
        raise ValueError("checkpoint policies must be a list")
    return Episode(politics.restore(payload["state"]), [restore_policy(memory) for memory in payload["policies"]])
