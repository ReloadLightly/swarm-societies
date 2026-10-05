"""Independent checks of paired inference and portable published evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from swarm_societies.ecology import run_episode
from swarm_societies.evaluation import ROOT, atomic_json, digest, initialize_context
from swarm_societies.experiment import METRICS, aggregate, evaluate_case, paired_comparison

_spec=importlib.util.spec_from_file_location('verify_evidence', ROOT/'scripts/verify_evidence.py')
_verifier=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_verifier)
verify_evidence, EvidenceError = _verifier.verify_evidence, _verifier.EvidenceError


def build_evidence(directory):
    directory=Path(directory)
    state=initialize_context(directory/'final_population.json', members=2, steps=2)
    for key,relative in [('simulator_sha256','swarm_societies/ecology.py'),
                         ('candidate_runtime_sha256','swarm_societies/candidate.py')]:
        state[key]=digest((ROOT/relative).read_text())
    atomic_json(directory/'final_population.json',state)
    cases=[{'seed':seed,'opponents':panel,'focal':focal} for seed in (9001,9002)
           for panel in ('initial','cooperative','selfish') for focal in range(3)]
    atomic_json(directory/'fresh_cases.json',{'cases':cases})
    results=[]
    rows_by_name={}
    for name,label,institutions in [
        ('initial_population','Initial population',state['initial_institutions']),
        ('fixed_institution','Fixed cooperative institution',[str(ROOT/'seeds/cooperative.py')]*3)
    ]:
        rows=[evaluate_case((case,institutions,state['initial_members'],state['initial_institutions'],
                             state['initial_members'],state['config'],
                             dict(zip(('initial','cooperative','selfish'),state['initial_institutions'])))) for case in cases]
        summary=aggregate(label,rows)
        atomic_json(directory/f'{name}.json',{'rows':rows,'summary':summary,'label':label})
        rows_by_name[name]=rows
        results.append(summary)
    comparisons=[paired_comparison('fixed_institution - initial_population',
                                    rows_by_name['fixed_institution'],rows_by_name['initial_population'])]
    atomic_json(directory/'comparisons.json',comparisons)
    counts={'accepted_member_updates':0,'accepted_institution_updates':0,
            'evaluator_jobs':0,'unique_evaluated_programs':0,'valid_evaluator_jobs':0,'invalid_evaluator_jobs':0}
    atomic_json(directory/'summary.json',{'status':'running','results':results,'search_counts':counts,'lineage':[]})
    atomic_json(directory/'search_evaluations.json',[])
    replay=run_episode(state['institutions'],state['config'],424242,True,member_programs=state['members'])
    replay['population_label']='Final ecological population'
    atomic_json(directory/'replay.json',replay)


class ExperimentTests(unittest.TestCase):
    def test_seed_clusters_not_members_or_case_count_are_uncertainty_unit(self):
        old=[]
        new=[]
        for seed, differences in [(10,[1,2,3]),(20,[-3,-2,-1])]:
            for focal,difference in enumerate(differences):
                row={'seed':seed,'opponents':'initial','focal':focal,**{key:10. for key in METRICS}}
                old.append(row)
                new.append({**row,**{key:10.+difference for key in METRICS}})
        result=paired_comparison('new - old',new,old)
        self.assertEqual(result['n_cases'],6)
        self.assertEqual(result['n_environment_seeds'],2)
        self.assertEqual(result['welfare']['mean_difference'],0)
        # Resampling the two seed means gives endpoints -2 and +2, rather
        # than treating six focal-society rows as independent replicates.
        self.assertEqual(result['welfare']['seed_cluster_bootstrap_95'],[-2.,2.])

    def test_portable_evidence_verification_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            build_evidence(base)
            result=verify_evidence(base)
            self.assertEqual(result['status'],'passed')
            self.assertEqual(result['fresh_cases_per_treatment'],18)
            with self.assertRaisesRegex(EvidenceError,'interim'):
                verify_evidence(base,require_final=True)
            source=next((base/'programs').glob('*.py'))
            original_source=source.read_text()
            source.write_text(original_source+'\n# tampered\n')
            with self.assertRaisesRegex(EvidenceError,'Source checksum'):
                verify_evidence(base)
            source.write_text(original_source)
            target=base/'initial_population.json'
            original=target.read_text()
            changed=json.loads(original)
            changed['rows'][0]['seed']=changed['rows'][1]['seed']
            changed['rows'][0]['focal']=changed['rows'][1]['focal']
            atomic_json(target,changed)
            with self.assertRaisesRegex(EvidenceError,'Duplicate fresh-case'):
                verify_evidence(base)
            target.write_text(original)
            changed=json.loads(original)
            changed['summary']['welfare']+=.1
            atomic_json(target,changed)
            with self.assertRaisesRegex(EvidenceError,'Metric mismatch'):
                verify_evidence(base)
            target.write_text(original)
            replay=base/'replay.json'
            changed=json.loads(replay.read_text())
            changed['replay'][0]['patches'][0]+=.01
            atomic_json(replay,changed)
            with self.assertRaisesRegex(EvidenceError,'replay digest'):
                verify_evidence(base)


if __name__=='__main__':
    unittest.main()
