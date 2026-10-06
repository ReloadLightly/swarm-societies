"""Independent cost, timing, ablation and archive controls for active probes."""
from copy import deepcopy
import gc
import json
from pathlib import Path
import shutil
from unittest.mock import patch
import weakref

import numpy as np
import pytest

from scripts import run_world_model_experiment as study
from swarm_societies.world_model_v1 import decision


ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_WEIGHTS = {
    'early': (1., 0., 0., 0., 0., 0., 0., 0.),
    'late': (0., 0., 0., 0., 1., 0., 0., 0.),
    'split': (.5, 0., 0., 0., .5, 0., 0., 0.),
    'redistribute': (0.,) * 8,
}


@pytest.fixture(scope='module')
def tiny_design():
    design = study.make_design(development=True)
    design['warmup_ticks'] = design['probe_ticks'] = 8
    design['late_offset'] = 4
    design['horizon'] = 8
    design['planner_samples'] = design['selector_samples'] = 32
    design['prediction_samples'] = 32
    design['n_probes'] = 4
    design['learner_settings'] = {
        'n_particles': 32, 'rejuvenation_steps': 1, 'ess_fraction': .5,
    }
    design['config']['ticks'] = 24
    design['config']['disturbance_tick'] = 12
    design['cases'] = design['cases'][:2]
    return design


@pytest.fixture(scope='module')
def tiny_case(tiny_design):
    return study.evaluate_case(tiny_design['cases'][0], tiny_design)


def test_prior_decision_sources_remain_byte_identical():
    frozen = json.loads((ROOT / 'evidence/world-model-decision-v1/design.json').read_text())
    for name, expected in frozen['source_hashes'].items():
        assert study.sha(ROOT / name) == expected, name


def test_smoke_numerics_do_not_change_canonical_protocol_defaults(tiny_design):
    design = study.make_design(development=True)
    assert design['warmup_ticks'] == design['probe_ticks'] == 8
    assert design['late_offset'] == 4
    assert design['horizon'] == 32
    assert design['planner_samples'] == design['selector_samples'] == 512
    assert design['learner_settings']['n_particles'] == 1024
    assert design['learner_settings']['rejuvenation_steps'] == 4
    assert len(design['cases']) == 6
    assert tiny_design['horizon'] == 8
    evaluation = study.make_design(development=False)
    assert len(evaluation['cases']) == 24
    for field in ('arena_id', 'environment_seed'):
        assert not {case[field] for case in design['cases']} & {
            case[field] for case in evaluation['cases']}


def test_exact_escrow_tranches_zero_probe_tax_and_opportunity_baseline(tiny_case):
    assert len(tiny_case['paths']) == 12
    for path in tiny_case['paths']:
        focal, schedule = path['focal'], path['schedule']
        escrow = tiny_case['legal_observations'][str(focal)]['treasury']
        assert escrow > 0.
        assert path['escrow'] == escrow
        assert path['cost_matched'] == (schedule != 'redistribute')
        records = path['probe_records']
        assert [record['tick'] for record in records] == list(range(8, 16))
        spent = 0.
        for offset, record in enumerate(records):
            receipt = record['institution_receipt']
            expected = escrow * SCHEDULE_WEIGHTS[schedule][offset]
            assert receipt['investment'] == pytest.approx(expected, abs=1e-12)
            spent += expected
            assert receipt['tax'] == receipt['contribution'] == receipt['aid_received'] == 0.
            assert receipt['defense_expenditure'] == 0.
            distributed = escrow if schedule == 'redistribute' and offset == 0 else 0.
            assert receipt['redistribution'] == pytest.approx(distributed, abs=1e-12)
            remaining = 0. if schedule == 'redistribute' else escrow - spent
            assert receipt['treasury_after'] == pytest.approx(remaining, abs=1e-12)
            assert all(member['tax'] == 0. for member in record['member_receipts'])
        assert records[-1]['institution_receipt']['treasury_after'] == 0.
        assert path['metrics']['actual_experiment_investment'] == pytest.approx(
            0. if schedule == 'redistribute' else escrow, abs=1e-12)


def test_nonfocal_escrows_redistribute_once_and_never_fund_probe_investment(tiny_case):
    for path in tiny_case['paths']:
        receipts = path['checkpoint']['world']['state']['institution_receipts']
        for society in range(3):
            if society == path['focal']:
                continue
            escrow = tiny_case['legal_observations'][str(society)]['treasury']
            probe = [row for row in receipts if row['society_id'] == society and 8 <= row['tick'] < 16]
            assert len(probe) == 8
            assert all(row['investment'] == row['tax'] == row['treasury_after'] == 0. for row in probe)
            assert [row['redistribution'] for row in probe] == [escrow] + [0.] * 7


def test_every_path_receives_only_its_own_lagged_events_and_matched_wire_budget(tiny_case):
    initial = tiny_case['checkpoint']['sharing']
    initial_bytes = sum(frame['bytes'] for frame in initial['frames'])
    wire_increments = []
    for path in tiny_case['paths']:
        focal = path['focal']
        previous = tiny_case['warmup']['institution_models'][str(focal)]
        assert path['pre_model'] == previous
        assert len(previous['evidence']) == 8
        received = path['post_model']['evidence']
        assert len(received) == 16
        canonical = {packet['event_id']: packet for packet in tiny_case['warmup']['packets']}
        canonical.update({packet['event_id']: packet for record in path['probe_records']
                          for packet in record['packets']})
        for row in received:
            packet = canonical[row['event_id']]
            assert packet['patch'] == focal and packet['tick'] < 16
            assert row['growth'] == packet['growth']
            assert row['headroom'] == packet['capacity'] - packet['stock_before']
        obs = path['legal_observation']
        decision.validate_observation(obs)
        assert obs['tick'] == 16
        assert obs['last_growth']['tick'] == 15
        assert obs['last_growth']['patch'] == focal
        assert obs['last_growth']['event_id'] in {row['event_id'] for row in received}
        sharing = path['checkpoint']['sharing']
        deliveries = [frame for frame in sharing['frames']
                      if frame['recipient'] == f'institution:{focal}'
                      and frame['event_id'] == obs['last_growth']['event_id']]
        assert deliveries and all(frame['status'] == 'delivered' for frame in deliveries)
        assert all(frame['delivery_tick'] == 16 for frame in deliveries)
        assert all(frame['bytes'] == 1024 and frame['payload_bytes'] <= 1024
                   for frame in sharing['frames'])
        wire_increments.append(sum(frame['bytes'] for frame in sharing['frames']) - initial_bytes)
    assert len(set(wire_increments)) == 1
    assert wire_increments[0] == 3 * 8 * (2 + 8) * 1024


def test_counterfactual_probe_ids_are_disjoint_but_warmup_provenance_is_shared(tiny_case):
    warmup = {row['event_id'] for row in tiny_case['warmup']['packets']}
    assert len(warmup) == 24
    previously_seen = set()
    for path in tiny_case['paths']:
        new_ids = {packet['event_id'] for record in path['probe_records'] for packet in record['packets']}
        assert len(new_ids) == 24
        assert not new_ids & previously_seen
        assert not new_ids & warmup
        previously_seen.update(new_ids)
        assert warmup <= set(path['checkpoint']['sharing']['store'])
        assert set(path['checkpoint']['sharing']['store']) == warmup | new_ids
        initial_ids = {packet['event_id'] for packet in path['pre_model']['evidence']}
        assert initial_ids == {packet['event_id'] for packet in
            tiny_case['warmup']['institution_models'][str(path['focal'])]['evidence']}


def test_frozen_updated_and_known_forecasts_use_the_declared_coefficient_sources(tiny_case):
    truth = [tiny_case['case']['world_parameters'][key] for key in ('r', 'b', 'g')]
    for path in tiny_case['paths']:
        assert {forecast['belief'] for forecast in path['forecasts']} == {'frozen', 'updated', 'known'}
        for forecast in path['forecasts']:
            if forecast['belief'] == 'known':
                assert forecast['coefficient_draws'] == [truth] * 32
            else:
                snapshot = path['pre_model'] if forecast['belief'] == 'frozen' else path['post_model']
                expected = study.sample_coefficients(snapshot, 32, forecast['coefficient_seed'])
                assert forecast['coefficient_draws'] == expected
        assert path['forecast_commitment_sha256'] == study.digest(path['forecasts'])
    assert tiny_case['selector_commitment_sha256'] == study.digest({
        'selections': tiny_case['selections'], 'draws': tiny_case['selector_draws'],
        'observations': tiny_case['legal_observations'],
    })


def test_costly_allocation_cannot_change_the_same_tick_renewal_measurement(tiny_case):
    def measurements(packets):
        # Counterfactual paths intentionally have distinct provenance IDs.
        return [{key: value for key, value in packet.items() if key != 'event_id'}
                for packet in packets]

    for focal in range(3):
        paths = {path['schedule']: path for path in tiny_case['paths'] if path['focal'] == focal}
        # All four paths share current growth and sensor noise before the first
        # allocation. Late investment still has no effect on its allocation tick.
        first = [measurements(path['probe_records'][0]['packets']) for path in paths.values()]
        assert all(packets == first[0] for packets in first)
        for offset in range(5):
            assert (measurements(paths['late']['probe_records'][offset]['packets'])
                    == measurements(paths['redistribute']['probe_records'][offset]['packets']))


def test_choices_and_forecasts_are_committed_before_protected_outcomes(tiny_design, monkeypatch):
    select = study.experimentation.select_experiment
    probe = study.probe_path
    forecast = study.decision.forecast
    branch = study.branch_outcomes
    events = []
    forecast_observations = []

    def record_select(*args, **kwargs):
        assert 'probe' not in events
        events.append('select')
        return select(*args, **kwargs)

    def record_probe(checkpoint, *args, **kwargs):
        assert events.count('select') == 9
        assert 'branch' not in events
        saved = deepcopy(checkpoint)
        events.append('probe')
        result = probe(checkpoint, *args, **kwargs)
        assert checkpoint == saved
        return result

    def record_forecast(obs, coefficients, **kwargs):
        assert 'branch' not in events
        assert obs['tick'] == 16 and obs['last_growth']['tick'] == 15
        assert set(obs) == decision.OBS_KEYS
        forecast_observations.append(deepcopy(obs))
        events.append('forecast')
        return forecast(obs, coefficients, **kwargs)

    def record_branch(snapshot, *args, **kwargs):
        assert events.count('probe') == 12
        assert events.count('forecast') == 36
        saved = deepcopy(snapshot)
        events.append('branch')
        result = branch(snapshot, *args, **kwargs)
        assert snapshot == saved
        return result

    monkeypatch.setattr(study.experimentation, 'select_experiment', record_select)
    monkeypatch.setattr(study, 'probe_path', record_probe)
    monkeypatch.setattr(study.decision, 'forecast', record_forecast)
    monkeypatch.setattr(study, 'branch_outcomes', record_branch)
    result = study.evaluate_case(tiny_design['cases'][0], tiny_design)
    assert events.count('select') == 9 and events.count('branch') == 36
    assert result['protected_state_before'] == result['protected_state_after']
    for offset in range(0, len(forecast_observations), 3):
        frozen, updated, known = forecast_observations[offset:offset + 3]
        assert frozen == updated == known


def test_net_utility_contains_probe_consumption_without_double_charging_investment(tiny_case):
    for path in tiny_case['paths']:
        consumed = sum(row['society_metrics']['consumption'] for row in path['probe_records']) / 4
        assert path['metrics']['probe_consumption_per_member'] == pytest.approx(consumed, abs=1e-12)
        assert len(path['scores']) == len(path['branches']) == len(path['forecasts']) == 3
        for score in path['scores']:
            assert score['utility'] == pytest.approx(
                score['consumption_per_member'] + .2 * score['terminal_wealth_per_member'])
            assert score['total_utility'] == pytest.approx(score['utility'] + consumed)
            chosen = next(branch for branch in path['branches']
                          if branch['public_fraction'] == score['action'])
            assert score['utility'] == chosen['utility']
        scores = {row['belief']: row for row in path['scores']}
        assert (scores['updated']['total_utility'] - scores['frozen']['total_utility']
                == pytest.approx(scores['updated']['utility'] - scores['frozen']['utility']))


def test_primary_uses_precommitted_random_choice_and_exact_material_decomposition(tiny_case):
    by_key = {(row['focal'], row['strategy'], row['belief']): row for row in tiny_case['scores']}
    assert len(by_key) == 36
    for selected in tiny_case['selections']:
        if selected['strategy'] == 'fixed':
            assert selected['schedule'] == 'split'
        if selected['strategy'] == 'random':
            index = np.random.default_rng(selected['selection_seed']).integers(3)
            assert selected['schedule'] == ('early', 'late', 'split')[index]
        for belief in ('frozen', 'updated', 'known'):
            score = by_key[selected['focal'], selected['strategy'], belief]
            assert score['schedule'] == selected['schedule']
            path = next(path for path in tiny_case['paths'] if path['focal'] == selected['focal']
                        and path['schedule'] == selected['schedule'])
            physical = next(row for row in path['scores'] if row['belief'] == belief)
            assert score['total_utility'] == physical['total_utility']
    for contrast in tiny_case['contrasts']:
        focal = contrast['focal']
        comparator = contrast['contrast'].removeprefix('active_minus_')
        au, af = (by_key[focal, 'active', belief] for belief in ('updated', 'frozen'))
        cu, cf = (by_key[focal, comparator, belief] for belief in ('updated', 'frozen'))
        update_value = (au['utility'] - af['utility']) - (cu['utility'] - cf['utility'])
        material = af['total_utility'] - cf['total_utility']
        total = au['total_utility'] - cu['total_utility']
        assert contrast['update_value_difference'] == update_value
        assert contrast['frozen_total_utility_difference'] == material
        assert contrast['total_utility_difference'] == total
        assert total == pytest.approx(material + update_value, abs=1e-12)
        if comparator in ('random', 'fixed'):
            assert contrast['experiment_investment_difference'] == 0.


def duplicate_record_for_arena(record, description):
    result = deepcopy(record)
    arena = description['arena_id']
    result['arena_id'] = arena
    result['case'] = deepcopy(description)
    for name in ('scores', 'contrasts'):
        for row in result[name]:
            row['arena_id'] = arena
    for path in result['paths']:
        path['metrics']['arena_id'] = arena
        for name in ('scores', 'branches'):
            for row in path[name]:
                row['arena_id'] = arena
    return result


def test_summary_bootstraps_independent_arenas_after_averaging_focal_update_values(tiny_case, tiny_design):
    records = [duplicate_record_for_arena(tiny_case, case) for case in tiny_design['cases']]
    for index, record in enumerate(records):
        for contrast in record['contrasts']:
            if contrast['contrast'] == 'active_minus_random':
                contrast['update_value_difference'] = ((0., 0., 3.), (10., 10., 40.))[index][contrast['focal']]
    summary, tables = study.summarize(records, tiny_design)
    assert summary['primary'] == {'mean': 10.5, 'ci95': [1., 20.], 'n_arenas': 2, 'valid_arenas': 2}
    assert summary['n_focal_states'] == 6
    assert summary['n_probe_paths'] == 24
    assert summary['n_allocation_continuations'] == 72
    assert summary['n_policy_decisions'] == summary['n_physical_path_forecasts'] == 72
    assert len(tables['arenas']) == 2 * 4 * 3
    assert summary['model_generation_calls'] == summary['independent_evolutionary_runs'] == 0


@pytest.mark.parametrize('missing', ['selection', 'path', 'forecast', 'branch', 'policy_score'])
def test_summary_rejects_missing_nested_records_without_shrinking_denominators(tiny_case, tiny_design, missing):
    record = deepcopy(tiny_case)
    if missing == 'selection':
        record['selections'].pop()
    elif missing == 'path':
        record['paths'].pop()
    elif missing == 'forecast':
        record['paths'][0]['forecasts'].pop()
    elif missing == 'branch':
        record['paths'][0]['branches'].pop()
    else:
        record['scores'].pop()
    design = {**tiny_design, 'cases': tiny_design['cases'][:1]}
    with pytest.raises(ValueError):
        study.summarize([record], design)


def gate_ready_record(tiny_case):
    """Synthetic readiness controls; no positive comparative payoff is required."""
    record = deepcopy(tiny_case)
    for selection in record['selections']:
        if selection['strategy'] == 'active':
            selection['schedule'] = 'late' if selection['focal'] == 1 else 'early'
            for row in selection['scores']:
                row['score'] = 2. if row['schedule'] == selection['schedule'] else 1.
    record['selector_commitment_sha256'] = study.digest({
        'selections': record['selections'], 'draws': record['selector_draws'],
        'observations': record['legal_observations'],
    })
    for index, path in enumerate(record['paths']):
        for row in path['forecasts']:
            row['action'] = 1. if index < 2 and row['belief'] == 'updated' else 0.
        path['forecast_commitment_sha256'] = study.digest(path['forecasts'])
    for contrast in record['contrasts']:
        contrast['update_value_difference'] = -10.
        contrast['total_utility_difference'] = -20.
    return record


def test_development_gate_checks_readiness_without_selecting_for_positive_results(tiny_case, tiny_design):
    record = gate_ready_record(tiny_case)
    gate = study.gate_summary([record], tiny_design)
    assert gate['passed']
    assert gate['counts']['distinct_active_schedules'] == 2
    assert gate['counts']['nonfixed_proxy_advantages'] == 3
    assert gate['counts']['costed_update_action_changes'] == 2
    assert all(row['update_value_difference'] < 0 for row in record['contrasts'])
    for path in record['paths']:
        for row in path['forecasts']:
            row['action'] = 1. if path['schedule'] == 'redistribute' and row['belief'] == 'updated' else 0.
        path['forecast_commitment_sha256'] = study.digest(path['forecasts'])
    gate = study.gate_summary([record], tiny_design)
    assert not gate['passed']
    assert gate['counts']['all_update_action_changes'] == 3
    assert gate['counts']['costed_update_action_changes'] == 0


@pytest.mark.parametrize('violation', ['spending', 'bytes', 'lag', 'forecast_commitment'])
def test_gate_rechecks_recorded_cost_timing_and_commitment_invariants(tiny_case, tiny_design, violation):
    record = gate_ready_record(tiny_case)
    path = record['paths'][0]
    if violation == 'spending':
        path['probe_records'][0]['institution_receipt']['investment'] += 1.
    elif violation == 'bytes':
        path['metrics']['sent_bytes'] += 1024
    elif violation == 'lag':
        path['legal_observation']['last_growth']['tick'] += 1
    else:
        path['forecasts'][0]['action'] = .5
    gate = study.gate_summary([record], tiny_design)
    assert not gate['passed']
    assert not gate['checks']['all_invariants_valid']


@pytest.fixture(scope='module')
def tiny_archive(tmp_path_factory, tiny_design):
    directory = tmp_path_factory.mktemp('experiment-study-control') / 'evidence'
    canonical_factory = study.make_design

    def test_design_factory(*, development=False, arenas=24):
        if development:
            value = deepcopy(tiny_design)
            value['cases'] = value['cases'][:1]
            # This test-only gate cannot pass even if one short-horizon path
            # unexpectedly changes action. Production gate values stay frozen.
            value['gate']['minimum_costed_action_changes'] = 100
            return value
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


def test_tiny_archive_replays_all_probes_learning_and_continuations(tiny_archive):
    receipt = verify_archive(tiny_archive)
    assert receipt['verified']
    assert receipt['n_arenas'] == receipt['semantic_case_replays'] == 1
    assert receipt['n_probe_paths'] == 12
    assert receipt['n_allocation_continuations'] == 36
    assert receipt['model_generation_calls'] == 0
    assert tiny_archive['summary']['n_policy_decisions'] == 36
    for name, expected in tiny_archive['design']['source_hashes'].items():
        assert study.sha(tiny_archive['directory'] / 'sources' / name) == expected
        assert study.sha(study.ROOT / name) == expected


def test_failed_gate_blocks_fresh_evaluation_and_completed_evidence_cannot_be_overwritten(tiny_archive, tmp_path):
    directory = tiny_archive['directory']
    gate = json.loads((directory / 'gate.json').read_text())
    assert not gate['passed']
    verify = study.verify
    with patch.object(study, 'make_design', tiny_archive['factory']), \
            patch.object(study, 'verify', lambda path: verify(path, workers=1)):
        with pytest.raises(ValueError, match='Development gate failed'):
            study.prepare(tmp_path / 'evaluation', development_gate=directory)
    assert not (tmp_path / 'evaluation').exists()
    with pytest.raises(ValueError, match='completed passing development gate'):
        study.prepare(tmp_path / 'missing-gate')
    before = {str(path.relative_to(directory)): study.sha(path)
              for path in directory.rglob('*') if path.is_file()}
    with pytest.raises(ValueError, match='Completed studies cannot be overwritten'):
        study.run(directory, workers=1)
    with pytest.raises(ValueError, match='fresh empty directory'):
        study.prepare(directory, development=True)
    assert before == {str(path.relative_to(directory)): study.sha(path)
                      for path in directory.rglob('*') if path.is_file()}


def test_failed_selection_retains_all_planned_rows_and_blocks_completion(tiny_archive, tmp_path):
    directory = tmp_path / 'failed-selection'
    select = study.experimentation.select_experiment
    calls = []

    def fail_first(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError('deliberate selector failure')
        return select(*args, **kwargs)

    with patch.object(study, 'make_design', tiny_archive['factory']), \
            patch.object(study.experimentation, 'select_experiment', fail_first):
        design = study.prepare(directory, development=True)
        with pytest.raises(ValueError, match='retained; completion is prohibited'):
            study.run(directory, workers=1)
    assert not (directory / 'completion.json').exists()
    record = study.packed_read(directory / 'cases' / design['cases'][0]['arena_id'] / 'case.json.gz')
    assert len(record['selections']) == 9
    assert len(record['paths']) == 12
    assert len(record['scores']) == 36
    assert sum(row['status'] == 'failed' for row in record['scores']) == 3
    summary = json.loads((directory / 'summary.json').read_text())
    assert summary['n_policy_decisions'] == 36
    assert summary['primary'] == {'n_arenas': 1, 'valid_arenas': 0, 'mean': None, 'ci95': None}
    for condition in summary['conditions']:
        if condition['strategy'] == 'active':
            assert condition['failed_plans'] == 1
            assert condition['metrics']['total_utility']['valid_arenas'] == 0


@pytest.mark.parametrize('mutation', [
    'spending', 'crossed_path_evidence', 'current_growth', 'selection',
    'branch', 'heldout_target',
])
def test_semantic_tampering_is_rejected_after_manifest_hash_rewrite(tiny_archive, tmp_path, mutation):
    directory = copy_archive(tiny_archive, tmp_path)
    arena = tiny_archive['design']['cases'][0]['arena_id']
    relative = f'cases/{arena}/case.json.gz'
    record = study.packed_read(directory / relative)
    if mutation == 'spending':
        record['paths'][0]['probe_records'][0]['institution_receipt']['investment'] += .1
    elif mutation == 'crossed_path_evidence':
        record['paths'][0]['post_model']['evidence'][-1] = deepcopy(record['paths'][1]['post_model']['evidence'][-1])
    elif mutation == 'current_growth':
        record['paths'][0]['legal_observation']['last_growth']['tick'] += 1
    elif mutation == 'selection':
        record['selections'][0]['schedule'] = 'redistribute'
    elif mutation == 'branch':
        record['paths'][0]['branches'][0]['utility'] += 1.
    else:
        record['probes'][0]['target'] += 1.
    study.packed_write(directory / relative, record)
    rehash(directory, relative)
    with pytest.raises(ValueError, match='semantic reconstruction differs'):
        verify_archive(tiny_archive, directory)


@pytest.mark.parametrize('artifact,expected_error', [
    ('paths.csv', 'table differs'), ('summary.json', 'summary differs'),
    ('gate.json', 'development gate differs'),
])
def test_derived_tables_summary_and_gate_are_reconstructed_after_hash_rewrite(
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
            value['passed'] = True
        study.json_write(path, value)
    rehash(directory, artifact)
    with pytest.raises(ValueError, match=expected_error):
        verify_archive(tiny_archive, directory)


def test_rehashed_design_cannot_change_frozen_resource_or_numerical_contract(tiny_archive, tmp_path):
    directory = copy_archive(tiny_archive, tmp_path)
    design = json.loads((directory / 'design.json').read_text())
    design['late_offset'] += 1
    study.json_write(directory / 'design.json', design)
    (directory / 'design.sha256').write_text(study.sha(directory / 'design.json') + '\n')
    rehash(directory, 'design.json')
    rehash(directory, 'design.sha256')
    with pytest.raises(ValueError, match='Frozen experiment contract differs: late_offset'):
        verify_archive(tiny_archive, directory)


def test_memory_projection_preserves_every_aggregate_and_gate_result(tiny_case, tiny_design):
    records = [duplicate_record_for_arena(tiny_case, case) for case in tiny_design['cases']]
    projected = [study.project_record(record, tiny_design) for record in records]
    assert study.summarize(projected, tiny_design) == study.summarize(records, tiny_design)
    assert study.gate_summary(projected, tiny_design) == study.gate_summary(records, tiny_design)
    assert len(study.canonical(projected)) < len(study.canonical(records)) / 5

    def nested_keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from nested_keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from nested_keys(item)

    assert not {'checkpoint', 'particles', 'rng_state', 'probe_records',
                'coefficient_draws'} & set(nested_keys(projected))


def test_projection_preserves_failures_and_derives_invariants_from_full_receipts(tiny_case, tiny_design):
    record = deepcopy(tiny_case)
    record['paths'][0]['probe_records'][0]['institution_receipt']['investment'] += .1
    record['paths'][1]['metrics']['failed_updates'] = 1
    # Serialized audit flags cannot override the actual receipt or failure data.
    record['invariant_checks'] = {key: True for key in study.record_invariants(tiny_case, tiny_design)}
    record['_projected_record'] = True
    projected = study.project_record(record, tiny_design)
    assert study.record_invariants(projected, tiny_design) == study.record_invariants(record, tiny_design)
    assert not study.record_invariants(projected, tiny_design)['resource_contract']
    full_gate = study.gate_summary([record], tiny_design)
    projected_gate = study.gate_summary([projected], tiny_design)
    assert full_gate == projected_gate
    assert not projected_gate['passed']
    assert projected_gate['failed_operations'] == 1
    with pytest.raises(ValueError):
        study._assert_no_failed_operations([projected], tiny_design)


def test_serialized_projection_cannot_act_as_a_trusted_full_record(tiny_case, tiny_design):
    projected = study.project_record(tiny_case, tiny_design)
    forged = json.loads(json.dumps(projected))
    forged['invariant_checks'] = {key: True for key in study.record_invariants(tiny_case, tiny_design)}
    forged['_projected_record'] = True
    with pytest.raises((KeyError, ValueError)):
        study.record_invariants(forged, tiny_design)
    with pytest.raises(ValueError, match='requires a full case'):
        study.project_record(projected, tiny_design)


def test_archive_reader_releases_each_full_case_before_decoding_the_next(tiny_case, tiny_design, monkeypatch, tmp_path):
    class TrackedRecord(dict):
        pass

    references = []
    descriptions = {case['arena_id']: case for case in tiny_design['cases']}

    def read_one(path):
        gc.collect()
        assert all(reference() is None for reference in references)
        full = TrackedRecord(duplicate_record_for_arena(tiny_case, descriptions[path.parent.name]))
        references.append(weakref.ref(full))
        return full

    monkeypatch.setattr(study, 'packed_read', read_one)
    records = study._records(tmp_path, tiny_design)
    gc.collect()
    assert len(records) == len(references) == 2
    assert all(reference() is None for reference in references)
    assert {record['arena_id'] for record in records} == set(descriptions)
