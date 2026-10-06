"""Containment and exact-result checks for the additive execution boundary."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from swarm_societies import execution_v1 as execution
from swarm_societies.candidate import CandidateProgram

ROOT = Path(__file__).resolve().parents[1]


def source(body="return {'action': 'harvest', 'target': o.get('society_id', 0), 'state': s}"):
    return ('def member_policy(o, s):\n    ' + body.replace('\n', '\n    ') +
            "\ndef institution(o, s):\n    return {'tax_rate': .2, 'public_fraction': .3}\n")


def policy_job(body=None, **changes):
    return {'kind': 'candidate_policy', 'source': source() if body is None else source(body),
            'function': 'member_policy', 'observation': {}, 'state': {}, **changes}


def episode_job(kind='consumption_episode', **changes):
    programs = [{'source': (ROOT / 'seeds' / f'{name}.py').read_text(), 'name': name}
                for name in ('initial', 'cooperative', 'selfish')]
    return {'kind': kind, 'programs': programs,
            'member_programs': [[programs[(s + m) % 3] for m in range(2)] for s in range(3)],
            'config': {'n_societies': 3, 'members_per_society': 2, 'ticks': 6,
                       'disturbance_tick': 3}, 'seed': 713, 'replay': True, **changes}


@unittest.skipUnless(sys.platform == 'linux', 'Linux resource/process-group boundary')
class ExecutionTests(unittest.TestCase):
    def test_ordinary_policy_receipt_and_input_are_unchanged(self):
        job = policy_job('o["new"] = 1\ns["counter"] = s.get("counter", 0) + 1\nreturn {"state": s}')
        before = deepcopy(job)
        with patch.object(CandidateProgram, 'call', side_effect=AssertionError('Parent policy execution')):
            receipt = execution.execute_job(job)
        self.assertEqual(receipt['status'], 'ok', receipt)
        self.assertEqual(receipt['result'], {'state': {'counter': 1}})
        self.assertEqual(job, before)
        self.assertTrue(receipt['worker']['limits_applied_before_candidate_load'])
        self.assertEqual(receipt['worker']['applied_limits']['RLIMIT_AS'], [execution.ExecutionLimits().memory_bytes] * 2)
        self.assertEqual(receipt['runtime']['executable'], sys.executable)
        for name in execution.SOURCE_FILES:
            self.assertEqual(receipt['source_sha256']['swarm_societies/' + name],
                             hashlib.sha256((ROOT / 'swarm_societies' / name).read_bytes()).hexdigest())
        self.assertEqual(receipt['stdout'], '')
        self.assertEqual(receipt['stderr'], '')

    def test_validation_compiles_without_calling_functions(self):
        from swarm_societies.evaluation import component_hashes
        text = source('return [0] * 10000000000')
        receipt = execution.execute_job({'kind': 'candidate_validate', 'source': text})
        self.assertEqual(receipt['status'], 'ok', receipt)
        self.assertEqual(receipt['result'], {'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
                                           'component_hashes': component_hashes(text)})

    def test_policy_inputs_and_outputs_preserve_observable_dictionary_order(self):
        job = policy_job('return {"state": s, "keys": list(o.keys()) + list(s.keys())}',
                         observation={'z': 1, 'a': 2}, state={'y': 3, 'b': 4})
        receipt = execution.execute_job(job)
        self.assertEqual(receipt['status'], 'ok', receipt)
        self.assertEqual(receipt['result']['keys'], ['z', 'a', 'y', 'b'])
        self.assertEqual(list(receipt['result']['state']), ['y', 'b'])

    def test_hash_seed_is_controlled_across_workers_and_parent_hash_seeds(self):
        job = policy_job('return {"order": list({"alpha", "beta", "gamma", "delta"})}')
        receipts = [execution.execute_job(job) for _ in range(3)]
        self.assertTrue(all(r['status'] == 'ok' for r in receipts))
        for receipt in receipts:
            self.assertEqual(receipt['worker']['python_hash_seed'], '0')
            self.assertEqual(receipt['worker']['hash_randomization'], 0)
            self.assertTrue(receipt['worker']['safe_path'])
            self.assertTrue(receipt['worker']['no_user_site'])
            self.assertEqual(receipt['result'], receipts[0]['result'])
        script = ('import json\nfrom swarm_societies.execution_v1 import execute_job\n'
                  'print(json.dumps(execute_job(' + repr(job) + ')["result"]))\n')
        for seed in ('17', '8091'):
            result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                                    env={**os.environ, 'PYTHONHASHSEED': seed},
                                    capture_output=True, text=True, timeout=10, check=True)
            self.assertEqual(json.loads(result.stdout), receipts[0]['result'])

    def test_huge_allocation_fails_in_worker_and_parent_continues(self):
        receipt = execution.execute_job(policy_job('data = [0] * 10000000000\nreturn {"n": len(data)}'),
                                        limits=replace(execution.ExecutionLimits(), memory_bytes=256 * 1024**2))
        self.assertEqual(receipt['status'], 'error')
        self.assertEqual(receipt['error']['kind'], 'memory_limit', receipt)
        self.assertEqual(execution.execute_job(policy_job())['status'], 'ok')

    def test_infinite_python_loop_is_bounded(self):
        receipt = execution.execute_job(policy_job('while True:\n    value = 1'),
                                        limits=replace(execution.ExecutionLimits(), wall_seconds=2))
        self.assertEqual(receipt['status'], 'error')
        self.assertIn('line budget', receipt['error']['message'])

    def test_expensive_builtin_hits_parent_wall_deadline(self):
        receipt = execution.execute_job(policy_job('return {"value": sum(range(1000000000000))}'),
                                        limits=replace(execution.ExecutionLimits(), wall_seconds=.3))
        self.assertEqual(receipt['error']['kind'], 'wall_timeout', receipt)
        self.assertLess(receipt['wall_seconds'], 3)

    def test_expensive_builtin_hits_cpu_limit(self):
        receipt = execution.execute_job(policy_job('return {"value": sum(range(1000000000000))}'),
                                        limits=replace(execution.ExecutionLimits(), cpu_seconds=1, wall_seconds=5))
        self.assertEqual(receipt['error']['kind'], 'cpu_limit', receipt)
        self.assertEqual(receipt['returncode'], -signal.SIGXCPU)

    def test_recursive_and_invalid_policy_outputs_are_failures(self):
        cases = [policy_job('return member_policy(o, s)'), policy_job('return []'),
                 policy_job('return {"value": float("nan")}'), policy_job('return {"x": "x" * 40000}'),
                 policy_job('return {"x": 1 / 0}')]
        for job in cases:
            with self.subTest(body=job['source'][:90]):
                receipt = execution.execute_job(job)
                self.assertEqual(receipt['status'], 'error', receipt)
                self.assertLessEqual(len(receipt['error']['message']), 2048)

    def test_result_limit_has_a_small_failure_receipt(self):
        receipt = execution.execute_job(policy_job('return {"text": "x" * 2000}'),
                                        limits=replace(execution.ExecutionLimits(), result_bytes=1024))
        self.assertEqual(receipt['error']['kind'], 'output_limit', receipt)
        self.assertLessEqual(receipt['result_bytes'], 1024)

    def test_sources_imports_private_access_and_extra_job_fields_rejected(self):
        cases = [policy_job('import os\nreturn {}'), policy_job('return {"x": o.__class__}'),
                 policy_job(function='__init__'), policy_job(source='x' * 60001),
                 policy_job(arbitrary_callable='os.system'), {'kind': 'os.system'},
                 policy_job(source='é' * 40000)]
        for job in cases:
            with self.subTest(keys=list(job)):
                self.assertEqual(execution.execute_job(job)['status'], 'error')

    def test_request_rejected_before_launch_and_no_arbitrary_serializers(self):
        class Hostile:
            def __repr__(self):
                raise AssertionError('must not inspect arbitrary object')
        with patch.object(execution.subprocess, 'Popen', side_effect=AssertionError('Must not launch')):
            self.assertEqual(execution.execute_job(policy_job(observation={'x': 'x' * 3000}),
                limits=replace(execution.ExecutionLimits(), request_bytes=1024))['error']['kind'], 'invalid_job')
            self.assertEqual(execution.execute_job(policy_job(state={'x': Hostile()}))['error']['kind'], 'invalid_job')
            self.assertEqual(execution.execute_job(policy_job(state={'x': float('nan')}))['error']['kind'], 'invalid_job')

    def test_invalid_limits_are_configuration_errors(self):
        for changes in ({'wall_seconds': float('nan')}, {'memory_bytes': 1},
                        {'cpu_seconds': True}, {'result_bytes': 0}, {'stdout_bytes': -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                execution.execute_job(policy_job(), limits=replace(execution.ExecutionLimits(), **changes))

    def test_bounded_read_checks_size_before_json_parse_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            path.write_text('[' + ' ' * 4000)
            with patch.object(execution.json, 'loads', side_effect=AssertionError('No parse')):
                with self.assertRaises(ValueError):
                    execution.bounded_read_json(path, 100)
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                execution.bounded_read_json(link)
            fifo = Path(directory) / 'fifo'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                execution.bounded_read_json(fifo)
            path.write_text('{"x": NaN}')
            with self.assertRaises(ValueError):
                execution.bounded_read_json(path)

    def test_atomic_receipt_never_overwrites_incumbent_or_follows_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            incumbent = parent / 'incumbent.json'
            incumbent.write_bytes(b'preserved checkpoint')
            receipt = execution.execute_job(policy_job(), receipt_path=parent / 'new.json')
            self.assertEqual(json.loads((parent / 'new.json').read_text()), receipt)
            with self.assertRaises(FileExistsError):
                execution.atomic_write_receipt(incumbent, receipt)
            link = parent / 'link.json'
            link.symlink_to(incumbent)
            with self.assertRaises(FileExistsError):
                execution.atomic_write_receipt(link, receipt)
            linked_parent = parent / 'linked-parent'
            linked_parent.symlink_to(parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                execution.atomic_write_receipt(linked_parent / 'different.json', receipt)
            self.assertEqual(incumbent.read_bytes(), b'preserved checkpoint')
            self.assertFalse(list(parent.glob('.execution-receipt-*')))

    def _fixture_worker(self, text, **changes):
        # Trusted test executable exercises supervisor failures impossible to
        # request through the candidate language; production has no such job.
        with tempfile.TemporaryDirectory() as directory:
            worker = Path(directory) / 'fixture.py'
            worker.write_text(text)
            with patch.object(execution, 'WORKER', worker):
                return execution.execute_job(policy_job(), limits=replace(execution.ExecutionLimits(), **changes))

    def test_abrupt_worker_death_and_malformed_ipc_have_failure_receipts(self):
        receipt = self._fixture_worker('import os,signal\nos.kill(os.getpid(),signal.SIGTERM)\n')
        self.assertEqual(receipt['error']['kind'], 'worker_death', receipt)
        self.assertEqual(receipt['returncode'], -signal.SIGTERM)
        for payload in ('[]', '{"status":', '{"status":"ok","result":NaN,"worker":{}}'):
            receipt = self._fixture_worker('import os,sys\nos.write(int(sys.argv[2]), ' + repr(payload.encode()) + ')\n')
            self.assertEqual(receipt['error']['kind'], 'protocol_error', receipt)

    def test_stdout_and_stderr_are_capped(self):
        for stream in ('stdout', 'stderr'):
            receipt = self._fixture_worker(
                'import sys,time\nsys.' + stream + '.buffer.write(b"x" * 1000000)\ntime.sleep(10)\n',
                stdout_bytes=1024, stderr_bytes=1024, wall_seconds=2)
            self.assertEqual(receipt['error']['kind'], 'output_limit', receipt)
            self.assertEqual(len(receipt[stream]), 1024)
            self.assertTrue(receipt[stream + '_truncated'])

    def test_timeout_kills_entire_process_group(self):
        receipt = self._fixture_worker('import os,time,sys\npid=os.fork()\n'
            'if pid == 0:\n time.sleep(30)\nelse:\n print(pid,flush=True)\n time.sleep(30)\n',
            wall_seconds=.3)
        self.assertEqual(receipt['error']['kind'], 'wall_timeout', receipt)
        child = int(receipt['stdout'].strip())
        # A killed child can briefly remain an unreaped zombie; it cannot run.
        for _ in range(30):
            path = Path(f'/proc/{child}/stat')
            if not path.exists() or path.read_text().split()[2] == 'Z':
                break
            time.sleep(.01)
        else:
            self.fail('Worker descendant survived group cleanup')

    def test_default_caps_allow_numeric_imports_in_isolated_worker(self):
        receipt = execution.execute_job({'kind': 'runtime_probe'})
        self.assertEqual(receipt['status'], 'ok', receipt)
        self.assertEqual(receipt['result']['linear_algebra_result'], 1)
        self.assertEqual(receipt['result']['address_space_limit_bytes'], execution.ExecutionLimits().memory_bytes)
        self.assertTrue(receipt['result']['cwd_isolated'])
        self.assertEqual(receipt['result']['thread_limit'], '1')

    def test_every_episode_job_retains_exact_frozen_result(self):
        from swarm_societies import ecology, ecology_consumption_v2, ecology_world_model_v1, ecology_stepwise_v1
        for kind, module in (('legacy_episode', ecology), ('consumption_episode', ecology_consumption_v2),
                             ('world_model_episode', ecology_world_model_v1), ('stepwise_episode', ecology_stepwise_v1)):
            job = episode_job(kind)
            kwargs = {}
            if kind in ('world_model_episode', 'stepwise_episode'):
                job.update(world_parameters={'r': 3.1, 'b': .7, 'g': .3}, observation_mode='full_observation_control')
                kwargs.update(world_parameters=module.WorldParameters(**job['world_parameters']),
                              observation_mode=job['observation_mode'])
            programs = [CandidateProgram(p['source'], p['name']) for p in job['programs']]
            members = [[CandidateProgram(p['source'], p['name']) for p in row] for row in job['member_programs']]
            expected = module.run_episode(programs, module.EcologyConfig(**job['config']), seed=job['seed'],
                                          replay=True, member_programs=members, **kwargs)
            with self.subTest(kind=kind):
                receipt = execution.execute_job(job)
                self.assertEqual(receipt['status'], 'ok', receipt)
                self.assertEqual(receipt['result'], expected)

    def test_normalized_consumption_case_matches_full_saved_helper_output(self):
        from swarm_societies.consumption_study import simulate_consumption
        job = episode_job('consumption_case')
        case = {'id': 'bounded-fixture', 'config': job.pop('config'), 'seed': job.pop('seed')}
        job.update(case=case, disturbance=False)
        programs = [CandidateProgram(p['source'], p['name']) for p in job['programs']]
        members = [[CandidateProgram(p['source'], p['name']) for p in row] for row in job['member_programs']]
        expected = simulate_consumption(programs, members, case, replay=True, disturbance=False)
        receipt = execution.execute_job(job)
        self.assertEqual(receipt['status'], 'ok', receipt)
        self.assertEqual(receipt['result'], expected)

    def test_omitted_society_count_derives_from_inline_programs(self):
        from swarm_societies import ecology_consumption_v2 as module
        job = episode_job()
        job['programs'] = job['programs'][:2]
        job.pop('member_programs')
        job['config'].pop('n_societies')
        expected = module.run_episode([CandidateProgram(p['source'], p['name']) for p in job['programs']],
                                      module.EcologyConfig(n_societies=2, **job['config']),
                                      seed=job['seed'], replay=True)
        receipt = execution.execute_job(job)
        self.assertEqual(receipt['status'], 'ok', receipt)
        self.assertEqual(receipt['result'], expected)

    def test_stepwise_continuation_preserves_rng_module_memory_and_inputs(self):
        from swarm_societies.ecology_stepwise_v1 import StepwiseEcology
        text = 'counter = []\n' + source('counter.append(1)\nreturn {"action": "harvest", "effort": (len(counter) % 4) / 3}')
        job = episode_job('stepwise_advance', steps=2)
        job['programs'] = [{'source': text, 'name': 'stateful'}] * 3
        job.pop('member_programs')
        engine = StepwiseEcology([CandidateProgram(text, 'stateful')] * 3,
                                 config=job['config'], seed=job['seed'], replay=True)
        engine.step()
        engine.step()
        first = execution.execute_job(job)
        self.assertEqual(first['status'], 'ok', first)
        self.assertEqual(first['result']['snapshot'], engine.snapshot())
        saved = deepcopy(first['result']['snapshot'])
        while engine.phase != 'complete':
            engine.step()
        second = execution.execute_job({'kind': 'stepwise_advance', 'snapshot': saved, 'steps': 100})
        self.assertEqual(second['status'], 'ok', second)
        self.assertEqual(second['result']['result'], engine.result())
        self.assertEqual(second['result']['snapshot'], engine.snapshot())
        self.assertEqual(saved, first['result']['snapshot'])
        self.assertEqual(second['result']['steps_completed'], 4)

    def test_failed_snapshot_continuation_does_not_mutate_checkpoint(self):
        first = execution.execute_job(episode_job('stepwise_advance', steps=1))
        saved = first['result']['snapshot']
        for row in saved['members']:
            row[0]['source'] = source('data = [0] * 10000000000\nreturn {}')
        before = deepcopy(saved)
        receipt = execution.execute_job({'kind': 'stepwise_advance', 'snapshot': saved, 'steps': 1})
        self.assertEqual(receipt['status'], 'error', receipt)
        self.assertEqual(saved, before)

    def test_stepwise_snapshot_preserves_private_state_dictionary_iteration_order(self):
        from swarm_societies.ecology_stepwise_v1 import StepwiseEcology
        text = source('s = s or {"z": 1, "a": 2}\n'
                      'effort = .25 if list(s.keys())[0] == "z" else 1.0\n'
                      'return {"action": "harvest", "effort": effort, "state": s}')
        job = episode_job('stepwise_advance', steps=1)
        job['programs'] = [{'source': text}] * 3
        job.pop('member_programs')
        engine = StepwiseEcology([CandidateProgram(text)] * 3, config=job['config'],
                                 seed=job['seed'], replay=True)
        while engine.phase != 'complete':
            engine.step()
        first = execution.execute_job(job)
        checkpoint = first['result']['snapshot']
        private = checkpoint['state']['societies'][0]['members'][0]['private']
        self.assertEqual(list(private), ['z', 'a'])
        last = execution.execute_job({'kind': 'stepwise_advance', 'snapshot': checkpoint, 'steps': 100})
        self.assertEqual(last['status'], 'ok', last)
        self.assertEqual(last['result']['result'], engine.result())

    def test_local_set_literal_and_saved_list_match_full_episode_on_continuation(self):
        text = source('s = s or {"order": list({"alpha", "beta", "gamma", "delta"})}\n'
                      'items = list({"alpha", "beta", "gamma", "delta"})\n'
                      'effort = .25 if items == s["order"] else 1.0\n'
                      'return {"action": "harvest", "effort": effort, "state": s}')
        job = episode_job('stepwise_advance', steps=2)
        job['programs'] = [{'source': text}] * 3
        job.pop('member_programs')
        first = execution.execute_job(job)
        self.assertEqual(first['status'], 'ok', first)
        resumed = execution.execute_job({'kind': 'stepwise_advance',
                                         'snapshot': first['result']['snapshot'], 'steps': 100})
        full_job = {key: value for key, value in job.items() if key != 'steps'}
        full_job['kind'] = 'stepwise_episode'
        full = execution.execute_job(full_job)
        self.assertEqual(resumed['status'], 'ok', resumed)
        self.assertEqual(full['status'], 'ok', full)
        self.assertEqual(resumed['result']['result'], full['result'])

    def test_pending_stepwise_boundaries_resume_once(self):
        from swarm_societies.ecology_stepwise_v1 import StepwiseEcology
        job = episode_job()
        for phase in ('institutions', 'members'):
            engine = StepwiseEcology([CandidateProgram(p['source']) for p in job['programs']],
                                     config=job['config'], seed=job['seed'])
            engine.begin_tick()
            if phase == 'members':
                engine.set_institution_decisions()
            saved = engine.snapshot()
            if phase == 'institutions':
                engine.set_institution_decisions()
            engine.finish_tick()
            receipt = execution.execute_job({'kind': 'stepwise_advance', 'snapshot': saved, 'steps': 1})
            self.assertEqual(receipt['status'], 'ok', receipt)
            self.assertEqual(receipt['result']['snapshot'], engine.snapshot())

    def test_original_candidate_and_simulators_remain_frozen(self):
        expected = {'candidate.py': '0ff988ac0a8b05ca0919bb67267e6645a232fb49530cfbd51122c6b8d1dfa89b',
                    'ecology.py': '76e4ba5a2abf4f20356c8c4710d0a5632b50cd87e97d363c27b556642508eba7',
                    'ecology_consumption_v2.py': '82c3ffe2e9431541e6e0cfbda6c97bccadfe87518bd3d17ff7661434d84e2344',
                    'ecology_world_model_v1.py': '6b1a84387efd3704efb3c4986cafcb6d9607c344c597e1aa7ec99b084357e8e7'}
        for name, value in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / 'swarm_societies' / name).read_bytes()).hexdigest(), value)


if __name__ == '__main__':
    unittest.main()
