"""Heterogeneity probe for paper contract section 2. Run from the repo root:
.venv/bin/python scripts/scratch/consequence_probe_heterogeneity.py out.json"""
import json, random, statistics as st, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
sys.path.insert(0, '.')
from consequence_probe import run

if __name__ == '__main__':
    seeds = range(90001, 90005)
    spreads = {'moderate K_j in 20..60': [20., 30., 40., 50., 60.],
               'wide K_j in 10..90': [10., 20., 40., 60., 90.]}
    jobs = []
    for name, levels in spreads.items():
        for need in (1.2, 1.6):
            for s in seeds:
                caps = levels * 3 + [40.]
                random.Random(s).shuffle(caps)
                mean = sum(caps) / len(caps)
                jobs.append((f'{name} | oracle true K_j', need, 'logistic', .5, None, caps, s, 512, .6))
                jobs.append((f'{name} | oracle, floor .25', need, 'logistic', .25, None, caps, s, 512, .6))
                for kb in (round(mean), 30., 20.):
                    jobs.append((f'{name} | believes K={kb:g} everywhere', need, 'logistic', .5, kb, caps, s, 512, .6))
    with ProcessPoolExecutor(2) as pool:
        rows = list(pool.map(run, jobs))
    json.dump(rows, open(sys.argv[1], 'w'))
    keys = []
    for r in rows:
        if (r['label'], r['need']) not in keys: keys.append((r['label'], r['need']))
    for label, need in keys:
        sel = [r for r in rows if r['label'] == label and r['need'] == need]
        print(f"need {need}  {label:48s} {st.mean(r['share_of_need'] for r in sel):.3f} "
              f"[{min(r['share_of_need'] for r in sel):.3f}-{max(r['share_of_need'] for r in sel):.3f}]")
