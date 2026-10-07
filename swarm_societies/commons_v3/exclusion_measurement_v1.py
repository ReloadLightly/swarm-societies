"""Evaluator-only cohort accounting for costly exclusion, version 1.

Never pass these aggregates or other individuals' ledger rows to a policy.
An experiment must fix ``original_member_ids`` before its paired treatments;
current membership summaries alone confound effects with entry and exit.
"""
from __future__ import annotations

from dataclasses import asdict
import math

from . import exclusion_v1 as exclusion


VERSION = "commons-v3-exclusion-measurement-v1"


def summarize_step(before, result, original_member_ids):
    """Project one transition, retaining costs and outcomes in physical units.

    The original cohort is a supplied, fixed reference group, not necessarily
    the treatment's current membership. Empty groups have count zero and sums
    zero; no mean or benefit is imputed. Blocked requests are not lost harvest
    or causal outsider costs. Costs already reduce consumption/inventory and
    must not be deducted a second time from realized welfare.
    """
    if type(before) is not exclusion.State or type(result) is not exclusion.Result:
        raise ValueError("an exclusion transition is required")
    n = before.political.world.config.n_agents
    ids = tuple(original_member_ids)
    if (any(type(i) is not int or not 0 <= i < n for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("original cohort requires distinct valid identities")
    if (result.ledger.tick != before.political.world.tick
            or result.state.political.world.tick != before.political.world.tick + 1
            or result.state.political.world.config != before.political.world.config
            or result.state.political.world.seed != before.political.world.seed
            or len(result.ledger.agents) != n
            or tuple(row.id for row in result.ledger.agents) != tuple(range(n))
            or result.state.political != result.political.state):
        raise ValueError("transition boundary differs")
    opening_members = {a for i in before.political.institutions if i.active for a in i.members}
    original_members = set(ids)
    rows = [asdict(row) for row in result.ledger.agents]
    agents = result.state.political.world.agents
    physical_costs = ("movement_cost", "message_cost", "harvest_cost", "waste")
    political_flows = ("political_fee_private", "dues_contribution", "collateral_forfeited")
    for row, physical in zip(rows, result.political.physical.ledger.agents):
        row.update({name: getattr(physical, name) for name in physical_costs})
        row.update({name: 0. for name in political_flows})
    for entry in result.political.ledger.entries:
        if entry["kind"] == "fee" and entry["source"] == "private":
            rows[entry["actor"]]["political_fee_private"] += entry["amount"]
        elif entry["kind"] == "dues":
            rows[entry["actor"]]["dues_contribution"] += entry["amount"]
        elif entry["kind"] == "forfeit":
            rows[entry["subject"]]["collateral_forfeited"] += entry["amount"]
    sums = ("requested_harvest", "effective_harvest", "guard_foregone_request",
            "blocked_request", "guard_cost", "resistance_cost", "harvested",
            "consumption", "shortfall", *physical_costs, *political_flows)

    def aggregate(indices):
        return {"count": len(indices),
                **{field: math.fsum(rows[i][field] for i in indices) for field in sums},
                "inventory_after": math.fsum(agents[i].inventory for i in indices)}

    all_ids = set(range(n))
    partitions = {"population": all_ids,
                  "original_members": original_members,
                  "original_outsiders": all_ids - original_members,
                  "opening_members": opening_members,
                  "opening_outsiders": all_ids - opening_members}
    return {"version": VERSION, "tick": result.ledger.tick,
            "original_member_ids": sorted(original_members),
            "opening_member_ids": sorted(opening_members),
            "cohorts": {name: aggregate(sorted(group)) for name, group in partitions.items()},
            "stock_after": math.fsum(p.stock for p in result.state.political.world.patches),
            "custody_after": result.ledger.custody_after,
            "political_operating_cost": result.political.ledger.political_cost,
            "treasury_operating_cost": math.fsum(e["amount"] for e in result.political.ledger.entries
                if e["kind"] == "fee" and e["source"] == "treasury"),
            "material_residual": result.ledger.residual}
