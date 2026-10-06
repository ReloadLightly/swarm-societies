#!/usr/bin/env python3
"""Audit renewal posterior computation on frozen, independent calibration panels.

Prior-predictive SBC and ecological conditional-likelihood coverage are different
questions. Frozen published learners are compared without changing their code.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

from scripts.run_world_model_study import (PRIOR, POLICY, csv_read, csv_write,
    json_write, query_from, sha, stable_seed)
from swarm_societies.ecology_world_model_v1 import EcologyConfig, WorldParameters, run_episode
from swarm_societies.candidate import CandidateProgram
from swarm_societies.world_model_v1.learner import RenewalSMC
from swarm_societies.world_model_v1.reference import fit_reference, reference_log_likelihood

VERSION = 'world-model-calibration-v1'
PARAMETERS = ('r', 'b', 'g')
METHODS = ('prior', 'published', 'higher_compute', 'reference')
SETTINGS = {'prior': {'n_particles': 1024, 'rejuvenation_steps': 4},
            'published': {'n_particles': 1024, 'rejuvenation_steps': 4},
            'higher_compute': {'n_particles': 4096, 'rejuvenation_steps': 8}}
SOURCE_FILES = ('scripts/run_world_model_calibration.py', 'scripts/run_world_model_study.py',
    'swarm_societies/world_model_v1/reference.py', 'swarm_societies/world_model_v1/learner.py',
    'swarm_societies/world_model_v1/__init__.py', 'swarm_societies/ecology_world_model_v1.py',
    'swarm_societies/ecology_consumption_v2.py', 'swarm_societies/candidate.py',
    'docs/world-model-calibration-protocol.md', 'requirements-world-model-v1.txt')


def prepare(directory, sbc_cases=128, ecology_cases=64, development=False):
    directory = Path(directory)
    if (directory/'design.json').exists():
        raise ValueError('Frozen design already exists; use a new output directory')
    if min(sbc_cases, ecology_cases) < 1:
        raise ValueError('Both cohorts require at least one case')
    bank = 'development' if development else 'evaluation'
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for cohort, count in (('prior_predictive', sbc_cases), ('ecological', ecology_cases)):
        for index in range(count):
            case_id = f'{bank}-{cohort}-{index:03d}'
            rng = np.random.default_rng(stable_seed(VERSION, case_id, 'laws'))
            bounds = PRIOR if cohort == 'prior_predictive' else {'r': (2.4, 6.8), 'b': (.7, 2.7), 'g': (.05, .7)}
            cases.append({'case_id': case_id, 'cohort': cohort, 'index': index,
                          'truth': {p: float(rng.uniform(*bounds[p])) for p in PARAMETERS},
                          'role_rotation': index % 3})
    for name in SOURCE_FILES:
        target = directory/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    design = {'schema_version': 1, 'study': VERSION, 'bank': bank,
        'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'prior': PRIOR, 'sensor_sigma': .05, 'cases': cases, 'methods': list(METHODS),
        'smc_settings': SETTINGS, 'sbc_observations': 128, 'ecology_ticks': 128,
        'sbc_features': 'Independent own/other Uniform(0,2), headroom cycles 30,30,6,0; laws from full prior',
        'ecological_features': 'Frozen fixed policies and full infrastructure audit, pooled three patch histories; conditional likelihood only',
        'reference_settings': {'n_chains': 4, 'warmup': 1000, 'draws': 4000},
        'reference_retry': {'n_chains': 4, 'warmup': 2000, 'draws': 8000},
        'reference_gate': {'max_rhat': 1.01, 'min_bulk_ess': 400, 'min_tail_ess': 400},
        'cdf_quantities': ['r', 'b', 'g', 'log_likelihood'],
        'primary': 'Marginal posterior agreement with qualified independent MCMC references; prior-predictive 90% coverage and CDF diagnostics',
        'agreement': 'Absolute posterior mean gap/reference SD, interval width ratio, endpoint gap/prior width; paired differences on same qualified cases',
        'intervals': 'Wilson 95% binomial coverage intervals; continuous metrics use 2000 case bootstrap draws, seed8307; cases not chains or particles are replication units',
        'pit_band': '95% DKW simultaneous ECDF band for independent prior-predictive cases; diagnostic approximation subject to finite posterior computation',
        'failure_policy': 'All outcomes and failed reference attempts retained. Failed final references excluded only from qualified agreement, with denominator reported; raw coverage/CDF remains visible. Unhandled computation exceptions abort completion; no scheduled cases are silently omitted or replaced.',
        'inference_calls': 0, 'source_hashes': {p: sha(ROOT/p) for p in SOURCE_FILES},
        'software': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__}}
    json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(sha(directory/'design.json')+'\n')
    return design


def check_design(directory, live=False):
    directory = Path(directory)
    if sha(directory/'design.json') != (directory/'design.sha256').read_text().strip():
        raise ValueError('Frozen calibration design checksum mismatch')
    design = json.loads((directory/'design.json').read_text())
    for path, expected in design['source_hashes'].items():
        if sha(directory/'sources'/path) != expected or (live and sha(ROOT/path) != expected):
            raise ValueError('Frozen source mismatch: '+path)
    return design


def generate_data(case, design):
    """Evaluator-owned simulator. Returned legal packets exclude all law truth."""
    case_id, cohort, truth = case['case_id'], case['cohort'], case['truth']
    rng = np.random.default_rng(stable_seed(VERSION, case_id, 'data'))
    packets, audit, saturation = [], {'cohort': cohort}, []
    if cohort == 'prior_predictive':
        for tick in range(design['sbc_observations']):
            own, other = rng.uniform(0, 2, 2)
            gap = (30., 30., 6., 0.)[tick % 4]
            growth = min(gap, truth['r']*rng.uniform(.85, 1.15)+truth['b']*own+truth['g']*other)
            saturation.append(growth == gap)
            packets.append({'event_id': f'{case_id}/{tick}', 'stock_before': 30.-gap,
                            'capacity': 30., 'own_infrastructure': float(own),
                            'other_infrastructure': float(other),
                            'growth': float(growth+rng.normal(0, design['sensor_sigma'])),
                            'sensor_sigma': design['sensor_sigma']})
    elif cohort == 'ecological':
        program = CandidateProgram(f'ROLE_ROTATION = {case["role_rotation"]}\n\n'+POLICY)
        config = EcologyConfig(n_societies=3, members_per_society=4, ticks=design['ecology_ticks'],
                    disturbance_tick=design['ecology_ticks']//2, initial_patch=10., patch_capacity=30.,
                    regeneration=5., enable_disturbance=False)
        result = run_episode([program]*3, config=config,
                    seed=stable_seed(VERSION, case_id, 'ecology'), world_parameters=WorldParameters(**truth),
                    observation_mode='full_observation_control')
        for raw in result['learning_observations']:
            saturation.append(bool(raw['censored']))
            packets.append({**query_from(raw), 'event_id': f'{case_id}/{raw["event_id"]}',
                            'growth': float(raw['growth']+rng.normal(0, design['sensor_sigma'])),
                            'sensor_sigma': design['sensor_sigma']})
        audit.update(ledger_residual=result['ledger']['residual'], material_digest=result['legacy_digest'])
    else:
        raise ValueError('Unknown cohort')
    audit['n_observations'] = len(packets)
    features = np.array([[1., p['own_infrastructure'], p['other_infrastructure']] for p in packets])
    audit.update(feature_rank=int(np.linalg.matrix_rank(features)),
                 feature_condition_number=float(np.linalg.cond(features)),
                 own_other_correlation=float(np.corrcoef(features[:,1:].T)[0,1]),
                 saturated_fraction=float(np.mean(saturation)))
    return packets, audit


def weighted_quantiles(values, weights, probabilities):
    order = np.argsort(values)
    return np.interp(probabilities, np.cumsum(weights[order]), values[order])


def posterior_rows(case, method, particles, weights, log_likelihood, truth_log_likelihood):
    particles, log_likelihood = np.asarray(particles), np.asarray(log_likelihood)
    weights = np.asarray(weights, dtype=float)
    if (particles.ndim != 2 or particles.shape[1] != 3 or weights.shape != (len(particles),)
            or log_likelihood.shape != weights.shape or not np.isfinite(log_likelihood).all()
            or not np.isfinite(truth_log_likelihood) or not np.isfinite(particles).all()
            or not np.isfinite(weights).all() or (weights < 0).any()
            or not np.isclose(weights.sum(), 1., rtol=0, atol=1e-10)):
        raise ValueError('Invalid posterior representation')
    base = {'case_id': case['case_id'], 'cohort': case['cohort'], 'method': method}
    rows, pits = [], []
    for j, p in enumerate(PARAMETERS):
        values = particles[:,j]
        mean = float(np.dot(weights, values))
        sd = float(np.sqrt(np.dot(weights, (values-mean)**2)))
        q05, q95 = weighted_quantiles(values, weights, [.05, .95])
        truth = case['truth'][p]
        cdf = float(np.clip(weights[values < truth].sum()+.5*weights[values == truth].sum(), 0., 1.))
        rows.append({**base, 'parameter': p, 'truth': truth, 'mean': mean, 'sd': sd,
                     'q05': float(q05), 'q95': float(q95), 'width90': float(q95-q05),
                     'covered90': int(q05 <= truth <= q95), 'absolute_error': abs(mean-truth), 'cdf': cdf})
        pits.append({**base, 'quantity': p, 'truth': truth, 'cdf': cdf})
    pits.append({**base, 'quantity': 'log_likelihood', 'truth': truth_log_likelihood,
                 'cdf': float(np.clip(weights[log_likelihood < truth_log_likelihood].sum()
                              +.5*weights[log_likelihood == truth_log_likelihood].sum(), 0., 1.))})
    return rows, pits


def run_case(task):
    directory, case, design = task
    directory = Path(directory)
    case_id = case['case_id']
    packets, audit = generate_data(case, design)
    truth_array = np.array([[case['truth'][p] for p in PARAMETERS]])
    truth_loglik = float(reference_log_likelihood(truth_array, packets, sensor_sigma=design['sensor_sigma'])[0])
    rows, pits, diagnostics, arrays = [], [], [], {}
    for method in METHODS:
        started = time.process_time()
        seed = stable_seed(VERSION, case_id, 'reference' if method == 'reference' else 'smc')
        if method != 'reference':
            model = RenewalSMC(seed=seed, prior=design['prior'], sensor_sigma=design['sensor_sigma'], **design['smc_settings'][method])
            if method != 'prior':
                for packet in packets:
                    model.update(packet)
            particles, weights = model.particles.copy(), model.weights.copy()
            fit_elapsed = time.process_time()-started
            # Evaluate the same full-data test quantity even if an online update failed.
            score_started = time.process_time()
            loglik = reference_log_likelihood(particles, packets, sensor_sigma=design['sensor_sigma'])
            score_elapsed = time.process_time()-score_started
            diag = {'status': 'passed' if not model.diagnostics['failed_updates'] else 'failed',
                    **model.diagnostics, 'weight_ess': model.effective_sample_size,
                    'unique_particles': len(np.unique(particles, axis=0)), 'attempts': 1,
                    'rhat_max': None, 'bulk_ess_min': None, 'tail_ess_min': None}
        else:
            gate = design['reference_gate']
            if gate['min_bulk_ess'] != gate['min_tail_ess']:
                raise ValueError('Reference uses a shared bulk/tail ESS threshold')
            reference_kwargs = dict(prior=design['prior'], sensor_sigma=design['sensor_sigma'],
                rhat_limit=gate['max_rhat'], min_ess=gate['min_bulk_ess'])
            result = fit_reference(packets, seed=seed, **reference_kwargs, **design['reference_settings'])
            attempts = [{'status': result['status'], **result['diagnostics']}]
            if result['status'] != 'passed':
                arrays['reference_attempt1_chains'] = result['draws']
                arrays['reference_attempt1_loglik_chains'] = result['draw_log_likelihood']
                result = fit_reference(packets, seed=stable_seed(VERSION, case_id, 'reference-retry'),
                    **reference_kwargs, **design['reference_retry'])
                attempts.append({'status': result['status'], **result['diagnostics']})
            fit_elapsed = time.process_time()-started
            score_elapsed = 0.  # The retained MCMC scores are already cached by the fitter.
            particles = result['draws'].reshape(-1, 3)
            weights = np.full(len(particles), 1./len(particles))
            loglik = result['draw_log_likelihood'].reshape(-1)
            arrays['reference_chains'] = result['draws']
            arrays['reference_loglik_chains'] = result['draw_log_likelihood']
            gate_diagnostics = result['diagnostics']
            gates = [gate_diagnostics]+([gate_diagnostics['log_likelihood']] if gate_diagnostics['log_likelihood'] else [])
            diag = {'status': result['status'], 'attempts': len(attempts),
                    'attempt_diagnostics': attempts, **gate_diagnostics,
                    'rhat_max': max((r or float('inf')) for d in gates for r in d['rhat']),
                    'bulk_ess_min': min(e for d in gates for e in d['bulk_ess']),
                    'tail_ess_min': min(e for d in gates for e in d['tail_ess'])}
            if not np.isfinite(diag['rhat_max']):
                diag['rhat_max'] = None
        elapsed = time.process_time()-started
        rows_part, pits_part = posterior_rows(case, method, particles, weights, loglik, truth_loglik)
        rows.extend(rows_part); pits.extend(pits_part)
        mean = weights @ particles
        centered = particles-mean
        covariance = (centered.T*weights) @ centered
        sd = np.sqrt(np.diag(covariance))
        varying = np.ptp(particles,axis=0) > 0
        diag['posterior_correlation'] = [[float(covariance[i,j]/(sd[i]*sd[j]))
            if varying[i] and varying[j] and sd[i]*sd[j] > 0 else None for j in range(3)] for i in range(3)]
        diagnostics.append({'case_id': case_id, 'cohort': case['cohort'], 'method': method,
                            'cpu_seconds': elapsed, 'fit_cpu_seconds': fit_elapsed,
                            'score_cpu_seconds': score_elapsed, 'n_observations': len(packets), **diag})
        if method != 'reference':
            arrays[f'{method}_particles'] = particles
            arrays[f'{method}_weights'] = weights
            arrays[f'{method}_log_likelihood'] = loglik
    payload = {'case': case, 'audit': audit, 'observations': packets,
               'parameters': rows, 'cdf': pits, 'diagnostics': diagnostics}
    target = directory/'cases'/case_id
    json_write(target.with_suffix('.json'), payload)
    np.savez_compressed(target.with_suffix('.npz'), **arrays)
    return payload


def bootstrap(values):
    x = np.asarray(values, dtype=float)
    if not len(x):
        return {'mean': None, 'ci95': [None, None], 'n': 0}
    rng = np.random.default_rng(8307)
    means = x[rng.integers(0, len(x), size=(2000, len(x)))].mean(axis=1)
    lo, hi = np.quantile(means, [.025, .975])
    return {'mean': float(x.mean()), 'ci95': [float(lo), float(hi)], 'n': len(x)}


def coverage_interval(values):
    """Wilson binomial interval, including when all scheduled cases cover."""
    x = np.asarray(values, dtype=float)
    if not len(x):
        return {'mean': None, 'ci95': [None, None], 'n': 0}
    n, p, z = len(x), float(x.mean()), 1.959963984540054
    denominator = 1+z*z/n
    center = (p+z*z/(2*n))/denominator
    radius = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return {'mean': p, 'ci95': [max(0.,float(center-radius)),min(1.,float(center+radius))], 'n': n}


def collect(directory, design):
    payloads = [json.loads((Path(directory)/'cases'/f'{c["case_id"]}.json').read_text()) for c in design['cases']]
    rows = [r for p in payloads for r in p['parameters']]
    pits = [r for p in payloads for r in p['cdf']]
    diagnostics = [r for p in payloads for r in p['diagnostics']]
    agreements = []
    for payload in payloads:
        qualified = next(d['status']=='passed' for d in payload['diagnostics'] if d['method']=='reference')
        ref = {r['parameter']:r for r in payload['parameters'] if r['method']=='reference'}
        ref_diag = next(d for d in payload['diagnostics'] if d['method']=='reference')
        for row in payload['parameters']:
            if row['method'] == 'reference':
                continue
            r = ref[row['parameter']]
            agreements.append({'case_id': row['case_id'], 'cohort': row['cohort'], 'method': row['method'],
                'parameter': row['parameter'], 'reference_passed': int(qualified),
                'mean_gap_reference_sd': abs(row['mean']-r['mean'])/max(r['sd'], 1e-12),
                'reference_mean_mcse_sd': (ref_diag['mean_mcse'][PARAMETERS.index(row['parameter'])]/max(r['sd'],1e-12)
                    if ref_diag['mean_mcse'][PARAMETERS.index(row['parameter'])] is not None else None),
                'width_ratio': row['width90']/max(r['width90'], 1e-12),
                'endpoint_gap_prior_width': max(abs(row['q05']-r['q05']),abs(row['q95']-r['q95']))/(PRIOR[row['parameter']][1]-PRIOR[row['parameter']][0])})
    summaries = []
    for cohort in ('prior_predictive','ecological'):
        for method in METHODS:
            for parameter in PARAMETERS:
                selected = [r for r in rows if (r['cohort'],r['method'],r['parameter'])==(cohort,method,parameter)]
                match = [r for r in agreements if (r['cohort'],r['method'],r['parameter'])==(cohort,method,parameter) and r['reference_passed']]
                summaries.append({'cohort':cohort,'method':method,'parameter':parameter,
                    'covered90': coverage_interval([r['covered90'] for r in selected]),
                    **{k:bootstrap([r[k] for r in selected]) for k in ('width90','absolute_error')},
                    **{k:bootstrap([r[k] for r in match]) for k in ('mean_gap_reference_sd','width_ratio','endpoint_gap_prior_width')}})
    contrasts = []
    for cohort in ('prior_predictive','ecological'):
        for parameter in PARAMETERS:
            bymethod = {m:{r['case_id']:r for r in agreements if r['cohort']==cohort and r['parameter']==parameter and r['method']==m and r['reference_passed']} for m in ('published','higher_compute')}
            shared = sorted(set(bymethod['published']) & set(bymethod['higher_compute']))
            contrasts.append({'cohort':cohort,'parameter':parameter,
                **{key:bootstrap([bymethod['higher_compute'][c][key]-bymethod['published'][c][key] for c in shared]) for key in ('mean_gap_reference_sd','endpoint_gap_prior_width')}})
    summary = {'study':VERSION,'cohort_counts':{c:sum(r['cohort']==c for r in design['cases']) for c in ('prior_predictive','ecological')},
               'reference_failures':{c:sum(d['status']!='passed' for d in diagnostics if d['cohort']==c and d['method']=='reference') for c in ('prior_predictive','ecological')},
               'all_case_summaries':summaries, 'paired_higher_minus_published':contrasts,
               'compute_metric':'fit_cpu_seconds (includes reference convergence diagnostics and prescribed retries; excludes separate full-data CDF scoring)',
               'compute':[{ 'cohort':c,'method':m,**bootstrap([d['fit_cpu_seconds'] for d in diagnostics if d['cohort']==c and d['method']==m])} for c in ('prior_predictive','ecological') for m in METHODS],
               'interpretation':['Prior-predictive CDF calibration is distinct from ecological task coverage.',
                 'Reference passes are numerical diagnostics, not proof of exact posterior calculation.',
                 'Ecological likelihood conditions on features; it does not model their latent-outcome-dependent generation.',
                 'Higher compute is a sensitivity comparison, not a changed production default.']}
    return rows,pits,diagnostics,agreements,summary


def run(directory, workers=4):
    directory = Path(directory)
    design = check_design(directory, live=True)
    if (directory/'completion.json').exists():
        raise ValueError('Completed evidence already exists; verify or use a new directory')
    (directory/'cases').mkdir(exist_ok=True)
    started = time.perf_counter()
    tasks = [(str(directory),c,design) for c in design['cases']]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i,payload in enumerate(pool.map(run_case,tasks),1):
            ref = next(d for d in payload['diagnostics'] if d['method']=='reference')
            print(json.dumps({'completed':i,'total':len(tasks),'case_id':payload['case']['case_id'],
                              'reference_status':ref['status'],'seconds':round(time.perf_counter()-started,1)}),flush=True)
    rows,pits,diagnostics,agreements,summary = collect(directory,design)
    for name,data in (('parameters.csv',rows),('cdf.csv',pits),('agreement.csv',agreements)):
        csv_write(directory/name,data)
    json_write(directory/'diagnostics.json',diagnostics)
    json_write(directory/'summary.json',summary)
    files = sorted(p for p in directory.rglob('*') if p.is_file() and p.name!='completion.json')
    json_write(directory/'completion.json',{'study':VERSION,'completed_utc':datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds':time.perf_counter()-started,'workers':workers,'inference_calls':0,
        'artifacts':{str(p.relative_to(directory)):sha(p) for p in files}})
    return summary


def verify(directory):
    directory = Path(directory)
    design = check_design(directory)
    complete = json.loads((directory/'completion.json').read_text())
    case_ids = [case['case_id'] for case in design['cases']]
    if len(case_ids) != len(set(case_ids)) or set(design['methods']) != set(METHODS):
        raise ValueError('Invalid case or method coverage in calibration design')
    required = {'design.json', 'design.sha256', 'parameters.csv', 'cdf.csv',
                'agreement.csv', 'diagnostics.json', 'summary.json'}
    required.update('sources/'+name for name in design['source_hashes'])
    required.update(f'cases/{case_id}.{extension}' for case_id in case_ids for extension in ('json', 'npz'))
    if not required <= set(complete['artifacts']):
        raise ValueError('Completion manifest omits calibration evidence')
    for path,expected in complete['artifacts'].items():
        if sha(directory/path)!=expected:
            raise ValueError('Calibration artifact mismatch: '+path)

    def check_coverage(records, fields, expected, label):
        identities = [tuple(record[field] for field in fields) for record in records]
        if len(identities) != len(set(identities)) or set(identities) != set(expected):
            raise ValueError('Missing, foreign or duplicated calibration '+label)

    def check_export(filename, expected):
        actual = csv_read(directory/filename)
        rendered = [{key: '' if value is None else str(value) for key, value in row.items()} for row in expected]
        if actual != rendered:
            raise ValueError('Exported '+filename+' differs from case primitives')

    def close(actual, expected, label):
        if not np.isfinite(np.asarray(actual, dtype=float)).all() or not np.allclose(actual, expected, rtol=1e-9, atol=1e-10):
            raise ValueError('Calibration numerical reconstruction mismatch: '+label)

    from swarm_societies.world_model_v1.reference import chain_diagnostics
    likelihood_rows = 0
    for case in design['cases']:
        payload = json.loads((directory/'cases'/f'{case["case_id"]}.json').read_text())
        packets,audit = generate_data(case,design)
        if payload['case'] != case or payload['observations'] != packets or payload['audit'] != audit:
            raise ValueError('Frozen data generation mismatch')
        event_ids = [packet['event_id'] for packet in packets]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError('Duplicated calibration environmental evidence')
        expected_n = design['sbc_observations'] if case['cohort'] == 'prior_predictive' else 3*design['ecology_ticks']
        if len(packets) != expected_n:
            raise ValueError('Unexpected calibration observation count')
        allowed_packet_fields = {'event_id', 'stock_before', 'capacity', 'own_infrastructure',
                                 'other_infrastructure', 'growth', 'sensor_sigma'}
        if any(set(packet) != allowed_packet_fields for packet in packets):
            raise ValueError('Illegal learner packet fields')
        check_coverage(payload['parameters'], ('method', 'parameter'),
                       {(method, parameter) for method in METHODS for parameter in PARAMETERS}, 'parameter rows')
        check_coverage(payload['cdf'], ('method', 'quantity'),
                       {(method, quantity) for method in METHODS for quantity in design['cdf_quantities']}, 'CDF rows')
        check_coverage(payload['diagnostics'], ('method',), {(method,) for method in METHODS}, 'diagnostic rows')
        for rows in (payload['parameters'], payload['cdf'], payload['diagnostics']):
            if any(row['case_id'] != case['case_id'] or row['cohort'] != case['cohort'] for row in rows):
                raise ValueError('Foreign case identity in calibration primitives')
        for diag in payload['diagnostics']:
            if diag['n_observations'] != expected_n or not np.isfinite(diag['cpu_seconds']) or diag['cpu_seconds'] < 0:
                raise ValueError('Invalid calibration accounting')
            if any(not np.isfinite(diag[field]) or diag[field] < 0 for field in ('fit_cpu_seconds', 'score_cpu_seconds')):
                raise ValueError('Invalid calibration CPU accounting')
            if diag['fit_cpu_seconds']+diag['score_cpu_seconds'] > diag['cpu_seconds']+1e-8:
                raise ValueError('Calibration CPU components exceed total')
        truth_ll = float(reference_log_likelihood(np.array([[case['truth'][p] for p in PARAMETERS]]),packets,sensor_sigma=design['sensor_sigma'])[0])
        with np.load(directory/'cases'/f'{case["case_id"]}.npz',allow_pickle=False) as arrays:
            for method in METHODS:
                diag = next(row for row in payload['diagnostics'] if row['method'] == method)
                if method=='reference':
                    chains = arrays['reference_chains']
                    if diag['attempts'] not in (1, 2) or len(diag['attempt_diagnostics']) != diag['attempts']:
                        raise ValueError('Invalid reference attempt accounting')
                    if diag['attempts'] == 1 and diag['status'] != 'passed':
                        raise ValueError('Scheduled reference retry is missing')
                    if diag['attempts'] == 2 and diag['attempt_diagnostics'][0]['status'] == 'passed':
                        raise ValueError('Unscheduled reference retry after passing attempt')
                    if diag['attempts'] == 2:
                        first_chains = arrays['reference_attempt1_chains']
                        first_ll = arrays['reference_attempt1_loglik_chains']
                        initial_settings = design['reference_settings']
                        if (first_chains.shape != (initial_settings['n_chains'], initial_settings['draws'], 3)
                                or first_ll.shape != first_chains.shape[:2]):
                            raise ValueError('First reference attempt differs from scheduled budget')
                        first_diag = chain_diagnostics(first_chains, rhat_limit=design['reference_gate']['max_rhat'],
                                                       min_ess=design['reference_gate']['min_bulk_ess'])
                        first_log_diag = (None if np.ptp(first_ll) < 1e-10 else chain_diagnostics(first_ll,
                            rhat_limit=design['reference_gate']['max_rhat'], min_ess=design['reference_gate']['min_tail_ess']))
                        if first_diag['passed'] and (first_log_diag is None or first_log_diag['passed']):
                            raise ValueError('Reference retry lacks a failing initial gate')
                        recorded_first = diag['attempt_diagnostics'][0]
                        for field in ('rhat', 'bulk_ess', 'tail_ess'):
                            if recorded_first[field] != first_diag[field]:
                                raise ValueError('First reference diagnostics differ from retained chains')
                        if recorded_first['log_likelihood'] != first_log_diag:
                            raise ValueError('First reference log-likelihood diagnostics mismatch')
                        close(first_ll, reference_log_likelihood(first_chains, packets,
                              sensor_sigma=design['sensor_sigma']), 'initial reference sample log likelihood')
                        likelihood_rows += first_ll.size
                    settings = design['reference_retry'] if diag['attempts'] == 2 else design['reference_settings']
                    if chains.shape != (settings['n_chains'], settings['draws'], 3):
                        raise ValueError('Reference draws differ from scheduled budget')
                    particles = chains.reshape(-1,3)
                    weights = np.full(len(particles),1./len(particles))
                    ll_chains = arrays['reference_loglik_chains']
                    if ll_chains.shape != chains.shape[:2]:
                        raise ValueError('Reference likelihood/draw shape mismatch')
                    ll = ll_chains.reshape(-1)
                    gate = design['reference_gate']
                    computed = chain_diagnostics(chains, rhat_limit=gate['max_rhat'], min_ess=gate['min_bulk_ess'])
                    log_computed = (None if np.ptp(ll_chains) < 1e-10 else
                                    chain_diagnostics(ll_chains, rhat_limit=gate['max_rhat'], min_ess=gate['min_tail_ess']))
                    passed = computed['passed'] and (log_computed is None or log_computed['passed'])
                    if (diag['status'] == 'passed') != passed or diag['attempt_diagnostics'][-1]['status'] != diag['status']:
                        raise ValueError('Reference qualification differs from retained chains')
                    for field in ('rhat', 'bulk_ess', 'tail_ess'):
                        if diag[field] != computed[field]:
                            raise ValueError('Reference diagnostics differ from retained chains')
                    if diag['log_likelihood'] != log_computed:
                        raise ValueError('Reference log-likelihood diagnostics mismatch')
                else:
                    particles,weights,ll = (arrays[f'{method}_{name}'] for name in ('particles','weights','log_likelihood'))
                    if particles.shape != (design['smc_settings'][method]['n_particles'], 3):
                        raise ValueError('SMC particles differ from scheduled budget')
                    if diag['attempts'] != 1 or (diag['status'] == 'passed') != (diag['failed_updates'] == 0):
                        raise ValueError('Invalid SMC status accounting')
                    expected_accepted = 0 if method == 'prior' else expected_n-diag['failed_updates']
                    if diag['accepted_observations'] != expected_accepted or diag['duplicate_events'] != 0:
                        raise ValueError('Invalid SMC evidence accounting')
                    if method == 'prior':
                        untouched = RenewalSMC(seed=stable_seed(VERSION, case['case_id'], 'smc'),
                            prior=design['prior'], sensor_sigma=design['sensor_sigma'], **design['smc_settings'][method])
                        if not np.array_equal(particles, untouched.particles) or not np.array_equal(weights, untouched.weights):
                            raise ValueError('Frozen prior was updated')
                bounds = np.array([design['prior'][p] for p in PARAMETERS])
                if ((particles < bounds[:, 0]) | (particles > bounds[:, 1])).any():
                    raise ValueError('Posterior values outside frozen prior support')
                rebuilt_ll = reference_log_likelihood(particles, packets, sensor_sigma=design['sensor_sigma'])
                close(ll, rebuilt_ll, 'stored sample log likelihood')
                likelihood_rows += len(particles)
                expected_rows,expected_pits = posterior_rows(case,method,particles,weights,ll,truth_ll)
                if expected_rows != [r for r in payload['parameters'] if r['method']==method] or expected_pits != [r for r in payload['cdf'] if r['method']==method]:
                    raise ValueError('Posterior primitive reconstruction mismatch')
    rows,pits,diagnostics,agreements,summary = collect(directory,design)
    if summary != json.loads((directory/'summary.json').read_text()):
        raise ValueError('Summary reconstruction mismatch')
    if diagnostics != json.loads((directory/'diagnostics.json').read_text()):
        raise ValueError('Exported diagnostics differ from case primitives')
    for filename, primitives in (('parameters.csv', rows), ('cdf.csv', pits), ('agreement.csv', agreements)):
        check_export(filename, primitives)
    return {'verified':True,'cases':len(design['cases']),'posterior_rows':len(rows),
            'cdf_rows':len(pits),'agreement_rows':len(agreements),'sample_likelihoods':likelihood_rows,
            'artifacts':len(complete['artifacts'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','verify'))
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/world-model-calibration-v1')
    parser.add_argument('--sbc-cases',type=int,default=128)
    parser.add_argument('--ecology-cases',type=int,default=64)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--development',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.output,args.sbc_cases,args.ecology_cases,args.development)
        print(json.dumps({'prepared':str(args.output),'cases':len(result['cases'])}))
    elif args.command=='run':
        result=run(args.output,args.workers)
        print(json.dumps({'complete':str(args.output),'reference_failures':result['reference_failures']}))
    else:
        print(json.dumps(verify(args.output),indent=2))


if __name__=='__main__':
    main()
