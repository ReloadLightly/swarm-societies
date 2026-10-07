"""Optional local agreements and explicit material custody, version 1.

This is a separately versioned physical extension. The frozen engine executes
the physical substep; this module accounts for every resource entering/leaving
that substep and for material held outside private inventories. Collateral is
voluntary, locally settled, and cannot authorize seizure of outside resources.
See docs/commons-v3-institutions-contract-v1.md for the supplied assumptions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math

from . import engine as physical

VERSION = "commons-v3-politics-v1"
SNAPSHOT_VERSION = "commons-v3-politics-snapshot-v1"
KINDS = {"none", "propose", "endorse", "refuse", "join", "exit", "pay",
         "withdraw", "monitor", "sanction", "amend", "replace", "dissolve",
         "cache", "retrieve"}


def _number(value, name, minimum=0., maximum=1e6):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"invalid {name}")


def _integer(value, name, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"invalid {name}")


@dataclass(frozen=True)
class Charter:
    quota: float = 2.
    bond: float = 1.
    dues: float = .1
    fine: float = .5

    def __post_init__(self):
        for name in ("quota", "bond", "dues", "fine"):
            _number(getattr(self, name), name)


@dataclass(frozen=True)
class PoliticalConfig:
    founding_cost: float = .1
    monitoring_cost: float = .05
    settlement_cost: float = .02
    treasury_capacity: float = 80.
    proposal_lifetime: int = 8

    def __post_init__(self):
        for name in ("founding_cost", "monitoring_cost", "settlement_cost", "treasury_capacity"):
            _number(getattr(self, name), name)
        if self.treasury_capacity <= 0:
            raise ValueError("custody capacity must be positive")
        _integer(self.proposal_lifetime, "proposal_lifetime", 1, 1024)


@dataclass(frozen=True)
class Intent:
    kind: str = "none"
    target: int | None = None
    charter: Charter | None = None
    amount: float = 0.
    funding: str = "private"

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in KINDS:
            raise ValueError("unknown political intent")
        if self.target is not None:
            _integer(self.target, "intent target")
        if self.charter is not None and type(self.charter) is not Charter:
            raise ValueError("invalid charter")
        _number(self.amount, "amount")
        if self.funding not in ("private", "treasury"):
            raise ValueError("invalid funding source")
        if self.funding != "private" and self.kind not in ("monitor", "sanction"):
            raise ValueError("treasury funding only pays monitoring or settlement")
        if self.kind in ("propose", "amend", "replace") and self.charter is None:
            raise ValueError("this intent requires a charter")
        if self.kind not in ("none", "exit") and self.target is None:
            raise ValueError("this intent requires a target")


@dataclass(frozen=True)
class Bond:
    owner: int
    amount: float
    release_tick: int | None = None


@dataclass(frozen=True)
class Cache:
    owner: int
    site_id: int
    amount: float


@dataclass(frozen=True)
class Institution:
    id: int
    site_id: int
    charter: Charter
    members: tuple[int, ...]
    bonds: tuple[Bond, ...]
    treasury: float = 0.
    active: bool = True
    revision: int = 0
    successor: int | None = None


@dataclass(frozen=True)
class Proposal:
    id: int
    kind: str
    proposer: int
    site_id: int
    institution: int | None = None
    charter: Charter | None = None
    created_tick: int = 0
    expires_tick: int = 0


@dataclass(frozen=True)
class Evidence:
    id: int
    observer: int
    institution: int | None
    subject: int
    site_id: int
    observed_tick: int
    harvested: float
    quota: float
    fine: float
    revision: int
    used: bool = False


@dataclass(frozen=True)
class State:
    world: physical.WorldState
    config: PoliticalConfig
    institutions: tuple[Institution, ...] = ()
    proposals: tuple[Proposal, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    caches: tuple[Cache, ...] = ()
    next_id: int = 0
    political_cost: float = 0.
    forfeited: float = 0.


@dataclass(frozen=True)
class PoliticalLedger:
    tick: int
    inventory_before: float
    custody_before: float
    inventory_after: float
    custody_after: float
    political_cost: float
    forfeited: float
    physical_residual: float
    residual: float
    entries: tuple[dict, ...]


@dataclass(frozen=True)
class Result:
    state: State
    physical: physical.StepResult
    ledger: PoliticalLedger
    events: tuple[dict, ...]


def initialize(config=physical.Config(), seed=0, political_config=PoliticalConfig()):
    state = State(physical.initialize(config, seed), political_config)
    _validate(state)
    return state


def custody(state):
    return math.fsum([c.amount for c in state.caches] +
                     [i.treasury + math.fsum(b.amount for b in i.bonds) for i in state.institutions])


def _validate(state):
    if type(state) is not State or type(state.config) is not PoliticalConfig:
        raise ValueError("invalid political state")
    physical._validate_state(state.world)
    _integer(state.next_id, "next identity")
    for name in ("political_cost", "forfeited"):
        _number(getattr(state, name), name, maximum=1e15)
    for name in ("institutions", "proposals", "evidence", "caches"):
        if type(getattr(state, name)) is not tuple:
            raise ValueError("political collections must be tuples")
    n, sites, tick = state.world.config.n_agents, state.world.config.n_patches, state.world.tick
    ids, members, capacities = set(), set(), [0.] * sites
    institutions = {i.id: i for i in state.institutions if type(i) is Institution}
    for i in state.institutions:
        if type(i) is not Institution or type(i.charter) is not Charter:
            raise ValueError("invalid institution")
        _integer(i.id, "institution ID", maximum=state.next_id - 1)
        _integer(i.site_id, "institution site", maximum=sites - 1)
        _integer(i.revision, "charter revision")
        _number(i.treasury, "treasury")
        if i.id in ids or type(i.active) is not bool or type(i.members) is not tuple or type(i.bonds) is not tuple:
            raise ValueError("invalid institution identity or collections")
        ids.add(i.id)
        if tuple(sorted(set(i.members))) != i.members or (not i.active and (i.members or i.treasury)):
            raise ValueError("invalid active membership")
        if i.active and not i.members:
            raise ValueError("active institution has no members")
        for member in i.members:
            _integer(member, "member", maximum=n - 1)
            if member in members:
                raise ValueError("multiple active memberships")
            members.add(member)
        owners = set()
        for b in i.bonds:
            if type(b) is not Bond:
                raise ValueError("invalid bond")
            _integer(b.owner, "bond owner", maximum=n - 1)
            _number(b.amount, "bond amount")
            if b.owner in owners or ((b.owner in i.members) != (b.release_tick is None)):
                raise ValueError("invalid bond ownership")
            if b.release_tick is None and b.amount > i.charter.bond:
                raise ValueError("active collateral exceeds accepted pledge")
            if b.release_tick is not None:
                _integer(b.release_tick, "bond release", maximum=tick + 1)
            owners.add(b.owner)
        if not set(i.members) <= owners:
            raise ValueError("every member must have a custody record")
        if i.successor is not None:
            _integer(i.successor, "successor", maximum=state.next_id - 1)
            if i.active or i.successor not in institutions or i.successor <= i.id:
                raise ValueError("invalid succession")
        capacities[i.site_id] += i.treasury + math.fsum(b.amount for b in i.bonds)
    for p in state.proposals:
        if type(p) is not Proposal or p.kind not in ("found", "amend", "replace", "dissolve"):
            raise ValueError("invalid proposal")
        _integer(p.id, "proposal ID", maximum=state.next_id - 1)
        _integer(p.proposer, "proposer", maximum=n - 1)
        _integer(p.site_id, "proposal site", maximum=sites - 1)
        _integer(p.created_tick, "proposal tick", maximum=tick)
        _integer(p.expires_tick, "proposal expiry", p.created_tick + 1)
        if p.institution is not None:
            _integer(p.institution, "proposal institution", maximum=state.next_id - 1)
        if p.id in ids or p.expires_tick != p.created_tick + state.config.proposal_lifetime:
            raise ValueError("invalid proposal identity or lifetime")
        ids.add(p.id)
        if p.kind == "found":
            if p.institution is not None or type(p.charter) is not Charter:
                raise ValueError("invalid founding proposal")
        elif (p.institution not in institutions or institutions[p.institution].site_id != p.site_id
              or (p.kind != "dissolve" and type(p.charter) is not Charter)):
            raise ValueError("invalid change proposal")
    for e in state.evidence:
        if type(e) is not Evidence:
            raise ValueError("invalid evidence")
        for name in ("observer", "subject"):
            _integer(getattr(e, name), name, maximum=n - 1)
        _integer(e.id, "evidence ID", maximum=state.next_id - 1)
        _integer(e.site_id, "evidence site", maximum=sites - 1)
        _integer(e.observed_tick, "evidence tick", maximum=tick - 1)
        _integer(e.revision, "evidence revision")
        for name in ("harvested", "quota", "fine"):
            _number(getattr(e, name), name)
        if e.id in ids or type(e.used) is not bool:
            raise ValueError("invalid evidence identity")
        ids.add(e.id)
        if e.institution is not None:
            _integer(e.institution, "evidence institution", maximum=state.next_id - 1)
            if e.institution not in institutions or institutions[e.institution].site_id != e.site_id:
                raise ValueError("evidence has no custody site")
        elif e.fine != 0:
            raise ValueError("nonmember evidence cannot carry a fine")
    keys = set()
    for c in state.caches:
        if type(c) is not Cache:
            raise ValueError("invalid cache")
        _integer(c.owner, "cache owner", maximum=n - 1)
        _integer(c.site_id, "cache site", maximum=sites - 1)
        _number(c.amount, "cache amount")
        if (c.owner, c.site_id) in keys:
            raise ValueError("duplicate cache")
        keys.add((c.owner, c.site_id))
        capacities[c.site_id] += c.amount
    if any(value > state.config.treasury_capacity + 1e-9 for value in capacities):
        raise ValueError("site custody capacity exceeded")


def _at(world, actor, site):
    if type(site) is not int or not 0 <= site < len(world.patches):
        return False
    a, p = world.agents[actor], world.patches[site]
    return (a.x, a.y) == (p.x, p.y)


def _packet(state, actor, packet):
    own = next((i for i in state.institutions if actor in i.members), None)
    local = []
    for i in state.institutions:
        if _at(state.world, actor, i.site_id):
            bond = next((b for b in i.bonds if b.owner == actor), None)
            local.append({"id": i.id, "site_id": i.site_id, "charter": asdict(i.charter),
                          "members": list(i.members), "treasury": i.treasury,
                          "revision": i.revision, "active": i.active, "successor": i.successor,
                          "own_bond": None if bond is None else asdict(bond)})
    packet["politics"] = {"version": VERSION, "config": asdict(state.config),
        "membership": None if own is None else own.id,
        "accepted_charter": None if own is None else asdict(own.charter),
        "institutions": local,
        "proposals": [asdict(p) for p in state.proposals
                      if p.expires_tick > state.world.tick and _at(state.world, actor, p.site_id)],
        "evidence": [asdict(e) for e in state.evidence if e.observer == actor],
        "caches": [asdict(c) for c in state.caches if c.owner == actor and _at(state.world, actor, c.site_id)]}
    return packet


def observe(state, agent_id):
    _validate(state)
    return _packet(state, agent_id, physical.observe(state.world, agent_id))


def observations(state):
    _validate(state)
    return tuple(_packet(state, a, packet) for a, packet in enumerate(physical.observations(state.world)))


def step(state, physical_actions, intents=None):
    """Commit one optional intent per individual; failures leave it unexecuted.

    Fees/deposits precede the frozen physical step. Receipts and membership
    changes take effect afterward. Refunds cannot finance same-tick actions.
    """
    _validate(state)
    actions = physical._validate_actions(state.world, physical_actions)
    n, tick, cfg = len(actions), state.world.tick, state.config
    if intents is None:
        intents = (Intent(),) * n
    if type(intents) not in (tuple, list) or len(intents) != n or any(type(i) is not Intent for i in intents):
        raise ValueError("one Intent per individual is required")
    inventory = [a.inventory for a in state.world.agents]
    institutions = {i.id: i for i in state.institutions}
    proposals = {p.id: p for p in state.proposals if p.expires_tick > tick}
    old_evidence = {e.id: e for e in state.evidence if e.observed_tick == tick - 1 and not e.used}
    caches = {(c.owner, c.site_id): c for c in state.caches}
    opening_membership = {a: i for i in state.institutions for a in i.members}
    pledged = {(i.id, b.owner): b.amount for i in state.institutions
               for b in i.bonds if b.release_tick is None}
    spendable = {i.id: i.treasury for i in state.institutions}
    next_id, operating, forfeited = state.next_id, 0., 0.
    events, entries, monitors, exits, withdrawals, retrieves = [], [], [], [], [], []

    def identity():
        nonlocal next_id
        value = next_id
        next_id += 1
        return value

    def event(actor, ok, reason="ok", **values):
        events.append({"tick": tick, "actor": actor, "kind": intents[actor].kind,
                       "ok": ok, "reason": reason, **values})

    def entry(kind, actor, amount, **values):
        entries.append({"kind": kind, "actor": actor, "amount": amount, **values})

    def local(actor, site):
        return actions[actor].move == (0, 0) and _at(state.world, actor, site)

    def used_capacity(site):
        return math.fsum([c.amount for c in caches.values() if c.site_id == site] +
                         [i.treasury + math.fsum(b.amount for b in i.bonds)
                          for i in institutions.values() if i.site_id == site])

    def room(site, amount):
        return amount <= cfg.treasury_capacity - used_capacity(site) + 1e-12

    def fee(actor, amount, institution=None):
        nonlocal operating
        if intents[actor].funding == "treasury":
            if (institution is None or actor not in institution.members
                    or spendable.get(institution.id, 0.) < amount):
                return False
            spendable[institution.id] -= amount
            current = institutions[institution.id]
            institutions[institution.id] = replace(current, treasury=current.treasury - amount)
            entry("fee", actor, amount, source="treasury", institution=institution.id)
        else:
            if inventory[actor] < amount:
                return False
            inventory[actor] -= amount
            entry("fee", actor, amount, source="private")
        operating += amount
        return True

    def dissolve(i):
        # Treasury becomes claims, not remotely transferred private inventory.
        members = i.members
        bonds = {b.owner: b for b in i.bonds}
        remainder = i.treasury
        for j, member in enumerate(members):
            share = remainder if j == len(members) - 1 else i.treasury / len(members)
            remainder -= share
            old = bonds[member]
            bonds[member] = Bond(member, old.amount + share, tick + 2)
        return replace(i, active=False, members=(), treasury=0., bonds=tuple(bonds[a] for a in sorted(bonds)))

    # Previously paid, personal evidence can settle only already pledged custody.
    for actor, intent in enumerate(intents):
        if intent.kind != "sanction":
            continue
        e = old_evidence.get(intent.target)
        i = None if e is None else institutions.get(e.institution)
        b = None if i is None else next((b for b in i.bonds if b.owner == e.subject), None)
        if (e is None or e.observer != actor or i is None or b is None or b.amount <= 0
                or e.harvested <= e.quota + 1e-12 or e.fine <= 0 or not local(actor, e.site_id)
                or not fee(actor, cfg.settlement_cost, i)):
            event(actor, False, "unavailable")
            continue
        amount = min(e.fine, b.amount)
        current = institutions[i.id]
        institutions[i.id] = replace(current, bonds=tuple(replace(old, amount=old.amount - amount)
                                    if old.owner == e.subject else old for old in current.bonds))
        forfeited += amount
        if (i.id, e.subject) in pledged:
            pledged[i.id, e.subject] -= amount
        # Multiple observers corroborate one event; they cannot multiply its
        # charter fine or collect another settlement fee for that same event.
        old_evidence = {key: other for key, other in old_evidence.items()
                        if (other.institution, other.subject, other.observed_tick)
                        != (e.institution, e.subject, e.observed_tick)}
        entry("forfeit", actor, amount, institution=i.id, subject=e.subject, evidence=e.id)
        event(actor, True, institution=i.id, amount=amount, evidence=e.id)

    for actor, intent in enumerate(intents):
        kind, target = intent.kind, intent.target
        if kind in ("none", "sanction", "endorse"):
            continue
        i = institutions.get(target)
        if kind in ("propose", "amend", "replace", "dissolve"):
            site = target if kind == "propose" else (None if i is None else i.site_id)
            eligible = (actor not in opening_membership) if kind == "propose" else (
                i is not None and i.active and actor in i.members
                and (kind == "dissolve" or intent.charter.bond == i.charter.bond))
            if not eligible or not local(actor, site) or not fee(actor, cfg.founding_cost):
                event(actor, False, "unavailable")
                continue
            p = Proposal(identity(), "found" if kind == "propose" else kind, actor, site,
                         None if kind == "propose" else target, intent.charter, tick, tick + cfg.proposal_lifetime)
            proposals[p.id] = p
            event(actor, True, proposal=p.id)
        elif kind == "refuse":
            p = next((p for p in state.proposals if p.id == target and p.expires_tick > tick), None)
            event(actor, p is not None and local(actor, p.site_id), "refused" if p is not None and local(actor, p.site_id) else "unavailable")
        elif kind == "exit":
            own = opening_membership.get(actor)
            if own is None or (target is not None and target != own.id):
                event(actor, False, "unavailable")
            else:
                exits.append((actor, own.id))
                event(actor, True, institution=own.id)
        elif kind == "join":
            old = opening_membership.get(actor)
            existing = None if i is None else next((b for b in i.bonds if b.owner == actor), None)
            if (i is None or not i.active or old is not None or existing is not None
                    or not local(actor, i.site_id) or inventory[actor] < i.charter.bond
                    or not room(i.site_id, i.charter.bond)):
                event(actor, False, "unavailable")
                continue
            inventory[actor] -= i.charter.bond
            institutions[i.id] = replace(i, members=tuple(sorted((*i.members, actor))),
                bonds=tuple(sorted((*i.bonds, Bond(actor, i.charter.bond)), key=lambda b: b.owner)))
            entry("bond", actor, i.charter.bond, institution=i.id)
            event(actor, True, institution=i.id)
        elif kind == "pay":
            if (i is None or not i.active or actor not in i.members or not local(actor, i.site_id)
                    or intent.amount > inventory[actor] or not room(i.site_id, intent.amount)):
                event(actor, False, "unavailable")
                continue
            inventory[actor] -= intent.amount
            institutions[i.id] = replace(i, treasury=i.treasury + intent.amount)
            entry("dues", actor, intent.amount, institution=i.id)
            event(actor, True, institution=i.id, amount=intent.amount)
        elif kind == "monitor":
            own = opening_membership.get(actor)
            own = own if own is not None and own.site_id == target else None
            if not local(actor, target) or not fee(actor, cfg.monitoring_cost, own):
                event(actor, False, "unavailable")
                continue
            monitors.append((actor, target))
            event(actor, True, site=target)
        elif kind == "withdraw":
            b = None if i is None else next((b for b in i.bonds if b.owner == actor), None)
            if (b is None or b.release_tick is None or b.release_tick > tick or not local(actor, i.site_id)):
                event(actor, False, "unavailable")
            else:
                withdrawals.append((actor, i.id, intent.amount))
        elif kind == "cache":
            if not local(actor, target) or intent.amount > inventory[actor] or not room(target, intent.amount):
                event(actor, False, "unavailable")
                continue
            inventory[actor] -= intent.amount
            prior = caches.get((actor, target), Cache(actor, target, 0.))
            caches[actor, target] = replace(prior, amount=prior.amount + intent.amount)
            entry("cache", actor, intent.amount, site=target)
            event(actor, True, site=target, amount=intent.amount)
        elif kind == "retrieve":
            if not local(actor, target) or (actor, target) not in caches:
                event(actor, False, "unavailable")
            else:
                retrieves.append((actor, target, intent.amount))

    # Only proposals visible at commitment may receive endorsements. Consent
    # is simultaneous and is never stored as a standing blank cheque.
    endorsed = set()
    for p in sorted(state.proposals, key=lambda p: p.id):
        voters = [a for a, intent in enumerate(intents) if intent.kind == "endorse" and intent.target == p.id]
        if not voters:
            continue
        endorsed.update(voters)
        valid = p.id in proposals and all(local(a, p.site_id) for a in voters)
        if p.kind == "found":
            valid = (valid and p.proposer in voters and len(voters) >= 2
                     and all(a not in opening_membership and inventory[a] >= p.charter.bond for a in voters)
                     and room(p.site_id, len(voters) * p.charter.bond))
            if valid:
                for a in voters:
                    inventory[a] -= p.charter.bond
                    entry("bond", a, p.charter.bond, institution=p.id)
                institutions[p.id] = Institution(p.id, p.site_id, p.charter, tuple(voters),
                                                 tuple(Bond(a, p.charter.bond) for a in voters))
        else:
            i = institutions.get(p.institution)
            opening = next((i for i in state.institutions if i.id == p.institution), None)
            valid = (valid and i is not None and i.active and opening is not None
                     and set(voters) == set(i.members) == set(opening.members))
            if valid and p.kind == "replace":
                # The custody identity that a live receipt names must remain
                # available throughout its one-tick settlement window.
                valid = (not any(e.institution == i.id for e in state.evidence)
                         and not any(site == i.site_id for _, site in monitors))
            if valid:
                if p.kind == "dissolve":
                    institutions[i.id] = dissolve(i)
                elif p.kind == "amend":
                    institutions[i.id] = replace(i, charter=p.charter, revision=i.revision + 1)
                else:
                    active_bonds = tuple(b for b in i.bonds if b.owner in i.members)
                    old_claims = tuple(b for b in i.bonds if b.owner not in i.members)
                    institutions[p.id] = Institution(p.id, i.site_id, p.charter, i.members, active_bonds,
                                                     i.treasury, revision=i.revision + 1)
                    institutions[i.id] = replace(i, active=False, members=(), bonds=old_claims,
                                                 treasury=0., successor=p.id)
        for a in voters:
            event(a, bool(valid), "ok" if valid else "unavailable", proposal=p.id)
        if valid:
            proposals.pop(p.id)
    for actor, intent in enumerate(intents):
        if intent.kind == "endorse" and actor not in endorsed:
            event(actor, False, "unavailable")

    intermediate = replace(state.world, agents=tuple(replace(a, inventory=inventory[a.id]) for a in state.world.agents))
    result = physical.step(intermediate, actions)
    world = result.state

    # Evidence records measured allocation, after contention and movement. It
    # binds the charter/membership at commitment, never a new end-of-tick rule.
    evidence = []
    for observer, site in monitors:
        for a, row in zip(world.agents, result.ledger.agents):
            if not _at(world, a.id, site):
                continue
            old = opening_membership.get(a.id)
            old = old if old is not None and old.site_id == site else None
            evidence.append(Evidence(identity(), observer, None if old is None else old.id,
                a.id, site, tick, row.harvested, 0. if old is None else old.charter.quota,
                0. if old is None else min(old.charter.fine, pledged[old.id, a.id]),
                0 if old is None else old.revision))

    # Every departing member remains accountable for this tick's pledged rule.
    for actor, identity_ in exits:
        i = institutions[identity_]
        if len(i.members) == 1:
            institutions[i.id] = dissolve(i)
        else:
            institutions[i.id] = replace(i, members=tuple(a for a in i.members if a != actor),
                bonds=tuple(replace(b, release_tick=tick + 2) if b.owner == actor else b for b in i.bonds))

    balances = [a.inventory for a in world.agents]
    for actor, identity_, requested in withdrawals:
        i = institutions[identity_]
        b = next(b for b in i.bonds if b.owner == actor)
        amount = min(requested, b.amount, world.config.inventory_capacity - balances[actor])
        balances[actor] += amount
        bonds = tuple(replace(old, amount=old.amount - amount) if old.owner == actor else old for old in i.bonds)
        institutions[i.id] = replace(i, bonds=tuple(b for b in bonds if b.amount > 0 or b.release_tick is None))
        entry("withdraw", actor, amount, institution=i.id)
        event(actor, True, institution=i.id, amount=amount)
    for actor, site, requested in retrieves:
        c = caches[actor, site]
        amount = min(requested, c.amount, world.config.inventory_capacity - balances[actor])
        balances[actor] += amount
        caches[actor, site] = replace(c, amount=c.amount - amount)
        entry("retrieve", actor, amount, site=site)
        event(actor, True, site=site, amount=amount)
    world = replace(world, agents=tuple(replace(a, inventory=balances[a.id]) for a in world.agents))
    after = State(world, cfg, tuple(institutions[k] for k in sorted(institutions)),
        tuple(proposals[k] for k in sorted(proposals)), tuple(evidence),
        tuple(caches[k] for k in sorted(caches)), next_id,
        state.political_cost + operating, state.forfeited + forfeited)
    _validate(after)
    before_i = math.fsum(a.inventory for a in state.world.agents)
    after_i = math.fsum(a.inventory for a in world.agents)
    before_c, after_c = custody(state), custody(after)
    pl = result.ledger
    residual = (before_i + before_c + pl.stock_before + pl.growth
                - after_i - after_c - pl.stock_after - pl.consumption - pl.movement_cost
                - pl.message_cost - pl.harvest_cost - pl.waste - operating - forfeited)
    if abs(residual) > 1e-8 * max(1., before_i + before_c + pl.stock_before + pl.growth):
        raise ArithmeticError("political/physical material accounting failed")
    ledger = PoliticalLedger(tick, before_i, before_c, after_i, after_c, operating,
                             forfeited, pl.residual, residual, tuple(entries))
    return Result(after, result, ledger, tuple(events))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def snapshot(state):
    _validate(state)
    payload = {"world": physical.snapshot(state.world), "config": asdict(state.config),
               **{name: [asdict(row) for row in getattr(state, name)]
                  for name in ("institutions", "proposals", "evidence", "caches")},
               "next_id": state.next_id, "political_cost": state.political_cost, "forfeited": state.forfeited}
    content = {"version": SNAPSHOT_VERSION, "state": payload}
    # Actual files contain JSON arrays. Keep the public snapshot JSON-native
    # so an in-memory round trip and a file round trip obey the same contract.
    content = json.loads(json.dumps(content, allow_nan=False))
    return {**content, "sha256": _digest(content)}


def restore(checkpoint):
    try:
        if type(checkpoint) is not dict or set(checkpoint) != {"version", "state", "sha256"}:
            raise ValueError("invalid political checkpoint")
        content = {"version": checkpoint["version"], "state": checkpoint["state"]}
        if content["version"] != SNAPSHOT_VERSION or checkpoint["sha256"] != _digest(content):
            raise ValueError("political checkpoint checksum/version mismatch")
        data = content["state"]
        if set(data) != {"world", "config", "institutions", "proposals", "evidence", "caches",
                         "next_id", "political_cost", "forfeited"}:
            raise ValueError("invalid checkpoint state fields")
        institutions = tuple(Institution(**{**i, "charter": Charter(**i["charter"]),
                                             "members": tuple(i["members"]),
                                             "bonds": tuple(Bond(**b) for b in i["bonds"])}) for i in data["institutions"])
        proposals = tuple(Proposal(**{**p, "charter": None if p["charter"] is None else Charter(**p["charter"])})
                          for p in data["proposals"])
        state = State(physical.restore(data["world"]), PoliticalConfig(**data["config"]), institutions,
                      proposals, tuple(Evidence(**e) for e in data["evidence"]),
                      tuple(Cache(**c) for c in data["caches"]), data["next_id"], data["political_cost"], data["forfeited"])
        _validate(state)
        if snapshot(state) != checkpoint:
            raise ValueError("noncanonical checkpoint")
        return state
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError("malformed political checkpoint") from exc
