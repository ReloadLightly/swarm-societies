"""Source-bound continuation of audited coordination and membership controls.

The registry contains only explicitly imported built-ins. A checkpoint binds
the complete political and physical state, private last-step receipts, policy
memories, and all future fixture schedules. Future decisions are regenerated
from legal local observations; no saved action or supplied executable is run.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .engine import Action
from . import politics_v1 as politics
from .own_feedback_v2 import feedback_from_result, validate_feedback
from .policies_institutions_v1 import COORDINATOR_VERSION, CoordinatingForager
from .political_episode_v1 import SCRIPT_VERSION, ScriptedPolicy
from .policies_coordination_v2 import COORDINATION_VERSION, CoordinationPolicy
from .policies_membership_v2 import MEMBERSHIP_VERSION, MembershipPolicy


VERSION = "commons-v3-political-episode-checkpoint-v2"
SOURCE_FILES = ("../__init__.py", "__init__.py", "engine.py", "policies_navigation_v1.py",
                "politics_v1.py", "policies_institutions_v1.py", "political_episode_v1.py",
                "own_feedback_v2.py", "policies_coordination_v2.py", "policies_membership_v2.py",
                "political_episode_v2.py")
REGISTRY = {COORDINATOR_VERSION: CoordinatingForager, SCRIPT_VERSION: ScriptedPolicy,
            COORDINATION_VERSION: CoordinationPolicy, MEMBERSHIP_VERSION: MembershipPolicy}


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise ValueError("checkpoint must contain finite JSON data") from error


def _sources():
    root = Path(__file__).parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def restore_policy(memory):
    if type(memory) is not dict or type(memory.get("version")) is not str:
        raise ValueError("policy memory must name an audited registry version")
    policy_type = REGISTRY.get(memory["version"])
    if policy_type is None:
        raise ValueError("checkpoint policy is outside the audited registry")
    original = _canonical(memory)
    policy = policy_type.restore(json.loads(original))
    if type(policy) is not policy_type or _canonical(policy.memory()) != original:
        raise ValueError("policy memory must use its canonical representation")
    return policy


def _validate_context(state, policy, agent_id):
    if type(policy) in (CoordinationPolicy, MembershipPolicy):
        policy.validate_context(state, agent_id)
        return
    coordinator = policy if type(policy) is CoordinatingForager else policy.coordinator
    cfg, tick = state.world.config, state.world.tick
    forager = coordinator.forager
    coordinates = [*forager.sites.values(), *forager.seen, *forager.visits]
    if forager.destination is not None:
        coordinates.append(forager.destination)
    if any(not 0 <= x < cfg.width or not 0 <= y < cfg.height for x, y in coordinates):
        raise ValueError("policy memory coordinates exceed the physical grid")
    if any(identity >= cfg.n_patches or row["tick"] >= tick
           for identity, row in forager.records.items()):
        raise ValueError("policy site identity or time exceeds the checkpoint")
    if any(peer >= cfg.n_agents or site >= cfg.n_patches or observed >= tick
           for (peer, site), observed in coordinator.sent.items()):
        raise ValueError("sent-report memory exceeds the checkpoint")
    if any(sender >= cfg.n_agents or observed >= tick for sender, observed in coordinator.sources.values()):
        raise ValueError("report provenance exceeds the checkpoint")
    if sum(forager.visits.values()) > tick:
        raise ValueError("policy has observed more decisions than the checkpoint tick")


class Episode:
    """Own audited controllers, complete state, and equally supplied receipts."""

    def __init__(self, state, policies, *, private_feedback=None, feedback_origin_tick=None):
        politics.snapshot(state)
        if (type(policies) not in (list, tuple) or len(policies) != state.world.config.n_agents
                or any(type(policy) not in REGISTRY.values() for policy in policies)):
            raise ValueError("one explicitly audited built-in policy is required per individual")
        detached = tuple(restore_policy(policy.memory()) for policy in policies)
        for identity, policy in enumerate(detached):
            _validate_context(state, policy, identity)
        feedback = ([None] * len(detached)) if private_feedback is None else private_feedback
        self.private_feedback = validate_feedback(state, feedback)
        if feedback_origin_tick is None:
            feedback_origin_tick = state.world.tick if all(row is None for row in feedback) else state.world.tick - 1
        self.feedback_origin_tick = feedback_origin_tick
        self.state, self.policies = state, detached
        self.last_actions = self.last_intents = None
        self._validate_owned()

    def _validate_owned(self):
        if (type(self.policies) is not tuple or len(self.policies) != self.state.world.config.n_agents
                or any(type(policy) not in REGISTRY.values() for policy in self.policies)):
            raise ValueError("episode controllers are outside the audited registry")
        for identity, policy in enumerate(self.policies):
            _validate_context(self.state, policy, identity)
        validate_feedback(self.state, self.private_feedback)
        if (type(self.feedback_origin_tick) is not int
                or not 0 <= self.feedback_origin_tick <= self.state.world.tick
                or all(row is None for row in self.private_feedback)
                != (self.feedback_origin_tick == self.state.world.tick)):
            raise ValueError("continued episodes require prior-step private feedback")

    def advance(self):
        """Regenerate a decision round; failures preserve the entire boundary."""
        self._validate_owned()
        previous = tuple(json.loads(_canonical(policy.memory())) for policy in self.policies)
        try:
            packets = politics.observations(self.state)
            decisions = []
            for policy, packet, receipt in zip(self.policies, packets, self.private_feedback):
                packet["private_feedback"] = deepcopy(receipt)
                decisions.append(policy(packet))
            actions, intents = [], []
            for decision in decisions:
                if type(decision) is Action:
                    action, intent = decision, politics.Intent()
                elif (type(decision) is tuple and len(decision) == 2
                      and type(decision[0]) is Action and type(decision[1]) is politics.Intent):
                    action, intent = decision
                else:
                    raise ValueError("audited policy returned an invalid decision")
                actions.append(action)
                intents.append(intent)
            result = politics.step(self.state, tuple(actions), tuple(intents))
            feedback = feedback_from_result(result)
            for identity, policy in enumerate(self.policies):
                _validate_context(result.state, policy, identity)
        except Exception:
            self.policies = tuple(restore_policy(memory) for memory in previous)
            raise
        self.state, self.private_feedback = result.state, feedback
        self.last_actions, self.last_intents = tuple(actions), tuple(intents)
        return result

    def checkpoint(self):
        self._validate_owned()
        payload = {"version": VERSION, "sources": _sources(), "state": politics.snapshot(self.state),
                   "policies": [policy.memory() for policy in self.policies],
                   "private_feedback": self.private_feedback,
                   "feedback_origin_tick": self.feedback_origin_tick}
        detached = json.loads(_canonical(payload))
        return {"payload": detached, "sha256": hashlib.sha256(_canonical(detached)).hexdigest()}


def restore_checkpoint(checkpoint):
    if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
        raise ValueError("invalid episode checkpoint envelope")
    payload = checkpoint["payload"]
    if hashlib.sha256(_canonical(payload)).hexdigest() != checkpoint["sha256"]:
        raise ValueError("episode checkpoint checksum differs")
    if (type(payload) is not dict
            or set(payload) != {"version", "sources", "state", "policies", "private_feedback", "feedback_origin_tick"}
            or payload["version"] != VERSION or payload["sources"] != _sources()):
        raise ValueError("episode checkpoint version or audited source closure differs")
    if type(payload["policies"]) is not list or type(payload["private_feedback"]) is not list:
        raise ValueError("checkpoint policies and private feedback must be lists")
    return Episode(politics.restore(payload["state"]),
                   [restore_policy(memory) for memory in payload["policies"]],
                   private_feedback=payload["private_feedback"],
                   feedback_origin_tick=payload["feedback_origin_tick"])
