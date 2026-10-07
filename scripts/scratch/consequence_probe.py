"""Scratch consequence probe for docs/paper-contract-world-models-v1.md section 2 (not production code).

Run from the repo root: .venv/bin/python scripts/scratch/consequence_probe.py out.json

Runs the frozen v3 engine and the frozen navigation forager. "Believed capacity"
replaces the capacity field in the forager's observation only; the physics is
unchanged. A heterogeneous-capacity variant patches per-site capacity into a
private copy of the engine functions inside this process only.
"""
import copy, inspect, json, statistics as st, sys, textwrap
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
sys.path.insert(0, '.')
from swarm_societies.commons_v3 import engine
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy

CAPS = None  # per-site capacities for the heterogeneous variant

def patch_heterogeneous():
    for name, repl in (('_validate_state', [('p.stock > cfg.patch_capacity', 'p.stock > CAPS[p.id]')]),
                       ('_observe_validated', [('"capacity": cfg.patch_capacity', '"capacity": CAPS[p.id]')]),
                       ('step', [('remaining / cfg.patch_capacity', 'remaining / CAPS[old.id]'),
                                 ('cfg.renewal_rate * cfg.patch_capacity / 4.0', 'cfg.renewal_rate * CAPS[old.id] / 4.0'),
                                 ('cfg.patch_capacity - remaining', 'CAPS[old.id] - remaining')])):
        src = textwrap.dedent(inspect.getsource(getattr(engine, name)))
        for a, b in repl:
            assert a in src, (name, a)
            src = src.replace(a, b)
        ns = engine.__dict__
        exec(compile(src, f'<patched {name}>', 'exec'), ns)

def run(job):
    global CAPS
    label, need, law, floor, believed, caps, seed, horizon, init_frac = job
    if not getattr(engine, '_wm_patched', False):
        patch_heterogeneous()
        engine._wm_patched = True
    true_caps = list(caps) if caps is not None else [40.0] * 16
    top = float(max(true_caps))
    cfg = engine.Config(need=need, renewal_law=law, patch_capacity=top, initial_patch_stock=top * init_frac)
    engine.CAPS = [top] * 16          # permissive bound while the frozen initializer validates
    state = engine.initialize(cfg, seed)
    engine.CAPS = true_caps           # physical per-site capacities from here on
    state = replace(state, patches=tuple(replace(p, stock=init_frac * true_caps[p.id]) for p in state.patches))
    pols = [ForagerPolicy(reserve_ticks=2, stock_floor_fraction=floor, route_mode='net_yield') for _ in range(cfg.n_agents)]
    alone = shared = 0
    for t in range(horizon):
        obs = engine.observations(state)
        acts = []
        for i, o in enumerate(obs):
            if believed is not None:
                o = copy.deepcopy(o)
                for s in o['sites']:
                    s['capacity'] = believed if not isinstance(believed, (list, tuple)) else believed[s['id']]
            acts.append(pols[i](o))
        res = engine.step(state, acts)
        state = res.state
        harvesters = {}
        for a, row in zip(state.agents, res.ledger.agents):
            if row.harvested > 0:
                harvesters.setdefault((a.x, a.y), []).append(a.id)
        for ids in harvesters.values():
            if len(ids) == 1: alone += 1
            else: shared += len(ids)
    cons = sum(a.consumption for a in state.agents) / (cfg.n_agents * horizon * need)
    return {'label': label, 'need': need, 'seed': seed, 'share_of_need': cons,
            'alone_fraction_of_harvest_events': alone / max(1, alone + shared)}

if __name__ == '__main__':
    seeds = range(90001, 90005)
    H = 512
    jobs = []
    # 1. Homogeneous K=40, forager believes capacity K_b (floor = 0.5 K_b). Initial stock 0.6 K.
    for need in (1.2, 1.6):
        for kb in (20., 30., 40., 50., 60., 80.):
            for s in seeds:
                jobs.append((f'homog believed K={kb:g}', need, 'logistic', .5, kb, None, s, H, .6))
        for s in seeds:
            jobs.append(('homog no floor', need, 'logistic', 0., None, None, s, H, .6))
    # 2. Additive law: does restraint cost much when it is not needed?
    for need in (1.2, 1.6):
        for floor in (0., .5):
            for s in seeds:
                jobs.append((f'additive floor {floor}', need, 'additive', floor, None, None, s, H, .6))
    # 3. Heterogeneous site capacities (mean 40), oracle vs prior-mean belief vs no floor.
    import random
    for need in (1.2, 1.6):
        for s in seeds:
            caps = [20., 30., 40., 50., 60.] * 3 + [40.]
            random.Random(s).shuffle(caps)
            jobs.append(('hetero oracle (true K_j)', need, 'logistic', .5, None, caps, s, H, .6))
            jobs.append(('hetero prior (believes 40)', need, 'logistic', .5, 40., caps, s, H, .6))
            jobs.append(('hetero no floor', need, 'logistic', 0., None, caps, s, H, .6))
    with ProcessPoolExecutor(2) as pool:
        rows = list(pool.map(run, jobs))
    json.dump(rows, open(sys.argv[1], 'w'))
    keys = []
    for r in rows:
        if (r['label'], r['need']) not in keys: keys.append((r['label'], r['need']))
    for label, need in keys:
        sel = [r for r in rows if r['label'] == label and r['need'] == need]
        print(f"need {need}  {label:30s} share of need {st.mean(r['share_of_need'] for r in sel):.3f} "
              f"[{min(r['share_of_need'] for r in sel):.3f}-{max(r['share_of_need'] for r in sel):.3f}]  "
              f"sole-harvester events {st.mean(r['alone_fraction_of_harvest_events'] for r in sel):.2f}")
