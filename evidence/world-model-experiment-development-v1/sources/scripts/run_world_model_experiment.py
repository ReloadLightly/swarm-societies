#!/usr/bin/env python3
"""Cost-matched escrow experiments and a subsequent parameter-update ablation.

Every experiment selector is committed before any physical probe path. Updated
and frozen coefficient controls later receive identical legal state inputs.
Protected evaluator branches never feed a selector or another live belief.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
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

from scripts import run_world_model_decision as base
from swarm_societies.candidate import CandidateProgram
from swarm_societies.ecology_stepwise_v1 import EcologyConfig, StepwiseEcology
from swarm_societies.world_model_v1 import decision, experimentation
from swarm_societies.world_model_v1.learner import RenewalSMC, empirical_crps
from swarm_societies.world_model_v1.sharing import SharingRuntime

VERSION = 'world-model-experiment-v1'
STRATEGIES = ('active', 'fixed', 'random')
BELIEFS = ('frozen', 'updated', 'known')
SCHEDULES = ('early', 'late', 'split', 'redistribute')
SOURCES = tuple(dict.fromkeys((
    'scripts/run_world_model_experiment.py',
    'swarm_societies/world_model_v1/experimentation.py',
    'docs/world-model-experiment-protocol.md', *base.SOURCES,
)))
canonical, digest, sha = base.canonical, base.digest, base.sha
stable_seed, json_write = base.stable_seed, base.json_write
packed_read, packed_write, csv_bytes = base.packed_read, base.packed_write, base.csv_bytes
_require, sample_coefficients = base._require, base.sample_coefficients

DECISION_METRICS = (*base.SCORE_METRICS, 'total_utility', 'total_consumption_per_member',
    'total_shortfall_per_member', 'probe_consumption_per_member', 'probe_shortfall_per_member',
    'probe_harvest_per_member', 'actual_experiment_investment', 'probe_effort_cost',
    'total_external_harm', 'other_society_total_utility', 'pre_crps_uncapped',
    'post_crps_uncapped', 'crps_change_uncapped', 'pre_crps_all', 'post_crps_all',
    'crps_change_all', 'sent_bytes', 'delivered_bytes', 'own_unique_events_added')
CONTRAST_METRICS = ('update_value_difference', 'total_utility_difference',
    'frozen_total_utility_difference', 'decomposition_residual', 'crps_difference',
    'experiment_investment_difference')


class _ProjectedRecord(dict):
    """Small, in-memory projection with checks derived from a decoded full case.

    JSON cannot instantiate this type. Stored flags therefore cannot substitute
    for reconstructing invariants from the full checkpoints and receipts.
    """

    def __init__(self, data, invariant_checks):
        super().__init__(data)
        self.invariant_checks = deepcopy(invariant_checks)


def make_design(*, development=False, arenas=24):
    if type(arenas) is not int or arenas < 1:
        raise ValueError('Arena count must be positive')
    if development:
        arenas = 6
    bank = 'development' if development else 'evaluation'
    cases = []
    for index in range(arenas):
        arena = f'experiment-{bank}-{index:03d}'
        rng = np.random.default_rng(stable_seed(VERSION, arena, 'laws'))
        laws = ({'r': (2.4, 4.6, 6.8)[index//2], 'b': (.7, 2.7)[index % 2], 'g': .3}
                if development else {key: float(rng.uniform(*bounds)) for key, bounds in
                zip(base.PARAMETERS, ((2.4, 6.8), (.7, 2.7), (.05, .7)))})
        cases.append({'arena_id': arena, 'index': index, 'role_rotation': index % 3,
                      'environment_seed': stable_seed(VERSION, arena, 'environment'),
                      'world_parameters': laws})
    return {
        'study': VERSION, 'schema_version': 1, 'bank': bank, 'cases': cases,
        'config': asdict(EcologyConfig(n_societies=3, members_per_society=4, ticks=48,
            disturbance_tick=24, initial_patch=10., patch_capacity=30., regeneration=5.,
            enable_disturbance=False)),
        'warmup_ticks': 8, 'probe_ticks': 8, 'late_offset': 4, 'horizon': 32,
        'menu': [0., .5, 1.], 'strategies': list(STRATEGIES), 'beliefs': list(BELIEFS),
        'schedules': list(SCHEDULES), 'planner_samples': 512, 'selector_samples': 512,
        'n_probes': 64, 'prediction_samples': 512, 'prior': deepcopy(base.PRIOR),
        'sensor_sigma': .05, 'learner_settings': {'n_particles': 1024,
            'rejuvenation_steps': 4, 'ess_fraction': .5},
        'sharing_condition': 'redundant', 'observation_mode': 'full_observation_control',
        'escrow': 'All institutions reserve all tax receipts on the final warmup tick. Probe tax is zero, transfers/defense are absent, so pre-probe legal treasury B is the complete experiment budget.',
        'schedules_contract': {name: list(value) for name, value in experimentation.SCHEDULES.items()},
        'redistribution_control': 'Outside the cost-matched comparison: return B on the first probe tick, zero probe investment.',
        'selector': 'Joint Gaussian moment information proxy, not exact expected information gain. Fixed chooses split; random precommits one uniformly selected schedule.',
        'observation_contract': 'Same legacy institution allowlist and authenticated previous-tick home growth event as decision-v1. Post-probe frozen and updated controls receive the identical current observation; only coefficient updates differ.',
        'objective': '(probe consumption + continuation consumption + 0.2 final wealth) / members',
        'primary': '(active updated minus frozen utility) minus (random updated minus frozen utility), averaging focal rotations within independent arenas.',
        'replication_unit': 'Independent shared-law arena; societies, strategies, schedules, belief ablations, members and physical branches are dependent.',
        'bootstrap': {'draws': 2000, 'seed': 9501, 'level': .95},
        'gate': {'minimum_distinct_active_schedules': 2, 'minimum_nonfixed_advantages': 2,
                 'proxy_tolerance': 1e-4, 'minimum_costed_action_changes': 2},
        'probe_design': '64 independent common held-out same-law queries: even rows uncapped headroom30, odd rows headroom0/2/6; own/external infrastructure uniform[0,2]. Targets never select experiments or update beliefs.',
        'failure_policy': 'Retain failed selections/forecasts/updates and invalidate incomplete means. Failures or violated invariants prevent completion; no replacement or omission of arenas.',
        'model_generation_calls': 0, 'independent_evolutionary_runs': 0,
    }


def prepare(directory, arenas=24, development=False, development_gate=None):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Preparation requires a fresh empty directory')
    _require(development or arenas == 24, 'Evaluation contains exactly 24 independent arenas')
    design = make_design(development=development, arenas=arenas)
    proof = None
    if not development:
        _require(development_gate is not None, 'Evaluation requires a completed passing development gate')
        gate_directory = Path(development_gate)
        _require(not directory.resolve().is_relative_to(gate_directory.resolve()),
                 'Evaluation output cannot be inside its development proof')
        receipt = verify(gate_directory)
        gate_design = check_design(gate_directory)
        gate = json.loads((gate_directory/'gate.json').read_text())
        _require(gate_design['bank'] == 'development' and gate['passed'], 'Development gate failed')
        proof = {'receipt': receipt, **{name+'_sha256': sha(gate_directory/f'{name}.json')
                                      for name in ('design', 'gate', 'completion')}}
    directory.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        target = directory/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    if proof is not None:
        shutil.copytree(Path(development_gate), directory/'development-proof')
    design.update(frozen_utc=datetime.now(timezone.utc).isoformat(), development_proof=proof,
        source_hashes={name: sha(ROOT/name) for name in SOURCES},
        software={'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__})
    json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(sha(directory/'design.json')+'\n')
    return design


def check_design(directory, live=True):
    directory = Path(directory)
    _require(sha(directory/'design.json') == (directory/'design.sha256').read_text().strip(),
             'Experiment design checksum differs')
    design = json.loads((directory/'design.json').read_text())
    _require(design['bank'] in ('development', 'evaluation'), 'Unknown experiment bank')
    _require(design['bank'] != 'evaluation' or len(design['cases']) == 24,
             'Evaluation must retain all 24 arenas')
    expected = make_design(development=design['bank'] == 'development', arenas=len(design['cases']))
    for key, value in expected.items():
        _require(design.get(key) == value, 'Frozen experiment contract differs: '+key)
    _require(set(design['source_hashes']) == set(SOURCES), 'Source inventory differs')
    for name, expected_hash in design['source_hashes'].items():
        _require(sha(directory/'sources'/name) == expected_hash, 'Archived source mismatch: '+name)
        if live:
            _require(sha(ROOT/name) == expected_hash, 'Live source changed after freeze: '+name)
    if design['bank'] == 'evaluation':
        proof = design.get('development_proof')
        _require(isinstance(proof, dict), 'Evaluation lacks development proof')
        for name in ('design', 'gate', 'completion'):
            _require(sha(directory/'development-proof'/f'{name}.json') == proof[name+'_sha256'],
                     'Development proof hash differs: '+name)
        _require(json.loads((directory/'development-proof'/'gate.json').read_text())['passed'],
                 'Development gate did not pass')
    return design


def _packets(completed, noise, case, design, *, path_prefix=''):
    result = {}
    for raw in completed['learning_observations']:
        packet = {key: float(raw[key]) for key in
                  ('stock_before', 'capacity', 'own_infrastructure', 'other_infrastructure')}
        packet.update(event_id=f'{case["arena_id"]}/{path_prefix}{raw["event_id"]}', tick=raw['tick'],
            patch=raw['patch'], phase='before_actions', sensor_sigma=design['sensor_sigma'],
            growth=float(raw['growth']+noise.normal(0, design['sensor_sigma'])))
        result[raw['patch']] = packet
    return result


def _admit(sharing, packets):
    sharing.observe_tick(packets)
    sharing.submit_reports()
    sharing.finish_tick()


def _latest_delivered(sharing_snapshot, focal, tick):
    actor = f'institution:{focal}'
    packet = next(packet for packet in sharing_snapshot['store'].values()
                  if packet['tick'] == tick and packet['patch'] == focal)
    evidence = sharing_snapshot['models'][actor]['evidence']
    _require(any(row['event_id'] == packet['event_id'] for row in evidence),
             'Latest home packet was not admitted to institutional belief')
    _require(any(row['recipient'] == actor and row['event_id'] == packet['event_id']
                 and row['status'] == 'delivered' for row in sharing_snapshot['frames']),
             'Latest packet has no authenticated positive-delay delivery')
    return deepcopy(packet)


def make_probes(case, design):
    rng = np.random.default_rng(stable_seed(VERSION, case['arena_id'], 'heldout-probes'))
    law, rows = case['world_parameters'], []
    for index in range(design['n_probes']):
        gap = 30. if index % 2 == 0 else float((0, 2, 6)[(index//2) % 3])
        query = {'stock_before': 30.-gap, 'capacity': 30.,
                 'own_infrastructure': float(rng.uniform(0, 2)),
                 'other_infrastructure': float(rng.uniform(0, 2))}
        growth = min(gap, law['r']*rng.uniform(.85, 1.15)
                     + law['b']*query['own_infrastructure']+law['g']*query['other_infrastructure'])
        rows.append({'probe_id': index, 'group': 'uncapped' if index % 2 == 0 else 'capacity',
                     'query': query, 'target': float(growth+rng.normal(0, design['sensor_sigma']))})
    return rows


def score_model(snapshot, probes, case, focal, design):
    model = RenewalSMC.from_snapshot(snapshot)
    before = model.snapshot()
    rows = []
    for probe in probes:
        samples = model.predict(probe['query'], n_samples=design['prediction_samples'],
            seed=stable_seed(VERSION, case['arena_id'], focal, probe['probe_id'], 'heldout-forecast'))
        rows.append({'probe_id': probe['probe_id'], 'group': probe['group'],
                     'crps': float(empirical_crps(samples, probe['target']))})
    _require(model.snapshot() == before, 'Held-out scoring mutated its belief')
    return rows


def _protected(world, sharing, noise):
    return {'world': digest(world.snapshot()), 'sharing': digest(sharing.snapshot()),
            'sensor_rng': digest(noise.bit_generator.state)}


def _probe_overrides(focal, schedule, offset):
    overrides = {society: {'tax_rate': 0., 'public_fraction': 0., 'reserve_fraction': 0.,
                          'defense_fraction': 0.} for society in range(3)}
    if schedule != 'redistribute':
        weights = experimentation.SCHEDULES[schedule]
        remaining = 1.-sum(weights[:offset])
        fraction = weights[offset]/remaining if remaining > 0 else 0.
        reserve = 1.-fraction if remaining > 0 else 0.
        overrides[focal].update(public_fraction=fraction, reserve_fraction=reserve)
    return overrides


def probe_path(checkpoint, focal, schedule, case, design):
    """Run one protected physical experiment and commit its downstream forecasts."""
    _require(schedule in SCHEDULES, 'Unknown physical experiment schedule')
    original = digest(checkpoint)
    world = StepwiseEcology.from_snapshot(checkpoint['world'])
    sharing = SharingRuntime.from_snapshot(checkpoint['sharing'])
    noise = np.random.default_rng()
    noise.bit_generator.state = deepcopy(checkpoint['sensor_rng'])
    before_summary = sharing.summary()
    pre_model = deepcopy(checkpoint['sharing']['models'][f'institution:{focal}'])
    escrow = checkpoint['world']['state']['_institution_observations'][focal]['treasury']
    records = []
    for offset in range(design['probe_ticks']):
        tick = design['warmup_ticks']+offset
        if offset:
            sharing.start_tick(tick)
            institutions = world.begin_tick()
        else:
            institutions = deepcopy(checkpoint['world']['state']['_institution_observations'])
        world.set_institution_decisions(_probe_overrides(focal, schedule, offset))
        completed = world.finish_tick()
        packets = _packets(completed, noise, case, design,
                           path_prefix=f'probe-s{focal}-{schedule}/')
        _admit(sharing, packets)
        receipt = next(row for row in completed['local_observations']['institution_receipts']
                       if row['society_id'] == focal)
        records.append({'tick': tick, 'institution_observation': institutions[focal],
            'institution_receipt': receipt,
            'member_receipts': [row for row in completed['local_observations']['member_receipts']
                                if row['society_id'] == focal],
            'society_metrics': next(row for row in completed['timeseries'] if row['society'] == focal),
            'other_society_metrics': [row for row in completed['timeseries'] if row['society'] != focal],
            'packets': list(packets.values())})
    decision_tick = design['warmup_ticks']+design['probe_ticks']
    sharing.start_tick(decision_tick)
    institutions = world.begin_tick()
    after_state = sharing.snapshot()
    after_summary = sharing.summary()
    last = _latest_delivered(after_state, focal, decision_tick-1)
    obs = decision.observation(institutions[focal], last,
                               consumption_need=design['config']['consumption_need'])
    post_model = deepcopy(after_state['models'][f'institution:{focal}'])
    post_checkpoint = {'world': world.snapshot(), 'sharing': after_state,
                       'sensor_rng': deepcopy(noise.bit_generator.state)}
    forecasts = []
    for belief in BELIEFS:
        coefficient_seed = stable_seed(VERSION, case['arena_id'], focal, 'allocation-coefficients')
        forecast_seed = stable_seed(VERSION, case['arena_id'], focal, 'allocation-forecast')
        draws = (np.tile([case['world_parameters'][key] for key in base.PARAMETERS],
                         (design['planner_samples'], 1)).tolist() if belief == 'known' else
                 sample_coefficients(pre_model if belief == 'frozen' else post_model,
                                     design['planner_samples'], coefficient_seed))
        forecasts.append({'focal': focal, 'belief': belief,
            'coefficient_seed': coefficient_seed, 'forecast_seed': forecast_seed,
            'coefficient_draws': draws, **base._forecast(obs, draws, forecast_seed, design)})
    n = design['config']['members_per_society']
    member_receipts = [row for record in records for row in record['member_receipts']]
    own_before = before_summary['per_society'][str(focal)]
    own_after = after_summary['per_society'][str(focal)]
    metrics = {
        'arena_id': case['arena_id'], 'focal': focal, 'schedule': schedule,
        'cost_matched': int(schedule != 'redistribute'), 'escrow': escrow,
        'actual_experiment_investment': sum(row['institution_receipt']['investment'] for row in records),
        'probe_consumption_per_member': sum(row['society_metrics']['consumption'] for row in records)/n,
        'probe_shortfall_per_member': sum(row['society_metrics']['shortfall'] for row in records)/n,
        'probe_harvest_per_member': sum(row['society_metrics']['harvest'] for row in records)/n,
        'probe_redistribution_per_member': sum(row['institution_receipt']['redistribution'] for row in records)/n,
        'probe_welfare': float(np.mean([row['society_metrics']['welfare'] for row in records])),
        'probe_effort_cost': sum(row['cost'] for row in member_receipts),
        'probe_external_harm': sum(row['society_metrics']['external_harm'] for row in records),
        'probe_other_consumption_per_member': sum(row['consumption'] for record in records
                                                  for row in record['other_society_metrics'])/(2*n),
        'own_unique_events_added': len(post_model['evidence'])-len(pre_model['evidence']),
        'sent_bytes': own_after['sent_bytes']-own_before['sent_bytes'],
        'delivered_bytes': own_after['delivered_bytes']-own_before['delivered_bytes'],
        'all_sent_bytes': after_summary['sent_bytes']-before_summary['sent_bytes'],
        'all_delivered_bytes': after_summary['delivered_bytes']-before_summary['delivered_bytes'],
        'failed_updates': after_summary['failed_updates']-before_summary['failed_updates'],
    }
    expected_spend = escrow if schedule != 'redistribute' else 0.
    _require(abs(metrics['actual_experiment_investment']-expected_spend) <= 1e-12*max(1., escrow),
             'Experiment did not spend its exact committed escrow')
    _require(abs(records[-1]['institution_receipt']['treasury_after']) <= 1e-12,
             'Experiment left unspent escrow')
    _require(metrics['own_unique_events_added'] == design['probe_ticks'],
             'Probe did not deliver every planned home event')
    for offset, record in enumerate(records):
        receipt = record['institution_receipt']
        expected = 0. if schedule == 'redistribute' else escrow*experimentation.SCHEDULES[schedule][offset]
        _require(abs(receipt['investment']-expected) <= 1e-12*max(1., escrow),
                 'Actual experiment tranches differ from the committed schedule')
        _require(receipt['tax'] == receipt['contribution'] == receipt['aid_received'] == 0.,
                 'Probe budget included an uncommitted incoming transfer')
    _require(digest(checkpoint) == original, 'Probe path changed its common checkpoint')
    return {'focal': focal, 'schedule': schedule, 'cost_matched': schedule != 'redistribute',
            'escrow': escrow, 'initial_checkpoint_sha256': original, 'probe_records': records,
            'checkpoint': post_checkpoint, 'legal_observation': obs, 'pre_model': pre_model,
            'post_model': post_model, 'forecasts': forecasts,
            'forecast_commitment_sha256': digest(forecasts),
            'metrics': metrics, 'sharing_before': before_summary, 'sharing_after': after_summary}


def branch_outcomes(world_snapshot, focal, action, design):
    allocation_design = {**design, 'warmup_ticks': design['warmup_ticks']+design['probe_ticks']}
    return base.branch_outcomes(world_snapshot, focal, action, allocation_design)


def _path_scores(path, case, design):
    forecasts = [{**row, 'condition': row['belief']} for row in path['forecasts']]
    rows = base.score_forecasts(case['arena_id'], forecasts, path['branches'], design)
    result = []
    for row in rows:
        belief = row.pop('condition')
        row.update(schedule=path['schedule'], belief=belief)
        metrics = path['metrics']
        if row['status'] == 'ok':
            row.update(total_utility=row['utility']+metrics['probe_consumption_per_member'],
                total_consumption_per_member=row['consumption_per_member']+metrics['probe_consumption_per_member'],
                total_shortfall_per_member=row['shortfall_per_member']+metrics['probe_shortfall_per_member'],
                total_external_harm=row['external_harm']+metrics['probe_external_harm'],
                other_society_total_utility=row['other_society_utility']+metrics['probe_other_consumption_per_member'])
        else:
            row.update({name: None for name in ('total_utility', 'total_consumption_per_member',
                'total_shortfall_per_member', 'total_external_harm', 'other_society_total_utility')})
        for name in DECISION_METRICS:
            if name in metrics:
                row[name] = metrics[name]
        result.append(row)
    return result


def _policy_scores(paths, selections, case):
    rows = []
    for focal in range(3):
        for strategy in (*STRATEGIES, 'redistribute'):
            selection = (next(row for row in selections if row['focal'] == focal
                              and row['strategy'] == strategy) if strategy != 'redistribute' else
                         {'status': 'ok', 'schedule': 'redistribute'})
            if selection['status'] == 'ok':
                path = next(row for row in paths if row['focal'] == focal
                            and row['schedule'] == selection['schedule'])
                rows.extend({**row, 'strategy': strategy} for row in path['scores'])
            else:
                for belief in BELIEFS:
                    rows.append({'arena_id': case['arena_id'], 'focal': focal, 'strategy': strategy,
                        'schedule': None, 'belief': belief, 'status': 'failed', 'action': None,
                        **{name: None for name in DECISION_METRICS}})
    return rows


def _contrasts(scores, case):
    rows = []
    for focal in range(3):
        selected = {(row['strategy'], row['belief']): row for row in scores if row['focal'] == focal}
        for comparator in ('random', 'fixed', 'redistribute'):
            rows_used = [selected[strategy, belief] for strategy in ('active', comparator)
                         for belief in ('updated', 'frozen')]
            row = {'arena_id': case['arena_id'], 'focal': focal, 'contrast': 'active_minus_'+comparator,
                   'status': 'ok' if all(item['status'] == 'ok' for item in rows_used) else 'failed'}
            if row['status'] != 'ok':
                row.update({key: None for key in CONTRAST_METRICS})
            else:
                au, af = selected['active', 'updated'], selected['active', 'frozen']
                cu, cf = selected[comparator, 'updated'], selected[comparator, 'frozen']
                update = (au['utility']-af['utility'])-(cu['utility']-cf['utility'])
                total = au['total_utility']-cu['total_utility']
                material = af['total_utility']-cf['total_utility']
                residual = total-material-update
                _require(abs(residual) < 1e-10, 'Utility decomposition double-counted a cost or intermediate wealth')
                row.update(update_value_difference=update, total_utility_difference=total,
                    frozen_total_utility_difference=material, decomposition_residual=residual,
                    crps_difference=au['post_crps_uncapped']-cu['post_crps_uncapped'],
                    experiment_investment_difference=au['actual_experiment_investment']-cu['actual_experiment_investment'])
            rows.append(row)
    return rows


def evaluate_case(case, design):
    _require(design['probe_ticks'] == experimentation.PROBE_TICKS, 'Selector and physical probe horizons differ')
    _require(design['config']['ticks'] == design['warmup_ticks']+design['probe_ticks']+design['horizon'],
             'Physical episode does not match warmup, probe and continuation windows')
    policy = CandidateProgram(f'ROLE_ROTATION = {case["role_rotation"]}\n'
                              f'WARMUP_TICKS = {design["warmup_ticks"]}\n\n'+base.POLICY)
    world = StepwiseEcology([policy]*3, config=design['config'], seed=case['environment_seed'],
        world_parameters=case['world_parameters'], observation_mode=design['observation_mode'])
    sharing = SharingRuntime(design['sharing_condition'], arena_id=case['arena_id'],
        seed=stable_seed(VERSION, case['arena_id'], 'learners'),
        learner_kwargs={'prior': design['prior'], 'sensor_sigma': design['sensor_sigma'], **design['learner_settings']})
    noise = np.random.default_rng(stable_seed(VERSION, case['arena_id'], 'sensors'))
    warmup_packets = []
    for tick in range(design['warmup_ticks']):
        sharing.start_tick(tick)
        override = ({society: {'public_fraction': 0., 'reserve_fraction': 1.}
                     for society in range(3)} if tick == design['warmup_ticks']-1 else None)
        completed = world.step(institution_decisions=override)
        packets = _packets(completed, noise, case, design)
        warmup_packets.extend(packets.values())
        _admit(sharing, packets)
    sharing.start_tick(design['warmup_ticks'])
    institutions = world.begin_tick()
    state = sharing.snapshot()
    models = {str(focal): deepcopy(state['models'][f'institution:{focal}']) for focal in range(3)}
    observations = {str(focal): decision.observation(institutions[focal],
                    _latest_delivered(state, focal, design['warmup_ticks']-1),
                    consumption_need=design['config']['consumption_need']) for focal in range(3)}
    checkpoint = {'world': world.snapshot(), 'sharing': state, 'sensor_rng': deepcopy(noise.bit_generator.state)}
    protected_before = _protected(world, sharing, noise)
    global_before = digest(base._numpy_global_state())
    selections, selector_draws = [], {}
    for focal in range(3):
        coefficient_seed = stable_seed(VERSION, case['arena_id'], focal, 'selector-coefficients')
        draws = sample_coefficients(models[str(focal)], design['selector_samples'], coefficient_seed)
        selector_draws[str(focal)] = {'seed': coefficient_seed, 'draws': draws}
        for strategy in STRATEGIES:
            selection_seed = stable_seed(VERSION, case['arena_id'], focal, strategy, 'experiment-selection')
            try:
                result = experimentation.select_experiment(observations[str(focal)], draws,
                            strategy=strategy, seed=selection_seed)
                canonical(result)
                _require(result['schedule'] in experimentation.SCHEDULES, 'Selector chose an unavailable schedule')
                selections.append({'focal': focal, 'status': 'ok', 'selection_seed': selection_seed, **result})
            except Exception as exc:
                selections.append({'focal': focal, 'strategy': strategy, 'status': 'failed',
                    'schedule': None, 'selection_seed': selection_seed,
                    'error': f'{type(exc).__name__}: {exc}'})
    selection_commitment = digest({'selections': selections, 'draws': selector_draws,
                                   'observations': observations})
    _require(_protected(world, sharing, noise) == protected_before, 'Selection mutated protected state')
    probes = make_probes(case, design)
    pre_scores = {str(focal): score_model(models[str(focal)], probes, case, focal, design) for focal in range(3)}
    paths = []
    # All experiment selections are already committed; complete all downstream
    # forecasts before evaluating any downstream allocation branch.
    for focal in range(3):
        for schedule in SCHEDULES:
            path = probe_path(checkpoint, focal, schedule, case, design)
            path['pre_scores'] = deepcopy(pre_scores[str(focal)])
            path['post_scores'] = score_model(path['post_model'], probes, case, focal, design)
            for suffix, group in (('uncapped', 'uncapped'), ('all', None)):
                for phase in ('pre', 'post'):
                    chosen = [row['crps'] for row in path[phase+'_scores'] if group is None or row['group'] == group]
                    path['metrics'][phase+'_crps_'+suffix] = float(np.mean(chosen))
                path['metrics']['crps_change_'+suffix] = (path['metrics']['post_crps_'+suffix]
                                                          - path['metrics']['pre_crps_'+suffix])
            paths.append(path)
    for focal in range(3):
        part = [path for path in paths if path['focal'] == focal]
        for name in ('sent_bytes', 'delivered_bytes', 'all_sent_bytes', 'all_delivered_bytes', 'own_unique_events_added'):
            _require(len({path['metrics'][name] for path in part}) == 1, 'Path communication opportunities differ: '+name)
        costed = [path for path in part if path['cost_matched']]
        _require(all(abs(path['metrics']['actual_experiment_investment']-observations[str(focal)]['treasury']) < 1e-10
                     for path in costed), 'Selected costed schedules do not share the same escrow budget')
    for path in paths:
        before = digest(path['checkpoint'])
        path['branches'] = [{'arena_id': case['arena_id'], **branch_outcomes(path['checkpoint']['world'],
                             path['focal'], action, design)} for action in design['menu']]
        _require(before == digest(path['checkpoint']), 'Downstream branch changed probe path checkpoint')
        _require(digest(path['forecasts']) == path['forecast_commitment_sha256'], 'Downstream branch changed forecasts')
        path['scores'] = _path_scores(path, case, design)
    scores = _policy_scores(paths, selections, case)
    contrasts = _contrasts(scores, case)
    protected_after = _protected(world, sharing, noise)
    _require(protected_before == protected_after, 'Protected experiment evaluation changed the live checkpoint')
    _require(global_before == digest(base._numpy_global_state()), 'Experiment changed global NumPy RNG')
    _require(selection_commitment == digest({'selections': selections, 'draws': selector_draws,
                                             'observations': observations}), 'Experiment selections changed after evaluation')
    return {'study': VERSION, 'arena_id': case['arena_id'], 'case': deepcopy(case),
        'warmup': {'packets': warmup_packets, 'institution_models': models, 'sharing_summary': sharing.summary()},
        'checkpoint': checkpoint, 'legal_observations': observations,
        'selector_draws': selector_draws, 'selections': selections,
        'selector_commitment_sha256': selection_commitment, 'probes': probes, 'paths': paths,
        'scores': scores, 'contrasts': contrasts,
        'protected_state_before': protected_before, 'protected_state_after': protected_after,
        'numpy_global_rng_unchanged': True}


def record_invariants(record, design):
    """Recheck saved phase, resource and matched-report facts without trusting a flag."""
    if isinstance(record, _ProjectedRecord):
        return deepcopy(record.invariant_checks)
    decision_tick = design['warmup_ticks']+design['probe_ticks']
    checks = {
        'protected_state': record['protected_state_before'] == record['protected_state_after'],
        'selector_commitment': record['selector_commitment_sha256'] == digest({
            'selections': record['selections'], 'draws': record['selector_draws'],
            'observations': record['legal_observations']}),
        'complete_path_grid': len(record['paths']) == 12 and {
            (row['focal'], row['schedule']) for row in record['paths']}
            == {(focal, schedule) for focal in range(3) for schedule in SCHEDULES},
        'resource_contract': True, 'report_timing': True, 'communication_match': True,
        'downstream_commitments': True,
    }
    for path in record['paths']:
        focal, schedule = path['focal'], path['schedule']
        escrow = record['legal_observations'][str(focal)]['treasury']
        rows = path['probe_records']
        receipts = [row['institution_receipt'] for row in rows]
        expected = ([0.]*design['probe_ticks'] if schedule == 'redistribute'
                    else [escrow*weight for weight in experimentation.SCHEDULES[schedule]])
        spending = sum(row['investment'] for row in receipts)
        checks['resource_contract'] &= (len(rows) == design['probe_ticks']
            and [row['tick'] for row in rows] == list(range(design['warmup_ticks'], decision_tick))
            and all(abs(row['investment']-amount) <= 1e-12*max(1., escrow)
                    for row, amount in zip(receipts, expected))
            and abs(spending-path['metrics']['actual_experiment_investment']) <= 1e-12
            and abs(receipts[-1]['treasury_after']) <= 1e-12
            and all(row['tax'] == row['contribution'] == row['aid_received']
                    == row['defense_expenditure'] == 0. for row in receipts))
        packet = path['legal_observation']['last_growth']
        checks['report_timing'] &= (path['legal_observation']['tick'] == decision_tick
            and packet['tick'] == decision_tick-1 and packet['patch'] == focal
            and len(path['post_model']['evidence'])-len(path['pre_model']['evidence']) == design['probe_ticks']
            and any(row['event_id'] == packet['event_id'] and row['recipient'] == f'institution:{focal}'
                    and row['status'] == 'delivered' and row['delivery_tick'] == decision_tick
                    for row in path['checkpoint']['sharing']['frames']))
        checks['downstream_commitments'] &= digest(path['forecasts']) == path['forecast_commitment_sha256']
    for focal in range(3):
        selected = [path for path in record['paths'] if path['focal'] == focal]
        for name in ('sent_bytes', 'delivered_bytes', 'all_sent_bytes', 'all_delivered_bytes',
                     'own_unique_events_added'):
            checks['communication_match'] &= len({path['metrics'][name] for path in selected}) == 1
    return {key: bool(value) for key, value in checks.items()}


def project_record(record, design):
    """Derive full-case checks, then retain only fields needed by scalar outputs."""
    _require(not isinstance(record, _ProjectedRecord), 'Projection requires a full case record')
    checks = record_invariants(record, design)
    selections = []
    for selected in record['selections']:
        row = {key: deepcopy(value) for key, value in selected.items()
               if key in ('focal', 'strategy', 'status', 'schedule', 'error')}
        row['scores'] = [{key: item[key] for key in ('schedule', 'score')}
                         for item in selected.get('scores', [])]
        selections.append(row)
    paths = []
    for path in record['paths']:
        row = {key: deepcopy(path[key]) for key in
               ('focal', 'schedule', 'cost_matched', 'metrics', 'scores', 'branches')}
        row['forecasts'] = [{key: deepcopy(value) for key, value in forecast.items()
                             if key in ('focal', 'belief', 'status', 'action', 'error')}
                            for forecast in path['forecasts']]
        paths.append(row)
    data = {key: deepcopy(record[key]) for key in
            ('arena_id', 'legal_observations', 'scores', 'contrasts',
             'protected_state_before', 'protected_state_after')}
    data.update(selections=selections, paths=paths,
                warmup={'sharing_summary': deepcopy(record['warmup']['sharing_summary'])})
    return _ProjectedRecord(data, checks)


def gate_summary(records, design):
    states, changes = [], []
    failures = 0
    for record in records:
        failures += sum(row['status'] != 'ok' for row in record['selections'])
        failures += record['warmup']['sharing_summary']['failed_updates']
        for selection in record['selections']:
            if selection['strategy'] != 'active':
                continue
            values = {row['schedule']: row['score'] for row in selection.get('scores', [])}
            choice = selection['schedule']
            states.append({'arena_id': record['arena_id'], 'focal': selection['focal'],
                'active_schedule': choice, 'status': selection['status'],
                'escrow': record['legal_observations'][str(selection['focal'])]['treasury'],
                'proxy_minus_split': values[choice]-values['split'] if choice in values else None})
        for path in record['paths']:
            failures += path['metrics']['failed_updates']
            failures += sum(row['status'] != 'ok' for row in path['forecasts'])
            pair = {row['belief']: row for row in path['forecasts']}
            valid = pair['updated']['status'] == pair['frozen']['status'] == 'ok'
            if valid and pair['updated']['action'] != pair['frozen']['action']:
                changes.append({'arena_id': record['arena_id'], 'focal': path['focal'],
                                'schedule': path['schedule'], 'cost_matched': path['cost_matched'],
                                'updated_action': pair['updated']['action'], 'frozen_action': pair['frozen']['action']})
    rules = design['gate']
    active_names = {row['active_schedule'] for row in states if row['status'] == 'ok'}
    advantages = sum(row['status'] == 'ok' and row['active_schedule'] != 'split'
                     and row['proxy_minus_split'] > rules['proxy_tolerance'] for row in states)
    costed_changes = sum(row['cost_matched'] for row in changes)
    checks = {
        'all_positive_escrow': bool(states) and all(row['escrow'] > 0 for row in states),
        'all_invariants_valid': all(all(record_invariants(record, design).values()) for record in records),
        'all_selections_forecasts_updates_valid': failures == 0,
        'multiple_active_schedules': len(active_names) >= rules['minimum_distinct_active_schedules'],
        'nonfixed_proxy_advantages': advantages >= rules['minimum_nonfixed_advantages'],
        'costed_update_action_changes': costed_changes >= rules['minimum_costed_action_changes'],
    }
    return {'study': VERSION, 'bank': 'development', 'passed': all(checks.values()), 'checks': checks,
            'n_arenas': len(records), 'n_states': len(states), 'rules': rules,
            'counts': {'distinct_active_schedules': len(active_names), 'nonfixed_proxy_advantages': advantages,
                       'costed_update_action_changes': costed_changes, 'all_update_action_changes': len(changes)},
            'failed_operations': failures, 'states': states, 'action_changes': changes}


def _tables(records):
    selections, acquisitions, paths, decisions, branches, scores, contrasts = [], [], [], [], [], [], []
    for record in records:
        arena = record['arena_id']
        for selected in record['selections']:
            candidate = {row['schedule']: row['score'] for row in selected.get('scores', [])}
            name = selected['schedule']
            selections.append({'arena_id': arena, 'focal': selected['focal'],
                'strategy': selected['strategy'], 'status': selected['status'], 'schedule': name,
                'escrow': record['legal_observations'][str(selected['focal'])]['treasury'],
                'proxy_score': candidate.get(name),
                'proxy_minus_split': candidate[name]-candidate['split'] if name in candidate else None})
            if selected['strategy'] == 'active':
                acquisitions.extend({'arena_id': arena, 'focal': selected['focal'],
                    'schedule': schedule, 'status': selected['status'], 'proxy_score': candidate.get(schedule)}
                    for schedule in experimentation.SCHEDULES)
        for path in record['paths']:
            paths.append(path['metrics'])
            decisions.extend(path['scores'])
            branches.extend({**row, 'schedule': path['schedule']} for row in path['branches'])
        scores.extend(record['scores'])
        contrasts.extend(record['contrasts'])
    return {'selections': selections, 'acquisition': acquisitions, 'paths': paths,
            'decisions': decisions, 'branches': branches, 'scores': scores, 'contrasts': contrasts}


def summarize(records, design):
    _require(len(records) == len(design['cases']) and {row['arena_id'] for row in records}
             == {row['arena_id'] for row in design['cases']}, 'Arena coverage differs')
    for record in records:
        _require(len(record['selections']) == 9 and {
            (row['focal'], row['strategy']) for row in record['selections']}
            == {(focal, strategy) for focal in range(3) for strategy in STRATEGIES},
            'Experiment selection grid is incomplete or duplicated')
        for path in record['paths']:
            _require(len(path['branches']) == len(design['menu']) and
                {row['public_fraction'] for row in path['branches']} == set(design['menu'])
                and all(row['focal'] == path['focal'] for row in path['branches']),
                'Physical allocation branch grid is incomplete or duplicated')
            for field in ('forecasts', 'scores'):
                _require(len(path[field]) == len(BELIEFS) and
                    {row['belief'] for row in path[field]} == set(BELIEFS)
                    and all(row['focal'] == path['focal'] for row in path[field]),
                    'Physical path belief grid is incomplete or duplicated: '+field)
    tables = _tables(records)
    expected_scores = {(case['arena_id'], focal, strategy, belief) for case in design['cases']
                       for focal in range(3) for strategy in (*STRATEGIES, 'redistribute') for belief in BELIEFS}
    _require(len(tables['scores']) == len(expected_scores) and
        {(r['arena_id'], r['focal'], r['strategy'], r['belief']) for r in tables['scores']} == expected_scores,
        'Policy decision grid is incomplete or duplicated')
    expected_paths = {(case['arena_id'], focal, schedule) for case in design['cases']
                      for focal in range(3) for schedule in SCHEDULES}
    _require(len(tables['paths']) == len(expected_paths) and
        {(r['arena_id'], r['focal'], r['schedule']) for r in tables['paths']} == expected_paths,
        'Physical experiment grid is incomplete or duplicated')
    arenas = []
    conditions = []
    for strategy in (*STRATEGIES, 'redistribute'):
        for belief in BELIEFS:
            by_arena = []
            for case in design['cases']:
                rows = [row for row in tables['scores'] if row['arena_id'] == case['arena_id']
                        and row['strategy'] == strategy and row['belief'] == belief]
                valid = all(row['status'] == 'ok' for row in rows)
                aggregate = {'arena_id': case['arena_id'], 'strategy': strategy, 'belief': belief,
                    'status': 'ok' if valid else 'incomplete',
                    **{key: float(np.mean([row[key] for row in rows])) if valid else None for key in DECISION_METRICS}}
                arenas.append(aggregate)
                by_arena.append(aggregate)
            raw = [row for row in tables['scores'] if row['strategy'] == strategy and row['belief'] == belief]
            conditions.append({'strategy': strategy, 'belief': belief,
                'failed_plans': sum(row['status'] != 'ok' for row in raw),
                'metrics': {key: base.bootstrap([row[key] for row in by_arena], design) for key in DECISION_METRICS}})
    paired = []
    for comparator in ('random', 'fixed', 'redistribute'):
        name = 'active_minus_'+comparator
        values = {key: [] for key in CONTRAST_METRICS}
        for case in design['cases']:
            rows = [row for row in tables['contrasts'] if row['arena_id'] == case['arena_id'] and row['contrast'] == name]
            _require(len(rows) == 3 and {row['focal'] for row in rows} == set(range(3)), 'Contrast focal grid differs')
            for key in CONTRAST_METRICS:
                values[key].append(float(np.mean([row[key] for row in rows]))
                                   if all(row['status'] == 'ok' for row in rows) else None)
        paired.append({'contrast': name,
                       'metrics': {key: base.bootstrap(data, design) for key, data in values.items()}})
    tables['arenas'] = arenas
    return {'study': VERSION, 'bank': design['bank'], 'n_arenas': len(records),
        'n_focal_states': 3*len(records), 'n_probe_paths': len(tables['paths']),
        'n_allocation_continuations': len(tables['branches']),
        'n_policy_decisions': len(tables['scores']), 'n_physical_path_forecasts': len(tables['decisions']),
        'model_generation_calls': 0, 'independent_evolutionary_runs': 0,
        'replication_unit': design['replication_unit'], 'conditions': conditions,
        'paired_contrasts': paired, 'primary': paired[0]['metrics']['update_value_difference']}, tables


def _case_path(directory, case):
    return Path(directory)/'cases'/case['arena_id']/'case.json.gz'


def _run_case(task):
    directory, case, design = task
    path = _case_path(directory, case)
    try:
        generated = evaluate_case(case, design)
        if path.exists():
            _require(packed_read(path) == generated, 'Existing experiment case fails semantic resume: '+case['arena_id'])
        else:
            packed_write(path, generated)
    except Exception as exc:
        failure = path.parent/'failure.json'
        failure.parent.mkdir(parents=True, exist_ok=True)
        json_write(failure, {'case': case, 'error': f'{type(exc).__name__}: {exc}',
                            'design_sha256': digest(design)})
        raise
    return case['arena_id']


def _verify_case(task):
    directory, case, design = task
    _require(packed_read(_case_path(directory, case)) == evaluate_case(case, design),
             'Experiment semantic reconstruction differs: '+case['arena_id'])
    return case['arena_id']


def _records(directory, design):
    # Full checkpoints dominate archive size. Retaining all 24 decoded cases
    # simultaneously would require several GiB; scalar projections stay small.
    records = []
    for case in design['cases']:
        full = packed_read(_case_path(directory, case))
        records.append(project_record(full, design))
        del full
    return records


def _assert_no_failed_operations(records, design):
    failures = []
    for record in records:
        failures.extend(row for row in record['selections'] if row['status'] != 'ok')
        failures.extend(row for path in record['paths'] for row in path['forecasts'] if row['status'] != 'ok')
        if record['warmup']['sharing_summary']['failed_updates']:
            failures.append(record['warmup']['sharing_summary'])
        failures.extend(path['metrics'] for path in record['paths'] if path['metrics']['failed_updates'])
    _require(not failures, 'Failed selections, forecasts or learner updates are retained; completion is prohibited')
    _require(all(all(record_invariants(record, design).values()) for record in records),
             'Failed resource, timing or isolation checks are retained; completion is prohibited')


def run(directory, workers=2):
    directory = Path(directory)
    _require(not (directory/'completion.json').exists(), 'Completed studies cannot be overwritten')
    _require(type(workers) is int and workers > 0, 'Worker count must be positive')
    design = check_design(directory)
    start = time.monotonic()
    base._parallel(_run_case, [(str(directory), case, design) for case in design['cases']], workers)
    records = _records(directory, design)
    summary, tables = summarize(records, design)
    for name, rows in tables.items():
        (directory/f'{name}.csv').write_bytes(csv_bytes(rows))
    json_write(directory/'summary.json', summary)
    if design['bank'] == 'development':
        json_write(directory/'gate.json', gate_summary(records, design))
    _assert_no_failed_operations(records, design)
    json_write(directory/'completion.json', {
        'study': VERSION, 'completed_utc': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': time.monotonic()-start,
        'elapsed_scope': 'This run command, including semantic verification of any existing cases',
        **{key: summary[key] for key in ('n_arenas', 'n_focal_states', 'n_probe_paths',
            'n_allocation_continuations', 'n_policy_decisions', 'n_physical_path_forecasts')},
        'model_generation_calls': 0, 'independent_evolutionary_runs': 0,
        'artifact_hashes': base._artifacts(directory)})
    return summary


def verify(directory, workers=2):
    directory = Path(directory)
    design = check_design(directory)
    completion = json.loads((directory/'completion.json').read_text())
    _require(completion['study'] == VERSION and completion['model_generation_calls'] == 0
             and completion['independent_evolutionary_runs'] == 0, 'Completion identity differs')
    _require(completion['artifact_hashes'] == base._artifacts(directory), 'Experiment artifact hashes differ')
    base._parallel(_verify_case, [(str(directory), case, design) for case in design['cases']], workers)
    records = _records(directory, design)
    _assert_no_failed_operations(records, design)
    summary, tables = summarize(records, design)
    for name, rows in tables.items():
        _require((directory/f'{name}.csv').read_bytes() == csv_bytes(rows), 'Experiment table differs: '+name)
    _require(json.loads((directory/'summary.json').read_text()) == summary, 'Experiment summary differs')
    if design['bank'] == 'development':
        _require(json.loads((directory/'gate.json').read_text()) == gate_summary(records, design),
                 'Experiment development gate differs')
    else:
        _require(verify(directory/'development-proof', workers=workers)
                 == design['development_proof']['receipt'], 'Development proof receipt differs')
    for key in ('n_arenas', 'n_focal_states', 'n_probe_paths', 'n_allocation_continuations',
                'n_policy_decisions', 'n_physical_path_forecasts'):
        _require(completion[key] == summary[key], 'Completion count differs: '+key)
    return {'verified': True, 'study': VERSION, 'bank': design['bank'],
            'n_arenas': len(records), 'n_probe_paths': summary['n_probe_paths'],
            'n_allocation_continuations': summary['n_allocation_continuations'],
            'semantic_case_replays': len(records),
            'artifact_hashes_checked': len(completion['artifact_hashes']), 'model_generation_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'verify'))
    parser.add_argument('--output', default='evidence/world-model-experiment-v1')
    parser.add_argument('--development', action='store_true')
    parser.add_argument('--development-gate')
    parser.add_argument('--workers', type=int, default=2)
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
