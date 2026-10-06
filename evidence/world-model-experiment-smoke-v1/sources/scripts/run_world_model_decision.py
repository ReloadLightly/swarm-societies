#!/usr/bin/env python3
"""Frozen single-allocation control, with a separate development gate.

The planner receives only legacy institution observations and previously
received home events. Full simulator branches belong exclusively to evaluation.
No evolutionary search or model-generation calls occur in this study.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

from swarm_societies.candidate import CandidateProgram
from swarm_societies.ecology_stepwise_v1 import EcologyConfig, StepwiseEcology
from swarm_societies.world_model_v1 import decision
from swarm_societies.world_model_v1.sharing import SharingRuntime

VERSION = 'world-model-decision-v1'
CONDITIONS = ('prior', 'learned', 'known')
PARAMETERS = ('r', 'b', 'g')
PRIOR = {'r': [2., 8.], 'b': [.5, 3.], 'g': [0., .8]}
SOURCES = (
    'scripts/run_world_model_decision.py',
    'swarm_societies/ecology_stepwise_v1.py',
    'swarm_societies/ecology_world_model_v1.py',
    'swarm_societies/ecology_consumption_v2.py',
    'swarm_societies/candidate.py',
    'swarm_societies/world_model_v1/decision.py',
    'swarm_societies/world_model_v1/sharing.py',
    'swarm_societies/world_model_v1/learner.py',
    'swarm_societies/world_model_v1/__init__.py',
    'docs/world-model-decision-protocol.md',
    'requirements-world-model-v1.txt',
)
MATERIAL_METRICS = (
    'utility', 'focal_welfare', 'consumption_per_member', 'shortfall_per_member',
    'terminal_wealth_per_member', 'investment', 'external_harm',
    'other_society_welfare', 'other_society_utility',
)
SCORE_METRICS = (*MATERIAL_METRICS, 'regret', 'forecast_utility',
                 'utility_prediction_error', 'utility_absolute_error',
                 'forecast_budget', 'actual_budget', 'budget_prediction_error',
                 'budget_absolute_error', 'menu_forecast_mae')
POLICY = '''def institution(obs, state):
    role = (obs['society_id'] + ROLE_ROTATION) % 3
    phase = (obs['tick'] // 8 + role * 3) % 9
    public = 0.0 if phase < 3 else (0.3 if phase < 6 else 0.8)
    if obs['tick'] >= WARMUP_TICKS:
        public = 0.0
    return {'tax_rate': 0.6, 'public_fraction': public,
            'defense_fraction': 0.0, 'reserve_fraction': 0.0,
            'raid_permission': False, 'state': {}}

def member_policy(obs, state):
    return {'action': 'harvest', 'target': obs['society_id'],
            'effort': 1.0, 'state': {}}
'''


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_seed(*parts):
    return int.from_bytes(hashlib.sha256('/'.join(map(str, parts)).encode()).digest()[:8], 'big')


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def packed_write(path, value):
    """One atomic, deterministic case artifact; never overwrite completed cases."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_bytes(gzip.compress(canonical(value), mtime=0))
    temporary.replace(path)


def packed_read(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def csv_bytes(rows):
    if not rows:
        raise ValueError('Cannot emit an empty study table')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def make_design(*, development=False, arenas=24):
    """Canonical prospective contract; numerical smoke tests may copy it locally."""
    if type(arenas) is not int or arenas < 1:
        raise ValueError('Arena count must be a positive integer')
    if development:
        arenas = 6
    bank = 'development' if development else 'evaluation'
    cases = []
    for index in range(arenas):
        arena = f'decision-{bank}-{index:03d}'
        rng = np.random.default_rng(stable_seed(VERSION, arena, 'laws'))
        laws = ({'r': (2.4, 4.6, 6.8)[index//2], 'b': (.7, 2.7)[index % 2], 'g': .3}
                if development else {key: float(rng.uniform(*bounds)) for key, bounds in
                                      zip(PARAMETERS, ((2.4, 6.8), (.7, 2.7), (.05, .7)))})
        cases.append({'arena_id': arena, 'index': index, 'role_rotation': index % 3,
                      'environment_seed': stable_seed(VERSION, arena, 'environment'),
                      'world_parameters': laws})
    return {
        'study': VERSION, 'schema_version': 1, 'bank': bank, 'cases': cases,
        'config': asdict(EcologyConfig(n_societies=3, members_per_society=4,
            ticks=64, disturbance_tick=32, initial_patch=10., patch_capacity=30.,
            regeneration=5., enable_disturbance=False)),
        'warmup_ticks': 32, 'horizon': 32, 'menu': [0., .5, 1.],
        'conditions': list(CONDITIONS), 'planner_samples': 512,
        'prior': deepcopy(PRIOR), 'sensor_sigma': .05,
        'learner_settings': {'n_particles': 1024, 'rejuvenation_steps': 4, 'ess_fraction': .5},
        'sharing_condition': 'redundant',
        'observation_mode': 'full_observation_control',
        'observation_contract': 'Legacy institution fields plus its authenticated delivered home growth event from the preceding tick; no current growth, true productivity, future tax budget, weather or RNG.',
        'timing': 'Warmup reports after completed ecology ticks; start_tick(warmup_ticks) delivers the final warmup home event before any focal allocation forecast.',
        'objective': '(window consumption + 0.2 terminal wealth) / members',
        'primary': 'Learned minus prior utility; average the three focal rotations within each independent shared-law arena.',
        'replication_unit': 'Independent shared-law arena; three focal rotations, belief conditions, menu branches, members and planning samples are nested observations.',
        'bootstrap': {'draws': 2000, 'seed': 9401, 'level': .95},
        'gate': {'minimum_rank_switches': 2, 'minimum_realized_zero': 2,
                 'minimum_realized_one': 2, 'minimum_known_positive_one': 2,
                 'absolute_tolerance': .005, 'mcse_multiplier': 3.,
                 'counterfactual_b': [.7, 2.7]},
        'failure_policy': 'Failed forecasts remain explicit and invalidate incomplete-panel means and intervals. Any failed forecast or learner update prevents completion, as do unhandled simulation or learning exceptions; no cases are dropped or replaced.',
        'scope': 'Single fixed-planner allocation; no active experimentation, discovery, new model generation or evolution. Known coefficients do not supply hidden state or guarantee an optimal controller.',
        'model_generation_calls': 0, 'independent_evolutionary_runs': 0,
    }


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare(directory, arenas=24, development=False, development_gate=None):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Preparation requires a fresh empty output directory')
    if not development and arenas != 24:
        raise ValueError('The prospective evaluation panel contains exactly 24 independent arenas')
    design = make_design(development=development, arenas=arenas)
    proof = None
    if not development:
        if development_gate is None:
            raise ValueError('Evaluation preparation requires a completed passing development gate')
        gate_directory = Path(development_gate)
        _require(not directory.resolve().is_relative_to(gate_directory.resolve()),
                 'Evaluation output cannot be nested inside its development proof')
        receipt = verify(gate_directory)
        gate_design = check_design(gate_directory, live=True)
        gate = json.loads((gate_directory/'gate.json').read_text())
        _require(gate_design['bank'] == 'development' and gate['passed'],
                 'Development gate has not passed; evaluation preparation is prohibited')
        proof = {'receipt': receipt, 'design_sha256': sha(gate_directory/'design.json'),
                 'gate_sha256': sha(gate_directory/'gate.json'),
                 'completion_sha256': sha(gate_directory/'completion.json')}
    directory.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        target = directory/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    if proof is not None:
        # Keep all development records for an independently checkable gate.
        shutil.copytree(Path(development_gate), directory/'development-proof')
    design.update(frozen_utc=datetime.now(timezone.utc).isoformat(),
                  source_hashes={name: sha(ROOT/name) for name in SOURCES},
                  development_proof=proof,
                  software={'python': platform.python_version(), 'numpy': np.__version__,
                            'scipy': scipy.__version__})
    json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(sha(directory/'design.json')+'\n')
    return design


def check_design(directory, live=True):
    directory = Path(directory)
    _require(sha(directory/'design.json') == (directory/'design.sha256').read_text().strip(),
             'Frozen decision design checksum mismatch')
    design = json.loads((directory/'design.json').read_text())
    _require(design['bank'] in ('development', 'evaluation'), 'Invalid decision bank')
    _require(design['bank'] != 'evaluation' or len(design['cases']) == 24,
             'Evaluation must retain all 24 independent arenas')
    expected = make_design(development=design['bank'] == 'development', arenas=len(design['cases']))
    for key, value in expected.items():
        _require(design.get(key) == value, 'Frozen decision contract differs: '+key)
    _require(set(design['source_hashes']) == set(SOURCES), 'Source inventory differs')
    for name, expected_hash in design['source_hashes'].items():
        _require(sha(directory/'sources'/name) == expected_hash,
                 'Archived decision source mismatch: '+name)
        if live:
            _require(sha(ROOT/name) == expected_hash, 'Live decision source changed after freeze: '+name)
    if design['bank'] == 'evaluation':
        proof = design.get('development_proof')
        _require(isinstance(proof, dict), 'Evaluation lacks a development gate proof')
        for name in ('design', 'gate', 'completion'):
            _require(sha(directory/'development-proof'/f'{name}.json') == proof[name+'_sha256'],
                     'Development proof hash differs: '+name)
        _require(json.loads((directory/'development-proof'/'gate.json').read_text())['passed'],
                 'Archived development gate failed')
    return design


def sample_coefficients(snapshot, count, seed):
    """Inverse-CDF draws use common uniforms without consuming any live belief RNG."""
    particles = np.asarray(snapshot['particles'], dtype=float)
    weights = np.exp(np.asarray(snapshot['log_weights'], dtype=float))
    weights /= weights.sum()
    cumulative = np.cumsum(weights)
    cumulative[-1] = 1.
    uniforms = np.random.default_rng(seed).random(count)
    return particles[np.searchsorted(cumulative, uniforms, side='right')].tolist()


def _numpy_global_state():
    name, state, position, gaussian, cached = np.random.get_state()
    return [name, state.tolist(), position, gaussian, cached]


def _protected_hashes(engine, sharing, noise):
    return {'engine': digest(engine.snapshot()), 'sharing': digest(sharing.snapshot()),
            'sensor_rng': digest(noise.bit_generator.state)}


def _forecast(obs, draws, seed, design):
    try:
        result = decision.forecast(obs, draws, seed=seed, horizon=design['horizon'], menu=design['menu'])
        # Validate finite JSON before accepting this as a committed forecast.
        canonical(result)
        _require(result['action'] in design['menu'], 'Forecast chose an unavailable action')
        for name in ('actions', 'paired'):
            _require([row['public_fraction'] for row in result[name]] == design['menu'],
                     'Forecast menu output is incomplete or unordered: '+name)
        _require(all(np.isfinite(row['utility']) and np.isfinite(row['initial_budget'])
                     for row in result['actions']), 'Invalid forecast action values')
        return {'status': 'ok', **result}
    except Exception as exc:
        return {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}


def branch_outcomes(snapshot, focal, action, design):
    """Evaluator-only physical branch; no branch state or outcome enters forecasts."""
    branch = StepwiseEcology.from_snapshot(snapshot)
    branch.set_institution_decisions({focal: {'public_fraction': action}})
    branch.finish_tick()
    while branch.phase != 'complete':
        branch.step()
    result = branch.result()
    window = [row for row in result['timeseries'] if row['tick'] >= design['warmup_ticks']]
    n_members = design['config']['members_per_society']
    society_values = []
    for society in range(design['config']['n_societies']):
        rows = [row for row in window if row['society'] == society]
        members = [row for row in result['member_metrics'] if row['society_id'] == society]
        consumption = sum(row['consumption'] for row in rows)/n_members
        wealth = sum(row['final_wealth'] for row in members)/n_members
        society_values.append({
            'utility': consumption+.2*wealth,
            'focal_welfare': sum(row['welfare'] for row in rows)/design['horizon'],
            'consumption_per_member': consumption,
            'shortfall_per_member': sum(row['shortfall'] for row in rows)/n_members,
            'terminal_wealth_per_member': wealth,
            'investment': sum(row['investment'] for row in rows),
            'external_harm': sum(row['external_harm'] for row in rows),
        })
    own = society_values[focal]
    others = [row for index, row in enumerate(society_values) if index != focal]
    receipt = next(row for row in result['local_observations']['institution_receipts']
                   if row['tick'] == design['warmup_ticks'] and row['society_id'] == focal)
    return {'focal': focal, 'public_fraction': action, **own,
            'other_society_welfare': sum(row['focal_welfare'] for row in others)/len(others),
            'other_society_utility': sum(row['utility'] for row in others)/len(others),
            'initial_budget': receipt['budget'], 'trajectory_digest': result['digest']}


def score_forecasts(arena, forecasts, branches, design):
    rows = []
    for forecast in forecasts:
        focal, condition = forecast['focal'], forecast['condition']
        choices = [row for row in branches if row['focal'] == focal]
        row = {'arena_id': arena, 'focal': focal, 'condition': condition,
               'status': forecast['status'], 'action': forecast.get('action')}
        if forecast['status'] != 'ok':
            rows.append({**row, **{metric: None for metric in SCORE_METRICS}})
            continue
        selected = next(branch for branch in choices if branch['public_fraction'] == forecast['action'])
        predicted = next(item for item in forecast['actions'] if item['public_fraction'] == forecast['action'])
        utility_error = predicted['utility']-selected['utility']
        budget_error = predicted['initial_budget']-selected['initial_budget']
        row.update({key: selected[key] for key in MATERIAL_METRICS})
        row.update(regret=max(item['utility'] for item in choices)-selected['utility'],
                   forecast_utility=predicted['utility'], utility_prediction_error=utility_error,
                   utility_absolute_error=abs(utility_error), forecast_budget=predicted['initial_budget'],
                   actual_budget=selected['initial_budget'], budget_prediction_error=budget_error,
                   budget_absolute_error=abs(budget_error),
                   menu_forecast_mae=float(np.mean([
                       abs(item['utility']-next(branch['utility'] for branch in choices
                           if branch['public_fraction'] == item['public_fraction']))
                       for item in forecast['actions']])))
        rows.append(row)
    return rows


def evaluate_case(case, design):
    """Deterministic complete case; forecasts are committed before all branches."""
    arena = case['arena_id']
    policy = CandidateProgram(f'ROLE_ROTATION = {case["role_rotation"]}\n'
                              f'WARMUP_TICKS = {design["warmup_ticks"]}\n\n'+POLICY)
    engine = StepwiseEcology([policy]*3, config=design['config'],
        seed=case['environment_seed'], world_parameters=case['world_parameters'],
        observation_mode=design['observation_mode'])
    sharing = SharingRuntime(design['sharing_condition'], arena_id=arena,
        seed=stable_seed(VERSION, arena, 'learners'),
        learner_kwargs={'prior': design['prior'], 'sensor_sigma': design['sensor_sigma'],
                        **design['learner_settings']})
    priors = {str(s): sharing.evaluator_models()[f'institution:{s}'].snapshot() for s in range(3)}
    noise = np.random.default_rng(stable_seed(VERSION, arena, 'sensor'))
    packets, last_owned = [], {}
    for tick in range(design['warmup_ticks']):
        sharing.start_tick(tick)
        completed = engine.step()
        current = {}
        for raw in completed['learning_observations']:
            packet = {key: float(raw[key]) for key in
                      ('stock_before', 'capacity', 'own_infrastructure', 'other_infrastructure')}
            packet.update(event_id=f'{arena}/{raw["event_id"]}', tick=tick, patch=raw['patch'],
                          phase='before_actions', growth=float(raw['growth']+noise.normal(0, design['sensor_sigma'])),
                          sensor_sigma=design['sensor_sigma'])
            packets.append(packet)
            current[raw['patch']] = packet
        sharing.observe_tick(current)
        sharing.submit_reports()
        sharing.finish_tick()
    sharing.start_tick(design['warmup_ticks'])
    learning_state = sharing.snapshot()
    learned = {str(s): sharing.evaluator_models()[f'institution:{s}'].snapshot() for s in range(3)}
    for society in range(3):
        key = f'institution:{society}'
        accepted = {row['event_id'] for row in learned[str(society)]['evidence']}
        packet = next(row for row in packets if row['tick'] == design['warmup_ticks']-1
                      and row['patch'] == society)
        delivered = [row for row in learning_state['frames'] if row['recipient'] == key
                     and row['event_id'] == packet['event_id'] and row['status'] == 'delivered']
        _require(packet['event_id'] in accepted and delivered,
                 'The planner must receive its final warmup event through authenticated delivery')
        last_owned[society] = packet
    institutions = engine.begin_tick()
    observations = {str(s): decision.observation(institutions[s], last_owned[s],
                    consumption_need=design['config']['consumption_need']) for s in range(3)}
    protected_before = _protected_hashes(engine, sharing, noise)
    global_rng_before = digest(_numpy_global_state())
    branch_snapshot = engine.snapshot()
    checkpoint = {'world': branch_snapshot, 'sharing': sharing.snapshot(),
                  'sensor_rng': deepcopy(noise.bit_generator.state)}
    forecasts, gate_forecasts = [], []
    for focal in range(3):
        coefficient_seed = stable_seed(VERSION, arena, focal, 'coefficient-draws')
        forecast_seed = stable_seed(VERSION, arena, focal, 'forecast')
        for condition in CONDITIONS:
            draws = (np.tile([case['world_parameters'][key] for key in PARAMETERS],
                             (design['planner_samples'], 1)).tolist() if condition == 'known'
                     else sample_coefficients(priors[str(focal)] if condition == 'prior' else learned[str(focal)],
                                              design['planner_samples'], coefficient_seed))
            forecasts.append({'focal': focal, 'condition': condition,
                'coefficient_seed': coefficient_seed, 'forecast_seed': forecast_seed,
                'coefficient_draws': draws,
                **_forecast(observations[str(focal)], draws, forecast_seed, design)})
        if design['bank'] == 'development':
            item = {'focal': focal}
            for label, b in zip(('low', 'high'), design['gate']['counterfactual_b']):
                draws = np.tile([case['world_parameters']['r'], b, case['world_parameters']['g']],
                                (design['planner_samples'], 1)).tolist()
                item[label] = _forecast(observations[str(focal)], draws, forecast_seed, design)
            gate_forecasts.append(item)
    commitment = digest({'forecasts': forecasts, 'gate_forecasts': gate_forecasts})
    _require(_protected_hashes(engine, sharing, noise) == protected_before,
             'Forecast generation changed protected live state')
    branches = []
    for focal in range(3):
        for action in design['menu']:
            branches.append({'arena_id': arena, **branch_outcomes(branch_snapshot, focal, action, design)})
    protected_after = _protected_hashes(engine, sharing, noise)
    _require(protected_after == protected_before, 'Evaluator branching changed protected live state')
    _require(digest(_numpy_global_state()) == global_rng_before,
             'Forecasts or evaluator branches changed the global NumPy RNG')
    _require(digest({'forecasts': forecasts, 'gate_forecasts': gate_forecasts}) == commitment,
             'Committed forecasts were changed after evaluator branching')
    return {'study': VERSION, 'arena_id': arena, 'case': deepcopy(case),
            'warmup': {'packets': packets, 'prior_models': priors, 'learned_models': learned,
                       'sharing_summary': sharing.summary(),
                       'engine_snapshot_sha256': protected_before['engine'],
                       'sharing_snapshot_sha256': protected_before['sharing']},
            'checkpoint': checkpoint, 'numpy_global_rng_unchanged': True,
            'legal_observations': observations, 'forecasts': forecasts,
            'gate_forecasts': gate_forecasts, 'forecast_commitment_sha256': commitment,
            'branches': branches, 'scores': score_forecasts(arena, forecasts, branches, design),
            'protected_state_before': protected_before, 'protected_state_after': protected_after}


def bootstrap(values, design):
    finite = [value for value in values if value is not None and np.isfinite(value)]
    result = {'mean': None, 'ci95': None, 'n_arenas': len(values), 'valid_arenas': len(finite)}
    if len(finite) != len(values) or not values:
        return result
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(design['bootstrap']['seed'])
    sampled = values[rng.integers(0, len(values), size=(design['bootstrap']['draws'], len(values)))].mean(axis=1)
    result.update(mean=float(values.mean()), ci95=np.quantile(sampled, [.025, .975]).tolist())
    return result


def summarize(scores, branches, design):
    arenas = []
    expected_scores = {(case['arena_id'], focal, condition) for case in design['cases']
                       for focal in range(3) for condition in CONDITIONS}
    _require(len(scores) == len(expected_scores) and
             {(row['arena_id'], row['focal'], row['condition']) for row in scores} == expected_scores,
             'Score grid is missing or duplicates focal decisions')
    expected_branches = {(case['arena_id'], focal, action) for case in design['cases']
                         for focal in range(3) for action in design['menu']}
    _require(len(branches) == len(expected_branches) and
             {(row['arena_id'], row['focal'], row['public_fraction']) for row in branches} == expected_branches,
             'Branch grid is missing or duplicates actions')
    for case in design['cases']:
        for condition in CONDITIONS:
            selected = [row for row in scores if row['arena_id'] == case['arena_id']
                        and row['condition'] == condition]
            complete = all(row['status'] == 'ok' for row in selected)
            row = {'arena_id': case['arena_id'], 'condition': condition,
                   'status': 'ok' if complete else 'incomplete', 'n_focals': len(selected),
                   'action_mean': float(np.mean([r['action'] for r in selected])) if complete else None,
                   'n_action_zero': sum(r['action'] == 0. for r in selected),
                   'n_action_half': sum(r['action'] == .5 for r in selected),
                   'n_action_one': sum(r['action'] == 1. for r in selected)}
            row.update({metric: float(np.mean([r[metric] for r in selected])) if complete else None
                        for metric in SCORE_METRICS})
            arenas.append(row)
    summaries = []
    for condition in CONDITIONS:
        selected = [row for row in arenas if row['condition'] == condition]
        raw = [row for row in scores if row['condition'] == condition]
        summaries.append({'condition': condition,
            'metrics': {metric: bootstrap([row[metric] for row in selected], design) for metric in SCORE_METRICS},
            'choice_counts': {str(action): sum(row['action'] == action for row in raw) for action in design['menu']},
            'planned_decisions': len(raw), 'valid_plans': sum(row['status'] == 'ok' for row in raw),
            'failed_plans': sum(row['status'] != 'ok' for row in raw)})
    paired = []
    for left, right in (('learned', 'prior'), ('known', 'prior'), ('learned', 'known')):
        values = {}
        for metric in SCORE_METRICS:
            differences = []
            for case in design['cases']:
                pair = {row['condition']: row[metric] for row in arenas if row['arena_id'] == case['arena_id']}
                differences.append(None if pair[left] is None or pair[right] is None else pair[left]-pair[right])
            values[metric] = bootstrap(differences, design)
        paired.append({'contrast': left+'_minus_'+right, 'left': left, 'right': right, 'metrics': values})
    summary = {'study': VERSION, 'bank': design['bank'], 'n_arenas': len(design['cases']),
        'n_focal_decisions': len(scores), 'n_branches': len(branches),
        'independent_evolutionary_runs': 0, 'model_generation_calls': 0,
        'replication_unit': design['replication_unit'], 'conditions': summaries,
        'paired_contrasts': paired, 'primary': paired[0]['metrics']['utility']}
    return summary, arenas


def gate_summary(cases, design):
    rules = design['gate']
    rows = []
    for case in cases:
        for forecast in case['gate_forecasts']:
            focal = forecast['focal']
            row = {'arena_id': case['arena_id'], 'focal': focal, 'rank_switch': False,
                   'low_gap': None, 'high_gap': None, 'low_tolerance': None, 'high_tolerance': None}
            if all(forecast[label]['status'] == 'ok' for label in ('low', 'high')):
                for label in ('low', 'high'):
                    extreme = next(p for p in forecast[label]['paired'] if p['public_fraction'] == 1.)
                    row[label+'_gap'] = extreme['minus_redistribute']
                    row[label+'_tolerance'] = max(rules['absolute_tolerance'],
                                                  rules['mcse_multiplier']*extreme['paired_mcse'])
                row['rank_switch'] = (forecast['low']['action'] == 0. and forecast['high']['action'] == 1.
                    and row['low_gap'] < -row['low_tolerance'] and row['high_gap'] > row['high_tolerance'])
            branch = {item['public_fraction']: item for item in case['branches'] if item['focal'] == focal}
            best = max(design['menu'], key=lambda action: branch[action]['utility'])
            delta = branch[1.]['utility']-branch[0.]['utility']
            known = next(item for item in case['forecasts'] if item['focal'] == focal and item['condition'] == 'known')
            row.update(realized_best=best, realized_one_minus_zero=delta,
                realized_zero=best == 0. and -delta >= rules['absolute_tolerance'],
                realized_one=best == 1. and delta >= rules['absolute_tolerance'],
                known_positive_one=known['status'] == 'ok' and known['action'] == 1.
                                   and delta > rules['absolute_tolerance'])
            rows.append(row)
    counts = {key: sum(row[key] for row in rows) for key in
              ('rank_switch', 'realized_zero', 'realized_one', 'known_positive_one')}
    failed = sum(item['status'] != 'ok' for case in cases for item in case['forecasts'])
    failed += sum(item[label]['status'] != 'ok' for case in cases for item in case['gate_forecasts'] for label in ('low', 'high'))
    checks = {'multiple_robust_rank_switches': counts['rank_switch'] >= rules['minimum_rank_switches'],
              'realized_redistribution_support': counts['realized_zero'] >= rules['minimum_realized_zero'],
              'realized_investment_support': counts['realized_one'] >= rules['minimum_realized_one'],
              'known_law_positive_investment': counts['known_positive_one'] >= rules['minimum_known_positive_one'],
              'all_forecasts_valid': failed == 0}
    return {'study': VERSION, 'bank': 'development', 'passed': all(checks.values()),
            'n_arenas': len(cases), 'n_states': len(rows), 'checks': checks,
            'counts': counts, 'failed_forecasts': failed, 'rules': rules, 'states': rows}


def _case_path(directory, case):
    return Path(directory)/'cases'/case['arena_id']/'case.json.gz'


def _run_case(task):
    directory, case, design = task
    path = _case_path(directory, case)
    generated = evaluate_case(case, design)
    if path.exists():
        _require(packed_read(path) == generated, 'Existing case fails semantic resume verification: '+case['arena_id'])
    else:
        packed_write(path, generated)
    return case['arena_id']


def _verify_case(task):
    directory, case, design = task
    stored = packed_read(_case_path(directory, case))
    generated = evaluate_case(case, design)
    _require(stored == generated, 'Decision semantic reconstruction differs: '+case['arena_id'])
    return case['arena_id']


def _parallel(function, tasks, workers):
    if workers == 1:
        return [function(task) for task in tasks]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(function, tasks))


def _aggregate(directory, design):
    cases = [packed_read(_case_path(directory, case)) for case in design['cases']]
    scores = [row for case in cases for row in case['scores']]
    branches = [row for case in cases for row in case['branches']]
    summary, arenas = summarize(scores, branches, design)
    return cases, scores, branches, summary, arenas


def _artifacts(directory):
    directory = Path(directory)
    return {str(path.relative_to(directory)): sha(path) for path in sorted(directory.rglob('*'))
            if path.is_file() and path.name != 'completion.json' and not path.name.endswith('.tmp')
            and 'development-proof' not in path.relative_to(directory).parts}


def run(directory, workers=4):
    directory = Path(directory)
    if (directory/'completion.json').exists():
        raise ValueError('Completed studies cannot be overwritten')
    _require(type(workers) is int and workers >= 1, 'Worker count must be positive')
    design = check_design(directory, live=True)
    start = time.monotonic()
    _parallel(_run_case, [(str(directory), case, design) for case in design['cases']], workers)
    cases, scores, branches, summary, arenas = _aggregate(directory, design)
    for name, rows in (('scores', scores), ('branches', branches), ('arenas', arenas)):
        (directory/f'{name}.csv').write_bytes(csv_bytes(rows))
    json_write(directory/'summary.json', summary)
    if design['bank'] == 'development':
        json_write(directory/'gate.json', gate_summary(cases, design))
    failed_plans = sum(row['status'] != 'ok' for case in cases for row in case['forecasts'])
    failed_plans += sum(row[label]['status'] != 'ok' for case in cases
                        for row in case['gate_forecasts'] for label in ('low', 'high'))
    failed_updates = sum(case['warmup']['sharing_summary']['failed_updates'] for case in cases)
    _require(failed_plans == 0 and failed_updates == 0,
             'Failed forecasts or learner updates are retained; completion is prohibited')
    completion = {'study': VERSION, 'completed_utc': datetime.now(timezone.utc).isoformat(),
                  'elapsed_seconds': time.monotonic()-start, 'elapsed_scope': 'This run command, including semantic checks of any pre-existing cases',
                  'n_arenas': len(cases), 'n_focal_decisions': len(scores), 'n_branches': len(branches),
                  'model_generation_calls': 0, 'independent_evolutionary_runs': 0,
                  'artifact_hashes': _artifacts(directory)}
    json_write(directory/'completion.json', completion)
    return summary


def verify(directory, workers=4):
    directory = Path(directory)
    design = check_design(directory, live=True)
    completion = json.loads((directory/'completion.json').read_text())
    _require(completion['study'] == VERSION and completion['model_generation_calls'] == 0
             and completion['independent_evolutionary_runs'] == 0, 'Invalid completion identity')
    _require(completion['artifact_hashes'] == _artifacts(directory), 'Decision artifact hashes differ')
    _parallel(_verify_case, [(str(directory), case, design) for case in design['cases']], workers)
    cases, scores, branches, summary, arenas = _aggregate(directory, design)
    for name, rows in (('scores', scores), ('branches', branches), ('arenas', arenas)):
        _require((directory/f'{name}.csv').read_bytes() == csv_bytes(rows), 'Decision aggregate table differs: '+name)
    _require(json.loads((directory/'summary.json').read_text()) == summary, 'Decision summary differs')
    if design['bank'] == 'development':
        _require(json.loads((directory/'gate.json').read_text()) == gate_summary(cases, design),
                 'Development gate differs from recorded forecasts and branches')
    else:
        proof_receipt = verify(directory/'development-proof', workers=workers)
        _require(proof_receipt == design['development_proof']['receipt'], 'Development proof verification receipt differs')
    _require(completion['n_arenas'] == len(cases) and completion['n_focal_decisions'] == len(scores)
             and completion['n_branches'] == len(branches), 'Completion counts differ')
    return {'verified': True, 'study': VERSION, 'bank': design['bank'], 'n_arenas': len(cases),
            'n_focal_decisions': len(scores), 'n_branches': len(branches),
            'semantic_case_replays': len(cases), 'artifact_hashes_checked': len(completion['artifact_hashes']),
            'model_generation_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'verify'))
    parser.add_argument('--output', default='evidence/world-model-decision-v1')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--development', action='store_true')
    parser.add_argument('--development-gate')
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output, development=args.development, development_gate=args.development_gate)
        print(json.dumps({'study': result['study'], 'bank': result['bank'], 'n_arenas': len(result['cases'])}))
    elif args.command == 'run':
        print(json.dumps(run(args.output, workers=args.workers), indent=2))
    else:
        print(json.dumps(verify(args.output, workers=args.workers), indent=2))


if __name__ == '__main__':
    main()
