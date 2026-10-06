"""Versioned, bounded subprocess execution of allowlisted policy jobs.

This is resource containment, not an OS security sandbox. Candidate syntax is
still checked by the unchanged candidate.py. No callable, pickle, import target,
or filesystem policy path crosses the worker boundary. A candidate_policy job
is one fresh call; consumption_episode retains all policy memory for its whole
episode. Direct in-process APIs remain suitable only for audited trusted code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

VERSION = 'bounded-execution-v1'
WORKER = Path(__file__).with_name('execution_worker_v1.py')
SOURCE_LIMIT_BYTES = 65536
EPISODE_KINDS = frozenset(('legacy_episode', 'consumption_episode', 'world_model_episode',
                           'stepwise_episode'))
JOB_KINDS = EPISODE_KINDS | {'candidate_policy', 'candidate_validate', 'consumption_case',
                             'stepwise_advance', 'runtime_probe'}
SOURCE_FILES = ('execution_v1.py', 'execution_worker_v1.py', 'candidate.py', 'ecology.py',
                'ecology_consumption_v2.py', 'ecology_world_model_v1.py', 'ecology_stepwise_v1.py',
                'consumption_study.py', 'evaluation.py')


@dataclass(frozen=True)
class ExecutionLimits:
    wall_seconds: float = 30.0
    cpu_seconds: int = 15
    memory_bytes: int = 768 * 1024 * 1024
    request_bytes: int = 8 * 1024 * 1024
    result_bytes: int = 16 * 1024 * 1024
    stdout_bytes: int = 64 * 1024
    stderr_bytes: int = 64 * 1024

    def validate(self):
        if (type(self.wall_seconds) not in (int, float) or
                not math.isfinite(self.wall_seconds) or not 0 < self.wall_seconds <= 7200):
            raise ValueError('wall_seconds must be finite, positive and at most 7200')
        bounds = {'cpu_seconds': (1, 3600), 'memory_bytes': (64 * 1024 * 1024, 64 * 1024**3),
                  'request_bytes': (1024, 64 * 1024**2), 'result_bytes': (1024, 128 * 1024**2),
                  'stdout_bytes': (0, 1024 * 1024), 'stderr_bytes': (0, 1024 * 1024)}
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{name} must be an integer in [{low}, {high}]')
        return self


def _plain_json(value, *, depth=0, budget=None):
    """Reject arbitrary Python objects without invoking their methods."""
    if budget is None:
        budget = [500000]
    budget[0] -= 1
    if budget[0] < 0 or depth > 64:
        raise ValueError('JSON structure exceeds node/depth limits')
    kind = type(value)
    if kind in (str, int, bool, type(None)):
        return
    if kind is float:
        if not math.isfinite(value):
            raise ValueError('Nonfinite JSON number')
        return
    if kind is list:
        if len(value) > budget[0]:
            raise ValueError('JSON structure exceeds node limit')
        for child in value:
            _plain_json(child, depth=depth + 1, budget=budget)
        return
    if kind is dict:
        if len(value) > budget[0]:
            raise ValueError('JSON structure exceeds node limit')
        for key, child in value.items():
            if type(key) is not str:
                raise ValueError('JSON object keys must be plain strings')
            _plain_json(child, depth=depth + 1, budget=budget)
        return
    raise ValueError('Only plain JSON values may cross the execution boundary')


def _encode_json(value, limit):
    _plain_json(value)
    # Reject oversized text before JSONEncoder allocates its escaped form.
    stack = [value]
    text_size = 0
    while stack:
        item = stack.pop()
        if type(item) is str:
            text_size += len(item)
            if text_size > limit:
                raise ValueError('JSON exceeds byte limit')
        elif type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
    encoded = bytearray()
    # Dict iteration is observable by candidate programs. Sorting keys here
    # changes policy inputs and the future behavior of restored checkpoints.
    encoder = json.JSONEncoder(allow_nan=False, ensure_ascii=True, separators=(',', ':'))
    for part in encoder.iterencode(value):
        if len(part) > limit - len(encoded):
            raise ValueError('JSON exceeds byte limit')
        encoded.extend(part.encode('ascii'))
    return bytes(encoded)


def bounded_read_bytes(path, max_bytes):
    """Read a regular nonsymlink file, rejecting its size before allocating it."""
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError('max_bytes must be a nonnegative integer')
    descriptor = os.open(os.fspath(path), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Input must be a regular nonsymlink file')
        if info.st_size > max_bytes:
            raise ValueError('Input exceeds byte limit')
        with os.fdopen(descriptor, 'rb', closefd=False) as handle:
            data = handle.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError('Input exceeds byte limit')
        return data
    finally:
        os.close(descriptor)


def bounded_read_json(path, max_bytes=8 * 1024 * 1024):
    value = json.loads(bounded_read_bytes(path, max_bytes).decode('utf-8'),
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
    _plain_json(value)
    return value


def read_source(path, max_bytes=SOURCE_LIMIT_BYTES):
    """Bound source-file reads; compilation and execution occur only in worker."""
    source = bounded_read_bytes(path, min(max_bytes, SOURCE_LIMIT_BYTES)).decode('utf-8')
    if len(source) > 60000:
        raise ValueError('Candidate source exceeds frozen 60000-character limit')
    return source


def atomic_write_receipt(path, receipt):
    """Publish a receipt once, without replacing an incumbent or following links."""
    path = Path(path).absolute()
    if path.name in ('', '.', '..') or path.parent.resolve() != path.parent:
        raise ValueError('Receipt parent must exist without symlink components')
    data = _encode_json(receipt, 160 * 1024 * 1024)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix='.execution-receipt-', dir=path.parent)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        # link is an atomic, no-replace publication, including for dangling links.
        os.link(temporary, path.name, dst_dir_fd=parent, follow_symlinks=False)
        os.fsync(parent)
    finally:
        if temporary is not None:
            os.unlink(temporary)
        os.close(parent)


def _validate_source(source):
    if type(source) is not str or len(source) > 60000:
        raise ValueError('Candidate source must be a string of at most 60000 characters')
    if len(source.encode('utf-8')) > SOURCE_LIMIT_BYTES:
        raise ValueError('Candidate source exceeds 65536 UTF-8 bytes')


def _validate_program(program):
    if type(program) is not dict or set(program) - {'source', 'name'} or 'source' not in program:
        raise ValueError('Program must contain inline source and optional name only')
    _validate_source(program['source'])
    if 'name' in program and (type(program['name']) is not str or len(program['name']) > 256):
        raise ValueError('Program name must be a string of at most 256 characters')


def validate_job(job):
    _plain_json(job)
    if type(job) is not dict or job.get('kind') not in JOB_KINDS:
        raise ValueError('Unknown or malformed allowlisted job')
    kind = job['kind']
    if kind == 'candidate_validate':
        if set(job) != {'kind', 'source'}:
            raise ValueError('candidate_validate accepts only inline source')
        _validate_source(job['source'])
    elif kind == 'candidate_policy':
        if set(job) - {'kind', 'source', 'function', 'observation', 'state', 'max_lines'}:
            raise ValueError('Unexpected candidate_policy field')
        _validate_source(job.get('source'))
        if job.get('function') not in ('member_policy', 'institution'):
            raise ValueError('Only member_policy and institution may be called')
        if type(job.get('observation')) is not dict or type(job.get('state')) is not dict:
            raise ValueError('Policy observation/state must be JSON objects')
        lines = job.get('max_lines', 10000)
        if type(lines) is not int or not 1 <= lines <= 1000000000:
            raise ValueError('max_lines must be an integer in [1, 1000000000]')
    elif kind == 'stepwise_advance' and 'snapshot' in job:
        if set(job) != {'kind', 'snapshot', 'steps'} or type(job['snapshot']) is not dict:
            raise ValueError('Snapshot continuation accepts only snapshot and steps')
        if type(job['steps']) is not int or not 1 <= job['steps'] <= 10000:
            raise ValueError('steps must be an integer in [1, 10000]')
        saved = job['snapshot']
        if (type(saved.get('institutions')) is not list or
                type(saved.get('members')) is not list):
            raise ValueError('Malformed snapshot program inventory')
        for program in saved['institutions']:
            if type(program) is not dict:
                raise ValueError('Malformed snapshot program')
            _validate_source(program.get('source'))
        for row in saved['members']:
            if type(row) is not list:
                raise ValueError('Malformed snapshot members')
            for program in row:
                if type(program) is not dict:
                    raise ValueError('Malformed snapshot program')
                _validate_source(program.get('source'))
    elif kind in EPISODE_KINDS | {'consumption_case', 'stepwise_advance'}:
        allowed = {'kind', 'programs', 'member_programs', 'config', 'seed', 'replay'}
        if kind in ('world_model_episode', 'stepwise_episode', 'stepwise_advance'):
            allowed |= {'world_parameters', 'observation_mode'}
            law = job.get('world_parameters')
            if law is not None:
                if type(law) is not dict or set(law) - {'r', 'b', 'g', 'rho', 'eta', 'h', 'c'}:
                    raise ValueError('Malformed world parameters')
                for name, value in law.items():
                    if name == 'r' and value is None:
                        continue
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError('Invalid world parameter: ' + name)
            if job.get('observation_mode', 'local') not in ('local', 'full_observation_control'):
                raise ValueError('Unknown observation mode')
        if kind == 'stepwise_advance':
            allowed.add('steps')
            if type(job.get('steps')) is not int or not 1 <= job['steps'] <= 10000:
                raise ValueError('steps must be an integer in [1, 10000]')
        if kind == 'consumption_case':
            allowed -= {'config', 'seed'}
            allowed |= {'case', 'disturbance'}
            case = job.get('case')
            if type(case) is not dict or type(case.get('config')) is not dict or type(case.get('seed')) is not int:
                raise ValueError('Consumption case requires config and integer seed')
            if type(job.get('disturbance', True)) is not bool:
                raise ValueError('disturbance must be boolean')
        if set(job) - allowed:
            raise ValueError('Unexpected episode field')
        programs = job.get('programs')
        if type(programs) is not list or not 2 <= len(programs) <= 64:
            raise ValueError('Episode requires 2 to 64 institution programs')
        for program in programs:
            _validate_program(program)
        config = job['case']['config'] if kind == 'consumption_case' else job.get('config', {})
        if type(config) is not dict:
            raise ValueError('Episode config must be a JSON object')
        integer_fields = {'n_societies': (2, 64), 'members_per_society': (2, 256),
                          'ticks': (2, 1000000), 'disturbance_tick': (1, 999999)}
        number_fields = {'initial_wealth', 'initial_patch', 'patch_capacity', 'regeneration',
                         'consumption_need', 'drought_factor'}
        if set(config) - integer_fields.keys() - number_fields - {'enable_disturbance'}:
            raise ValueError('Unknown ecology config field')
        if kind == 'legacy_episode' and 'enable_disturbance' in config:
            raise ValueError('Legacy ecology has no enable_disturbance parameter')
        for name, value in config.items():
            if name in integer_fields:
                low, high = integer_fields[name]
                if type(value) is not int or not low <= value <= high:
                    raise ValueError('Invalid bounded integer config: ' + name)
            elif name in number_fields:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('Invalid numeric config: ' + name)
            elif type(value) is not bool:
                raise ValueError('enable_disturbance must be boolean')
        default_societies = 3 if kind == 'consumption_case' else len(programs)
        if config.get('n_societies', default_societies) != len(programs):
            raise ValueError('Institution count differs from config')
        members = job.get('member_programs')
        if members is not None:
            if type(members) is not list or len(members) != len(programs):
                raise ValueError('Invalid member program matrix')
            for row in members:
                if type(row) is not list or len(row) != config.get('members_per_society', 6):
                    raise ValueError('Member count differs from config')
                for program in row:
                    _validate_program(program)
        if type(job.get('seed', 0)) is not int:
            raise ValueError('Episode seed must be an integer')
        if type(job.get('replay', False)) is not bool:
            raise ValueError('Episode replay must be boolean')
    elif set(job) != {'kind'}:
        raise ValueError('runtime_probe accepts no additional fields')


def _kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def execute_job(job, *, limits=None, receipt_path=None):
    """Execute one plain-JSON job and return an explicit bounded success/failure.

    Configuration errors in limits or receipt paths raise; candidate/job/worker
    failures are receipts. Existing receipt paths are never overwritten.
    """
    limits = (limits if limits is not None else ExecutionLimits()).validate()
    started = time.monotonic()
    receipt = {'version': VERSION, 'status': 'error', 'job_sha256': None,
               'limits': asdict(limits), 'returncode': None, 'stdout': '', 'stderr': '',
               'stdout_truncated': False, 'stderr_truncated': False,
               'runtime': {'python': sys.version, 'executable': sys.executable,
                           'platform': sys.platform, 'machine': platform.machine(),
                           'implementation': platform.python_implementation()},
               'source_sha256': {f'swarm_societies/{name}': hashlib.sha256(
                   bounded_read_bytes(Path(__file__).with_name(name), 1024 * 1024)).hexdigest()
                   for name in SOURCE_FILES}}

    def finish(error=None):
        if error is not None:
            receipt['error'] = {'kind': error[0], 'message': error[1][:2048]}
        receipt['wall_seconds'] = time.monotonic() - started
        if receipt_path is not None:
            atomic_write_receipt(receipt_path, receipt)
        return receipt

    if sys.platform != 'linux':
        return finish(('unsupported_platform', 'This execution version requires Linux resource/process-group semantics'))
    try:
        validate_job(job)
        request = _encode_json(job, limits.request_bytes)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        return finish(('invalid_job', str(exc)))
    receipt['job_sha256'] = hashlib.sha256(request).hexdigest()
    receipt['request_bytes'] = len(request)
    buffers = {name: bytearray() for name in ('stdout', 'stderr', 'result')}
    caps = {'stdout': limits.stdout_bytes, 'stderr': limits.stderr_bytes, 'result': limits.result_bytes}
    failure = None
    process = None
    result_read = result_write = None
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                   'TZ': 'UTC', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
                   'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
                   'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1'}
    try:
        with tempfile.TemporaryDirectory(prefix='swarm-execution-v1-') as directory:
            request_path = Path(directory) / 'request.json'
            request_path.write_bytes(request)
            result_read, result_write = os.pipe()
            process = subprocess.Popen(
                # -I would ignore PYTHONHASHSEED as well as unsafe environment
                # settings. The explicit environment already removes those;
                # -P and -s exclude cwd/script and user-site import paths.
                [sys.executable, '-P', '-s', '-B', str(WORKER), str(request_path), str(result_write),
                 json.dumps(asdict(limits), separators=(',', ':'))],
                cwd=directory, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(result_write,),
                start_new_session=True, close_fds=True)
            os.close(result_write)
            result_write = None
            deadline = started + limits.wall_seconds
            with selectors.DefaultSelector() as selector:
                for stream, name in ((process.stdout, 'stdout'), (process.stderr, 'stderr'),
                                     (result_read, 'result')):
                    os.set_blocking(stream if isinstance(stream, int) else stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, name)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        failure = ('wall_timeout', 'Worker exceeded parent wall deadline')
                        break
                    for key, _ in selector.select(min(remaining, .05)):
                        data = os.read(key.fd, 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        name = key.data
                        space = caps[name] - len(buffers[name])
                        buffers[name].extend(data[:space])
                        if len(data) > space:
                            if name in ('stdout', 'stderr'):
                                receipt[name + '_truncated'] = True
                            failure = ('output_limit', name + ' exceeded byte limit')
                            break
                    if failure:
                        break
            if failure:
                _kill_group(process)
            remaining = max(.01, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                failure = ('wall_timeout', 'Worker exceeded parent wall deadline')
                _kill_group(process)
                process.wait()
            # Also remove surviving descendants holding no monitored descriptors.
            _kill_group(process)
            receipt['returncode'] = process.returncode
    except OSError as exc:
        failure = ('launch_error', f'{type(exc).__name__}: {exc}')
    finally:
        if process is not None:
            _kill_group(process)
            if process.poll() is None:
                process.wait()
            process.stdout.close()
            process.stderr.close()
        for descriptor in (result_read, result_write):
            if descriptor is not None:
                os.close(descriptor)
    for name in ('stdout', 'stderr'):
        receipt[name] = bytes(buffers[name]).decode('utf-8', errors='replace')
    receipt['result_bytes'] = len(buffers['result'])
    if failure:
        return finish(failure)
    if receipt['returncode'] != 0:
        code = receipt['returncode']
        kind = 'cpu_limit' if code == -signal.SIGXCPU else 'worker_death'
        return finish((kind, f'Worker terminated with return code {code}'))
    try:
        response = json.loads(buffers['result'])
        _plain_json(response)
        if response.get('status') == 'ok' and set(response) == {'status', 'result', 'worker'}:
            receipt.update(status='ok', result=response['result'], worker=response['worker'])
        elif response.get('status') == 'error' and set(response) == {'status', 'error', 'worker'}:
            receipt['worker'] = response['worker']
            error = response['error']
            if set(error) != {'kind', 'message'} or not all(type(x) is str for x in error.values()):
                raise ValueError('Malformed worker error')
            return finish((error['kind'], error['message']))
        else:
            raise ValueError('Malformed worker response schema')
    except (ValueError, TypeError, AttributeError, RecursionError) as exc:
        return finish(('protocol_error', str(exc)))
    return finish()
