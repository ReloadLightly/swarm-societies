"""Parent-committed historical search selection with bounded policy execution.

This adapter preserves the old objectives, schedule and 1e-9 acceptance margin.
It is execution hardening, not a new scientific search protocol or allowance.
The parent alone holds the context lock and commits the population. All source
compilation and candidate calls occur in execution_v1 workers with inline code.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import statistics
import tempfile
import time

from . import evaluation as legacy
from . import consumption_evaluation as consumption
from .execution_v1 import (
    ExecutionLimits, bounded_read_bytes, bounded_read_json,
    execute_job, read_source,
)

VERSION = 'bounded-search-selection-v1'
ROOT = Path(__file__).resolve().parents[1]
ENGINES = ('legacy', 'consumption-v2')
CONTEXT_BYTES = 64 * 1024 * 1024
OUTPUT_NAMES = ('ecology_evaluation.json', 'metrics.json', 'correct.json')


class EvaluationFailure(ValueError):
    """A failed bounded job cannot supply a partial selection score."""


def _sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, allow_nan=False, indent=2) + '\n').encode()


def _atomic_replace(path, value):
    path = Path(path)
    data = _json_bytes(value)
    descriptor, temporary = tempfile.mkstemp(prefix='.bounded-selection-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _snapshot_source(source, directory):
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError('Program archive cannot be a symlink')
    target = directory / (_sha_bytes(source.encode()) + '.py')
    descriptor, temporary = tempfile.mkstemp(prefix='.bounded-program-', dir=directory)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(source.encode())
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target, follow_symlinks=False)
        except FileExistsError:
            if read_source(target) != source:
                raise ValueError('Existing program snapshot differs from its source hash')
    finally:
        os.unlink(temporary)
    return str(target)


def _sources(paths, budget=None):
    result = []
    for path in paths:
        source = read_source(path)
        if len(Path(path).stem) == 64 and _sha_bytes(source.encode()) != Path(path).stem:
            raise ValueError('Population source checksum mismatch')
        descriptor = {'source': source, 'name': Path(path).name}
        if budget is not None:
            # Count repeated sources each time: each occurrence crosses JSON IPC.
            budget[0] -= len(json.dumps(descriptor, ensure_ascii=True, separators=(',', ':')).encode()) + 1
            if budget[0] < 0:
                raise ValueError('Population source inventory exceeds request byte limit')
        result.append(descriptor)
    return result


def _population_sources(institutions, members, limit):
    budget = [limit - 4 - 2 * len(members)]
    return _sources(institutions, budget), [_sources(row, budget) for row in members]


def _check_context(state, engine, limits):
    if type(state) is not dict:
        raise ValueError('Search context must be an object')
    config = state if engine == 'consumption-v2' else state.get('config')
    if type(config) is not dict:
        raise ValueError('Missing population configuration')
    for name, low, high in (('n_societies', 2, 64), ('members_per_society', 2, 256)):
        if type(config.get(name)) is not int or not low <= config[name] <= high:
            raise ValueError('Invalid bounded population configuration: ' + name)
    societies, members = config['n_societies'], config['members_per_society']
    for key in ('institutions', 'initial_institutions'):
        if type(state.get(key)) is not list or len(state[key]) != societies:
            raise ValueError('Invalid population inventory: ' + key)
        if any(type(path) is not str for path in state[key]):
            raise ValueError('Population source paths must be strings')
    for key in ('members', 'initial_members'):
        if type(state.get(key)) is not list or len(state[key]) != societies:
            raise ValueError('Invalid population inventory: ' + key)
        if any(type(row) is not list or len(row) != members for row in state[key]):
            raise ValueError('Invalid population member matrix: ' + key)
        if any(type(path) is not str for row in state[key] for path in row):
            raise ValueError('Population source paths must be strings')
    if engine == 'consumption-v2':
        if state.get('version') != 2 or state.get('condition') not in consumption.CONDITIONS:
            raise ValueError('Expected a consumption-v2 search context')
        if set(state.get('frozen_source_hashes', {})) != set(consumption.FROZEN_FILES):
            raise ValueError('Frozen consumption source inventory differs')
        hashes = state['frozen_source_hashes']
        if state['condition'] == 'fixed_institution' and state['institutions'] != state['initial_institutions']:
            raise ValueError('Fixed-institution population changed')
    else:
        if state.get('version') != 1:
            raise ValueError('Expected a legacy search context')
        hashes = {name: state[key] for name, key in (
            ('swarm_societies/ecology.py', 'simulator_sha256'),
            ('swarm_societies/candidate.py', 'candidate_runtime_sha256'),
            ('docs/protocol.md', 'protocol_sha256'))}
    for name, expected in hashes.items():
        if _sha_bytes(bounded_read_bytes(ROOT / name, 1024 * 1024)) != expected:
            raise ValueError('Frozen source changed: ' + name)
    if type(state.get('evaluations')) is not list:
        raise ValueError('Missing evaluation history')
    for key in ('accepted_member_updates', 'accepted_institution_updates'):
        if type(state.get(key)) is not int or state[key] < 0:
            raise ValueError('Invalid accepted-update counter: ' + key)
    # Read and checksum sources in the parent without constructing a program.
    for prefix in ('', 'initial_'):
        _population_sources(state[prefix + 'institutions'], state[prefix + 'members'], limits.request_bytes)


def _target(state, engine, index):
    if engine == 'consumption-v2':
        return consumption.target_for(state, index)
    kind = 'member' if index % 2 else 'institution'
    slot = max(0, index - 1) // 2
    society = slot % state['config']['n_societies']
    member = (slot // state['config']['n_societies']) % state['config']['members_per_society']
    return ('initial' if index == 0 else kind), society, member if kind == 'member' else None


def _outputs(results, record, engine):
    feedback = {key: record[key] for key in
                ('kind', 'target_society', 'target_member', 'valid', 'accepted', 'error')}
    for key in ('incumbent_objective', 'candidate_objective', 'paired_gain', 'outcomes'):
        if key in record:
            feedback[key] = record[key]
    if engine == 'consumption-v2':
        feedback['condition'] = record['condition']
        feedback.pop('outcomes', None)
        if record.get('outcomes'):
            means = {}
            for side in ('incumbent', 'candidate'):
                societies = [row[side + '_society'] for row in record['outcomes']]
                means[side] = {key: statistics.mean(row['overall'][key] for row in societies)
                              for key in ('welfare', 'consumption_per_member_tick',
                                          'shortfall_per_member_tick', 'infrastructure')}
                means[side]['member_utility_per_tick'] = statistics.mean(
                    row['normalized_mean_individual_utility'] for row in societies)
                means[side]['other_welfare'] = statistics.mean(
                    row[side + '_others_welfare'] for row in record['outcomes'])
            feedback['outcome_means'] = means
    _atomic_replace(results / 'ecology_evaluation.json', record)
    _atomic_replace(results / 'metrics.json', {
        'combined_score': record['combined_score'], 'public': feedback,
        'private': {'max_rss_kib': record['max_rss_kib'], 'elapsed_seconds': record['elapsed_seconds']}})
    _atomic_replace(results / 'correct.json', {'correct': record['valid'], 'error': record['error']})


def evaluate_search(program_path, results_dir, context_path, *, engine='consumption-v2', limits=None):
    """Evaluate one scheduled proposal, rejecting every incomplete worker result.

    Repeated completed or failed job IDs are idempotent. A reused ID with changed
    candidate, context or limits is rejected. Parent interruptions before the
    context commit leave the incumbent and scheduled index untouched; retained
    attempt receipts make an interrupted re-evaluation visible.
    """
    if engine not in ENGINES:
        raise ValueError('Unknown search engine')
    limits = (limits or ExecutionLimits()).validate()
    program_path, context_path = Path(program_path).absolute(), Path(context_path).absolute()
    results = Path(results_dir).absolute()
    if context_path.is_symlink() or results.is_symlink():
        raise ValueError('Context/results cannot be symlinks')
    context_path, results = context_path.resolve(), results.resolve()
    results.mkdir(parents=True, exist_ok=True)
    protected = {program_path.resolve(), context_path}
    if any((results / name).resolve() in protected for name in OUTPUT_NAMES):
        raise ValueError('Search output aliases a protected input')
    lock_path = context_path.with_suffix('.lock')
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    started = time.monotonic()
    try:
        if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
            raise ValueError('Context lock must be a regular file')
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        state = bounded_read_json(context_path, CONTEXT_BYTES)
        _check_context(state, engine, limits)
        source, source_error = None, None
        try:
            source = read_source(program_path)
        except (OSError, ValueError, UnicodeError) as exc:
            source_error = f'{type(exc).__name__}: {exc}'[:2048]
        source_hash = _sha_bytes(source.encode()) if source is not None else None
        identity = {'adapter': VERSION, 'engine': engine, 'context': str(context_path),
                    'program_path': str(program_path), 'program_sha256': source_hash,
                    'source_error': source_error, 'limits': asdict(limits)}
        for prior in state['evaluations']:
            if prior['job_id'] == str(results):
                if prior.get('execution_identity') != identity:
                    raise ValueError('Job ID already belongs to different execution inputs')
                for receipt in prior['execution_receipts']:
                    path = results / receipt['path']
                    if (path.resolve().parent.parent != (results / 'execution').resolve()
                            or _sha_bytes(bounded_read_bytes(path, 160 * 1024 * 1024)) != receipt['sha256']):
                        raise ValueError('Cached execution receipt changed')
                _outputs(results, prior, engine)
                return prior
        index = len(state['evaluations'])
        kind, society, member = _target(state, engine, index)
        institutions, members = state['institutions'].copy(), deepcopy(state['members'])
        predecessor = members[society][member] if kind == 'member' else institutions[society]
        record = {'job_id': str(results), 'evaluation': index, 'kind': kind,
                  'target_society': society, 'target_member': member,
                  'program_sha256': source_hash, 'program_path': None,
                  'ecological_predecessor_sha256': _sha_bytes(read_source(predecessor).encode()),
                  'accepted': False, 'valid': False, 'error': None, 'combined_score': -1e6,
                  'population_before': {'institutions': institutions, 'members': members},
                  'execution_identity': identity, 'execution_receipts': [],
                  'selection_rule': 'Historical new > old + 1e-9; no new model-search allowance',
                  'execution_sources': {name: _sha_bytes(bounded_read_bytes(ROOT / name, 1024 * 1024))
                       for name in ('swarm_societies/search_execution_v1.py',
                                    'swarm_societies/execution_v1.py',
                                    'swarm_societies/execution_worker_v1.py')}}
        if engine == 'consumption-v2':
            record['condition'] = state['condition']
        else:
            record['search_seeds'] = state['search_seeds']
        archive = results / 'execution'
        archive.mkdir(exist_ok=True)
        if archive.is_symlink():
            raise ValueError('Execution receipt archive cannot be a symlink')
        attempt = Path(tempfile.mkdtemp(prefix='attempt-', dir=archive))
        worker_peaks = []

        def run(job, stage):
            path = attempt / f'{len(record["execution_receipts"]):03d}-{stage}.json'
            receipt = execute_job(job, limits=limits, receipt_path=path)
            peak = receipt.get('worker', {}).get('max_rss_kib')
            if type(peak) is int and peak >= 0:
                worker_peaks.append(peak)
            record['execution_receipts'].append({
                'stage': stage, 'path': str(path.relative_to(results)),
                'sha256': _sha_bytes(bounded_read_bytes(path, 160 * 1024 * 1024)),
                'job_sha256': receipt['job_sha256'], 'status': receipt['status']})
            if receipt['status'] != 'ok':
                detail = receipt.get('error', {})
                raise EvaluationFailure(f'{stage}: {detail.get("kind")}: {detail.get("message")}')
            return receipt['result']

        try:
            if source_error:
                raise EvaluationFailure('source_read: ' + source_error)
            validation = run({'kind': 'candidate_validate', 'source': source}, 'validation')
            if validation['source_sha256'] != source_hash:
                raise EvaluationFailure('Worker source identity differs')
            record['component_hashes'] = validation['component_hashes']
            saved = _snapshot_source(source, context_path.parent / 'programs')
            record['program_path'] = saved
            new_institutions, new_members = institutions.copy(), deepcopy(members)
            if kind == 'member':
                new_members[society][member] = saved
            elif kind == 'institution':
                new_institutions[society] = saved
            old_programs, old_members = _population_sources(institutions, members, limits.request_bytes)
            new_programs, new_member_sources = _population_sources(new_institutions, new_members, limits.request_bytes)
            cases = state['search_cases'] if engine == 'consumption-v2' else state['search_seeds']
            old_values, new_values, outcomes = [], [], []
            for case_index, case in enumerate(cases):
                common = ({'kind': 'consumption_case', 'case': case} if engine == 'consumption-v2'
                          else {'kind': 'legacy_episode', 'config': state['config'], 'seed': case})
                before = run({**common, 'programs': old_programs, 'member_programs': old_members},
                             f'incumbent-{case_index}')
                after = before if kind == 'initial' else run(
                    {**common, 'programs': new_programs, 'member_programs': new_member_sources},
                    f'candidate-{case_index}')
                objective = consumption.objective if engine == 'consumption-v2' else legacy.objective
                objective_kind = 'institution' if kind == 'initial' else kind
                old_values.append(objective(before, objective_kind, society, member))
                new_values.append(objective(after, objective_kind, society, member))
                row = {'case' if engine == 'consumption-v2' else 'seed': case,
                       'incumbent_society': before['society_metrics'][society],
                       'candidate_society': after['society_metrics'][society]}
                if engine == 'consumption-v2':
                    for side, episode in (('incumbent', before), ('candidate', after)):
                        row[side + '_others_welfare'] = statistics.mean(
                            item['overall']['welfare'] for i, item in enumerate(episode['society_metrics'])
                            if i != society)
                outcomes.append(row)
            old, new = ((statistics.mean(old_values), statistics.mean(new_values)) if engine == 'consumption-v2'
                        else (sum(old_values) / len(old_values), sum(new_values) / len(new_values)))
            score = 1 + (new - old) / max(1, abs(old))
            if not all(math.isfinite(value) for value in (old, new, score)):
                raise EvaluationFailure('Nonfinite paired objectives')
            accepted = kind != 'initial' and new > old + 1e-9
            record.update(valid=True, accepted=accepted, incumbent_objective=old, candidate_objective=new,
                          paired_gain=new - old, combined_score=score,
                          case_objectives={'incumbent': old_values, 'candidate': new_values}, outcomes=outcomes)
        except Exception as exc:
            record.update(valid=False, accepted=False, combined_score=-1e6,
                          error=f'{type(exc).__name__}: {exc}'[:4096])
        record['elapsed_seconds'] = time.monotonic() - started
        # Largest reported child peak, not parent usage. Terminated workers may
        # not report; counts make partial coverage explicit on failed proposals.
        record['max_rss_kib'] = max(worker_peaks, default=None)
        record['worker_rss_reports'] = len(worker_peaks)
        if record['valid'] and record['accepted']:
            state['institutions'], state['members'] = new_institutions, new_members
            state[f'accepted_{kind}_updates'] += 1
        state['evaluations'].append(record)
        # Publish recoverable outputs first. The context is the commit point;
        # a retry after that commit regenerates outputs without executing code.
        _outputs(results, record, engine)
        _atomic_replace(context_path, state)
        return record
    finally:
        os.close(lock_fd)
