"""Recover interrupted frozen runs without silently refitting saved evidence."""

import json
from pathlib import Path
import shutil

import pytest

from scripts import resume_world_model_sharing as recovery
from scripts import run_world_model_sharing as frozen


@pytest.fixture(scope='module')
def saved_cases(tmp_path_factory):
    directory = tmp_path_factory.mktemp('sharing-recovery-source')
    design = frozen.prepare(directory, arenas=2, ticks=8, development=True)
    design['learner_settings'] = {'n_particles':32, 'rejuvenation_steps':1, 'ess_fraction':.5}
    design['n_probes'], design['forecast_samples'] = 4, 32
    frozen.json_write(directory/'design.json', design)
    (directory/'design.sha256').write_text(frozen.sha(directory/'design.json')+'\n')
    for case in design['cases']:
        frozen.run_case((directory, case, design))
    return directory, design


def interrupted_copy(saved_cases, tmp_path):
    source, design = saved_cases
    directory = tmp_path/'evidence'
    shutil.copytree(source, directory)
    partial = directory/'cases'/design['cases'][1]['arena_id']
    shutil.rmtree(partial)
    partial.mkdir()
    (partial/'data.json.gz').write_bytes(b'preserve this interrupted original artifact')
    (directory/'checkpoints.csv').write_bytes(b'preserve unfinished aggregate')
    return directory, design


def test_resume_reuses_verified_case_archives_partial_and_completes_frozen_verifier(
        saved_cases, tmp_path, monkeypatch):
    directory, design = interrupted_copy(saved_cases, tmp_path)
    first = design['cases'][0]['arena_id']
    second = design['cases'][1]['arena_id']
    original = recovery._inventory(directory/'cases'/first)
    calls = []
    actual_dispatch = recovery._dispatch

    def dispatch(tasks, workers):
        calls.extend(task[1]['arena_id'] for task in tasks)
        yield from actual_dispatch(tasks, workers)

    monkeypatch.setattr(recovery, '_dispatch', dispatch)
    root = tmp_path/'recovery'
    summary = recovery.resume(directory, workers=1, recovery_dir=root)
    assert calls == [second]
    assert summary['n_arenas'] == 2
    assert recovery._inventory(directory/'cases'/first) == original
    result = frozen.verify(directory)
    assert result['verified'] and result['arenas'] == 2
    session, = root.iterdir()
    assert (session/'archived/cases'/second/'data.json.gz').read_bytes() == (
        b'preserve this interrupted original artifact')
    assert (session/'archived/checkpoints.csv').read_bytes() == b'preserve unfinished aggregate'
    manifest = json.loads((session/'recovery.json').read_text())
    assert manifest['status'] == 'complete'
    assert manifest['reused_cases'] == [first]
    assert manifest['recomputed_cases'] == [second]
    for name, digest in manifest['archived_artifacts'].items():
        assert frozen.sha(session/'archived'/name) == digest
    completion = json.loads((directory/'completion.json').read_text())
    assert completion['original_full_wall_seconds'] is None
    assert 'recovery session only' in completion['elapsed_seconds_scope']
    assert completion['elapsed_seconds'] > 0
    assert completion['recovery']['reused_cases'] == [first]
    assert not any('recovery' in name for name in completion['artifacts'])


def test_corrupt_complete_case_fails_before_archiving_or_dispatch(saved_cases, tmp_path, monkeypatch):
    directory, design = interrupted_copy(saved_cases, tmp_path)
    data_path = directory/'cases'/design['cases'][0]['arena_id']/'data.json.gz'
    data = frozen.packed_read(data_path)
    data['packets'][0]['growth'] += 1
    frozen.packed_write(data_path, data)
    original = recovery._inventory(directory)

    def forbidden_dispatch(*args):
        raise AssertionError('Corrupt complete cases must not be silently recomputed')

    monkeypatch.setattr(recovery, '_dispatch', forbidden_dispatch)
    with pytest.raises(ValueError, match='Regenerated arena data differs'):
        recovery.resume(directory, workers=1, recovery_dir=tmp_path/'recovery')
    assert recovery._inventory(directory) == original
    session, = (tmp_path/'recovery').iterdir()
    assert not (session/'archived').exists()
    assert json.loads((session/'recovery.json').read_text())['status'] == 'failed'


def test_completed_study_rejects_all_writes(saved_cases, tmp_path, monkeypatch):
    directory, _ = interrupted_copy(saved_cases, tmp_path)
    # Even an unverified completion marker forbids recovery writes.
    (directory/'completion.json').write_text('{}\n')
    original = recovery._inventory(directory)
    with pytest.raises(ValueError, match='Completed sharing study exists'):
        recovery.resume(directory, recovery_dir=tmp_path/'recovery')
    assert recovery._inventory(directory) == original
    assert not (tmp_path/'recovery').exists()


def test_recovery_requires_live_frozen_sources(saved_cases, tmp_path, monkeypatch):
    directory, _ = interrupted_copy(saved_cases, tmp_path)
    original = recovery._inventory(directory)
    checks = []

    def changed_sources(path, live=False):
        checks.append(live)
        raise ValueError('Frozen sharing source mismatch: changed source')

    monkeypatch.setattr(frozen, 'check_design', changed_sources)
    with pytest.raises(ValueError, match='Frozen sharing source mismatch'):
        recovery.resume(directory, recovery_dir=tmp_path/'recovery')
    assert checks == [True]
    assert recovery._inventory(directory) == original
    assert not (tmp_path/'recovery').exists()


def test_recovery_lock_prevents_competing_resumes(tmp_path):
    directory = tmp_path/'evidence'
    with recovery._exclusive_recovery(directory):
        with pytest.raises(ValueError, match='Another recovery process'):
            with recovery._exclusive_recovery(directory):
                pytest.fail('Competing recovery acquired the same lock')


def test_original_worker_guard_matches_output_and_ignores_other_studies(tmp_path, monkeypatch):
    target = tmp_path/'evidence'

    class Process:
        pid = 9000001
        info = {'pid':pid, 'cmdline':['python', 'scripts/run_world_model_sharing.py',
            'run', '--output', str(target)]}

    monkeypatch.setattr(recovery.psutil, 'process_iter', lambda attrs: [Process()])
    with pytest.raises(ValueError, match='Sharing runner still active'):
        recovery._assert_no_active_runner(target)
    recovery._assert_no_active_runner(tmp_path/'other-study')


def test_recovery_archive_cannot_contaminate_evidence(tmp_path):
    directory = tmp_path/'evidence'
    with pytest.raises(ValueError, match='outside the evidence directory'):
        recovery.resume(directory, recovery_dir=directory/'recovery')
    assert not directory.exists()
