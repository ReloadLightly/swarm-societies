import unittest
from pathlib import Path
from swarm_societies.candidate import CandidateError, CandidateProgram
from swarm_societies.ecology import EcologyConfig, run_episode

ROOT = Path(__file__).resolve().parents[1]
SEEDS = [ROOT / 'seeds' / f'{name}.py' for name in ('initial','cooperative','selfish')]
SMALL = EcologyConfig(n_societies=3, members_per_society=3, ticks=20, disturbance_tick=10)


def program(member, institution="return {'redistribution': [1 for x in observation['members']]}"):
    return CandidateProgram('def member_policy(observation, private_state):\n    ' + member.replace('\n','\n    ') +
                            '\n\ndef institution(observation, shared_state):\n    '+institution.replace('\n','\n    '))


class EcologyTests(unittest.TestCase):
    def test_reproducibility_conservation_and_nonnegative_stocks(self):
        first = run_episode(SEEDS, SMALL, 217, True)
        second = run_episode(SEEDS, SMALL, 217, True)
        self.assertEqual(first['digest'], second['digest'])
        self.assertAlmostEqual(first['ledger']['residual'], 0, places=8)
        for frame in first['replay']:
            self.assertTrue(all(p >= 0 for p in frame['patches']))
            self.assertTrue(all(m['wealth'] >= 0 for s in frame['societies'] for m in s['members']))
        self.assertNotEqual(first['digest'], run_episode(SEEDS, SMALL, 218)['digest'])

    def test_institution_has_material_effect(self):
        members = [[SEEDS[0]] * 3 for _ in range(3)]
        a = run_episode([SEEDS[0]] * 3, SMALL, 42, member_programs=members)
        b = run_episode([SEEDS[1]] * 3, SMALL, 42, member_programs=members)
        self.assertNotEqual(a['aggregate']['mean_welfare'], b['aggregate']['mean_welfare'])
        self.assertNotEqual(a['ledger']['investment'], b['ledger']['investment'])

    def test_opponent_changes_focal_fitness(self):
        a = run_episode([SEEDS[0], SEEDS[1], SEEDS[1]], SMALL, 42)
        b = run_episode([SEEDS[0], SEEDS[2], SEEDS[2]], SMALL, 42)
        self.assertNotEqual(a['society_metrics'][0]['mean_individual_utility'],
                            b['society_metrics'][0]['mean_individual_utility'])

    def test_partner_changes_focal_fitness(self):
        a_members = [[SEEDS[0]] * 3 for _ in range(3)]
        b_members = [[SEEDS[0], SEEDS[2], SEEDS[2]], a_members[1], a_members[2]]
        a = run_episode([SEEDS[0]] * 3, SMALL, 42, member_programs=a_members)
        b = run_episode([SEEDS[0]] * 3, SMALL, 42, member_programs=b_members)
        self.assertNotEqual(a['member_metrics'][0]['utility'], b['member_metrics'][0]['utility'])

    def test_private_and_shared_memory_and_partial_observation(self):
        p = program("\n".join([
            "allowed = ['tick','society_id','member_id','n_societies','n_members','wealth','productivity','infrastructure','tax_rate','patches','messages','last_action']",
            "if sorted(observation.keys()) != sorted(allowed): return {'action': 'invalid'}",
            "if len(observation['patches']) != 2: return {'action': 'invalid'}",
            "n = private_state.get('n', 0)",
            "if observation['messages'].get('count') != n: return {'action': 'invalid'}",
            "return {'action': 'harvest' if n % 2 else 'rest', 'state': {'n': n + 1}, 'message': {'count': n}}"
        ]), "n = shared_state.get('n', 0)\nreturn {'messages': {'count': n}, 'state': {'n': n + 1}, 'redistribution': [1 for x in observation['members']]}" )
        result = run_episode([p]*3, SMALL, 7)
        self.assertTrue(all(m['actions'] == {'rest': 10, 'harvest': 10} for m in result['member_metrics']))

    def test_observation_mutation_cannot_change_truth(self):
        plain = program("return {'action': 'rest'}")
        mutant = program("observation['wealth'] = 999999\nreturn {'action': 'rest'}")
        a, b = run_episode([plain]*3, SMALL, 7), run_episode([mutant]*3, SMALL, 7)
        self.assertEqual(a['aggregate'], b['aggregate'])
        self.assertEqual(a['ledger'], b['ledger'])

    def test_candidate_security_and_limits(self):
        for source in ("import os", "def member_policy(o,s):\n return o.__class__"):
            with self.assertRaises(CandidateError): CandidateProgram(source)
        looping = program("while True:\n    pass")
        with self.assertRaises(CandidateError): looping.call('member_policy', {}, {}, max_lines=20)
        nan = program("return {'bad': float('nan')}")
        with self.assertRaises(CandidateError): nan.call('member_policy', {}, {})

    def test_disturbance_is_material_not_just_label(self):
        config = EcologyConfig(n_societies=3, members_per_society=3, ticks=30, disturbance_tick=15)
        undisturbed = EcologyConfig(n_societies=3, members_per_society=3, ticks=30, disturbance_tick=15, drought_factor=1.)
        a = run_episode(SEEDS, config, 1)
        b = run_episode(SEEDS, undisturbed, 1)
        self.assertLess(a['ledger']['regeneration'], b['ledger']['regeneration'])
        self.assertEqual([s['pre'] for s in a['society_metrics']], [s['pre'] for s in b['society_metrics']])


if __name__ == '__main__':
    unittest.main()
