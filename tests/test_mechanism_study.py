"""Pairing, negative controls, and portable evidence for post-hoc transplants."""
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.run_mechanism_study import LABELS, METRICS, factorial_rows, make_cases, prepare, verify_inputs
from scripts.evaluate_consumption_study import case_metrics
from swarm_societies.consumption_evaluation import initialize_context
from swarm_societies.consumption_study import make_fresh_cases, make_search_cases
from swarm_societies.evaluation import atomic_json


class MechanismStudyTests(unittest.TestCase):
    def test_factorial_pairing_detects_missing_duplicate_and_mismatched_cases(self):
        row = {'case': {'id': 'case-0', 'seed': 100}, 'focal': 0, 'opponents': 'initial',
               'drought': {m: 1. for m in METRICS}, 'no_drought': {m: 2. for m in METRICS},
               'drought_welfare_effect': -1.}
        populations = {label: [deepcopy(row)] for label in LABELS}
        for label, value in [('members_only', 2.), ('institutions_only', 3.), ('coevolution', 8.)]:
            populations[label][0]['drought']['welfare'] = value
        manifest = {'contrasts': {'interaction': {'coevolution': 1, 'members_only': -1, 'institutions_only': -1, 'initial': 1}}}
        result = factorial_rows(populations, manifest)
        self.assertEqual(result[0]['contrasts']['interaction']['drought']['welfare'], 4.)
        for corruption in ('missing', 'duplicate', 'scenario'):
            changed = deepcopy(populations)
            if corruption == 'missing': changed['initial'] = []
            elif corruption == 'duplicate': changed['initial'] *= 2
            else: changed['initial'][0]['case']['seed'] = 101
            with self.assertRaises(ValueError): factorial_rows(changed, manifest)

    def test_new_case_namespace_and_portable_programs_preserve_replay(self):
        self.assertEqual(make_cases(), make_cases())
        previous = make_fresh_cases() + make_search_cases(2026100501)
        self.assertFalse({c['seed'] for c in make_cases()} & {c['seed'] for c in previous})
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            context = base/'source/context.json'
            initialize_context(context, 'coevolution', 1, 2026100501)
            original = base/'original'
            manifest = prepare(original, context)
            copied = base/'copied'
            shutil.copytree(original, copied)
            shutil.rmtree(base/'source')
            self.assertEqual(verify_inputs(copied), manifest)
            case = deepcopy(make_cases()[0])
            case['config'].update(ticks=5, disturbance_tick=2)
            outcomes = []
            for directory in (original, copied):
                pop = manifest['populations']['initial']
                institutions = [str(directory/p) for p in pop['institutions']]
                members = [[str(directory/p) for p in row] for row in pop['members']]
                outcomes.append(case_metrics((case, 'selfish', 0, institutions, members, institutions, members)))
            self.assertEqual(outcomes[0], outcomes[1])
            source = next((copied/'programs').glob('*.py'))
            source.write_text(source.read_text()+'\n# changed\n')
            with self.assertRaisesRegex(ValueError, 'checksum'): verify_inputs(copied)


if __name__ == '__main__':
    unittest.main()
