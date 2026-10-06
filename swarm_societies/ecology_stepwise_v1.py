"""Explicit, restorable transitions with frozen world-model-v1 episode parity.

This module is a separately versioned evaluator engine. Its ordinary actor
observations are exactly the legacy payloads, and its compatibility wrapper
returns the complete frozen result schema and hashes. New current-tick sensor
packets are released only after finish_tick; begin_tick does not release growth.
Snapshots contain evaluator-only laws, RNG and material state and must never be
passed to a planner. The engine is not a security boundary against trusted callers
inspecting its Python attributes.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import random

from .candidate import CandidateError, CandidateProgram, as_program, clean_json
from .ecology_world_model_v1 import (
    EcologyConfig, WorldParameters, OBSERVATION_MODES, _patch_measurement,
    bounded, gini,
)

SNAPSHOT_VERSION = 'ecology-stepwise-v1'


class PhaseError(ValueError):
    """A requested transition or observation is unavailable in this phase."""


def _program_snapshot(program):
    """Save mutable module literals as well as the explicit policy state.

    Source functions are recreated from the source and referenced by name inside
    containers. Lists/dicts retain aliases and cycles. Runtime generators and
    other unsupported Python objects fail explicitly without changing the world.
    This format is data, never a pickle or code evaluated beyond CandidateProgram.
    """
    function_names = {
        id(value): name for name, value in program.namespace.items()
        if callable(value) and name != '__builtins__'
    }
    objects, memo, active_tuples = [], {}, set()

    def encode(value):
        if value is None or isinstance(value, (bool, int, str)):
            return {'value': value}
        if isinstance(value, float):
            return {'float': value.hex()}
        if isinstance(value, bytes):
            return {'bytes': value.hex()}
        if isinstance(value, complex):
            return {'complex': [value.real.hex(), value.imag.hex()]}
        if id(value) in function_names:
            return {'function': function_names[id(value)]}
        kind = type(value).__name__
        # Reconstructing a set can change its iteration order, so a checkpoint
        # cannot promise exact continuation for policies depending on that order.
        if type(value) not in (list, dict, tuple):
            raise ValueError(f'Unsupported candidate module state in snapshot: {kind}')
        if id(value) in memo:
            if id(value) in active_tuples:
                raise ValueError('Unsupported tuple cycle in candidate module snapshot')
            return {'reference': memo[id(value)]}
        index = len(objects)
        memo[id(value)] = index
        objects.append(None)
        if isinstance(value, tuple):
            active_tuples.add(id(value))
        items = [[encode(k), encode(v)] for k, v in value.items()] if isinstance(value,
            dict) else [encode(v) for v in value]
        active_tuples.discard(id(value))
        objects[index] = {'kind': kind, 'items': items}
        return {'reference': index}

    values = {name: encode(value) for name, value in program.namespace.items()
              if name != '__builtins__' and id(value) not in function_names}
    return {'source': program.source, 'name': program.name,
            'values': values, 'objects': objects}


def _restore_program(saved):
    program = CandidateProgram(saved['source'], saved['name'])
    objects, visiting = {}, set()

    def decode(value):
        if 'value' in value:
            return value['value']
        if 'float' in value:
            return float.fromhex(value['float'])
        if 'bytes' in value:
            return bytes.fromhex(value['bytes'])
        if 'complex' in value:
            return complex(*(float.fromhex(x) for x in value['complex']))
        if 'function' in value:
            return program.namespace[value['function']]
        index = value['reference']
        if index in objects:
            return objects[index]
        row = saved['objects'][index]
        kind = row['kind']
        if kind == 'tuple':
            if index in visiting:
                raise ValueError('Unsupported tuple cycle in candidate module snapshot')
            visiting.add(index)
            objects[index] = tuple(decode(x) for x in row['items'])
            visiting.remove(index)
        elif kind == 'list':
            objects[index] = []
            objects[index].extend(decode(x) for x in row['items'])
        elif kind == 'dict':
            objects[index] = {}
            for key, item in row['items']:
                objects[index][decode(key)] = decode(item)
        elif kind == 'set':
            objects[index] = set()
            objects[index].update(decode(x) for x in row['items'])
        else:
            raise ValueError(f'Unsupported candidate snapshot object: {kind}')
        return objects[index]

    for name, value in saved['values'].items():
        program.namespace[name] = decode(value)
    return program


class StepwiseEcology:
    """Strict ready -> institutions -> members -> ready/complete lifecycle.

    Override mappings patch a default policy's decision; its function is still
    called once and its returned private/shared state remains authoritative.
    Source-level module memory is also kept independent in restored branches.
    """

    def __init__(self, programs, config=None, seed=0, replay=False,
                 member_programs=None, *, world_parameters=None,
                 observation_mode='local'):
        self.reset(programs, config, seed, replay, member_programs,
                   world_parameters=world_parameters,
                   observation_mode=observation_mode)

    def reset(self, programs, config=None, seed=0, replay=False,
              member_programs=None, *, world_parameters=None,
              observation_mode='local'):
        self.__dict__.clear()
        self.phase = 'uninitialized'
        self.config, self.seed = config, seed
        self.replay, self.observation_mode = replay, observation_mode
        self.config = self.config or EcologyConfig(n_societies=len(programs))
        if isinstance(self.config, dict):
            self.config = EcologyConfig(**self.config)
        self.config.validate()
        if isinstance(world_parameters, dict):
            world_parameters = WorldParameters(**world_parameters)
        world_parameters = WorldParameters() if world_parameters is None else world_parameters
        if not isinstance(world_parameters, WorldParameters):
            raise ValueError('world_parameters must be a WorldParameters or dictionary')
        world_parameters.validate()
        if self.observation_mode not in OBSERVATION_MODES:
            raise ValueError(f'unknown observation mode: {self.observation_mode}')
        self.law = WorldParameters(**{**asdict(world_parameters),
            'r': self.config.regeneration if world_parameters.r is None else world_parameters.r})
        self.law.validate()
        self.S, self.M = (self.config.n_societies, self.config.members_per_society)
        if len(programs) != self.S:
            raise ValueError('institution program count does not match society count')
        self.inst = [as_program(p) for p in programs]
        if member_programs is None:
            member_programs = [[p] * self.M for p in programs]
        if len(member_programs) != self.S or any((len(row) != self.M for row in member_programs)):
            raise ValueError('member program matrix must have society × member shape')
        self.policies = [[as_program(p) for p in row] for row in member_programs]
        self.rng = random.Random(seed)
        self.productivity = [[self.rng.uniform(0.85, 1.15) for m in range(self.M)] for s in range(self.S)]
        self.drought = [self.config.drought_factor * self.rng.uniform(0.85, 1.15) for s in range(self.S)]
        self.societies = [{'id': s, 'treasury': 0.0, 'infrastructure': 0.0, 'defense': 0.0,
            'members': [{'id': m, 'wealth': self.config.initial_wealth, 'private': {},
            'utility': 0.0, 'consumed': 0.0, 'shortfall': 0.0, 'action': 'rest', 'target': s,
            'patch': s} for m in range(self.M)], 'shared': {}, 'reports': [],
            'messages': {}} for s in range(self.S)]
        self.patches = [self.config.initial_patch] * self.S
        self.frames, self.rows = ([], [])
        self.learning_observations, self.regeneration_audit = ([], [])
        self.patch_measurements, self.member_receipts, self.institution_receipts = ([], [], [])
        self.totals = {'regeneration': 0.0, 'consumption': 0.0, 'effort_cost': 0.0, 'raid_destruction': 0.0,
            'investment': 0.0, 'defense': 0.0}
        self.initial_liquid = self.S * (self.config.initial_patch + self.M * self.config.initial_wealth)
        self.member_records = [[{'harvest': 0.0, 'contribution': 0.0, 'tax': 0.0, 'raid_gain': 0.0,
            'raid_loss': 0.0, 'share': 0.0, 'received': 0.0,
            'actions': {}} for m in range(self.M)] for s in range(self.S)]
        self.tick = 0
        self.phase = 'ready'
        self._completed = None
        self._institution_observations = None
        self._member_observations = None
        return self

    def _require(self, phase):
        if self.phase != phase:
            raise PhaseError(f'Expected {phase} phase, got {self.phase}')

    def begin_tick(self):
        """Draw the frozen tick inputs and return ordinary institution payloads.

        Renewal has occurred but its instrumented measurements stay unavailable
        until the completed reporting boundary. Returned payloads are copies.
        """
        self._require('ready')
        self.events, self.decisions = ([], [])
        self.tick_receipts = [[{'event_id': f'member:{self.tick}:{s}:{m}', 'tick': self.tick, 'society_id': s,
            'member_id': m, 'phase': 'after_allocation', 'wealth_before': member['wealth'],
            'cost': 0.0, 'tax': 0.0, 'harvest': 0.0, 'contribution': 0.0, 'share': 0.0,
            'raid_gain': 0.0, 'raid_loss': 0.0, 'redistribution': 0.0, 'consumption': 0.0,
            'denied': False, 'supply_limited': False} for m,
            member in enumerate(soc['members'])] for s, soc in enumerate(self.societies)]
        self.tick_metrics = [{'harvest': 0.0, 'contribution': 0.0, 'tax': 0.0, 'investment': 0.0,
            'aid_given': 0.0, 'aid_received': 0.0, 'external_harm': 0.0, 'harm_received': 0.0,
            'within_conflict': 0.0, 'raid_gain': 0.0, 'consumption': 0.0, 'shortfall': 0.0,
            'raid_attempts': 0.0, 'within_raid_attempts': 0.0, 'inter_raid_attempts': 0.0,
            'redistribution': 0.0} for _ in range(self.S)]
        # Every environmental input is drawn before policies, even if unused.
        self.weather = [self.rng.uniform(0.85, 1.15) for _ in range(self.S)]
        self.raid_draw = [[self.rng.random() for _ in range(self.M)] for _ in range(self.S)]
        self.victim_draw = [[self.rng.randrange(self.M) for _ in range(self.M)] for _ in range(self.S)]
        self.order = [(s, m) for s in range(self.S) for m in range(self.M)]
        self.rng.shuffle(self.order)
        for soc in self.societies:
            soc['infrastructure'] *= self.law.rho
        self.infrastructure_after_decay = [soc['infrastructure'] for soc in self.societies]
        self.phase_measurements = []
        for s, soc in enumerate(self.societies):
            self.phase_measurements.append(_patch_measurement(self.tick, s, 'after_decay', self.patches[s],
                soc['infrastructure']))
        for s, soc in enumerate(self.societies):
            other_total = sum((other['infrastructure'] for j, other in enumerate(self.societies) if j != s))
            spillover = self.law.g * other_total / (self.S - 1)
            factor = self.drought[s] if self.config.enable_disturbance and self.tick >= self.config.disturbance_tick else 1.0
            stock_before = self.patches[s]
            flow = self.law.r * self.weather[s] * factor + self.law.b * soc['infrastructure'] + spillover
            growth = min(max(0.0, self.config.patch_capacity - self.patches[s]), flow)
            self.patches[s] += growth
            self.totals['regeneration'] += growth
            growth_packet = {'event_id': f'growth:{self.tick}:{s}', 'tick': self.tick, 'society_id': s,
                'patch': s, 'phase': 'before_actions', 'stock_before': stock_before,
                'stock_after': self.patches[s], 'capacity': self.config.patch_capacity,
                'capacity_gap': max(0.0, self.config.patch_capacity - stock_before),
                'own_infrastructure': soc['infrastructure'], 'growth': growth,
                'censored': self.patches[s] >= self.config.patch_capacity, 'measurement_precision': 0.0}
            self.regeneration_audit.append({**growth_packet,
                'other_infrastructure': other_total / (self.S - 1), 'regime': factor})
            if self.observation_mode == 'full_observation_control':
                growth_packet['other_infrastructure'] = other_total / (self.S - 1)
            self.learning_observations.append(growth_packet)
            self.phase_measurements.append(_patch_measurement(self.tick, s, 'before_actions', self.patches[s],
                soc['infrastructure']))
        # The frozen engine calls each institution inside the renewal loop.
        # Its payload contains only its own infrastructure, wealth and reports;
        # no intervening policy can observe another patch's renewal progress.
        self._institution_observations = []
        for s, soc in enumerate(self.societies):
            observation = {'tick': self.tick, 'society_id': s, 'n_societies': self.S,
                'treasury': soc['treasury'], 'infrastructure': soc['infrastructure'],
                'mean_wealth': sum((m['wealth'] for m in soc['members'])) / self.M,
                'members': [{'id': m['id'], 'wealth': round(m['wealth'],
                6)} for m in soc['members']], 'reports': soc['reports']}
            self._institution_observations.append(observation)
        self.phase = 'institutions'
        return deepcopy(self._institution_observations)

    def set_institution_decisions(self, overrides=None):
        """Call prescribed institutions and patch specified current decisions.

        Keys are society IDs. Values may alter material decision fields only;
        state/messages are the prescribed policy's output, never override input.
        The actual investment field is the frozen name ``public_fraction``.
        """
        self._require('institutions')
        overrides = self._validate_overrides(overrides, member=False)
        try:
            for s, soc in enumerate(self.societies):
                observation = self._institution_observations[s]
                decision = self.inst[s].call('institution', observation, soc['shared'])
                soc['shared'] = clean_json(decision.get('state', {}), 8192)
                if not isinstance(soc['shared'], dict):
                    raise CandidateError('institution state must be a dictionary')
                soc['messages'] = clean_json(decision.get('messages', {}), 8192)
                if not isinstance(soc['messages'], dict):
                    raise CandidateError('institution messages must be a dictionary')
                decision.update(overrides.get(s, {}))
                self.decisions.append(decision)
            self._member_observations = [[None for _ in range(self.M)]
                                         for _ in range(self.S)]
            for s, m in self.order:
                soc, member = self.societies[s], self.societies[s]['members'][m]
                visible = sorted({s, (s + 1 + (m + self.tick) % (self.S-1)) % self.S})
                observation = {'tick': self.tick, 'society_id': s, 'member_id': m, 'n_societies': self.S,
                    'n_members': self.M, 'wealth': member['wealth'],
                    'productivity': self.productivity[s][m],
                    'infrastructure': soc['infrastructure'],
                    'tax_rate': bounded(self.decisions[s].get('tax_rate', 0), 0, 0.8),
                    'patches': [{'id': p, 'stock': round(self.patches[p],
                    6)} for p in visible], 'messages': soc['messages'], 'last_action': member['action']}
                self._member_observations[s][m] = observation
        except Exception:
            self.phase = 'failed'
            raise
        self.phase = 'members'
        return deepcopy(self.decisions)

    def member_observations(self):
        """Return the legacy member payload matrix only after institutions act."""
        self._require('members')
        return deepcopy(self._member_observations)

    def _validate_overrides(self, overrides, *, member):
        if overrides is None:
            return {}
        if not isinstance(overrides, dict):
            raise ValueError('Overrides must be a dictionary keyed by actor identity')
        allowed = ({'action', 'target', 'effort', 'message'} if member else
                   {'tax_rate', 'public_fraction', 'defense_fraction',
                    'reserve_fraction', 'redistribution', 'raid_permission'})
        result = {}
        for key, value in overrides.items():
            if member:
                valid = (isinstance(key, tuple) and len(key) == 2 and
                         all(type(i) is int for i in key) and
                         0 <= key[0] < self.S and 0 <= key[1] < self.M)
            else:
                valid = type(key) is int and 0 <= key < self.S
            if not valid:
                raise ValueError(f'Invalid override actor: {key!r}')
            if not isinstance(value, dict) or not set(value).issubset(allowed):
                raise ValueError('Override contains unsupported fields or policy memory')
            result[key] = clean_json(value)
        return result

    def finish_tick(self, member_actions=None):
        """Call member policies, resolve actions and return complete tick records.

        The policy invocation order, resource resolution order, floating-point
        operation order and accounting all match the frozen whole-episode engine.
        Current growth measurements are first released at this boundary.
        """
        self._require('members')
        member_actions = self._validate_overrides(member_actions, member=True)
        offsets = {name: len(getattr(self, name)) for name in
                   ('learning_observations', 'patch_measurements', 'member_receipts',
                    'institution_receipts', 'rows', 'frames')}
        try:
            self.actions, self.next_reports = ({}, [[] for _ in range(self.S)])
            for s, m in self.order:
                soc, member = (self.societies[s], self.societies[s]['members'][m])
                visible = sorted({s, (s + 1 + (m + self.tick) % (self.S - 1)) % self.S})
                observation = self._member_observations[s][m]
                answer = self.policies[s][m].call('member_policy', observation, member['private'])
                answer.update(member_actions.get((s, m), {}))
                member['private'] = clean_json(answer.get('state', {}), 8192)
                if not isinstance(member['private'], dict):
                    raise CandidateError('member state must be a dictionary')
                action = answer.get('action', 'rest')
                if action not in ('harvest', 'contribute', 'raid', 'share', 'rest', 'guard'):
                    raise CandidateError(f'unknown member action: {action}')
                try:
                    target = int(answer.get('target', s)) % self.S
                except (TypeError, ValueError) as exc:
                    raise CandidateError('invalid action target') from exc
                requested_target = target
                if action == 'harvest' and target not in visible:
                    target = s
                effort = bounded(answer.get('effort', 1))
                self.tick_receipts[s][m].update(requested_action=action, requested_target=requested_target,
                    action=action, target=target, effort=effort, productivity=self.productivity[s][m])
                message = clean_json(answer.get('message', {}), 1024)
                if not isinstance(message, dict):
                    raise CandidateError('member message must be a dictionary')
                self.next_reports[s].append({'member': m, 'message': message})
                member.update(action=action, target=target, patch=target if action == 'harvest' else s)
                self.actions[s, m] = (action, target, effort)
                record = self.member_records[s][m]
                record['actions'][action] = record['actions'].get(action, 0) + 1
            for s, m in self.order:
                soc, member = (self.societies[s], self.societies[s]['members'][m])
                action, target, effort = self.actions[s, m]
                record, metric = (self.member_records[s][m], self.tick_metrics[s])
                receipt = self.tick_receipts[s][m]
                receipt['wealth_at_resolution'] = member['wealth']
                cost = min(member['wealth'], self.law.c * effort) if action not in ('rest',) else 0.0
                member['wealth'] -= cost
                self.totals['effort_cost'] += cost
                receipt['cost'] = cost
                if action == 'harvest':
                    amount = min(self.patches[target], self.law.h * self.productivity[s][m] * effort)
                    self.patches[target] -= amount
                    tax = amount * bounded(self.decisions[s].get('tax_rate', 0), 0, 0.8)
                    member['wealth'] += amount - tax
                    soc['treasury'] += tax
                    metric['harvest'] += amount
                    metric['tax'] += tax
                    record['harvest'] += amount
                    record['tax'] += tax
                    receipt.update(harvest=amount, tax=tax, supply_limited=self.patches[target] <= 0.0)
                    self.events.append({'kind': 'harvest', 'society': s, 'member': m, 'patch': target,
                        'amount': amount})
                    if tax:
                        self.events.append({'kind': 'tax', 'society': s, 'member': m, 'amount': tax})
                elif action in ('contribute', 'share'):
                    amount = min(member['wealth'], 2.0 * effort)
                    member['wealth'] -= amount
                    receiver = s if action == 'contribute' else target
                    self.societies[receiver]['treasury'] += amount
                    if receiver == s:
                        metric['contribution'] += amount
                        record['contribution'] += amount
                        receipt['contribution'] = amount
                    else:
                        metric['aid_given'] += amount
                        self.tick_metrics[receiver]['aid_received'] += amount
                        record['share'] += amount
                        receipt['share'] = amount
                    self.events.append({'kind': action, 'society': s, 'member': m, 'target_society': receiver,
                        'amount': amount})
                elif action == 'raid':
                    metric['raid_attempts'] += 1
                    metric['within_raid_attempts' if s == target else 'inter_raid_attempts'] += 1
                    if target != s and (not self.decisions[s].get('raid_permission', True)):
                        receipt['denied'] = True
                        continue
                    victim_id = self.victim_draw[s][m]
                    if target == s and victim_id == m:
                        victim_id = (m + 1) % self.M
                    victim_soc, victim = (self.societies[target], self.societies[target]['members'][victim_id])
                    guards = sum((self.actions[target, k][0] == 'guard' for k in range(self.M)))
                    defense = victim_soc['defense'] + 0.4 * guards
                    success = self.raid_draw[s][m] < 0.75 / (1.0 + defense)
                    amount = min(victim['wealth'], 2.3 * effort / (1.0 + 0.4 * defense)) if success else 0.0
                    gain, loss = (amount * 0.72, amount * 0.28)
                    victim['wealth'] -= amount
                    member['wealth'] += gain
                    self.totals['raid_destruction'] += loss
                    metric['raid_gain'] += gain
                    record['raid_gain'] += gain
                    self.member_records[target][victim_id]['raid_loss'] += amount
                    receipt['raid_gain'] += gain
                    self.tick_receipts[target][victim_id]['raid_loss'] += amount
                    if target == s:
                        metric['within_conflict'] += amount
                    else:
                        metric['external_harm'] += amount
                        self.tick_metrics[target]['harm_received'] += amount
                    self.events.append({'kind': 'raid', 'society': s, 'member': m, 'target_society': target,
                        'target_member': victim_id, 'amount': gain, 'loss': loss})
            for s, soc in enumerate(self.societies):
                self.phase_measurements.append(_patch_measurement(self.tick, s, 'after_actions',
                    self.patches[s], soc['infrastructure']))
            for s, soc in enumerate(self.societies):
                metric, decision = (self.tick_metrics[s], self.decisions[s])
                public = bounded(decision.get('public_fraction', 0))
                defense = bounded(decision.get('defense_fraction', 0))
                reserve = bounded(decision.get('reserve_fraction', 0))
                norm = max(1.0, public + defense + reserve)
                public, defense, reserve = (public / norm, defense / norm, reserve / norm)
                budget = soc['treasury']
                invest, defend = (budget * public, budget * defense)
                # Keep the frozen arithmetic order, including default eta.
                soc['infrastructure'] += invest / (8.0 * self.M) if self.law.eta == 0.125 else invest * self.law.eta / self.M
                soc['defense'] = 0.65 * soc['defense'] + defend / self.M
                self.totals['investment'] += invest
                self.totals['defense'] += defend
                metric['investment'] += invest
                amount = budget * max(0.0, 1 - public - defense - reserve)
                weights = decision.get('redistribution', [1.0] * self.M)
                if not isinstance(weights, list) or len(weights) != self.M:
                    raise CandidateError('redistribution must be a member-length list')
                weights = [bounded(w, 0, 100) for w in weights]
                if sum(weights) <= 0:
                    weights = [1.0] * self.M
                total_weight = sum(weights)
                for m, member in enumerate(soc['members']):
                    transfer = amount * weights[m] / total_weight
                    member['wealth'] += transfer
                    metric['redistribution'] += transfer
                    self.member_records[s][m]['received'] += transfer
                    self.tick_receipts[s][m]['redistribution'] = transfer
                    consumed = min(member['wealth'], self.config.consumption_need)
                    member['wealth'] -= consumed
                    member['consumed'] += consumed
                    member['shortfall'] += self.config.consumption_need - consumed
                    member['utility'] = member['consumed'] + 0.2 * member['wealth']
                    self.totals['consumption'] += consumed
                    metric['consumption'] += consumed
                    metric['shortfall'] += self.config.consumption_need - consumed
                    self.tick_receipts[s][m].update(consumption=consumed, wealth_after=member['wealth'])
                    if transfer:
                        self.events.append({'kind': 'redistribute', 'society': s, 'member': m, 'amount': transfer})
                soc['treasury'] = max(0.0, budget - invest - defend - amount)
                self.institution_receipts.append({'event_id': f'institution:{self.tick}:{s}',
                    'tick': self.tick, 'society_id': s, 'phase': 'after_allocation',
                    'budget': budget, 'tax': metric['tax'],
                    'contribution': metric['contribution'],
                    'aid_received': metric['aid_received'], 'investment': invest,
                    'defense_expenditure': defend, 'redistribution': amount,
                    'treasury_after': soc['treasury'],
                    'infrastructure_after_decay': self.infrastructure_after_decay[s],
                    'infrastructure_after_allocation': soc['infrastructure'], 'n_members': self.M})
                soc['reports'] = self.next_reports[s]
                if invest:
                    self.events.append({'kind': 'invest', 'society': s, 'amount': invest})
                wealth = [member['wealth'] for member in soc['members']]
                metric.update(tick=self.tick, society=s,
                    phase='post' if self.tick >= self.config.disturbance_tick else 'pre',
                    mean_wealth=sum(wealth) / self.M, wealth_gini=gini(wealth),
                    infrastructure=soc['infrastructure'], treasury=soc['treasury'],
                    welfare=(metric['consumption'] - 0.5 * metric['shortfall']) / self.M,
                    mean_individual_utility=sum((member['utility'] for member in soc['members'])) / self.M)
                self.rows.append(metric)
            for s, soc in enumerate(self.societies):
                self.phase_measurements.append(_patch_measurement(self.tick, s, 'after_allocation',
                    self.patches[s], soc['infrastructure']))
            for s, soc in enumerate(self.societies):
                for m in range(self.M):
                    self.member_receipts.append(self.tick_receipts[s][m])
                    visible = {s, (s + 1 + (m + self.tick) % (self.S - 1)) % self.S}
                    for measurement in self.phase_measurements:
                        if measurement['patch'] in visible:
                            self.patch_measurements.append({**measurement, 'society_id': s, 'member_id': m})
            if self.replay:
                self.frames.append({'tick': self.tick,
                    'disturbed': self.config.enable_disturbance and self.tick >= self.config.disturbance_tick,
                    'patches': list(self.patches), 'societies': [{'id': s['id'],
                    'treasury': s['treasury'], 'infrastructure': s['infrastructure'],
                    'members': [{k: m[k] for k in ('id', 'wealth', 'action', 'target',
                    'patch')} for m in s['members']]} for s in self.societies], 'events': self.events})
        except Exception:
            self.phase = 'failed'
            raise
        self._completed = {
            'tick': self.tick,
            'learning_observations': self.learning_observations[offsets['learning_observations']-self.S:],
            'local_observations': {
                name: getattr(self, name)[offsets[name]:] for name in
                ('patch_measurements', 'member_receipts', 'institution_receipts')},
            'timeseries': self.rows[offsets['rows']:],
            'replay': self.frames[offsets['frames']:],
        }
        self.tick += 1
        self.phase = 'complete' if self.tick == self.config.ticks else 'ready'
        self._institution_observations = None
        self._member_observations = None
        return deepcopy(self._completed)

    def completed_observations(self):
        """Read the most recently completed tick, even while the next is pending."""
        if self._completed is None:
            raise PhaseError('No tick has completed its reporting phase')
        return deepcopy(self._completed)

    def step(self, institution_decisions=None, member_actions=None):
        """Advance one whole tick from ready, optionally applying overrides."""
        self._require('ready')
        # Reject malformed inputs before drawing any randomness.
        self._validate_overrides(institution_decisions, member=False)
        self._validate_overrides(member_actions, member=True)
        self.begin_tick()
        self.set_institution_decisions(institution_decisions)
        return self.finish_tick(member_actions)

    def snapshot(self):
        """Return copied evaluator-only state; never a legal planner observation.

        The result survives a JSON round trip. Unsupported candidate module
        objects fail explicitly, without modifying the engine or its RNG.
        """
        if self.phase not in ('ready', 'institutions', 'members', 'complete'):
            raise PhaseError(f'Cannot snapshot phase {self.phase}')
        excluded = {'config', 'law', 'rng', 'inst', 'policies', 'actions'}
        saved = {
            'snapshot_version': SNAPSHOT_VERSION,
            'config': asdict(self.config), 'law': asdict(self.law),
            'rng_state': deepcopy(self.rng.getstate()),
            'institutions': [_program_snapshot(p) for p in self.inst],
            'members': [[_program_snapshot(p) for p in row] for row in self.policies],
            'state': deepcopy({k: v for k, v in self.__dict__.items() if k not in excluded}),
        }
        # No tuple-keyed actions are pending at a legal boundary. They are
        # already fully reflected in receipts, material state and policy memory.
        return json.loads(json.dumps(saved, allow_nan=False))

    @classmethod
    def from_snapshot(cls, snapshot):
        """Restore an independent evaluator branch without replaying policies."""
        saved = deepcopy(snapshot)
        if saved.get('snapshot_version') != SNAPSHOT_VERSION:
            raise ValueError('Unsupported stepwise ecology snapshot version')
        restored = cls.__new__(cls)
        restored.__dict__.update(saved['state'])
        restored.config = EcologyConfig(**saved['config'])
        restored.config.validate()
        restored.law = WorldParameters(**saved['law'])
        restored.law.validate()
        restored.rng = random.Random()
        def tuples(value):
            return tuple(tuples(x) for x in value) if isinstance(value, (list, tuple)) else value
        restored.rng.setstate(tuples(saved['rng_state']))
        restored.inst = [_restore_program(p) for p in saved['institutions']]
        restored.policies = [[_restore_program(p) for p in row] for row in saved['members']]
        if restored.phase not in ('ready', 'institutions', 'members', 'complete'):
            raise ValueError('Invalid snapshot phase')
        return restored

    def result(self):
        """Return the exact frozen episode result, only after the final tick."""
        self._require('complete')
        society_metrics = []
        for s, soc in enumerate(self.societies):
            phases = {}
            for phase in ('pre', 'post', 'overall'):
                selected = [row for row in self.rows if row['society'] == s and (phase == 'overall' or row['phase'] == phase)]
                means = ('welfare', 'mean_wealth', 'wealth_gini', 'infrastructure', 'treasury')
                sums = ('harvest', 'contribution', 'tax', 'investment', 'aid_given', 'aid_received',
                    'external_harm', 'harm_received', 'within_conflict', 'raid_gain',
                    'consumption', 'shortfall', 'raid_attempts', 'within_raid_attempts',
                    'inter_raid_attempts', 'redistribution')
                phases[phase] = {key: sum((row[key] for row in selected)) / len(selected) for key in means}
                phases[phase].update({key: sum((row[key] for row in selected)) for key in sums})
                phases[phase]['cooperation_within'] = phases[phase]['contribution'] + phases[phase]['tax']
                phases[phase]['cooperation_between'] = phases[phase]['aid_given']
            phases.update(society_id=s, final_mean_wealth=sum((m['wealth'] for m in soc['members'])) / self.M,
                mean_individual_utility=sum((m['utility'] for m in soc['members'])) / self.M,
                adaptation=phases['post']['welfare'] - phases['pre']['welfare'])
            society_metrics.append(phases)
        members = [{**self.member_records[s][m], 'society_id': s, 'member_id': m,
            'utility': member['utility'], 'consumption': member['consumed'],
            'shortfall': member['shortfall'], 'final_wealth': member['wealth']} for s,
            soc in enumerate(self.societies) for m, member in enumerate(soc['members'])]
        final_liquid = sum(self.patches) + sum((s['treasury'] + sum((m['wealth'] for m in s['members'])) for s in self.societies))
        expected = self.initial_liquid + self.totals['regeneration'] - sum((v for k,
            v in self.totals.items() if k != 'regeneration'))
        if abs(final_liquid - expected) > 1e-07 * max(1.0, expected):
            raise AssertionError('material accounting violated')
        config_data = asdict(self.config)
        result = {'schema_version': 2, 'seed': self.seed, 'config': config_data,
            'program_hashes': [p.digest for p in self.inst],
            'member_program_hashes': [[p.digest for p in row] for row in self.policies],
            'society_metrics': society_metrics, 'member_metrics': members,
            'aggregate': {'mean_welfare': sum((s['overall']['welfare'] for s in society_metrics)) / self.S,
            'pre_welfare': sum((s['pre']['welfare'] for s in society_metrics)) / self.S,
            'post_welfare': sum((s['post']['welfare'] for s in society_metrics)) / self.S,
            'external_harm': sum((s['overall']['external_harm'] for s in society_metrics)),
            'mean_individual_utility': sum((m['utility'] for m in members)) / len(members)},
            'ledger': {**self.totals, 'initial_liquid': self.initial_liquid,
            'final_liquid': final_liquid, 'residual': final_liquid - expected},
            'timeseries': self.rows, 'replay': self.frames}
        result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',',
            ':')).encode()).hexdigest()
        result['legacy_digest'] = result.pop('digest')
        result.update(schema_version=3, simulator_version='world-model-v1',
            observation_mode=self.observation_mode,
            learning_observations=self.learning_observations,
            local_observations={'patch_measurements': self.patch_measurements,
            'member_receipts': self.member_receipts,
            'institution_receipts': self.institution_receipts},
            audit={'world_parameters': asdict(self.law), 'regeneration': self.regeneration_audit})
        result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',',
            ':')).encode()).hexdigest()
        return deepcopy(result)


def run_episode(programs, config=None, seed=0, replay=False, member_programs=None,
                *, world_parameters=None, observation_mode='local'):
    """Compatibility wrapper with complete frozen trajectory and result parity."""
    ecology = StepwiseEcology(programs, config, seed, replay, member_programs,
                              world_parameters=world_parameters,
                              observation_mode=observation_mode)
    while ecology.phase != 'complete':
        ecology.step()
    return ecology.result()
