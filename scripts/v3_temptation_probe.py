#!/usr/bin/env python3
"""Where does the private temptation in commons v3 come from? (run from repo root, ~1 min)

Uses seeds 90001-90008, disjoint from every frozen qualification panel, the
frozen fixed-floor control and its supplied aggressive variant, 256 ticks.
Reports the focal private gain from switching restrained -> aggressive,
divided by need, at utility weights 0 / 0.05 / 0.2, against 0 and 23
aggressive peers, at inventory capacity 80 (reference) and 8.
Intervals are ordinary 95% t-intervals over 8 seeds (descriptive only).
"""
import math, statistics as st, sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
sys.path.insert(0, '.')
from swarm_societies.commons_v3.engine import Config
from swarm_societies.commons_v3.qualification_episode_v1 import record_episode
from swarm_societies.commons_v3.qualification_design_v1 import CONTROLS

SEEDS = range(90001, 90009)
CONTROL = next(c for c in CONTROLS if c['id'] == 'fixed_floor')
NEED, FOCAL = 1.2, 0
PANELS = {'reference (capacity 80)': {}, 'inventory capacity 8': {'inventory_capacity': 8.0}}


def focal_agent(job):
    updates, seed, mask = job
    cfg = replace(Config(initial_patch_stock=40., need=NEED), **updates)
    case = {'id': f'probe-{seed}', 'config': asdict(cfg), 'horizon': 256, 'seed': seed}
    ep = record_episode(case, CONTROL, mask)
    return ep['agents'][FOCAL]


def interval(values):
    m = st.mean(values)
    h = 2.365 * st.stdev(values) / math.sqrt(len(values))
    return f'{m:+.4f} [{m - h:+.4f}, {m + h:+.4f}]'


if __name__ == '__main__':
    others = list(range(1, 24))
    masks = {('none', 'restrained'): [], ('none', 'aggressive'): [FOCAL],
             ('all', 'restrained'): others, ('all', 'aggressive'): [FOCAL] + others}
    for panel, updates in PANELS.items():
        jobs = [(updates, s, m) for s in SEEDS for m in masks.values()]
        with ProcessPoolExecutor() as pool:
            agents = list(pool.map(focal_agent, jobs))
        res = {(s, key): agents[i * 4 + j] for i, s in enumerate(SEEDS) for j, key in enumerate(masks)}
        base = st.mean(res[(s, ('none', 'restrained'))]['consumption_per_tick'] for s in SEEDS) / NEED
        print(f'\n== {panel}: restrained focal among restrained peers consumes {base:.2%} of need')
        for peers, label in (('none', '0 aggressive peers'), ('all', '23 aggressive peers')):
            for w in ('0.0', '0.05', '0.2'):
                gains = [(res[(s, (peers, 'aggressive'))]['utility'][w] - res[(s, (peers, 'restrained'))]['utility'][w]) / NEED
                         for s in SEEDS]
                print(f'  {label:20} weight {w:4}: focal gain / need {interval(gains)}')
