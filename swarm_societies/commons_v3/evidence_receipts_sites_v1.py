"""Delayed, complete-cohort extraction receipts and canonical growth evidence.

Only local observations establish an extraction cohort. Its members' harvests
remain unknown until their own authenticated, paid messages arrive. Complete
records subtract the cohort's total harvest; they never relabel it as the
observer's own harvest. L2 relays canonical (site,tick,z,stock_next) records.
"""

from dataclasses import asdict, dataclass
import math

from .evidence_sites_v1 import LocalEvidence, StockBound
from .messages_sites_v1 import BeliefSummary, GrowthEvidence, HarvestReceipt, decode
from .observations_messages_sites_v1 import VERSION as ADAPTER_VERSION, validate_private_harvest


VERSION = "commons-v3-receipt-evidence-sites-v1"
COUNTERS = ("eligible", "clean_own", "clean_receipts", "new_relay", "duplicates", "confounded", "belief_messages")


@dataclass(frozen=True)
class ReceiptEvidenceBatch:
    bounds: tuple[StockBound, ...]
    growth: tuple[GrowthEvidence, ...]
    beliefs: tuple[tuple[int, BeliefSummary], ...]


class ReceiptEvidence:
    def __init__(self, *, accept_relay=True, accept_beliefs=True):
        if type(accept_relay) is not bool or type(accept_beliefs) is not bool:
            raise ValueError("social evidence switches must be boolean")
        self.accept_relay, self.accept_beliefs = accept_relay, accept_beliefs
        self.local = LocalEvidence()
        self.own_receipt: HarvestReceipt | None = None
        self.cohort: tuple[int, ...] = ()
        self.known: dict[tuple[int, int], GrowthEvidence] = {}
        self.events: dict[tuple[int, int], dict] = {}
        self.counters = dict.fromkeys(COUNTERS, 0)

    def _learn(self, record, output, *, relayed):
        key = record.site, record.tick
        existing = self.known.get(key)
        if existing is not None:
            if existing != record:
                raise ValueError("conflicting records for the same physical growth event")
            self.counters["duplicates"] += 1
            return
        self.known[key] = record
        output.append(record)
        if relayed:
            self.counters["new_relay"] += 1

    def _resolve(self, key, output):
        event = self.events[key]
        if event["resolved"] or set(event["receipts"]) != set(event["cohort"]):
            return
        total = math.fsum(event["receipts"][identity] for identity in event["cohort"])
        tolerance = 8 * math.ulp(max(1., event["stock_before"]))
        if total > event["stock_before"] + tolerance:
            raise ValueError("complete receipts exceed the observed physical stock")
        z = max(0., event["stock_before"] - total)
        if event["stock_next"] < z:
            raise ValueError("complete receipts leave unexplained stock loss")
        growth = GrowthEvidence(key[0], key[1], z, event["stock_next"])
        self._learn(growth, output, relayed=False)
        event["total_harvest"] = total
        event["resolved"] = True
        self.counters["clean_own" if len(event["cohort"]) == 1 else "clean_receipts"] += 1

    def observe(self, observation, previous_action=None):
        if (type(observation) is not dict or observation.get("adapter_version") != ADAPTER_VERSION
                or "private_harvest" not in observation):
            raise ValueError("receipt evidence requires the own-harvest observation adapter")
        own = validate_private_harvest(observation["private_harvest"], observation)
        previous = self.local.memory()["previous"]
        if previous is not None and observation["tick"] > previous["tick"] and own is None:
            raise ValueError("a continued observation requires its preceding own harvest")
        local_batch = self.local.observe(observation, previous_action)
        if local_batch.reason == "repeated_observation":
            return ReceiptEvidenceBatch((), (), ())
        current = self.local.memory()["previous"]
        me = current["self"]
        site = next((site for site in current["sites"]
                     if (site["x"], site["y"]) == (me["x"], me["y"])), None)
        self.own_receipt, self.cohort = None, ()
        growth, beliefs = [], []
        if site is not None and own is not None:
            self.own_receipt = HarvestReceipt(site["id"], own["tick"], own["harvested"])
            self.cohort = tuple(sorted([me["id"], *(peer["id"] for peer in current["peers"]
                                                   if (peer["x"], peer["y"]) == (site["x"], site["y"]))]))
            if previous is not None and previous["tick"] + 1 == current["tick"]:
                old = next((old for old in previous["sites"] if old["id"] == site["id"]), None)
                if old is not None:
                    if (old["x"], old["y"]) != (site["x"], site["y"]):
                        raise ValueError("site coordinates changed between observations")
                    key = site["id"], own["tick"]
                    self.events[key] = {
                        "stock_before": old["stock"], "stock_next": site["stock"],
                        "observer": me["id"], "cohort": self.cohort,
                        "own_harvest": own["harvested"], "receipts": {me["id"]: own["harvested"]},
                        "total_harvest": None, "resolved": False}
                    self.counters["eligible"] += 1
                    if len(self.cohort) > 1:
                        self.counters["confounded"] += 1
                    self._resolve(key, growth)
        for message in observation["messages"]:
            if (type(message) is not dict
                    or any(type(message.get(name)) is not int for name in ("sender", "recipient", "sent_tick", "delivery_tick"))
                    or message["sender"] < 0 or message["sender"] == me["id"]
                    or message["recipient"] != me["id"] or message["delivery_tick"] != current["tick"]
                    or message["sent_tick"] != current["tick"] - 1):
                raise ValueError("message transport identity or timing differs from observation")
            try:
                receipt, social = decode(message["text"])
            except (KeyError, ValueError):
                # Unsupported application payloads carry no evidence.
                continue
            sender = message["sender"]
            if receipt is not None and receipt.tick == message["sent_tick"] - 1:
                key = receipt.site, receipt.tick
                event = self.events.get(key)
                if (event is not None and sender in event["cohort"]
                        and receipt.harvested <= observation["self"]["max_harvest"]):
                    if sender in event["receipts"]:
                        if event["receipts"][sender] != receipt.harvested:
                            raise ValueError("conflicting harvest receipts from the same cohort member")
                        self.counters["duplicates"] += 1
                    else:
                        event["receipts"][sender] = receipt.harvested
                        self._resolve(key, growth)
            if self.accept_relay and type(social) is GrowthEvidence and social.tick < message["sent_tick"]:
                self._learn(social, growth, relayed=True)
            elif self.accept_beliefs and type(social) is BeliefSummary:
                beliefs.append((sender, social))
                self.counters["belief_messages"] += 1
        return ReceiptEvidenceBatch(local_batch.bounds, tuple(growth), tuple(beliefs))

    def memory(self):
        events = []
        for (site, tick), event in sorted(self.events.items()):
            events.append({"site": site, "tick": tick,
                           **{key: value for key, value in event.items() if key not in ("cohort", "receipts")},
                           "cohort": list(event["cohort"]),
                           "receipts": [[identity, amount] for identity, amount in sorted(event["receipts"].items())]})
        return {"version": VERSION, "accept_relay": self.accept_relay, "accept_beliefs": self.accept_beliefs,
                "local": self.local.memory(),
                "own_receipt": asdict(self.own_receipt) if self.own_receipt is not None else None,
                "cohort": list(self.cohort), "known": [asdict(record) for _, record in sorted(self.known.items())],
                "events": events, "counters": dict(self.counters)}
