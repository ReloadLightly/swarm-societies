#!/usr/bin/env python3
"""Freeze a paired v2 campaign before starting subscription inference."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.consumption_evaluation import CONDITIONS, initialize_context, file_hash
from swarm_societies.consumption_study import make_fresh_cases
from swarm_societies.evaluation import ROOT, atomic_json
from swarm_societies.shinka_bridge import MODEL, EFFORT, SERVICE_TIER, UPSTREAM_REVISION


def prepare_campaign(directory, replicates=1, minutes_per_run=30):
    directory = Path(directory).resolve()
    if replicates < 1 or minutes_per_run <= 0:
        raise ValueError('Replicates and budget must be positive')
    if (directory/'campaign.json').exists():
        raise ValueError('Campaign already exists; use its status/resume command')
    directory.mkdir(parents=True, exist_ok=True)
    fresh_path = directory/'protected_fresh_cases.json'
    atomic_json(fresh_path, {'cases':make_fresh_cases(), 'selection':'final ecological population; no fresh selection'})
    runs = []
    for replicate in range(1, replicates+1):
        replication_seed = 2026100500 + replicate
        order = list(CONDITIONS)
        random.Random(replication_seed).shuffle(order)
        for condition in order:
            run_id = f'pair-{replicate:02d}-{condition}'
            run_dir = directory/run_id
            context = run_dir/'evolution_context.json'
            state = initialize_context(context, condition, replicate, replication_seed)
            runs.append({'id':run_id, 'condition':condition, 'replicate':replicate,
                         'run_dir':str(run_dir), 'context':str(context),
                         'initial_program':state['initial_institutions'][0],
                         'task_prompt':str(ROOT/'docs/evolution-prompt-consumption-v2.md'),
                         'evaluator':str(ROOT/'scripts/evaluate_consumption_candidate.py'),
                         'budget_minutes':minutes_per_run,
                         'search_seed':1000000+replicate*2+CONDITIONS.index(condition)})
    plan = {'schema_version':1, 'study':'consumption-v2',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'model_route':{'model':MODEL,'reasoning_effort':EFFORT,'service_tier':SERVICE_TIER,
                           'authentication':'chatgpt','shinka_revision':UPSTREAM_REVISION,
                           'paid_api_allowed':False,'embedding_model':None,'judging_model':None},
            'replicates_per_condition':replicates, 'budget_minutes_per_run':minutes_per_run,
            'total_search_minutes':2*replicates*minutes_per_run,
            'interpretation':'Exploratory matched pilot; no replicated search claim' if replicates==1 else 'Independent paired evolutionary runs are the replication unit',
            'protocol':str(ROOT/'docs/protocol-consumption-v2.md'),
            'protocol_sha256':file_hash(ROOT/'docs/protocol-consumption-v2.md'),
            'fresh_cases':str(fresh_path), 'fresh_cases_sha256':file_hash(fresh_path),
            'runs':runs,
            'postprocess_command':[sys.executable,str(ROOT/'scripts/evaluate_consumption_study.py'),
                                   '--plan',str(directory/'campaign.json'),'--workers','2']}
    atomic_json(directory/'campaign.json', plan)
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign-dir',type=Path,default=ROOT/'runs/consumption-v2')
    p.add_argument('--replicates',type=int,default=1)
    p.add_argument('--minutes-per-run',type=float,default=30)
    args=p.parse_args()
    plan=prepare_campaign(args.campaign_dir,args.replicates,args.minutes_per_run)
    print(f"Prepared {len(plan['runs'])} runs, {plan['total_search_minutes']:g} total search minutes: {args.campaign_dir}/campaign.json")


if __name__ == '__main__':
    main()
