"""Exact-float local receipt/evidence/belief frames and shared message timing.

The engine authenticates the immediate sender and charges actual UTF-8 bytes.
R1 contains only that sender's own harvest. E1 provenance is the physical event
(site,tick), independent of its relay path. B1 carries data, not a fusion rule.
"""

from dataclasses import dataclass
import math
import struct

from .observations_messages_sites_v1 import validate_private_harvest


VERSION = "commons-v3-messages-sites-v1"
RECEIPT_BYTES, SOCIAL_BYTES, COMBINED_BYTES = 30, 96, 126
SOCIAL_PERIOD = 4


@dataclass(frozen=True)
class HarvestReceipt:
    site: int
    tick: int
    harvested: float


@dataclass(frozen=True)
class GrowthEvidence:
    site: int
    tick: int
    z: float
    stock_next: float


@dataclass(frozen=True)
class BeliefSummary:
    site: int
    median: float
    iqr: float


def _identity(value, name, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"invalid {name}")


def _amount(value, name):
    if type(value) not in (int, float) or not 0 <= value <= 1e6 or not math.isfinite(value):
        raise ValueError(f"invalid {name}")


def encode(record):
    if record is None:
        return "N1" + "." * (SOCIAL_BYTES - 2)
    if type(record) not in (HarvestReceipt, GrowthEvidence, BeliefSummary):
        raise ValueError("unknown message record")
    _identity(record.site, "site", 65535)
    if type(record) in (HarvestReceipt, GrowthEvidence):
        _identity(record.tick, "tick", 2**32 - 1)
    if type(record) is HarvestReceipt:
        _amount(record.harvested, "harvested")
        return "R1" + struct.pack(">HId", record.site, record.tick, record.harvested).hex()
    if type(record) is GrowthEvidence:
        _amount(record.z, "z")
        _amount(record.stock_next, "stock_next")
        if record.stock_next < record.z:
            raise ValueError("growth evidence must not lose post-harvest stock")
        body = "E1" + struct.pack(">HIdd", record.site, record.tick, record.z, record.stock_next).hex()
    else:
        _amount(record.median, "median")
        _amount(record.iqr, "iqr")
        if record.median == 0:
            raise ValueError("capacity median must be positive")
        body = "B1" + struct.pack(">Hdd", record.site, record.median, record.iqr).hex()
    return body.ljust(SOCIAL_BYTES, ".")


def _frame(text):
    prefix = text[:2]
    if prefix == "R1" and len(text) == RECEIPT_BYTES:
        record = HarvestReceipt(*struct.unpack(">HId", bytes.fromhex(text[2:])))
    elif prefix == "E1" and len(text) == SOCIAL_BYTES and text[46:] == "." * 50:
        record = GrowthEvidence(*struct.unpack(">HIdd", bytes.fromhex(text[2:46])))
    elif prefix == "B1" and len(text) == SOCIAL_BYTES and text[38:] == "." * 58:
        record = BeliefSummary(*struct.unpack(">Hdd", bytes.fromhex(text[2:38])))
    elif prefix == "N1" and text == encode(None):
        return None
    else:
        raise ValueError("invalid message frame or padding")
    if encode(record) != text:
        raise ValueError("message is not canonical")
    return record


def decode(text):
    """Return (own receipt or None, social record or None); N1 means no data."""
    if type(text) is not str or not text.isascii():
        raise ValueError("messages must be canonical ASCII")
    try:
        if len(text) == COMBINED_BYTES:
            receipt, social = _frame(text[:RECEIPT_BYTES]), _frame(text[RECEIPT_BYTES:])
            if type(receipt) is not HarvestReceipt or type(social) is HarvestReceipt:
                raise ValueError("invalid combined message")
            return receipt, social
        record = _frame(text)
        return (record, None) if type(record) is HarvestReceipt else (None, record)
    except (struct.error, OverflowError) as exc:
        raise ValueError("invalid binary message payload") from exc


def social_recipient(observation):
    """One content-independent visible-peer slot every four observation ticks."""
    tick, identity = observation["tick"], observation["self"]["id"]
    _identity(tick, "tick", 2**32 - 1)
    if tick % SOCIAL_PERIOD:
        return None
    peers = sorted(peer["id"] for peer in observation["peers"])
    if len(set(peers)) != len(peers) or identity in peers:
        raise ValueError("duplicate or self peer ID")
    return peers[(tick // SOCIAL_PERIOD + identity) % len(peers)] if peers else None


def schedule_messages(observation, *, arm, receipt=None, cohort=(), social=None):
    """Four unique local recipients; combine a social frame with a receipt.

Budgets and schedules match L2/L3 at equal local histories. Movement and private
funds can still change realized delivery and paid bytes; the engine decides
those outcomes after joint movement. No action or payment is fabricated here.
    """
    if arm not in ("L1", "L2", "L3"):
        raise ValueError("unknown communicating arm")
    allowed_social = GrowthEvidence if arm == "L2" else BeliefSummary
    if social is not None and (arm == "L1" or type(social) is not allowed_social):
        raise ValueError("social frame does not match the arm")
    me = observation["self"]
    if me["max_messages"] != 4:
        raise ValueError("communicating arms require max_messages=4")
    peers = {peer["id"] for peer in observation["peers"]}
    if len(peers) != len(observation["peers"]) or me["id"] in peers:
        raise ValueError("duplicate or self peer ID")
    candidates, receipt_text = [], None
    if receipt is not None:
        if type(receipt) is not HarvestReceipt or receipt.tick != observation["tick"] - 1:
            raise ValueError("only the preceding own harvest can be sent as a receipt")
        own = validate_private_harvest(observation.get("private_harvest"), observation)
        if own is None or own["harvested"] != receipt.harvested:
            raise ValueError("receipt differs from the private own outcome")
        if (type(cohort) is not tuple or len(set(cohort)) != len(cohort)
                or me["id"] not in cohort or any(type(identity) is not int or identity < 0 for identity in cohort)):
            raise ValueError("receipt cohort must contain unique agent IDs including self")
        site = next((site for site in observation["sites"]
                     if (site["x"], site["y"]) == (me["x"], me["y"])), None)
        actual_cohort = {me["id"], *(peer["id"] for peer in observation["peers"]
                                    if (peer["x"], peer["y"]) == (me["x"], me["y"]))}
        if site is None or site["id"] != receipt.site or set(cohort) != actual_cohort:
            raise ValueError("receipt site or cohort differs from the observed extraction location")
        ordered = sorted(cohort)
        offset = (receipt.site + receipt.tick) % len(ordered)
        ordered = ordered[offset:] + ordered[:offset]
        candidates = [identity for identity in ordered if identity in peers]
        receipt_text = encode(receipt)
    target = social_recipient(observation) if arm in ("L2", "L3") else None
    frames = {}
    if target is not None:
        frames[target] = (receipt_text if target in candidates else "") + encode(social)
    for target in candidates:
        if target in frames:
            continue
        if len(frames) == 4:
            break
        frames[target] = receipt_text
    if any(len(text.encode("utf-8")) > me["max_message_bytes"] for text in frames.values()):
        raise ValueError("configured message size is too small")
    return tuple(sorted(frames.items()))
