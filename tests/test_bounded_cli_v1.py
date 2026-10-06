"""Exercise the public CLI boundary, including a failed batch and safe replay."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'seeds' / 'initial.py').read_text()


def run_cli(*args):
    return subprocess.run([sys.executable, '-m', 'swarm_societies.run_bounded_v1',
                           *map(str, args)], cwd=ROOT, capture_output=True,
                          text=True, timeout=35)


def episode_job():
    return {'kind': 'consumption_episode', 'programs': [{'source': SOURCE}] * 2,
            'config': {'n_societies': 2, 'members_per_society': 2,
                       'ticks': 4, 'disturbance_tick': 2}, 'seed': 19, 'replay': True}


@pytest.mark.skipif(sys.platform != 'linux', reason='Execution v1 requires Linux')
def test_public_replay_and_receipt_never_overwritten(tmp_path):
    config = tmp_path / 'config.json'
    config.write_text(json.dumps(episode_job()['config']))
    receipt = tmp_path / 'replay.json'
    args = ('episode', '--programs', ROOT / 'seeds/initial.py', ROOT / 'seeds/initial.py',
            '--config', config, '--seed', '19', '--replay', '--receipt', receipt)
    result = run_cli(*args)
    assert result.returncode == 0, result.stderr + result.stdout
    saved = receipt.read_bytes()
    data = json.loads(saved)
    assert data['status'] == 'ok'
    assert len(data['result']['replay']) == 4
    assert run_cli(*args).returncode == 2
    assert receipt.read_bytes() == saved


@pytest.mark.skipif(sys.platform != 'linux', reason='Execution v1 requires Linux')
def test_batch_records_failure_and_continues_without_replacing_previous_run(tmp_path):
    path = tmp_path / 'jobs.json'
    path.write_text(json.dumps([{'kind': 'not_allowlisted'}, episode_job()]))
    output = tmp_path / 'batch'
    result = run_cli('batch', '--input', path, '--output', output)
    assert result.returncode == 1, result.stderr
    summary = json.loads((output / 'summary.json').read_text())
    assert (summary['jobs'], summary['succeeded'], summary['failed']) == (2, 1, 1)
    for row in summary['receipts']:
        assert hashlib.sha256((output / row['receipt']).read_bytes()).hexdigest() == row['receipt_sha256']
    before = {file.name: file.read_bytes() for file in output.iterdir()}
    assert run_cli('batch', '--input', path, '--output', output).returncode == 2
    assert {file.name: file.read_bytes() for file in output.iterdir()} == before


def test_oversized_input_fails_before_json_parse(tmp_path):
    path = tmp_path / 'oversized.json'
    path.write_bytes(b' ' * (8 * 1024 * 1024 + 1))
    receipt = tmp_path / 'receipt.json'
    result = run_cli('job', '--input', path, '--receipt', receipt)
    assert result.returncode == 2
    assert 'byte limit' in result.stderr
    assert not receipt.exists()


def test_source_expansion_is_bounded_before_worker_launch(tmp_path, monkeypatch, capsys):
    from swarm_societies import run_bounded_v1 as cli
    limits = tmp_path / 'limits.json'
    limits.write_text(json.dumps({'request_bytes': 1024}))
    reads = []
    def read(path):
        reads.append(path)
        return '#' * 600
    monkeypatch.setattr(cli, 'read_source', read)
    def no_worker(*args, **kwargs):
        pytest.fail('Oversized expanded source job reached worker')
    monkeypatch.setattr(cli, 'execute_job', no_worker)
    result = cli.main(['--limits', str(limits), 'episode', '--programs', 'one.py', 'two.py',
                       '--receipt', str(tmp_path / 'never.json')])
    assert result == 2
    assert len(reads) == 2
    assert 'Inline policy sources exceed request byte limit' in capsys.readouterr().err


def test_member_dimensions_checked_before_policy_files_are_read(tmp_path, monkeypatch, capsys):
    from swarm_societies import run_bounded_v1 as cli
    members = tmp_path / 'members.json'
    members.write_text(json.dumps([['missing.py'] * 1000] * 2))
    def no_source(*args, **kwargs):
        pytest.fail('Invalid member matrix expanded before shape check')
    monkeypatch.setattr(cli, 'read_source', no_source)
    assert cli.main(['episode', '--programs', 'one.py', 'two.py', '--members', str(members),
                     '--receipt', str(tmp_path / 'never.json')]) == 2
    assert 'dimensions' in capsys.readouterr().err


@pytest.mark.skipif(sys.platform != 'linux', reason='Execution v1 requires Linux')
def test_checkpoint_continuation_uses_worker_and_retains_completed_result(tmp_path):
    job = episode_job()
    job.update(kind='stepwise_advance', steps=2)
    job_path, first_path = tmp_path / 'job.json', tmp_path / 'first.json'
    job_path.write_text(json.dumps(job))
    first = run_cli('job', '--input', job_path, '--receipt', first_path)
    assert first.returncode == 0, first.stderr + first.stdout
    first_result = json.loads(first_path.read_text())['result']
    assert first_result['complete'] is False
    snapshot_path, final_path = tmp_path / 'snapshot.json', tmp_path / 'final.json'
    snapshot_path.write_text(json.dumps(first_result['snapshot']))
    saved = snapshot_path.read_bytes()
    final = run_cli('advance', '--snapshot', snapshot_path, '--steps', '2', '--receipt', final_path)
    assert final.returncode == 0, final.stderr + final.stdout
    result = json.loads(final_path.read_text())['result']
    assert result['complete'] is True
    assert len(result['result']['replay']) == 4
    assert snapshot_path.read_bytes() == saved
