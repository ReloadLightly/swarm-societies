#!/usr/bin/env python3
"""Replay completed search comparisons to recover all societal externalities.

This analysis never modifies selection, candidates, prompts, or checkpoints.
It uses only the exact recorded search seeds and ecological population snapshots.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from swarm_societies.evaluation import atomic_json, objective, simulate

ACTIONS=('harvest','contribute','raid','share','rest','guard')
SOCIETY_METRICS=('welfare','consumption','shortfall','infrastructure','mean_wealth','wealth_gini',
                 'harvest','tax','contribution','investment','redistribution','cooperation_within',
                 'cooperation_between','external_harm','harm_received','within_conflict','raid_gain',
                 'raid_attempts','within_raid_attempts','inter_raid_attempts','aid_given','aid_received')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_source(path, directory):
    name=Path(path).name
    choices=[directory/'programs'/name,Path(path),ROOT/path]
    for candidate in choices:
        if candidate.is_file():
            if len(candidate.stem)==64 and sha(candidate)!=candidate.stem:
                raise ValueError(f'Source checksum mismatch: {candidate}')
            return str(candidate.resolve())
    raise FileNotFoundError(f'Recorded source unavailable: {path}')


def measured(episode, kind, society, member):
    own=episode['society_metrics'][society]
    own_members=[row for row in episode['member_metrics'] if row['society_id']==society]
    selected=next((row for row in own_members if row['member_id']==member),None) if kind=='member' else None
    peers=[row for row in own_members if row['member_id']!=member] if kind=='member' else []
    scalar={'objective':objective(episode,kind,society,member),
            'focal_mean_individual_utility':own['mean_individual_utility'],
            'focal_final_mean_wealth':own['final_mean_wealth'],
            'focal_adaptation':own['adaptation'],
            'global_welfare':episode['aggregate']['mean_welfare'],
            'global_external_harm':episode['aggregate']['external_harm']}
    if selected:
        scalar.update(selected_member_utility=selected['utility'],
                      selected_member_consumption=selected['consumption'],
                      selected_member_final_wealth=selected['final_wealth'],
                      selected_member_contribution=selected['contribution'],
                      selected_member_raid_gain=selected['raid_gain'],
                      selected_member_raid_loss=selected['raid_loss'],
                      peers_mean_utility=statistics.mean(row['utility'] for row in peers))
    for phase in ('pre','post','overall'):
        scalar.update({f'focal_{phase}_{key}':own[phase][key] for key in SOCIETY_METRICS})
        scalar[f'other_{phase}_welfare']=statistics.mean(row[phase]['welfare'] for index,row in enumerate(episode['society_metrics']) if index!=society)
    for action in ACTIONS:
        scalar[f'focal_action_{action}']=sum(row['actions'].get(action,0) for row in own_members)
        if selected:
            scalar[f'selected_action_{action}']=selected['actions'].get(action,0)
    return {'metrics':scalar,'members':episode['member_metrics'],
            'societies':[{'society_id':row['society_id'],
                          'mean_individual_utility':row['mean_individual_utility'],
                          'final_mean_wealth':row['final_mean_wealth'],
                          'adaptation':row['adaptation'],
                          **{phase:{key:row[phase][key] for key in SOCIETY_METRICS}
                             for phase in ('pre','post','overall')}} for row in episode['society_metrics']],
            'ledger_residual':episode['ledger']['residual']}


def average(measurements):
    return {key:statistics.mean(row['metrics'][key] for row in measurements)
            for key in measurements[0]['metrics']}


def check_objective(actual, expected, label):
    if not math.isclose(actual,expected,rel_tol=1e-11,abs_tol=1e-11):
        raise ValueError(f'Replayed objective differs from stored selection evidence ({label}): {actual} != {expected}')


def analyze_search(run_dir, output=None, *, evaluations=None, progress=False):
    directory=Path(run_dir).resolve()
    context=directory/'evolution_context.json'
    if not context.exists(): context=directory/'final_population.json'
    context_bytes=context.read_bytes()
    state=json.loads(context_bytes)
    context_hash=hashlib.sha256(context_bytes).hexdigest()
    for key,relative in [('simulator_sha256','swarm_societies/ecology.py'),
                         ('candidate_runtime_sha256','swarm_societies/candidate.py')]:
        if key in state and sha(ROOT/relative)!=state[key]:
            raise ValueError(f'Frozen engine source changed: {relative}')
    requested=set(evaluations) if evaluations is not None else None
    records=[row for row in state['evaluations'] if row.get('valid') and row['kind'] in ('member','institution')
             and (requested is None or row['evaluation'] in requested)]
    output_records=[]
    for ev in records:
        before=ev['population_before']
        institutions=[resolve_source(path,directory) for path in before['institutions']]
        members=[[resolve_source(path,directory) for path in row] for row in before['members']]
        candidate=resolve_source(ev['program_path'],directory)
        if sha(candidate)!=ev['program_sha256']:
            raise ValueError(f'Candidate source differs from recorded evaluation {ev["evaluation"]}')
        after_institutions=institutions.copy()
        after_members=[row.copy() for row in members]
        kind,society,member=ev['kind'],ev['target_society'],ev['target_member']
        predecessor=members[society][member] if kind=='member' else institutions[society]
        if sha(predecessor)!=ev['ecological_predecessor_sha256']:
            raise ValueError(f'Historical incumbent source mismatch: evaluation {ev["evaluation"]}')
        if kind=='member': after_members[society][member]=candidate
        else: after_institutions[society]=candidate
        cases=[]
        for index,seed in enumerate(ev['search_seeds']):
            incumbent=simulate(institutions,members,state['config'],seed)
            challenger=simulate(after_institutions,after_members,state['config'],seed)
            old=measured(incumbent,kind,society,member)
            new=measured(challenger,kind,society,member)
            check_objective(old['metrics']['objective'],ev['case_objectives']['incumbent'][index],f'{ev["evaluation"]}/{seed}/incumbent')
            check_objective(new['metrics']['objective'],ev['case_objectives']['candidate'][index],f'{ev["evaluation"]}/{seed}/candidate')
            cases.append({'seed':seed,'before':old,'after':new})
        old_mean=average([case['before'] for case in cases])
        new_mean=average([case['after'] for case in cases])
        difference={key:new_mean[key]-old_mean[key] for key in old_mean}
        check_objective(old_mean['objective'],ev['incumbent_objective'],f'{ev["evaluation"]}/mean incumbent')
        check_objective(new_mean['objective'],ev['candidate_objective'],f'{ev["evaluation"]}/mean candidate')
        check_objective(difference['objective'],ev['paired_gain'],f'{ev["evaluation"]}/paired gain')
        expected_acceptance=difference['objective']>1e-9
        if bool(ev['accepted'])!=expected_acceptance:
            raise ValueError(f'Acceptance rule disagrees with measured objectives: evaluation {ev["evaluation"]}')
        notes=[]
        if kind=='member' and new_mean['selected_action_raid']==0:
            notes.append('The selected member made zero raids on these search cases. Raiding or raid-learning code is not evidence of realized raid behavior here.')
        if kind=='member' and new_mean['selected_action_contribute']==0:
            notes.append('The selected member made zero voluntary contributions on these search cases; tax payments remain a separate form of material pooling.')
        notes.append('Only the scheduled component was substituted; edits to the other component in the source were not executed for this comparison.')
        record={'evaluation':ev['evaluation'],'job_id':str(ev['job_id']).replace(str(ROOT)+'/', ''),
                'kind':kind,'target_society':society,'target_member':member,
                'accepted':ev['accepted'],'program_sha256':ev['program_sha256'],
                'ecological_predecessor_sha256':ev['ecological_predecessor_sha256'],
                'search_seeds':ev['search_seeds'],
                'population_before_hashes':{'institutions':[sha(path) for path in institutions],
                                            'members':[[sha(path) for path in row] for row in members]},
                'objective_verification':'all paired case objectives and stored mean gains reproduced',
                'mean_before':old_mean,'mean_after':new_mean,'mean_difference':difference,
                'notes':notes,'cases':cases}
        output_records.append(record)
        if progress:
            print(json.dumps({'evaluation':ev['evaluation'],'kind':kind,'accepted':ev['accepted'],
                              'objective_gain':difference['objective'],
                              'other_societies_welfare_change':difference['other_overall_welfare']}),flush=True)
    report={'schema_version':1,'analysis':'posthoc deterministic replay; never used for selection',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'python_version':platform.python_version(),'config':state['config'],
            'source_context_sha256':context_hash,
            'simulator_sha256':sha(ROOT/'swarm_societies/ecology.py'),
            'candidate_runtime_sha256':sha(ROOT/'swarm_societies/candidate.py'),
            'analyzed_evaluations':len(output_records),
            'accepted_evaluations':sum(row['accepted'] for row in output_records),
            'checkpoint_evaluations':len(state['evaluations']),
            'metric_note':'Means are across the recorded paired search seeds for each historical population. They are not fresh evaluation or independent evolutionary replications. Action counts are mean counts per episode.',
            'evaluations':output_records}
    if output is not None: atomic_json(output,report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,default=ROOT/'runs/first')
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/experiment/search-effects.json')
    parser.add_argument('--evaluation',type=int,action='append',help='Optional evaluator index, repeatable; Shinka generation can differ.')
    args=parser.parse_args(argv)
    result=analyze_search(args.run_dir,args.output,evaluations=args.evaluation,progress=True)
    print(json.dumps({'output':str(args.output),'analyzed_evaluations':result['analyzed_evaluations'],
                      'accepted_evaluations':result['accepted_evaluations']}),flush=True)
    return 0


if __name__=='__main__': raise SystemExit(main())
