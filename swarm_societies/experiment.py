"""Reproduce recorded ecology, fresh evaluation, and compact scientific evidence."""
from __future__ import annotations
import argparse
import concurrent.futures
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import sqlite3
import statistics
import time

from .evaluation import ROOT, atomic_json, read_json, initialize_context, simulate, component_hashes, digest, snapshot_program



def load_population(run_dir):
    """Resolve either a local checkpoint or the compact published population."""
    context=run_dir/'evolution_context.json'
    if not context.exists(): context=run_dir/'final_population.json'
    state=read_json(context)
    def resolve(path):
        original=Path(path)
        alternatives=[original,run_dir/'programs'/original.name,ROOT/original]
        for candidate in alternatives:
            if candidate.is_file():
                if len(candidate.stem)==64 and digest(candidate.read_text())!=candidate.stem:
                    raise ValueError(f'Source checksum mismatch: {candidate}')
                return str(candidate.resolve())
        raise FileNotFoundError(f'Missing recorded program: {path}')
    for key in ['institutions','initial_institutions']:
        state[key]=[resolve(p) for p in state[key]]
    for key in ['members','initial_members']:
        state[key]=[[resolve(p) for p in row] for row in state[key]]
    return state


def case_panel(run_dir, societies):
    path = run_dir / 'protected_fresh_cases.json'
    if path.exists():
        return read_json(path)
    rng = random.Random(8675309)
    seeds = rng.sample(range(10000, 10000000), 12)
    panel = {'selection_rule':'final ecological population; no fresh selection',
             'created_utc':datetime.now(timezone.utc).isoformat(),
             'cases':[{'seed':seed,'opponents':panel,'focal':focal}
                      for seed in seeds for panel in ['initial','cooperative','selfish']
                      for focal in range(societies)]}
    atomic_json(path,panel)
    return panel


def evaluate_case(job):
    case, institutions, members, initial_institutions, initial_members, config, references = job
    n,m=config['n_societies'],config['members_per_society']
    focal=case['focal']
    if case['opponents']=='initial':
        opponents=initial_institutions.copy()
        peers=[row.copy() for row in initial_members]
    else:
        p=references[case['opponents']]
        opponents=[p]*n
        peers=[[p]*m for _ in range(n)]
    opponents[focal]=institutions[focal]
    peers[focal]=members[focal]
    episode=simulate(opponents,peers,config,case['seed'])
    own=episode['society_metrics'][focal]
    overall=own['overall']
    row={**case,'pre_welfare':own['pre']['welfare'],'post_welfare':own['post']['welfare'],
         'welfare':overall['welfare'],'individual_utility':own['mean_individual_utility'],
         'other_welfare':statistics.mean(s['overall']['welfare'] for i,s in enumerate(episode['society_metrics']) if i!=focal),
         'within_cooperation':overall['cooperation_within'],'voluntary_contribution':overall['contribution'],
         'tax':overall['tax'],'between_cooperation':overall['cooperation_between'],
         'within_conflict':overall['within_conflict'],'between_conflict':overall['external_harm'],
         'within_raid_attempts':overall['within_raid_attempts'],'between_raid_attempts':overall['inter_raid_attempts'],
         'shortfall':overall['shortfall'],'final_wealth':own['final_mean_wealth'],
         'wealth_gini':overall['wealth_gini'],'adaptation':own['adaptation'],
         'pre_shortfall':own['pre']['shortfall'],'post_shortfall':own['post']['shortfall'],
         'pre_consumption':own['pre']['consumption'],'post_consumption':own['post']['consumption'],
         'pre_infrastructure':own['pre']['infrastructure'],'post_infrastructure':own['post']['infrastructure'],
         'focal_members':[{k:member[k] for k in ['member_id','utility','consumption','shortfall','final_wealth','tax','contribution','raid_gain','raid_loss']}
                          for member in episode['member_metrics'] if member['society_id']==focal],
         'ledger_residual':episode['ledger']['residual']}
    return row


METRICS=['pre_welfare','post_welfare','welfare','individual_utility','other_welfare',
         'within_cooperation','voluntary_contribution','tax','between_cooperation','within_conflict',
         'between_conflict','within_raid_attempts','between_raid_attempts','shortfall','final_wealth',
         'wealth_gini','adaptation','pre_shortfall','post_shortfall','pre_consumption','post_consumption',
         'pre_infrastructure','post_infrastructure']


def aggregate(label, rows):
    return {'label':label,'n':len(rows),**{key:statistics.mean(r[key] for r in rows) for key in METRICS}}


def paired_comparison(name, rows, baseline):
    old={(r['seed'],r['opponents'],r['focal']):r for r in baseline}
    result={'contrast':name,'n_cases':len(rows),'n_environment_seeds':len({r['seed'] for r in rows})}
    for metric in METRICS:
        by_seed={}
        for row in rows:
            difference=row[metric]-old[(row['seed'],row['opponents'],row['focal'])][metric]
            by_seed.setdefault(row['seed'],[]).append(difference)
        cluster_means=[statistics.mean(v) for v in by_seed.values()]
        rng=random.Random(4001)
        boot=sorted(statistics.mean(rng.choices(cluster_means,k=len(cluster_means))) for _ in range(2000))
        result[metric]={'mean_difference':statistics.mean(cluster_means),'seed_cluster_bootstrap_95':[boot[49],boot[1949]]}
    result['interpretation']='Descriptive environment-seed uncertainty conditional on one evolutionary run; not replication of search.'
    return result


def fresh(args):
    run_dir=args.run_dir.resolve()
    state=load_population(run_dir)
    if not args.baseline_only and (run_dir/'budget_checkpoint.json').exists():
        if read_json(run_dir/'budget_checkpoint.json')['status']=='running':
            raise RuntimeError('Final population is not frozen. Wait for search to end, or use --baseline-only.')
    panel=case_panel(run_dir,state['config']['n_societies'])
    references={}
    for i,name in enumerate(['initial','cooperative','selfish']):
        references[name]=(state['initial_institutions'][i] if i<len(state['initial_institutions']) else
                          snapshot_program(ROOT/'seeds'/f'{name}.py',run_dir/'reference_programs'))
    coop=references['cooperative']
    treatments=[('initial_population','Initial population',state['initial_institutions'],state['initial_members']),
                ('fixed_institution','Fixed cooperative institution',[coop]*state['config']['n_societies'],state['initial_members'])]
    if not args.baseline_only and (state['accepted_member_updates']+state['accepted_institution_updates']>0):
        treatments.extend([
            ('descendant','Final descendants',state['institutions'],state['members']),
            ('members_only','Descendant members only',state['initial_institutions'],state['members']),
            ('institutions_only','Descendant institutions only',state['institutions'],state['initial_members'])])
    output=run_dir/'fresh'
    output.mkdir(exist_ok=True)
    all_rows={}
    started=time.monotonic()
    for key,label,inst,members in treatments:
        fingerprint=digest(json.dumps({'institutions':[digest(Path(p).read_text()) for p in inst],
                 'members':[[digest(Path(p).read_text()) for p in row] for row in members],
                 'config':state['config'],'cases':panel['cases'],
                 'initial_opponents':[digest(Path(p).read_text()) for p in state['initial_institutions']],
                 'initial_partners':[[digest(Path(p).read_text()) for p in row] for row in state['initial_members']],
                 'reference_programs':{name:digest(Path(p).read_text()) for name,p in references.items()},
                 'candidate_runtime':digest((ROOT/'swarm_societies/candidate.py').read_text()),
                 'simulator':digest((ROOT/'swarm_societies/ecology.py').read_text()),
                 'evaluation':digest(Path(__file__).read_text())},sort_keys=True))
        target=output/f'{key}.json'
        if target.exists() and read_json(target).get('fingerprint')==fingerprint:
            result=read_json(target)
        else:
            jobs=[(case,inst,members,state['initial_institutions'],state['initial_members'],state['config'],references) for case in panel['cases']]
            with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
                rows=list(pool.map(evaluate_case,jobs))
            result={'fingerprint':fingerprint,'label':label,'rows':rows,'summary':aggregate(label,rows)}
            atomic_json(target,result)
        all_rows[key]=result
        print(json.dumps(result['summary']),flush=True)
    comparisons=[]
    for key in all_rows:
        if key!='initial_population':
            comparisons.append(paired_comparison(f'{key} - initial_population',all_rows[key]['rows'],all_rows['initial_population']['rows']))
    if 'descendant' in all_rows:
        comparisons.append(paired_comparison('descendant - fixed_institution',all_rows['descendant']['rows'],all_rows['fixed_institution']['rows']))
    atomic_json(output/'manifest.json',{'treatments':[t[0] for t in treatments],
                'reference_program_hashes':{name:digest(Path(p).read_text()) for name,p in references.items()},
                'fingerprints':{key:result['fingerprint'] for key,result in all_rows.items()}})
    atomic_json(output/'comparisons.json',comparisons)
    atomic_json(output/'timing.json',{'elapsed_seconds_this_invocation':time.monotonic()-started,'workers':args.workers,'baseline_only':args.baseline_only})
    return all_rows


def portable(value):
    if isinstance(value,dict): return {k:portable(v) for k,v in value.items()}
    if isinstance(value,list): return [portable(v) for v in value]
    if isinstance(value,str): return value.replace(str(ROOT)+'/', '')
    return value


def collect_shinka(run_dir):
    path=run_dir/'programs.sqlite'
    if not path.exists(): return []
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT * FROM programs ORDER BY generation, timestamp')]


def export(args):
    run_dir=args.run_dir.resolve()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    state=load_population(run_dir)
    rows=collect_shinka(run_dir)
    evaluations=state['evaluations']
    attempt_counts=[]
    event_counts=[]
    database=run_dir/'programs.sqlite'
    if database.exists():
        with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as db:
            attempt_counts=[{'stage':stage,'status':status,'count':count} for stage,status,count in
                            db.execute('SELECT stage,status,count(*) FROM attempt_log GROUP BY stage,status')]
            event_counts=[{'status':status,'count':count} for status,count in
                          db.execute('SELECT status,count(*) FROM generation_event_log GROUP BY status')]
    status=read_json(run_dir/'budget_checkpoint.json') if (run_dir/'budget_checkpoint.json').exists() else {'status':'not_started'}
    history=[]
    lineage=[]
    hash_to_id={}
    # All archived proposal source is compact evidence; full DB/prompts remain ignored.
    programs=out/'programs'
    programs.mkdir(exist_ok=True)
    required_hashes=set()
    for row in rows:
        code=row.get('code','')
        sha=digest(code)
        hash_to_id[sha]=str(row['id'])
        required_hashes.add(sha)
        (programs/f'{sha}.py').write_text(code)
    for seed_path in sorted(set(state['initial_institutions'])):
        sha=digest(Path(seed_path).read_text())
        if not any(r['generation']==0 and digest(r['code'])==sha for r in rows):
            node_id='seed-'+sha[:12]
            hash_to_id[sha]=node_id
            lineage.append({'id':node_id,'parent_id':None,'generation':0,
                            'society':state['initial_institutions'].index(seed_path),
                            'label':f"S{state['initial_institutions'].index(seed_path)} · initial seed",'kind':'initial','score':None,
                            'valid':True,'accepted':False,'program_sha256':sha,'changes':''})
    eval_by_generation={}
    eval_by_hash={}
    for ev in evaluations:
        for part in Path(ev['job_id']).parts:
            if part.startswith('gen_') and part[4:].isdigit():
                eval_by_generation[int(part[4:])]=ev
        eval_by_hash.setdefault(ev['program_sha256'],[]).append(ev)
    for row in rows:
        sha=digest(row.get('code',''))
        matches=eval_by_hash.get(sha,[])
        ev=eval_by_generation.get(row['generation'],matches[0] if len(matches)==1 else {})
        score=row.get('combined_score')
        history.append({'generation':row['generation'],'score':score,'valid':bool(row['correct']),
                        'accepted':ev.get('accepted',False),'kind':ev.get('kind','proposal' if row['correct'] else 'infrastructure failure'),
                        'society':ev.get('target_society',0),
                        'program_sha256':sha,'paired_gain':ev.get('paired_gain')})
        parent=row.get('parent_id')
        parent_row=next((p for p in rows if p['id']==parent),None)
        changes=[]
        if parent_row:
            try:
                old_hashes=component_hashes(parent_row['code']); new_hashes=component_hashes(row['code'])
                changes=[k for k,v in new_hashes.items() if old_hashes.get(k)!=v]
                if not changes and parent_row['code']!=row['code']: changes=['helpers/constants/comments']
            except (SyntaxError,IndexError): changes=['invalid source']
        predecessor_id=None
        pred_sha=ev.get('ecological_predecessor_sha256')
        prior=[other for other in evaluations if other['evaluation']<ev.get('evaluation',0)
               and other.get('accepted') and other.get('kind')==ev.get('kind')
               and other.get('target_society')==ev.get('target_society')
               and other.get('target_member')==ev.get('target_member')
               and other.get('program_sha256')==pred_sha]
        if prior:
            prior_ev=max(prior,key=lambda other:other['evaluation'])
            prior_gen=next((g for g,e in eval_by_generation.items() if e['job_id']==prior_ev['job_id']),None)
            prior_row=next((r for r in rows if r['generation']==prior_gen),None)
            predecessor_id=str(prior_row['id']) if prior_row else None
        elif pred_sha in {digest(Path(p).read_text()) for p in state['initial_institutions']}:
            initial_row=next((r for r in rows if r['generation']==0 and digest(r['code'])==pred_sha),None)
            predecessor_id=str(initial_row['id']) if initial_row else 'seed-'+pred_sha[:12]
        node={'id':str(row['id']),'parent_id':str(parent) if parent else None,
              'generation':row['generation'],'society':ev.get('target_society',0),
              'label':f"G{row['generation']} · S{ev.get('target_society',0)} {ev.get('kind','proposal')}",
              'kind':ev.get('kind','proposal' if row['correct'] else 'infrastructure failure'),
              'target_member':ev.get('target_member'),
              'score':score,'valid':bool(row['correct']),'accepted':ev.get('accepted',False),
              'changes':', '.join(changes),'changed_components':changes,'program_sha256':sha,
              'ecological_predecessor_id':predecessor_id,
              'ecological_predecessor_sha256':ev.get('ecological_predecessor_sha256'),
              'candidate_objective':ev.get('candidate_objective'),'incumbent_objective':ev.get('incumbent_objective')}
        lineage.append(node)
    results=[]
    fresh_manifest=read_json(run_dir/'fresh/manifest.json') if (run_dir/'fresh/manifest.json').exists() else None
    for key in ['initial_population','fixed_institution','descendant','members_only','institutions_only']:
        path=run_dir/'fresh'/f'{key}.json'
        if path.exists() and (fresh_manifest is None or key in fresh_manifest['treatments']):
            item=read_json(path)
            results.append(item['summary'])
            atomic_json(out/f'{key}.json',item)
    # Preserve all ecological source dependencies even if absent from Shinka's archive.
    dependency_paths=set(state['institutions']+state['initial_institutions'])
    for matrix in [state['members'],state['initial_members']]:
        dependency_paths.update(p for row in matrix for p in row)
    for ev in evaluations:
        dependency_paths.update(ev['population_before']['institutions'])
        dependency_paths.update(p for row in ev['population_before']['members'] for p in row)
        if ev.get('program_path'): dependency_paths.add(ev['program_path'])
    dependency_paths.update(str(p) for p in (run_dir/'reference_programs').glob('*.py'))
    for filename in dependency_paths:
        path=Path(filename)
        if not path.exists(): path=programs/path.name
        sha=digest(path.read_text())
        required_hashes.add(sha)
        if path.resolve()!=(programs/f'{sha}.py').resolve():
            shutil.copy2(path,programs/f'{sha}.py')
    for archived in programs.glob('*.py'):
        if archived.stem not in required_hashes: archived.unlink()
    unique={ev['program_sha256'] for ev in evaluations}
    usage={'completed_calls':0,'input_tokens':0,'cached_input_tokens':0,'output_tokens':0,'reasoning_output_tokens':0}
    call_files=list(run_dir.rglob('subscription_calls/*.jsonl'))
    unknown_calls=0
    for path in call_files:
        completed=False
        for line in path.read_text().splitlines():
            try: event=json.loads(line)
            except json.JSONDecodeError: continue
            if event.get('type')=='turn.completed':
                usage['completed_calls']+=1
                completed=True
                for key in ['input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens']:
                    usage[key]+=event.get('usage',{}).get(key,0)
        if not completed: unknown_calls+=1
    usage['calls_with_unknown_usage']=unknown_calls
    summary={'schema_version':1,'status':status['status'],'results':results,'search_history':history,'lineage':lineage,
             'search_counts':{'shinka_database_programs':len(rows),'shinka_valid_programs':sum(bool(r['correct']) for r in rows),
                              'shinka_invalid_programs':sum(not bool(r['correct']) for r in rows),
                              'evaluator_jobs':len(evaluations),'unique_evaluated_programs':len(unique),
                              'evaluated_mutations':max(0,len(evaluations)-1),
                              'valid_evaluated_mutations':sum(ev['valid'] for ev in evaluations[1:]),
                              'invalid_evaluated_mutations':sum(not ev['valid'] for ev in evaluations[1:]),
                              'valid_evaluator_jobs':sum(ev['valid'] for ev in evaluations),
                              'invalid_evaluator_jobs':sum(not ev['valid'] for ev in evaluations),
                              'accepted_member_updates':state['accepted_member_updates'],
                              'accepted_institution_updates':state['accepted_institution_updates'],
                              'completed_search_generations':len({r['generation'] for r in rows if r['generation']>0}),
                              'accepted_ecological_updates':state['accepted_member_updates']+state['accepted_institution_updates'],
                              'infrastructure_failed_programs':sum(not r['correct'] and r['generation'] not in eval_by_generation for r in rows)},
             'resource_usage':portable(status),'inference_usage':usage,
             'shinka_attempt_counts':attempt_counts,'shinka_generation_events':event_counts,
             'usage_note':'Only completed Codex calls expose usage; an interrupted in-flight call may be unreported. Cached input is a subset of input; reasoning is a subset of output.',
             'evaluation_note':f"{36*state['config']['n_societies']} common cases: 12 environment seeds × 3 frozen opponent panels × {state['config']['n_societies']} focal identities. One exploratory evolutionary run; cases are not search replications.",
             'config':state['config'],
             'lineage_note':'Solid arrows: Shinka source-parent inheritance. Dashed arrows: ecological comparison incumbent when different; retained status indicates replacement. Source can change both functions; only the scheduled unit enters the population.'}
    atomic_json(out/'summary.json',summary)
    atomic_json(out/'search_evaluations.json',portable(evaluations))
    atomic_json(out/'final_population.json',portable(state))
    for src,dest in [(run_dir/'fresh/comparisons.json',out/'comparisons.json'),
                     (run_dir/'protected_fresh_cases.json',out/'fresh_cases.json'),
                     (run_dir/'actual_settings.json',out/'actual_settings.json'),
                     (run_dir/'budget_checkpoint.json',out/'budget_checkpoint.json'),
                     (run_dir/'fresh/manifest.json',out/'fresh_manifest.json'),
                     (run_dir/'fresh/timing.json',out/'fresh_timing.json')]:
        if src.exists(): atomic_json(dest,portable(read_json(src)))
    print(json.dumps({'output':str(out),'search_counts':summary['search_counts'],'inference_usage':usage},indent=2))
    return summary


def replay(args):
    state=load_population(args.run_dir)
    initial=args.initial
    episode=simulate(state['initial_institutions'] if initial else state['institutions'],
                     state['initial_members'] if initial else state['members'],state['config'],args.seed,True)
    episode['population_label']='Initial population' if initial else 'Final ecological population'
    # Presentation label is excluded from the simulator's recorded digest.
    atomic_json(args.output,episode)
    print(json.dumps({'output':str(args.output),'aggregate':episode['aggregate'],'digest':episode['digest']},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    prepare=sub.add_parser('prepare'); prepare.add_argument('--run-dir',type=Path,default=ROOT/'runs/first')
    prepare.add_argument('--societies',type=int,default=3);prepare.add_argument('--members',type=int,default=4);prepare.add_argument('--ticks',type=int,default=60)
    fresh_p=sub.add_parser('fresh');fresh_p.add_argument('--run-dir',type=Path,default=ROOT/'runs/first')
    fresh_p.add_argument('--workers',type=int,default=2);fresh_p.add_argument('--baseline-only',action='store_true')
    export_p=sub.add_parser('export');export_p.add_argument('--run-dir',type=Path,default=ROOT/'runs/first');export_p.add_argument('--output',type=Path,default=ROOT/'evidence/experiment')
    replay_p=sub.add_parser('replay');replay_p.add_argument('--run-dir',type=Path,default=ROOT/'runs/first');replay_p.add_argument('--output',type=Path,default=ROOT/'evidence/experiment/replay.json')
    replay_p.add_argument('--seed',type=int,default=424242);replay_p.add_argument('--initial',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        state=initialize_context(args.run_dir/'evolution_context.json',args.societies,args.members,args.ticks)
        case_panel(args.run_dir,state['config']['n_societies'])
        print(f'Prepared {args.run_dir}')
    elif args.command=='fresh': fresh(args)
    elif args.command=='export': export(args)
    else: replay(args)


if __name__=='__main__':main()
