"""Reject published summary and scenario tampering without altering frozen code."""
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.verify_mechanism_evidence import verify
from swarm_societies.evaluation import ROOT, atomic_json, read_json


class MechanismVerificationTests(unittest.TestCase):
    def test_published_evidence_verifies(self):
        result = verify(ROOT/'evidence/mechanism-v1')
        self.assertEqual(result['n_rollouts'], 864)
        self.assertEqual(result['n_cases_per_population'], 108)

    def test_rejects_top_level_results_counts_hashes_and_raw_case_corruption(self):
        corruptions = (
            ('summary.json', 'results', 'Top-level results'),
            ('summary.json', 'count', 'Top-level rollout'),
            ('summary.json', 'hash', 'Top-level manifest'),
            ('initial.json', 'scenario', 'Raw scenario'),
            ('initial.json', 'duplicate', 'factorial case'),
            ('initial.json', 'missing', 'factorial case'),
        )
        for filename, mode, message in corruptions:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)/'evidence'
                shutil.copytree(ROOT/'evidence/mechanism-v1', directory)
                path = directory/filename
                data = read_json(path)
                if mode == 'results': data['results'][0]['drought']['welfare'] += .1
                elif mode == 'count': data['n_rollouts_total'] -= 1
                elif mode == 'hash': data['manifest_sha256'] = '0'*64
                elif mode == 'scenario': data['rows'][0]['case']['config']['ticks'] += 1
                elif mode == 'duplicate': data['rows'][0] = data['rows'][1]
                elif mode == 'missing': data['rows'].pop()
                atomic_json(path, data)
                with self.assertRaisesRegex(ValueError, message): verify(directory)


if __name__ == '__main__':
    unittest.main()
