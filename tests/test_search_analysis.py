"""Posthoc observability must reproduce selection without changing it."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from swarm_societies.evaluation import ROOT, atomic_json, evaluate_search, initialize_context, read_json

_spec=importlib.util.spec_from_file_location('analyze_search',ROOT/'scripts/analyze_search.py')
_analysis=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_analysis)


class SearchAnalysisTests(unittest.TestCase):
    def test_historical_comparisons_reproduce_without_altering_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            context=base/'evolution_context.json'
            initialize_context(context,members=2,steps=2)
            evaluate_search(ROOT/'seeds/initial.py',base/'gen_0/results',context)
            inactive=base/'inactive.py'
            inactive.write_text("def member_policy(observation, private_state):\n return {'action':'rest'}\n"
                                "def institution(observation, shared_state):\n return {}\n")
            evaluate_search(inactive,base/'gen_1/results',context)
            investor=base/'investor.py'
            investor.write_text("def member_policy(observation, private_state):\n return {'action':'rest'}\n"
                                "def institution(observation, shared_state):\n return {'tax_rate':.35,'public_fraction':1}\n")
            evaluate_search(investor,base/'gen_2/results',context)
            original=context.read_bytes()
            report=_analysis.analyze_search(base)
            self.assertEqual(context.read_bytes(),original)
            self.assertEqual(report['analyzed_evaluations'],2)
            self.assertEqual(report['accepted_evaluations'],1)
            member,institution=report['evaluations']
            self.assertFalse(member['accepted'])
            self.assertTrue(institution['accepted'])
            self.assertEqual(member['mean_after']['selected_action_rest'],2)
            self.assertEqual(member['mean_after']['selected_action_raid'],0)
            self.assertLess(member['mean_difference']['selected_member_utility'],0)
            self.assertIn('other_overall_welfare',institution['mean_difference'])
            self.assertEqual(len(institution['cases'][0]['after']['members']),6)
            state=read_json(context)
            state['evaluations'][1]['case_objectives']['candidate'][0]+=1
            atomic_json(context,state)
            with self.assertRaisesRegex(ValueError,'Replayed objective differs'):
                _analysis.analyze_search(base)


if __name__=='__main__': unittest.main()
