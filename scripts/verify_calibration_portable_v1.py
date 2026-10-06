#!/usr/bin/env python3
"""Supplemental portable semantic verification of calibration-v1 evidence.

The evidence-verification flow below is copied from the immutable
scripts/run_world_model_calibration.py (SHA-256 pinned in ORIGINAL_SOURCE_HASHES),
with attribution to that repository implementation. The separate copy keeps the
old verifier executable and reviewable. Numerical/data/export routines are
reused only after their source hashes and the archive's source copies match the
original freeze. No runtime code rewriting or monkeypatching is performed.

Only recomputed reference rhat/bulk_ess/tail_ess scalars permit new tolerance.
Likelihood reconstruction retains the original rtol=1e-9, atol=1e-10. Other
values remain exact, including every qualification and retry decision.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

from scripts import run_world_model_calibration as original
from swarm_societies.world_model_v1.reference import chain_diagnostics

VERIFIER_VERSION = 'calibration-portable-verification-v1'
RTOL = ATOL = 1e-12
DIAGNOSTIC_FLOAT_FIELDS = ('rhat', 'bulk_ess', 'tail_ess')
DIAGNOSTIC_EXACT_FIELDS = ('passed', 'rhat_limit', 'min_ess', 'split_chains', 'draws_per_split_chain')
ORIGINAL_SOURCE_HASHES = {
    "docs/world-model-calibration-protocol.md": "5a0cad50c7cb52ce951418aa6d2dd1b01a2e0b6f52a86dd96a66564ce649287a",
    "requirements-world-model-v1.txt": "9a9ebd5cf3256bb8fe44ce6d8cb6e791201f1ff7295e0149f8ef3a8bbfa778cd",
    "scripts/run_world_model_calibration.py": "30cdf91ec084f66cf0320b9c0e701b00aaf1f25daf48a3b434b723d8a09c1a1c",
    "scripts/run_world_model_study.py": "0434d6d512e875dfda87e0218e5230423937dbac825d65aaf4049bb8160c0f88",
    "swarm_societies/candidate.py": "0ff988ac0a8b05ca0919bb67267e6645a232fb49530cfbd51122c6b8d1dfa89b",
    "swarm_societies/ecology_consumption_v2.py": "82c3ffe2e9431541e6e0cfbda6c97bccadfe87518bd3d17ff7661434d84e2344",
    "swarm_societies/ecology_world_model_v1.py": "6b1a84387efd3704efb3c4986cafcb6d9607c344c597e1aa7ec99b084357e8e7",
    "swarm_societies/world_model_v1/__init__.py": "ef887d652d060bab39cc23090c1197907efebbad6e733aa525b443ca25540970",
    "swarm_societies/world_model_v1/learner.py": "0dda816df570d9b813d60a29ad2fbbc2529a29a3cf74b628720b0caa3877bfdc",
    "swarm_societies/world_model_v1/reference.py": "597bb03ec3a720b1a052647fd20fee82f9b3956a852c4f7bd4e6b3d8aee9b831"
}

# These routines and constants are unchanged, source-pinned scientific code.
METHODS, PARAMETERS, VERSION = original.METHODS, original.PARAMETERS, original.VERSION
sha, csv_read = original.sha, original.csv_read
check_design, generate_data, collect = original.check_design, original.generate_data, original.collect
posterior_rows, reference_log_likelihood = original.posterior_rows, original.reference_log_likelihood
RenewalSMC, stable_seed = original.RenewalSMC, original.stable_seed


def _pointer(path, key):
    return path + '/' + str(key).replace('~', '~0').replace('/', '~1')


def assert_exact(recorded, computed, path):
    """JSON equality with types: True, 1 and 1.0 are not interchangeable."""
    if type(recorded) is not type(computed):
        raise ValueError('Exact type mismatch at ' + path)
    if isinstance(recorded, dict):
        if recorded.keys() != computed.keys():
            raise ValueError('Exact field mismatch at ' + path)
        for key in recorded:
            assert_exact(recorded[key], computed[key], _pointer(path, key))
    elif isinstance(recorded, list):
        if len(recorded) != len(computed):
            raise ValueError('Exact shape mismatch at ' + path)
        for index, (left, right) in enumerate(zip(recorded, computed)):
            assert_exact(left, right, _pointer(path, index))
    elif isinstance(recorded, float) and not (math.isfinite(recorded) and math.isfinite(computed)):
        raise ValueError('Nonfinite exact value at ' + path)
    elif recorded != computed:
        raise ValueError('Exact value mismatch at ' + path)


def _finite_json(value, path):
    if isinstance(value, dict):
        for key, item in value.items():
            _finite_json(item, _pointer(path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _finite_json(item, _pointer(path, index))
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Nonfinite archived value at ' + path)


class DiagnosticAudit:
    """Narrow tolerance and an audit trail for every unequal allowed scalar."""
    def __init__(self):
        self.compared_floats = 0
        self.drifts = []

    def compare(self, recorded, computed, path):
        core = (*DIAGNOSTIC_FLOAT_FIELDS, *DIAGNOSTIC_EXACT_FIELDS)
        if not isinstance(recorded, dict) or not isinstance(computed, dict):
            raise ValueError('Diagnostic object required at ' + path)
        if any(key not in recorded or key not in computed for key in core):
            raise ValueError('Missing diagnostic field at ' + path)
        for key in DIAGNOSTIC_EXACT_FIELDS:
            assert_exact(recorded[key], computed[key], _pointer(path, key))
        for key in DIAGNOSTIC_FLOAT_FIELDS:
            left, right = recorded[key], computed[key]
            field_path = _pointer(path, key)
            if type(left) is not list or type(right) is not list or len(left) != len(right):
                raise ValueError('Diagnostic shape mismatch at ' + field_path)
            for index, (a, b) in enumerate(zip(left, right)):
                item_path = _pointer(field_path, index)
                # Null R-hat is the frozen representation of a degenerate failed
                # trace. Preserve it exactly; it never receives tolerance.
                if a is None or b is None:
                    if key != 'rhat':
                        raise ValueError('Null ESS diagnostic at ' + item_path)
                    assert_exact(a, b, item_path)
                    continue
                if type(a) is not float or type(b) is not float:
                    raise ValueError('Diagnostic float type required at ' + item_path)
                if not (math.isfinite(a) and math.isfinite(b)):
                    raise ValueError('Nonfinite diagnostic at ' + item_path)
                self.compared_floats += 1
                delta = abs(a - b)
                allowed = delta <= ATOL + RTOL * abs(b)
                if a != b:
                    self.drifts.append({'pointer': item_path, 'recorded': a, 'recomputed': b,
                        'absolute_error': delta if math.isfinite(delta) else None,
                        'relative_error': delta / abs(b) if b and math.isfinite(delta / abs(b)) else None,
                        'within_tolerance': allowed})
                if not allowed:
                    raise ValueError('Diagnostic numerical mismatch at ' + item_path)
                # Even a tolerated scalar must stay on its original side of
                # the gate, independently of the aggregate passed boolean.
                threshold = computed['rhat_limit'] if key == 'rhat' else computed['min_ess']
                left_pass = a < threshold if key == 'rhat' else a >= threshold
                right_pass = b < threshold if key == 'rhat' else b >= threshold
                if left_pass != right_pass:
                    raise ValueError('Diagnostic qualification boundary discrepancy at ' + item_path)

    def summary(self):
        absolute = [d['absolute_error'] for d in self.drifts if d['absolute_error'] is not None]
        relative = [d['relative_error'] for d in self.drifts if d['relative_error'] is not None]
        return {'compared_float_values': self.compared_floats, 'drift_count': len(self.drifts),
                'max_absolute_error': max(absolute, default=0.),
                'max_relative_error': max(relative, default=0.), 'drifts': self.drifts,
                'relative_error_definition': 'abs(recorded-recomputed)/abs(recomputed); null at zero or overflow'}


def _compare_reference(recorded, computed, log_computed, path, audit, settings, observations):
    qualified = computed['passed'] and (log_computed is None or log_computed['passed'])
    # fit_reference replaces the coefficient-only `passed` flag with the joint
    # coefficient/likelihood qualification. In a retained failed first attempt,
    # coefficients can pass while likelihood mixing alone requires the retry.
    # Keep all coefficient scalars and gate boundaries independently checked.
    audit.compare(recorded, {**computed, 'passed': qualified}, path)
    for field, expected in [('n_chains', settings['n_chains']),
                            ('draws_per_chain', settings['draws']), ('warmup', settings['warmup']),
                            ('unique_observations', observations), ('duplicate_events', 0),
                            ('flat_log_likelihood', log_computed is None)]:
        assert_exact(recorded[field], expected, _pointer(path, field))
    recorded_log = recorded['log_likelihood']
    log_path = _pointer(path, 'log_likelihood')
    if recorded_log is None or log_computed is None:
        assert_exact(recorded_log, log_computed, log_path)
    else:
        assert_exact(sorted(recorded_log), sorted(log_computed), log_path + '/keys')
        audit.compare(recorded_log, log_computed, log_path)
    assert_exact(recorded['status'], 'passed' if qualified else 'failed', _pointer(path, 'status'))


def _check_original_sources(directory, design):
    assert_exact(design['source_hashes'], ORIGINAL_SOURCE_HASHES, '/design/source_hashes')
    for name, expected in ORIGINAL_SOURCE_HASHES.items():
        if sha(ROOT / name) != expected or sha(directory / 'sources' / name) != expected:
            raise ValueError('Pinned original source mismatch: ' + name)


def _positive_int(value, label):
    if type(value) is not int or value < 1:
        raise ValueError('Positive integer required: ' + label)


def _check_design_types(design):
    for key in ('sbc_observations', 'ecology_ticks'):
        _positive_int(design[key], key)
    for settings in (design['reference_settings'], design['reference_retry']):
        for key in ('n_chains', 'draws'):
            _positive_int(settings[key], key)
        if type(settings['warmup']) is not int or settings['warmup'] < 0:
            raise ValueError('Nonnegative integer warmup required')
    if len(design['methods']) != len(set(design['methods'])):
        raise ValueError('Duplicated calibration methods')
    for settings in design['smc_settings'].values():
        _positive_int(settings['n_particles'], 'n_particles')
        if type(settings['rejuvenation_steps']) is not int or settings['rejuvenation_steps'] < 0:
            raise ValueError('Nonnegative integer rejuvenation_steps required')
    for key, value in design['reference_gate'].items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Finite positive diagnostic threshold required: ' + key)
    if design['reference_gate']['min_bulk_ess'] != design['reference_gate']['min_tail_ess']:
        raise ValueError('Reference requires a shared bulk/tail ESS threshold')
    _finite_json(design, '/design')


def _check_count_types(diag, path):
    count_fields = ('n_observations', 'attempts', 'accepted_observations', 'duplicate_events',
                    'failed_updates', 'likelihood_evaluations', 'rejuvenation_accepts',
                    'rejuvenation_proposals', 'resampling_events', 'unique_particles',
                    'draws_per_chain', 'draws_per_split_chain', 'initialization_boundary_fallbacks',
                    'likelihood_candidate_evaluations', 'n_chains', 'split_chains',
                    'unique_observations', 'warmup')
    for key in count_fields:
        if key in diag and (type(diag[key]) is not int or diag[key] < 0):
            raise ValueError('Nonnegative integer count required at ' + _pointer(path, key))
    for key in ('passed', 'flat_log_likelihood'):
        if key in diag and type(diag[key]) is not bool:
            raise ValueError('Exact boolean type required at ' + _pointer(path, key))
    for index, attempt in enumerate(diag.get('attempt_diagnostics', [])):
        _check_count_types(attempt, path + f'/attempt_diagnostics/{index}')


# Adapted copy of the frozen verifier. The case loop, reconstructed likelihoods,
# posterior summaries, denominators and exact exported tables remain intact.

def _verify_evidence(directory, audit):
    directory = Path(directory)
    design = check_design(directory)
    _check_original_sources(directory, design)
    _check_design_types(design)
    complete = json.loads((directory/'completion.json').read_text())
    case_ids = [case['case_id'] for case in design['cases']]
    if len(case_ids) != len(set(case_ids)) or set(design['methods']) != set(METHODS):
        raise ValueError('Invalid case or method coverage in calibration design')
    required = {'design.json', 'design.sha256', 'parameters.csv', 'cdf.csv',
                'agreement.csv', 'diagnostics.json', 'summary.json'}
    required.update('sources/'+name for name in design['source_hashes'])
    required.update(f'cases/{case_id}.{extension}' for case_id in case_ids for extension in ('json', 'npz'))
    if required != set(complete['artifacts']):
        raise ValueError('Completion manifest omits calibration evidence')
    actual_cases = {str(p.relative_to(directory)) for p in (directory/'cases').iterdir()}
    expected_cases = {f'cases/{case_id}.{ext}' for case_id in case_ids for ext in ('json', 'npz')}
    if actual_cases != expected_cases:
        raise ValueError('Missing or unexpected calibration case files')
    for path,expected in complete['artifacts'].items():
        if not (directory/path).resolve().is_relative_to(directory.resolve()):
            raise ValueError('Artifact escapes evidence directory: ' + path)
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

    likelihood_rows = 0
    for case in design['cases']:
        case_path = '/cases/' + case['case_id'] + '.json'
        payload = json.loads((directory/'cases'/f'{case["case_id"]}.json').read_text())
        _finite_json(payload, case_path)
        packets,generated_audit = generate_data(case,design)
        assert_exact(payload['case'], case, case_path + '/case')
        assert_exact(payload['observations'], packets, case_path + '/observations')
        assert_exact(payload['audit'], generated_audit, case_path + '/audit')
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
        for index, diag in enumerate(payload['diagnostics']):
            _check_count_types(diag, case_path + f'/diagnostics/{index}')
            assert_exact(diag['n_observations'], expected_n, case_path + '/n_observations')
            if diag['n_observations'] != expected_n or not np.isfinite(diag['cpu_seconds']) or diag['cpu_seconds'] < 0:
                raise ValueError('Invalid calibration accounting')
            if any(not np.isfinite(diag[field]) or diag[field] < 0 for field in ('fit_cpu_seconds', 'score_cpu_seconds')):
                raise ValueError('Invalid calibration CPU accounting')
            if diag['fit_cpu_seconds']+diag['score_cpu_seconds'] > diag['cpu_seconds']+1e-8:
                raise ValueError('Calibration CPU components exceed total')
        truth_ll = float(reference_log_likelihood(np.array([[case['truth'][p] for p in PARAMETERS]]),packets,sensor_sigma=design['sensor_sigma'])[0])
        with np.load(directory/'cases'/f'{case["case_id"]}.npz',allow_pickle=False) as arrays:
            for method in METHODS:
                diag_index = next(i for i, row in enumerate(payload['diagnostics']) if row['method'] == method)
                diag = payload['diagnostics'][diag_index]
                diag_path = case_path + f'/diagnostics/{diag_index}'
                _positive_int(diag['attempts'], diag_path + '/attempts')
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
                        _compare_reference(recorded_first, first_diag, first_log_diag,
                            diag_path + '/attempt_diagnostics/0', audit, initial_settings, expected_n)
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
                    _compare_reference(diag, computed, log_computed, diag_path, audit, settings, expected_n)
                    _compare_reference(diag['attempt_diagnostics'][-1], computed, log_computed,
                        diag_path + f'/attempt_diagnostics/{diag["attempts"] - 1}', audit, settings, expected_n)
                else:
                    particles,weights,ll = (arrays[f'{method}_{name}'] for name in ('particles','weights','log_likelihood'))
                    if particles.shape != (design['smc_settings'][method]['n_particles'], 3):
                        raise ValueError('SMC particles differ from scheduled budget')
                    if weights.shape != (len(particles),) or ll.shape != (len(particles),):
                        raise ValueError('SMC weight/likelihood shape mismatch')
                    if diag['attempts'] != 1 or (diag['status'] == 'passed') != (diag['failed_updates'] == 0):
                        raise ValueError('Invalid SMC status accounting')
                    expected_accepted = 0 if method == 'prior' else expected_n-diag['failed_updates']
                    assert_exact(diag['accepted_observations'], expected_accepted, diag_path + '/accepted_observations')
                    assert_exact(diag['duplicate_events'], 0, diag_path + '/duplicate_events')
                    if type(diag['failed_updates']) is not int or diag['failed_updates'] < 0:
                        raise ValueError('Invalid SMC failed-update count')
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
                assert_exact([r for r in payload['parameters'] if r['method']==method], expected_rows, case_path + '/parameters/' + method)
                assert_exact([r for r in payload['cdf'] if r['method']==method], expected_pits, case_path + '/cdf/' + method)
    rows,pits,diagnostics,agreements,summary = collect(directory,design)
    assert_exact(json.loads((directory/'summary.json').read_text()), summary, '/summary')
    assert_exact(json.loads((directory/'diagnostics.json').read_text()), diagnostics, '/diagnostics')
    for filename, primitives in (('parameters.csv', rows), ('cdf.csv', pits), ('agreement.csv', agreements)):
        check_export(filename, primitives)
    return {'verified':True,'cases':len(design['cases']),'posterior_rows':len(rows),
            'cdf_rows':len(pits),'agreement_rows':len(agreements),'sample_likelihoods':likelihood_rows,
            'artifacts':len(complete['artifacts'])}


class VerificationFailure(ValueError):
    """A failed verification with a JSON-safe audit receipt attached."""
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def _receipt_target(directory, path):
    if path is None:
        return None
    target = Path(path).resolve()
    if target.is_relative_to(directory.resolve()):
        raise ValueError('Receipt must be outside the frozen evidence directory')
    if target.exists():
        raise FileExistsError('Receipt already exists: ' + str(target))
    return target


def _write_receipt(path, receipt):
    if path is not None:
        # Recheck after a potentially long replay, including symlink resolution.
        path = _receipt_target(Path(receipt['source_directory']), path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write('\n')


def verify(directory, *, receipt_path=None):
    """Verify all scheduled cases without fitting new chains or changing evidence.

    A supplied receipt destination must be new and outside the input archive.
    Failures raise VerificationFailure and also retain a failure receipt there.
    """
    directory = Path(directory).resolve()
    destination = _receipt_target(directory, receipt_path)
    audit = DiagnosticAudit()
    receipt = {
        'verifier': VERIFIER_VERSION, 'verified': False,
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'source_directory': str(directory),
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__,
                    'scipy': scipy.__version__, 'platform': platform.platform(),
                    'machine': platform.machine(), 'implementation': platform.python_implementation(),
                    'thread_environment': {key: os.environ.get(key) for key in
                        ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}},
        'verifier_source_sha256': sha(Path(__file__)),
        'original_source_hashes': ORIGINAL_SOURCE_HASHES,
        'tolerances': {
            'reference_diagnostics': {'fields': list(DIAGNOSTIC_FLOAT_FIELDS),
                'rtol': RTOL, 'atol': ATOL,
                'rule': 'abs(recorded-recomputed) <= atol + rtol*abs(recomputed)',
                'locations': 'reference top level, every retained attempt, and their log_likelihood diagnostics'},
            'sample_log_likelihood': {'rtol': 1e-9, 'atol': 1e-10,
                'scope': 'Unchanged original verifier rule for reconstructed retained likelihood arrays'},
            'other_comparisons': 'Exact, with JSON scalar types preserved; no qualification or retry tolerance'},
        'pointer_root': 'Virtual archive tree: /cases/<filename>.json/... addresses that retained JSON document',
        'recipe': {'command': [sys.executable, str(Path(__file__).resolve()), '--source', str(directory)] +
                   (['--receipt', str(destination)] if destination else []),
                   'method': 'Pinned original data generation, retained-chain diagnostics and likelihood reconstruction; no posterior refit'},
    }
    try:
        receipt['input_hashes'] = {name: sha(directory/name)
                                   for name in ('design.json', 'design.sha256', 'completion.json')}
        receipt.update(_verify_evidence(directory, audit))
    except (ValueError, KeyError, TypeError, OSError, IndexError, OverflowError) as exc:
        receipt['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        receipt['numerical_drift'] = audit.summary()
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        _write_receipt(destination, receipt)
        raise VerificationFailure(str(exc), receipt) from exc
    receipt['numerical_drift'] = audit.summary()
    receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
    _write_receipt(destination, receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'evidence/world-model-calibration-v1')
    parser.add_argument('--receipt', type=Path,
                        help='New receipt file outside the input evidence directory')
    args = parser.parse_args(argv)
    try:
        result = verify(args.source, receipt_path=args.receipt)
    except VerificationFailure as exc:
        print(json.dumps(exc.receipt, indent=2, sort_keys=True, allow_nan=False), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
