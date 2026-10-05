#!/usr/bin/env python3
"""Measure actual episode throughput and process memory before choosing search concurrency."""
import concurrent.futures
import json
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from swarm_societies.ecology import EcologyConfig, run_episode
from swarm_societies.evaluation import ROOT, atomic_json


def episode(seed):
    started = time.perf_counter()
    programs = [ROOT / 'seeds' / f'{name}.py' for name in ['initial','cooperative','selfish']]
    result = run_episode(programs, EcologyConfig(n_societies=3,members_per_society=4,ticks=60,disturbance_tick=30),seed)
    return {'seed':seed,'seconds':time.perf_counter()-started,
            'rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'ledger_residual':result['ledger']['residual']}


if __name__ == '__main__':
    measurements=[]
    for workers in [1,2]:
        started=time.perf_counter()
        if workers==1:
            rows=[episode(i) for i in range(4)]
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
                rows=list(pool.map(episode,range(4)))
        elapsed=time.perf_counter()-started
        measurements.append({'workers':workers,'wall_seconds':elapsed,'episodes_per_second':4/elapsed,'episodes':rows})
    result={'measurements':measurements,'selected':{'societies':3,'members_per_society':4,'ticks':60,'proposal_concurrency':1,'evaluation_concurrency':1},
            'reason':'Sequential ecological updates require a frozen incumbent/challenger context. Simulation is inexpensive relative to subscription inference; two-process timing is recorded, not a reason to evaluate stale contexts.'}
    atomic_json(ROOT/'evidence/benchmark.json',result)
    print(json.dumps(result,indent=2))
