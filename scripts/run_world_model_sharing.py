#!/usr/bin/env python3
"""Prospective passive experiment on private learning and truthful report content."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy

from scripts.run_world_model_study import (PRIOR, POLICY, csv_read, csv_write,
    json_write, query_from, sha, stable_seed, score_samples)
from swarm_societies.candidate import CandidateProgram
from swarm_societies.ecology_world_model_v1 import EcologyConfig, WorldParameters, run_episode
from swarm_societies.world_model_v1.sharing import SharingRuntime

VERSION = 'world-model-sharing-v1'
CONDITIONS = ('isolated', 'redundant', 'complementary', 'delayed_complementary', 'union_ceiling')
PARAMETERS = ('r', 'b', 'g')
SOURCE_FILES = ('scripts/run_world_model_sharing.py', 'scripts/run_world_model_study.py',
    'swarm_societies/world_model_v1/sharing.py', 'swarm_societies/world_model_v1/learner.py',
    'swarm_societies/world_model_v1/__init__.py', 'swarm_societies/ecology_world_model_v1.py',
    'swarm_societies/ecology_consumption_v2.py', 'swarm_societies/candidate.py',
    'docs/world-model-sharing-protocol.md', 'requirements-world-model-v1.txt')


def packed_write(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    Path(path).write_bytes(gzip.compress(raw, mtime=0))


def packed_read(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def prepare(directory, arenas=24, ticks=128, development=False):
    directory = Path(directory)
    if (directory/'design.json').exists():
        raise ValueError('Frozen design exists; use a fresh output directory')
    if arenas < 1 or ticks < 8:
        raise ValueError('Need at least one arena and eight ticks')
    bank = 'development' if development else 'evaluation'
    directory.mkdir(parents=True, exist_ok=True)
    cases = []
    for index in range(arenas):
        arena = f'sharing-{bank}-{index:03d}'
        rng = np.random.default_rng(stable_seed(VERSION, arena, 'laws'))
        cases.append({'arena_id': arena, 'index': index, 'role_rotation': index % 3,
            'environment_seed': stable_seed(VERSION, arena, 'environment'),
            'world_parameters': {p: float(rng.uniform(*bounds)) for p,bounds in
                zip(PARAMETERS, ((2.4,6.8),(.7,2.7),(.05,.7)))}})
    config = asdict(EcologyConfig(n_societies=3, members_per_society=4, ticks=ticks,
        disturbance_tick=ticks//2, initial_patch=10., patch_capacity=30., regeneration=5., enable_disturbance=False))
    for name in SOURCE_FILES:
        target = directory/'sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    design = {'study':VERSION, 'schema_version':1, 'bank':bank,
        'frozen_utc':datetime.now(timezone.utc).isoformat(), 'cases':cases, 'config':config,
        'conditions':list(CONDITIONS), 'prior':PRIOR, 'sensor_sigma':.05,
        'learner_settings':{'n_particles':1024,'rejuvenation_steps':4,'ess_fraction':.5},
        'checkpoints':sorted({0,ticks,*[t for t in (4,8,16,32,64,128) if t <= ticks]}),
        'evidence_checkpoints':sorted({0,2*ticks,*[n for n in (8,16,32,64,128,256) if n <= 2*ticks]}),
        'n_probes':64,'forecast_samples':512,'frame_bytes':1024,
        'normal_hop_delay':1,'slow_hop_delay':4,'senders':[0,1],
        'observation_contract':'One noisy canonical growth event per patch/tick, assigned to home-plus-rotating-neighbor members, with full infrastructure audit features. Identical event/noise copies are deduplicated.',
        'timing':'Start-tick queued delivery; end-tick private observation and reports; two positive-delay hops; no horizon flush.',
        'primary':'Arena-average MEMBER held-out uncapped CRPS area over completed ticks / horizon; complementary minus redundant is the primary paired contrast.',
        'secondary':['delay contrast','union information ceiling','institution learning','exact unique-evidence curves','parameter intervals','wire bytes and duplicate versus novel evidence','runtime CPU'],
        'probe_design':'64 shared same-law independent queries per arena; 32 guaranteed uncapped primary; 32 headroom0,2,6 controls; forecast RNG fixed by arena/owner/probe, not condition/checkpoint.',
        'evidence_axis':'Score immediately after exactly n unique accepted events; same counts need not mean same examples/order. Institutions do not enter member evidence-axis comparisons.',
        'replication_unit':'Independent shared-law arena. Members/societies/probes/ticks are dependent; average members within arena before bootstrap.',
        'bootstrap':{'draws':2000,'seed':9301,'level':.95},
        'scope':'Passive fixed-policy, truthful report-content intervention. No learned action selection, evolved router, strategic claims, hidden-feature marginalization, or material communication cost.',
        'failure_policy':'All failed learner updates and invalid reports retained. Unhandled exceptions abort completion; no cases replaced or omitted. Pending messages are recorded without post-horizon delivery.',
        'model_generation_calls':0,'source_hashes':{p:sha(ROOT/p) for p in SOURCE_FILES},
        'software':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__}}
    json_write(directory/'design.json',design)
    (directory/'design.sha256').write_text(sha(directory/'design.json')+'\n')
    return design


def check_design(directory, live=False):
    directory = Path(directory)
    if sha(directory/'design.json') != (directory/'design.sha256').read_text().strip():
        raise ValueError('Frozen sharing design checksum mismatch')
    design = json.loads((directory/'design.json').read_text())
    for name, expected in design['source_hashes'].items():
        if sha(directory/'sources'/name) != expected or (live and sha(ROOT/name) != expected):
            raise ValueError('Frozen sharing source mismatch: '+name)
    return design


def generate_case(case, design):
    """Evaluator owns truth; only the packet allowlist enters the runtime."""
    policy = CandidateProgram(f'ROLE_ROTATION = {case["role_rotation"]}\n\n'+POLICY)
    world = run_episode([policy]*3,config=design['config'],seed=case['environment_seed'],
        world_parameters=WorldParameters(**case['world_parameters']), observation_mode='full_observation_control')
    noise = np.random.default_rng(stable_seed(VERSION,case['arena_id'],'sensor'))
    packets = [{**query_from(raw), 'event_id':f'{case["arena_id"]}/{raw["event_id"]}',
        'tick':raw['tick'],'patch':raw['patch'],'phase':'before_actions',
        'growth':float(raw['growth']+noise.normal(0,design['sensor_sigma'])),
        'sensor_sigma':design['sensor_sigma']} for raw in world['learning_observations']]
    rng = np.random.default_rng(stable_seed(VERSION,case['arena_id'],'probes'))
    law = case['world_parameters']
    probes = []
    for index in range(design['n_probes']):
        gap = 30. if index % 2 == 0 else float((0,2,6)[(index//2)%3])
        query = {'stock_before':30.-gap,'capacity':30.,
            'own_infrastructure':float(rng.uniform(0,2)),'other_infrastructure':float(rng.uniform(0,2))}
        physical = min(gap,law['r']*rng.uniform(.85,1.15)+law['b']*query['own_infrastructure']+law['g']*query['other_infrastructure'])
        probes.append({'probe_id':index,'probe_group':'uncapped' if gap == 30 else 'capacity_control',
            **query,'target':float(physical+rng.normal(0,design['sensor_sigma']))})
    audit = {'material_digest':world['legacy_digest'],'ledger_residual':world['ledger']['residual'],
        'aggregate':world['aggregate'],'n_events':len(packets)}
    return packets,probes,audit


def actor_identity(key):
    parts = key.split(':')
    return {'actor':key,'actor_type':parts[0],'society':int(parts[1]),
            'member':int(parts[2]) if parts[0]=='member' else -1}


def score_model(model, case, actor, probes, design):
    before = model.snapshot()
    info = model.summary()
    scores = []
    for probe in probes:
        draws = model.predict(query_from(probe), n_samples=design['forecast_samples'],
            seed=stable_seed(VERSION,case['arena_id'],actor,probe['probe_id'],'forecast'))
        scores.append({'probe_id':probe['probe_id'],'probe_group':probe['probe_group'],
                      'target':probe['target'],**score_samples(draws,probe['target'])})
    if before != model.snapshot():
        raise AssertionError('Scoring mutated a private learner')
    primary = [row for row in scores if row['probe_group']=='uncapped']
    metrics = {'probe_crps':float(np.mean([s['crps'] for s in primary])),
        'probe_crps_all':float(np.mean([s['crps'] for s in scores])),
        'probe_mse':float(np.mean([s['squared_error'] for s in primary])),
        'coverage_90':float(np.mean([s['covered'] for s in primary])),
        'interval_width_90':float(np.mean([s['width'] for s in primary]))}
    parameters = []
    for j,p in enumerate(PARAMETERS):
        lo,hi = info['intervals_90'][p]
        truth = case['world_parameters'][p]
        parameters.append({'parameter':p,'true_value':truth,'posterior_mean':info['mean'][p],
            'posterior_sd':float(np.sqrt(max(0.,info['covariance'][j][j]))),
            'lo90':lo,'hi90':hi,'covered90':int(lo<=truth<=hi),'width90':hi-lo,
            'absolute_error':abs(info['mean'][p]-truth)})
    metrics['parameter_nrmse'] = float(np.sqrt(np.mean([
        ((p['posterior_mean']-p['true_value'])/(PRIOR[p['parameter']][1]-PRIOR[p['parameter']][0]))**2 for p in parameters])))
    return metrics,parameters,scores


def transport_rows(runtime, arena, condition):
    ledger = runtime.ledger()
    rows = []
    for society in range(3):
        frames = [r for r in ledger['frames'] if int(r['sender'].split(':')[1])==society]
        updates = [r for r in ledger['updates'] if int(r['actor_key'].split(':')[1])==society]
        member_reports = [r for r in updates if r['actor_key'].startswith('member:') and r['channel']=='downlink']
        rows.append({'arena_id':arena,'condition':condition,'society':society,
            'sent_frames':len(frames),'sent_bytes':sum(r['bytes'] for r in frames),
            'delivered_bytes':sum(r['bytes'] for r in frames if r['status']=='delivered'),
            'pending_bytes':sum(r['bytes'] for r in frames if r['status']=='queued'),
            'delivered_frames':sum(r['status']=='delivered' for r in frames),
            'pending_frames':sum(r['status']=='queued' for r in frames),
            'uplink_frames':sum(r['channel']=='uplink' for r in frames),
            'downlink_frames':sum(r['channel']=='downlink' for r in frames),
            'novel_member_updates':sum(r['status']=='updated' for r in member_reports),
            'duplicate_member_reports':sum(r['status']=='duplicate' for r in member_reports),
            'institution_unique_updates':sum(r['status']=='updated' and r['actor_key'].startswith('institution:') for r in updates),
            'institution_duplicate_reports':sum(r['status']=='duplicate' and r['actor_key'].startswith('institution:') for r in updates),
            'failed_updates':sum(r['status']=='failed' for r in updates),
            'mean_delivered_age':float(np.mean([r['delivered_tick']-r['event_tick'] for r in frames if r['channel']=='downlink' and r['status']=='delivered'])) if member_reports else 0.})
    return rows


def run_case(task):
    directory,case,design = task
    destination = Path(directory)/'cases'/case['arena_id']
    destination.mkdir(parents=True,exist_ok=True)
    packets,probes,audit = generate_case(case,design)
    packed_write(destination/'data.json.gz',{'case':case,'packets':packets,'probes':probes,'audit':audit})
    checkpoints,parameters,predictions,transport,costs = [],[],[],[],[]
    bytick = {tick:{p['patch']:p for p in packets if p['tick']==tick} for tick in range(design['config']['ticks'])}
    for condition in CONDITIONS:
        cache = {}
        accepted_counts = {}
        scoring_cpu = 0.
        def record(runtime,key,model,axis,coordinate,completed_ticks):
            nonlocal scoring_cpu
            start = time.process_time()
            info = model.summary()
            count = info['n_observations']
            if (key,count) not in cache:
                cache[key,count] = score_model(model,case,key,probes,design)
            metrics,parameter_rows,score_rows = cache[key,count]
            base = {'arena_id':case['arena_id'],'condition':condition,**actor_identity(key),
                    'axis':axis,'coordinate':coordinate,'completed_ticks':completed_ticks}
            checkpoints.append({**base,**metrics,'unique_observations':count,
                'duplicate_events':info['diagnostics']['duplicate_events'],
                'failed_updates':info['diagnostics']['failed_updates'],'ess':info['effective_sample_size']})
            parameters.extend({**base,**row} for row in parameter_rows)
            predictions.extend({**base,**row} for row in score_rows)
            scoring_cpu += time.process_time()-start
        def after_update(runtime,key,model,status,event,channel):
            count = accepted_counts.get(key,0)+1
            accepted_counts[key] = count
            if key.startswith('member:') and count in design['evidence_checkpoints']:
                completed = runtime.clock + int(channel in ('local','union_ceiling'))
                record(runtime,key,model,'evidence',count,completed)
        started = time.process_time()
        runtime = SharingRuntime(condition,arena_id=case['arena_id'],
            seed=stable_seed(VERSION,case['arena_id'],'learners'),
            learner_kwargs={'prior':design['prior'],'sensor_sigma':design['sensor_sigma'],**design['learner_settings']},
            on_update=after_update)
        for key,model in runtime.evaluator_models().items():
            record(runtime,key,model,'ticks',0,0)
            if key.startswith('member:'):
                record(runtime,key,model,'evidence',0,0)
        for tick in range(design['config']['ticks']):
            runtime.step(tick,bytick[tick])
            if tick+1 in design['checkpoints']:
                for key,model in runtime.evaluator_models().items():
                    record(runtime,key,model,'ticks',tick+1,tick+1)
        total_cpu = time.process_time()-started
        transport.extend(transport_rows(runtime,case['arena_id'],condition))
        costs.append({'arena_id':case['arena_id'],'condition':condition,
                      'runtime_cpu_seconds':max(0.,total_cpu-scoring_cpu),'scoring_cpu_seconds':scoring_cpu})
        packed_write(destination/f'{condition}.json.gz',runtime.snapshot())
    for name,rows in (('checkpoints.csv',checkpoints),('parameters.csv',parameters),
                      ('predictions.csv.gz',predictions),('transport.csv',transport),('costs.csv',costs)):
        csv_write(destination/name,rows)
    return {'arena_id':case['arena_id'],'n_checkpoints':len(checkpoints),
        'n_predictions':len(predictions),'failed_updates':sum(r['failed_updates'] for r in transport)}


def bootstrap(values):
    x = np.asarray(values,dtype=float)
    if not len(x) or not np.isfinite(x).all():
        raise ValueError('Need finite independent arena values')
    rng = np.random.default_rng(9301)
    means = x[rng.integers(0,len(x),size=(2000,len(x)))].mean(axis=1)
    return {'mean':float(x.mean()),'ci95':np.quantile(means,[.025,.975]).tolist(),'n_arenas':len(x)}


def summarize(checkpoints,transport,costs,design):
    arenas = [case['arena_id'] for case in design['cases']]
    metrics = []
    for arena in arenas:
        for condition in CONDITIONS:
            for actor_type in ('member','institution'):
                count = 12 if actor_type=='member' else 3
                selected = [r for r in checkpoints if (r['arena_id'],r['condition'],r['actor_type'],r['axis'])==(arena,condition,actor_type,'ticks')]
                curve = []
                for tick in design['checkpoints']:
                    part = [r for r in selected if int(r['coordinate'])==tick]
                    if len(part)!=count or len({r['actor'] for r in part})!=count:
                        raise ValueError('Incomplete actor/checkpoint coverage')
                    curve.append(np.mean([float(r['probe_crps']) for r in part]))
                last = [r for r in selected if int(r['coordinate'])==design['config']['ticks']]
                row = {'arena_id':arena,'condition':condition,'actor_type':actor_type,
                    'crps_aulc_ticks':float(np.sum((np.array(curve[1:])+curve[:-1])*np.diff(design['checkpoints'])/2)/design['config']['ticks']),
                    **{k:float(np.mean([float(r[k]) for r in last])) for k in
                       ('probe_crps','coverage_90','interval_width_90','parameter_nrmse','unique_observations','failed_updates')}}
                if actor_type=='member':
                    evidence = [r for r in checkpoints if (r['arena_id'],r['condition'],r['actor_type'],r['axis'])==(arena,condition,'member','evidence')]
                    evidence_curve=[]
                    for n in design['evidence_checkpoints']:
                        part=[r for r in evidence if int(r['coordinate'])==n]
                        if len(part)!=12 or len({r['actor'] for r in part})!=12:
                            raise ValueError('Incomplete exact-evidence checkpoint coverage')
                        if any(int(r['unique_observations'])!=n for r in part):
                            raise ValueError('Evidence checkpoint skipped exact count')
                        evidence_curve.append(np.mean([float(r['probe_crps']) for r in part]))
                    row['crps_aulc_evidence']=float(np.sum((np.array(evidence_curve[1:])+evidence_curve[:-1])*np.diff(design['evidence_checkpoints'])/2)/design['evidence_checkpoints'][-1])
                metrics.append(row)
    summaries=[]
    for condition in CONDITIONS:
        for actor_type in ('member','institution'):
            part=[r for r in metrics if (r['condition'],r['actor_type'])==(condition,actor_type)]
            keys=[k for k in part[0] if k not in ('arena_id','condition','actor_type')]
            summaries.append({'condition':condition,'actor_type':actor_type,
                              **{key:bootstrap([r[key] for r in part]) for key in keys}})
    contrasts=[]
    for left,right in (('complementary','redundant'),('complementary','isolated'),('redundant','isolated'),
                       ('delayed_complementary','complementary'),('union_ceiling','complementary')):
        for actor_type in ('member','institution'):
            bycondition={c:{r['arena_id']:r for r in metrics if r['condition']==c and r['actor_type']==actor_type} for c in (left,right)}
            keys=['crps_aulc_ticks','probe_crps']+(['crps_aulc_evidence'] if actor_type=='member' else [])
            contrasts.append({'contrast':left+'_minus_'+right,'actor_type':actor_type,
                **{k:bootstrap([bycondition[left][a][k]-bycondition[right][a][k] for a in arenas]) for k in keys}})
    transport_summary=[]
    for condition in CONDITIONS:
        values={a:[r for r in transport if r['arena_id']==a and r['condition']==condition] for a in arenas}
        keys=('sent_bytes','sent_frames','delivered_frames','pending_frames','novel_member_updates','duplicate_member_reports','failed_updates')
        transport_summary.append({'condition':condition,**{k:bootstrap([sum(float(r[k]) for r in values[a]) for a in arenas]) for k in keys}})
    return {'study':VERSION,'n_arenas':len(arenas),'replication_unit':design['replication_unit'],
        'primary':design['primary'],'conditions':summaries,'paired_contrasts':contrasts,
        'arena_metrics':metrics,'transport':transport_summary,
        'compute':[{'condition':c,**{k:bootstrap([float(r[k]) for r in costs if r['condition']==c]) for k in ('runtime_cpu_seconds','scoring_cpu_seconds')}} for c in CONDITIONS],
        'notes':['All methods observe the same material trajectory; learning is passive.',
            'Content contrast matches sent bytes and latency; delayed contrast matches capacity but has fewer realized sends before the fixed horizon.',
            'Union is an unpriced information ceiling, not a matched-budget institution.',
            'Equal evidence count does not imply equal evidence content or order.']}


def run(directory,workers=4):
    directory=Path(directory)
    design=check_design(directory,live=True)
    if (directory/'completion.json').exists():
        raise ValueError('Completed sharing study exists; verify or use a new directory')
    started=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        outcomes=[]
        for outcome in pool.map(run_case,[(str(directory),case,design) for case in design['cases']]):
            outcomes.append(outcome)
            print(json.dumps({'completed':len(outcomes),'total':len(design['cases']),**outcome,
                              'elapsed_seconds':round(time.perf_counter()-started,1)}),flush=True)
    tables={}
    for name in ('checkpoints','parameters','transport','costs'):
        tables[name]=[row for case in design['cases'] for row in csv_read(directory/'cases'/case['arena_id']/(name+'.csv'))]
        csv_write(directory/(name+'.csv'),tables[name])
    summary=summarize(tables['checkpoints'],tables['transport'],tables['costs'],design)
    json_write(directory/'summary.json',summary)
    files=sorted(p for p in directory.rglob('*') if p.is_file() and p.name!='completion.json')
    json_write(directory/'completion.json',{'study':VERSION,'completed_utc':datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds':time.perf_counter()-started,'workers':workers,'model_generation_calls':0,
        'outcomes':outcomes,'artifacts':{str(p.relative_to(directory)):sha(p) for p in files}})
    return summary


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('Expected finite numerical evidence') from exc
    _require(np.isfinite(result), 'Expected finite numerical evidence')
    return result


def _close(actual, expected, message):
    _require(np.isclose(_number(actual), _number(expected), rtol=1e-10, atol=1e-11), message)


def _canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def _table_matches(actual, expected, label):
    """Compare exported CSV records with primitives without allowing extra rows."""
    _require(len(actual) == len(expected), label+' row count differs')
    for left, right in zip(actual, expected):
        _require(set(left) == set(right), label+' fields differ')
        for key, value in right.items():
            if isinstance(value, (int, float, np.number)):
                _close(left[key], value, label+' value differs: '+key)
            else:
                _require(left[key] == str(value), label+' identity differs: '+key)


def _expected_transport(condition, packets, ticks, failed_attempts=None):
    """Independent finite-state schedule reconstruction; no learner is fitted.

    A frame is charged when sent, its payload is immutable, and all queued
    deliveries precede new local observations. This generator deliberately
    does not call SharingRuntime's route or update methods.
    """
    from swarm_societies.world_model_v1.sharing import VERSION as runtime_version
    actors = [f'member:{s}:{m}' for s in range(3) for m in range(4)]
    actors += [f'institution:{s}' for s in range(3)]
    accepted = {actor:set() for actor in actors}
    failed_attempts = {} if failed_attempts is None else failed_attempts
    updates, frames = [], []
    store = {packet['event_id']:packet for packet in packets}
    owners = {event:sorted(f'member:{s}:{m}' for s in range(3) for m in range(4)
        if packet['patch'] in (s,(s+1+(m+packet['tick'])%2)%3)) for event,packet in store.items()}
    delay = 4 if condition == 'delayed_complementary' else 1
    by_tick = {(packet['tick'],packet['patch']):packet for packet in packets}
    queue = []

    def admit(tick, actor, packet, channel, frame=None):
        identity = packet['event_id']
        reason = failed_attempts.get(len(updates))
        status = 'failed' if reason is not None else ('duplicate' if identity in accepted[actor] else 'updated')
        if status != 'failed':
            accepted[actor].add(identity)
        updates.append({'tick':tick,'actor_key':actor,'event_id':identity,
                        'status':status,'channel':channel,'frame_id':frame,'reason':reason})

    def enqueue(tick, channel, sender, recipient, origin, packet, parent):
        frame = {'frame_id':f'frame:{len(frames)}','tick':tick,'kind':'sent',
            'channel':channel,'sender':sender,'recipient':recipient,'origin_member':origin,
            'event_id':packet['event_id'],'event_tick':packet['tick'],
            'measurement_sha256':hashlib.sha256(_canonical_bytes(packet)).hexdigest(),
            'parent_frame_id':parent,'bytes':1024,'delivery_tick':tick+delay,
            'status':'queued','delivered_tick':None,'packet':dict(packet)}
        body = {'version':runtime_version,**{key:frame[key] for key in
            ('frame_id','channel','sender','recipient','origin_member','event_id','event_tick',
             'measurement_sha256','parent_frame_id','tick','delivery_tick','packet')}}
        frame['payload_bytes'] = len(_canonical_bytes(body))
        _require(frame['payload_bytes'] <= 1024, 'Expected wire payload exceeds frame size')
        queue.append(len(frames))
        frames.append(frame)

    for tick in range(ticks):
        due = [index for index in queue if frames[index]['delivery_tick'] == tick]
        queue = [index for index in queue if frames[index]['delivery_tick'] != tick]
        for index in due:
            frame = frames[index]
            frame['status'], frame['delivered_tick'] = 'delivered',tick
            admit(tick,frame['recipient'],frame['packet'],frame['channel'],frame['frame_id'])
            if frame['channel'] == 'uplink':
                society = int(frame['recipient'].split(':')[1])
                for member in range(4):
                    enqueue(tick,'downlink',frame['recipient'],f'member:{society}:{member}',
                            frame['origin_member'],frame['packet'],frame['frame_id'])
        for society in range(3):
            for member in range(4):
                actor = f'member:{society}:{member}'
                visible = (society,(society+1+(member+tick)%2)%3)
                for patch in visible:
                    admit(tick,actor,by_tick[tick,patch],'local')
                if condition == 'union_ceiling':
                    for patch in range(3):
                        if patch not in visible:
                            admit(tick,actor,by_tick[tick,patch],'union_ceiling')
            if condition == 'union_ceiling':
                for patch in range(3):
                    admit(tick,f'institution:{society}',by_tick[tick,patch],'union_ceiling')
        if condition not in ('isolated','union_ceiling'):
            for society in range(3):
                for member in (0,1):
                    actor = f'member:{society}:{member}'
                    patch = society if condition == 'redundant' else (society+1+(member+tick)%2)%3
                    enqueue(tick,'uplink',actor,f'institution:{society}',actor,by_tick[tick,patch],None)
    return {'frames':frames,'updates':updates,'rejections':[], 'store':store,'owners':owners,
        'queue':queue,'current':{str(p):by_tick[ticks-1,p]['event_id'] for p in range(3)},
        'submitted':sorted(f'member:{s}:{m}' for s in range(3) for m in (0,1))
                    if condition not in ('isolated','union_ceiling') else []}


def _verify_design_contract(design):
    _require(design['study'] == VERSION and design['schema_version'] == 1,
             'Sharing design version differs')
    _require(design['conditions'] == list(CONDITIONS), 'Sharing condition grid differs')
    _require(design['frame_bytes'] == 1024 and design['normal_hop_delay'] == 1
        and design['slow_hop_delay'] == 4 and design['senders'] == [0,1],
        'Sharing channel contract differs')
    _require(design['prior'] == PRIOR and design['sensor_sigma'] == .05,
             'Sharing likelihood contract differs')
    _require(design['bootstrap'] == {'draws':2000,'seed':9301,'level':.95},
             'Sharing bootstrap contract differs')
    cfg = design['config']
    ticks = cfg['ticks']
    _require(cfg['n_societies'] == 3 and cfg['members_per_society'] == 4
        and ticks >= 8 and not cfg['enable_disturbance'], 'Sharing ecology contract differs')
    _require(design['bank'] in ('development','evaluation'), 'Unknown sharing case bank')
    _require(design['checkpoints'] == sorted({0,ticks,*[t for t in (4,8,16,32,64,128) if t <= ticks]})
        and design['evidence_checkpoints'] == sorted({0,2*ticks,*[n for n in (8,16,32,64,128,256) if n <= 2*ticks]}),
        'Sharing checkpoint grid differs')
    _require(design['n_probes'] >= 2 and design['n_probes'] % 2 == 0
        and design['forecast_samples'] >= 2, 'Sharing probe contract differs')
    _require(design['model_generation_calls'] == 0 and len(design['cases']) >= 1,
             'Sharing calls or case count differs')
    _require(set(design['source_hashes']) == set(SOURCE_FILES), 'Sharing source inventory differs')
    for index,case in enumerate(design['cases']):
        arena = f'sharing-{design["bank"]}-{index:03d}'
        rng = np.random.default_rng(stable_seed(VERSION,arena,'laws'))
        expected = {'arena_id':arena,'index':index,'role_rotation':index%3,
            'environment_seed':stable_seed(VERSION,arena,'environment'),
            'world_parameters':{p:float(rng.uniform(*bounds)) for p,bounds in
                zip(PARAMETERS,((2.4,6.8),(.7,2.7),(.05,.7)))}}
        _require(case == expected, 'Sharing case grid or law draw differs')


def _checkpoint_key(row):
    return (row['condition'],row['actor'],row['axis'],int(row['coordinate']))


def _verify_case(directory, case, design):
    """Rebuild one arena's communication, scored primitives, and final forecasts."""
    from swarm_societies.world_model_v1.learner import RenewalSMC, _log_likelihood
    directory = Path(directory)
    case_dir = directory/'cases'/case['arena_id']
    packets, probes, audit = generate_case(case,design)
    data = packed_read(case_dir/'data.json.gz')
    _require(data == {'case':case,'packets':packets,'probes':probes,'audit':audit},
             'Regenerated arena data differs')
    _require(abs(audit['ledger_residual']) < 1e-7, 'Material accounting residual differs')
    ticks = design['config']['ticks']
    actor_keys = [f'member:{s}:{m}' for s in range(3) for m in range(4)] + [f'institution:{s}' for s in range(3)]
    expected_keys = {(condition,actor,axis,coordinate)
        for condition in CONDITIONS for actor in actor_keys for axis in ('ticks','evidence')
        if axis == 'ticks' or actor.startswith('member:')
        for coordinate in design['checkpoints' if axis == 'ticks' else 'evidence_checkpoints']}
    tables = {name:csv_read(case_dir/(name+'.csv')) for name in ('checkpoints','parameters','transport','costs')}
    checkpoint_by_key = {_checkpoint_key(row):row for row in tables['checkpoints']}
    _require(len(checkpoint_by_key) == len(tables['checkpoints']) and set(checkpoint_by_key) == expected_keys,
             'Checkpoint identity grid differs')
    prediction_rows = csv_read(case_dir/'predictions.csv.gz')
    prediction_by_key = {}
    for row in prediction_rows:
        key = _checkpoint_key(row)
        identity = (key,int(row['probe_id']))
        _require(key in expected_keys and identity not in prediction_by_key, 'Prediction identity grid differs')
        prediction_by_key[identity] = row
    _require(len(prediction_by_key) == len(expected_keys)*len(probes), 'Prediction identity grid differs')
    parameter_by_key = {}
    for row in tables['parameters']:
        key = _checkpoint_key(row)
        identity = (key,row['parameter'])
        _require(key in expected_keys and row['parameter'] in PARAMETERS and identity not in parameter_by_key,
                 'Parameter identity grid differs')
        parameter_by_key[identity] = row
    _require(len(parameter_by_key) == 3*len(expected_keys), 'Parameter identity grid differs')
    _require(len(tables['costs']) == len(CONDITIONS) and {row['condition'] for row in tables['costs']} == set(CONDITIONS),
             'Cost identity grid differs')
    for row in tables['costs']:
        _require(row['arena_id'] == case['arena_id'], 'Cost arena identity differs')
        _require(_number(row['runtime_cpu_seconds']) >= 0 and _number(row['scoring_cpu_seconds']) >= 0,
                 'Negative compute cost')
    expected_transport_rows = []
    snapshots, expected_by_condition, models_by_condition = {}, {}, {}
    for condition in CONDITIONS:
        snapshot = packed_read(case_dir/f'{condition}.json.gz')
        failed_attempts = {index:row.get('reason') for index,row in enumerate(snapshot['updates']) if row['status'] == 'failed'}
        _require(all(isinstance(reason,str) and reason for reason in failed_attempts.values()),
                 'Failed update lacks a retained reason')
        expected = _expected_transport(condition,packets,ticks,failed_attempts)
        expected_by_condition[condition] = expected
        snapshots[condition] = snapshot
        _require(snapshot['condition'] == condition and snapshot['clock'] == ticks-1
            and snapshot['phase'] == 'finished' and snapshot['n_societies'] == 3
            and snapshot['members_per_society'] == 4,
            'Runtime checkpoint identity or horizon differs')
        _require(snapshot['seed'] == stable_seed(VERSION,case['arena_id'],'learners'), 'Runtime seed differs')
        _require(snapshot.get('arena_id',case['arena_id']) == case['arena_id'], 'Runtime arena binding differs')
        _require(snapshot['learner_kwargs'] == {'prior':design['prior'],'sensor_sigma':design['sensor_sigma'],**design['learner_settings']},
                 'Runtime learner configuration differs')
        for field in ('frames','updates','rejections','store','owners','queue','current','submitted'):
            _require(snapshot[field] == expected[field], 'Transport reconstruction differs: '+field)
        _require(set(snapshot['models']) == set(actor_keys), 'Private learner identity grid differs')
        restored = SharingRuntime.from_snapshot(snapshot)
        _require(restored.snapshot() == snapshot, 'Runtime snapshot restoration differs')
        expected_transport_rows.extend(transport_rows(restored,case['arena_id'],condition))
        models = restored.evaluator_models()
        models_by_condition[condition] = models
        for actor in actor_keys:
            stored = snapshot['models'][actor]
            history = [row for row in expected['updates'] if row['actor_key'] == actor]
            accepted = [expected['store'][row['event_id']] for row in history if row['status'] == 'updated']
            evidence = [{'event_id':p['event_id'],'headroom':p['capacity']-p['stock_before'],
                'own_infrastructure':p['own_infrastructure'],'other_infrastructure':p['other_infrastructure'],
                'growth':p['growth']} for p in accepted]
            _require(stored['evidence'] == evidence, 'Accepted posterior evidence differs from legal delivery order')
            for field,value in (('accepted_observations',len(accepted)),
                ('duplicate_events',sum(row['status'] == 'duplicate' for row in history)),
                ('failed_updates',sum(row['status'] == 'failed' for row in history))):
                _require(stored['diagnostics'][field] == value, 'Learner diagnostic counts differ: '+field)
            for field in ('n_particles','ess_fraction','rejuvenation_steps'):
                _require(stored[field] == design['learner_settings'][field], 'Posterior learner configuration differs')
            _require(stored['prior'] == design['prior'] and stored['sensor_sigma'] == design['sensor_sigma'],
                     'Posterior likelihood contract differs')
            particles = np.asarray(stored['particles'])
            likelihood = np.zeros(len(particles))
            for event in evidence:
                likelihood += _log_likelihood(particles,event['headroom'],event['own_infrastructure'],
                                              event['other_infrastructure'],event['growth'],design['sensor_sigma'])
            _require(np.allclose(likelihood,stored['log_likelihood'],rtol=1e-10,atol=1e-9),
                     'Posterior cached likelihood differs from legal evidence')
            if not evidence and not any(row['status'] == 'failed' for row in history):
                from swarm_societies.world_model_v1.sharing import actor_seed
                prior = RenewalSMC(seed=actor_seed(snapshot['seed'],actor),**snapshot['learner_kwargs'])
                _require(stored == prior.snapshot(), 'No-evidence learner differs from its frozen prior')
    _table_matches(tables['transport'],expected_transport_rows,'Transport table')
    for actor in actor_keys:
        if actor.startswith('member:'):
            isolated = snapshots['isolated']['models'][actor]
            redundant = snapshots['redundant']['models'][actor]
            _require({k:v for k,v in isolated.items() if k != 'diagnostics'} ==
                     {k:v for k,v in redundant.items() if k != 'diagnostics'},
                     'Redundant-report negative control changes posterior state')
            _require({k:v for k,v in isolated['diagnostics'].items() if k != 'duplicate_events'} ==
                     {k:v for k,v in redundant['diagnostics'].items() if k != 'duplicate_events'},
                     'Redundant-report negative control changes inference work')
    for key,row in checkpoint_by_key.items():
        condition,actor,axis,coordinate = key
        base = {'arena_id':case['arena_id'],'condition':condition,**actor_identity(actor),
                'axis':axis,'coordinate':coordinate}
        _table_matches([{k:row[k] for k in base}],[base],'Checkpoint ownership')
        history = [event for event in expected_by_condition[condition]['updates'] if event['actor_key'] == actor]
        if axis == 'ticks':
            history = [event for event in history if event['tick'] < coordinate]
            completed = coordinate
        elif coordinate == 0:
            history,completed = [],0
        else:
            accepted_positions = [j for j,event in enumerate(history) if event['status'] == 'updated']
            _require(len(accepted_positions) >= coordinate, 'Evidence checkpoint outside support')
            history = history[:accepted_positions[coordinate-1]+1]
            final_event = history[-1]
            completed = final_event['tick']+int(final_event['channel'] in ('local','union_ceiling'))
        _require(int(row['completed_ticks']) == completed and int(row['unique_observations']) ==
            sum(event['status'] == 'updated' for event in history) and int(row['duplicate_events']) ==
            sum(event['status'] == 'duplicate' for event in history) and int(row['failed_updates']) ==
            sum(event['status'] == 'failed' for event in history),
            'Checkpoint counts or availability time differ')
        _require(1-1e-8 <= _number(row['ess']) <= design['learner_settings']['n_particles']+1e-8,
                 'Invalid checkpoint effective sample size')
        base['completed_ticks'] = completed
        scores = []
        for probe in probes:
            score = prediction_by_key[key,probe['probe_id']]
            _table_matches([{k:score[k] for k in base}],[base],'Prediction ownership')
            _require(score['probe_group'] == probe['probe_group'], 'Probe group differs')
            _close(score['target'],probe['target'],'Probe target differs')
            low,high,mean,target = [_number(score[k]) for k in ('lo90','hi90','mean','target')]
            _require(low <= high and _number(score['crps']) >= -1e-10, 'Invalid prediction primitive')
            _close(score['width'],high-low,'Prediction interval width differs')
            _close(score['squared_error'],(mean-target)**2,'Prediction squared error differs')
            _require(int(score['covered']) == int(low <= target <= high), 'Prediction coverage differs')
            scores.append(score)
        primary = [score for score in scores if score['probe_group'] == 'uncapped']
        for field,source,selected in (('probe_crps','crps',primary),('probe_crps_all','crps',scores),
            ('probe_mse','squared_error',primary),('coverage_90','covered',primary),('interval_width_90','width',primary)):
            _close(row[field],np.mean([float(score[source]) for score in selected]),'Checkpoint score reconstruction differs: '+field)
        errors = []
        for parameter in PARAMETERS:
            estimate = parameter_by_key[key,parameter]
            _table_matches([{k:estimate[k] for k in base}],[base],'Parameter ownership')
            truth = case['world_parameters'][parameter]
            _close(estimate['true_value'],truth,'Parameter truth differs')
            low,high,mean = [_number(estimate[k]) for k in ('lo90','hi90','posterior_mean')]
            bounds = design['prior'][parameter]
            _require(bounds[0] <= low <= high <= bounds[1] and bounds[0] <= mean <= bounds[1]
                and _number(estimate['posterior_sd']) >= 0, 'Invalid parameter primitive')
            _close(estimate['width90'],high-low,'Parameter width differs')
            _close(estimate['absolute_error'],abs(mean-truth),'Parameter absolute error differs')
            _require(int(estimate['covered90']) == int(low <= truth <= high), 'Parameter coverage differs')
            errors.append(((mean-truth)/(bounds[1]-bounds[0]))**2)
        _close(row['parameter_nrmse'],np.sqrt(np.mean(errors)),'Checkpoint parameter error differs')
        if condition == 'redundant' and actor.startswith('member:'):
            isolated_key = ('isolated',actor,axis,coordinate)
            for probe in probes:
                first = prediction_by_key[isolated_key,probe['probe_id']]
                second = prediction_by_key[key,probe['probe_id']]
                _require({k:v for k,v in first.items() if k != 'condition'} ==
                    {k:v for k,v in second.items() if k != 'condition'}, 'Redundant control forecast differs')
    terminal_forecasts = 0
    for condition,models in models_by_condition.items():
        for actor,model in models.items():
            key = (condition,actor,'ticks',ticks)
            metrics,parameters,scores = score_model(model,case,actor,probes,design)
            for field,value in metrics.items():
                _close(checkpoint_by_key[key][field],value,'Terminal checkpoint forecast differs: '+field)
            _close(checkpoint_by_key[key]['ess'],model.summary()['effective_sample_size'],'Terminal ESS differs')
            for result in parameters:
                stored = parameter_by_key[key,result['parameter']]
                _table_matches([{k:stored[k] for k in result}],[result],'Terminal parameter reconstruction')
            for result in scores:
                stored = prediction_by_key[key,result['probe_id']]
                _table_matches([{k:stored[k] for k in result}],[result],'Terminal forecast reconstruction')
                terminal_forecasts += 1
    return tables, {'arena_id':case['arena_id'],'n_checkpoints':len(checkpoint_by_key),
        'n_predictions':len(prediction_rows),
        'failed_updates':sum(int(row['failed_updates']) for row in tables['transport'])}, terminal_forecasts


def verify(directory):
    """Verify transport independently and recompute recorded and terminal scores.

    Intermediate score averages are rebuilt from archived forecast primitives;
    terminal forecasts are independently regenerated from saved posteriors.
    This is not a refit of every intermediate posterior trajectory.
    """
    directory = Path(directory)
    design = check_design(directory)
    _verify_design_contract(design)
    completion = json.loads((directory/'completion.json').read_text())
    _require(completion['study'] == VERSION and completion['model_generation_calls'] == 0,
             'Completion identity differs')
    inventory = {str(path.relative_to(directory)) for path in directory.rglob('*')
                 if path.is_file() and path.name != 'completion.json'}
    _require(set(completion['artifacts']) == inventory, 'Completion artifact inventory differs')
    for name,expected in completion['artifacts'].items():
        _require(sha(directory/name) == expected, 'Sharing artifact checksum differs: '+name)
    _require({path.name for path in (directory/'cases').iterdir()} == {case['arena_id'] for case in design['cases']},
             'Case directory grid differs')
    combined = {name:[] for name in ('checkpoints','parameters','transport','costs')}
    outcomes,terminal_forecasts = [],0
    for case in design['cases']:
        tables,outcome,count = _verify_case(directory,case,design)
        for name,rows in tables.items():
            combined[name].extend(rows)
        outcomes.append(outcome)
        terminal_forecasts += count
    for name,rows in combined.items():
        _table_matches(csv_read(directory/(name+'.csv')),rows,'Exported '+name)
    summary = summarize(combined['checkpoints'],combined['transport'],combined['costs'],design)
    _require(json.loads((directory/'summary.json').read_text()) == summary, 'Paired arena summary reconstruction differs')
    _require(completion['outcomes'] == outcomes, 'Completion outcomes differ')
    return {'verified':True,'study':VERSION,'arenas':len(design['cases']),
        'checkpoints':len(combined['checkpoints']),'parameter_rows':len(combined['parameters']),
        'prediction_rows':sum(row['n_predictions'] for row in outcomes),
        'terminal_forecasts_regenerated':terminal_forecasts,'artifacts':len(inventory),
        'scope':'Independent route/admission reconstruction; all primitive score summaries; terminal posterior likelihoods and forecasts. Intermediate posterior trajectories are not refitted.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','verify'))
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/world-model-sharing-v1')
    parser.add_argument('--arenas',type=int,default=24)
    parser.add_argument('--ticks',type=int,default=128)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--development',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        design=prepare(args.output,args.arenas,args.ticks,args.development)
        print(json.dumps({'prepared':str(args.output),'arenas':len(design['cases'])}))
    elif args.command=='run':
        summary=run(args.output,args.workers)
        print(json.dumps({'complete':str(args.output),'n_arenas':summary['n_arenas']}))
    else:
        print(json.dumps(verify(args.output),indent=2))


if __name__=='__main__':
    main()
