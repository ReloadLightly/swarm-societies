"""Search containment, exact historical fitness, and parent-only commits."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from swarm_societies import consumption_evaluation as consumption
from swarm_societies import evaluation as legacy
from swarm_societies import search_execution_v1 as bounded
from swarm_societies.execution_v1 import ExecutionLimits


ROOT = Path(__file__).resolve().parents[1]
GREEDY = '''def member_policy(obs, state):
    return {'action': 'harvest', 'target': max(obs['patches'], key=lambda p: p['stock'])['id'], 'effort': 1.0}

def institution(obs, state):
    return {'tax_rate': 0., 'public_fraction': 0., 'raid_permission': False}
'''


def context(directory, engine):
    directory.mkdir(parents=True)
    path = directory / 'context.json'
    if engine == 'legacy':
        state = legacy.initialize_context(path, members=2, steps=4)
        state['config']['initial_wealth'] = 20.
        state['search_seeds'] = [101, 202]
        legacy.atomic_json(path, state)
    else:
        cases = deepcopy(consumption.make_search_cases(815)[:2])
        for case in cases:
            case['config'].update(ticks=4, disturbance_tick=2, initial_wealth=20.)
        consumption.initialize_context(path, 'coevolution', 1, 815, cases=cases)
    return path


def write_candidate(directory, source=GREEDY):
    path = directory / 'proposal.py'
    path.write_text(source)
    return path


def read(path):
    return json.loads(path.read_text())


@pytest.mark.parametrize('engine', bounded.ENGINES)
def test_exact_objectives_acceptance_and_feedback_match_trusted_historical_evaluator(tmp_path, engine):
    left = context(tmp_path / 'old', engine)
    right = context(tmp_path / 'bounded', engine)
    candidate = write_candidate(tmp_path)
    original = legacy.evaluate_search if engine == 'legacy' else consumption.evaluate_search
    meaningful = ('evaluation', 'kind', 'target_society', 'target_member', 'program_sha256',
                  'ecological_predecessor_sha256', 'component_hashes', 'accepted', 'valid',
                  'error', 'combined_score', 'incumbent_objective', 'candidate_objective',
                  'paired_gain', 'case_objectives', 'outcomes')
    for index in range(3):
        expected = original(candidate, tmp_path / f'old-job-{index}', left)
        result = bounded.evaluate_search(candidate, tmp_path / f'new-job-{index}', right, engine=engine)
        assert {key: result[key] for key in meaningful} == {key: expected[key] for key in meaningful}
        assert read(tmp_path / f'new-job-{index}' / 'metrics.json')['public'] == read(
            tmp_path / f'old-job-{index}' / 'metrics.json')['public']
        assert result['execution_receipts'] and all(row['status'] == 'ok' for row in result['execution_receipts'])
        for receipt in result['execution_receipts']:
            data = (tmp_path / f'new-job-{index}' / receipt['path']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == receipt['sha256']
        peaks = [read(tmp_path / f'new-job-{index}' / row['path'])['worker']['max_rss_kib']
                 for row in result['execution_receipts']]
        assert result['max_rss_kib'] == max(peaks)
        assert result['worker_rss_reports'] == len(peaks)
    # This fixture includes an actual private-payoff improvement, not just ties.
    assert read(right)['evaluations'][1]['accepted']
    assert read(right)['accepted_member_updates'] == read(left)['accepted_member_updates']
    assert read(right)['accepted_institution_updates'] == read(left)['accepted_institution_updates']


def test_no_candidate_construction_in_parent_and_success_is_idempotent(tmp_path, monkeypatch):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path)
    from swarm_societies.candidate import CandidateProgram
    monkeypatch.setattr(CandidateProgram, '__init__', lambda *args, **kwargs: pytest.fail('parent compilation'))
    result = bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy')
    assert result['valid']
    committed = path.read_bytes()
    monkeypatch.setattr(bounded, 'execute_job', lambda *args, **kwargs: pytest.fail('replayed completed job'))
    assert bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy') == result
    assert path.read_bytes() == committed


@pytest.mark.parametrize('source,limits,expected', [
    ('def member_policy(obs, state):\n    data = [0] * 1000000000\n    return {}\n' +
     'def institution(obs, state):\n    return {}\n', ExecutionLimits(), 'memory_limit'),
    ('def member_policy(obs, state):\n    total = sum(range(100000000000))\n    return {}\n' +
     'def institution(obs, state):\n    return {}\n', replace(ExecutionLimits(), wall_seconds=.5), 'wall_timeout'),
    ('def member_policy(obs, state):\n    while True:\n        pass\n' +
     'def institution(obs, state):\n    return {}\n', ExecutionLimits(), 'candidate_error'),
])
def test_worker_failure_rejects_scheduled_proposal_preserves_incumbent_and_is_idempotent(
        tmp_path, monkeypatch, source, limits, expected):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path)
    bounded.evaluate_search(candidate, tmp_path / 'initial', path, engine='legacy')
    before = read(path)
    candidate.write_text(source)
    result = bounded.evaluate_search(candidate, tmp_path / 'failed', path, engine='legacy', limits=limits)
    assert not result['valid'] and not result['accepted'] and result['combined_score'] == -1e6
    assert expected in result['error']
    after = read(path)
    for key in ('institutions', 'members', 'accepted_member_updates', 'accepted_institution_updates'):
        assert after[key] == before[key]
    assert len(after['evaluations']) == len(before['evaluations']) + 1
    assert result['evaluation'] == 1 and result['kind'] == 'member'
    monkeypatch.setattr(bounded, 'execute_job', lambda *args, **kwargs: pytest.fail('replayed failed job'))
    assert bounded.evaluate_search(candidate, tmp_path / 'failed', path, engine='legacy', limits=limits) == result
    assert len(read(path)['evaluations']) == 2


def test_output_limit_never_accepts_partial_incumbent_metrics(tmp_path):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path)
    before = read(path)
    result = bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy',
                                    limits=replace(ExecutionLimits(), result_bytes=1024))
    assert not result['valid'] and not result['accepted']
    assert 'output_limit' in result['error']
    assert 'case_objectives' not in result
    assert read(path)['members'] == before['members']


def test_bad_source_is_recorded_once_without_constructing_it(tmp_path):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path, 'x' * 70000)
    result = bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy')
    assert not result['valid'] and 'source_read' in result['error']
    assert result['execution_receipts'] == []
    assert bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy') == result


def test_changed_input_and_tampered_receipt_cannot_reuse_a_job_id(tmp_path):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path)
    result = bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy')
    committed = path.read_bytes()
    candidate.write_text(GREEDY + '\n# changed\n')
    with pytest.raises(ValueError, match='different execution inputs'):
        bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy')
    candidate.write_text(GREEDY)
    receipt = tmp_path / 'job' / result['execution_receipts'][0]['path']
    receipt.write_text('{}')
    with pytest.raises(ValueError, match='receipt changed'):
        bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy')
    assert path.read_bytes() == committed


def test_malformed_counter_rejected_before_worker_or_population_commit(tmp_path, monkeypatch):
    path = context(tmp_path / 'context', 'legacy')
    state = read(path)
    state['accepted_member_updates'] = 'invalid'
    legacy.atomic_json(path, state)
    before = path.read_bytes()
    monkeypatch.setattr(bounded, 'execute_job', lambda *args, **kwargs: pytest.fail('malformed context executed'))
    with pytest.raises(ValueError, match='counter'):
        bounded.evaluate_search(write_candidate(tmp_path), tmp_path / 'job', path, engine='legacy')
    assert path.read_bytes() == before


@pytest.mark.parametrize('mutation', ['society_bound', 'member_bound', 'matrix_shape', 'path_type'])
def test_invalid_population_inventory_rejected_before_any_source_read(tmp_path, monkeypatch, mutation):
    path = context(tmp_path / 'context', 'legacy')
    state = read(path)
    if mutation == 'society_bound':
        state['config']['n_societies'] = 65
    elif mutation == 'member_bound':
        state['config']['members_per_society'] = 257
    elif mutation == 'matrix_shape':
        state['members'][0] *= 1000
    else:
        state['initial_members'][0][0] = {'source': 'not a path'}
    legacy.atomic_json(path, state)
    before = path.read_bytes()
    monkeypatch.setattr(bounded, 'read_source', lambda *args, **kwargs: pytest.fail('invalid inventory read'))
    with pytest.raises(ValueError, match='population|Population'):
        bounded.evaluate_search(write_candidate(tmp_path), tmp_path / 'job', path, engine='legacy')
    assert path.read_bytes() == before


def test_repeated_source_occurrences_count_against_parent_request_bound(tmp_path, monkeypatch):
    path = context(tmp_path / 'context', 'legacy')
    before = path.read_bytes()
    monkeypatch.setattr(bounded, 'execute_job', lambda *args, **kwargs: pytest.fail('oversize inventory executed'))
    with pytest.raises(ValueError, match='inventory exceeds request byte limit'):
        bounded.evaluate_search(write_candidate(tmp_path), tmp_path / 'job', path, engine='legacy',
                                limits=replace(ExecutionLimits(), request_bytes=1024))
    assert path.read_bytes() == before


def test_output_publication_failure_does_not_commit_population(tmp_path, monkeypatch):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path)
    bounded.evaluate_search(candidate, tmp_path / 'initial', path, engine='legacy')
    before = path.read_bytes()
    monkeypatch.setattr(bounded, '_outputs', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError, match='disk failure'):
        bounded.evaluate_search(candidate, tmp_path / 'job', path, engine='legacy')
    assert path.read_bytes() == before


def test_cli_supports_historical_argument_names_without_authorizing_search(tmp_path):
    path = context(tmp_path / 'context', 'legacy')
    candidate = write_candidate(tmp_path)
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/evaluate_search_bounded_v1.py'),
        '--program_path', str(candidate), '--results_dir', str(tmp_path / 'job'),
        '--context_path', str(path), '--engine', 'legacy'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['valid']
    assert read(tmp_path / 'job' / 'correct.json')['correct']
    assert 'no new model-search allowance' in read(path)['evaluations'][0]['selection_rule']
