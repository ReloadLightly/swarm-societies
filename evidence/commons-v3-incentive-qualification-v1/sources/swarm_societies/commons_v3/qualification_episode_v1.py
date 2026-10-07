"""Audited local-forager episodes with primitive qualification records.

Only the unchanged engine observation packet reaches a policy. Global arrays
and cohort diagnostics are recorded after the physical step for audit/analysis.
For spatial reference episodes, snapshot continuation restores physical state
and reuses committed actions; it does not restore policy memory.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import statistics

from .engine import Config, initialize, observations, restore, snapshot, step
from .policies_navigation_v1 import ForagerPolicy

VERSION = "commons-v3-qualification-episode-v1"
WEIGHTS = (0., .05, .2)
COHORTS = ("normal", "aggressive")
LEDGER_RELATIVE_TOLERANCE = 1e-9
WASTE_ABSOLUTE_TOLERANCE = 1e-9
DEPLETION_FRACTION = .1
AGENT_TICK_FIELDS = ("consumption", "shortfall", "movement_cost", "message_cost",
                     "harvested", "harvest_cost", "waste", "transfer_in", "transfer_out", "residual")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _frame(state, kinds):
    return {"tick": state.tick,
            "agents": [{"id": a.id, "x": a.x, "y": a.y, "inventory": a.inventory, "policy": kinds[a.id]}
                       for a in state.agents],
            "sites": [{"id": p.id, "x": p.x, "y": p.y, "stock": p.stock} for p in state.patches]}


def _mean_or_none(values):
    values = list(values)
    return statistics.mean(values) if values else None


def _inputs(case, control, aggressive_ids, spatial):
    if type(case) is not dict or not {"id", "config", "horizon", "seed"} <= set(case):
        raise ValueError("case requires id, config, horizon and seed")
    if type(case["id"]) is not str or not case["id"]:
        raise ValueError("case id must be nonempty text")
    if type(case["horizon"]) is not int or case["horizon"] < 1:
        raise ValueError("horizon must be a positive integer")
    if type(case["seed"]) is not int or type(case["config"]) is not dict:
        raise ValueError("seed must be an integer and config a dictionary")
    if type(spatial) is not bool:
        raise ValueError("spatial must be boolean")
    cfg = Config(**case["config"])
    if (type(control) is not dict or set(control) != {"id", "parameters"}
            or control["id"] not in ("fixed_floor", "selected")
            or type(control["parameters"]) is not dict
            or set(control["parameters"]) != {"reserve_ticks", "stock_floor_fraction", "route_mode"}):
        raise ValueError("control requires a fixed_floor/selected id and the three frozen forager parameters")
    try:
        identities = list(aggressive_ids)
    except TypeError as error:
        raise ValueError("aggressive_ids must be an iterable of distinct agent IDs") from error
    if (any(type(identity) is not int or not 0 <= identity < cfg.n_agents for identity in identities)
            or len(identities) != len(set(identities))):
        raise ValueError("aggressive_ids must contain distinct integers in the population range")
    # Detach returned bindings from caller-owned dictionaries; reject values
    # that cannot enter the canonical evidence format before any episode runs.
    bound_case = json.loads(canonical({**case, "config": asdict(cfg)}))
    bound_control = json.loads(canonical(control))
    return cfg, bound_case, bound_control, sorted(identities)


def record_episode(case, control, aggressive_ids, *, spatial=False):
    """Return one deterministic episode for a fixed control and aggressive mask.

    Agent arrays use ID order 0..n_agents-1, site arrays use 0..n_patches-1.
    Both cohort keys are always present. Empty cohorts have zero tick totals
    and null endpoint per-agent means. No qualification case is chosen here.
    """
    cfg, case, control, aggressive_ids = _inputs(case, control, aggressive_ids, spatial)
    aggressive = set(aggressive_ids)
    kinds = tuple("aggressive" if identity in aggressive else "normal" for identity in range(cfg.n_agents))
    policies = [ForagerPolicy(**control["parameters"], aggressive=kind == "aggressive") for kind in kinds]
    members = {kind: [identity for identity, own_kind in enumerate(kinds) if own_kind == kind] for kind in COHORTS}
    state = initialize(cfg, case["seed"])
    initial_state_sha256 = snapshot(state)["sha256"]
    site_layout = [{"id": p.id, "x": p.x, "y": p.y} for p in state.patches]
    site_cells = {(p.x, p.y) for p in state.patches}
    horizon = case["horizon"]
    late_count = max(1, horizon // 4)
    late_start = horizon - late_count
    quarter3_start = horizon // 2
    quarter3_count = late_start - quarter3_start
    quarter3_consumption = [0.] * cfg.n_agents
    late_consumption = [0.] * cfg.n_agents
    late_shortfall = [0.] * cfg.n_agents
    prefix256_late = [0.] * cfg.n_agents
    prefix256 = {"prefix256_consumption_per_agent_tick": None,
                 "prefix256_late_consumption_per_agent_tick": None,
                 "prefix256_terminal_stock_fraction": None}
    movement_steps = [0] * cfg.n_agents
    trajectory, frames = [], [_frame(state, kinds)] if spatial else []
    frame_ticks = {horizon // 4, horizon // 2, horizon}
    checkpoint_tick = horizon // 2
    checkpoint = snapshot(state) if spatial and checkpoint_tick == 0 else None
    resumed = restore(checkpoint) if checkpoint is not None else None
    if resumed is not None and resumed != state:
        raise ValueError("physical snapshot round-trip differs")
    replay_ticks = 0
    max_residual = max_relative = max_tick_waste = 0.
    flow = sum(a.inventory for a in state.agents) + sum(p.stock for p in state.patches)
    weather = hashlib.sha256()
    for tick in range(horizon):
        # This is the complete policy input boundary. Nothing from the
        # evaluator-only columns below is merged into an observation packet.
        packets = observations(state)
        actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        result = step(state, actions)
        if resumed is not None:
            replayed = step(resumed, actions)
            if replayed != result:
                raise ValueError("physical snapshot continuation differs under the same committed actions")
            resumed = replayed.state
            replay_ticks += 1
        state, ledger = result.state, result.ledger
        flow += ledger.growth + ledger.consumption + ledger.movement_cost + ledger.message_cost + ledger.harvest_cost + ledger.waste
        residual = max(abs(ledger.residual), *(abs(a.residual) for a in ledger.agents), *(abs(p.residual) for p in ledger.patches))
        max_residual = max(max_residual, residual)
        max_relative = max(max_relative, residual / max(1., flow))
        max_tick_waste = max(max_tick_waste, ledger.waste)
        if residual > LEDGER_RELATIVE_TOLERANCE * max(1., flow):
            raise ValueError("material accounting failed")
        if ledger.waste > WASTE_ABSOLUTE_TOLERANCE:
            raise ValueError("capacity-aware forager wasted extracted resources")
        for row in ledger.agents:
            movement_steps[row.id] += int(row.moved)
            if quarter3_start <= tick < late_start:
                quarter3_consumption[row.id] += row.consumption
            if tick >= late_start:
                late_consumption[row.id] += row.consumption
                late_shortfall[row.id] += row.shortfall
            if 192 <= tick < 256:
                prefix256_late[row.id] += row.consumption
        for row in ledger.patches:
            weather.update(canonical([row.weather_event_id, row.weather]))
        unaffordable = 0
        for agent, policy in zip(state.agents, policies):
            if (agent.x, agent.y) not in site_cells and policy.sites:
                distance = min(abs(agent.x - x) + abs(agent.y - y) for x, y in policy.sites.values())
                unaffordable += int(agent.inventory < cfg.movement_cost * distance)
        if unaffordable:
            raise ValueError("forager lost its prospective known-return fuel invariant")
        occupied = {(agent.x, agent.y) for agent in state.agents}
        off_site = {agent.id for agent in state.agents if (agent.x, agent.y) not in site_cells}
        cohort_ticks = {kind: {"n": len(ids),
                              "consumption": sum(ledger.agents[i].consumption for i in ids),
                              "shortfall": sum(ledger.agents[i].shortfall for i in ids),
                              "inventory": sum(state.agents[i].inventory for i in ids)}
                        for kind, ids in members.items()}
        trajectory.append({
            "tick": state.tick, "consumption": ledger.consumption,
            "shortfall": sum(a.shortfall for a in ledger.agents),
            "stock": result.metrics.stocks, "reserves": result.metrics.reserves,
            "growth": ledger.growth, "growth_waste": ledger.growth_waste,
            "movement_cost": ledger.movement_cost, "message_cost": ledger.message_cost,
            "harvest_cost": ledger.harvest_cost, "waste": ledger.waste,
            "moves": sum(a.moved for a in ledger.agents), "unaffordable_known_returns": unaffordable,
            "off_site_agents": len(off_site),
            "hungry_off_site_agents": sum(a.id in off_site and a.shortfall > 0 for a in ledger.agents),
            "unoccupied_stock_fraction": sum(p.stock for p in state.patches if (p.x, p.y) not in occupied)
                                         / (cfg.n_patches * cfg.patch_capacity),
            "mean_known_sites": statistics.mean(len(policy.sites) for policy in policies),
            "depleted_patches": sum(p.stock < DEPLETION_FRACTION * cfg.patch_capacity for p in state.patches),
            "accounting_residual": ledger.residual, "accounting_cumulative_flow": flow,
            "cohorts": cohort_ticks,
            "agent_positions": [[a.x, a.y] for a in state.agents],
            "agent_inventory": [a.inventory for a in state.agents],
            "agent_known_sites": [len(policy.sites) for policy in policies],
            "agent_moved": [a.moved for a in ledger.agents],
            **{"agent_" + field: [getattr(a, field) for a in ledger.agents] for field in AGENT_TICK_FIELDS},
            "site_stock": [p.stock for p in state.patches],
            "site_residual": [p.residual for p in ledger.patches],
        })
        if spatial and state.tick in frame_ticks:
            frames.append(_frame(state, kinds))
        if state.tick == 256:
            prefix256 = {
                "prefix256_consumption_per_agent_tick": statistics.mean(a.consumption / 256 for a in state.agents),
                "prefix256_late_consumption_per_agent_tick": statistics.mean(value / 64 for value in prefix256_late),
                "prefix256_terminal_stock_fraction": result.metrics.stocks / (cfg.n_patches * cfg.patch_capacity),
            }
        if spatial and state.tick == checkpoint_tick:
            checkpoint = snapshot(state)
            resumed = restore(checkpoint)
            if resumed != state:
                raise ValueError("physical snapshot round-trip differs")
    if spatial and (resumed != state or replay_ticks != horizon - checkpoint_tick):
        raise ValueError("physical snapshot continuation coverage is incomplete")
    agents = []
    for agent in state.agents:
        identity = agent.id
        agents.append({
            "id": identity, "policy": kinds[identity],
            "consumption": agent.consumption, "shortfall": agent.shortfall,
            "consumption_per_tick": agent.consumption / horizon,
            "shortfall_per_tick": agent.shortfall / horizon,
            "quarter3_consumption": quarter3_consumption[identity],
            "quarter3_consumption_per_tick": quarter3_consumption[identity] / quarter3_count if quarter3_count else None,
            "late_consumption": late_consumption[identity], "late_shortfall": late_shortfall[identity],
            "late_consumption_per_tick": late_consumption[identity] / late_count,
            "late_shortfall_per_tick": late_shortfall[identity] / late_count,
            "terminal_inventory": agent.inventory, "movement_steps": movement_steps[identity],
            "movement_cost": agent.movement_cost, "message_cost": agent.message_cost,
            "harvested": agent.harvested, "harvest_cost": agent.harvest_cost, "waste": agent.waste,
            "transfer_in": agent.transfer_in, "transfer_out": agent.transfer_out,
            "terminal_known_sites": len(policies[identity].sites),
            "utility": {str(weight): (agent.consumption + weight * agent.inventory) / horizon for weight in WEIGHTS},
        })
    mean = lambda field: statistics.mean(a[field] for a in agents)
    persistent_longest = persistent_run = 0
    for row in trajectory[horizon // 2:]:
        persistent_run = persistent_run + 1 if 2 * row["depleted_patches"] >= cfg.n_patches else 0
        persistent_longest = max(persistent_longest, persistent_run)
    summary = {
        "consumption_per_agent_tick": mean("consumption_per_tick"),
        "shortfall_per_agent_tick": mean("shortfall_per_tick"),
        "quarter3_consumption_per_agent_tick": mean("quarter3_consumption_per_tick") if quarter3_count else None,
        "late_consumption_per_agent_tick": mean("late_consumption_per_tick"),
        "late_shortfall_per_agent_tick": mean("late_shortfall_per_tick"),
        "terminal_inventory_per_agent": mean("terminal_inventory"),
        "terminal_stock_fraction": trajectory[-1]["stock"] / (cfg.n_patches * cfg.patch_capacity),
        "late_stock_fraction": statistics.mean(row["stock"] / (cfg.n_patches * cfg.patch_capacity) for row in trajectory[-late_count:]),
        "depleted_patch_time_fraction": sum(row["depleted_patches"] for row in trajectory) / (horizon * cfg.n_patches),
        "late_depleted_patch_time_fraction": sum(row["depleted_patches"] for row in trajectory[-late_count:]) / (late_count * cfg.n_patches),
        "persistent_depletion_longest_ticks": persistent_longest,
        "persistent_depletion_threshold_ticks": horizon / 8,
        "movement_steps_per_agent": mean("movement_steps"),
        "total_movement_cost": sum(a.movement_cost for a in state.agents),
        "total_message_cost": sum(a.message_cost for a in state.agents),
        "total_harvest_cost": sum(a.harvest_cost for a in state.agents),
        "total_waste": sum(a.waste for a in state.agents),
        "max_tick_waste": max_tick_waste,
        "max_unaffordable_known_returns": max(row["unaffordable_known_returns"] for row in trajectory),
        "mean_off_site_agent_fraction": statistics.mean(row["off_site_agents"] / cfg.n_agents for row in trajectory),
        "mean_hungry_off_site_agent_fraction": statistics.mean(row["hungry_off_site_agents"] / cfg.n_agents for row in trajectory),
        "terminal_unoccupied_stock_fraction": trajectory[-1]["unoccupied_stock_fraction"],
        "terminal_mean_known_sites": trajectory[-1]["mean_known_sites"],
        "max_ledger_residual": max_residual, "max_relative_ledger_residual": max_relative,
        **prefix256,
    }
    cohort_fields = ("consumption_per_tick", "shortfall_per_tick", "late_consumption_per_tick",
                     "late_shortfall_per_tick", "terminal_inventory")
    cohorts = {kind: {
        "n": len(ids),
        "consumption": sum(agents[i]["consumption"] for i in ids),
        "shortfall": sum(agents[i]["shortfall"] for i in ids),
        "inventory": sum(agents[i]["terminal_inventory"] for i in ids),
        **{field: _mean_or_none(agents[i][field] for i in ids) for field in cohort_fields},
        "utility": {str(weight): _mean_or_none(agents[i]["utility"][str(weight)] for i in ids) for weight in WEIGHTS},
    } for kind, ids in members.items()}
    bindings = {"case": case, "control": control, "aggressive_ids": aggressive_ids}
    return {
        "version": VERSION, **bindings, "aggressive_count": len(aggressive_ids), "input_sha256": _digest(bindings),
        "summary": summary, "agents": agents, "cohorts": cohorts, "trajectory": trajectory,
        "site_layout": site_layout, "spatial_frames": frames,
        "initial_state_sha256": initial_state_sha256, "weather_sha256": weather.hexdigest(),
        "final_state_sha256": snapshot(state)["sha256"],
        "late_window": {"start_tick": late_start + 1, "end_tick": horizon, "ticks": late_count},
        "quarter3_window": {"start_tick": quarter3_start + 1 if quarter3_count else None,
                            "end_tick": late_start if quarter3_count else None, "ticks": quarter3_count},
        "checkpoint_continuation_checked": spatial,
        "checkpoint_continuation": {
            "checkpoint_tick": checkpoint_tick if spatial else None,
            "checkpoint_sha256": checkpoint["sha256"] if spatial else None,
            "future_ticks_checked": replay_ticks, "verified": spatial,
            "scope": "Exact physical states, ledgers and metrics under identical future committed actions; policy memory is not restored.",
        },
    }
