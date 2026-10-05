"""Scientific selection invariants exercised against real, small rollouts."""
import json
from pathlib import Path
import tempfile
import unittest
from swarm_societies.evaluation import (ROOT, evaluate_search, initialize_context,
                                        objective, read_json, simulate)


class SelectionTests(unittest.TestCase):
    def test_paired_contextual_selection_persistence_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            context = base / 'context.json'
            state = initialize_context(context, members=2, steps=2)
            first = evaluate_search(ROOT / 'seeds/initial.py', base / 'job0', context)
            self.assertTrue(first['valid'])
            self.assertFalse(first['accepted'])
            self.assertEqual(first['paired_gain'], 0)
            # Deliberately inactive mutant loses private consumption/buffer utility.
            rest = base / 'rest.py'
            rest.write_text("def member_policy(observation, private_state):\n return {'action':'rest'}\n"
                            "def institution(observation, shared_state):\n return {}\n")
            negative = evaluate_search(rest, base / 'job1', context)
            self.assertTrue(negative['valid'])
            self.assertFalse(negative['accepted'])
            self.assertLess(negative['paired_gain'], 0)
            self.assertEqual(read_json(context)['members'], state['members'])
            # At this short horizon reserves meet needs; stronger investment changes
            # the declared collective objective while the member matrix stays fixed.
            invest = base / 'invest.py'
            invest.write_text("def member_policy(observation, private_state):\n return {'action':'rest'}\n"
                              "def institution(observation, shared_state):\n"
                              " return {'tax_rate':0.35,'public_fraction':1.0}\n")
            positive = evaluate_search(invest, base / 'job2', context)
            self.assertTrue(positive['valid'])
            self.assertTrue(positive['accepted'])
            latest = read_json(context)
            self.assertEqual(latest['members'], state['members'])
            self.assertEqual(latest['accepted_institution_updates'], 1)
            self.assertEqual(latest['institutions'][0], positive['program_path'])
            self.assertEqual(positive['population_before']['institutions'], state['institutions'])
            for index, seed in enumerate(positive['search_seeds']):
                before = simulate(state['institutions'], state['members'], state['config'], seed)
                after = simulate(latest['institutions'], state['members'], state['config'], seed)
                self.assertEqual(positive['case_objectives']['incumbent'][index], objective(before,'institution',0,0))
                self.assertEqual(positive['case_objectives']['candidate'][index], objective(after,'institution',0,0))
            again = evaluate_search(rest, base / 'job2', context)
            self.assertEqual(again, positive)
            self.assertEqual(len(read_json(context)['evaluations']), 3)
            self.assertTrue(json.loads((base/'job2/correct.json').read_text())['correct'])

    def test_invalid_candidate_is_not_accepted_or_given_fitness_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            context = base/'context.json'
            state = initialize_context(context, members=2, steps=2)
            evaluate_search(ROOT/'seeds/initial.py', base/'job0', context)
            bad = base/'bad.py'
            bad.write_text('import os\n')
            rejected = evaluate_search(bad, base/'job1', context)
            latest = read_json(context)
            self.assertFalse(rejected['valid'])
            self.assertFalse(rejected['accepted'])
            self.assertLess(rejected['combined_score'], 0)
            self.assertIn('unsupported syntax', rejected['error'])
            self.assertEqual(state['members'], latest['members'])
            self.assertEqual(state['institutions'], latest['institutions'])


if __name__ == '__main__':
    unittest.main()
