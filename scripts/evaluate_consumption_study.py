#!/usr/bin/env python3
"""Evaluate frozen final v2 populations against common fresh/no-drought cases."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_societies.consumption_study import simulate_consumption
from swarm_societies.consumption_evaluation import verify_frozen_sources, file_hash
from swarm_societies.evaluation import ROOT, atomic_json, read_json


def case_metrics(job):
    case, panel, focal, institutions, members, initial_institutions, initial_members = job
    if panel == 'initial':
        others, peers = initial_institutions.copy(), [row.copy() for row in initial_members]
    else:
        # Frozen seed snapshots are in every context's initial population.
        source = initial_institutions[1 if panel=='cooperative' else 2]
        others, peers = [source]*3, [[source]*4 for _ in range(3)]
    others[focal], peers[focal] = institutions[focal], members[focal]
    row={'case':case, 'opponents':panel, 'focal':focal}
    for name, enabled in [('drought',True),('no_drought',False)]:
        episode=simulate_consumption(others,peers,case,disturbance=enabled)
        own=episode['society_metrics'][focal]
        ticks=episode['config']['ticks']
        post=ticks-episode['config']['disturbance_tick']
        row[name]={'welfare':own['overall']['welfare'],'post_welfare':own['post']['welfare'],
                   'pre_welfare':own['pre']['welfare'],
                   'utility_per_tick':own['normalized_mean_individual_utility'],
                   'raw_individual_utility':own['mean_individual_utility'],
                   'final_mean_wealth':own['final_mean_wealth'],
                   'shortfall_per_member_tick':own['overall']['shortfall']/(4*ticks),
                   'post_shortfall_per_member_tick':own['post']['shortfall']/(4*post),
                   'consumption_per_member_tick':own['overall']['consumption']/(4*ticks),
                   'outward_harm_per_tick':own['overall']['external_harm']/ticks,
                   'voluntary_contribution_per_tick':own['overall']['contribution']/ticks,
                   'tax_per_tick':own['overall']['tax']/ticks,
                   'between_aid_per_tick':own['overall']['aid_given']/ticks,
                   'within_conflict_per_tick':own['overall']['within_conflict']/ticks,
                   'infrastructure':own['overall']['infrastructure'],
                   'other_welfare':statistics.mean(s['overall']['welfare'] for i,s in enumerate(episode['society_metrics']) if i!=focal),
                   'members':[m for m in episode['member_metrics'] if m['society_id']==focal],
                   'ledger_residual':episode['ledger']['residual'], 'episode_digest':episode['digest']}
    row['drought_welfare_effect']=row['drought']['welfare']-row['no_drought']['welfare']
    row['drought_post_welfare_effect']=row['drought']['post_welfare']-row['no_drought']['post_welfare']
    return row


def aggregate(rows):
    metrics=[k for k,v in rows[0]['drought'].items() if isinstance(v,(int,float)) and k!='ledger_residual']
    result={'n_cases':len(rows),'n_rollouts':2*len(rows)}
    for phase in ('drought','no_drought'):
        result[phase]={k:statistics.mean(r[phase][k] for r in rows) for k in metrics}
    for key in ('drought_welfare_effect','drought_post_welfare_effect'):
        result[key]=statistics.mean(r[key] for r in rows)
    return result


def evaluate_campaign(plan_path, workers=2):
    plan_path=Path(plan_path).resolve()
    plan=read_json(plan_path)
    if file_hash(plan['protocol'])!=plan['protocol_sha256']:
        raise ValueError('Frozen protocol changed')
    if file_hash(plan['fresh_cases'])!=plan['fresh_cases_sha256']:
        raise ValueError('Protected fresh panel changed')
    cases=read_json(plan['fresh_cases'])['cases']
    out=plan_path.parent/'fresh'
    out.mkdir(exist_ok=True)
    start=time.monotonic()
    populations=[]
    states=[]
    for spec in plan['runs']:
        budget=read_json(Path(spec['run_dir'])/'budget_checkpoint.json')
        if budget['status'] not in ('budget_exhausted','completed'):
            raise ValueError(f"Run is not terminal: {spec['id']}")
        state=read_json(spec['context'])
        verify_frozen_sources(state)
        if states and ([file_hash(p) for p in state['initial_institutions']] != [file_hash(p) for p in states[0]['initial_institutions']] or
                       [[file_hash(p) for p in row] for row in state['initial_members']] != [[file_hash(p) for p in row] for row in states[0]['initial_members']]):
            raise ValueError('Paired contexts do not share the same initial population')
        states.append(state)
        populations.append((spec['id'],state['institutions'],state['members'],state))
    first=states[0]
    populations.insert(0,('initial',first['initial_institutions'],first['initial_members'],first))
    summaries=[]
    for label, institutions, members, state in populations:
        fingerprint=hashlib.sha256(json.dumps({'cases':cases,'institutions':[file_hash(p) for p in institutions],
                       'members':[[file_hash(p) for p in row] for row in members],
                       'initial_institutions':[file_hash(p) for p in state['initial_institutions']],
                       'initial_members':[[file_hash(p) for p in row] for row in state['initial_members']],
                       'sources':state['frozen_source_hashes'],'analysis':file_hash(__file__)},sort_keys=True).encode()).hexdigest()
        destination=out/f'{label}.json'
        if destination.exists() and read_json(destination).get('fingerprint')==fingerprint:
            summaries.append({'label':label,**read_json(destination)['summary']})
            continue
        jobs=[(case,panel,focal,institutions,members,state['initial_institutions'],state['initial_members'])
              for case in cases for panel in ('initial','cooperative','selfish') for focal in range(3)]
        rows=[]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for index,row in enumerate(pool.map(case_metrics,jobs)):
                rows.append(row)
                if (index+1)%18==0: print(f'fresh {label}: {index+1}/{len(jobs)} cases',flush=True)
        summary=aggregate(rows)
        atomic_json(destination,{'label':label,'fingerprint':fingerprint,'summary':summary,'rows':rows})
        summaries.append({'label':label,**summary})
    paired=[]
    for replicate in range(1,plan['replicates_per_condition']+1):
        left=next(r for r in summaries if r['label']==f'pair-{replicate:02d}-coevolution')
        right=next(r for r in summaries if r['label']==f'pair-{replicate:02d}-fixed_institution')
        paired.append({'replicate':replicate,'contrast':'coevolution - fixed_institution',
                       'welfare_difference':left['drought']['welfare']-right['drought']['welfare'],
                       'post_welfare_difference':left['drought']['post_welfare']-right['drought']['post_welfare'],
                       'drought_effect_difference':left['drought_welfare_effect']-right['drought_welfare_effect']})
    result={'study':'consumption-v2','completed_utc':datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds_this_invocation':time.monotonic()-start,'workers':workers,
            'replicates_per_condition':plan['replicates_per_condition'],
            'interpretation':plan['interpretation'],'results':summaries,'paired_run_differences':paired,
            'paired_run_summary':{'n_pairs':len(paired),
                                  'mean_welfare_difference':statistics.mean(p['welfare_difference'] for p in paired),
                                  'sd_welfare_difference':statistics.stdev(p['welfare_difference'] for p in paired) if len(paired)>1 else None},
            'replication_note':'Run-level paired differences are the search replication units; fresh rollouts are not independent searches.'}
    atomic_json(out/'summary.json',result)
    print(json.dumps(result,indent=2),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.workers<1:p.error('workers must be positive')
    evaluate_campaign(args.plan,args.workers)


if __name__=='__main__':main()
