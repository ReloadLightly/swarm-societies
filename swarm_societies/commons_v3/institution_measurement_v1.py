"""Evaluator-only measurements for the first institutional development study.

Nothing in this module is a policy observation. Political custody, actual
violations, and original-cohort outcomes require evaluator state and must never
be fed back to a controller. Consumption already reflects material costs;
reporting those costs separately does not authorize subtracting them again.
"""
from __future__ import annotations

from copy import deepcopy
import math
import statistics

from . import politics_v1 as politics


VERSION = "commons-v3-institution-measurement-v1"
UTILITY_WEIGHTS = (0., .05, .2)
DEPLETION_FRACTION = .1
PHYSICAL_FLOWS = ("consumption", "shortfall", "harvested", "movement_cost",
                  "message_cost", "harvest_cost", "waste", "transfer_in", "transfer_out")
POLITICAL_FLOWS = ("political_fee_private", "political_fee_treasury_operator",
                   "collateral_forfeited", "bond_deposit", "dues_contribution",
                   "cache_deposit", "claim_withdrawal", "cache_retrieval")
FLOW_FIELDS = PHYSICAL_FLOWS + POLITICAL_FLOWS
CUSTODY_FIELDS = ("cache", "active_bond", "released_claim", "mature_claim")


def _mean(values):
    values = list(values)
    return statistics.mean(values) if values else None


def _custody(state):
    rows = [{name: 0. for name in CUSTODY_FIELDS} for _ in state.world.agents]
    for cache in state.caches:
        rows[cache.owner]["cache"] += cache.amount
    for institution in state.institutions:
        for bond in institution.bonds:
            key = "active_bond" if bond.release_tick is None else "released_claim"
            rows[bond.owner][key] += bond.amount
            if bond.release_tick is not None and bond.release_tick <= state.world.tick:
                rows[bond.owner]["mature_claim"] += bond.amount
    return rows


def _ownership(state):
    """Diagnostic title to resources, without liquidation or accessibility.

    Current members share the pooled treasury equally; a final-recipient
    correction preserves its amount despite floating-point division. Released
    claims remain with their owner. This book convention is prospective and
    separate from the frozen carried-inventory utility definition.
    """
    custody = _custody(state)
    shares = [0.] * len(state.world.agents)
    for institution in state.institutions:
        remaining = institution.treasury
        for position, member in enumerate(institution.members):
            amount = remaining if position == len(institution.members) - 1 else institution.treasury / len(institution.members)
            shares[member] += amount
            remaining -= amount
    return [{"inventory": agent.inventory, **custody[agent.id], "pooled_treasury_share": shares[agent.id],
             "book_wealth": math.fsum((agent.inventory, custody[agent.id]["cache"], custody[agent.id]["active_bond"],
                                      custody[agent.id]["released_claim"], shares[agent.id]))}
            for agent in state.world.agents]


def record_tick(before, result, actions, intents):
    """Record actual tick flows, local roles, and separately funded operations.

    Opening membership and the after-movement site define quota obligations.
    A joining agent is not retroactively bound; an exiting member remains bound
    during their final tick. Monitoring receipts deduplicate multiple witnesses
    and never turn an outsider's extraction into an institutional violation.
    """
    after, physical = result.state, result.physical.ledger
    n, tick = len(before.world.agents), before.world.tick
    if (after.world.tick != tick + 1 or result.ledger.tick != tick or physical.tick != tick
            or len(actions) != n or len(intents) != n or len(after.world.agents) != n):
        raise ValueError("measurement requires one complete matching decision round")
    opening = {actor: institution for institution in before.institutions for actor in institution.members}
    closing = {actor: institution for institution in after.institutions for actor in institution.members}
    sites = {(site.x, site.y): site.id for site in after.world.patches}
    institutional_sites = {institution.site_id for institution in before.institutions if institution.active}
    custody = _custody(after)
    flows = [{name: 0. for name in POLITICAL_FLOWS} for _ in range(n)]
    kind_field = {"bond": "bond_deposit", "dues": "dues_contribution", "cache": "cache_deposit",
                  "withdraw": "claim_withdrawal", "retrieve": "cache_retrieval"}
    for entry in result.ledger.entries:
        actor, amount, kind = entry["actor"], entry["amount"], entry["kind"]
        if kind == "fee":
            field = "political_fee_private" if entry["source"] == "private" else "political_fee_treasury_operator"
        elif kind == "forfeit":
            actor, field = entry["subject"], "collateral_forfeited"
        elif kind in kind_field:
            field = kind_field[kind]
        else:
            raise ValueError("unrecognized political ledger entry")
        flows[actor][field] += amount
    observed = {(e.institution, e.subject, e.observed_tick) for e in after.evidence
                if e.observed_tick == tick and e.institution is not None and e.harvested > e.quota + 1e-12}
    receipts = {(e.subject, e.observed_tick) for e in after.evidence if e.observed_tick == tick}
    agents = []
    for agent, ledger, action, intent in zip(after.world.agents, physical.agents, actions, intents):
        identity = agent.id
        own, end_own = opening.get(identity), closing.get(identity)
        before_agent = before.world.agents[identity]
        site = sites.get((agent.x, agent.y))
        bound = own is not None and own.site_id == site
        violation = bool(bound and ledger.harvested > own.charter.quota + 1e-12)
        row = {"id": identity, "inventory": agent.inventory, "custody": custody[identity],
               **{name: getattr(ledger, name) for name in PHYSICAL_FLOWS}, **flows[identity],
               "membership_before": None if own is None else own.id,
               "membership_after": None if end_own is None else end_own.id,
               "site_before": sites.get((before_agent.x, before_agent.y)), "site_after": site,
               "at_affiliated_site_before": bool(own is not None and own.site_id == sites.get((before_agent.x, before_agent.y))),
               "at_affiliated_site_after": bound,
               "nonmember_at_institutional_site": own is None and site in institutional_sites,
               "outside_own_institution_at_site": site in institutional_sites and not bound,
               "off_site": site is None, "hungry_off_site": site is None and ledger.shortfall > 0.,
               "requested_harvest": action.harvest, "bound_quota": own.charter.quota if bound else None,
               "actual_violation": violation, "observed_violation": bool(violation and (own.id, identity, tick) in observed),
               "extraction_observed": (identity, tick) in receipts, "intent": intent.kind}
        agents.append(row)
    active_before = {institution.id for institution in before.institutions if institution.active}
    active_after = {institution.id for institution in after.institutions if institution.active}
    occupied = {row["site_after"] for row in agents if row["site_after"] is not None}
    stock = math.fsum(site.stock for site in after.world.patches)
    return {"version": VERSION, "tick": tick, "agents": agents,
            "stock": stock, "stock_fraction": stock / (after.world.config.n_patches * after.world.config.patch_capacity),
            "depleted_patch_fraction": sum(site.stock < DEPLETION_FRACTION * after.world.config.patch_capacity
                                            for site in after.world.patches) / after.world.config.n_patches,
            "unoccupied_stock": math.fsum(site.stock for site in after.world.patches if site.id not in occupied),
            "active_institutions": sorted(active_after), "activated_institutions": sorted(active_after - active_before),
            "deactivated_institutions": sorted(active_before - active_after),
            "pooled_treasury": math.fsum(institution.treasury for institution in after.institutions),
            "custody_total": politics.custody(after), "political_cost": result.ledger.political_cost,
            "forfeited": result.ledger.forfeited, "physical_residual": physical.residual,
            "material_residual": result.ledger.residual,
            "events": deepcopy(list(result.events)), "political_entries": deepcopy(list(result.ledger.entries))}


def _gini(values):
    total, n = math.fsum(values), len(values)
    if not n:
        return None
    if total == 0.:
        return 0.
    ordered = sorted(values)
    return math.fsum((2 * rank - n - 1) * value for rank, value in enumerate(ordered, 1)) / (n * total)


def _quantile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(values) - 1) * q
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def summarize(initial, final, records, *, cohorts, late_window=64):
    """Aggregate original IDs, preserving exiters and empty cohorts.

    ``cohorts`` must be declared from original IDs, never from later membership.
    Overlap between named original cohorts is allowed; the all-population cohort
    is always included. Dynamic member/nonmember averages are labeled separately
    because their changing denominators cannot estimate an entry benefit.
    """
    n = len(initial.world.agents)
    horizon = final.world.tick - initial.world.tick
    if (horizon <= 0 or len(records) != horizon or len(final.world.agents) != n
            or type(late_window) is not int or late_window < 1):
        raise ValueError("a nonempty complete trajectory and positive late window are required")
    if initial.world.config != final.world.config or initial.config != final.config:
        raise ValueError("episode configuration changed")
    for offset, record in enumerate(records):
        if (record["version"] != VERSION or record["tick"] != initial.world.tick + offset
                or [row["id"] for row in record["agents"]] != list(range(n))):
            raise ValueError("trajectory is incomplete or its agent order differs")
    if type(cohorts) is not dict:
        raise ValueError("original cohorts must be a mapping")
    bound_cohorts = {"population": list(range(n))}
    for name, identities in cohorts.items():
        if type(name) is not str or not name or type(identities) not in (list, tuple):
            raise ValueError("cohort names and original identity lists are required")
        ids = list(identities)
        if any(type(identity) is not int or not 0 <= identity < n for identity in ids) or len(set(ids)) != len(ids):
            raise ValueError("cohort identities must be unique original individuals")
        if name == "population" and sorted(ids) != list(range(n)):
            raise ValueError("population cohort must retain every original individual")
        bound_cohorts[name] = sorted(ids)
    late_count = min(late_window, horizon)
    custody = _custody(final)
    initial_wealth, terminal_wealth = _ownership(initial), _ownership(final)
    need = final.world.config.need
    agents = []
    for identity, final_agent in enumerate(final.world.agents):
        rows = [record["agents"][identity] for record in records]
        flows = {name: math.fsum(row[name] for row in rows) for name in FLOW_FIELDS}
        initial_agent = initial.world.agents[identity]
        if any(not math.isclose(flows[name], getattr(final_agent, name) - getattr(initial_agent, name),
                                rel_tol=1e-9, abs_tol=1e-9) for name in PHYSICAL_FLOWS):
            raise ValueError("recorded physical totals differ from endpoint counters")
        if rows[-1]["inventory"] != final_agent.inventory or rows[-1]["custody"] != custody[identity]:
            raise ValueError("recorded final ownership differs from endpoint state")
        # Keep the frozen carried convention alongside the prospective book
        # ownership diagnostic. Neither changes policies or realized resources.
        utility = {str(weight): (flows["consumption"] + weight * final_agent.inventory) / horizon
                   for weight in UTILITY_WEIGHTS}
        book_utility = {str(weight): (flows["consumption"] + weight * terminal_wealth[identity]["book_wealth"]) / horizon
                        for weight in UTILITY_WEIGHTS}
        late_consumption = math.fsum(row["consumption"] for row in rows[-late_count:]) / late_count
        agents.append({"id": identity, **flows,
            "consumption_per_tick": flows["consumption"] / horizon,
            "shortfall_per_tick": flows["shortfall"] / horizon,
            "late_consumption_per_tick": late_consumption,
            "late_shortfall_per_tick": math.fsum(row["shortfall"] for row in rows[-late_count:]) / late_count,
            "consumption_need_fraction": flows["consumption"] / (horizon * need) if need > 0. else None,
            "late_consumption_need_fraction": late_consumption / need if need > 0. else None,
            "terminal_inventory": final_agent.inventory, "terminal_custody": custody[identity],
            "initial_wealth": initial_wealth[identity], "terminal_wealth": terminal_wealth[identity],
            "terminal_book_wealth": terminal_wealth[identity]["book_wealth"],
            "carried_utility": utility, "book_utility": book_utility,
            "carried_utility_need_fraction": {key: value / need if need > 0. else None for key, value in utility.items()},
            "book_utility_need_fraction": {key: value / need if need > 0. else None for key, value in book_utility.items()},
            "inventory_utility_component": {str(weight): weight * final_agent.inventory / horizon for weight in UTILITY_WEIGHTS},
            "membership_ticks": sum(row["membership_before"] is not None for row in rows),
            "ever_member": any(row["membership_before"] is not None or row["membership_after"] is not None for row in rows),
            "terminal_membership": rows[-1]["membership_after"],
            "entry_count": sum(row["membership_before"] is None and row["membership_after"] is not None for row in rows),
            "exit_count": sum(row["membership_before"] is not None and row["membership_after"] is None for row in rows),
            "actual_violations": sum(row["actual_violation"] for row in rows),
            "observed_violations": sum(row["observed_violation"] for row in rows),
            "off_site_ticks": sum(row["off_site"] for row in rows),
            "hungry_off_site_ticks": sum(row["hungry_off_site"] for row in rows),
            "off_site_shortfall": math.fsum(row["shortfall"] for row in rows if row["off_site"]),
            "nonmember_at_institutional_site_ticks": sum(row["nonmember_at_institutional_site"] for row in rows)})
    means = ("consumption_per_tick", "shortfall_per_tick", "late_consumption_per_tick",
             "late_shortfall_per_tick", "terminal_inventory", "terminal_book_wealth")
    cohort_results = {}
    for name, ids in bound_cohorts.items():
        selected = [agents[identity] for identity in ids]
        cohort_results[name] = {"ids": ids, "n": len(ids),
            **{field: math.fsum(agent[field] for agent in selected) for field in FLOW_FIELDS},
            **{field: _mean(agent[field] for agent in selected) for field in means},
            "consumption_need_fraction": _mean(agent["consumption_need_fraction"] for agent in selected) if need > 0. else None,
            "late_consumption_need_fraction": _mean(agent["late_consumption_need_fraction"] for agent in selected) if need > 0. else None,
            "carried_utility": {str(weight): _mean(agent["carried_utility"][str(weight)] for agent in selected) for weight in UTILITY_WEIGHTS},
            "book_utility": {str(weight): _mean(agent["book_utility"][str(weight)] for agent in selected) for weight in UTILITY_WEIGHTS},
            "carried_utility_need_fraction": {str(weight): _mean(agent["carried_utility_need_fraction"][str(weight)] for agent in selected)
                                               if need > 0. else None for weight in UTILITY_WEIGHTS},
            "book_utility_need_fraction": {str(weight): _mean(agent["book_utility_need_fraction"][str(weight)] for agent in selected)
                                            if need > 0. else None for weight in UTILITY_WEIGHTS},
            "initial_wealth_totals": {field: math.fsum(agent["initial_wealth"][field] for agent in selected) for field in initial_wealth[0]},
            "terminal_wealth_totals": {field: math.fsum(agent["terminal_wealth"][field] for agent in selected) for field in terminal_wealth[0]},
            "terminal_custody": {field: math.fsum(agent["terminal_custody"][field] for agent in selected) for field in CUSTODY_FIELDS},
            "ever_members": sum(agent["ever_member"] for agent in selected),
            "terminal_members": sum(agent["terminal_membership"] is not None for agent in selected),
            "entry_count": sum(agent["entry_count"] for agent in selected),
            "exit_count": sum(agent["exit_count"] for agent in selected),
            "actual_violations": sum(agent["actual_violations"] for agent in selected),
            "observed_violations": sum(agent["observed_violations"] for agent in selected),
            "shortfall_gini": _gini([agent["shortfall"] for agent in selected]),
            "shortfall_per_tick_p90": _quantile([agent["shortfall_per_tick"] for agent in selected], .9),
            "shortfall_per_tick_max": max((agent["shortfall_per_tick"] for agent in selected), default=None)}
    dynamic = {}
    for name, member in (("member", True), ("nonmember", False)):
        rows = [row for record in records for row in record["agents"] if (row["membership_before"] is not None) == member]
        dynamic[name] = {"agent_ticks": len(rows), "consumption_per_agent_tick": _mean(row["consumption"] for row in rows),
                         "shortfall_per_agent_tick": _mean(row["shortfall"] for row in rows)}
    event_counts = {}
    for record in records:
        for event in record["events"]:
            key = event["kind"] + ("_success" if event["ok"] else "_failure")
            event_counts[key] = event_counts.get(key, 0) + 1
    treasury = math.fsum(institution.treasury for institution in final.institutions)
    political_cost = math.fsum(record["political_cost"] for record in records)
    forfeited = math.fsum(record["forfeited"] for record in records)
    attributed_fees = math.fsum(agent["political_fee_private"] + agent["political_fee_treasury_operator"] for agent in agents)
    attributed_forfeits = math.fsum(agent["collateral_forfeited"] for agent in agents)
    if (not math.isclose(political_cost, final.political_cost - initial.political_cost, rel_tol=1e-9, abs_tol=1e-9)
            or not math.isclose(forfeited, final.forfeited - initial.forfeited, rel_tol=1e-9, abs_tol=1e-9)
            or not math.isclose(political_cost, attributed_fees, rel_tol=1e-9, abs_tol=1e-9)
            or not math.isclose(forfeited, attributed_forfeits, rel_tol=1e-9, abs_tol=1e-9)):
        raise ValueError("recorded political costs differ from endpoint counters or actor attribution")
    return {"version": VERSION, "start_tick": initial.world.tick, "end_tick": final.world.tick, "ticks": horizon,
            "late_window": {"start_tick": final.world.tick - late_count, "end_tick_exclusive": final.world.tick, "ticks": late_count},
            "agents": agents, "cohorts": cohort_results, "dynamic_membership_diagnostics": dynamic,
            "initial": {**{field: math.fsum(row[field] for row in initial_wealth) for field in initial_wealth[0]},
                "custody_total": politics.custody(initial)},
            "terminal": {"inventory": math.fsum(agent.inventory for agent in final.world.agents),
                **{field: math.fsum(row[field] for row in custody) for field in CUSTODY_FIELDS},
                "pooled_treasury": treasury, "custody_total": politics.custody(final),
                "book_wealth": math.fsum(row["book_wealth"] for row in terminal_wealth),
                "stock": records[-1]["stock"], "stock_fraction": records[-1]["stock_fraction"],
                "depleted_patch_fraction": records[-1]["depleted_patch_fraction"],
                "active_institutions": len(records[-1]["active_institutions"])},
            "mean_stock_fraction": _mean(record["stock_fraction"] for record in records),
            "late_mean_stock_fraction": _mean(record["stock_fraction"] for record in records[-late_count:]),
            "mean_depleted_patch_fraction": _mean(record["depleted_patch_fraction"] for record in records),
            "late_mean_depleted_patch_fraction": _mean(record["depleted_patch_fraction"] for record in records[-late_count:]),
            "political_cost": political_cost, "forfeited": forfeited,
            "max_material_residual": max(abs(record["material_residual"]) for record in records),
            "institution_free_ticks": sum(not record["active_institutions"] for record in records),
            "institution_activations": sum(len(record["activated_institutions"]) for record in records),
            "institution_deactivations": sum(len(record["deactivated_institutions"]) for record in records),
            "event_counts": dict(sorted(event_counts.items())),
            "utility_scope": "Carried utility preserves the frozen private-inventory convention. Book utility additionally attributes caches, bonds, released claims and equal current-member shares of pooled treasury at unchanged weights; it is a diagnostic accounting convention, not redeemed consumption or guaranteed accessible, fine-free wealth.",
            "membership_scope": "Declared original IDs retain exiters; dynamic membership averages are descriptive and selected."}
