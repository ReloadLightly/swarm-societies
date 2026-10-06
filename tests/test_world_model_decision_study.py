"""Independent information, counterfactual and evidence checks for decisions."""
from copy import deepcopy
import json
import shutil
from unittest.mock import patch

import numpy as np
import pytest

from scripts import run_world_model_decision as study
from swarm_societies.world_model_v1 import decision


@pytest.fixture(scope='module')
def tiny_design():
    value = study.make_design(development=True)
    value['warmup_ticks'] = 8
    value['horizon'] = 8
    value['planner_samples'] = 32
    value['learner_settings'] = {
        'n_particles': 32, 'rejuvenation_steps': 1, 'ess_fraction': .5,
    }
    value['config']['ticks'] = 16
    value['config']['disturbance_tick'] = 8
    value['cases'] = value['cases'][:2]
    return value


@pytest.fixture(scope='module')
def tiny_case(tiny_design):
    return study.evaluate_case(tiny_design['cases'][0], tiny_design)


def test_testonly_development_design_leaves_production_defaults_unchanged(tiny_design):
    canonical = study.make_design(development=True)
    assert canonical['warmup_ticks'] == canonical['horizon'] == 32
    assert canonical['planner_samples'] == 512
    assert canonical['learner_settings']['n_particles'] == 1024
    assert canonical['learner_settings']['rejuvenation_steps'] == 4
    assert len(canonical['cases']) == 6
    assert tiny_design['warmup_ticks'] == 8
    assert {tuple(case['world_parameters'][name] for name in ('r', 'b', 'g'))
            for case in canonical['cases']} == {
                (r, b, .3) for r in (2.4, 4.6, 6.8) for b in (.7, 2.7)}


def test_fresh_evaluation_arena_bank_does_not_reuse_development_worlds(tiny_design):
    evaluation = study.make_design(development=False, arenas=24)
    development = study.make_design(development=True)
    for field in ('arena_id', 'environment_seed'):
        assert not {case[field] for case in development['cases']} & {
            case[field] for case in evaluation['cases']}
    assert len(evaluation['cases']) == 24


def test_institution_receives_only_delivered_home_evidence_before_decision(tiny_case, tiny_design):
    warmup = tiny_case['warmup']
    assert len(warmup['packets']) == 3 * tiny_design['warmup_ticks']
    assert len({packet['event_id'] for packet in warmup['packets']}) == len(warmup['packets'])
    by_id = {packet['event_id']: packet for packet in warmup['packets']}
    for focal in range(3):
        learned = warmup['learned_models'][str(focal)]
        prior = warmup['prior_models'][str(focal)]
        assert prior['evidence'] == []
        assert len(learned['evidence']) == tiny_design['warmup_ticks']
        received = [by_id[packet['event_id']] for packet in learned['evidence']]
        assert {packet['patch'] for packet in received} == {focal}
        assert {packet['tick'] for packet in received} == set(range(8))
        for raw, fitted in zip(received, learned['evidence']):
            assert fitted['growth'] == raw['growth']
            assert fitted['headroom'] == raw['capacity'] - raw['stock_before']
        obs = tiny_case['legal_observations'][str(focal)]
        decision.validate_observation(obs)
        assert obs['tick'] == 8 and obs['society_id'] == focal
        assert obs['last_growth']['tick'] == 7
        assert obs['last_growth'] in received
        assert set(obs) == decision.OBS_KEYS
        assert set(obs['last_growth']) == decision.PACKET_KEYS
        assert not {'stock_after', 'weather', 'world_parameters', 'budget', 'rng_state'} & obs.keys()


def test_forecasts_and_case_are_reproducible_with_protected_state_unchanged(tiny_case, tiny_design):
    assert tiny_case == study.evaluate_case(tiny_design['cases'][0], tiny_design)
    assert tiny_case['protected_state_before'] == tiny_case['protected_state_after']
    assert len(tiny_case['forecasts']) == len(tiny_case['scores']) == 9
    assert len(tiny_case['branches']) == 9
    assert len({(row['focal'], row['condition']) for row in tiny_case['scores']}) == 9
    assert len({(row['focal'], row['public_fraction']) for row in tiny_case['branches']}) == 9
    assert len(tiny_case['forecast_commitment_sha256']) == 64
    for row in tiny_case['forecasts']:
        assert len(row['coefficient_draws']) == 32
        assert np.asarray(row['coefficient_draws']).shape == (32, 3)
    checkpoint = tiny_case['checkpoint']
    for protected, saved in (('engine', 'world'), ('sharing', 'sharing'), ('sensor_rng', 'sensor_rng')):
        assert study.digest(checkpoint[saved]) == tiny_case['protected_state_before'][protected]
    assert tiny_case['forecast_commitment_sha256'] == study.digest({
        'forecasts': tiny_case['forecasts'], 'gate_forecasts': tiny_case['gate_forecasts'],
    })


def test_realized_choice_scores_reconcile_with_finite_menu_branches(tiny_case):
    for score in tiny_case['scores']:
        values = {branch['public_fraction']: branch for branch in tiny_case['branches']
                  if branch['focal'] == score['focal']}
        chosen = values[score['action']]
        assert score['utility'] == chosen['utility']
        assert score['utility'] == pytest.approx(
            score['consumption_per_member'] + .2 * score['terminal_wealth_per_member'])
        assert score['regret'] == pytest.approx(
            max(value['utility'] for value in values.values()) - score['utility'])
        assert score['actual_budget'] == chosen['initial_budget']
        assert score['budget_prediction_error'] == score['forecast_budget'] - score['actual_budget']
        assert score['utility_prediction_error'] == score['forecast_utility'] - score['utility']


def test_all_forecasts_are_made_before_any_evaluator_branch(tiny_design, monkeypatch):
    original_forecast = study.decision.forecast
    original_branch = study.branch_outcomes
    sequence = []

    def recorded_forecast(*args, **kwargs):
        assert 'branch' not in sequence
        sequence.append('forecast')
        return original_forecast(*args, **kwargs)

    def recorded_branch(snapshot, focal, action, design):
        assert sequence.count('forecast') == 15
        sequence.append('branch')
        original_snapshot = deepcopy(snapshot)
        result = original_branch(snapshot, focal, action, design)
        assert snapshot == original_snapshot
        return result

    monkeypatch.setattr(study.decision, 'forecast', recorded_forecast)
    monkeypatch.setattr(study, 'branch_outcomes', recorded_branch)
    result = study.evaluate_case(tiny_design['cases'][0], tiny_design)
    assert sequence == ['forecast'] * 15 + ['branch'] * 9
    assert result['protected_state_before'] == result['protected_state_after']


def test_posterior_sampling_does_not_consume_belief_randomness(tiny_case):
    snapshot = tiny_case['warmup']['learned_models']['0']
    original = deepcopy(snapshot)
    first = study.sample_coefficients(snapshot, 32, 812)
    second = study.sample_coefficients(snapshot, 32, 812)
    np.testing.assert_array_equal(first, second)
    assert snapshot == original
    assert all(tuple(row) in {tuple(particle) for particle in snapshot['particles']}
               for row in first)


def test_short_horizon_development_gate_cannot_authorize_evaluation(tiny_case, tiny_design):
    result = study.gate_summary([tiny_case], tiny_design)
    assert not result['passed']


def test_failed_forecast_stays_in_the_complete_planned_grid(tiny_design, monkeypatch):
    original = study.decision.forecast
    calls = []

    def fail_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError('deliberate test forecast failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(study.decision, 'forecast', fail_once)
    result = study.evaluate_case(tiny_design['cases'][0], tiny_design)
    assert len(result['forecasts']) == len(result['scores']) == 9
    failed = [row for row in result['scores'] if row['status'] != 'ok']
    assert len(failed) == 1
    assert len(result['branches']) == 9
    assert not study.gate_summary([result], tiny_design)['passed']
    one_arena = {**tiny_design, 'cases': tiny_design['cases'][:1]}
    summary, arenas = study.summarize(result['scores'], result['branches'], one_arena)
    condition = next(row for row in summary['conditions'] if row['condition'] == failed[0]['condition'])
    assert condition['planned_decisions'] == 3
    assert condition['valid_plans'] == 2 and condition['failed_plans'] == 1
    assert condition['metrics']['utility'] == {
        'n_arenas': 1, 'valid_arenas': 0, 'mean': None, 'ci95': None,
    }
    assert summary['n_arenas'] == 1 and len(arenas) == 3
    assert summary['primary']['n_arenas'] == 1
    assert summary['primary']['valid_arenas'] == 0
    assert summary['primary']['mean'] is None


def test_three_focal_rotations_are_averaged_before_arena_bootstrap(tiny_case, tiny_design):
    scores, branches = [], []
    for index, case in enumerate(tiny_design['cases']):
        for saved in tiny_case['scores']:
            row = {**saved, 'arena_id': case['arena_id']}
            base = ((0., 0., 3.), (10., 10., 40.))[index][row['focal']]
            row['utility'] = 0. if row['condition'] == 'prior' else base + (row['condition'] == 'known')
            scores.append(row)
        branches.extend({**row, 'arena_id': case['arena_id']} for row in tiny_case['branches'])
    summary, arenas = study.summarize(scores, branches, tiny_design)
    learned = [row for row in arenas if row['condition'] == 'learned']
    assert [row['utility'] for row in learned] == [1., 20.]
    assert all(row['n_focals'] == 3 for row in learned)
    assert summary['primary'] == {
        'mean': 10.5, 'ci95': [1., 20.], 'n_arenas': 2, 'valid_arenas': 2,
    }
    assert summary['n_arenas'] == 2
    assert summary['n_focal_decisions'] == summary['n_branches'] == 18
    assert summary['independent_evolutionary_runs'] == summary['model_generation_calls'] == 0
    with pytest.raises(ValueError, match='Score grid'):
        study.summarize(scores[:-1], branches, tiny_design)
    with pytest.raises(ValueError, match='Branch grid'):
        study.summarize(scores, branches[:-1], tiny_design)


def robust_gate_cases(tiny_case, tiny_design):
    """Construct transparent action values to test the development rule itself."""
    cases = []
    for index, description in enumerate(tiny_design['cases']):
        case = deepcopy(tiny_case)
        case['arena_id'] = description['arena_id']
        for item in case['gate_forecasts']:
            for label, action, gap in (('low', 0., -.02), ('high', 1., .02)):
                item[label]['status'] = 'ok'
                item[label]['action'] = action
                extreme = next(row for row in item[label]['paired'] if row['public_fraction'] == 1.)
                extreme.update(minus_redistribute=gap, paired_mcse=.001)
        for branch in case['branches']:
            branch['utility'] = branch['public_fraction'] * (.02 if index else -.02)
        for forecast in case['forecasts']:
            forecast['status'] = 'ok'
            if forecast['condition'] == 'known':
                forecast['action'] = 1. if index else 0.
        cases.append(case)
    return cases


def test_gate_requires_robust_rank_changes_and_both_realized_extremes(tiny_case, tiny_design):
    cases = robust_gate_cases(tiny_case, tiny_design)
    gate = study.gate_summary(cases, tiny_design)
    assert gate['passed']
    assert gate['counts'] == {
        'rank_switch': 6, 'realized_zero': 3, 'realized_one': 3, 'known_positive_one': 3,
    }
    uncertain = deepcopy(cases)
    for case in uncertain:
        for item in case['gate_forecasts']:
            for row in item['high']['paired']:
                row['paired_mcse'] = .01
    assert not study.gate_summary(uncertain, tiny_design)['passed']
    middle_best = deepcopy(cases)
    for case in middle_best:
        for branch in case['branches']:
            if branch['public_fraction'] == .5:
                branch['utility'] = 1.
    rejected = study.gate_summary(middle_best, tiny_design)
    assert not rejected['passed']
    assert rejected['counts']['realized_zero'] == rejected['counts']['realized_one'] == 0


@pytest.fixture(scope='module')
def tiny_archive(tmp_path_factory, tiny_design):
    directory = tmp_path_factory.mktemp('decision-study-control') / 'evidence'
    canonical_factory = study.make_design

    def test_design_factory(*, development=False, arenas=24):
        if development:
            return deepcopy(tiny_design)
        return canonical_factory(development=False, arenas=arenas)

    with patch.object(study, 'make_design', test_design_factory):
        design = study.prepare(directory, development=True)
        summary = study.run(directory, workers=1)
    return {'directory': directory, 'design': design, 'summary': summary,
            'factory': test_design_factory}


def verify_archive(tiny_archive, directory=None):
    with patch.object(study, 'make_design', tiny_archive['factory']):
        return study.verify(directory or tiny_archive['directory'], workers=1)


def copy_archive(tiny_archive, tmp_path):
    destination = tmp_path / 'evidence'
    shutil.copytree(tiny_archive['directory'], destination)
    return destination


def rehash(directory, relative):
    manifest = json.loads((directory / 'completion.json').read_text())
    manifest['artifact_hashes'][relative] = study.sha(directory / relative)
    study.json_write(directory / 'completion.json', manifest)


def test_complete_tiny_archive_replays_and_checks_frozen_sources(tiny_archive):
    receipt = verify_archive(tiny_archive)
    assert receipt['verified']
    assert receipt['n_arenas'] == receipt['semantic_case_replays'] == 2
    assert receipt['n_focal_decisions'] == receipt['n_branches'] == 18
    assert receipt['model_generation_calls'] == 0
    for name, expected in tiny_archive['design']['source_hashes'].items():
        assert study.sha(tiny_archive['directory'] / 'sources' / name) == expected
        assert study.sha(study.ROOT / name) == expected


def test_failed_completed_gate_blocks_evaluation_preparation(tiny_archive, tmp_path):
    gate = json.loads((tiny_archive['directory'] / 'gate.json').read_text())
    assert not gate['passed']
    original_verify = study.verify
    with patch.object(study, 'make_design', tiny_archive['factory']), \
            patch.object(study, 'verify', lambda directory: original_verify(directory, workers=1)):
        with pytest.raises(ValueError, match='gate has not passed'):
            study.prepare(tmp_path / 'evaluation', development_gate=tiny_archive['directory'])
    assert not (tmp_path / 'evaluation').exists()
    with pytest.raises(ValueError, match='requires a completed passing development gate'):
        study.prepare(tmp_path / 'missing-gate')


def test_completed_and_frozen_studies_cannot_be_overwritten(tiny_archive):
    directory = tiny_archive['directory']
    before = {str(path.relative_to(directory)): study.sha(path)
              for path in directory.rglob('*') if path.is_file()}
    with pytest.raises(ValueError, match='Completed studies cannot be overwritten'):
        study.run(directory, workers=1)
    with pytest.raises(ValueError, match='fresh empty output directory'):
        study.prepare(directory, development=True)
    assert before == {str(path.relative_to(directory)): study.sha(path)
                      for path in directory.rglob('*') if path.is_file()}


def test_failed_forecasts_leave_full_case_records_but_block_completion(tiny_archive, tmp_path):
    directory = tmp_path / 'failed-plans'
    with patch.object(study, 'make_design', tiny_archive['factory']), \
            patch.object(study.decision, 'forecast', side_effect=ValueError('deliberate planning failure')):
        design = study.prepare(directory, development=True)
        with pytest.raises(ValueError, match='retained; completion is prohibited'):
            study.run(directory, workers=1)
    assert not (directory / 'completion.json').exists()
    for case in design['cases']:
        record = study.packed_read(directory / 'cases' / case['arena_id'] / 'case.json.gz')
        assert len(record['scores']) == len(record['branches']) == 9
        assert all(row['status'] == 'failed' for row in record['scores'])
    summary = json.loads((directory / 'summary.json').read_text())
    assert summary['n_arenas'] == 2
    assert summary['n_focal_decisions'] == 18
    assert summary['primary'] == {'n_arenas': 2, 'valid_arenas': 0, 'mean': None, 'ci95': None}
    for condition in summary['conditions']:
        assert condition['planned_decisions'] == condition['failed_plans'] == 6
        assert condition['valid_plans'] == 0


@pytest.mark.parametrize('mutation', [
    'legal_current_growth', 'learned_evidence', 'forecast_action', 'branch_utility',
    'sensor_rng', 'ownership', 'commitment',
])
def test_semantic_case_tampering_fails_after_manifest_hash_rewrite(
        tiny_archive, tmp_path, mutation):
    directory = copy_archive(tiny_archive, tmp_path)
    case = tiny_archive['design']['cases'][0]
    relative = f'cases/{case["arena_id"]}/case.json.gz'
    record = study.packed_read(directory / relative)
    if mutation == 'legal_current_growth':
        record['legal_observations']['0']['last_growth']['tick'] += 1
    elif mutation == 'learned_evidence':
        record['warmup']['learned_models']['0']['evidence'][0]['growth'] += 1.
    elif mutation == 'forecast_action':
        record['forecasts'][0]['action'] = .25
    elif mutation == 'branch_utility':
        record['branches'][0]['utility'] += 1.
    elif mutation == 'sensor_rng':
        record['checkpoint']['sensor_rng']['state']['state'] += 1
    elif mutation == 'ownership':
        owners = record['checkpoint']['sharing']['owners']
        owners[next(iter(owners))] = []
    else:
        record['forecast_commitment_sha256'] = '0' * 64
    study.packed_write(directory / relative, record)
    rehash(directory, relative)
    with pytest.raises(ValueError, match='semantic reconstruction differs'):
        verify_archive(tiny_archive, directory)


@pytest.mark.parametrize('artifact,expected_error', [
    ('scores.csv', 'aggregate table differs'),
    ('summary.json', 'summary differs'),
    ('gate.json', 'gate differs'),
])
def test_derived_evidence_tampering_fails_after_hash_rewrite(
        tiny_archive, tmp_path, artifact, expected_error):
    directory = copy_archive(tiny_archive, tmp_path)
    path = directory / artifact
    if artifact.endswith('.csv'):
        path.write_bytes(path.read_bytes() + b'\n')
    else:
        value = json.loads(path.read_text())
        if artifact == 'summary.json':
            value['primary']['mean'] += 1.
        else:
            value['passed'] = not value['passed']
        study.json_write(path, value)
    rehash(directory, artifact)
    with pytest.raises(ValueError, match=expected_error):
        verify_archive(tiny_archive, directory)


def test_rehashed_design_cannot_change_frozen_numerical_contract(tiny_archive, tmp_path):
    directory = copy_archive(tiny_archive, tmp_path)
    design = json.loads((directory / 'design.json').read_text())
    design['planner_samples'] += 1
    study.json_write(directory / 'design.json', design)
    (directory / 'design.sha256').write_text(study.sha(directory / 'design.json') + '\n')
    rehash(directory, 'design.json')
    rehash(directory, 'design.sha256')
    with pytest.raises(ValueError, match='Frozen decision contract differs: planner_samples'):
        verify_archive(tiny_archive, directory)
