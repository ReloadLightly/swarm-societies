"""Trusted ecological selection and frozen common-case evaluation.

Candidates receive observations only. This module is outside the evolve block.
"""
from __future__ import annotations
import ast
import fcntl
import hashlib
import json
import math
from pathlib import Path
import resource
import time

ROOT = Path(__file__).resolve().parents[1]
SEARCH_SEEDS = [101, 202, 303]


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def component_hashes(source):
    tree = ast.parse(source)
    result = {}
    for name in ['member_policy', 'institution']:
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        result[name] = digest(ast.dump(nodes[0], include_attributes=False)) if nodes else None
    # Helpers/constants are included in full-source hashes and may affect either component.
    return result


def snapshot_program(path, directory):
    source = Path(path).read_text()
    sha = digest(source)
    target = Path(directory) / f'{sha}.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(source)
    return str(target.resolve())


def initialize_context(path, societies=3, members=4, steps=60):
    path = Path(path).resolve()
    if path.exists():
        return read_json(path)
    names = ['initial', 'cooperative', 'selfish']
    programs = [snapshot_program(ROOT / 'seeds' / f'{names[i % 3]}.py', path.parent / 'programs')
                for i in range(societies)]
    state = {'version': 1, 'config': {'n_societies': societies, 'members_per_society': members,
                                   'ticks': steps, 'disturbance_tick': steps // 2},
             'search_seeds': SEARCH_SEEDS, 'institutions': programs,
             'members': [[p] * members for p in programs],
             'initial_institutions': programs.copy(),
             'initial_members': [[p] * members for p in programs],
             'evaluations': [], 'accepted_member_updates': 0, 'accepted_institution_updates': 0,
             'protocol_sha256': digest((ROOT / 'docs/protocol.md').read_text()),
             'simulator_sha256': digest((ROOT / 'swarm_societies/ecology.py').read_text()),
             'candidate_runtime_sha256': digest((ROOT / 'swarm_societies/candidate.py').read_text())}
    atomic_json(path, state)
    return state


def simulate(institutions, members, config, seed, replay=False):
    from .ecology import EcologyConfig, run_episode
    return run_episode(institutions, EcologyConfig(**config), seed=seed, replay=replay,
                       member_programs=members)


def society_metric(episode, society, phase='overall'):
    return episode['society_metrics'][society][phase]


def member_utility(episode, society, member):
    metrics = episode['member_metrics']
    # The simulator reports one row per member with explicit membership.
    rows = [r for r in metrics if r['society_id'] == society and r['member_id'] == member]
    return float(rows[0]['utility'])


def objective(episode, kind, society, member):
    if kind == 'member':
        return member_utility(episode, society, member)
    return float(society_metric(episode, society)['welfare'])


def evaluate_search(program_path, results_dir, context_path):
    """Serialized, idempotent ecological update invoked by upstream Shinka jobs."""
    started = time.monotonic()
    results_dir = Path(results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    context_path = Path(context_path).resolve()
    lock = context_path.with_suffix('.lock')
    with lock.open('a') as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        state = read_json(context_path)
        job_id = str(results_dir)
        for previous in state['evaluations']:
            if previous['job_id'] == job_id:
                write_job_result(results_dir, previous)
                return previous
        index = len(state['evaluations'])
        is_initial = index == 0
        kind = 'member' if index % 2 == 1 else 'institution'
        slot = max(0, index - 1) // 2
        society = slot % state['config']['n_societies']
        member = (slot // state['config']['n_societies']) % state['config']['members_per_society']
        institutions = state['institutions'].copy()
        members = [row.copy() for row in state['members']]
        incumbent_path = members[society][member] if kind == 'member' else institutions[society]
        source = Path(program_path).read_text()
        record = {'job_id': job_id, 'evaluation': index, 'kind': 'initial' if is_initial else kind,
                  'target_society': society, 'target_member': member if kind == 'member' else None,
                  'program_sha256': digest(source), 'ecological_predecessor_sha256': digest(Path(incumbent_path).read_text()),
                  'accepted': False, 'valid': False, 'error': None,
                  'population_before': {'institutions': institutions, 'members': members},
                  'search_seeds': state['search_seeds'], 'combined_score': -1e6}
        try:
            from .candidate import CandidateProgram
            CandidateProgram(source)
            record['component_hashes'] = component_hashes(source)
            saved = snapshot_program(program_path, context_path.parent / 'programs')
            record['program_path'] = saved
            challenger_institutions = institutions.copy()
            challenger_members = [row.copy() for row in members]
            if not is_initial:
                if kind == 'member':
                    challenger_members[society][member] = saved
                else:
                    challenger_institutions[society] = saved
            incumbent_values, candidate_values, outcomes = [], [], []
            for seed in state['search_seeds']:
                before = simulate(institutions, members, state['config'], seed)
                after = before if is_initial else simulate(challenger_institutions, challenger_members, state['config'], seed)
                incumbent_values.append(objective(before, kind, society, member))
                candidate_values.append(objective(after, kind, society, member))
                outcomes.append({'seed': seed, 'incumbent_society': before['society_metrics'][society],
                                 'candidate_society': after['society_metrics'][society]})
            old = sum(incumbent_values) / len(incumbent_values)
            new = sum(candidate_values) / len(candidate_values)
            score = 1 + (new - old) / max(1, abs(old))
            if not all(math.isfinite(v) for v in [old, new, score]):
                raise ValueError('nonfinite measured score')
            accepted = not is_initial and new > old + 1e-9
            record.update(valid=True, incumbent_objective=old, candidate_objective=new,
                          paired_gain=new-old, combined_score=score, accepted=accepted,
                          case_objectives={'incumbent':incumbent_values,'candidate':candidate_values}, outcomes=outcomes)
            if accepted:
                state['institutions'], state['members'] = challenger_institutions, challenger_members
                state[f'accepted_{kind}_updates'] += 1
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
        record['elapsed_seconds'] = time.monotonic() - started
        record['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        state['evaluations'].append(record)
        atomic_json(context_path, state)
        atomic_json(results_dir / 'ecology_evaluation.json', record)
        write_job_result(results_dir, record)
        return record


def write_job_result(results_dir, record):
    feedback = {k: record[k] for k in ['kind','target_society','target_member','valid','accepted','error']}
    for key in ['incumbent_objective','candidate_objective','paired_gain','outcomes']:
        if key in record:
            feedback[key] = record[key]
    atomic_json(Path(results_dir) / 'metrics.json', {'combined_score': record['combined_score'],
                'public': feedback, 'private': {'max_rss_kib': record['max_rss_kib'],
                                               'elapsed_seconds': record['elapsed_seconds']}})
    atomic_json(Path(results_dir) / 'correct.json', {'correct': record['valid'], 'error': record['error']})
