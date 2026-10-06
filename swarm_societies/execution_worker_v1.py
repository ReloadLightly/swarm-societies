"""Private executable for execution_v1; no public arbitrary-callable interface."""
from __future__ import annotations

# Only standard-library bootstrap code runs before resource limits are applied.
import json
import os
from pathlib import Path
import resource
import sys


def main():
    request_path, result_descriptor, limits_json = sys.argv[1:]
    limits = json.loads(limits_json)
    cpu = limits['cpu_seconds']
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_AS, (limits['memory_bytes'], limits['memory_bytes']))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits['result_bytes'], limits['result_bytes']))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from swarm_societies.execution_v1 import bounded_read_json, validate_job, _encode_json

    worker = {'pid': os.getpid(), 'limits_applied_before_candidate_load': True,
              'python_hash_seed': os.environ['PYTHONHASHSEED'],
              'hash_randomization': sys.flags.hash_randomization,
              'safe_path': sys.flags.safe_path, 'no_user_site': sys.flags.no_user_site,
              'applied_limits': {name: list(resource.getrlimit(getattr(resource, name)))
                                 for name in ('RLIMIT_AS', 'RLIMIT_CPU', 'RLIMIT_CORE',
                                              'RLIMIT_FSIZE', 'RLIMIT_NOFILE')}}
    try:
        job = bounded_read_json(request_path, limits['request_bytes'])
        validate_job(job)
        if job['kind'] == 'runtime_probe':
            import numpy
            import scipy.linalg
            result = {'numpy_version': numpy.__version__, 'scipy_version': scipy.__version__,
                      'linear_algebra_result': float(scipy.linalg.det(numpy.eye(2))),
                      'address_space_limit_bytes': resource.getrlimit(resource.RLIMIT_AS)[0],
                      'cpu_limit_seconds': resource.getrlimit(resource.RLIMIT_CPU)[0],
                      'cwd_isolated': Path.cwd().name.startswith('swarm-execution-v1-'),
                      'thread_limit': os.environ['OPENBLAS_NUM_THREADS']}
        else:
            from swarm_societies.candidate import CandidateProgram
            if job['kind'] == 'candidate_validate':
                from swarm_societies.evaluation import component_hashes
                program = CandidateProgram(job['source'], '<bounded-validation>')
                result = {'source_sha256': program.digest,
                          'component_hashes': component_hashes(job['source'])}
            elif job['kind'] == 'candidate_policy':
                program = CandidateProgram(job['source'], '<bounded-policy>')
                result = program.call(job['function'], job['observation'], job['state'],
                                      max_lines=job.get('max_lines', 10000))
            else:
                def program(spec):
                    return CandidateProgram(spec['source'], spec.get('name', '<bounded-policy>'))

                if job['kind'] == 'stepwise_advance' and 'snapshot' in job:
                    from swarm_societies.ecology_stepwise_v1 import StepwiseEcology
                    engine = StepwiseEcology.from_snapshot(job['snapshot'])
                else:
                    programs = [program(spec) for spec in job['programs']]
                    members = job.get('member_programs')
                    if members is not None:
                        members = [[program(spec) for spec in row] for row in members]
                    if job['kind'] == 'legacy_episode':
                        from swarm_societies import ecology as module
                    elif job['kind'] in ('consumption_episode', 'consumption_case'):
                        from swarm_societies import ecology_consumption_v2 as module
                    elif job['kind'] == 'world_model_episode':
                        from swarm_societies import ecology_world_model_v1 as module
                    else:
                        from swarm_societies import ecology_stepwise_v1 as module
                    kwargs = {'seed': job.get('seed', 0), 'replay': job.get('replay', False),
                              'member_programs': members}
                    if job['kind'] in ('world_model_episode', 'stepwise_episode', 'stepwise_advance'):
                        law = job.get('world_parameters')
                        kwargs.update(world_parameters=module.WorldParameters(**law) if law is not None else None,
                                      observation_mode=job.get('observation_mode', 'local'))
                    if job['kind'] == 'consumption_case':
                        from swarm_societies.consumption_study import simulate_consumption
                        result = simulate_consumption(programs, members, job['case'],
                                                      replay=job.get('replay', False),
                                                      disturbance=job.get('disturbance', True))
                    elif job['kind'] == 'stepwise_advance':
                        config = module.EcologyConfig(**{'n_societies': len(programs), **job.get('config', {})})
                        engine = module.StepwiseEcology(programs, config, **kwargs)
                    else:
                        config = module.EcologyConfig(**{'n_societies': len(programs), **job.get('config', {})})
                        result = module.run_episode(programs, config, **kwargs)
                if job['kind'] == 'stepwise_advance':
                    completed = 0
                    for _ in range(job['steps']):
                        if engine.phase == 'complete':
                            break
                        if engine.phase == 'ready':
                            engine.step()
                        else:
                            if engine.phase == 'institutions':
                                engine.set_institution_decisions()
                            engine.finish_tick()
                        completed += 1
                    result = {'snapshot': engine.snapshot(), 'steps_completed': completed,
                              'complete': engine.phase == 'complete'}
                    if result['complete']:
                        result['result'] = engine.result()
        response = {'status': 'ok', 'result': result, 'worker': worker}
    except BaseException as exc:
        kind = 'memory_limit' if isinstance(exc, MemoryError) else 'candidate_error'
        message = f'{type(exc).__name__}: {exc}'[:2048]
        if 'MemoryError' in message:
            kind = 'memory_limit'
        response = {'status': 'error', 'error': {'kind': kind, 'message': message}, 'worker': worker}
    worker['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    try:
        payload = _encode_json(response, limits['result_bytes'])
    except (ValueError, MemoryError, RecursionError, OverflowError):
        payload = json.dumps({'status': 'error', 'error': {'kind': 'output_limit',
                              'message': 'Worker result exceeded serialization limits'},
                              'worker': worker}, separators=(',', ':')).encode('utf-8')
    descriptor = int(result_descriptor)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(payload)
        stream.flush()


if __name__ == '__main__':
    main()
