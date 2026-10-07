"""Immutable physical commons, version 3 development engine.

The phase order is observe/commit, move, messages and transfers, extract,
consume, then renew.  There are no institutions, memberships, quotas, deaths,
or executable policy sources in this module.  Weather and contention priorities
are keyed events, never draws from a mutable random stream.

Harvest costs consume a fraction of the gross extracted material. Movement and
messages must be affordable from the sender's own inventory. Incoming transfers
cannot fund these actions or outgoing transfers in the same tick. Inventory
overflow is discarded *before* consumption. Renewal above capacity is reported
separately as unrealized growth, not counted twice as material waste.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
from typing import Any


VERSION = "commons-v3-physical-v1"
SNAPSHOT_VERSION = "commons-v3-snapshot-v1"


def _integer(value: Any, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")


def _number(value: Any, name: str, minimum: float = 0, maximum: float = 1e15) -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be finite and in [{minimum}, {maximum}]")


@dataclass(frozen=True)
class Config:
    width: int = 12
    height: int = 12
    n_agents: int = 24
    n_patches: int = 16
    sensing_radius: int = 1
    need: float = 1.0
    initial_inventory: float = 2.0
    inventory_capacity: float = 80.0
    patch_capacity: float = 40.0
    initial_patch_stock: float = 30.0
    renewal_rate: float = 0.24
    recovery: float = 0.02
    weather_amplitude: float = 0.1
    max_harvest: float = 4.0
    movement_cost: float = 0.02
    harvest_cost_per_unit: float = 0.02
    message_byte_cost: float = 0.001
    max_message_bytes: int = 128
    max_messages: int = 1
    renewal_law: str = "logistic"
    contention: str = "proportional"
    terminal_wealth_weight: float = 0.05

    def __post_init__(self) -> None:
        _integer(self.width, "width", 1, 1024)
        _integer(self.height, "height", 1, 1024)
        _integer(self.n_agents, "n_agents", 1, 4096)
        _integer(self.n_patches, "n_patches", 1, min(4096, self.width * self.height))
        _integer(self.sensing_radius, "sensing_radius", 0, 1024)
        _integer(self.max_message_bytes, "max_message_bytes", 0, 4096)
        _integer(self.max_messages, "max_messages", 0, min(64, self.n_agents))
        for name in ("need", "initial_inventory", "inventory_capacity", "patch_capacity",
                     "initial_patch_stock", "recovery", "max_harvest", "movement_cost",
                     "message_byte_cost", "terminal_wealth_weight"):
            _number(getattr(self, name), name, maximum=1e6)
        if self.inventory_capacity <= 0 or self.patch_capacity <= 0:
            raise ValueError("capacities must be positive")
        if self.initial_inventory > self.inventory_capacity or self.initial_patch_stock > self.patch_capacity:
            raise ValueError("initial resources exceed capacity")
        _number(self.renewal_rate, "renewal_rate", maximum=4)
        _number(self.weather_amplitude, "weather_amplitude", maximum=1)
        _number(self.harvest_cost_per_unit, "harvest_cost_per_unit", maximum=1)
        if self.harvest_cost_per_unit >= 1:
            raise ValueError("harvest_cost_per_unit must be less than one")
        if self.renewal_law not in ("logistic", "additive"):
            raise ValueError("unknown renewal_law")
        if self.contention not in ("proportional", "keyed_priority"):
            raise ValueError("unknown contention")


@dataclass(frozen=True)
class AgentState:
    id: int
    x: int
    y: int
    inventory: float
    consumption: float = 0.0
    shortfall: float = 0.0
    harvested: float = 0.0
    movement_cost: float = 0.0
    message_cost: float = 0.0
    harvest_cost: float = 0.0
    waste: float = 0.0
    transfer_in: float = 0.0
    transfer_out: float = 0.0


@dataclass(frozen=True)
class PatchState:
    id: int
    x: int
    y: int
    stock: float
    cumulative_growth: float = 0.0
    cumulative_harvest: float = 0.0
    growth_waste: float = 0.0


@dataclass(frozen=True)
class Message:
    sender: int
    recipient: int
    sent_tick: int
    delivery_tick: int
    text: str


@dataclass(frozen=True)
class WorldState:
    config: Config
    seed: int
    tick: int
    agents: tuple[AgentState, ...]
    patches: tuple[PatchState, ...]
    messages: tuple[Message, ...] = ()

    def __post_init__(self) -> None:
        if type(self.agents) is not tuple or type(self.patches) is not tuple or type(self.messages) is not tuple:
            raise ValueError("state collections must be immutable tuples")


@dataclass(frozen=True)
class Action:
    move: tuple[int, int] = (0, 0)
    harvest: float = 0.0
    transfers: tuple[tuple[int, float], ...] = ()
    messages: tuple[tuple[int, str], ...] = ()
    reserve: float = 0.0


@dataclass(frozen=True)
class AgentLedger:
    id: int
    inventory_before: float
    moved: bool
    movement_cost: float
    message_bytes: int
    message_cost: float
    transfer_out: float
    transfer_in: float
    harvested: float
    harvest_cost: float
    consumption: float
    shortfall: float
    waste: float
    inventory_after: float
    residual: float


@dataclass(frozen=True)
class PatchLedger:
    id: int
    stock_before: float
    harvested: float
    stock_after_harvest: float
    weather: float
    potential_growth: float
    growth: float
    growth_waste: float
    stock_after: float
    residual: float
    weather_event_id: str


@dataclass(frozen=True)
class TransferReceipt:
    sender: int
    recipient: int
    requested: float
    transferred: float
    reachable: bool


@dataclass(frozen=True)
class MessageReceipt:
    sender: int
    recipient: int
    byte_count: int
    cost: float
    delivered: bool
    reason: str


@dataclass(frozen=True)
class Ledger:
    tick: int
    agents: tuple[AgentLedger, ...]
    patches: tuple[PatchLedger, ...]
    transfers: tuple[TransferReceipt, ...]
    messages: tuple[MessageReceipt, ...]
    inventory_before: float
    stock_before: float
    inventory_after: float
    stock_after: float
    growth: float
    consumption: float
    movement_cost: float
    message_cost: float
    harvest_cost: float
    waste: float
    growth_waste: float
    residual: float


@dataclass(frozen=True)
class Metrics:
    consumption: float
    shortfall: float
    reserves: float
    stocks: float
    private_utility: tuple[float, ...]
    movement_cost: float
    message_cost: float
    harvest_cost: float
    waste: float


@dataclass(frozen=True)
class StepResult:
    state: WorldState
    ledger: Ledger
    metrics: Metrics


def _event(seed: int, kind: str, tick: int, identity: int) -> int:
    payload = f"{VERSION}|{seed}|{kind}|{tick}|{identity}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _distance(left: Any, right: Any) -> int:
    return abs(left.x - right.x) + abs(left.y - right.y)


def initialize(config: Config = Config(), seed: int = 0) -> WorldState:
    """Create fixed site geometry and seed-shuffled agent assignment to slots.

    The first n_patches slots lie on sites in site-ID order. Later groups visit
    sites in checkerboard order: even (row+column) parity first, then odd parity,
    with increasing site ID within each parity. Thus the default eight extra
    slots adjoin sites 0,2,5,7,8,10,13,15. Each group uses one offset, cycling
    through on-site, east, south, west, north; the first extra group uses east.
    Out-of-bounds offsets fall back to the site's cell. All starts are on or
    adjacent to a resource site. Geometry is independent of resources and seed;
    the seed permutes agent identities across these fixed slots.
    """
    if type(config) is not Config:
        raise ValueError("config must be Config")
    _integer(seed, "seed", 0, 2**64 - 1)
    columns = min(config.width, max(1, math.ceil(math.sqrt(config.n_patches * config.width / config.height))))
    if math.ceil(config.n_patches / columns) > config.height:
        columns = math.ceil(config.n_patches / config.height)
    rows = math.ceil(config.n_patches / columns)
    patches = tuple(PatchState(i, int((i % columns + 0.5) * config.width / columns),
                               int((i // columns + 0.5) * config.height / rows),
                               float(config.initial_patch_stock)) for i in range(config.n_patches))
    offsets = ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1))
    checkerboard = sorted(range(config.n_patches),
                          key=lambda i: (((i // columns) + (i % columns)) % 2, i))
    slots = []
    for i in range(config.n_agents):
        site_id = i if i < config.n_patches else checkerboard[i % config.n_patches]
        patch = patches[site_id]
        dx, dy = offsets[(i // config.n_patches) % len(offsets)]
        x, y = patch.x + dx, patch.y + dy
        if not (0 <= x < config.width and 0 <= y < config.height):
            x, y = patch.x, patch.y
        slots.append((x, y))
    order = sorted(range(config.n_agents), key=lambda i: (_event(seed, "initial-slot", 0, i), i))
    agents = tuple(AgentState(i, *slots[order[i]], float(config.initial_inventory)) for i in range(config.n_agents))
    state = WorldState(config, seed, 0, agents, patches)
    _validate_state(state)
    return state


def _validate_state(state: WorldState) -> None:
    if type(state) is not WorldState or type(state.config) is not Config:
        raise ValueError("expected WorldState with Config")
    cfg = state.config
    cfg.__post_init__()
    _integer(state.seed, "seed", 0, 2**64 - 1)
    _integer(state.tick, "tick", 0, 2**31 - 1)
    if len(state.agents) != cfg.n_agents or len(state.patches) != cfg.n_patches:
        raise ValueError("state population does not match config")
    for collection, cls in ((state.agents, AgentState), (state.patches, PatchState)):
        if type(collection) is not tuple:
            raise ValueError("state collections must be tuples")
        for i, item in enumerate(collection):
            if type(item) is not cls or type(item.id) is not int or item.id != i:
                raise ValueError("state IDs must be canonical contiguous integers")
            _integer(item.x, "x", 0, cfg.width - 1)
            _integer(item.y, "y", 0, cfg.height - 1)
            for field in fields(item):
                if field.name not in ("id", "x", "y"):
                    _number(getattr(item, field.name), field.name)
    if len({(p.x, p.y) for p in state.patches}) != cfg.n_patches:
        raise ValueError("resource sites must occupy distinct cells")
    if any(a.inventory > cfg.inventory_capacity for a in state.agents):
        raise ValueError("agent inventory exceeds capacity")
    if any(p.stock > cfg.patch_capacity for p in state.patches):
        raise ValueError("patch stock exceeds capacity")
    if type(state.messages) is not tuple or len(state.messages) > cfg.n_agents * cfg.max_messages:
        raise ValueError("invalid message collection")
    seen = set()
    for msg in state.messages:
        if type(msg) is not Message:
            raise ValueError("invalid message type")
        _integer(msg.sender, "sender", 0, cfg.n_agents - 1)
        _integer(msg.recipient, "recipient", 0, cfg.n_agents - 1)
        _integer(msg.sent_tick, "sent_tick", 0, 2**31 - 1)
        _integer(msg.delivery_tick, "delivery_tick", 1, 2**31 - 1)
        if msg.sender == msg.recipient or msg.delivery_tick != state.tick or msg.sent_tick != state.tick - 1:
            raise ValueError("invalid delayed-message timing or recipient")
        _message_bytes(msg.text, cfg)
        key = (msg.sender, msg.recipient)
        if key in seen:
            raise ValueError("duplicate message")
        seen.add(key)
    if tuple(sorted(state.messages, key=lambda m: (m.sender, m.recipient))) != state.messages:
        raise ValueError("message order is not canonical")
    if any(sum(m.sender == a.id for m in state.messages) > cfg.max_messages for a in state.agents):
        raise ValueError("message count exceeds sender limit")


def _message_bytes(text: str, cfg: Config) -> int:
    if type(text) is not str:
        raise ValueError("message must be a string")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("message must contain valid UTF-8") from exc
    if size == 0 or size > cfg.max_message_bytes:
        raise ValueError("message byte length is outside the configured limit")
    return size


def observe(state: WorldState, agent_id: int) -> dict[str, Any]:
    """Return a fresh legal local packet; evaluator state is never embedded."""
    _validate_state(state)
    _integer(agent_id, "agent_id", 0, state.config.n_agents - 1)
    return _observe_validated(state, agent_id)


def observations(state: WorldState) -> tuple[dict[str, Any], ...]:
    """Return independent local packets after one full state validation."""
    _validate_state(state)
    return tuple(_observe_validated(state, agent.id) for agent in state.agents)


def _observe_validated(state: WorldState, agent_id: int) -> dict[str, Any]:
    cfg, agent = state.config, state.agents[agent_id]
    peers = [a for a in state.agents if _distance(agent, a) <= cfg.sensing_radius]
    public_self = {"id": agent.id, "x": agent.x, "y": agent.y, "inventory": agent.inventory}
    for name in ("width", "height", "need", "inventory_capacity", "max_harvest", "sensing_radius",
                 "movement_cost", "harvest_cost_per_unit", "message_byte_cost", "max_message_bytes", "max_messages"):
        public_self[name] = getattr(cfg, name)
    return {
        "version": VERSION,
        "tick": state.tick,
        "self": public_self,
        "sites": [{"id": p.id, "x": p.x, "y": p.y, "stock": p.stock,
                   "capacity": cfg.patch_capacity,
                   "peer_count": sum(a.x == p.x and a.y == p.y for a in peers)}
                  for p in state.patches if _distance(agent, p) <= cfg.sensing_radius],
        "peers": [{"id": a.id, "x": a.x, "y": a.y} for a in peers if a.id != agent_id],
        "messages": [asdict(m) for m in state.messages if m.recipient == agent_id],
    }


def _validate_actions(state: WorldState, actions: Sequence[Action] | Mapping[int, Action]) -> tuple[Action, ...]:
    cfg = state.config
    if isinstance(actions, Mapping):
        if len(actions) != cfg.n_agents or any(type(k) is not int for k in actions) or set(actions) != set(range(cfg.n_agents)):
            raise ValueError("actions must contain every agent exactly once")
        ordered = tuple(actions[i] for i in range(cfg.n_agents))
    elif isinstance(actions, (tuple, list)):
        if len(actions) != cfg.n_agents:
            raise ValueError("actions must contain every agent exactly once")
        ordered = tuple(actions)
    else:
        raise ValueError("actions must be a sequence or ID mapping")
    canonical = []
    for agent, action in zip(state.agents, ordered):
        if type(action) is not Action:
            raise ValueError("each action must be Action")
        if type(action.move) is not tuple or len(action.move) != 2 or any(type(v) is not int for v in action.move):
            raise ValueError("move must be an integer (dx,dy) tuple")
        dx, dy = action.move
        if abs(dx) + abs(dy) > 1:
            raise ValueError("movement must be cardinal and at most one cell")
        if not (0 <= agent.x + dx < cfg.width and 0 <= agent.y + dy < cfg.height):
            raise ValueError("movement would leave the bounded grid")
        _number(action.harvest, "harvest", maximum=cfg.max_harvest)
        _number(action.reserve, "reserve", maximum=cfg.inventory_capacity)
        for pairs, name, limit in ((action.transfers, "transfers", cfg.n_agents - 1),
                                   (action.messages, "messages", cfg.max_messages)):
            if type(pairs) is not tuple or len(pairs) > limit:
                raise ValueError(f"invalid {name} collection")
            targets = set()
            for pair in pairs:
                if type(pair) is not tuple or len(pair) != 2:
                    raise ValueError(f"invalid {name} entry")
                recipient, value = pair
                _integer(recipient, "recipient", 0, cfg.n_agents - 1)
                if recipient == agent.id or recipient in targets:
                    raise ValueError("self/duplicate recipients are not allowed")
                if _distance(agent, state.agents[recipient]) > cfg.sensing_radius:
                    raise ValueError("recipient was not locally visible at commitment")
                targets.add(recipient)
                if name == "transfers":
                    _number(value, "transfer amount", maximum=cfg.inventory_capacity)
                else:
                    _message_bytes(value, cfg)
        canonical.append(Action(action.move, float(action.harvest),
                                tuple(sorted(action.transfers)), tuple(sorted(action.messages)), float(action.reserve)))
    return tuple(canonical)


def _allocate(requests: list[tuple[int, float]], available: float, priorities: dict[int, int] | None = None) -> dict[int, float]:
    """Physical allocation, with a last-recipient correction only for roundoff."""
    if not requests:
        return {}
    total = math.fsum(value for _, value in requests)
    if total <= available:
        return dict(requests)
    if priorities is not None:
        remaining = available
        result = {}
        for identity, request in sorted(requests, key=lambda p: (priorities[p[0]], p[0])):
            amount = min(request, remaining)
            result[identity] = amount
            remaining = max(0.0, remaining - amount)
        return result
    scale = available / total if total else 0.0
    result = {identity: request * scale for identity, request in requests}
    # fsum can still round the aggregate one ulp above physical availability.
    excess = math.fsum(result.values()) - available
    if excess > 0:
        largest = max(result, key=lambda identity: (result[identity], identity))
        result[largest] = max(0.0, result[largest] - excess)
    return result


def metrics(state: WorldState) -> Metrics:
    """Cumulative consumption/shortfall/cost totals and current terminal stocks."""
    _validate_state(state)
    return Metrics(math.fsum(a.consumption for a in state.agents),
                   math.fsum(a.shortfall for a in state.agents),
                   math.fsum(a.inventory for a in state.agents),
                   math.fsum(p.stock for p in state.patches),
                   tuple(a.consumption + state.config.terminal_wealth_weight * a.inventory for a in state.agents),
                   math.fsum(a.movement_cost for a in state.agents),
                   math.fsum(a.message_cost for a in state.agents),
                   math.fsum(a.harvest_cost for a in state.agents),
                   math.fsum(a.waste for a in state.agents))


def step(state: WorldState, actions: Sequence[Action] | Mapping[int, Action]) -> StepResult:
    """Commit the entire valid joint action, returning a new immutable state.

    Unaffordable movement does not happen. Messages are paid in recipient-ID
    order, then outgoing transfers share remaining own funds proportionally.
    Both require reach after movement as well as visibility before movement.
    Transfers arriving this phase are added only after every sender's budget
    has been resolved. Requested harvest is capped solely by physical stock
    contention and the declared maximum harvest rate, never by a social rule.
    """
    _validate_state(state)
    if state.tick >= 2**31 - 1:
        raise ValueError("tick counter exhausted")
    actions = _validate_actions(state, actions)
    cfg, n = state.config, len(state.agents)
    own = [float(a.inventory) for a in state.agents]
    positions = [(a.x, a.y) for a in state.agents]
    moved, move_cost, msg_cost, msg_bytes = [False] * n, [0.0] * n, [0.0] * n, [0] * n
    outgoing, incoming = [0.0] * n, [0.0] * n
    transfer_receipts, message_receipts, messages = [], [], []
    for i, action in enumerate(actions):
        if action.move != (0, 0) and own[i] >= cfg.movement_cost:
            positions[i] = (positions[i][0] + action.move[0], positions[i][1] + action.move[1])
            own[i] -= cfg.movement_cost
            moved[i], move_cost[i] = True, float(cfg.movement_cost)

    def reachable(left: int, right: int) -> bool:
        return abs(positions[left][0] - positions[right][0]) + abs(positions[left][1] - positions[right][1]) <= cfg.sensing_radius

    for i, action in enumerate(actions):
        for recipient, text in action.messages:
            size = _message_bytes(text, cfg)
            cost = cfg.message_byte_cost * size
            accepted = reachable(i, recipient) and own[i] >= cost
            reason = "sent" if accepted else ("out_of_range" if not reachable(i, recipient) else "insufficient_inventory")
            if accepted:
                own[i] -= cost
                msg_cost[i] += cost
                msg_bytes[i] += size
                messages.append(Message(i, recipient, state.tick, state.tick + 1, text))
            message_receipts.append(MessageReceipt(i, recipient, size, cost if accepted else 0.0, accepted, reason))
        requests = [(recipient, amount) for recipient, amount in action.transfers if reachable(i, recipient)]
        allocations = _allocate(requests, own[i])
        outgoing[i] = math.fsum(allocations.values())
        own[i] = max(0.0, own[i] - outgoing[i])
        for recipient, amount in action.transfers:
            actual = allocations.get(recipient, 0.0)
            incoming[recipient] += actual
            transfer_receipts.append(TransferReceipt(i, recipient, amount, actual, reachable(i, recipient)))

    harvested = [0.0] * n
    patch_harvest = [0.0] * len(state.patches)
    for patch in state.patches:
        requests = [(i, a.harvest) for i, a in enumerate(actions) if a.harvest > 0 and positions[i] == (patch.x, patch.y)]
        priorities = ({i: _event(state.seed, f"priority-p{patch.id}", state.tick, i) for i, _ in requests}
                      if cfg.contention == "keyed_priority" else None)
        allocation = _allocate(requests, patch.stock, priorities)
        for i, amount in allocation.items():
            harvested[i] = amount
        patch_harvest[patch.id] = math.fsum(allocation.values())

    agents, agent_rows = [], []
    for i, old in enumerate(state.agents):
        harvest_cost = harvested[i] * cfg.harvest_cost_per_unit
        before_cap = own[i] + incoming[i] + harvested[i] - harvest_cost
        waste = max(0.0, before_cap - cfg.inventory_capacity)
        available = min(cfg.inventory_capacity, before_cap)
        consumed = min(cfg.need, max(0.0, available - actions[i].reserve))
        inventory = max(0.0, available - consumed)
        shortfall = cfg.need - consumed
        residual = inventory - (old.inventory - move_cost[i] - msg_cost[i] - outgoing[i] + incoming[i]
                                + harvested[i] - harvest_cost - consumed - waste)
        agents.append(AgentState(i, *positions[i], inventory, old.consumption + consumed,
                                 old.shortfall + shortfall, old.harvested + harvested[i],
                                 old.movement_cost + move_cost[i], old.message_cost + msg_cost[i],
                                 old.harvest_cost + harvest_cost, old.waste + waste,
                                 old.transfer_in + incoming[i], old.transfer_out + outgoing[i]))
        agent_rows.append(AgentLedger(i, old.inventory, moved[i], move_cost[i], msg_bytes[i], msg_cost[i],
                                      outgoing[i], incoming[i], harvested[i], harvest_cost, consumed,
                                      shortfall, waste, inventory, residual))

    patches, patch_rows = [], []
    for old in state.patches:
        extraction = patch_harvest[old.id]
        remaining = max(0.0, old.stock - extraction)
        weather = 1.0 + cfg.weather_amplitude * (2.0 * (_event(state.seed, "weather", state.tick, old.id) / 2**64) - 1.0)
        production = (cfg.renewal_rate * remaining * (1.0 - remaining / cfg.patch_capacity)
                      if cfg.renewal_law == "logistic" else cfg.renewal_rate * cfg.patch_capacity / 4.0)
        potential = (production + cfg.recovery) * weather
        growth = min(max(0.0, cfg.patch_capacity - remaining), potential)
        growth_waste = max(0.0, potential - growth)
        stock = remaining + growth
        patches.append(PatchState(old.id, old.x, old.y, stock, old.cumulative_growth + growth,
                                  old.cumulative_harvest + extraction, old.growth_waste + growth_waste))
        patch_rows.append(PatchLedger(old.id, old.stock, extraction, remaining, weather, potential, growth,
                                      growth_waste, stock, stock - (old.stock - extraction + growth),
                                      f"{VERSION}/seed-{state.seed}/tick-{state.tick}/patch-{old.id}/weather"))
    new = WorldState(cfg, state.seed, state.tick + 1, tuple(agents), tuple(patches), tuple(messages))
    totals = {name: math.fsum(getattr(row, name) for row in agent_rows)
              for name in ("inventory_before", "inventory_after", "consumption", "movement_cost", "message_cost", "harvest_cost", "waste")}
    stock_before = math.fsum(p.stock for p in state.patches)
    stock_after = math.fsum(p.stock for p in new.patches)
    growth = math.fsum(p.growth for p in patch_rows)
    residual = (totals["inventory_after"] + stock_after - totals["inventory_before"] - stock_before - growth
                + totals["consumption"] + totals["movement_cost"] + totals["message_cost"] + totals["harvest_cost"] + totals["waste"])
    ledger = Ledger(state.tick, tuple(agent_rows), tuple(patch_rows), tuple(transfer_receipts), tuple(message_receipts),
                    totals["inventory_before"], stock_before, totals["inventory_after"], stock_after, growth,
                    totals["consumption"], totals["movement_cost"], totals["message_cost"], totals["harvest_cost"],
                    totals["waste"], math.fsum(p.growth_waste for p in patch_rows), residual)
    return StepResult(new, ledger, metrics(new))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def snapshot(state: WorldState) -> dict[str, Any]:
    """Return a fresh JSON checkpoint including evaluator-only state and hash."""
    _validate_state(state)
    payload = asdict(state)
    # Round-trip tuples to actual JSON lists so snapshots have one wire shape.
    payload = json.loads(_canonical(payload))
    signed = {"version": SNAPSHOT_VERSION, "engine_version": VERSION, "state": payload}
    return {**signed, "sha256": hashlib.sha256(_canonical(signed)).hexdigest()}


def _record(cls: Any, data: Any) -> Any:
    if type(data) is not dict or set(data) != {f.name for f in fields(cls)}:
        raise ValueError(f"invalid {cls.__name__} fields")
    return cls(**data)


def restore(checkpoint: dict[str, Any]) -> WorldState:
    """Validate schema, integrity and physical bounds before restoring state.

    The digest detects corruption, not authorship: checkpoints are private
    evaluator inputs, never policy observations or an authentication boundary.
    """
    if type(checkpoint) is not dict or set(checkpoint) != {"version", "engine_version", "state", "sha256"}:
        raise ValueError("invalid snapshot fields")
    if checkpoint["version"] != SNAPSHOT_VERSION or checkpoint["engine_version"] != VERSION:
        raise ValueError("unsupported snapshot version")
    signed = {key: checkpoint[key] for key in ("version", "engine_version", "state")}
    try:
        actual = hashlib.sha256(_canonical(signed)).hexdigest()
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ValueError("snapshot is not finite JSON") from exc
    if type(checkpoint["sha256"]) is not str or actual != checkpoint["sha256"]:
        raise ValueError("snapshot integrity mismatch")
    payload = checkpoint["state"]
    if type(payload) is not dict or set(payload) != {f.name for f in fields(WorldState)}:
        raise ValueError("invalid WorldState fields")
    cfg = _record(Config, payload["config"])
    for name, limit in (("agents", cfg.n_agents), ("patches", cfg.n_patches), ("messages", cfg.n_agents * cfg.max_messages)):
        if type(payload[name]) is not list or len(payload[name]) > limit:
            raise ValueError(f"invalid snapshot {name}")
    state = WorldState(cfg, payload["seed"], payload["tick"],
                       tuple(_record(AgentState, row) for row in payload["agents"]),
                       tuple(_record(PatchState, row) for row in payload["patches"]),
                       tuple(_record(Message, row) for row in payload["messages"]))
    _validate_state(state)
    return state
