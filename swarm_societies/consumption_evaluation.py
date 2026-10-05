"""Trusted v2 selection; v1 simulator, protocol and recorded results stay frozen."""
from __future__ import annotations

import fcntl
import hashlib
import math
from pathlib import Path
import resource
import statistics
import time

from .candidate import CandidateProgram
from .consumption_study import make_search_cases, simulate_consumption
from .evaluation import ROOT, atomic_json, component_hashes, digest, read_json, snapshot_program, write_job_result as write_original_result

CONDITIONS = ('coevolution', 'fixed_institution')
FROZEN_FILES = (
    'swarm_societies/ecology_consumption_v2.py', 'swarm_societies/consumption_study.py',
    'swarm_societies/consumption_evaluation.py', 'swarm_societies/candidate.py',
    'swarm_societies/evaluation.py',
    'docs/protocol-consumption-v2.md', 'docs/evolution-prompt-consumption-v2.md',
    'scripts/evaluate_consumption_candidate.py',
)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def initialize_context(path, condition, replicate, replication_seed, *, cases=None):
    path = Path(path).resolve()
    if condition not in CONDITIONS:
        raise ValueError(f'Unknown condition: {condition}')
    if path.exists():
        old = read_json(path)
        if (old['condition'], old['replicate'], old['replication_seed']) != (condition, replicate, replication_seed):
            raise ValueError('Existing context belongs to a different condition/replicate')
        return old
    programs = [snapshot_program(ROOT/'seeds'/f'{name}.py', path.parent/'programs')
                for name in ('initial', 'cooperative', 'selfish')]
    state = {
        'version': 2, 'study': 'consumption-v2', 'condition': condition,
        'replicate': replicate, 'replication_seed': replication_seed,
        'n_societies': 3, 'members_per_society': 4,
        'search_cases': cases if cases is not None else make_search_cases(replication_seed),
        'initial_institutions': programs.copy(), 'initial_members': [[p]*4 for p in programs],
        'institutions': programs.copy(), 'members': [[p]*4 for p in programs],
        'evaluations': [], 'accepted_member_updates': 0, 'accepted_institution_updates': 0,
        'frozen_source_hashes': {name: file_hash(ROOT/name) for name in FROZEN_FILES},
        'objective': {'institution': 'mean consumption minus half shortfall per member per tick',
                      'member': '(consumption + 0.2 terminal wealth) / episode ticks'},
    }
    atomic_json(path, state)
    return state


def verify_frozen_sources(state):
    paths = state['institutions'] + state['initial_institutions']
    paths += [p for key in ('members', 'initial_members') for row in state[key] for p in row]
    for path in set(paths):
        if len(Path(path).stem) != 64 or file_hash(path) != Path(path).stem:
            raise ValueError(f'Population source checksum mismatch: {path}')
    for name, expected in state['frozen_source_hashes'].items():
        if file_hash(ROOT/name) != expected:
            raise ValueError(f'Frozen v2 source changed: {name}')
    if state['condition'] == 'fixed_institution' and state['institutions'] != state['initial_institutions']:
        raise ValueError('Fixed-institution condition has changed institutions')


def target_for(state, index):
    if index == 0:
        return 'initial', 0, None
    if state['condition'] == 'fixed_institution':
        kind, slot = 'member', index-1
    else:
        kind, slot = ('member' if index % 2 else 'institution'), (index-1)//2
    society = slot % state['n_societies']
    member = (slot // state['n_societies']) % state['members_per_society'] if kind == 'member' else None
    return kind, society, member


def objective(episode, kind, society, member):
    if kind == 'member':
        return next(row['normalized_utility'] for row in episode['member_metrics']
                    if row['society_id'] == society and row['member_id'] == member)
    return episode['society_metrics'][society]['overall']['welfare']


def write_job_result(results_dir, record):
    write_original_result(results_dir, record)
    path = Path(results_dir)/'metrics.json'
    metrics = read_json(path)
    metrics['public']['condition'] = record['condition']
    # Preserve exact scenarios in trusted audit records, not proposal feedback.
    metrics['public'].pop('outcomes', None)
    if record.get('outcomes'):
        feedback = {}
        for side in ('incumbent', 'candidate'):
            societies = [row[f'{side}_society'] for row in record['outcomes']]
            feedback[side] = {
                key: statistics.mean(row['overall'][key] for row in societies)
                for key in ('welfare', 'consumption_per_member_tick', 'shortfall_per_member_tick', 'infrastructure')
            }
            feedback[side]['member_utility_per_tick'] = statistics.mean(row['normalized_mean_individual_utility'] for row in societies)
            feedback[side]['other_welfare'] = statistics.mean(row[f'{side}_others_welfare'] for row in record['outcomes'])
        metrics['public']['outcome_means'] = feedback
    atomic_json(path, metrics)


def evaluate_search(program_path, results_dir, context_path):
    start = time.monotonic()
    results_dir, context_path = Path(results_dir).resolve(), Path(context_path).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    with context_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_json(context_path)
        verify_frozen_sources(state)
        job_id = str(results_dir)
        for prior in state['evaluations']:
            if prior['job_id'] == job_id:
                write_job_result(results_dir, prior)
                return prior
        index = len(state['evaluations'])
        kind, society, member = target_for(state, index)
        institutions, members = state['institutions'].copy(), [row.copy() for row in state['members']]
        source = Path(program_path).read_text()
        predecessor = members[society][member] if kind == 'member' else institutions[society]
        record = {'evaluation': index, 'job_id': job_id, 'kind': kind, 'target_society': society,
                  'target_member': member, 'condition': state['condition'],
                  'program_sha256': digest(source), 'ecological_predecessor_sha256': file_hash(predecessor),
                  'population_before': {'institutions': institutions, 'members': members},
                  'valid': False, 'accepted': False, 'error': None, 'combined_score': -1e6}
        try:
            CandidateProgram(source)
            saved = snapshot_program(program_path, context_path.parent/'programs')
            record.update(program_path=saved, component_hashes=component_hashes(source))
            new_institutions, new_members = institutions.copy(), [row.copy() for row in members]
            if kind == 'member':
                new_members[society][member] = saved
            elif kind == 'institution':
                new_institutions[society] = saved
            old_values, new_values, outcomes = [], [], []
            for case in state['search_cases']:
                before = simulate_consumption(institutions, members, case)
                after = before if kind == 'initial' else simulate_consumption(new_institutions, new_members, case)
                old_values.append(objective(before, kind, society, member))
                new_values.append(objective(after, kind, society, member))
                outcomes.append({'case': case, 'incumbent_society': before['society_metrics'][society],
                                 'candidate_society': after['society_metrics'][society],
                                 'incumbent_others_welfare': statistics.mean(row['overall']['welfare'] for i,row in enumerate(before['society_metrics']) if i != society),
                                 'candidate_others_welfare': statistics.mean(row['overall']['welfare'] for i,row in enumerate(after['society_metrics']) if i != society)})
            old, new = statistics.mean(old_values), statistics.mean(new_values)
            score = 1 + (new-old)/max(1, abs(old))
            if not all(math.isfinite(x) for x in (old, new, score)):
                raise ValueError('Nonfinite objective')
            accepted = kind != 'initial' and new > old + 1e-9
            record.update(valid=True, accepted=accepted, incumbent_objective=old, candidate_objective=new,
                          paired_gain=new-old, combined_score=score,
                          case_objectives={'incumbent':old_values, 'candidate':new_values}, outcomes=outcomes)
            if accepted:
                state['institutions'], state['members'] = new_institutions, new_members
                state[f'accepted_{kind}_updates'] += 1
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
        record['elapsed_seconds'] = time.monotonic()-start
        record['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        state['evaluations'].append(record)
        atomic_json(context_path, state)
        atomic_json(results_dir/'ecology_evaluation.json', record)
        write_job_result(results_dir, record)
        return record
