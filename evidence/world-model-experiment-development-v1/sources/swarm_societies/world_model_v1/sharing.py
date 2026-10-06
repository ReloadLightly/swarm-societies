"""Versioned, passive evidence transport for private swarm world models.

The trusted harness registers canonical sensor events. Actor ports carry an
identity established by that harness; report content never establishes identity
or ownership. Hashes detect changed content, not cryptographic authentication.
This is an in-process research runtime, not a Python sandbox or network service.
No parameters, weather draws, evaluator RNG state or predictions enter reports.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Callable, Mapping
from typing import Any

from .learner import RenewalSMC


VERSION = "world-model-sharing-runtime-v1"
CONDITIONS = ("isolated", "redundant", "complementary", "delayed_complementary", "union_ceiling")
FRAME_BYTES = 1024
PACKET_FIELDS = frozenset(("event_id", "tick", "patch", "phase", "stock_before",
                          "capacity", "own_infrastructure", "other_infrastructure",
                          "growth", "sensor_sigma"))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def actor_seed(seed: int, actor_key: str) -> int:
    """Condition-independent initialization for a particular private learner."""
    return int.from_bytes(hashlib.sha256(_canonical([VERSION, seed, actor_key])).digest()[:8], "big")


class _ReadOnlyModel:
    """Trusted evaluation facade; prediction and snapshots do not mutate belief."""

    __slots__ = ("__model",)

    def __init__(self, model: RenewalSMC) -> None:
        self.__model = model

    def summary(self) -> dict[str, Any]:
        return self.__model.summary()

    def predict(self, query: Mapping[str, Any], n_samples: int = 256, seed: int = 0) -> list[float]:
        return self.__model.predict(query, n_samples=n_samples, seed=seed)

    def snapshot(self) -> dict[str, Any]:
        return self.__model.snapshot()


class MemberPort:
    """An opaque bound member capability issued only by the trusted harness.

    Actor code should receive this port, never SharingRuntime. Private Python
    attributes are an API boundary, not protection against arbitrary introspection.
    Copying or constructing a port does not create a registered capability.
    """

    __slots__ = ("__runtime", "__actor_key")

    def __init__(self, runtime: "SharingRuntime", actor_key: str) -> None:
        self.__runtime = runtime
        self.__actor_key = actor_key

    @property
    def actor_key(self) -> str:
        return self.__actor_key

    def observations(self) -> list[dict[str, Any]]:
        return self.__runtime._port_observations(self)

    def belief_summary(self) -> dict[str, Any]:
        return self.__runtime._port_summary(self)

    def submit(self, event_id: str, payload: Mapping[str, Any] | None = None) -> str:
        return self.__runtime.submit_report(self, event_id, payload)


class SharingRuntime:
    """Private member/institution SMC instances and fixed truthful report rules.

    At each zero-based tick, deliver due frames, observe current local events,
    then submit current reports. Local sensing provides home plus one rotating
    other patch. The union ceiling gives all legally observed events immediately
    to each learner, without charging hypothetical communication. It is explicitly
    an information reference, not a bandwidth-matched treatment.

    A wire treatment gives each of two fixed senders one 1,024-byte uplink per
    tick. Every received uplink produces four separately charged downlinks,
    including duplicate events. Only evidence updates are deduplicated.
    """

    def __init__(self, condition: str, seed: int = 0, n_societies: int = 3,
                 members_per_society: int = 4, learner_kwargs: Mapping[str, Any] | None = None,
                 on_update: Callable[..., None] | None = None, arena_id: str | None = None) -> None:
        if condition not in CONDITIONS:
            raise ValueError("unknown sharing condition")
        # These fixed rules are the versioned three-society, four-member design.
        if n_societies != 3 or members_per_society != 4:
            raise ValueError("sharing v1 requires three societies with four members each")
        self.condition = condition
        self.seed = _integer(seed, "seed")
        self.n_societies = n_societies
        self.members_per_society = members_per_society
        if arena_id is not None and (not isinstance(arena_id, str) or not arena_id
                                     or "/" in arena_id or len(arena_id) > 100):
            raise ValueError("arena_id must be a nonempty prefix of at most 100 characters without slashes")
        self.arena_id = arena_id
        self.learner_kwargs = copy.deepcopy(dict(learner_kwargs or {}))
        if "seed" in self.learner_kwargs:
            raise ValueError("learner seed is owned by the runtime")
        self.on_update = on_update
        self._clock = -1
        self._phase = "finished"
        self._models = {}
        for society in range(n_societies):
            for member in range(members_per_society):
                key = f"member:{society}:{member}"
                self._models[key] = RenewalSMC(seed=actor_seed(seed, key), **self.learner_kwargs)
            key = f"institution:{society}"
            self._models[key] = RenewalSMC(seed=actor_seed(seed, key), **self.learner_kwargs)
        self._views = {key: _ReadOnlyModel(model) for key, model in self._models.items()}
        self._ports = {key: MemberPort(self, key) for key in self._models if key.startswith("member:")}
        self._registered_ports = {id(port): key for key, port in self._ports.items()}
        self._store: dict[str, dict[str, Any]] = {}
        self._owners: dict[str, set[str]] = {}
        self._current: dict[int, str] = {}
        self._submitted: set[str] = set()
        self._frames: list[dict[str, Any]] = []
        self._queue: list[int] = []
        self._updates: list[dict[str, Any]] = []
        self._rejections: list[dict[str, Any]] = []

    @property
    def clock(self) -> int:
        return self._clock

    @property
    def delay(self) -> int:
        return 4 if self.condition == "delayed_complementary" else 1

    def member_port(self, society: int, member: int) -> MemberPort:
        """Trusted binding operation; never expose the runtime to actor code."""
        key = f"member:{_integer(society, 'society')}:{_integer(member, 'member')}"
        if key not in self._ports:
            raise ValueError("unknown member")
        return self._ports[key]

    def _actor(self, port: MemberPort) -> str:
        key = self._registered_ports.get(id(port))
        if key is None or self._ports[key] is not port:
            raise ValueError("report requires a trusted bound member port")
        return key

    def _visible(self, society: int, member: int, tick: int) -> tuple[int, int]:
        return society, (society + 1 + (member + tick) % (self.n_societies - 1)) % self.n_societies

    def _port_observations(self, port: MemberPort) -> list[dict[str, Any]]:
        key = self._actor(port)
        if self._phase not in ("observed", "finished") or not self._current:
            return []
        _, society, member = key.split(":")
        return [copy.deepcopy(self._store[self._current[patch]])
                for patch in self._visible(int(society), int(member), self.clock)]

    def _port_summary(self, port: MemberPort) -> dict[str, Any]:
        summary = self._models[self._actor(port)].summary()
        return {key: summary[key] for key in ("mean", "intervals_90", "n_observations")}

    def evaluator_models(self) -> dict[str, _ReadOnlyModel]:
        """Trusted evaluator access only; actor ports cannot inspect other beliefs."""
        return dict(self._views)

    def _packet(self, packet: Mapping[str, Any], patch: int, *,
                tick: int | None = None, registered: bool = False) -> dict[str, Any]:
        if not isinstance(packet, Mapping) or set(packet) != PACKET_FIELDS:
            raise ValueError("sensor packet must contain exactly the declared fields")
        item = dict(packet)
        if (not isinstance(item["event_id"], str) or not item["event_id"]
                or len(item["event_id"]) > 200):
            raise ValueError("event_id must be a nonempty string of at most 200 characters")
        if self.arena_id is not None and not item["event_id"].startswith(self.arena_id + "/"):
            raise ValueError("sensor event belongs to another arena")
        if _integer(item["tick"], "tick") != (self.clock if tick is None else tick):
            raise ValueError("sensor event belongs to another or future tick")
        if _integer(item["patch"], "patch") != patch or item["phase"] != "before_actions":
            raise ValueError("sensor patch or phase differs from the declared observation contract")
        for name in PACKET_FIELDS - {"event_id", "tick", "patch", "phase"}:
            if isinstance(item[name], bool):
                raise ValueError(f"{name} must be finite numeric data")
            try:
                item[name] = float(item[name])
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"{name} must be finite numeric data") from exc
            if not math.isfinite(item[name]):
                raise ValueError(f"{name} must be finite numeric data")
        if (item["capacity"] <= 0 or not 0 <= item["stock_before"] <= item["capacity"]
                or item["own_infrastructure"] < 0 or item["other_infrastructure"] < 0):
            raise ValueError("invalid stocks or infrastructure")
        if item["sensor_sigma"] != next(iter(self._models.values())).sensor_sigma:
            raise ValueError("sensor_sigma differs from the declared learner")
        if not registered and item["event_id"] in self._store:
            raise ValueError("sensor event identity is already registered")
        return item

    def _update(self, actor_key: str, packet: Mapping[str, Any], channel: str,
                frame_id: str | None = None) -> None:
        result = self._models[actor_key].update(packet)
        self._updates.append({"tick": self.clock, "actor_key": actor_key,
                              "event_id": packet["event_id"], "status": result["status"],
                              "channel": channel, "frame_id": frame_id,
                              "reason": result.get("reason")})
        if result["status"] == "updated" and self.on_update is not None:
            self.on_update(self, actor_key, self._views[actor_key], copy.deepcopy(result),
                           copy.deepcopy(dict(packet)), channel)

    def start_tick(self, tick: int) -> None:
        if self._phase != "finished" or _integer(tick, "tick") != self.clock + 1:
            raise ValueError("ticks must be consecutive and previous tick must be finished")
        self._clock = tick
        self._phase = "started"
        self._current = {}
        self._submitted = set()
        due = [index for index in self._queue if self._frames[index]["delivery_tick"] <= tick]
        due_indices = set(due)
        self._queue = [index for index in self._queue if index not in due_indices]
        # Stable frame order is part of the numerical learner's evidence order.
        for index in due:
            frame = self._frames[index]
            if frame["delivery_tick"] != tick or frame["status"] != "queued":
                raise RuntimeError("invalid pending frame timing")
            frame["status"] = "delivered"
            frame["delivered_tick"] = tick
            self._update(frame["recipient"], frame["packet"], frame["channel"], frame["frame_id"])
            if frame["channel"] == "uplink":
                society = int(frame["recipient"].split(":")[1])
                for member in range(self.members_per_society):
                    self._enqueue("downlink", frame["recipient"], f"member:{society}:{member}",
                                  frame["origin_member"], frame["packet"], frame["frame_id"])

    def observe_tick(self, packets_by_patch: Mapping[int, Mapping[str, Any]]) -> None:
        if self._phase != "started":
            raise ValueError("local observations must follow start_tick exactly once")
        if set(packets_by_patch) != set(range(self.n_societies)):
            raise ValueError("one canonical sensor event is required for every patch")
        packets = {patch: self._packet(packets_by_patch[patch], patch)
                   for patch in range(self.n_societies)}
        if len({packet["event_id"] for packet in packets.values()}) != self.n_societies:
            raise ValueError("different physical events require different event identities")
        for patch, packet in packets.items():
            event_id = packet["event_id"]
            self._store[event_id] = packet
            self._current[patch] = event_id
            self._owners[event_id] = set()
        for society in range(self.n_societies):
            for member in range(self.members_per_society):
                key = f"member:{society}:{member}"
                for patch in self._visible(society, member, self.clock):
                    self._owners[self._current[patch]].add(key)
                    self._update(key, packets[patch], "local")
                if self.condition == "union_ceiling":
                    for patch in range(self.n_societies):
                        if patch not in self._visible(society, member, self.clock):
                            self._update(key, packets[patch], "union_ceiling")
            if self.condition == "union_ceiling":
                for patch in range(self.n_societies):
                    self._update(f"institution:{society}", packets[patch], "union_ceiling")
        self._phase = "observed"

    @staticmethod
    def _wire_body(frame: Mapping[str, Any]) -> dict[str, Any]:
        return {"version": VERSION, **{key: frame[key] for key in (
            "frame_id", "channel", "sender", "recipient", "origin_member", "event_id",
            "event_tick", "measurement_sha256", "parent_frame_id", "tick", "delivery_tick", "packet")}}

    def _enqueue(self, channel: str, sender: str, recipient: str, origin: str,
                 packet: Mapping[str, Any], parent: str | None) -> str:
        frame_id = f"frame:{len(self._frames)}"
        frame = {"frame_id": frame_id, "tick": self.clock, "kind": "sent", "channel": channel,
                 "sender": sender, "recipient": recipient, "origin_member": origin,
                 "event_id": packet["event_id"], "event_tick": packet["tick"],
                 "measurement_sha256": hashlib.sha256(_canonical(packet)).hexdigest(),
                 "parent_frame_id": parent, "bytes": FRAME_BYTES,
                 "delivery_tick": self.clock + self.delay, "status": "queued",
                 "delivered_tick": None, "packet": copy.deepcopy(dict(packet))}
        frame["payload_bytes"] = len(_canonical(self._wire_body(frame)))
        if frame["payload_bytes"] > FRAME_BYTES:
            raise ValueError("canonical report including provenance exceeds the fixed wire frame")
        self._queue.append(len(self._frames))
        self._frames.append(frame)
        return frame_id

    def frame_bytes(self, frame_id: str) -> bytes:
        """Trusted transport audit: actual JSON body followed by explicit padding."""
        try:
            frame = next(item for item in self._frames if item["frame_id"] == frame_id)
        except StopIteration as exc:
            raise ValueError("unknown frame") from exc
        body = _canonical(self._wire_body(frame))
        return body + b" " * (FRAME_BYTES - len(body))

    def submit_report(self, actor: MemberPort, event_id: str,
                      payload: Mapping[str, Any] | None = None) -> str:
        """Submit from a bound actor; all report metadata is set by the runtime."""
        key = None
        try:
            key = self._actor(actor)
            if self._phase != "observed":
                raise ValueError("reports are accepted only after this tick's local observations")
            if self.condition in ("isolated", "union_ceiling"):
                raise ValueError("this condition has no communication budget")
            _, society_text, member_text = key.split(":")
            society, member = int(society_text), int(member_text)
            if member not in (0, 1):
                raise ValueError("member has no sender slot")
            if key in self._submitted:
                raise ValueError("member's per-tick communication budget is exhausted")
            if not isinstance(event_id, str) or event_id not in self._store:
                raise ValueError("unknown or future event")
            packet = self._store[event_id]
            if key not in self._owners[event_id]:
                raise ValueError("member does not own this sensor observation")
            if packet["tick"] != self.clock:
                raise ValueError("only current-tick owned observations can be reported")
            selected_patch = society if self.condition == "redundant" else self._visible(society, member, self.clock)[1]
            if packet["patch"] != selected_patch:
                raise ValueError("event differs from the fixed truthful reporting rule")
            if payload is not None and _canonical(dict(payload)) != _canonical(packet):
                raise ValueError("reported content differs from the canonical sensor observation")
            frame_id = self._enqueue("uplink", key, f"institution:{society}", key, packet, None)
            self._submitted.add(key)
            return frame_id
        except (TypeError, ValueError) as exc:
            self._rejections.append({"tick": self.clock, "actor_key": key,
                                     "reason": str(exc)})
            raise ValueError(str(exc)) from exc

    def submit_reports(self) -> None:
        if self._phase != "observed":
            raise ValueError("fixed reports require current local observations")
        if self.condition not in ("isolated", "union_ceiling"):
            for society in range(self.n_societies):
                for member in (0, 1):
                    key = f"member:{society}:{member}"
                    if key not in self._submitted:
                        patch = society if self.condition == "redundant" else self._visible(society, member, self.clock)[1]
                        self.submit_report(self._ports[key], self._current[patch])

    def finish_tick(self) -> None:
        if self._phase != "observed":
            raise ValueError("finish_tick requires completed current observations")
        self._phase = "finished"

    def step(self, tick: int, packets_by_patch: Mapping[int, Mapping[str, Any]]) -> None:
        self.start_tick(tick)
        self.observe_tick(packets_by_patch)
        self.submit_reports()
        self.finish_tick()

    def ledger(self) -> dict[str, Any]:
        return copy.deepcopy({"frames": self._frames, "updates": self._updates,
                              "rejections": self._rejections})

    def summary(self) -> dict[str, Any]:
        def counts(frames: list[dict[str, Any]], updates: list[dict[str, Any]]) -> dict[str, int]:
            return {"sent_frames": len(frames), "sent_bytes": sum(row["bytes"] for row in frames),
                    "delivered_frames": sum(row["status"] == "delivered" for row in frames),
                    "delivered_bytes": sum(row["bytes"] for row in frames if row["status"] == "delivered"),
                    "pending_frames": sum(row["status"] == "queued" for row in frames),
                    "pending_bytes": sum(row["bytes"] for row in frames if row["status"] == "queued"),
                    "unique_updates": sum(row["status"] == "updated" for row in updates),
                    "duplicate_updates": sum(row["status"] == "duplicate" for row in updates),
                    "failed_updates": sum(row["status"] == "failed" for row in updates)}
        result = {"version": VERSION, "condition": self.condition, "clock": self.clock,
                  "arena_id": self.arena_id,
                  "phase": self._phase, **counts(self._frames, self._updates),
                  "rejected_reports": len(self._rejections)}
        result["per_society"] = {str(society): counts(
            [row for row in self._frames if int(row["sender"].split(":")[1]) == society],
            [row for row in self._updates if int(row["actor_key"].split(":")[1]) == society])
            for society in range(self.n_societies)}
        result["learners"] = {key: {"n_observations": len(model.evidence),
                                    "diagnostics": dict(model.diagnostics)}
                              for key, model in self._models.items()}
        return result

    def snapshot(self) -> dict[str, Any]:
        """Trusted checkpoint; unlike actor payloads it includes all private state."""
        return copy.deepcopy({"version": VERSION, "condition": self.condition, "seed": self.seed,
            "arena_id": self.arena_id,
            "n_societies": self.n_societies, "members_per_society": self.members_per_society,
            "learner_kwargs": self.learner_kwargs, "clock": self.clock, "phase": self._phase,
            "models": {key: model.snapshot() for key, model in self._models.items()},
            "store": self._store, "owners": {key: sorted(value) for key, value in self._owners.items()},
            "current": {str(key): value for key, value in self._current.items()},
            "submitted": sorted(self._submitted), "frames": self._frames, "queue": self._queue,
            "updates": self._updates, "rejections": self._rejections})

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, Any], on_update: Callable[..., None] | None = None) -> "SharingRuntime":
        if snapshot.get("version") != VERSION:
            raise ValueError("unsupported sharing snapshot version")
        state = copy.deepcopy(dict(snapshot))
        runtime = cls(state["condition"], seed=state["seed"], n_societies=state["n_societies"],
                      members_per_society=state["members_per_society"],
                      learner_kwargs=state["learner_kwargs"], on_update=on_update, arena_id=state["arena_id"])
        if set(state["models"]) != set(runtime._models):
            raise ValueError("snapshot learner identities differ")
        runtime._models = {key: RenewalSMC.from_snapshot(value) for key, value in state["models"].items()}
        runtime._views = {key: _ReadOnlyModel(model) for key, model in runtime._models.items()}
        runtime._clock = state["clock"]
        if not isinstance(runtime.clock, int) or runtime.clock < -1 or state["phase"] not in ("started", "observed", "finished"):
            raise ValueError("invalid snapshot clock or phase")
        runtime._phase = state["phase"]
        runtime._store = state["store"]
        runtime._owners = {key: set(value) for key, value in state["owners"].items()}
        runtime._current = {int(key): value for key, value in state["current"].items()}
        runtime._submitted = set(state["submitted"])
        runtime._frames = state["frames"]
        runtime._queue = state["queue"]
        runtime._updates = state["updates"]
        runtime._rejections = state["rejections"]
        runtime._validate_restored_state()
        return runtime

    def _validate_restored_state(self) -> None:
        """Check restored transport authority, packet consistency, and timing."""
        if set(self._owners) != set(self._store) or not self._submitted <= set(self._ports):
            raise ValueError("invalid restored observation ownership or submitted actors")
        observed_ticks = self.clock + (self._phase != "started")
        expected_events = {(tick, patch) for tick in range(observed_ticks) for patch in range(self.n_societies)}
        actual_events = set()
        for event_id, packet in self._store.items():
            if (set(packet) != PACKET_FIELDS or packet["event_id"] != event_id
                    or packet["tick"] > self.clock or packet["phase"] != "before_actions"):
                raise ValueError("invalid restored sensor event")
            normalized = self._packet(packet, packet["patch"], tick=packet["tick"], registered=True)
            if _canonical(normalized) != _canonical(packet):
                raise ValueError("noncanonical restored sensor event")
            actual_events.add((packet["tick"], packet["patch"]))
            expected = {key for key in self._ports if packet["patch"] in self._visible(
                int(key.split(":")[1]), int(key.split(":")[2]), packet["tick"])}
            if self._owners[event_id] != expected:
                raise ValueError("restored ownership differs from sensor footprint")
        if actual_events != expected_events or len(actual_events) != len(self._store):
            raise ValueError("restored sensor history is incomplete or repeats physical events")
        expected_current = set() if self._phase == "started" or self.clock < 0 else set(range(self.n_societies))
        if set(self._current) != expected_current:
            raise ValueError("invalid restored current observation coverage")
        if any(event_id not in self._store or self._store[event_id]["patch"] != patch
               or self._store[event_id]["tick"] != self.clock for patch, event_id in self._current.items()):
            raise ValueError("invalid restored current observations")
        expected_queue = []
        frames_by_id = {}
        used_sender_slots = set()
        downlink_recipients: dict[str, set[str]] = {}
        if self.condition in ("isolated", "union_ceiling") and self._frames:
            raise ValueError("zero-communication condition contains wire frames")
        for index, frame in enumerate(self._frames):
            event_id = frame["event_id"]
            if (frame["frame_id"] != f"frame:{index}" or event_id not in self._store
                    or frame["packet"] != self._store[event_id]
                    or frame["measurement_sha256"] != hashlib.sha256(_canonical(frame["packet"])).hexdigest()
                    or frame["event_tick"] != frame["packet"]["tick"]
                    or frame["origin_member"] not in self._owners[event_id]
                    or frame["bytes"] != FRAME_BYTES
                    or frame["payload_bytes"] != len(_canonical(self._wire_body(frame)))
                    or frame["payload_bytes"] > FRAME_BYTES
                    or frame["delivery_tick"] != frame["tick"] + self.delay
                    or not frame["event_tick"] <= frame["tick"] <= self.clock):
                raise ValueError("invalid restored wire provenance or timing")
            if frame["channel"] == "uplink":
                society = frame["origin_member"].split(":")[1]
                member = int(frame["origin_member"].split(":")[2])
                selected_patch = int(society) if self.condition == "redundant" else self._visible(
                    int(society), member, frame["tick"])[1]
                sender_slot = (frame["tick"], frame["sender"])
                if (frame["sender"] != frame["origin_member"] or frame["recipient"] != f"institution:{society}"
                        or frame["parent_frame_id"] is not None or frame["tick"] != frame["event_tick"]
                        or member not in (0, 1) or frame["packet"]["patch"] != selected_patch
                        or sender_slot in used_sender_slots):
                    raise ValueError("invalid restored uplink route")
                used_sender_slots.add(sender_slot)
            elif frame["channel"] == "downlink":
                parent = frames_by_id.get(frame["parent_frame_id"])
                if parent is None:
                    raise ValueError("invalid restored downlink parent")
                recipients = downlink_recipients.setdefault(parent["frame_id"], set())
                if (parent["channel"] != "uplink" or frame["sender"] != parent["recipient"]
                        or frame["recipient"] not in self._ports
                        or frame["recipient"].split(":")[1] != frame["sender"].split(":")[1]
                        or frame["event_id"] != parent["event_id"]
                        or frame["origin_member"] != parent["origin_member"]
                        or frame["tick"] != parent["delivered_tick"] or frame["recipient"] in recipients):
                    raise ValueError("invalid restored downlink route")
                recipients.add(frame["recipient"])
            else:
                raise ValueError("invalid restored channel")
            if frame["status"] == "queued":
                if frame["delivery_tick"] <= self.clock or frame["delivered_tick"] is not None:
                    raise ValueError("invalid restored pending delivery")
                expected_queue.append(index)
            elif frame["status"] != "delivered" or frame["delivered_tick"] != frame["delivery_tick"] or frame["delivered_tick"] > self.clock:
                raise ValueError("invalid restored delivered frame")
            frames_by_id[frame["frame_id"]] = frame
        if self._queue != expected_queue:
            raise ValueError("snapshot queue differs from pending wire frames")
        if self._submitted != {actor for tick, actor in used_sender_slots if tick == self.clock}:
            raise ValueError("restored sender quota differs from submitted frames")
        for frame in self._frames:
            if frame["channel"] == "uplink" and frame["status"] == "delivered":
                society = frame["recipient"].split(":")[1]
                expected = {f"member:{society}:{member}" for member in range(self.members_per_society)}
                if downlink_recipients.get(frame["frame_id"]) != expected:
                    raise ValueError("delivered uplink did not produce the complete charged broadcast")
        self._validate_restored_learning(frames_by_id)

    def _validate_restored_learning(self, frames_by_id: Mapping[str, Any]) -> None:
        accepted: dict[str, list[dict[str, Any]]] = {key: [] for key in self._models}
        seen: dict[str, set[str]] = {key: set() for key in self._models}
        counts = {key: {"updated": 0, "duplicate": 0, "failed": 0} for key in self._models}
        wire_updates = set()
        local_updates = set()
        union_updates = set()
        previous_tick = -1
        for row in self._updates:
            key, event_id, channel = row["actor_key"], row["event_id"], row["channel"]
            if key not in self._models or event_id not in self._store or row["status"] not in counts[key]:
                raise ValueError("invalid restored learner update")
            packet = self._store[event_id]
            if not packet["tick"] <= row["tick"] <= self.clock or row["tick"] < previous_tick:
                raise ValueError("invalid restored update timing")
            previous_tick = row["tick"]
            if channel in ("uplink", "downlink"):
                frame = frames_by_id.get(row["frame_id"])
                if (frame is None or row["frame_id"] in wire_updates or frame["status"] != "delivered"
                        or frame["event_id"] != event_id or frame["recipient"] != key
                        or frame["channel"] != channel or frame["delivered_tick"] != row["tick"]):
                    raise ValueError("restored update differs from delivered wire evidence")
                wire_updates.add(row["frame_id"])
            elif channel in ("local", "union_ceiling"):
                if row["tick"] != packet["tick"] or row["frame_id"] is not None:
                    raise ValueError("invalid restored direct observation timing")
                source = local_updates if channel == "local" else union_updates
                if (key, event_id) in source:
                    raise ValueError("restored direct observation is repeated")
                source.add((key, event_id))
            else:
                raise ValueError("invalid restored update channel")
            if (row["status"] == "duplicate") != (event_id in seen[key]):
                raise ValueError("restored deduplication decisions differ from evidence history")
            counts[key][row["status"]] += 1
            if row["status"] == "updated":
                seen[key].add(event_id)
                accepted[key].append({"event_id": event_id, "headroom": packet["capacity"] - packet["stock_before"],
                    "own_infrastructure": packet["own_infrastructure"],
                    "other_infrastructure": packet["other_infrastructure"], "growth": packet["growth"]})
        expected_local = {(actor, event_id) for event_id, owners in self._owners.items() for actor in owners}
        expected_union = {(actor, event_id) for event_id, owners in self._owners.items()
                          for actor in self._models if actor not in owners} if self.condition == "union_ceiling" else set()
        if local_updates != expected_local or union_updates != expected_union:
            raise ValueError("restored local or union observations differ from declared access")
        if wire_updates != {key for key, frame in frames_by_id.items() if frame["status"] == "delivered"}:
            raise ValueError("restored wire deliveries differ from learner attempts")
        for key, model in self._models.items():
            if model.evidence != accepted[key] or any(model.diagnostics[name] != counts[key][status]
                for name, status in (("accepted_observations", "updated"), ("duplicate_events", "duplicate"),
                                     ("failed_updates", "failed"))):
                raise ValueError("restored private beliefs differ from their evidence ledger")

    def restore(self, snapshot: Mapping[str, Any], on_update: Callable[..., None] | None = None) -> None:
        replacement = self.from_snapshot(snapshot, on_update=on_update)
        self.__dict__.clear()
        self.__dict__.update(replacement.__dict__)
        # Restored capabilities must refer to this runtime and replace stale ports.
        self._ports = {key: MemberPort(self, key) for key in self._models if key.startswith("member:")}
        self._registered_ports = {id(port): key for key, port in self._ports.items()}
