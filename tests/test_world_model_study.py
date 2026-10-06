"""Evidence boundaries and reconstruction checks for the identification control."""

from copy import deepcopy
import json
import shutil

import numpy as np
import pytest

from scripts import run_world_model_study as study


@pytest.fixture(scope='module')
def completed_study(tmp_path_factory):
    directory = tmp_path_factory.mktemp('world-model-study')
    design = study.prepare(directory, arenas=1, ticks=8, particles=64, development=True)
    calls = []
    instances = []
    original = study.RenewalSMC

    class TrackedLearner(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.label = ('prior', 'pooled', 'private-0', 'private-1', 'private-2')[len(instances)]
            instances.append(self)

        def predict(self, query, *args, **kwargs):
            calls.append(('predict', self.label, dict(query)))
            return super().predict(query, *args, **kwargs)

        def update(self, observation):
            calls.append(('update', self.label, dict(observation)))
            return super().update(observation)

    study.RenewalSMC = TrackedLearner
    try:
        summary = study.run(directory)
    finally:
        study.RenewalSMC = original
    return directory, design, summary, calls


def copied_study(completed_study, tmp_path):
    directory = tmp_path/'evidence'
    shutil.copytree(completed_study[0], directory)
    return directory


def refresh_artifact_hash(directory, relative):
    """Simulate a tamperer updating checksums: semantic verification must still fail."""
    completion = json.loads((directory/'completion.json').read_text())
    completion['artifacts'][relative] = study.sha(directory/relative)
    study.json_write(directory/'completion.json', completion)


def test_query_allowlist_excludes_outcomes_and_privileged_truth():
    query = {'stock_before': 4., 'capacity': 30., 'own_infrastructure': .5, 'other_infrastructure': .2}
    untrusted = {**query, 'growth': 12., 'target': 15., 'true_growth': 12.,
                 'world_parameters': {'r': 5.}, 'weather': 1.13, 'seed': 732,
                 'regime': .4, 'censored': False, 'stock_after': 16.}
    assert study.query_from(untrusted) == query


def test_probes_share_arena_laws_and_keep_inputs_independent_of_truth(completed_study):
    _, design, _, _ = completed_study
    case = design['cases'][0]
    original = study.make_probes(case, design)
    changed = deepcopy(case)
    changed['world_parameters']['b'] += .1
    alternative = study.make_probes(changed, design)
    assert original == study.make_probes(case, design)
    assert len({p['probe_id'] for p in original}) == design['n_probes']
    assert sum(p['probe_group'] == 'uncapped' for p in original) == 32
    for before, after in zip(original, alternative):
        assert study.query_from(before) == study.query_from(after)
        if before['probe_group'] == 'uncapped':
            assert after['target']-before['target'] == pytest.approx(.1*before['own_infrastructure'])


def test_shadow_updates_are_private_and_all_same_tick_predictions_precede_updates(completed_study):
    _, design, _, calls = completed_study
    updates = [(i, label, packet) for i, (kind, label, packet) in enumerate(calls) if kind == 'update']
    assert len(updates) == design['config']['ticks']*6
    for _, label, packet in updates:
        assert label != 'prior'
        assert not {'true_growth', 'world_parameters', 'weather', 'seed', 'regime', 'censored'} & packet.keys()
        if label.startswith('private-'):
            assert int(label.split('-')[1]) == packet['patch']
    for _, label, query in (call for call in calls if call[0] == 'predict'):
        assert set(query) == {'stock_before', 'capacity', 'own_infrastructure', 'other_infrastructure'}
    for tick in range(design['config']['ticks']):
        group = [(i, label, packet) for i, label, packet in updates if packet['tick'] == tick]
        first = group[0][0]
        preceding = calls[first-9:first]
        assert all(kind == 'predict' for kind, _, _ in preceding)
        assert [label for _, label, _ in preceding] == [
            'prior', 'private-0', 'pooled', 'prior', 'private-1', 'pooled', 'prior', 'private-2', 'pooled']
        assert [i for i, _, _ in group] == list(range(first, first+6))
        pooled = [packet['event_id'] for _, label, packet in group if label == 'pooled']
        assert len(set(pooled)) == 3


def test_end_to_end_verifier_reconstructs_probes_scores_and_snapshots(completed_study):
    directory, design, summary, _ = completed_study
    result = study.verify(directory)
    assert result['verified']
    assert result['terminal_snapshot_forecasts'] == 5*design['n_probes']
    assert summary['n_arenas'] == 1
    rows = study.csv_read(directory/'checkpoints.csv')
    initial = [float(row['probe_crps']) for row in rows if int(row['tick']) == 0]
    assert len(set(initial)) == 1
    prior = [float(row['probe_crps']) for row in rows if row['condition'] == 'prior']
    assert len(set(prior)) == 1
    for row in rows:
        expected = {'prior': 0, 'private': int(row['tick']), 'pooled': 3*int(row['tick'])}[row['condition']]
        assert int(row['unique_observations']) == expected
    assert np.isfinite(summary['conditions']['private']['crps_aulc_ticks']['mean'])


def test_frozen_design_edits_are_rejected(completed_study, tmp_path):
    directory = copied_study(completed_study, tmp_path)
    design = json.loads((directory/'design.json').read_text())
    design['cases'][0]['world_parameters']['r'] += .1
    study.json_write(directory/'design.json', design)
    with pytest.raises(ValueError, match='Frozen design checksum'):
        study.verify_design(directory, check_live=False)


@pytest.mark.parametrize('mutation', ['duplicate_society', 'foreign_arena', 'foreign_tick', 'nonfinite'])
def test_summary_requires_exact_checkpoint_identity_and_finite_data(completed_study, mutation):
    directory, design, _, _ = completed_study
    rows = study.csv_read(directory/'checkpoints.csv')
    if mutation == 'duplicate_society':
        rows[1]['society'] = rows[0]['society']
    elif mutation == 'foreign_arena':
        rows[0]['arena_id'] = 'foreign-arena'
    elif mutation == 'foreign_tick':
        rows[0]['tick'] = 999
    else:
        rows[0]['probe_crps'] = float('nan')
    with pytest.raises(ValueError, match='checkpoint'):
        study.summarize(rows, design)


def test_summary_tampering_fails_even_with_rewritten_artifact_checksum(completed_study, tmp_path):
    directory = copied_study(completed_study, tmp_path)
    summary = json.loads((directory/'summary.json').read_text())
    summary['n_arenas'] = 999
    study.json_write(directory/'summary.json', summary)
    refresh_artifact_hash(directory, 'summary.json')
    with pytest.raises(ValueError, match='Summary differs'):
        study.verify(directory)


def test_probe_tampering_fails_after_checksum_rewrite(completed_study, tmp_path):
    directory = copied_study(completed_study, tmp_path)
    rows = study.csv_read(directory/'probes.csv')
    rows[0]['target'] = float(rows[0]['target'])+.5
    study.csv_write(directory/'probes.csv', rows)
    refresh_artifact_hash(directory, 'probes.csv')
    with pytest.raises(ValueError, match='frozen probe target'):
        study.verify(directory)


def test_prediction_arithmetic_tampering_is_rejected(completed_study, tmp_path):
    directory = copied_study(completed_study, tmp_path)
    rows = study.csv_read(directory/'predictions.csv.gz')
    rows[0]['mean'] = float(rows[0]['mean'])+1.
    study.csv_write(directory/'predictions.csv.gz', rows)
    refresh_artifact_hash(directory, 'predictions.csv.gz')
    with pytest.raises(ValueError, match='squared error'):
        study.verify(directory)


def test_private_snapshot_cannot_contain_another_societys_evidence(completed_study, tmp_path):
    directory = copied_study(completed_study, tmp_path)
    arena = completed_study[1]['cases'][0]['arena_id']
    relative = f'snapshots/{arena}-private-0.json'
    snapshot = json.loads((directory/relative).read_text())
    snapshot['evidence'][0]['event_id'] = f'{arena}/growth:0:1'
    study.json_write(directory/relative, snapshot)
    refresh_artifact_hash(directory, relative)
    with pytest.raises(ValueError, match='foreign or privileged evidence'):
        study.verify(directory)
