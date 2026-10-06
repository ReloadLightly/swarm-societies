#!/usr/bin/env python3
"""Recover interrupted world-model-sharing-v1 cases without changing its design.

Complete cases are semantically verified and reused byte-for-byte. Incomplete
cases and unfinished aggregate exports are archived outside the evidence before
the original frozen case runner recomputes them. This is a recovery utility, not
a new experiment, inference allowance, or within-case learner checkpoint resume.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psutil

from scripts import run_world_model_sharing as frozen

VERSION = 'world-model-sharing-recovery-v1'
DEFAULT_RECOVERY = ROOT/'runs/world-model-sharing-recovery'
TABLES = ('checkpoints', 'parameters', 'transport', 'costs')
CASE_FILES = frozenset(('data.json.gz', 'predictions.csv.gz',
    *(name+'.csv' for name in TABLES),
    *(name+'.json.gz' for name in frozen.CONDITIONS)))
AGGREGATES = (*(name+'.csv' for name in TABLES), 'summary.json')


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path, value):
    temporary = path.with_name(path.name+'.tmp')
    frozen.json_write(temporary, value)
    temporary.replace(path)


def _inventory(directory):
    """Relative hashes also detect files unexpectedly added during validation."""
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Recovery refuses evidence symlinks: '+str(path))
        if path.is_file():
            result[str(path.relative_to(directory))] = frozen.sha(path)
    return result


def _assert_no_active_runner(directory):
    """The old runner predates our lock, so also refuse live original workers."""
    names = {'run_world_model_sharing.py', 'resume_world_model_sharing.py'}
    active = []
    for process in psutil.process_iter(['pid', 'cmdline']):
        if process.pid == os.getpid():
            continue
        argv = process.info['cmdline'] or []
        scripts = [i for i, arg in enumerate(argv) if Path(arg).name in names]
        if not scripts:
            continue
        start = scripts[0]
        tail = argv[start+1:]
        if Path(argv[start]).name == 'run_world_model_sharing.py' and (
                not tail or tail[0] != 'run'):
            continue
        output = str(ROOT/'evidence/world-model-sharing-v1')
        for index, arg in enumerate(tail):
            if arg == '--output' and index+1 < len(tail):
                output = tail[index+1]
            elif arg.startswith('--output='):
                output = arg.split('=', 1)[1]
        try:
            target = Path(output)
            if not target.is_absolute():
                target = Path(process.cwd())/target
            if target.resolve() == directory:
                active.append(process.pid)
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise ValueError('Cannot establish whether sharing runner is active') from exc
    if active:
        raise ValueError('Sharing runner still active for this evidence directory; PIDs: '+
                         ', '.join(map(str, active)))


@contextmanager
def _exclusive_recovery(directory):
    # A fixed location makes --recovery-dir variations use the same output lock.
    lock_root = DEFAULT_RECOVERY/'.locks'
    lock_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(directory).encode()).hexdigest()
    with (lock_root/(key+'.lock')).open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another recovery process holds this evidence lock') from exc
        try:
            _assert_no_active_runner(directory)
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _dispatch(tasks, workers):
    if not tasks:
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(frozen.run_case, tasks)


def resume(directory, workers=4, recovery_dir=None):
    directory = Path(directory).resolve()
    recovery_root = Path(recovery_dir or DEFAULT_RECOVERY).resolve()
    if workers < 1:
        raise ValueError('Need at least one worker')
    if recovery_root == directory or directory in recovery_root.parents:
        raise ValueError('Recovery archive must be outside the evidence directory')
    if (directory/'completion.json').exists():
        raise ValueError('Completed sharing study exists; verify instead of resuming')
    with _exclusive_recovery(directory):
        if (directory/'completion.json').exists():
            raise ValueError('Completed sharing study exists; verify instead of resuming')
        design = frozen.check_design(directory, live=True)
        frozen._verify_design_contract(design)
        started = time.perf_counter()
        recovery_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        session = recovery_root/(stamp+'-'+uuid.uuid4().hex[:8])
        session.mkdir()
        shutil.copyfile(__file__, session/'resume_world_model_sharing.py')
        manifest_path = session/'recovery.json'
        manifest = {'recovery_version':VERSION, 'study':frozen.VERSION,
            'output':str(directory), 'started_utc':_utc(), 'workers':workers,
            'design_sha256':frozen.sha(directory/'design.json'),
            'runner_sha256':frozen.sha(session/'resume_world_model_sharing.py'),
            'status':'verifying_saved_cases', 'reused_cases':[], 'recomputed_cases':[],
            'archived_artifacts':{}, 'model_generation_calls':0,
            'original_full_wall_seconds':None,
            'elapsed_scope':'This recovery session only; original full wall time unavailable.'}
        _atomic_json(manifest_path, manifest)
        try:
            case_root = directory/'cases'
            expected = {case['arena_id'] for case in design['cases']}
            if case_root.exists() and ({path.name for path in case_root.iterdir()}-expected):
                raise ValueError('Unexpected case directory outside frozen case grid')
            saved = _inventory(directory)
            outcomes, reused_hashes, pending, partials = {}, {}, [], []
            for case in design['cases']:
                arena = case['arena_id']
                case_dir = case_root/arena
                if case_dir.exists() and not case_dir.is_dir():
                    raise ValueError('Case path is not a directory: '+str(case_dir))
                present = {path.name for path in case_dir.iterdir()} if case_dir.exists() else set()
                if CASE_FILES <= present:
                    if present != CASE_FILES:
                        raise ValueError('Unexpected artifact in complete case: '+arena)
                    _, outcome, _ = frozen._verify_case(directory, case, design)
                    outcomes[arena] = outcome
                    manifest['reused_cases'].append(arena)
                    reused_hashes.update({name:digest for name,digest in saved.items()
                                         if name.startswith('cases/'+arena+'/')})
                    _atomic_json(manifest_path, manifest)
                    print(json.dumps({'verified_saved_case':arena,
                        'reused':len(outcomes), 'elapsed_seconds':round(time.perf_counter()-started,1)}), flush=True)
                else:
                    pending.append(case)
                    if case_dir.exists():
                        partials.append(case_dir)
            # Validate every complete case before moving or overwriting any evidence.
            _assert_no_active_runner(directory)
            if _inventory(directory) != saved:
                raise ValueError('Evidence changed during recovery preflight')
            manifest['status'] = 'archiving_partial_work'
            manifest['recomputed_cases'] = [case['arena_id'] for case in pending]
            targets = partials+[directory/name for name in AGGREGATES if (directory/name).exists()]
            for source in targets:
                relative = source.relative_to(directory)
                destination = session/'archived'/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                prefix = str(relative)
                manifest['archived_artifacts'].update({name:digest for name,digest in saved.items()
                    if name == prefix or name.startswith(prefix+'/')})
                _atomic_json(manifest_path, manifest)
                shutil.move(str(source), str(destination))
            manifest['status'] = 'running_missing_cases'
            _atomic_json(manifest_path, manifest)
            tasks = [(str(directory), case, design) for case in pending]
            for outcome in _dispatch(tasks, workers):
                arena = outcome['arena_id']
                outcomes[arena] = outcome
                manifest['completed_recomputed_cases'] = [case['arena_id'] for case in pending
                    if case['arena_id'] in outcomes]
                _atomic_json(manifest_path, manifest)
                print(json.dumps({'completed_case':arena, 'completed':len(outcomes),
                    'total':len(design['cases']), 'elapsed_seconds':round(time.perf_counter()-started,1)}), flush=True)
            if set(outcomes) != expected:
                raise ValueError('Recovery dispatcher did not return the complete case grid')
            manifest['status'] = 'verifying_recomputed_cases'
            _atomic_json(manifest_path, manifest)
            for case in pending:
                _, outcome, _ = frozen._verify_case(directory, case, design)
                if outcomes[case['arena_id']] != outcome:
                    raise ValueError('Recomputed case outcome differs from semantic verification')
                outcomes[case['arena_id']] = outcome
                print(json.dumps({'verified_recomputed_case':case['arena_id']}), flush=True)
            frozen.check_design(directory, live=True)
            if any(not (directory/name).is_file() or frozen.sha(directory/name) != digest
                   for name,digest in reused_hashes.items()):
                raise ValueError('Previously verified saved evidence changed during recovery')
            tables = {name:[row for case in design['cases'] for row in
                frozen.csv_read(case_root/case['arena_id']/(name+'.csv'))] for name in TABLES}
            summary = frozen.summarize(tables['checkpoints'],tables['transport'],tables['costs'],design)
            for name,rows in tables.items():
                frozen.csv_write(directory/(name+'.csv'),rows)
            frozen.json_write(directory/'summary.json',summary)
            completion = {'study':frozen.VERSION, 'completed_utc':_utc(),
                'elapsed_seconds':time.perf_counter()-started,
                'elapsed_seconds_scope':manifest['elapsed_scope'],
                'original_full_wall_seconds':None, 'workers':workers, 'model_generation_calls':0,
                'outcomes':[outcomes[case['arena_id']] for case in design['cases']],
                'artifacts':_inventory(directory),
                'recovery':{'version':VERSION, 'reused_cases':manifest['reused_cases'],
                    'recomputed_cases':manifest['recomputed_cases'],
                    'runner_sha256':manifest['runner_sha256']}}
            # The completion marker appears only after every case passes validation.
            frozen.json_write(session/'completion.json',completion)
            with tempfile.NamedTemporaryFile(mode='wb', prefix='.sharing-completion-',
                    dir=directory.parent, delete=False) as temporary:
                temporary.write((session/'completion.json').read_bytes())
                completion_temporary = Path(temporary.name)
            try:
                completion_temporary.replace(directory/'completion.json')
            finally:
                completion_temporary.unlink(missing_ok=True)
            manifest.update(status='complete', completed_utc=_utc(),
                resumed_elapsed_seconds=completion['elapsed_seconds'],
                completion_sha256=frozen.sha(directory/'completion.json'))
            _atomic_json(manifest_path, manifest)
            print(json.dumps({'complete':str(directory), 'recovery_manifest':str(manifest_path),
                'n_arenas':summary['n_arenas'], 'reused_cases':len(manifest['reused_cases']),
                'recomputed_cases':len(pending), 'resumed_elapsed_seconds':completion['elapsed_seconds'],
                'original_full_wall_seconds':None}), flush=True)
            return summary
        except BaseException as exc:
            manifest.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                stopped_utc=_utc(), error=f'{type(exc).__name__}: {exc}',
                resumed_elapsed_seconds=time.perf_counter()-started)
            _atomic_json(manifest_path, manifest)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/world-model-sharing-v1')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--recovery-dir', type=Path, default=DEFAULT_RECOVERY)
    args = parser.parse_args()
    resume(args.output, workers=args.workers, recovery_dir=args.recovery_dir)


if __name__ == '__main__':
    main()
