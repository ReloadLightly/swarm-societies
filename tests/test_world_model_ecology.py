from collections import defaultdict
from dataclasses import asdict
import hashlib
from pathlib import Path
import unittest

from swarm_societies.candidate import CandidateProgram
from swarm_societies.ecology_consumption_v2 import EcologyConfig as FrozenConfig, run_episode as run_frozen
from swarm_societies.ecology_world_model_v1 import EcologyConfig, WorldParameters, run_episode


ROOT = Path(__file__).resolve().parents[1]
SEEDS = [ROOT / 'seeds' / f'{name}.py' for name in ('initial', 'cooperative', 'selfish')]


def config(**changes):
    return EcologyConfig(**{'n_societies': 3, 'members_per_society': 3,
                            'ticks': 11, 'disturbance_tick': 5, **changes})


def program(member, institution="return {'tax_rate': 0.2, 'public_fraction': 0.3}"):
    return CandidateProgram('def member_policy(observation, state):\n    ' +
                            member.replace('\n', '\n    ') +
                            '\n\ndef institution(observation, state):\n    ' +
                            institution.replace('\n', '\n    ') + '\n')


class WorldModelEcologyTests(unittest.TestCase):
    def test_frozen_sources_unchanged(self):
        expected = {
            'ecology.py': '76e4ba5a2abf4f20356c8c4710d0a5632b50cd87e97d363c27b556642508eba7',
            'ecology_consumption_v2.py': '82c3ffe2e9431541e6e0cfbda6c97bccadfe87518bd3d17ff7661434d84e2344',
            'candidate.py': '0ff988ac0a8b05ca0919bb67267e6645a232fb49530cfbd51122c6b8d1dfa89b',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / 'swarm_societies' / name).read_bytes()).hexdigest(), digest)

    def test_default_world_has_exact_frozen_material_trajectory(self):
        for seed, regeneration, disturbed in ((0, 8.5, True), (731, 2.7, False), (42, 15.1, True)):
            with self.subTest(seed=seed):
                cfg = config(regeneration=regeneration, enable_disturbance=disturbed)
                frozen = run_frozen(SEEDS, FrozenConfig(**asdict(cfg)), seed, replay=True)
                for mode in ('local', 'full_observation_control'):
                    actual = run_episode(SEEDS, cfg, seed, replay=True, observation_mode=mode)
                    for key in frozen:
                        if key not in ('digest', 'schema_version'):
                            self.assertEqual(actual[key], frozen[key], key)
                    self.assertEqual(actual['legacy_digest'], frozen['digest'])
                    self.assertEqual(actual['audit']['world_parameters']['r'], regeneration)

    def test_receipts_reconcile_personal_and_global_resource_accounts(self):
        result = run_episode(SEEDS, config(), seed=712, replay=True)
        receipts = result['local_observations']['member_receipts']
        grouped = defaultdict(list)
        for row in receipts:
            expected = (row['wealth_before'] + row['harvest'] + row['raid_gain'] + row['redistribution']
                        - row['cost'] - row['tax'] - row['contribution'] - row['share']
                        - row['raid_loss'] - row['consumption'])
            self.assertAlmostEqual(row['wealth_after'], expected, places=12)
            grouped[row['tick'], row['society_id']].append(row)
        for key, receipt_key in (('effort_cost', 'cost'), ('consumption', 'consumption')):
            self.assertAlmostEqual(result['ledger'][key], sum(row[receipt_key] for row in receipts))
        destruction = sum(row['raid_loss'] - row['raid_gain'] for row in receipts)
        self.assertGreater(destruction, 0)
        self.assertAlmostEqual(result['ledger']['raid_destruction'], destruction)
        for row in result['local_observations']['institution_receipts']:
            self.assertAlmostEqual(row['budget'], row['investment'] + row['defense_expenditure'] +
                                   row['redistribution'] + row['treasury_after'])
            self.assertAlmostEqual(row['tax'], sum(r['tax'] for r in grouped[row['tick'], row['society_id']]))
            self.assertAlmostEqual(row['redistribution'], sum(r['redistribution'] for r in grouped[row['tick'], row['society_id']]))
        self.assertAlmostEqual(result['ledger']['regeneration'], sum(row['growth'] for row in result['learning_observations']))
        self.assertAlmostEqual(result['ledger']['residual'], 0, places=9)

    def test_phase_sensors_are_complete_local_and_match_material_events(self):
        cfg = config()
        result = run_episode(SEEDS, cfg, seed=81, replay=True)
        rows = result['local_observations']['patch_measurements']
        by_observer = defaultdict(list)
        physical = {}
        for row in rows:
            key = row['tick'], row['society_id'], row['member_id']
            by_observer[key].append(row)
            visible = {row['society_id'], (row['society_id'] + 1 + (row['member_id'] + row['tick']) % 2) % 3}
            self.assertIn(row['patch'], visible)
            content = {k: v for k, v in row.items() if k not in ('society_id', 'member_id')}
            if row['event_id'] in physical:
                self.assertEqual(physical[row['event_id']], content)
            physical[row['event_id']] = content
        self.assertEqual(len(by_observer), cfg.ticks * cfg.n_societies * cfg.members_per_society)
        for observed in by_observer.values():
            self.assertEqual(len(observed), 8)
            self.assertEqual({row['phase'] for row in observed},
                             {'after_decay', 'before_actions', 'after_actions', 'after_allocation'})
        for row in result['learning_observations']:
            tick, patch = row['tick'], row['patch']
            before = physical[f'patch:{tick}:{patch}:after_decay']
            ready = physical[f'patch:{tick}:{patch}:before_actions']
            after = physical[f'patch:{tick}:{patch}:after_actions']
            final = physical[f'patch:{tick}:{patch}:after_allocation']
            self.assertEqual(before['stock'], row['stock_before'])
            self.assertEqual(ready['stock'], row['stock_after'])
            extracted = sum(e['amount'] for e in result['replay'][tick]['events']
                            if e['kind'] == 'harvest' and e['patch'] == patch)
            self.assertAlmostEqual(ready['stock'] - extracted, after['stock'], places=12)
            self.assertEqual(after['stock'], final['stock'])
            self.assertEqual(final['stock'], result['replay'][tick]['patches'][patch])

    def test_private_truth_never_enters_legal_growth_or_candidate_payloads(self):
        member = """expected = ['tick', 'society_id', 'member_id', 'n_societies', 'n_members', 'wealth', 'productivity', 'infrastructure', 'tax_rate', 'patches', 'messages', 'last_action']
if sorted(observation.keys()) != sorted(expected):
    return {'action': 'invalid'}
return {'action': 'harvest', 'target': observation['society_id']}"""
        institution = """expected = ['tick', 'society_id', 'n_societies', 'treasury', 'infrastructure', 'mean_wealth', 'members', 'reports']
if sorted(observation.keys()) != sorted(expected):
    return {'redistribution': []}
return {'tax_rate': 0.2, 'public_fraction': 0.3}"""
        actor = program(member, institution)
        for mode in ('local', 'full_observation_control'):
            result = run_episode([actor] * 3, config(), seed=59,
                                 world_parameters=WorldParameters(r=3.1, b=1.7, g=.4),
                                 observation_mode=mode)
            for row in result['learning_observations']:
                self.assertEqual(row['society_id'], row['patch'])
                self.assertEqual('other_infrastructure' in row, mode == 'full_observation_control')
                self.assertFalse({'seed', 'weather', 'regime', 'r', 'b', 'g', 'world_parameters',
                                  'future', 'wealth', 'disturbance_tick'} & row.keys())
            self.assertEqual(result['audit']['world_parameters']['r'], 3.1)
            self.assertTrue(all('regime' in row for row in result['audit']['regeneration']))
            self.assertNotIn('weather', result['audit'])

    def test_nondefault_laws_control_growth_cost_and_infrastructure(self):
        cfg = config(initial_patch=3., enable_disturbance=False)
        law = WorldParameters(r=0., b=1.7, g=.6, rho=.72, eta=.3, h=1.6, c=.21)
        result = run_episode(SEEDS, cfg, seed=71, world_parameters=law,
                             observation_mode='full_observation_control')
        for row in result['learning_observations']:
            self.assertAlmostEqual(row['growth'], min(row['capacity_gap'],
                                   law.b*row['own_infrastructure'] + law.g*row['other_infrastructure']))
        previous = {}
        for row in result['local_observations']['institution_receipts']:
            sid = row['society_id']
            self.assertAlmostEqual(row['infrastructure_after_decay'], law.rho*previous.get(sid, 0.))
            self.assertAlmostEqual(row['infrastructure_after_allocation'], row['infrastructure_after_decay'] +
                                   law.eta*row['investment']/cfg.members_per_society)
            previous[sid] = row['infrastructure_after_allocation']
        for row in result['local_observations']['member_receipts']:
            expected = 0. if row['action'] == 'rest' else min(row['wealth_at_resolution'], law.c*row['effort'])
            self.assertEqual(row['cost'], expected)
            if row['action'] == 'harvest' and not row['supply_limited']:
                self.assertAlmostEqual(row['harvest'], law.h*row['productivity']*row['effort'])
        self.assertAlmostEqual(result['ledger']['residual'], 0., places=9)

    def test_rest_is_free_and_full_patches_are_uninformative(self):
        actor = program("return {'action': 'rest'}", "return {}")
        cfg = config(initial_patch=60., enable_disturbance=False)
        result = run_episode([actor]*3, cfg, world_parameters=WorldParameters(c=10.))
        self.assertEqual(result['ledger']['effort_cost'], 0.)
        for row in result['learning_observations']:
            self.assertEqual(row['growth'], 0.)
            self.assertEqual(row['capacity_gap'], 0.)
            self.assertTrue(row['censored'])
        self.assertTrue(all(row['cost'] == 0. for row in result['local_observations']['member_receipts']))

    def test_denied_raids_and_hidden_harvest_targets_have_honest_receipts(self):
        actor = program("""if observation['member_id'] == 0:
    return {'action': 'raid', 'target': (observation['society_id'] + 1) % 3}
visible = [p['id'] for p in observation['patches']]
target = [p for p in range(3) if p not in visible][0]
return {'action': 'harvest', 'target': target}""", "return {'raid_permission': False}")
        result = run_episode([actor]*3, config(), seed=6)
        for row in result['local_observations']['member_receipts']:
            if row['action'] == 'raid':
                self.assertTrue(row['denied'])
                self.assertEqual(row['raid_gain'], 0.)
            else:
                self.assertNotEqual(row['requested_target'], row['target'])
                self.assertEqual(row['target'], row['society_id'])
        self.assertGreater(result['ledger']['effort_cost'], 0.)

    def test_repeatability_and_sensor_streams_do_not_alias(self):
        first = run_episode(SEEDS, config(), seed=132, observation_mode='full_observation_control')
        second = run_episode(SEEDS, config(), seed=132, observation_mode='full_observation_control')
        self.assertEqual(first['digest'], second['digest'])
        saved = first['audit']['regeneration'][0]['growth']
        first['learning_observations'][0]['growth'] = -99.
        self.assertEqual(first['audit']['regeneration'][0]['growth'], saved)
        self.assertEqual(second['learning_observations'][0]['growth'], saved)

    def test_world_parameter_and_sensor_mode_validation(self):
        for invalid in ({'rho': 1.01}, {'r': -1}, {'eta': float('inf')}, {'b': True}, {'c': '0.1'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                run_episode(SEEDS, config(), world_parameters=invalid)
        with self.assertRaises(ValueError):
            run_episode(SEEDS, config(), world_parameters=0)
        with self.assertRaises(ValueError):
            run_episode(SEEDS, config(), observation_mode='omniscient')


if __name__ == '__main__':
    unittest.main()
