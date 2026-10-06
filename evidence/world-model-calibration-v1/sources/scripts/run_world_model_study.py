#!/usr/bin/env python3
"""Freeze and run a stationary, instrumented renewal-law identification control.

No evolutionary inference or model-guided action selection occurs. Evaluation
truth and probes remain outside learner packets; all predictions use saved
learner state and independent RNG. The arena is the replication unit.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

from swarm_societies.ecology_world_model_v1 import EcologyConfig, WorldParameters, run_episode
from swarm_societies.world_model_v1.learner import RenewalSMC

VERSION = 'world-model-v1'
PRIOR = {'r': [2., 8.], 'b': [.5, 3.], 'g': [0., .8]}
SENSOR_SIGMA = .05
SOURCES = (
    'scripts/run_world_model_study.py', 'swarm_societies/ecology_world_model_v1.py',
    'swarm_societies/world_model_v1/learner.py', 'swarm_societies/world_model_v1/__init__.py',
    'swarm_societies/candidate.py', 'swarm_societies/ecology_consumption_v2.py',
    'pyproject.toml',
)
POLICY = '''def institution(obs, state):
    role = (obs['society_id'] + ROLE_ROTATION) % 3
    phase = (obs['tick'] // 8 + role * 3) % 9
    public = 0.0 if phase < 3 else (0.3 if phase < 6 else 0.8)
    return {'tax_rate': 0.6, 'public_fraction': public,
            'defense_fraction': 0.0, 'reserve_fraction': 0.0,
            'raid_permission': False, 'state': {}}

def member_policy(obs, state):
    home = obs['society_id']
    target = home
    if (obs['tick'] + obs['member_id']) % 5 == 0:
        for patch in obs['patches']:
            if patch['id'] != home:
                target = patch['id']
    return {'action': 'harvest', 'target': target, 'effort': 1.0, 'state': {}}
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def stable_seed(*parts):
    return int.from_bytes(hashlib.sha256('/'.join(map(str, parts)).encode()).digest()[:8], 'big')


def prepare(directory, arenas=24, ticks=128, particles=1024, development=False):
    directory = Path(directory)
    if (directory/'design.json').exists():
        raise ValueError('Design exists; use run or a new directory, never overwrite it')
    if arenas < 1 or ticks < 8 or particles < 64:
        raise ValueError('Need at least one arena, eight ticks and 64 particles')
    directory.mkdir(parents=True, exist_ok=True)
    bank = 'development' if development else 'evaluation'
    config = asdict(EcologyConfig(n_societies=3, members_per_society=4, ticks=ticks,
                    disturbance_tick=ticks//2, initial_patch=10., patch_capacity=30.,
                    regeneration=5., enable_disturbance=False))
    cases = []
    for i in range(arenas):
        rng = np.random.default_rng(stable_seed(VERSION, bank, 'laws', i))
        laws = {'r': float(rng.uniform(2.4, 6.8)), 'b': float(rng.uniform(.7, 2.7)),
                'g': float(rng.uniform(.05, .7))}
        cases.append({'arena_id': f'{bank}-{i:03d}', 'index': i,
                      'environment_seed': stable_seed(VERSION, bank, 'ecology', i),
                      'role_rotation': i % 3, 'world_parameters': laws})
    for name in SOURCES:
        target = directory/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    programs = []
    for rotation in range(3):
        rel = f'programs/rotation-{rotation}.py'
        (directory/'programs').mkdir(exist_ok=True)
        (directory/rel).write_text(f'ROLE_ROTATION = {rotation}\n\n' + POLICY)
        programs.append(rel)
    design = {
        'schema_version': 1, 'study': VERSION, 'bank': bank,
        'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Stationary parameter identification, full infrastructure audit sensors, fixed policies; no structural discovery or active control',
        'replication_unit': 'Independent hidden-law/environment arena; societies and repeated probes are dependent',
        'config': config, 'prior': PRIOR, 'sensor_sigma': SENSOR_SIGMA,
        'measurement_model': 'Observed growth = min(capacity gap, r*Uniform(.85,1.15)+b*own infrastructure+g*mean other infrastructure) + Normal(0,.05)',
        'observation_mode': 'full_observation_control',
        'conditions': ['prior', 'private', 'pooled'],
        'information_control': 'Private receives own patch events with licensed full infrastructure features; pooled receives union across all three societies without a bandwidth cap; prior never updates',
        'sensor_cost': 'Free audit instrumentation in this identification control; no efficiency or governance claim',
        'n_particles': particles, 'rejuvenation_steps': 4, 'ess_fraction': .5,
        'forecast_samples': 512, 'n_probes': 64,
        'checkpoints': sorted({0, *[t for t in (4, 8, 16, 32, 64, 128, 256) if t <= ticks], ticks}),
        'primary_endpoint': 'CRPS on 32 guaranteed-uncapped common probes, integrated over world ticks and divided by horizon; lower is better',
        'secondary_endpoints': ['terminal CRPS', '90% predictive coverage and width', 'parameter normalized RMSE and interval coverage', 'unique evidence and learning CPU'],
        'probe_design': '64 common, independent one-step queries per arena; own and other infrastructure independently uniform [0,2]; 32 have headroom30 (guaranteed uncapped across prior support), remaining32 cycle headroom0,2,6; same hidden law draw, independent weather and sensor noise; fixed at every checkpoint. Primary metrics use guaranteed-uncapped probes, all-probe CRPS also retained.',
        'intervals': '2000 percentile bootstrap draws of independent arena means; paired contrasts resample whole arenas',
        'bootstrap_seed': 7301,
        'inference_calls': 0, 'cases': cases, 'programs': programs,
        'program_hashes': {p: sha(directory/p) for p in programs},
        'source_hashes': {p: sha(ROOT/p) for p in SOURCES},
        'software': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
    }
    json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(sha(directory/'design.json') + '\n')
    return design


def verify_design(directory, check_live=True):
    directory = Path(directory)
    if sha(directory/'design.json') != (directory/'design.sha256').read_text().strip():
        raise ValueError('Frozen design checksum mismatch')
    design = json.loads((directory/'design.json').read_text())
    for rel, expected in design['source_hashes'].items():
        if sha(directory/'sources'/rel) != expected:
            raise ValueError(f'Archived source mismatch: {rel}')
        if check_live and sha(ROOT/rel) != expected:
            raise ValueError(f'Live source changed after design freeze: {rel}')
    for rel, expected in design['program_hashes'].items():
        if sha(directory/rel) != expected:
            raise ValueError(f'Policy hash mismatch: {rel}')
    return design


def query_from(packet):
    """Allowlist: excludes growth, censoring, stock_after, regime, truth and RNG."""
    return {k: float(packet[k]) for k in ('stock_before', 'capacity', 'own_infrastructure', 'other_infrastructure')}


def score_samples(samples, target):
    values = np.sort(np.asarray(samples, dtype=float))
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError('Invalid forecast')
    n = len(values)
    crps = np.mean(np.abs(values-target)) - np.dot(2*np.arange(1, n+1)-n-1, values)/(n*n)
    low, high = np.quantile(values, [.05, .95])
    return {'crps': float(crps), 'mean': float(values.mean()), 'lo90': float(low),
            'hi90': float(high), 'covered': int(low <= target <= high),
            'width': float(high-low), 'squared_error': float((values.mean()-target)**2)}


def make_probes(case, design):
    rng = np.random.default_rng(stable_seed(VERSION, case['arena_id'], 'probes'))
    law = case['world_parameters']
    probes = []
    for p in range(design['n_probes']):
        gap = 30. if p % 2 == 0 else float((0, 2, 6)[(p//2) % 3])
        query = {'stock_before': 30.-gap, 'capacity': 30.,
                 'own_infrastructure': float(rng.uniform(0, 2)),
                 'other_infrastructure': float(rng.uniform(0, 2))}
        flow = law['r']*rng.uniform(.85, 1.15)+law['b']*query['own_infrastructure']+law['g']*query['other_infrastructure']
        truth = min(gap, flow)
        target = truth+rng.normal(0, design['sensor_sigma'])
        probes.append({'probe_id': p, 'probe_group': 'uncapped' if gap == 30 else 'capacity_control',
                       **query, 'true_growth': float(truth), 'target': float(target)})
    return probes


def csv_write(path, rows):
    if not rows:
        raise ValueError(f'Cannot write empty table: {path}')
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    raw = buffer.getvalue().encode()
    if str(path).endswith('.gz'):
        raw = gzip.compress(raw, mtime=0)
    Path(path).write_bytes(raw)


def csv_read(path):
    path = Path(path)
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return list(csv.DictReader(io.StringIO(raw.decode())))


def bootstrap(values, seed=7301):
    x = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(2000, len(x)))].mean(axis=1)
    lo, hi = np.quantile(means, [.025, .975])
    return {'mean': float(x.mean()), 'ci95': [float(lo), float(hi)], 'arenas': len(x)}


def summarize(checkpoints, design):
    arena_ids = [case['arena_id'] for case in design['cases']]
    if len(set(arena_ids)) != len(arena_ids):
        raise ValueError('Duplicated arena in design')
    expected_cells = {(arena, condition, society, tick)
                      for arena in arena_ids for condition in design['conditions']
                      for society in range(3) for tick in design['checkpoints']}
    actual_cells = []
    for row in checkpoints:
        actual_cells.append((row['arena_id'], row['condition'], int(row['society']), int(row['tick'])))
        for key in ('probe_crps', 'probe_mse', 'coverage_90', 'interval_width_90',
                    'parameter_nrmse', 'unique_observations', 'updates_failed'):
            if not np.isfinite(float(row[key])):
                raise ValueError(f'Nonfinite checkpoint value: {key}')
    if len(actual_cells) != len(set(actual_cells)) or set(actual_cells) != expected_cells:
        raise ValueError('Missing, foreign or duplicated society checkpoint')
    arena_metrics = []
    for case in design['cases']:
        arena = case['arena_id']
        for condition in design['conditions']:
            cells = [r for r in checkpoints if r['arena_id'] == arena and r['condition'] == condition]
            by_tick = {t: [r for r in cells if int(r['tick']) == t] for t in design['checkpoints']}
            if any(len(rows) != 3 for rows in by_tick.values()):
                raise ValueError('Missing or duplicated society checkpoint')
            curve = np.asarray([np.mean([float(r['probe_crps']) for r in by_tick[t]]) for t in design['checkpoints']])
            last = by_tick[design['config']['ticks']]
            arena_metrics.append({'arena_id': arena, 'condition': condition,
                'crps_aulc_ticks': float(np.sum((curve[1:]+curve[:-1])*np.diff(design['checkpoints'])/2)/design['config']['ticks']),
                **{key: float(np.mean([float(r[key]) for r in last])) for key in
                   ('probe_crps', 'probe_mse', 'coverage_90', 'interval_width_90', 'parameter_nrmse', 'unique_observations', 'updates_failed')}})
    keys = ('crps_aulc_ticks', 'probe_crps', 'probe_mse', 'coverage_90', 'interval_width_90', 'parameter_nrmse', 'unique_observations', 'updates_failed')
    conditions = {c: {key: bootstrap([r[key] for r in arena_metrics if r['condition'] == c]) for key in keys} for c in design['conditions']}
    contrasts = {}
    for lhs, rhs in (('private', 'prior'), ('pooled', 'private')):
        contrasts[f'{lhs}_minus_{rhs}'] = {}
        for key in keys:
            a = {r['arena_id']: r[key] for r in arena_metrics if r['condition'] == lhs}
            b = {r['arena_id']: r[key] for r in arena_metrics if r['condition'] == rhs}
            contrasts[f'{lhs}_minus_{rhs}'][key] = bootstrap([a[c['arena_id']]-b[c['arena_id']] for c in design['cases']])
    return {'schema_version': 1, 'study': VERSION, 'scope': design['scope'],
            'n_arenas': len(design['cases']), 'societies_per_arena': 3,
            'ticks': design['config']['ticks'], 'replication_unit': design['replication_unit'],
            'primary_endpoint': design['primary_endpoint'], 'conditions': conditions,
            'paired_contrasts': contrasts, 'arena_metrics': arena_metrics,
            'notes': ['Prior and pooled rows are identical references repeated across society IDs, never independent replications.',
                      'Pooled receives three times as many unique observations per tick; difference is an information advantage, not algorithmic superiority.',
                      'This is a full-feature, stationary identification control with free sensors and fixed policies.',
                      'No structural discovery, learned control, evolved learning institution or new evolutionary inference.']}


def run(directory):
    directory = Path(directory)
    design = verify_design(directory)
    if (directory/'completion.json').exists():
        raise ValueError('Completed study exists; verify it or use a new design directory')
    checkpoints, parameters, predictions, episodes, observations, probe_rows, prequential = [], [], [], [], [], [], []
    started = time.perf_counter()
    (directory/'snapshots').mkdir(exist_ok=True)
    for case in design['cases']:
        arena = case['arena_id']
        program = directory/design['programs'][case['role_rotation']]
        world = run_episode([program]*3, config=design['config'], seed=case['environment_seed'],
                            world_parameters=WorldParameters(**case['world_parameters']),
                            observation_mode=design['observation_mode'])
        episodes.append({'arena_id': arena, 'role_rotation': case['role_rotation'],
                         **case['world_parameters'], **world['aggregate'],
                         'ledger_residual': world['ledger']['residual'],
                         'material_digest': world['legacy_digest']})
        probes = make_probes(case, design)
        probe_rows.extend({'arena_id': arena, **p} for p in probes)
        learner_seed = stable_seed(VERSION, arena, 'learner')
        learner_kwargs = dict(seed=learner_seed, n_particles=design['n_particles'], prior=design['prior'],
                              sensor_sigma=design['sensor_sigma'], rejuvenation_steps=design['rejuvenation_steps'],
                              ess_fraction=design['ess_fraction'])
        models = {'prior': RenewalSMC(**learner_kwargs), 'pooled': RenewalSMC(**learner_kwargs)}
        models.update({f'private-{s}': RenewalSMC(**learner_kwargs) for s in range(3)})
        cpu = {key: 0. for key in models}
        counts = {key: 0 for key in models}
        failures = {key: 0 for key in models}
        packets = {}
        noise = np.random.default_rng(stable_seed(VERSION, arena, 'sensor'))
        for raw in world['learning_observations']:
            packet = {**query_from(raw), 'event_id': f'{arena}/{raw["event_id"]}',
                      'tick': raw['tick'], 'patch': raw['patch'],
                      'growth': float(raw['growth']+noise.normal(0, design['sensor_sigma'])),
                      'sensor_sigma': design['sensor_sigma']}
            packets.setdefault(raw['tick'], []).append((raw['society_id'], packet))
            observations.append({'arena_id': arena, 'society': raw['society_id'],
                                 **packet, 'true_growth': raw['growth']})

        def checkpoint(tick):
            for key, model in models.items():
                condition = 'private' if key.startswith('private-') else key
                sids = [int(key.split('-')[1])] if condition == 'private' else range(3)
                before = json.dumps(model.snapshot(), sort_keys=True, allow_nan=False)
                info = model.summary()
                scores = []
                for probe in probes:
                    samples = model.predict(query_from(probe), n_samples=design['forecast_samples'],
                        seed=stable_seed(VERSION, arena, probe['probe_id'], 'forecast'))
                    scores.append(score_samples(samples, probe['target']))
                if before != json.dumps(model.snapshot(), sort_keys=True, allow_nan=False):
                    raise AssertionError('Evaluation mutated live learner state')
                primary_scores = [score for probe, score in zip(probes, scores) if probe['probe_group'] == 'uncapped']
                # Parameter summary schema is normalized here at the public interface.
                means = info['mean']
                covariance = np.asarray(info['covariance'])
                intervals = info['intervals_90']
                nrmse = float(np.sqrt(np.mean([((means[p]-case['world_parameters'][p])/(design['prior'][p][1]-design['prior'][p][0]))**2 for p in PRIOR])))
                for sid in sids:
                    base = {'arena_id': arena, 'society': sid, 'condition': condition, 'tick': tick}
                    checkpoints.append({**base, 'unique_observations': counts[key],
                        'probe_mse': float(np.mean([s['squared_error'] for s in primary_scores])),
                        'probe_crps': float(np.mean([s['crps'] for s in primary_scores])),
                        'probe_crps_all': float(np.mean([s['crps'] for s in scores])),
                        'coverage_90': float(np.mean([s['covered'] for s in primary_scores])),
                        'interval_width_90': float(np.mean([s['width'] for s in primary_scores])),
                        'parameter_nrmse': nrmse, 'ess': info['effective_sample_size'],
                        'updates_failed': failures[key], 'learning_cpu_seconds': cpu[key]})
                    for j, p in enumerate(PRIOR):
                        parameters.append({**base, 'parameter': p, 'true_value': case['world_parameters'][p],
                            'posterior_mean': means[p], 'posterior_sd': float(np.sqrt(max(0., covariance[j,j]))),
                            'lo90': intervals[p][0], 'hi90': intervals[p][1]})
                    predictions.extend({**base, 'probe_id': probe['probe_id'], 'probe_group': probe['probe_group'], 'target': probe['target'],
                                        **score} for probe, score in zip(probes, scores))
                if tick == design['config']['ticks']:
                    json_write(directory/'snapshots'/f'{arena}-{key}.json', model.snapshot())

        checkpoint(0)
        for tick in range(design['config']['ticks']):
            # Commit all same-tick forecasts before any of this tick's outcomes update models.
            for sid, packet in packets[tick]:
                for key in ('prior', f'private-{sid}', 'pooled'):
                    samples = models[key].predict(query_from(packet), n_samples=design['forecast_samples'],
                        seed=stable_seed(VERSION, arena, tick, sid, 'prequential'))
                    score = score_samples(samples, packet['growth'])
                    prequential.append({'arena_id': arena, 'society': sid, 'condition': key.split('-')[0],
                                        'tick': tick+1, 'event_id': packet['event_id'], **score})
            for sid, packet in packets[tick]:
                for key in (f'private-{sid}', 'pooled'):
                    start = time.process_time()
                    result = models[key].update(packet)
                    cpu[key] += time.process_time()-start
                    counts[key] += 1
                    if result.get('status') in ('failed', 'collapse', 'invalid'):
                        failures[key] += 1
            if tick+1 in design['checkpoints']:
                checkpoint(tick+1)
        print(json.dumps({'arena_completed': arena, 'elapsed_seconds': round(time.perf_counter()-started, 2),
                          'failed_updates': sum(failures.values())}), flush=True)
    for name, rows in (('checkpoints.csv', checkpoints), ('parameters.csv', parameters),
                       ('predictions.csv.gz', predictions), ('episodes.csv', episodes),
                       ('observations.csv.gz', observations), ('probes.csv', probe_rows),
                       ('prequential.csv.gz', prequential)):
        csv_write(directory/name, rows)
    summary = summarize(checkpoints, design)
    json_write(directory/'summary.json', summary)
    artifacts = sorted(p for p in directory.rglob('*') if p.is_file() and p.name != 'completion.json')
    json_write(directory/'completion.json', {
        'study': VERSION, 'completed_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': time.perf_counter()-started,
        'inference_calls': 0, 'artifacts': {str(p.relative_to(directory)): sha(p) for p in artifacts},
        'rows': {'checkpoints': len(checkpoints), 'parameters': len(parameters), 'predictions': len(predictions),
                 'episodes': len(episodes), 'observations': len(observations), 'prequential': len(prequential)}})
    return summary


def verify(directory):
    directory = Path(directory)
    design = verify_design(directory, check_live=False)
    completed = json.loads((directory/'completion.json').read_text())
    tables = {'checkpoints': 'checkpoints.csv', 'parameters': 'parameters.csv',
              'predictions': 'predictions.csv.gz', 'episodes': 'episodes.csv',
              'observations': 'observations.csv.gz', 'prequential': 'prequential.csv.gz',
              'probes': 'probes.csv'}
    required = {'design.json', 'design.sha256', 'summary.json', *tables.values()}
    required.update('sources/'+name for name in design['source_hashes'])
    required.update(design['programs'])
    model_keys = ('prior', 'pooled', 'private-0', 'private-1', 'private-2')
    required.update(f'snapshots/{case["arena_id"]}-{key}.json'
                    for case in design['cases'] for key in model_keys)
    if not required <= set(completed['artifacts']):
        raise ValueError('Completion manifest omits required evidence')
    for rel, expected in completed['artifacts'].items():
        if sha(directory/rel) != expected:
            raise ValueError(f'Output hash mismatch: {rel}')
    recorded = {name: csv_read(directory/path) for name, path in tables.items()}
    for name, count in completed['rows'].items():
        if name not in recorded or len(recorded[name]) != count:
            raise ValueError(f'Completion row count mismatch: {name}')
    rows = recorded['checkpoints']
    rebuilt = summarize(rows, design)
    if rebuilt != json.loads((directory/'summary.json').read_text()):
        raise ValueError('Summary differs from recorded checkpoint arithmetic')

    def close(actual, expected, label):
        if not np.isfinite(float(actual)) or not np.isclose(float(actual), float(expected), rtol=1e-10, atol=1e-12):
            raise ValueError(f'Recorded arithmetic mismatch: {label}')

    def index(name, key, expected):
        indexed = {}
        for row in recorded[name]:
            identity = key(row)
            if identity in indexed:
                raise ValueError(f'Duplicated {name} row: {identity}')
            indexed[identity] = row
        if set(indexed) != set(expected):
            raise ValueError(f'Missing or foreign {name} coverage')
        return indexed

    arenas = [case['arena_id'] for case in design['cases']]
    horizon = design['config']['ticks']
    checkpoint_key = lambda row: (row['arena_id'], row['condition'], int(row['society']), int(row['tick']))
    checkpoint_cells = {(arena, condition, sid, tick) for arena in arenas
                        for condition in design['conditions'] for sid in range(3)
                        for tick in design['checkpoints']}
    checkpoint_rows = index('checkpoints', checkpoint_key, checkpoint_cells)
    probe_cells = {(arena, p) for arena in arenas for p in range(design['n_probes'])}
    probes = index('probes', lambda row: (row['arena_id'], int(row['probe_id'])), probe_cells)
    predictions = index('predictions', lambda row: (*checkpoint_key(row), int(row['probe_id'])),
                        {(*cell, p) for cell in checkpoint_cells for p in range(design['n_probes'])})
    parameters = index('parameters', lambda row: (*checkpoint_key(row), row['parameter']),
                       {(*cell, p) for cell in checkpoint_cells for p in PRIOR})
    observations = index('observations', lambda row: (row['arena_id'], int(row['tick']), int(row['patch'])),
                         {(arena, t, sid) for arena in arenas for t in range(horizon) for sid in range(3)})
    prequential = index('prequential', checkpoint_key,
                        {(arena, condition, sid, tick) for arena in arenas for condition in design['conditions']
                         for sid in range(3) for tick in range(1, horizon+1)})
    episodes = index('episodes', lambda row: row['arena_id'], arenas)

    def score_arithmetic(row, target, label):
        low, high = float(row['lo90']), float(row['hi90'])
        if low > high or float(row['crps']) < -1e-12:
            raise ValueError(f'Invalid predictive interval or CRPS: {label}')
        for key in ('crps', 'mean', 'lo90', 'hi90'):
            if not np.isfinite(float(row[key])):
                raise ValueError(f'Nonfinite prediction: {label}')
        close(row['covered'], int(low <= target <= high), label+' coverage')
        close(row['width'], high-low, label+' width')
        close(row['squared_error'], (float(row['mean'])-target)**2, label+' squared error')

    for case in design['cases']:
        arena = case['arena_id']
        if not np.isfinite(float(episodes[arena]['ledger_residual'])) or abs(float(episodes[arena]['ledger_residual'])) > 1e-7:
            raise ValueError('Material ledger residual exceeds tolerance')
        for p in PRIOR:
            close(episodes[arena][p], case['world_parameters'][p], 'episode law '+p)
        close(episodes[arena]['role_rotation'], case['role_rotation'], 'episode policy rotation')
        for expected_probe in make_probes(case, design):
            saved = probes[arena, expected_probe['probe_id']]
            for field, value in expected_probe.items():
                if field == 'probe_group':
                    if saved[field] != value:
                        raise ValueError('Probe group differs from frozen design')
                else:
                    close(saved[field], value, 'frozen probe '+field)
        sensor_rng = np.random.default_rng(stable_seed(VERSION, arena, 'sensor'))
        for tick in range(horizon):
            for sid in range(3):
                observation = observations[arena, tick, sid]
                if int(observation['society']) != sid or observation['event_id'] != f'{arena}/growth:{tick}:{sid}':
                    raise ValueError('Observation identity/ownership mismatch')
                close(observation['sensor_sigma'], design['sensor_sigma'], 'sensor noise model')
                close(observation['growth'], float(observation['true_growth']) + sensor_rng.normal(0, design['sensor_sigma']), 'recorded sensor draw')
                for condition in design['conditions']:
                    row = prequential[arena, condition, sid, tick+1]
                    if row['event_id'] != observation['event_id']:
                        raise ValueError('Prequential forecast linked to wrong event')
                    score_arithmetic(row, float(observation['growth']), 'prequential')

        for condition in design['conditions']:
            for sid in range(3):
                for tick in design['checkpoints']:
                    cell = (arena, condition, sid, tick)
                    row = checkpoint_rows[cell]
                    scored = []
                    for p in range(design['n_probes']):
                        prediction = predictions[(*cell, p)]
                        probe = probes[arena, p]
                        if prediction['probe_group'] != probe['probe_group']:
                            raise ValueError('Prediction linked to wrong probe group')
                        close(prediction['target'], probe['target'], 'prediction target')
                        score_arithmetic(prediction, float(probe['target']), 'probe')
                        scored.append(prediction)
                    primary = [r for r in scored if r['probe_group'] == 'uncapped']
                    for metric, primitive in (('probe_crps', 'crps'), ('probe_mse', 'squared_error'),
                                              ('coverage_90', 'covered'), ('interval_width_90', 'width')):
                        close(row[metric], np.mean([float(r[primitive]) for r in primary]), 'checkpoint '+metric)
                    close(row['probe_crps_all'], np.mean([float(r['crps']) for r in scored]), 'all-probe CRPS')
                    expected_count = 0 if condition == 'prior' else tick*(3 if condition == 'pooled' else 1)
                    close(row['unique_observations'], expected_count, 'unique observation count')
                    errors = []
                    for p in PRIOR:
                        parameter = parameters[(*cell, p)]
                        close(parameter['true_value'], case['world_parameters'][p], 'parameter truth')
                        if not all(np.isfinite(float(parameter[k])) for k in ('posterior_mean', 'posterior_sd', 'lo90', 'hi90')):
                            raise ValueError('Nonfinite parameter summary')
                        if float(parameter['posterior_sd']) < 0 or float(parameter['lo90']) > float(parameter['hi90']):
                            raise ValueError('Invalid parameter uncertainty')
                        errors.append(((float(parameter['posterior_mean'])-case['world_parameters'][p]) /
                                       (design['prior'][p][1]-design['prior'][p][0]))**2)
                    close(row['parameter_nrmse'], np.sqrt(np.mean(errors)), 'parameter NRMSE')

        # Repeated references are one learner, not three independent replicates.
        for condition in ('prior', 'pooled'):
            for tick in design['checkpoints']:
                reference = checkpoint_rows[arena, condition, 0, tick]
                for sid in (1, 2):
                    row = checkpoint_rows[arena, condition, sid, tick]
                    if {k: v for k, v in row.items() if k != 'society'} != {k: v for k, v in reference.items() if k != 'society'}:
                        raise ValueError('Repeated reference checkpoints differ across society IDs')
                    for p in range(design['n_probes']):
                        for field in ('crps', 'mean', 'lo90', 'hi90'):
                            close(predictions[(arena, condition, sid, tick, p)][field],
                                  predictions[(arena, condition, 0, tick, p)][field], 'repeated reference forecast')
        for condition in design['conditions']:
            for sid in range(3):
                for p in range(design['n_probes']):
                    for field in ('crps', 'mean', 'lo90', 'hi90'):
                        close(predictions[(arena, condition, sid, 0, p)][field],
                              predictions[(arena, 'prior', 0, 0, p)][field], 'common initial prior')

        for model_key in model_keys:
            snapshot = json.loads((directory/'snapshots'/f'{arena}-{model_key}.json').read_text())
            model = RenewalSMC.from_snapshot(snapshot)
            condition = 'private' if model_key.startswith('private-') else model_key
            sid = int(model_key.split('-')[1]) if condition == 'private' else 0
            cell = (arena, condition, sid, horizon)
            info = model.summary()
            for j, p in enumerate(PRIOR):
                saved_parameter = parameters[(*cell, p)]
                close(saved_parameter['posterior_mean'], info['mean'][p], 'terminal posterior mean')
                close(saved_parameter['posterior_sd'], np.sqrt(max(0., info['covariance'][j][j])), 'terminal posterior SD')
                close(saved_parameter['lo90'], info['intervals_90'][p][0], 'terminal posterior interval')
                close(saved_parameter['hi90'], info['intervals_90'][p][1], 'terminal posterior interval')
            expected_count = int(checkpoint_rows[cell]['unique_observations']) - int(checkpoint_rows[cell]['updates_failed'])
            if len(model.evidence) != expected_count:
                raise ValueError('Snapshot accepted evidence count mismatch')
            legal_ids = {observation['event_id']: observation for (a, _, s), observation in observations.items()
                         if a == arena and (condition == 'pooled' or (condition == 'private' and s == sid))}
            for event in model.evidence:
                if event['event_id'] not in legal_ids:
                    raise ValueError('Snapshot contains foreign or privileged evidence')
                legal = legal_ids[event['event_id']]
                for field in ('growth', 'own_infrastructure', 'other_infrastructure'):
                    close(event[field], legal[field], 'snapshot evidence '+field)
                close(event['headroom'], float(legal['capacity'])-float(legal['stock_before']), 'snapshot evidence headroom')
            for p in range(design['n_probes']):
                probe = probes[arena, p]
                regenerated = score_samples(model.predict(query_from(probe), n_samples=design['forecast_samples'],
                    seed=stable_seed(VERSION, arena, p, 'forecast')), float(probe['target']))
                for field, value in regenerated.items():
                    close(predictions[(*cell, p)][field], value, 'terminal snapshot forecast '+field)
            if condition == 'prior':
                for tick in design['checkpoints']:
                    for p in range(design['n_probes']):
                        for field in ('crps', 'mean', 'lo90', 'hi90'):
                            close(predictions[(arena, 'prior', 0, tick, p)][field],
                                  predictions[(*cell, p)][field], 'frozen prior prediction')
    return {'verified': True, 'arenas': len(design['cases']), 'checkpoints': len(rows),
            'artifacts': len(completed['artifacts']), 'prediction_rows': len(predictions),
            'terminal_snapshot_forecasts': len(arenas)*len(model_keys)*design['n_probes']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'verify'))
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/world-model-v1')
    parser.add_argument('--arenas', type=int, default=24)
    parser.add_argument('--ticks', type=int, default=128)
    parser.add_argument('--particles', type=int, default=1024)
    parser.add_argument('--development', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        design = prepare(args.output, args.arenas, args.ticks, args.particles, args.development)
        print(json.dumps({'prepared': str(args.output), 'arenas': len(design['cases']), 'bank': design['bank']}))
    elif args.command == 'run':
        result = run(args.output)
        print(json.dumps({'arenas': result['n_arenas'], 'conditions': result['conditions']}, indent=2))
    else:
        print(json.dumps(verify(args.output), indent=2))


if __name__ == '__main__':
    main()
