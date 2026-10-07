"""Declared supplied controls for the first institutional development panel.

These controllers retain both frozen competent forager backgrounds. They are
finite supplied rules, not optimized private responses. The four arms compare
policy bundles: their realized operation schedules and costs are not matched.
No existing policy, political primitive, or frozen source is changed here.
"""
from __future__ import annotations

from dataclasses import asdict, replace

from .policies_institutions_v1 import CoordinatingForager, _int, _number
from .politics_v1 import Charter, Intent


VERSION = "commons-v3-institutions-development-policy-v1"
ARMS = ("frozen", "decentralized", "charter_unmonitored", "charter_enforced")
KINDS = {"none", "propose", "endorse", "refuse", "join", "exit", "pay",
         "monitor", "sanction", "withdraw", "cache", "retrieve"}


class DevelopmentPolicy:
    """Common navigation/reporting with explicit optional political rules.

    Nonstubborn agents use the same restrained navigation in every arm. A
    responsive member can choose a lower request under a funded local threat;
    the physical engine never clamps the action. Stubborn agents retain the
    frozen aggressive controller, with no reports, caches, or political action
    in every arm. They are a fixed stress role, not a deterrence model.

    The unmonitored charter withholds contributions and never buys audits or
    settlements. Its members anticipate no detection. The enforced charter
    contributes to a bounded operating pool and supplies a fixed probability
    of 0.5 when another currently local member is the designated observer.
    That probability is an assumption, not an estimated detection frequency.
    """

    def __init__(self, arm="decentralized", *, behavior="responsive", reserve_ticks=4,
                 stock_floor_fraction=.5, route_mode="nearest", charter=None,
                 report_period=4, max_dues_need_fraction=.1, max_bond_need_ticks=2.,
                 anticipated_monitoring_probability=.5, cache_need_ticks=2.,
                 cache_deposit_above_need_ticks=6., cache_retrieve_below_need_ticks=2.):
        if arm not in ARMS:
            raise ValueError("unknown institutional development arm")
        if behavior not in ("responsive", "stubborn"):
            raise ValueError("unknown supplied development behavior")
        if charter is None:
            charter = Charter()
        if type(charter) is not Charter:
            raise ValueError("charter must be the supplied Charter record")
        for name, value, maximum in (
                ("max_dues_need_fraction", max_dues_need_fraction, 100.),
                ("max_bond_need_ticks", max_bond_need_ticks, 1e6),
                ("anticipated_monitoring_probability", anticipated_monitoring_probability, 1.),
                ("cache_need_ticks", cache_need_ticks, 1e6),
                ("cache_deposit_above_need_ticks", cache_deposit_above_need_ticks, 1e6),
                ("cache_retrieve_below_need_ticks", cache_retrieve_below_need_ticks, 1e6)):
            _number(value, name, maximum=maximum)
            setattr(self, name, value)
        if cache_retrieve_below_need_ticks > cache_deposit_above_need_ticks:
            raise ValueError("cache retrieval threshold exceeds deposit threshold")
        self.arm, self.behavior, self.charter = arm, behavior, charter
        self.coordinator = CoordinatingForager(reserve_ticks, stock_floor_fraction, route_mode,
            aggressive=behavior == "stubborn", share=arm != "frozen" and behavior != "stubborn",
            report_period=report_period)
        self.decisions: dict[str, int] = {}

    def memory(self):
        return {"version": VERSION, "arm": self.arm, "behavior": self.behavior,
                "charter": asdict(self.charter), "coordinator": self.coordinator.memory(),
                **{name: getattr(self, name) for name in (
                    "max_dues_need_fraction", "max_bond_need_ticks",
                    "anticipated_monitoring_probability", "cache_need_ticks",
                    "cache_deposit_above_need_ticks", "cache_retrieve_below_need_ticks")},
                "decisions": dict(sorted(self.decisions.items()))}

    @classmethod
    def restore(cls, memory):
        scalar_names = ("max_dues_need_fraction", "max_bond_need_ticks",
                        "anticipated_monitoring_probability", "cache_need_ticks",
                        "cache_deposit_above_need_ticks", "cache_retrieve_below_need_ticks")
        keys = {"version", "arm", "behavior", "charter", "coordinator", "decisions", *scalar_names}
        if type(memory) is not dict or set(memory) != keys or memory["version"] != VERSION:
            raise ValueError("unsupported development policy memory")
        try:
            coordinator = CoordinatingForager.restore(memory["coordinator"])
            forager = coordinator.forager
            policy = cls(memory["arm"], behavior=memory["behavior"], charter=Charter(**memory["charter"]),
                reserve_ticks=forager.reserve_ticks, stock_floor_fraction=forager.stock_floor_fraction,
                route_mode=forager.route_mode, report_period=coordinator.report_period,
                **{name: memory[name] for name in scalar_names})
        except TypeError as error:
            raise ValueError("invalid development policy configuration") from error
        if (coordinator.share != policy.coordinator.share
                or forager.aggressive != policy.coordinator.forager.aggressive):
            raise ValueError("reporting/aggression differs from the declared arm and role")
        policy.coordinator = coordinator
        if type(memory["decisions"]) is not dict:
            raise ValueError("decision counters must be a dictionary")
        for kind, count in memory["decisions"].items():
            if kind not in KINDS:
                raise ValueError("unknown development decision counter")
            policy.decisions[kind] = _int(count, "decision count")
        if policy.memory() != memory:
            raise ValueError("development policy memory is not canonical")
        return policy

    def _acceptable(self, charter, me):
        return (charter["dues"] <= self.max_dues_need_fraction * me["need"]
                and charter["bond"] <= self.max_bond_need_ticks * me["need"]
                and charter["quota"] >= min(me["max_harvest"],
                                            me["need"] / (1 - me["harvest_cost_per_unit"])))

    def _cache(self, observation, action, local_site, message_charge):
        """Use only the same local, private custody opportunity in each arm.

        Retrieving occurs after consumption and cannot repair this tick's
        shortfall. No route override or remote cache balance is available.
        A deposit can fail if other local users occupy the shared capacity;
        the policy receives no privileged occupancy information.
        """
        if action.move != (0, 0) or local_site is None:
            return Intent()
        me, political = observation["self"], observation["politics"]
        held = sum(row["amount"] for row in political["caches"]
                   if row["site_id"] == local_site["id"])
        desired = self.cache_retrieve_below_need_ticks * me["need"]
        if held > 0. and me["inventory"] < desired:
            return Intent("retrieve", local_site["id"], amount=min(held, desired - me["inventory"]))
        surplus = me["inventory"] - (self.cache_deposit_above_need_ticks * me["need"]
                                      + action.reserve + message_charge)
        amount = min(max(0., self.cache_need_ticks * me["need"] - held), max(0., surplus))
        if amount > 0.:
            return Intent("cache", local_site["id"], amount=amount)
        return Intent()

    def __call__(self, observation):
        action = self.coordinator(observation)
        intent = Intent()
        # These roles are exact frozen physical controls, including in a world
        # containing organizations founded by other individuals.
        if self.arm == "frozen" or self.behavior == "stubborn":
            self.decisions["none"] = self.decisions.get("none", 0) + 1
            return action, intent
        political, me, tick = observation["politics"], observation["self"], observation["tick"]
        member = political["membership"]
        institution = next((row for row in political["institutions"] if row["id"] == member), None)
        local_site = next((site for site in observation["sites"]
                           if (site["x"], site["y"]) == (me["x"], me["y"])), None)
        message_charge = sum(len(text.encode("utf-8")) * me["message_byte_cost"]
                             for _, text in action.messages)
        spare = max(0., me["inventory"] - me["need"] - action.reserve - message_charge)
        claims = [row for row in political["institutions"] if row["own_bond"] is not None
                  and row["own_bond"]["amount"] > 0. and row["own_bond"]["release_tick"] is not None
                  and row["own_bond"]["release_tick"] <= tick]
        if claims and (me["inventory"] < me["inventory_capacity"] or me["need"] > 0.):
            claim = min(claims, key=lambda row: row["id"])
            if action.move != (0, 0):
                action = replace(action, move=(0, 0), harvest=0.)
            intent = Intent("withdraw", claim["id"], amount=claim["own_bond"]["amount"])
        elif self.arm == "decentralized":
            intent = self._cache(observation, action, local_site, message_charge)
        elif (member is not None and political["accepted_charter"] is not None
              and not self._acceptable(political["accepted_charter"], me)):
            intent = Intent("exit", member)
        elif action.move == (0, 0) and member is not None and institution is not None:
            charter = institution["charter"]
            local_members = [me["id"], *(peer["id"] for peer in observation["peers"]
                if peer["id"] in institution["members"]
                and (peer["x"], peer["y"]) == (me["x"], me["y"]))]
            monitor = min(local_members)
            enforced = self.arm == "charter_enforced"
            if local_site is not None and action.harvest > charter["quota"]:
                attainable = local_site["stock"] / max(1, local_site["peer_count"])
                gain = (min(action.harvest, attainable) - min(charter["quota"], attainable)) * (1 - me["harvest_cost_per_unit"])
                bond = institution["own_bond"]
                held = 0. if bond is None else bond["amount"]
                funded = (enforced and monitor != me["id"]
                    and institution["treasury"] >= political["config"]["monitoring_cost"]
                                                + political["config"]["settlement_cost"])
                anticipated = self.anticipated_monitoring_probability * min(held, charter["fine"]) if funded else 0.
                if gain <= anticipated:
                    action = replace(action, harvest=charter["quota"])
            evidence = next((row for row in political["evidence"]
                if row["institution"] == member and not row["used"] and row["subject"] != me["id"]
                and row["harvested"] > row["quota"] and row["fine"] > 0.), None)
            if (enforced and evidence is not None
                    and institution["treasury"] >= political["config"]["settlement_cost"]):
                intent = Intent("sanction", evidence["id"], funding="treasury")
            elif (enforced and len(local_members) > 1 and monitor == me["id"]
                    and institution["treasury"] >= political["config"]["monitoring_cost"]):
                intent = Intent("monitor", institution["site_id"], funding="treasury")
            elif (enforced and spare >= charter["dues"] > 0.
                    and institution["treasury"] < 2 * len(institution["members"]) *
                        (political["config"]["monitoring_cost"] + political["config"]["settlement_cost"])):
                intent = Intent("pay", member, amount=charter["dues"])
        elif action.move == (0, 0) and member is None and local_site is not None:
            proposals = [row for row in political["proposals"] if row["kind"] == "found"]
            if proposals:
                proposal = min(proposals, key=lambda row: row["id"])
                agreeable = self._acceptable(proposal["charter"], me) and spare >= proposal["charter"]["bond"]
                intent = Intent("endorse" if agreeable else "refuse", proposal["id"])
            else:
                eligible = [row for row in political["institutions"] if row["active"]
                    and self._acceptable(row["charter"], me) and spare >= row["charter"]["bond"]
                    and row["own_bond"] is None]
                if eligible:
                    intent = Intent("join", min(eligible, key=lambda row: row["id"])["id"])
                else:
                    colocated = [peer["id"] for peer in observation["peers"]
                        if (peer["x"], peer["y"]) == (me["x"], me["y"])]
                    terms = asdict(self.charter)
                    if (colocated and me["id"] == min([me["id"], *colocated])
                            and not political["proposals"]
                            and not any(row["active"] for row in political["institutions"])
                            and self._acceptable(terms, me)
                            and spare >= terms["bond"] + political["config"]["founding_cost"]):
                        intent = Intent("propose", local_site["id"], self.charter)
        if intent.kind == "none":
            intent = self._cache(observation, action, local_site, message_charge)
        self.decisions[intent.kind] = self.decisions.get(intent.kind, 0) + 1
        return action, intent
