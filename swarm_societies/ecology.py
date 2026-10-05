"""Deterministic interacting-society ecology with protected material accounting."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
from .candidate import CandidateError, as_program, clean_json


@dataclass(frozen=True)
class EcologyConfig:
    n_societies: int = 3
    members_per_society: int = 6
    ticks: int = 80
    disturbance_tick: int = 40
    initial_wealth: float = 4.0
    initial_patch: float = 35.0
    patch_capacity: float = 60.0
    regeneration: float = 8.5
    consumption_need: float = 0.85
    drought_factor: float = 0.36

    def validate(self):
        if self.n_societies < 2 or self.members_per_society < 2:
            raise ValueError('at least two societies and two members per society required')
        if not 0 < self.disturbance_tick < self.ticks:
            raise ValueError('disturbance must occur within episode')
        for name in ('initial_wealth', 'initial_patch', 'patch_capacity', 'regeneration', 'consumption_need', 'drought_factor'):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'invalid {name}')


def bounded(value, low=0.0, high=1.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return min(high, max(low, value)) if math.isfinite(value) else low


def gini(values):
    total = sum(values)
    return sum(abs(a-b) for a in values for b in values) / (2 * len(values) * total) if total > 0 else 0.0


def run_episode(programs, config=None, seed=0, replay=False, member_programs=None):
    """Evaluate institution programs against optional heterogeneous member programs.

    No evaluator seed, future weather, peer private state or fitness is exposed to
    a candidate. JSON copies sever mutable references. Any candidate error invalidates
    the episode; the harness must record it, never substitute a successful fallback.
    """
    config = config or EcologyConfig(n_societies=len(programs))
    if isinstance(config, dict):
        config = EcologyConfig(**config)
    config.validate()
    S, M = config.n_societies, config.members_per_society
    if len(programs) != S:
        raise ValueError('institution program count does not match society count')
    inst = [as_program(p) for p in programs]
    if member_programs is None:
        member_programs = [[p] * M for p in programs]
    if len(member_programs) != S or any(len(row) != M for row in member_programs):
        raise ValueError('member program matrix must have society × member shape')
    policies = [[as_program(p) for p in row] for row in member_programs]
    rng = random.Random(seed)
    productivity = [[rng.uniform(0.85, 1.15) for m in range(M)] for s in range(S)]
    drought = [config.drought_factor * rng.uniform(0.85, 1.15) for s in range(S)]
    societies = [{'id': s, 'treasury': 0.0, 'infrastructure': 0.0, 'defense': 0.0,
                  'members': [{'id': m, 'wealth': config.initial_wealth, 'private': {},
                               'utility': 0.0, 'consumed': 0.0, 'shortfall': 0.0,
                               'action': 'rest', 'target': s, 'patch': s} for m in range(M)],
                  'shared': {}, 'reports': [], 'messages': {}} for s in range(S)]
    patches = [config.initial_patch] * S
    frames, rows = [], []
    totals = {'regeneration': 0.0, 'consumption': 0.0, 'effort_cost': 0.0,
              'raid_destruction': 0.0, 'investment': 0.0, 'defense': 0.0}
    initial_liquid = S * (config.initial_patch + M * config.initial_wealth)
    member_records = [[{'harvest': 0.0, 'contribution': 0.0, 'tax': 0.0,
                         'raid_gain': 0.0, 'raid_loss': 0.0, 'share': 0.0,
                         'received': 0.0, 'actions': {}} for m in range(M)] for s in range(S)]
    for tick in range(config.ticks):
        events, decisions = [], []
        tick_metrics = [{'harvest': 0., 'contribution': 0., 'tax': 0., 'investment': 0.,
                         'aid_given': 0., 'aid_received': 0., 'external_harm': 0.,
                         'harm_received': 0., 'within_conflict': 0., 'raid_gain': 0.,
                         'consumption': 0., 'shortfall': 0., 'raid_attempts': 0.,
                         'within_raid_attempts': 0., 'inter_raid_attempts': 0.,
                         'redistribution': 0.} for _ in range(S)]
        # Random environmental inputs are drawn irrespective of candidate actions.
        weather = [rng.uniform(.85, 1.15) for _ in range(S)]
        raid_draw = [[rng.random() for _ in range(M)] for _ in range(S)]
        victim_draw = [[rng.randrange(M) for _ in range(M)] for _ in range(S)]
        order = [(s, m) for s in range(S) for m in range(M)]
        rng.shuffle(order)
        for soc in societies:
            soc['infrastructure'] *= .96
        for s, soc in enumerate(societies):
            spillover = .08 * sum(other['infrastructure'] for j, other in enumerate(societies) if j != s) / (S-1)
            factor = drought[s] if tick >= config.disturbance_tick else 1.0
            flow = config.regeneration * weather[s] * factor + 2.2 * soc['infrastructure'] + spillover
            growth = min(max(0., config.patch_capacity-patches[s]), flow)
            patches[s] += growth
            totals['regeneration'] += growth
            observation = {'tick': tick, 'society_id': s, 'n_societies': S,
                           'treasury': soc['treasury'], 'infrastructure': soc['infrastructure'],
                           'mean_wealth': sum(m['wealth'] for m in soc['members']) / M,
                           'members': [{'id': m['id'], 'wealth': round(m['wealth'], 6)} for m in soc['members']],
                           'reports': soc['reports']}
            decision = inst[s].call('institution', observation, soc['shared'])
            soc['shared'] = clean_json(decision.get('state', {}), 8192)
            if not isinstance(soc['shared'], dict):
                raise CandidateError('institution state must be a dictionary')
            soc['messages'] = clean_json(decision.get('messages', {}), 8192)
            if not isinstance(soc['messages'], dict):
                raise CandidateError('institution messages must be a dictionary')
            decisions.append(decision)
        actions, next_reports = {}, [[] for _ in range(S)]
        for s, m in order:
            soc, member = societies[s], societies[s]['members'][m]
            visible = sorted({s, (s + 1 + (m + tick) % (S-1)) % S})
            observation = {'tick': tick, 'society_id': s, 'member_id': m, 'n_societies': S,
                           'n_members': M, 'wealth': member['wealth'],
                           'productivity': productivity[s][m], 'infrastructure': soc['infrastructure'],
                           'tax_rate': bounded(decisions[s].get('tax_rate', 0), 0, .8),
                           'patches': [{'id': p, 'stock': round(patches[p], 6)} for p in visible],
                           'messages': soc['messages'], 'last_action': member['action']}
            answer = policies[s][m].call('member_policy', observation, member['private'])
            member['private'] = clean_json(answer.get('state', {}), 8192)
            if not isinstance(member['private'], dict):
                raise CandidateError('member state must be a dictionary')
            action = answer.get('action', 'rest')
            if action not in ('harvest', 'contribute', 'raid', 'share', 'rest', 'guard'):
                raise CandidateError(f'unknown member action: {action}')
            try:
                target = int(answer.get('target', s)) % S
            except (TypeError, ValueError) as exc:
                raise CandidateError('invalid action target') from exc
            if action == 'harvest' and target not in visible:
                target = s  # a member cannot harvest an unobserved location this tick
            effort = bounded(answer.get('effort', 1))
            message = clean_json(answer.get('message', {}), 1024)
            if not isinstance(message, dict):
                raise CandidateError('member message must be a dictionary')
            next_reports[s].append({'member': m, 'message': message})
            member.update(action=action, target=target, patch=target if action == 'harvest' else s)
            actions[s, m] = (action, target, effort)
            record = member_records[s][m]
            record['actions'][action] = record['actions'].get(action, 0) + 1
        # Action intentions are simultaneous, scarce resource resolution has seeded order.
        for s, m in order:
            soc, member = societies[s], societies[s]['members'][m]
            action, target, effort = actions[s, m]
            record, metric = member_records[s][m], tick_metrics[s]
            cost = min(member['wealth'], .08 * effort) if action not in ('rest',) else 0.
            member['wealth'] -= cost
            totals['effort_cost'] += cost
            if action == 'harvest':
                amount = min(patches[target], 2.4 * productivity[s][m] * effort)
                patches[target] -= amount
                tax = amount * bounded(decisions[s].get('tax_rate', 0), 0, .8)
                member['wealth'] += amount-tax
                soc['treasury'] += tax
                metric['harvest'] += amount
                metric['tax'] += tax
                record['harvest'] += amount
                record['tax'] += tax
                events.append({'kind': 'harvest', 'society': s, 'member': m, 'patch': target, 'amount': amount})
                if tax:
                    events.append({'kind': 'tax', 'society': s, 'member': m, 'amount': tax})
            elif action in ('contribute', 'share'):
                amount = min(member['wealth'], 2.0 * effort)
                member['wealth'] -= amount
                receiver = s if action == 'contribute' else target
                societies[receiver]['treasury'] += amount
                if receiver == s:
                    metric['contribution'] += amount
                    record['contribution'] += amount
                else:
                    metric['aid_given'] += amount
                    tick_metrics[receiver]['aid_received'] += amount
                    record['share'] += amount
                events.append({'kind': action, 'society': s, 'member': m, 'target_society': receiver, 'amount': amount})
            elif action == 'raid':
                metric['raid_attempts'] += 1
                metric['within_raid_attempts' if s == target else 'inter_raid_attempts'] += 1
                if target != s and not decisions[s].get('raid_permission', True):
                    continue
                victim_id = victim_draw[s][m]
                if target == s and victim_id == m:
                    victim_id = (m+1) % M
                victim_soc, victim = societies[target], societies[target]['members'][victim_id]
                guards = sum(actions[target, k][0] == 'guard' for k in range(M))
                defense = victim_soc['defense'] + .4 * guards
                success = raid_draw[s][m] < .75 / (1. + defense)
                amount = min(victim['wealth'], 2.3 * effort / (1. + .4 * defense)) if success else 0.
                gain, loss = amount * .72, amount * .28
                victim['wealth'] -= amount
                member['wealth'] += gain
                totals['raid_destruction'] += loss
                metric['raid_gain'] += gain
                record['raid_gain'] += gain
                member_records[target][victim_id]['raid_loss'] += amount
                if target == s:
                    metric['within_conflict'] += amount
                else:
                    metric['external_harm'] += amount
                    tick_metrics[target]['harm_received'] += amount
                events.append({'kind': 'raid', 'society': s, 'member': m, 'target_society': target,
                               'target_member': victim_id, 'amount': gain, 'loss': loss})
        for s, soc in enumerate(societies):
            metric, decision = tick_metrics[s], decisions[s]
            public = bounded(decision.get('public_fraction', 0))
            defense = bounded(decision.get('defense_fraction', 0))
            reserve = bounded(decision.get('reserve_fraction', 0))
            norm = max(1., public+defense+reserve)
            public, defense, reserve = public/norm, defense/norm, reserve/norm
            budget = soc['treasury']
            invest, defend = budget*public, budget*defense
            soc['infrastructure'] += invest / (8.0 * M)
            soc['defense'] = .65 * soc['defense'] + defend / M
            totals['investment'] += invest
            totals['defense'] += defend
            metric['investment'] += invest
            amount = budget * max(0., 1-public-defense-reserve)
            weights = decision.get('redistribution', [1.] * M)
            if not isinstance(weights, list) or len(weights) != M:
                raise CandidateError('redistribution must be a member-length list')
            weights = [bounded(w, 0, 100) for w in weights]
            if sum(weights) <= 0:
                weights = [1.] * M
            total_weight = sum(weights)
            for m, member in enumerate(soc['members']):
                transfer = amount * weights[m] / total_weight
                member['wealth'] += transfer
                metric['redistribution'] += transfer
                member_records[s][m]['received'] += transfer
                consumed = min(member['wealth'], config.consumption_need)
                member['wealth'] -= consumed
                member['consumed'] += consumed
                member['shortfall'] += config.consumption_need-consumed
                member['utility'] = member['consumed'] + .2 * member['wealth']
                totals['consumption'] += consumed
                metric['consumption'] += consumed
                metric['shortfall'] += config.consumption_need-consumed
                if transfer:
                    events.append({'kind': 'redistribute', 'society': s, 'member': m, 'amount': transfer})
            soc['treasury'] = max(0., budget-invest-defend-amount)
            soc['reports'] = next_reports[s]
            if invest:
                events.append({'kind': 'invest', 'society': s, 'amount': invest})
            wealth = [member['wealth'] for member in soc['members']]
            metric.update(tick=tick, society=s, phase='post' if tick >= config.disturbance_tick else 'pre',
                          mean_wealth=sum(wealth)/M, wealth_gini=gini(wealth),
                          infrastructure=soc['infrastructure'], treasury=soc['treasury'],
                          welfare=(metric['consumption']-.5*metric['shortfall'])/M + .03*soc['infrastructure'],
                          mean_individual_utility=sum(member['utility'] for member in soc['members'])/M)
            rows.append(metric)
        if replay:
            frames.append({'tick': tick, 'disturbed': tick >= config.disturbance_tick,
                           'patches': list(patches),
                           'societies': [{'id': s['id'], 'treasury': s['treasury'],
                                          'infrastructure': s['infrastructure'],
                                          'members': [{k: m[k] for k in ('id','wealth','action','target','patch')}
                                                      for m in s['members']]} for s in societies],
                           'events': events})
    society_metrics = []
    for s, soc in enumerate(societies):
        phases = {}
        for phase in ('pre', 'post', 'overall'):
            selected = [row for row in rows if row['society'] == s and (phase == 'overall' or row['phase'] == phase)]
            means = ('welfare', 'mean_wealth', 'wealth_gini', 'infrastructure', 'treasury')
            sums = ('harvest','contribution','tax','investment','aid_given','aid_received','external_harm',
                    'harm_received','within_conflict','raid_gain','consumption','shortfall','raid_attempts',
                    'within_raid_attempts','inter_raid_attempts','redistribution')
            phases[phase] = {key: sum(row[key] for row in selected)/len(selected) for key in means}
            phases[phase].update({key: sum(row[key] for row in selected) for key in sums})
            phases[phase]['cooperation_within'] = phases[phase]['contribution'] + phases[phase]['tax']
            phases[phase]['cooperation_between'] = phases[phase]['aid_given']
        phases.update(society_id=s, final_mean_wealth=sum(m['wealth'] for m in soc['members'])/M,
                      mean_individual_utility=sum(m['utility'] for m in soc['members'])/M,
                      adaptation=phases['post']['welfare']-phases['pre']['welfare'])
        society_metrics.append(phases)
    members = [{**member_records[s][m], 'society_id':s,'member_id':m,
                'utility': member['utility'], 'consumption':member['consumed'],
                'shortfall':member['shortfall'],'final_wealth':member['wealth']}
               for s, soc in enumerate(societies) for m, member in enumerate(soc['members'])]
    final_liquid = sum(patches)+sum(s['treasury']+sum(m['wealth'] for m in s['members']) for s in societies)
    expected = initial_liquid+totals['regeneration']-sum(v for k,v in totals.items() if k != 'regeneration')
    if abs(final_liquid-expected) > 1e-7 * max(1., expected):
        raise AssertionError('material accounting violated')
    config_data = asdict(config)
    result = {'schema_version': 1, 'seed':seed, 'config':config_data,
              'program_hashes':[p.digest for p in inst],
              'member_program_hashes':[[p.digest for p in row] for row in policies],
              'society_metrics':society_metrics,'member_metrics':members,
              'aggregate':{'mean_welfare':sum(s['overall']['welfare'] for s in society_metrics)/S,
                           'pre_welfare':sum(s['pre']['welfare'] for s in society_metrics)/S,
                           'post_welfare':sum(s['post']['welfare'] for s in society_metrics)/S,
                           'external_harm':sum(s['overall']['external_harm'] for s in society_metrics),
                           'mean_individual_utility':sum(m['utility'] for m in members)/len(members)},
              'ledger':{**totals,'initial_liquid':initial_liquid,'final_liquid':final_liquid,
                        'residual':final_liquid-expected}, 'timeseries':rows,'replay':frames}
    result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    return result
