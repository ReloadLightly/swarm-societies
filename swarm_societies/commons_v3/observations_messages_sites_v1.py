"""Own-harvest observation affordance for every arm of the messaging study.

The contracted receipt arm needs each individual to know its own realized
extraction. That outcome is not generally recoverable from inventory after
consumption or overflow. This adapter exposes only that individual's preceding
gross harvest, equally to every arm, while retaining the frozen physical step.
It is an explicit observation addition, not extra inference from the v2 packet.
"""

from copy import deepcopy
import math

from . import engine_sites_v1 as engine


VERSION = "commons-v3-own-harvest-observation-v1"
RECEIPT_VERSION = "commons-v3-private-harvest-v1"
FIELDS = {"version", "tick", "agent", "harvested"}


def validate_private_harvest(receipt, observation):
    if receipt is None:
        return None
    if (type(receipt) is not dict or set(receipt) != FIELDS
            or receipt["version"] != RECEIPT_VERSION
            or type(receipt["tick"]) is not int or not 0 <= receipt["tick"] == observation["tick"] - 1
            or type(receipt["agent"]) is not int or receipt["agent"] != observation["self"]["id"]):
        raise ValueError("private harvest receipt identity, version or time differs")
    amount = receipt["harvested"]
    if (type(amount) not in (int, float) or not 0 <= amount <= observation["self"]["max_harvest"]
            or not math.isfinite(amount)):
        raise ValueError("private harvest receipt is outside the own physical bound")
    return dict(receipt)


def private_harvest_receipts(result):
    """Project exact per-step agent ledger amounts, never cumulative differences."""
    if type(result) is not engine.StepResult or result.ledger.tick != result.state.tick - 1:
        raise ValueError("expected the preceding physical StepResult")
    if len(result.ledger.agents) != len(result.state.agents):
        raise ValueError("one private receipt is required per individual")
    receipts = []
    for identity, row in enumerate(result.ledger.agents):
        if row.id != identity:
            raise ValueError("private harvest ledger IDs are not canonical")
        receipt = {"version": RECEIPT_VERSION, "tick": result.ledger.tick,
                   "agent": identity, "harvested": row.harvested}
        context = {"tick": result.state.tick,
                   "self": {"id": identity, "max_harvest": result.state.config.max_harvest}}
        receipts.append(validate_private_harvest(receipt, context))
    return tuple(receipts)


def attach_private_harvest(packet, receipt):
    if type(packet) is not dict or packet.get("observation_version") != engine.OBSERVATION_VERSION:
        raise ValueError("expected the base v2 local observation")
    own = validate_private_harvest(receipt, packet)
    return {**deepcopy(packet), "adapter_version": VERSION, "private_harvest": own}


def observations(state, previous_result_or_feedback=None):
    """Return detached local packets with strictly private preceding outcomes.

``None`` explicitly starts an observation history without a preceding outcome,
including a fresh start from a supplied physical snapshot. Continuations pass
the preceding StepResult or its projected receipt tuple.
    """
    packets = engine.observations(state)
    source = previous_result_or_feedback
    if source is None:
        receipts = (None,) * len(packets)
    elif type(source) is engine.StepResult:
        if source.state != state:
            raise ValueError("feedback result does not produce the observed state")
        receipts = private_harvest_receipts(source)
    elif type(source) in (tuple, list) and len(source) == len(packets):
        if any(row is None for row in source):
            raise ValueError("continued feedback must contain every own receipt")
        receipts = source
    else:
        raise ValueError("expected one private receipt per individual")
    return tuple(attach_private_harvest(packet, receipt) for packet, receipt in zip(packets, receipts))
