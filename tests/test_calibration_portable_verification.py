"""Portable reconstruction may relax roundoff, never the scientific gate."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from scripts import run_world_model_calibration as calibration
from scripts import verify_calibration_portable_v1 as portable


def diagnostic():
    return {'passed': True, 'rhat': [1.001, 1.002, 1.003],
            'bulk_ess': [500., 600., 700.], 'tail_ess': [450., 550., 650.],
            'rhat_limit': 1.01, 'min_ess': 400.,
            'split_chains': 8, 'draws_per_split_chain': 2000}


@pytest.mark.parametrize('field', portable.DIAGNOSTIC_FLOAT_FIELDS)
def test_one_ulp_drift_is_allowed_and_recorded_at_exact_pointer(field):
    recorded = diagnostic()
    computed = deepcopy(recorded)
    computed[field][1] = float(np.nextafter(computed[field][1], np.inf))
    audit = portable.DiagnosticAudit()
    audit.compare(recorded, computed, '/cases/example.json/diagnostics/3')
    summary = audit.summary()
    assert summary['compared_float_values'] == 9
    assert summary['drift_count'] == 1
    assert summary['drifts'][0]['pointer'] == f'/cases/example.json/diagnostics/3/{field}/1'
    assert summary['max_absolute_error'] > 0
    assert summary['max_relative_error'] < 1e-12
    assert summary['drifts'][0]['within_tolerance']


@pytest.mark.parametrize('field', portable.DIAGNOSTIC_FLOAT_FIELDS)
def test_material_drift_is_rejected(field):
    recorded, computed = diagnostic(), diagnostic()
    computed[field][0] += .001
    audit = portable.DiagnosticAudit()
    with pytest.raises(ValueError, match='numerical mismatch'):
        audit.compare(recorded, computed, '/diagnostics/3')
    assert audit.summary()['drifts'][0]['within_tolerance'] is False


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
@pytest.mark.parametrize('side', ['recorded', 'computed'])
def test_nonfinite_values_never_receive_tolerance(value, side):
    pair = {'recorded': diagnostic(), 'computed': diagnostic()}
    pair[side]['bulk_ess'][0] = value
    with pytest.raises(ValueError, match='Nonfinite'):
        portable.DiagnosticAudit().compare(pair['recorded'], pair['computed'], '/diag')


@pytest.mark.parametrize(('field', 'value'), [('passed', 1), ('split_chains', True),
    ('split_chains', 8.), ('draws_per_split_chain', 2000.), ('rhat_limit', 1), ('min_ess', 400)])
def test_boolean_integer_and_threshold_types_remain_exact(field, value):
    recorded, computed = diagnostic(), diagnostic()
    recorded[field] = value
    with pytest.raises(ValueError, match='Exact type mismatch'):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')


@pytest.mark.parametrize('value', [True, 500, None])
def test_diagnostic_float_fields_cannot_be_retyped(value):
    recorded, computed = diagnostic(), diagnostic()
    recorded['bulk_ess'][0] = value
    with pytest.raises(ValueError, match='type|Null'):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')


@pytest.mark.parametrize('change', ['shorter', 'nested', 'missing', 'tuple'])
def test_diagnostic_shapes_and_fields_are_exact(change):
    recorded, computed = diagnostic(), diagnostic()
    if change == 'shorter': recorded['rhat'].pop()
    if change == 'nested': recorded['rhat'][0] = [recorded['rhat'][0]]
    if change == 'missing': del recorded['tail_ess']
    if change == 'tuple': recorded['rhat'] = tuple(recorded['rhat'])
    with pytest.raises(ValueError):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')


@pytest.mark.parametrize('field', portable.DIAGNOSTIC_FLOAT_FIELDS)
def test_threshold_crossing_fails_even_when_overall_gate_stays_failed(field):
    recorded, computed = diagnostic(), diagnostic()
    recorded['passed'] = computed['passed'] = False
    # Another dimension fails, so an aggregate-status check alone misses this.
    recorded['tail_ess'][2] = computed['tail_ess'][2] = 300.
    if field == 'rhat':
        recorded[field][0] = float(np.nextafter(1.01, -np.inf))
        computed[field][0] = 1.01
    else:
        recorded[field][0] = 400.
        computed[field][0] = float(np.nextafter(400., -np.inf))
    with pytest.raises(ValueError, match='boundary discrepancy'):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')


def test_threshold_and_qualification_are_exact_despite_tiny_difference():
    recorded, computed = diagnostic(), diagnostic()
    computed['rhat_limit'] = float(np.nextafter(1.01, np.inf))
    with pytest.raises(ValueError, match='Exact value mismatch'):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')
    computed = diagnostic()
    computed['passed'] = False
    with pytest.raises(ValueError, match='Exact value mismatch'):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')


def test_degenerate_null_rhat_is_exact_failed_trace_representation():
    recorded, computed = diagnostic(), diagnostic()
    for value in (recorded, computed):
        value.update(passed=False, rhat=[None, None, None], bulk_ess=[0., 0., 0.], tail_ess=[0., 0., 0.])
    portable.DiagnosticAudit().compare(recorded, computed, '/diag')
    computed['rhat'][0] = float('inf')
    with pytest.raises(ValueError):
        portable.DiagnosticAudit().compare(recorded, computed, '/diag')


@pytest.mark.parametrize('mutation', [None, 'passed', 'status', 'log_likelihood_passed'])
def test_case067_retry_is_required_when_only_likelihood_mixing_fails(mutation):
    # This real retained trace caught a semantic difference between the raw
    # coefficient diagnostic and fit_reference's combined qualification flag.
    directory = portable.ROOT/'evidence/world-model-calibration-v1'
    design = json.loads((directory/'design.json').read_text())
    path = directory/'cases/evaluation-prior_predictive-067.json'
    payload = json.loads(path.read_text())
    reference = next(row for row in payload['diagnostics'] if row['method'] == 'reference')
    assert reference['attempts'] == 2
    recorded = deepcopy(reference['attempt_diagnostics'][0])
    gate = design['reference_gate']
    with np.load(path.with_suffix('.npz'), allow_pickle=False) as arrays:
        computed = portable.chain_diagnostics(arrays['reference_attempt1_chains'],
            rhat_limit=gate['max_rhat'], min_ess=gate['min_bulk_ess'])
        log_computed = portable.chain_diagnostics(arrays['reference_attempt1_loglik_chains'],
            rhat_limit=gate['max_rhat'], min_ess=gate['min_tail_ess'])
    assert computed['passed'] is True
    assert log_computed['passed'] is False
    assert recorded['passed'] is False and recorded['status'] == 'failed'
    if mutation == 'passed': recorded['passed'] = True
    if mutation == 'status': recorded['status'] = 'passed'
    if mutation == 'log_likelihood_passed': recorded['log_likelihood']['passed'] = True
    def compare():
        portable._compare_reference(recorded, computed, log_computed,
            '/cases/evaluation-prior_predictive-067.json/diagnostics/3/attempt_diagnostics/0',
            portable.DiagnosticAudit(), design['reference_settings'], reference['n_observations'])
    if mutation is None:
        compare()
    else:
        with pytest.raises(ValueError, match='Exact value mismatch'):
            compare()


@pytest.fixture(scope='module')
def tiny_archive(tmp_path_factory):
    directory = tmp_path_factory.mktemp('portable-calibration')
    design = calibration.prepare(directory, sbc_cases=1, ecology_cases=1, development=True)
    # Test-only numerical settings, not a modified published scientific design.
    design.update(sbc_observations=8, ecology_ticks=8)
    design['smc_settings'] = {method: {'n_particles': 32, 'rejuvenation_steps': 1}
                              for method in calibration.METHODS if method != 'reference'}
    design['reference_settings'] = {'n_chains': 4, 'warmup': 8, 'draws': 16}
    design['reference_retry'] = {'n_chains': 4, 'warmup': 16, 'draws': 32}
    calibration.json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(calibration.sha(directory/'design.json')+'\n')
    (directory/'cases').mkdir()
    for case in design['cases']:
        calibration.run_case((directory, case, design))
    rows, pits, diagnostics, agreement, summary = calibration.collect(directory, design)
    for name, records in [('parameters.csv', rows), ('cdf.csv', pits), ('agreement.csv', agreement)]:
        calibration.csv_write(directory/name, records)
    calibration.json_write(directory/'diagnostics.json', diagnostics)
    calibration.json_write(directory/'summary.json', summary)
    calibration.json_write(directory/'completion.json', {'study': calibration.VERSION,
        'artifacts': {str(p.relative_to(directory)): calibration.sha(p)
                      for p in sorted(directory.rglob('*')) if p.is_file()}})
    return directory, design


def copied(tiny_archive, tmp_path):
    directory = tmp_path/'archive'
    shutil.copytree(tiny_archive[0], directory)
    return directory


def rehash(directory, relative):
    manifest = json.loads((directory/'completion.json').read_text())
    manifest['artifacts'][relative] = calibration.sha(directory/relative)
    calibration.json_write(directory/'completion.json', manifest)


def case_payload(directory):
    path = sorted((directory/'cases').glob('*.json'))[0]
    data = json.loads(path.read_text())
    reference = next(r for r in data['diagnostics'] if r['method'] == 'reference')
    return path, data, reference


def save_case(directory, path, data):
    calibration.json_write(path, data)
    rehash(directory, str(path.relative_to(directory)))


def test_complete_small_archive_matches_original_and_never_changes_frozen_inputs(tiny_archive, tmp_path):
    directory, _ = tiny_archive
    before = {str(p): calibration.sha(p) for p in directory.rglob('*') if p.is_file()}
    exact = calibration.verify(directory)
    receipt = portable.verify(directory, receipt_path=tmp_path/'receipt.json')
    assert all(receipt[key] == value for key, value in exact.items())
    assert receipt['cases'] == 2
    assert receipt['numerical_drift']['drift_count'] == 0
    assert receipt['tolerances']['sample_log_likelihood'] == {
        'rtol': 1e-9, 'atol': 1e-10,
        'scope': 'Unchanged original verifier rule for reconstructed retained likelihood arrays'}
    assert json.loads((tmp_path/'receipt.json').read_text()) == receipt
    assert before == {str(p): calibration.sha(p) for p in directory.rglob('*') if p.is_file()}
    assert all(calibration.sha(portable.ROOT/name) == expected
               for name, expected in portable.ORIGINAL_SOURCE_HASHES.items())


def test_portability_drift_covers_retry_final_attempt_and_likelihood(tiny_archive, monkeypatch):
    original_diagnostics = portable.chain_diagnostics
    def shifted(*args, **kwargs):
        result = original_diagnostics(*args, **kwargs)
        for field in portable.DIAGNOSTIC_FLOAT_FIELDS:
            result[field] = [float(np.nextafter(x, np.inf)) if x is not None else None for x in result[field]]
        return result
    monkeypatch.setattr(portable, 'chain_diagnostics', shifted)
    receipt = portable.verify(tiny_archive[0])
    pointers = [row['pointer'] for row in receipt['numerical_drift']['drifts']]
    assert receipt['verified']
    assert any('/attempt_diagnostics/0/' in p for p in pointers)
    assert any('/attempt_diagnostics/1/' in p for p in pointers)
    assert any('/log_likelihood/' in p for p in pointers)
    assert any(p.endswith('/rhat/0') for p in pointers)
    assert all(row['within_tolerance'] for row in receipt['numerical_drift']['drifts'])


@pytest.mark.parametrize('where', ['final', 'first_attempt', 'last_attempt', 'log_likelihood'])
def test_changed_diagnostic_fails_after_manifest_rewrite(tiny_archive, tmp_path, where):
    directory = copied(tiny_archive, tmp_path)
    path, data, reference = case_payload(directory)
    target = {'final': reference, 'first_attempt': reference['attempt_diagnostics'][0],
              'last_attempt': reference['attempt_diagnostics'][-1],
              'log_likelihood': reference['log_likelihood']}[where]
    target['bulk_ess'][0] += .01
    save_case(directory, path, data)
    with pytest.raises(portable.VerificationFailure, match='numerical mismatch') as error:
        portable.verify(directory, receipt_path=tmp_path/'failed.json')
    receipt = json.loads((tmp_path/'failed.json').read_text())
    assert receipt == error.value.receipt
    assert not receipt['verified']
    assert receipt['numerical_drift']['drift_count'] >= 1


@pytest.mark.parametrize('field', ['attempts', 'n_observations', 'passed', 'split_chains'])
def test_semantic_counts_and_booleans_remain_typed(tiny_archive, tmp_path, field):
    directory = copied(tiny_archive, tmp_path)
    path, data, reference = case_payload(directory)
    reference[field] = int(reference[field]) if field == 'passed' else float(reference[field])
    save_case(directory, path, data)
    with pytest.raises(portable.VerificationFailure, match='type|integer'):
        portable.verify(directory)


@pytest.mark.parametrize('kind', ['nan', 'observation_ulp', 'first_status', 'final_status', 'missing_row', 'duplicate_row'])
def test_no_general_relaxation_of_case_semantics(tiny_archive, tmp_path, kind):
    directory = copied(tiny_archive, tmp_path)
    path, data, reference = case_payload(directory)
    if kind == 'nan': reference['bulk_ess'][0] = float('nan')
    elif kind == 'observation_ulp':
        data['observations'][0]['growth'] = float(np.nextafter(data['observations'][0]['growth'], np.inf))
    elif kind == 'first_status': reference['attempt_diagnostics'][0]['status'] = 'passed'
    elif kind == 'final_status': reference['status'] = 'passed'
    elif kind == 'missing_row': data['parameters'].pop()
    elif kind == 'duplicate_row': data['parameters'].append(deepcopy(data['parameters'][0]))
    if kind == 'nan':
        # A corrupted archive can contain nonstandard JSON even though the
        # trusted writer deliberately refuses to create it.
        path.write_text(json.dumps(data))
        rehash(directory, str(path.relative_to(directory)))
    else:
        save_case(directory, path, data)
    with pytest.raises(portable.VerificationFailure):
        portable.verify(directory)


@pytest.mark.parametrize('kind', ['shape', 'sample', 'likelihood', 'nonfinite', 'broadcast_weights', 'broadcast_likelihood'])
def test_retained_samples_and_likelihoods_remain_verified(tiny_archive, tmp_path, kind):
    directory = copied(tiny_archive, tmp_path)
    path = sorted((directory/'cases').glob('*.npz'))[0]
    with np.load(path, allow_pickle=False) as archive:
        arrays = {k: archive[k].copy() for k in archive.files}
    if kind == 'shape': arrays['reference_attempt1_chains'] = arrays['reference_attempt1_chains'][:, :-1]
    if kind == 'sample': arrays['published_particles'][0, 0] += .1
    if kind == 'likelihood': arrays['published_log_likelihood'][0] += .1
    if kind == 'nonfinite': arrays['reference_chains'][0, 0, 0] = np.inf
    if kind == 'broadcast_weights': arrays['published_weights'] = arrays['published_weights'][:1]
    if kind == 'broadcast_likelihood': arrays['published_log_likelihood'] = arrays['published_log_likelihood'][:1]
    np.savez_compressed(path, **arrays)
    rehash(directory, str(path.relative_to(directory)))
    with pytest.raises(portable.VerificationFailure):
        portable.verify(directory)


@pytest.mark.parametrize('kind', ['source', 'missing_case', 'unexpected_case', 'manifest_omission', 'duplicate_case'])
def test_source_and_case_inventory_integrity(tiny_archive, tmp_path, kind):
    directory = copied(tiny_archive, tmp_path)
    if kind == 'source':
        path = directory/'sources/scripts/run_world_model_calibration.py'
        path.write_text(path.read_text()+'\n# altered\n')
        rehash(directory, str(path.relative_to(directory)))
    elif kind == 'missing_case': sorted((directory/'cases').glob('*.json'))[0].unlink()
    elif kind == 'unexpected_case': (directory/'cases/foreign.json').write_text('{}')
    elif kind == 'manifest_omission':
        manifest = json.loads((directory/'completion.json').read_text())
        del manifest['artifacts']['summary.json']
        calibration.json_write(directory/'completion.json', manifest)
    elif kind == 'duplicate_case':
        design = json.loads((directory/'design.json').read_text())
        design['cases'].append(deepcopy(design['cases'][0]))
        calibration.json_write(directory/'design.json', design)
        (directory/'design.sha256').write_text(calibration.sha(directory/'design.json')+'\n')
        rehash(directory, 'design.json'); rehash(directory, 'design.sha256')
    with pytest.raises(portable.VerificationFailure):
        portable.verify(directory)


def test_receipts_cannot_modify_evidence_or_overwrite_files(tiny_archive, tmp_path):
    with pytest.raises(ValueError, match='outside'):
        portable.verify(tiny_archive[0], receipt_path=tiny_archive[0]/'receipt.json')
    target = tmp_path/'existing.json'
    target.write_text('keep')
    with pytest.raises(FileExistsError):
        portable.verify(tiny_archive[0], receipt_path=target)
    assert target.read_text() == 'keep'
    alias = tmp_path/'archive-alias'
    alias.symlink_to(tiny_archive[0], target_is_directory=True)
    with pytest.raises(ValueError, match='outside'):
        portable.verify(tiny_archive[0], receipt_path=alias/'receipt.json')


@pytest.mark.parametrize('filename', ['parameters.csv', 'cdf.csv', 'agreement.csv', 'summary.json'])
def test_exported_tables_and_summary_stay_exact(tiny_archive, tmp_path, filename):
    directory = copied(tiny_archive, tmp_path)
    if filename.endswith('.csv'):
        rows = calibration.csv_read(directory/filename)
        rows[0]['case_id'] = 'altered-case'
        calibration.csv_write(directory/filename, rows)
    else:
        value = json.loads((directory/filename).read_text())
        value['reference_failures']['ecological'] = 0
        calibration.json_write(directory/filename, value)
    rehash(directory, filename)
    with pytest.raises(portable.VerificationFailure, match='Exported|Exact'):
        portable.verify(directory)


def test_cli_generates_portable_receipt_without_rewriting_evidence(tiny_archive, tmp_path, capsys):
    target = tmp_path/'cli.json'
    assert portable.main(['--source', str(tiny_archive[0]), '--receipt', str(target)]) == 0
    assert json.loads(capsys.readouterr().out)['verified']
    assert json.loads(target.read_text())['verifier'] == portable.VERIFIER_VERSION
