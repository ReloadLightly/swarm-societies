"""Prospective panel boundaries, posterior primitives and calibration evidence."""

from copy import deepcopy
import json
import shutil

import numpy as np
import pytest

from scripts import run_world_model_calibration as calibration


@pytest.fixture(scope='module')
def tiny_calibration(tmp_path_factory):
    directory = tmp_path_factory.mktemp('calibration-control')
    design = calibration.prepare(directory, sbc_cases=1, ecology_cases=1, development=True)
    # A deliberately small test-only design exercises failed-reference retention;
    # it is not a production calibration estimate or a change to its budgets.
    design = deepcopy(design)
    design['sbc_observations'] = 8
    design['ecology_ticks'] = 8
    design['smc_settings'] = {
        'prior': {'n_particles': 64, 'rejuvenation_steps': 2},
        'published': {'n_particles': 64, 'rejuvenation_steps': 2},
        'higher_compute': {'n_particles': 128, 'rejuvenation_steps': 3},
    }
    design['reference_settings'] = {'n_chains': 4, 'warmup': 20, 'draws': 16}
    design['reference_retry'] = {'n_chains': 4, 'warmup': 40, 'draws': 32}
    calibration.json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(calibration.sha(directory/'design.json')+'\n')
    (directory/'cases').mkdir()
    fit_calls = []
    original_fit = calibration.fit_reference

    def tracked_fit(packets, **kwargs):
        fit_calls.append((deepcopy(packets), deepcopy(kwargs)))
        return original_fit(packets, **kwargs)

    calibration.fit_reference = tracked_fit
    try:
        for case in design['cases']:
            calibration.run_case((directory, case, design))
    finally:
        calibration.fit_reference = original_fit
    rows, pits, diagnostics, agreements, summary = calibration.collect(directory, design)
    for filename, records in (('parameters.csv', rows), ('cdf.csv', pits), ('agreement.csv', agreements)):
        calibration.csv_write(directory/filename, records)
    calibration.json_write(directory/'diagnostics.json', diagnostics)
    calibration.json_write(directory/'summary.json', summary)
    files = sorted(path for path in directory.rglob('*') if path.is_file())
    calibration.json_write(directory/'completion.json', {'study': calibration.VERSION,
        'artifacts': {str(path.relative_to(directory)): calibration.sha(path) for path in files}})
    return directory, design, summary, fit_calls


def copy_evidence(tiny_calibration, tmp_path):
    target = tmp_path/'evidence'
    shutil.copytree(tiny_calibration[0], target)
    return target


def rehash(directory, relative):
    manifest = json.loads((directory/'completion.json').read_text())
    manifest['artifacts'][relative] = calibration.sha(directory/relative)
    calibration.json_write(directory/'completion.json', manifest)


def test_exogenous_features_are_independent_of_truth_and_packets_are_legal(tiny_calibration):
    _, design, _, _ = tiny_calibration
    case = next(c for c in design['cases'] if c['cohort'] == 'prior_predictive')
    changed = deepcopy(case)
    changed['truth']['b'] += .1
    original, _ = calibration.generate_data(case, design)
    alternative, _ = calibration.generate_data(changed, design)
    expected_fields = {'event_id', 'stock_before', 'capacity', 'own_infrastructure',
                       'other_infrastructure', 'growth', 'sensor_sigma'}
    for first, second in zip(original, alternative):
        assert set(first) == expected_fields
        assert {k: v for k, v in first.items() if k != 'growth'} == {k: v for k, v in second.items() if k != 'growth'}
        if first['stock_before'] == 0:
            assert second['growth']-first['growth'] == pytest.approx(.1*first['own_infrastructure'])
    assert len({p['event_id'] for p in original}) == design['sbc_observations']


def test_ecological_panel_is_reproducible_and_has_three_distinct_patch_events_per_tick(tiny_calibration):
    _, design, _, _ = tiny_calibration
    case = next(c for c in design['cases'] if c['cohort'] == 'ecological')
    packets, audit = calibration.generate_data(case, design)
    assert (packets, audit) == calibration.generate_data(case, design)
    assert len(packets) == 3*design['ecology_ticks']
    assert len({p['event_id'] for p in packets}) == len(packets)
    assert audit['ledger_residual'] == pytest.approx(0., abs=1e-8)
    assert all(not {'truth', 'weather', 'regime', 'true_growth', 'seed'} & p.keys() for p in packets)


def test_development_and_evaluation_panels_have_disjoint_case_namespaces(tiny_calibration, tmp_path):
    evaluation = calibration.prepare(tmp_path/'evaluation', sbc_cases=1, ecology_cases=1)
    development = tiny_calibration[1]
    assert not {c['case_id'] for c in evaluation['cases']} & {c['case_id'] for c in development['cases']}
    for case in evaluation['cases']:
        bounds = calibration.PRIOR if case['cohort'] == 'prior_predictive' else {'r': (2.4, 6.8), 'b': (.7, 2.7), 'g': (.05, .7)}
        assert all(bounds[p][0] <= case['truth'][p] <= bounds[p][1] for p in calibration.PARAMETERS)


def test_weighted_cdf_handles_ties_and_data_dependent_log_likelihood():
    particles = np.array([[3., 1., .1], [5., 1.5, .4], [7., 2., .6]])
    weights = np.array([.2, .3, .5])
    case = {'case_id': 'hand-check', 'cohort': 'prior_predictive', 'truth': {'r': 5., 'b': 1.5, 'g': .4}}
    rows, cdf = calibration.posterior_rows(case, 'published', particles, weights, np.array([-3., -1., -2.]), -2.)
    assert [row['cdf'] for row in rows] == pytest.approx([.35]*3)
    assert rows[0]['mean'] == pytest.approx(5.6)
    assert rows[0]['q95'] == pytest.approx(6.8)
    assert cdf[-1]['quantity'] == 'log_likelihood'
    assert cdf[-1]['cdf'] == pytest.approx(.45)
    with pytest.raises(ValueError, match='posterior representation'):
        calibration.posterior_rows(case, 'published', particles, np.array([-.1, .3, .8]), np.zeros(3), 0.)


def test_reference_fit_sees_only_evidence_and_retry_is_predeclared(tiny_calibration):
    _, design, _, calls = tiny_calibration
    assert len(calls) == 2*len(design['cases'])
    for first, retry in zip(calls[::2], calls[1::2]):
        first_packets, first_kwargs = first
        retry_packets, retry_kwargs = retry
        assert first_packets == retry_packets
        assert first_kwargs['seed'] != retry_kwargs['seed']
        assert first_kwargs['draws'] == design['reference_settings']['draws']
        assert retry_kwargs['draws'] == design['reference_retry']['draws']
        assert 'truth' not in first_kwargs
        assert all(not {'truth', 'weather', 'true_growth', 'world_parameters'} & packet.keys() for packet in first_packets)


def test_failed_references_remain_in_coverage_denominators_and_not_qualified_agreement(tiny_calibration):
    _, design, summary, _ = tiny_calibration
    assert summary['cohort_counts'] == {'prior_predictive': 1, 'ecological': 1}
    assert summary['reference_failures'] == {'prior_predictive': 1, 'ecological': 1}
    for row in summary['all_case_summaries']:
        assert row['covered90']['n'] == 1
        assert row['mean_gap_reference_sd']['n'] == 0
        assert row['mean_gap_reference_sd']['mean'] is None
    for case in design['cases']:
        payload = json.loads((tiny_calibration[0]/'cases'/f'{case["case_id"]}.json').read_text())
        prior = next(d for d in payload['diagnostics'] if d['method'] == 'prior')
        assert prior['accepted_observations'] == 0
        reference = next(d for d in payload['diagnostics'] if d['method'] == 'reference')
        assert reference['attempts'] == 2
        assert len(reference['attempt_diagnostics']) == 2


def test_end_to_end_calibration_verifies_exported_and_array_primitives(tiny_calibration):
    verified = calibration.verify(tiny_calibration[0])
    assert verified['verified']
    assert verified['cases'] == 2
    assert verified['posterior_rows'] == 24
    assert verified['cdf_rows'] == 32
    assert verified['agreement_rows'] == 18


def test_design_tampering_is_rejected(tiny_calibration, tmp_path):
    directory = copy_evidence(tiny_calibration, tmp_path)
    design = json.loads((directory/'design.json').read_text())
    design['sbc_observations'] += 1
    calibration.json_write(directory/'design.json', design)
    with pytest.raises(ValueError, match='design checksum'):
        calibration.check_design(directory)


@pytest.mark.parametrize('filename', ['parameters.csv', 'cdf.csv', 'agreement.csv'])
def test_export_tampering_fails_after_checksum_rewrite(tiny_calibration, tmp_path, filename):
    directory = copy_evidence(tiny_calibration, tmp_path)
    rows = calibration.csv_read(directory/filename)
    rows[0]['case_id'] = 'foreign-case'
    calibration.csv_write(directory/filename, rows)
    rehash(directory, filename)
    with pytest.raises(ValueError, match='Exported'):
        calibration.verify(directory)


def test_posterior_primitive_tampering_is_rejected(tiny_calibration, tmp_path):
    directory = copy_evidence(tiny_calibration, tmp_path)
    relative = f'cases/{tiny_calibration[1]["cases"][0]["case_id"]}.json'
    payload = json.loads((directory/relative).read_text())
    payload['parameters'][0]['mean'] += .1
    calibration.json_write(directory/relative, payload)
    rehash(directory, relative)
    with pytest.raises(ValueError, match='Posterior primitive reconstruction'):
        calibration.verify(directory)


def test_stored_likelihood_tampering_is_rejected(tiny_calibration, tmp_path):
    directory = copy_evidence(tiny_calibration, tmp_path)
    relative = f'cases/{tiny_calibration[1]["cases"][0]["case_id"]}.npz'
    with np.load(directory/relative, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    arrays['published_log_likelihood'][0] += .5
    np.savez_compressed(directory/relative, **arrays)
    rehash(directory, relative)
    with pytest.raises(ValueError, match='stored sample log likelihood'):
        calibration.verify(directory)


def test_first_failed_attempt_is_preserved_and_verified(tiny_calibration, tmp_path):
    directory = copy_evidence(tiny_calibration, tmp_path)
    relative = f'cases/{tiny_calibration[1]["cases"][0]["case_id"]}.npz'
    with np.load(directory/relative, allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    assert arrays['reference_attempt1_chains'].shape[1] == tiny_calibration[1]['reference_settings']['draws']
    arrays['reference_attempt1_loglik_chains'] += .5
    np.savez_compressed(directory/relative, **arrays)
    rehash(directory, relative)
    with pytest.raises(ValueError, match='initial reference sample log likelihood'):
        calibration.verify(directory)


def test_summary_tampering_is_rejected(tiny_calibration, tmp_path):
    directory = copy_evidence(tiny_calibration, tmp_path)
    summary = json.loads((directory/'summary.json').read_text())
    summary['reference_failures']['ecological'] = 0
    calibration.json_write(directory/'summary.json', summary)
    rehash(directory, 'summary.json')
    with pytest.raises(ValueError, match='Summary reconstruction'):
        calibration.verify(directory)


def test_wilson_coverage_uncertainty_survives_all_successes():
    result = calibration.coverage_interval([1]*24)
    assert result['mean'] == 1.
    assert 0 < result['ci95'][0] < 1.
    assert result['ci95'][1] == pytest.approx(1.)
    assert calibration.coverage_interval([])['n'] == 0


def test_failed_reference_missing_mcse_remains_reportable(tiny_calibration, tmp_path):
    directory = copy_evidence(tiny_calibration, tmp_path)
    case = tiny_calibration[1]['cases'][0]
    relative = f'cases/{case["case_id"]}.json'
    payload = json.loads((directory/relative).read_text())
    reference = next(row for row in payload['diagnostics'] if row['method'] == 'reference')
    reference['mean_mcse'] = [None, None, None]
    calibration.json_write(directory/relative, payload)
    _, _, _, agreements, summary = calibration.collect(directory, tiny_calibration[1])
    affected = [row for row in agreements if row['case_id'] == case['case_id']]
    assert all(row['reference_mean_mcse_sd'] is None for row in affected)
    assert summary['reference_failures'][case['cohort']] == 1


def test_degenerate_failed_reference_saves_null_correlations(tiny_calibration, tmp_path, monkeypatch):
    from swarm_societies.world_model_v1.reference import chain_diagnostics

    def stuck_reference(packets, **kwargs):
        draws = np.broadcast_to(np.array([5., 1.5, .4]), (kwargs['n_chains'], kwargs['draws'], 3)).copy()
        log_likelihood = calibration.reference_log_likelihood(draws, packets, sensor_sigma=kwargs['sensor_sigma'])
        diagnostics = chain_diagnostics(draws, rhat_limit=kwargs['rhat_limit'], min_ess=kwargs['min_ess'])
        diagnostics.update(log_likelihood=None, mean_mcse=[None]*3)
        return {'draws': draws, 'draw_log_likelihood': log_likelihood,
                'diagnostics': diagnostics, 'status': 'failed'}

    monkeypatch.setattr(calibration, 'fit_reference', stuck_reference)
    (tmp_path/'cases').mkdir()
    design = tiny_calibration[1]
    payload = calibration.run_case((tmp_path, design['cases'][0], design))
    ref = next(row for row in payload['diagnostics'] if row['method'] == 'reference')
    assert ref['status'] == 'failed'
    assert ref['posterior_correlation'] == [[None]*3 for _ in range(3)]
    json.dumps(payload, allow_nan=False)
