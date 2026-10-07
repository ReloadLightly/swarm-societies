"""Private, one-step outcome receipts for the audited v2 political runner.

These are an explicit information affordance, supplied equally to every policy
in that runner. They describe only the recipient's own realized outcomes and
private costs. They expose neither other individuals' ledgers nor remote stock,
treasury expenditure, or evaluator measurements. Costs are bookkeeping fields;
they must not be subtracted again from consumption.
"""
from __future__ import annotations

from copy import deepcopy
import math


VERSION = "commons-v3-own-feedback-v2"
PHYSICAL_FIELDS = ("consumption", "shortfall", "harvested", "movement_cost",
                   "message_cost", "harvest_cost")
POLITICAL_FIELDS = ("political_fee_private", "dues_contribution", "collateral_forfeited")
FIELDS = frozenset(("version", "tick", "agent", *PHYSICAL_FIELDS, *POLITICAL_FIELDS))


def validate_private_receipt(receipt, *, tick, agent_id, need):
    """Check a receipt using only the recipient's allowed observation packet."""
    if receipt is None:
        return None
    if (type(receipt) is not dict or set(receipt) != FIELDS or receipt["version"] != VERSION
            or type(receipt["agent"]) is not int or receipt["agent"] != agent_id
            or type(receipt["tick"]) is not int or not 0 <= receipt["tick"] == tick - 1):
        raise ValueError("private feedback identity, schema, or time differs from observation")
    if any(type(receipt[key]) not in (int, float) or not math.isfinite(receipt[key])
           or receipt[key] < 0 for key in (*PHYSICAL_FIELDS, *POLITICAL_FIELDS)):
        raise ValueError("private feedback requires finite nonnegative outcomes")
    if not math.isclose(receipt["consumption"] + receipt["shortfall"], need,
                        rel_tol=1e-10, abs_tol=1e-10 * max(1., need)):
        raise ValueError("private feedback consumption and shortfall must account for need")
    return deepcopy(receipt)


def validate_feedback(state, feedback):
    """Validate/detach all receipts against a complete post-step state.

    An all-None list explicitly denotes a fresh start with no observed prior
    decision, even if the supplied physical state is already at a later tick.
    A continued episode has one receipt per individual for exactly the previous
    tick. Checks bound values and identities; they do not authenticate history.
    """
    cfg, tick = state.world.config, state.world.tick
    if type(feedback) not in (list, tuple) or len(feedback) != cfg.n_agents:
        raise ValueError("one private feedback receipt is required per individual")
    if all(row is None for row in feedback):
        return tuple(None for _ in feedback)
    tolerance = 1e-10 * max(1., cfg.need, cfg.max_harvest)
    bounds = {"consumption": cfg.need, "shortfall": cfg.need,
              "harvested": cfg.max_harvest, "movement_cost": cfg.movement_cost,
              "message_cost": cfg.max_messages * cfg.max_message_bytes * cfg.message_byte_cost,
              "harvest_cost": cfg.max_harvest * cfg.harvest_cost_per_unit,
              "political_fee_private": max(state.config.founding_cost,
                                            state.config.monitoring_cost,
                                            state.config.settlement_cost),
              "dues_contribution": min(cfg.inventory_capacity, state.config.treasury_capacity, 1e6),
              "collateral_forfeited": cfg.n_agents * 1e6}
    for identity, row in enumerate(feedback):
        validate_private_receipt(row, tick=tick, agent_id=identity, need=cfg.need)
        if (type(row) is not dict or set(row) != FIELDS or row["version"] != VERSION
                or type(row["agent"]) is not int or row["agent"] != identity
                or type(row["tick"]) is not int or not 0 <= row["tick"] == tick - 1):
            raise ValueError("private feedback identity, schema, or time differs from checkpoint")
        for key, maximum in bounds.items():
            value = row[key]
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 <= value <= maximum + tolerance):
                raise ValueError(f"private feedback {key} exceeds physical or custody bounds")
        if not math.isclose(row["consumption"] + row["shortfall"], cfg.need,
                            rel_tol=1e-10, abs_tol=tolerance):
            raise ValueError("private feedback consumption and shortfall must account for need")
        if not math.isclose(row["harvest_cost"], row["harvested"] * cfg.harvest_cost_per_unit,
                            rel_tol=1e-10, abs_tol=tolerance):
            raise ValueError("private feedback harvest cost differs from own extraction")
    return tuple(deepcopy(row) for row in feedback)


def feedback_from_result(result):
    """Project a committed step onto strictly private recipient receipts."""
    if result.ledger.tick != result.physical.ledger.tick:
        raise ValueError("physical and political receipt times differ")
    rows = [{"version": VERSION, "tick": result.physical.ledger.tick, "agent": row.id,
             **{name: getattr(row, name) for name in PHYSICAL_FIELDS},
             **{name: 0. for name in POLITICAL_FIELDS}}
            for row in result.physical.ledger.agents]
    for entry in result.ledger.entries:
        if entry["kind"] == "fee" and entry["source"] == "private":
            rows[entry["actor"]]["political_fee_private"] += entry["amount"]
        elif entry["kind"] == "dues":
            rows[entry["actor"]]["dues_contribution"] += entry["amount"]
        elif entry["kind"] == "forfeit":
            rows[entry["subject"]]["collateral_forfeited"] += entry["amount"]
    return validate_feedback(result.state, rows)
