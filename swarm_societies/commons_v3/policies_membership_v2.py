"""Supplied local opportunity and dissatisfaction rules for optional membership.

Uses the same decentralized coordinator with and without organization. Service
forecasts are static heuristics, not guaranteed bounds, optimal counterfactuals or
causal estimates. Own receipts are an explicit v2 information affordance; a
change in inventory is never interpreted as consumption. No frozen source is
modified, no treasury spending is treated as a private payment, and no terminal
utility coefficient is added or changed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import math

from .own_feedback_v2 import validate_private_receipt
from .policies_coordination_v2 import CoordinationPolicy
from .policies_institutions_v1 import _int, _number
from .politics_v1 import Charter, Intent


MEMBERSHIP_VERSION = "commons-v3-responsive-membership-policy-v2"
SCALARS = ("forecast_horizon", "minimum_stay", "poor_patience", "cooldown_ticks",
           "entry_reserve_ticks", "advantage_need_fraction", "shortfall_need_fraction",
           "private_cost_need_fraction")
INT_SCALARS = SCALARS[:4]
DECISIONS = {"none", "propose", "endorse", "refuse", "join", "exit", "withdraw", "retrieve"}


class MembershipPolicy:
    """Optional quota promises with prospective entry and responsive exit.

    There is no institutional preference bonus. Entry permits ties in predicted
    consumption service only if a protected liquid buffer survives all planned
    entry charges. Repeated dissatisfaction or a better local outside forecast
    triggers exit after the declared minimum stay. A failed forecast is allowed;
    neither it nor remaining in an institution proves beneficial membership.

    This first revision purchases no monitoring and pays no dues for an unused
    service. Existing v1 paid enforcement remains a separate supplied policy;
    its prospective mechanism controls are a later comparison.
    """

    def __init__(self, *, organization=True, coordinator=None, charter=None,
                 forecast_horizon=4, minimum_stay=4, poor_patience=3, cooldown_ticks=8,
                 entry_reserve_ticks=2., advantage_need_fraction=.05,
                 shortfall_need_fraction=.1, private_cost_need_fraction=.1):
        if type(organization) is not bool:
            raise ValueError("organization must be boolean")
        if coordinator is None:
            coordinator = CoordinationPolicy()
        if type(coordinator) is not CoordinationPolicy or coordinator.forager.aggressive:
            raise ValueError("membership requires an audited restrained coordinator")
        if charter is None:
            charter = Charter()
        if type(charter) is not Charter:
            raise ValueError("charter must be the audited Charter record")
        values = dict(forecast_horizon=forecast_horizon, minimum_stay=minimum_stay,
                      poor_patience=poor_patience, cooldown_ticks=cooldown_ticks,
                      entry_reserve_ticks=entry_reserve_ticks,
                      advantage_need_fraction=advantage_need_fraction,
                      shortfall_need_fraction=shortfall_need_fraction,
                      private_cost_need_fraction=private_cost_need_fraction)
        for name, value in values.items():
            if name in INT_SCALARS:
                _int(value, name, minimum=1, maximum=1024)
            else:
                _number(value, name, maximum=100.)
            setattr(self, name, value)
        self.organization, self.coordinator, self.charter = organization, coordinator, charter
        self.owner = self.last_tick = self.member_id = self.member_since = self.member_site = None
        self.bad_streak = self.cooldown_until = 0
        self.decisions = {}
        self.diagnostics = {}

    def memory(self):
        return {"version": MEMBERSHIP_VERSION, "organization": self.organization,
                "coordinator": self.coordinator.memory(), "charter": asdict(self.charter),
                **{name: getattr(self, name) for name in SCALARS},
                "owner": self.owner, "last_tick": self.last_tick,
                "member_id": self.member_id, "member_since": self.member_since, "member_site": self.member_site,
                "bad_streak": self.bad_streak, "cooldown_until": self.cooldown_until,
                "decisions": dict(sorted(self.decisions.items())),
                "diagnostics": deepcopy(self.diagnostics)}

    @classmethod
    def restore(cls, memory):
        keys = {"version", "organization", "coordinator", "charter", *SCALARS,
                "owner", "last_tick", "member_id", "member_since", "member_site", "bad_streak",
                "cooldown_until", "decisions", "diagnostics"}
        if type(memory) is not dict or set(memory) != keys or memory["version"] != MEMBERSHIP_VERSION:
            raise ValueError("unsupported membership memory")
        try:
            policy = cls(organization=memory["organization"],
                         coordinator=CoordinationPolicy.restore(memory["coordinator"]),
                         charter=Charter(**memory["charter"]),
                         **{name: memory[name] for name in SCALARS})
        except TypeError as error:
            raise ValueError("invalid membership configuration") from error
        for name in ("owner", "last_tick", "member_id", "member_since", "member_site"):
            value = memory[name]
            if value is not None:
                _int(value, name)
            setattr(policy, name, value)
        if (policy.owner is None) != (policy.last_tick is None):
            raise ValueError("membership owner and decision time must be present together")
        expected_tick = -1 if policy.last_tick is None else policy.last_tick
        if policy.owner != policy.coordinator.owner or expected_tick != policy.coordinator.last_tick:
            raise ValueError("membership and coordinator owner/time must agree")
        if (policy.member_id is None) != (policy.member_since is None):
            raise ValueError("membership identity and entry observation must be present together")
        if policy.member_site is not None and (policy.member_id is None or policy.member_site not in policy.coordinator.forager.sites):
            raise ValueError("remembered membership site must have been observed")
        for name in ("bad_streak", "cooldown_until"):
            setattr(policy, name, _int(memory[name], name))
        if policy.member_since is not None and (policy.last_tick is None or policy.member_since > policy.last_tick):
            raise ValueError("membership cannot predate its observed decision history")
        if (type(memory["decisions"]) is not dict
                or any(name not in DECISIONS for name in memory["decisions"])):
            raise ValueError("invalid membership decision counters")
        policy.decisions = {name: _int(value, "decision count", minimum=1)
                            for name, value in memory["decisions"].items()}
        d = memory["diagnostics"]
        if policy.last_tick is None:
            if d or policy.decisions or policy.member_id is not None or policy.bad_streak or policy.cooldown_until:
                raise ValueError("unobserved membership policy cannot contain decision history")
        else:
            expected = {"tick", "decision", "reason", "outside_rate", "member_rate",
                        "own_shortfall", "own_private_cost", "bad_streak", "planned_private_debit"}
            if type(d) is not dict or set(d) != expected or d["tick"] != policy.last_tick:
                raise ValueError("invalid membership diagnostic schema/time")
            if d["decision"] not in DECISIONS or d["reason"] not in REASONS:
                raise ValueError("unknown membership decision or reason")
            for name in ("outside_rate", "own_shortfall", "own_private_cost", "planned_private_debit"):
                _number(d[name], name)
            if d["member_rate"] is not None:
                _number(d["member_rate"], "member_rate")
            if type(d["bad_streak"]) is not int or d["bad_streak"] != policy.bad_streak:
                raise ValueError("diagnostic dissatisfaction differs from policy memory")
            if not 1 <= sum(policy.decisions.values()) <= policy.last_tick + 1:
                raise ValueError("membership decision count exceeds time")
        policy.diagnostics = deepcopy(d)
        if policy.memory() != memory:
            raise ValueError("membership memory must be canonical")
        return policy

    def validate_context(self, state, agent_id):
        self.restore(self.memory())
        self.coordinator.validate_context(state, agent_id)
        tick = state.world.tick
        if self.owner is not None and (self.owner != agent_id or self.last_tick != tick - 1):
            raise ValueError("membership owner/time differs from checkpoint")
        # member_id is the membership observed before the last decision; an
        # exit can legitimately remove it from current membership.
        if self.member_id is not None and self.member_id not in {i.id for i in state.institutions}:
            raise ValueError("remembered membership identity exceeds checkpoint")
        if self.member_site is not None and self.member_site >= state.world.config.n_patches:
            raise ValueError("remembered membership site exceeds checkpoint")
        if self.cooldown_until > tick + self.cooldown_ticks:
            raise ValueError("membership cooldown exceeds the declared rule")
        if self.bad_streak > sum(self.decisions.values()):
            raise ValueError("dissatisfaction exceeds observed decision count")

    def _rates(self, observation, coordinator, local, quota):
        """Static service forecast over a short window, without hidden renewal.

        Travel uses whole ticks and fuel; dated stock is discounted rather than
        presented as a current observation. The outside menu includes staying
        at the same site without a quota. These are forecast rates, not claims
        about realized future consumption or the true private optimum.
        """
        me, tick, forager = observation["self"], observation["tick"], coordinator.forager
        position = (me["x"], me["y"])
        outside = 0.
        for site, point in forager.sites.items():
            distance = abs(position[0] - point[0]) + abs(position[1] - point[1])
            if distance and not forager._feasible_goal(me, position, point):
                continue
            service = forager._service(me, site, tick, discount=True)
            usable = max(0, self.forecast_horizon - distance) * service - distance * me["movement_cost"]
            outside = max(outside, min(me["need"], max(0., usable) / self.forecast_horizon))
        member_rate = None
        if local is not None:
            gross = min(me["max_harvest"], forager._available(local["id"]) / forager._crowd(local["id"]), quota)
            member_rate = min(me["need"], gross * (1 - me["harvest_cost_per_unit"]))
        return outside, member_rate

    def __call__(self, observation):
        me, tick, political = observation["self"], observation["tick"], observation["politics"]
        _int(tick, "decision tick")
        if self.owner is not None and (self.owner != me["id"] or tick != self.last_tick + 1):
            raise ValueError("membership policy requires consecutive own decisions")
        receipt = validate_private_receipt(observation.get("private_feedback"), tick=tick,
                                           agent_id=me["id"], need=me["need"])
        # Preview on a detached controller. Only the final affordable plan is
        # committed to memory, once; proposed political debits precede physics.
        preview = CoordinationPolicy.restore(self.coordinator.memory())
        action = preview(observation)
        local = next((site for site in observation["sites"]
                      if (site["x"], site["y"]) == (me["x"], me["y"])), None)
        member = political["membership"]
        changed = member != self.member_id
        since = tick if changed or self.member_since is None else self.member_since
        accepted = political["accepted_charter"]
        own_local = next((i for i in political["institutions"] if i["id"] == member), None)
        member_site = None if changed else self.member_site
        if own_local is not None:
            member_site = own_local["site_id"]
        quota = self.charter.quota if accepted is None else accepted["quota"]
        service_site = local if member is None or own_local is not None else None
        outside, member_rate = self._rates(observation, preview, service_site, quota)
        shortfall = private_cost = 0.
        if (receipt is not None and not changed and member is not None and self.last_tick == tick - 1):
            shortfall = receipt["shortfall"]
            private_cost = math.fsum(receipt[name] for name in
                ("political_fee_private", "dues_contribution", "collateral_forfeited"))
        forecast_bad = member_rate is not None and outside > member_rate + self.advantage_need_fraction * me["need"]
        dissatisfied = (shortfall > self.shortfall_need_fraction * me["need"]
                        or private_cost > self.private_cost_need_fraction * me["need"]
                        or forecast_bad)
        streak = (0 if changed else self.bad_streak) + 1 if member is not None and dissatisfied else 0
        intent, debit, reason = Intent(), 0., "decentralized" if not self.organization else "no_local_offer"

        def entry_ok(terms, cost):
            nonlocal outside, member_rate
            outside, member_rate = self._rates(observation, preview, local, terms["quota"])
            protected = (1 + self.entry_reserve_ticks) * me["need"] + action.reserve
            messages = sum(len(text.encode("utf-8")) * me["message_byte_cost"] for _, text in action.messages)
            return (member_rate >= (1 - min(1., self.shortfall_need_fraction)) * me["need"]
                    and member_rate + 1e-12 >= outside
                    and me["inventory"] >= cost + protected + messages)

        claims = [row for row in political["institutions"]
                  if row["own_bond"] is not None
                  and row["own_bond"]["release_tick"] is not None
                  and row["own_bond"]["release_tick"] <= tick
                  and (row["own_bond"]["amount"] == 0. or me["inventory"] < me["inventory_capacity"])]
        if (self.organization and member is not None and tick - since >= self.minimum_stay
                and streak >= self.poor_patience):
            intent, reason = Intent("exit", member), "repeated_dissatisfaction"
        elif action.move == (0, 0) and claims:
            claim = min(claims, key=lambda row: row["id"])
            intent, reason = Intent("withdraw", claim["id"], amount=claim["own_bond"]["amount"]), "mature_local_refund"
        elif self.organization and member is not None:
            reason = "observing_membership"
        elif (self.organization and action.move == (0, 0) and local is not None
              and tick >= self.cooldown_until):
            proposals = [p for p in political["proposals"] if p["kind"] == "found"]
            institutions = [i for i in political["institutions"] if i["active"] and i["own_bond"] is None]
            if proposals:
                proposal = min(proposals, key=lambda row: row["id"])
                cost = proposal["charter"]["bond"]
                if entry_ok(proposal["charter"], cost):
                    intent, debit, reason = Intent("endorse", proposal["id"]), cost, "affordable_service_tie_or_gain"
                else:
                    intent, reason = Intent("refuse", proposal["id"]), "outside_or_liquidity_preferred"
            elif institutions:
                for institution in sorted(institutions, key=lambda row: row["id"]):
                    cost = institution["charter"]["bond"]
                    if entry_ok(institution["charter"], cost):
                        intent, debit, reason = Intent("join", institution["id"]), cost, "affordable_service_tie_or_gain"
                        break
                else:
                    reason = "outside_or_liquidity_preferred"
            elif not political["proposals"] and not any(i["active"] for i in political["institutions"]):
                peers = [p["id"] for p in observation["peers"] if (p["x"], p["y"]) == (me["x"], me["y"])]
                fee = political["config"]["founding_cost"]
                if (peers and me["id"] == min([me["id"], *peers])
                        and entry_ok(asdict(self.charter), fee + self.charter.bond)):
                    intent, debit, reason = Intent("propose", local["id"], self.charter), fee, "affordable_service_tie_or_gain"
        elif self.organization and member is None and tick < self.cooldown_until:
            reason = "exit_cooldown"

        if debit:
            packet = deepcopy(observation)
            packet["self"]["inventory"] -= debit
            funded = CoordinationPolicy.restore(self.coordinator.memory())
            funded_action = funded(packet)
            if funded_action.move == (0, 0):
                preview, action = funded, funded_action
            else:
                # Navigation and a local deposit cannot both happen this tick.
                intent, debit, reason = Intent(), 0., "navigation_preferred"
        # Optional quota promises apply during the final membership tick too.
        if self.organization and member is not None and accepted is not None and member_site is not None:
            destination = me["x"] + action.move[0], me["y"] + action.move[1]
            if preview.forager.sites.get(member_site) == destination:
                action = replace(action, harvest=min(action.harvest, accepted["quota"]))
        # A deposit/message may fail. Original carried headroom bounds requests
        # even if that anticipated outgoing material is never spent.
        after_move = me["inventory"] - (me["movement_cost"] if action.move != (0, 0) else 0.)
        headroom = max(0., me["inventory_capacity"] - after_move) / (1 - me["harvest_cost_per_unit"])
        action = replace(action, harvest=min(action.harvest, headroom))
        if intent.kind == "exit":
            self.cooldown_until = tick + self.cooldown_ticks + 1
        self.coordinator = preview
        self.owner, self.last_tick, self.member_id = me["id"], tick, member
        self.member_since = since if member is not None else None
        self.member_site = member_site if member is not None else None
        self.bad_streak = streak
        self.decisions[intent.kind] = self.decisions.get(intent.kind, 0) + 1
        self.diagnostics = {"tick": tick, "decision": intent.kind, "reason": reason,
                            "outside_rate": outside, "member_rate": member_rate,
                            "own_shortfall": shortfall, "own_private_cost": private_cost,
                            "bad_streak": streak, "planned_private_debit": debit}
        return action, intent


REASONS = {"decentralized", "no_local_offer", "repeated_dissatisfaction", "mature_local_refund",
           "observing_membership", "affordable_service_tie_or_gain", "outside_or_liquidity_preferred",
           "exit_cooldown", "navigation_preferred"}
