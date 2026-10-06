"""Independent transition, observation-boundary and frozen-engine parity checks."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from swarm_societies.candidate import CandidateError, CandidateProgram
from swarm_societies import ecology_stepwise_v1 as stepwise
from swarm_societies import ecology_world_model_v1 as frozen


ROOT = Path(__file__).resolve().parents[1]
SEEDS = [ROOT / 'seeds' / f'{name}.py'
         for name in ('initial', 'cooperative', 'selfish')]


def config(**changes):
    return frozen.EcologyConfig(**{
        'n_societies': 3, 'members_per_society': 3,
        'ticks': 11, 'disturbance_tick': 5, **changes,
    })


def program(member, institution="return {'tax_rate': .2, 'public_fraction': .3}"):
    return CandidateProgram(
        'def member_policy(observation, state):\n    '
        + member.replace('\n', '\n    ')
        + '\n\ndef institution(observation, state):\n    '
        + institution.replace('\n', '\n    ') + '\n')


def stateful_program():
    """Exercise every action, endogenous reports and both policy memories."""
    return program("""count = state.get('count', 0) + 1
history = (state.get('history', []) + [observation['wealth']])[-4:]
actions = ['harvest', 'contribute', 'raid', 'share', 'rest', 'guard']
choice = (observation['tick'] + observation['member_id'] + observation['society_id']) % 6
target = (observation['society_id'] + observation['member_id'] % 3) % observation['n_societies']
return {'action': actions[choice], 'target': target,
        'effort': .4 + .2 * (count % 4),
        'message': {'count': count, 'history': history,
                    'signal': observation['messages'].get('signal', 0)},
        'state': {'count': count, 'history': history}}""", """count = state.get('count', 0) + 1
previous = state.get('signal', 0)
signal = sum(row['message'].get('count', 0) for row in observation['reports'])
weights = [0 for row in observation['members']] if count % 3 == 0 else [row['id'] + 1 for row in observation['members']]
return {'tax_rate': .1 + .1 * (count % 5),
        'public_fraction': .8 if count % 2 else .15,
        'defense_fraction': .4, 'reserve_fraction': .2,
        'raid_permission': count % 2 == 0, 'redistribution': weights,
        'messages': {'signal': signal + previous, 'reports': observation['reports']},
        'state': {'count': count, 'signal': signal}}""")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def finish(engine):
    """Resume any supported boundary without repeating a candidate call."""
    if engine.phase == 'institutions':
        engine.set_institution_decisions()
    if engine.phase == 'members':
        engine.finish_tick()
    while engine.phase != 'complete':
        engine.step()
    return engine.result()


class StepwiseEcologyTests(unittest.TestCase):
    def test_reference_engine_remains_frozen(self):
        source = ROOT / 'swarm_societies' / 'ecology_world_model_v1.py'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         '6b1a84387efd3704efb3c4986cafcb6d9607c344c597e1aa7ec99b084357e8e7')

    def test_wrapper_matches_every_frozen_output_across_laws_and_modes(self):
        cases = (
            (0, config(), None),
            (731, config(regeneration=2.7, enable_disturbance=False), None),
            (42, config(regeneration=15.1, initial_patch=60.), None),
            (18, config(initial_patch=0., initial_wealth=0.),
             frozen.WorldParameters(r=0., b=0., g=0., rho=0., eta=0., h=0., c=0.)),
            (71, config(initial_patch=3., enable_disturbance=False),
             frozen.WorldParameters(r=3.1, b=1.7, g=.6, rho=.72, eta=.3, h=1.6, c=.21)),
            (815, config(n_societies=2, members_per_society=2, consumption_need=0.),
             frozen.WorldParameters(r=.4, b=3., g=.8, rho=1., eta=.125, h=4., c=.8)),
            (99, config(n_societies=4, members_per_society=4, patch_capacity=4.,
                        initial_patch=1., initial_wealth=.01), None),
        )
        for seed, cfg, law in cases:
            actors = [SEEDS[s % len(SEEDS)] for s in range(cfg.n_societies)]
            for mode in frozen.OBSERVATION_MODES:
                with self.subTest(seed=seed, mode=mode):
                    kwargs = {'seed': seed, 'replay': True,
                              'world_parameters': law, 'observation_mode': mode}
                    self.assertEqual(stepwise.run_episode(actors, cfg, **kwargs),
                                     frozen.run_episode(actors, cfg, **kwargs))

    def test_heterogeneous_stateful_candidate_payloads_and_answers_match(self):
        actor = stateful_program()
        actors = [actor, SEEDS[0], SEEDS[2]]
        members = [[actor, SEEDS[1], SEEDS[2]],
                   [SEEDS[2], actor, SEEDS[0]],
                   [SEEDS[1], SEEDS[0], actor]]
        original_call = CandidateProgram.call

        def run_recorded(runner):
            calls = []

            def record(candidate, function, observation, state, *args, **kwargs):
                before = deepcopy([candidate.digest, function, observation, state])
                answer = original_call(candidate, function, observation, state, *args, **kwargs)
                calls.append(digest([before, answer]))
                return answer

            with patch.object(CandidateProgram, 'call', record):
                result = runner(actors, config(), seed=632, replay=True,
                                member_programs=members,
                                world_parameters={'r': 2.1, 'b': 1.1, 'g': .3})
            return result, calls

        expected, expected_calls = run_recorded(frozen.run_episode)
        actual, actual_calls = run_recorded(stepwise.run_episode)
        self.assertEqual(actual_calls, expected_calls)
        self.assertEqual(len(actual_calls), config().ticks * 3 * 4)
        self.assertEqual(actual, expected)
        receipts = actual['local_observations']['member_receipts']
        self.assertEqual({row['action'] for row in receipts},
                         {'harvest', 'contribute', 'raid', 'share', 'rest', 'guard'})
        self.assertTrue(any(row['denied'] for row in receipts))
        self.assertGreater(actual['ledger']['raid_destruction'], 0.)

    def test_no_replay_and_dictionary_configuration_have_exact_parity(self):
        kwargs = {'config': asdict(config()), 'seed': 384, 'replay': False,
                  'world_parameters': {'r': 4.2, 'b': 2.3, 'g': .17}}
        self.assertEqual(stepwise.run_episode(SEEDS, **kwargs),
                         frozen.run_episode(SEEDS, **kwargs))

    def test_environment_rng_finishes_in_exact_frozen_state(self):
        """Catch extra/discarded draws even when material outcomes coincide."""
        random_type = random.Random

        def run_with_rng(module, actors):
            streams = []

            class RecordedRandom(random_type):
                def __init__(self, seed=None):
                    super().__init__(seed)
                    streams.append(self)

            with patch.object(module, 'random', SimpleNamespace(Random=RecordedRandom)):
                result = module.run_episode(actors, config(), seed=523, replay=True)
            self.assertEqual(len(streams), 1)
            return result, streams[0].getstate()

        resting = program("return {'action': 'rest'}", 'return {}')
        for actors in (SEEDS, [resting] * 3):
            with self.subTest(actors=[str(actor) for actor in actors]):
                expected, expected_rng = run_with_rng(frozen, actors)
                actual, actual_rng = run_with_rng(stepwise, actors)
                self.assertEqual(actual, expected)
                self.assertEqual(actual_rng, expected_rng)

    def test_json_snapshot_restores_every_phase_and_candidate_memory(self):
        actors = [stateful_program(), SEEDS[1], SEEDS[2]]
        kwargs = {'seed': 635, 'replay': True, 'observation_mode': 'full_observation_control',
                  'world_parameters': {'r': 3.9, 'b': 1.4, 'g': .23, 'rho': .87}}
        expected = frozen.run_episode(actors, config(), **kwargs)
        for checkpoint in (0, 3, config().ticks - 1):
            for phase in ('ready', 'institutions', 'members'):
                with self.subTest(checkpoint=checkpoint, phase=phase):
                    engine = stepwise.StepwiseEcology(actors, config(), **kwargs)
                    for _ in range(checkpoint):
                        engine.step()
                    if phase != 'ready':
                        engine.begin_tick()
                    if phase == 'members':
                        engine.set_institution_decisions()
                    saved = json.loads(json.dumps(engine.snapshot(), allow_nan=False))
                    restored = stepwise.StepwiseEcology.from_snapshot(saved)
                    self.assertEqual(restored.phase, phase)
                    self.assertEqual(restored.tick, checkpoint)
                    self.assertEqual(finish(restored), expected)
                    self.assertEqual(finish(engine), expected)
        completed = stepwise.StepwiseEcology(actors, config(), **kwargs)
        finish(completed)
        restored = stepwise.StepwiseEcology.from_snapshot(
            json.loads(json.dumps(completed.snapshot(), allow_nan=False)))
        self.assertEqual(restored.phase, 'complete')
        self.assertEqual(restored.result(), expected)

    def test_snapshot_preserves_mutable_module_policy_memory(self):
        actor = CandidateProgram("""member_calls = []
institution_calls = []

def member_policy(observation, state):
    member_calls.append(observation['tick'])
    return {'action': 'harvest', 'effort': .25 * (len(member_calls) % 4),
            'state': {'calls': len(member_calls)}}

def institution(observation, state):
    institution_calls.append(observation['tick'])
    return {'tax_rate': .2, 'public_fraction': .2 * (len(institution_calls) % 4)}
""")
        cfg = config()
        expected = frozen.run_episode([actor] * 3, cfg, seed=444, replay=True)
        for phase in ('ready', 'institutions', 'members'):
            with self.subTest(phase=phase):
                engine = stepwise.StepwiseEcology([actor] * 3, cfg, seed=444, replay=True)
                for _ in range(4):
                    engine.step()
                if phase != 'ready':
                    engine.begin_tick()
                if phase == 'members':
                    engine.set_institution_decisions()
                restored = stepwise.StepwiseEcology.from_snapshot(
                    json.loads(json.dumps(engine.snapshot())))
                self.assertEqual(finish(restored), expected)

    def test_phase_errors_do_not_mutate_engine(self):
        engine = stepwise.StepwiseEcology(SEEDS, config(), seed=10)

        def rejects_without_mutating(methods):
            for method in methods:
                saved = engine.snapshot()
                with self.subTest(phase=engine.phase, method=method.__name__), self.assertRaises(ValueError):
                    method()
                self.assertEqual(engine.snapshot(), saved)

        rejects_without_mutating([engine.set_institution_decisions, engine.member_observations,
                                  engine.finish_tick, engine.result, engine.completed_observations])
        engine.begin_tick()
        rejects_without_mutating([engine.begin_tick, engine.member_observations,
                                  engine.finish_tick, engine.step, engine.result,
                                  engine.completed_observations])
        engine.set_institution_decisions()
        rejects_without_mutating([engine.begin_tick, engine.set_institution_decisions,
                                  engine.step, engine.result, engine.completed_observations])
        finish(engine)
        rejects_without_mutating([engine.begin_tick, engine.set_institution_decisions,
                                  engine.member_observations, engine.finish_tick, engine.step])

    def test_legal_payloads_do_not_expose_pending_receipts_or_privileged_fields(self):
        engine = stepwise.StepwiseEcology(SEEDS, config(), seed=122,
                                         observation_mode='full_observation_control')
        institution_keys = {'tick', 'society_id', 'n_societies', 'treasury',
                            'infrastructure', 'mean_wealth', 'members', 'reports'}
        member_keys = {'tick', 'society_id', 'member_id', 'n_societies', 'n_members',
                       'wealth', 'productivity', 'infrastructure', 'tax_rate',
                       'patches', 'messages', 'last_action'}
        observations = engine.begin_tick()
        for row in observations:
            self.assertEqual(set(row), institution_keys)
            self.assertEqual(row['reports'], [])
        with self.assertRaises(ValueError):
            engine.completed_observations()
        engine.set_institution_decisions()
        for society in engine.member_observations():
            for row in society:
                self.assertEqual(set(row), member_keys)
        completed = engine.finish_tick()
        self.assertEqual(completed['tick'], 0)
        self.assertTrue(all(row['tick'] == 0 for row in completed['learning_observations']))
        for rows in completed['local_observations'].values():
            self.assertTrue(rows)
            self.assertTrue(all(row['tick'] == 0 for row in rows))
        previous = engine.completed_observations()
        engine.begin_tick()
        self.assertEqual(engine.completed_observations(), previous)
        engine.set_institution_decisions()
        self.assertEqual(engine.completed_observations(), previous)
        engine.finish_tick()
        latest = engine.completed_observations()
        self.assertTrue(all(row['tick'] == 1 for row in latest['learning_observations']))

    def test_returned_observations_decisions_receipts_and_results_do_not_alias(self):
        cfg = config()
        engine = stepwise.StepwiseEcology(SEEDS, cfg, seed=701, replay=True)
        expected = frozen.run_episode(SEEDS, cfg, seed=701, replay=True)
        initial = engine.begin_tick()
        initial[0]['members'][0]['wealth'] = -100000
        initial[0]['reports'].append({'member': 0, 'message': {'corrupt': True}})
        decisions = engine.set_institution_decisions()
        decisions[0]['state']['corrupt'] = True
        decisions[0]['messages']['corrupt'] = True
        observations = engine.member_observations()
        saved = deepcopy(observations)
        observations[0][0]['patches'][0]['stock'] = -100000
        observations[0][0]['messages']['corrupt'] = True
        self.assertEqual(engine.member_observations(), saved)
        completed = engine.finish_tick()
        completed['learning_observations'][0]['growth'] = -100000
        completed['local_observations']['member_receipts'][0]['cost'] = -100000
        latest = engine.completed_observations()
        latest['local_observations']['institution_receipts'][0]['budget'] = -100000
        actual = finish(engine)
        self.assertEqual(actual, expected)
        actual['replay'][0]['patches'][0] = -100000
        self.assertEqual(engine.result(), expected)

    def test_evaluator_branch_overrides_leave_live_world_and_rng_unchanged(self):
        actors = [stateful_program(), SEEDS[1], SEEDS[2]]
        cfg = config()
        engine = stepwise.StepwiseEcology(actors, cfg, seed=103, replay=True)
        for _ in range(4):
            engine.step()
        engine.begin_tick()
        saved = engine.snapshot()
        outcomes = []
        for public_fraction in (0., 1.):
            branch = stepwise.StepwiseEcology.from_snapshot(saved)
            branch.set_institution_decisions({0: {'public_fraction': public_fraction}})
            branch.finish_tick()
            outcomes.append(finish(branch))
            self.assertEqual(engine.snapshot(), saved)
        self.assertNotEqual(outcomes[0]['digest'], outcomes[1]['digest'])
        self.assertNotEqual(outcomes[0]['ledger']['investment'], outcomes[1]['ledger']['investment'])
        self.assertEqual(finish(engine), frozen.run_episode(actors, cfg, seed=103, replay=True))
        repeated = stepwise.StepwiseEcology.from_snapshot(saved)
        repeated.set_institution_decisions({0: {'public_fraction': 1.}})
        repeated.finish_tick()
        self.assertEqual(finish(repeated), outcomes[1])

    def test_snapshot_and_restored_world_are_independent_copies(self):
        engine = stepwise.StepwiseEcology(SEEDS, config(), seed=451, replay=True)
        engine.step()
        saved = engine.snapshot()
        pristine = deepcopy(saved)
        restored = stepwise.StepwiseEcology.from_snapshot(saved)
        restored.step()
        self.assertEqual(saved, pristine)
        self.assertEqual(engine.snapshot(), pristine)
        # Mutate every reachable list/dictionary value in the caller's snapshot.
        saved.clear()
        self.assertEqual(finish(restored), finish(engine))

    def test_member_override_preserves_other_members_and_default_state_updates(self):
        engine = stepwise.StepwiseEcology(SEEDS, config(), seed=333, replay=True)
        engine.begin_tick()
        engine.set_institution_decisions()
        result = engine.finish_tick({(0, 0): {'action': 'rest', 'message': {'override': True}}})
        rows = result['local_observations']['member_receipts']
        focal = next(row for row in rows if row['society_id'] == 0 and row['member_id'] == 0)
        self.assertEqual(focal['action'], 'rest')
        self.assertEqual(focal['cost'], 0.)
        self.assertEqual(len(rows), 9)
        next_observations = engine.begin_tick()
        self.assertIn({'member': 0, 'message': {'override': True}}, next_observations[0]['reports'])
        original_call = CandidateProgram.call
        focal_states = []

        def record(candidate, function, observation, state, *args, **kwargs):
            if (function == 'member_policy' and observation['society_id'] == 0
                    and observation['member_id'] == 0):
                focal_states.append(deepcopy(state))
            return original_call(candidate, function, observation, state, *args, **kwargs)

        engine.set_institution_decisions()
        with patch.object(CandidateProgram, 'call', record):
            engine.finish_tick()
        self.assertEqual(focal_states, [{'seen': 1}])
        finish(engine)

    def test_invalid_overrides_cannot_replace_policy_memory_or_advance_rng(self):
        engine = stepwise.StepwiseEcology(SEEDS, config(), seed=76)
        engine.begin_tick()
        institution_cases = (
            [], {-1: {}}, {3: {}}, {True: {}}, {0: {'state': {}}},
            {0: {'messages': {}}}, {0: {'unknown': 0}},
            {0: {'public_fraction': float('nan')}},
        )
        for overrides in institution_cases:
            saved = engine.snapshot()
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                engine.set_institution_decisions(overrides)
            self.assertEqual(engine.snapshot(), saved)
        engine.set_institution_decisions()
        member_cases = (
            [], {0: {}}, {(0, 3): {}}, {(3, 0): {}}, {(True, 0): {}},
            {(0, 0): {'state': {}}}, {(0, 0): {'unknown': 0}},
            {(0, 0): {'effort': float('nan')}},
        )
        for overrides in member_cases:
            saved = engine.snapshot()
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                engine.finish_tick(overrides)
            self.assertEqual(engine.snapshot(), saved)
        self.assertEqual(finish(engine), frozen.run_episode(SEEDS, config(), seed=76))

    def test_reset_clears_completed_records_memories_and_random_state(self):
        actor = stateful_program()
        engine = stepwise.StepwiseEcology([actor] * 3, config(), seed=879, replay=True)
        for _ in range(4):
            engine.step()
        engine.begin_tick()
        cfg = config(n_societies=2, members_per_society=2)
        kwargs = {'seed': 280, 'replay': False, 'world_parameters': {'r': 3.1}}
        engine.reset(SEEDS[:2], cfg, **kwargs)
        self.assertEqual(engine.tick, 0)
        self.assertEqual(engine.phase, 'ready')
        with self.assertRaises(ValueError):
            engine.completed_observations()
        self.assertEqual(finish(engine), frozen.run_episode(SEEDS[:2], cfg, **kwargs))

    def test_unsupported_module_memory_rejects_snapshot_without_changing_world(self):
        actor = CandidateProgram("""iterators = []

def member_policy(observation, state):
    iterators.append((value for value in [1, 2]))
    return {'action': 'harvest'}

def institution(observation, state):
    return {'tax_rate': .2, 'public_fraction': .3}
""")
        engine = stepwise.StepwiseEcology([actor] * 3, config(), seed=942, replay=True)
        engine.step()
        random_state = engine.rng.getstate()
        with self.assertRaisesRegex(ValueError, 'Unsupported candidate module state'):
            engine.snapshot()
        self.assertEqual((engine.phase, engine.tick), ('ready', 1))
        self.assertEqual(engine.rng.getstate(), random_state)
        self.assertEqual(finish(engine), frozen.run_episode([actor] * 3, config(),
                                                          seed=942, replay=True))

    def test_snapshot_preserves_module_aliases_and_list_cycles(self):
        actor = CandidateProgram("""memory = [[]]

def member_policy(observation, state):
    memory[0].append(observation['tick'])
    if len(memory) == 1:
        memory.append(memory[0])
        memory.append(memory)
    size = len(memory[1]) + len(memory[2][0])
    return {'action': 'harvest', 'effort': .2 * (size % 5)}

def institution(observation, state):
    return {'tax_rate': .2, 'public_fraction': .3}
""")
        engine = stepwise.StepwiseEcology([actor] * 3, config(), seed=541, replay=True)
        for _ in range(4):
            engine.step()
        restored = stepwise.StepwiseEcology.from_snapshot(
            json.loads(json.dumps(engine.snapshot())))
        expected = frozen.run_episode([actor] * 3, config(), seed=541, replay=True)
        self.assertEqual(finish(restored), expected)
        self.assertEqual(finish(engine), expected)

    def test_unsupported_tuple_cycle_rejects_before_creating_checkpoint(self):
        actor = CandidateProgram("""memory = []

def member_policy(observation, state):
    if not memory:
        link = []
        item = (link,)
        link.append(item)
        memory.append(item)
    return {'action': 'rest'}

def institution(observation, state):
    return {}
""")
        engine = stepwise.StepwiseEcology([actor] * 3, config(), seed=21)
        engine.step()
        with self.assertRaisesRegex(ValueError, '[Uu]nsupported.*tuple cycle'):
            engine.snapshot()
        self.assertEqual(finish(engine), frozen.run_episode([actor] * 3, config(), seed=21))

    def test_module_sets_reject_snapshot_instead_of_changing_iteration_order(self):
        actor = CandidateProgram("""seen = {1, 2}

def member_policy(observation, state):
    seen.update([observation['tick']])
    return {'action': 'harvest', 'effort': .2 * (len(seen) % 5)}

def institution(observation, state):
    return {'tax_rate': .2, 'public_fraction': .3}
""")
        engine = stepwise.StepwiseEcology([actor] * 3, config(), seed=620)
        engine.step()
        with self.assertRaisesRegex(ValueError, '[Uu]nsupported.*set'):
            engine.snapshot()
        self.assertEqual(finish(engine), frozen.run_episode([actor] * 3, config(), seed=620))

    def test_candidate_errors_are_terminal_and_never_silently_substituted(self):
        for actor, advance in (
            (program("return {'action': 'unknown'}"), 'member'),
            (program("return {'action': 'rest'}", "return {'state': []}"), 'institution'),
        ):
            with self.subTest(advance=advance):
                engine = stepwise.StepwiseEcology([actor] * 3, config())
                engine.begin_tick()
                if advance == 'member':
                    engine.set_institution_decisions()
                    target = engine.finish_tick
                else:
                    target = engine.set_institution_decisions
                with self.assertRaises(CandidateError):
                    target()
                self.assertEqual(engine.phase, 'failed')
                for method in (engine.step, engine.result, engine.snapshot):
                    with self.assertRaises(ValueError):
                        method()


if __name__ == '__main__':
    unittest.main()
