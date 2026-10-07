"""Costly local occupation and resistance, outside every frozen v3 source.

Claims confer no automatic exclusion. Any stationary individual can pay to
guard; guards forgo harvesting and divide finite pressure among rival harvest
requests. Opening members pool protection only at their own institution's site.
This is a supplied physical contest rule, not an evolved respect convention.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
import hashlib
import json
import math

from . import engine as physical
from . import politics_v1 as politics


VERSION = "commons-v3-costly-exclusion-v1"
SNAPSHOT_VERSION = "commons-v3-costly-exclusion-snapshot-v1"


@dataclass(frozen=True)
class ExclusionConfig:
    guard_unit_cost: float = .1
    resistance_unit_cost: float = .1
    max_effort: float = 4.

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            physical._number(value, field.name, maximum=1e6)
            if value <= 0:
                raise ValueError(f"{field.name} must be positive")


@dataclass(frozen=True)
class Force:
    guard: float = 0.
    resist: float = 0.

    def __post_init__(self):
        physical._number(self.guard, "guard effort", maximum=1e6)
        physical._number(self.resist, "resistance effort", maximum=1e6)
        if self.guard > 0 and self.resist > 0:
            raise ValueError("guard and resistance effort are mutually exclusive")


@dataclass(frozen=True)
class State:
    political: politics.State
    config: ExclusionConfig = ExclusionConfig()
    guard_cost: float = 0.
    resistance_cost: float = 0.


@dataclass(frozen=True)
class AgentLedger:
    id: int
    coalition: tuple[str, int]
    requested_harvest: float
    effective_harvest: float
    guard_foregone_request: float
    blocked_request: float
    pressure: float
    guard_effort: float
    resistance_effort: float
    guard_cost: float
    resistance_cost: float
    force_ok: bool
    reason: str
    harvested: float
    consumption: float
    shortfall: float


@dataclass(frozen=True)
class Ledger:
    tick: int
    agents: tuple[AgentLedger, ...]
    inventory_before: float
    inventory_after: float
    custody_before: float
    custody_after: float
    guard_cost: float
    resistance_cost: float
    political_residual: float
    residual: float


@dataclass(frozen=True)
class Result:
    state: State
    political: politics.Result
    ledger: Ledger


def _validate(state):
    if type(state) is not State or type(state.config) is not ExclusionConfig:
        raise ValueError("invalid exclusion state")
    politics._validate(state.political)
    physical._number(state.guard_cost, "cumulative guard cost")
    physical._number(state.resistance_cost, "cumulative resistance cost")


def initialize(config=physical.Config(), seed=0,
               political_config=politics.PoliticalConfig(),
               exclusion_config=ExclusionConfig()):
    state = State(politics.initialize(config, seed, political_config), exclusion_config)
    _validate(state)
    return state


def _packet(state, packet):
    packet["exclusion"] = {"version": VERSION, "config": asdict(state.config)}
    return packet


def observe(state, agent_id):
    """Only the existing legal local packet plus public contest parameters."""
    _validate(state)
    return _packet(state, politics.observe(state.political, agent_id))


def observations(state):
    _validate(state)
    return tuple(_packet(state, packet) for packet in politics.observations(state.political))


def step(state, physical_actions, intents=None, forces=None):
    """Apply simultaneous, affordable local force before political spending.

    A pure provisional political transition resolves movement after political
    debits. Only harvest requests change in the final transition from the SAME
    opening input. The provisional state is discarded; no costs or ecological
    transitions are applied twice. Neither call supplies evaluator information
    to a policy. Arrivals can be contested, but cannot guard/resist on arrival.
    """
    _validate(state)
    opening, cfg = state.political, state.config
    world = opening.world
    actions = physical._validate_actions(world, physical_actions)
    n = len(actions)
    if forces is None:
        forces = (Force(),) * n
    if (type(forces) not in (list, tuple) or len(forces) != n
            or any(type(force) is not Force for force in forces)):
        raise ValueError("one Force per individual is required")
    if any(max(force.guard, force.resist) > cfg.max_effort for force in forces):
        raise ValueError("force exceeds configured maximum effort")
    if intents is not None and (type(intents) not in (list, tuple) or len(intents) != n
                               or any(type(intent) is not politics.Intent for intent in intents)):
        raise ValueError("one Intent per individual is required")

    sites = {(p.x, p.y): p.id for p in world.patches}
    memberships = {actor: institution for institution in opening.institutions
                   if institution.active for actor in institution.members}

    def coalition(actor, site):
        institution = memberships.get(actor)
        if institution is not None and institution.site_id == site:
            return ("institution", institution.id)
        return ("individual", actor)

    balances = [agent.inventory for agent in world.agents]
    guards, resistance = [0.] * n, [0.] * n
    guard_costs, resistance_costs = [0.] * n, [0.] * n
    ok, reasons = [True] * n, ["none"] * n
    prepared_actions = list(actions)
    for actor, (action, force) in enumerate(zip(actions, forces)):
        if force.guard == 0 and force.resist == 0:
            continue
        agent = world.agents[actor]
        if action.move != (0, 0) or (agent.x, agent.y) not in sites:
            ok[actor], reasons[actor] = False, "not_stationary_at_site"
            continue
        if force.resist > 0 and action.harvest <= 0:
            ok[actor], reasons[actor] = False, "no_harvest_request"
            continue
        cost = (force.guard * cfg.guard_unit_cost
                + force.resist * cfg.resistance_unit_cost)
        if balances[actor] < cost:
            ok[actor], reasons[actor] = False, "insufficient_inventory"
            continue
        balances[actor] -= cost
        guards[actor], resistance[actor] = force.guard, force.resist
        guard_costs[actor] = force.guard * cfg.guard_unit_cost
        resistance_costs[actor] = force.resist * cfg.resistance_unit_cost
        reasons[actor] = "paid"
        if force.guard > 0:
            prepared_actions[actor] = replace(action, harvest=0.)

    debited = replace(opening, world=replace(world, agents=tuple(
        replace(agent, inventory=balances[agent.id]) for agent in world.agents)))
    provisional = politics.step(debited, prepared_actions, intents)
    ending = provisional.state.world.agents
    locations = [(agent.x, agent.y) for agent in ending]
    coalitions = [coalition(actor, sites.get(locations[actor])) for actor in range(n)]
    pressures = [[] for _ in range(n)]
    for guard, effort in enumerate(guards):
        if effort <= 0:
            continue
        opponents = [actor for actor, action in enumerate(prepared_actions)
                     if action.harvest > 0 and locations[actor] == locations[guard]
                     and coalitions[actor] != coalitions[guard]]
        if opponents:
            share = effort / len(opponents)
            for actor in opponents:
                pressures[actor].append(share)
    pressure = [math.fsum(values) for values in pressures]
    effective_actions = list(prepared_actions)
    for actor, p in enumerate(pressure):
        if p > 0:
            access = (1. + resistance[actor]) / (1. + resistance[actor] + p)
            effective_actions[actor] = replace(prepared_actions[actor],
                harvest=prepared_actions[actor].harvest * access)
    # Preserve exact inactive behavior, and avoid unnecessary second execution.
    if effective_actions == prepared_actions:
        final = provisional
    else:
        final = politics.step(debited, effective_actions, intents)
        movement = [(a.x, a.y, row.moved, row.movement_cost)
                    for a, row in zip(final.state.world.agents, final.physical.ledger.agents)]
        resolved = [(a.x, a.y, row.moved, row.movement_cost)
                    for a, row in zip(ending, provisional.physical.ledger.agents)]
        if movement != resolved:
            raise ArithmeticError("harvest adjustment changed movement resolution")

    guard_total, resistance_total = math.fsum(guard_costs), math.fsum(resistance_costs)
    after = State(final.state, cfg, state.guard_cost + guard_total,
                  state.resistance_cost + resistance_total)
    _validate(after)
    before_i = math.fsum(a.inventory for a in world.agents)
    after_i = math.fsum(a.inventory for a in final.state.world.agents)
    before_c, after_c = politics.custody(opening), politics.custody(final.state)
    pl, political = final.physical.ledger, final.ledger
    residual = (before_i + before_c + pl.stock_before + pl.growth
                - after_i - after_c - pl.stock_after - pl.consumption
                - pl.movement_cost - pl.message_cost - pl.harvest_cost - pl.waste
                - political.political_cost - political.forfeited
                - guard_total - resistance_total)
    if abs(residual) > 1e-8 * max(1., before_i + before_c + pl.stock_before + pl.growth):
        raise ArithmeticError("exclusion material accounting failed")
    rows = tuple(AgentLedger(actor, coalitions[actor], actions[actor].harvest,
        effective_actions[actor].harvest,
        actions[actor].harvest if guards[actor] > 0 else 0.,
        prepared_actions[actor].harvest - effective_actions[actor].harvest,
        pressure[actor], guards[actor], resistance[actor], guard_costs[actor],
        resistance_costs[actor], ok[actor], reasons[actor], pl.agents[actor].harvested,
        pl.agents[actor].consumption, pl.agents[actor].shortfall) for actor in range(n))
    ledger = Ledger(world.tick, rows, before_i, after_i, before_c, after_c,
                    guard_total, resistance_total, political.residual, residual)
    return Result(after, final, ledger)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def snapshot(state):
    _validate(state)
    content = {"version": SNAPSHOT_VERSION, "state": {
        "political": politics.snapshot(state.political), "config": asdict(state.config),
        "guard_cost": state.guard_cost, "resistance_cost": state.resistance_cost}}
    content = json.loads(json.dumps(content, allow_nan=False))
    return {**content, "sha256": _digest(content)}


def restore(checkpoint):
    try:
        if type(checkpoint) is not dict or set(checkpoint) != {"version", "state", "sha256"}:
            raise ValueError("invalid exclusion checkpoint fields")
        content = {key: checkpoint[key] for key in ("version", "state")}
        if (checkpoint["version"] != SNAPSHOT_VERSION or type(checkpoint["sha256"]) is not str
                or checkpoint["sha256"] != _digest(content)):
            raise ValueError("exclusion checkpoint integrity/version mismatch")
        data = checkpoint["state"]
        if type(data) is not dict or set(data) != {"political", "config", "guard_cost", "resistance_cost"}:
            raise ValueError("invalid exclusion state fields")
        if type(data["config"]) is not dict or set(data["config"]) != {f.name for f in fields(ExclusionConfig)}:
            raise ValueError("invalid exclusion config fields")
        state = State(politics.restore(data["political"]), ExclusionConfig(**data["config"]),
                      data["guard_cost"], data["resistance_cost"])
        _validate(state)
        if snapshot(state) != checkpoint:
            raise ValueError("noncanonical exclusion checkpoint")
        return state
    except (KeyError, TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("malformed exclusion checkpoint") from exc
