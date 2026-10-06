#!/usr/bin/env python3
"""Render the exploratory baseline review using recorded evidence only."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.visualize import BACKGROUND, INK, RULE, SECONDARY, digest, save, theme
import matplotlib
import matplotlib.pyplot as plt

CONDITIONS = ('initial', 'coevolution', 'reconstructed_greedy')
LABELS = ('Initial', 'Coevolved', 'Greedy\nreconstructed')
MARKERS = ('o', 's', 'D')
METRICS = (
    ('welfare', 'Focal consumption welfare', 'per member per tick · higher is better'),
    ('utility_per_tick', 'Focal private utility', 'per member per tick · higher is better'),
    ('outward_harm_per_tick', 'Outward raid loss', 'per focal society per tick · lower is better'),
    ('other_welfare', 'Other societies’ welfare', 'mean of the two others · higher is better'),
)


def read(path):
    return json.loads(path.read_text())


def close(left, right, label):
    if not math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError('Recorded arithmetic differs: ' + label)


def load(source):
    manifest = read(source / 'manifest.json')
    if manifest['version'] != 'baseline-review-v1':
        raise ValueError('Unexpected baseline review version')
    expected_artifacts = {'policy.py', 'audit.py', 'provenance.json', 'baseline.json',
                          'comparison.json', 'README.md'}
    if set(manifest['artifacts_sha256']) != expected_artifacts:
        raise ValueError('Incomplete review archive')
    for name, expected in manifest['artifacts_sha256'].items():
        if digest(source / name) != expected:
            raise ValueError('Changed review artifact: ' + name)
    for name, expected in manifest['external_inputs_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Changed frozen comparator/input: ' + name)
    provenance = read(source / 'provenance.json')
    comparison = read(source / 'comparison.json')
    baseline = read(source / 'baseline.json')
    old_manifest = read(ROOT / 'evidence/mechanism-v1/manifest.json')
    if (provenance['cases'] != old_manifest['cases'] or
            provenance['opponent_panels'] != old_manifest['opponent_panels'] or
            provenance['focal_societies'] != old_manifest['focal_societies']):
        raise ValueError('Review changed the frozen case panel')
    cases = {row['id']: row for row in provenance['cases']}
    expected = {(case, panel, focal) for case in cases
                for panel in provenance['opponent_panels'] for focal in provenance['focal_societies']}
    if len(cases) != 12 or len(expected) != 108:
        raise ValueError('Unexpected independent-environment or scenario counts')
    rows = {}
    for condition in CONDITIONS:
        data = baseline if condition == 'reconstructed_greedy' else read(
            ROOT / 'evidence/mechanism-v1' / f'{condition}.json')
        indexed = {}
        for row in data['rows']:
            key = (row['case']['id'], row['opponents'], row['focal'])
            if key in indexed or row['case'] != cases[key[0]]:
                raise ValueError('Duplicate or changed scenario')
            indexed[key] = row
            for phase in ('drought', 'no_drought'):
                for metric, *_ in METRICS:
                    if not math.isfinite(row[phase][metric]):
                        raise ValueError('Nonfinite recorded outcome')
                close(row[phase]['welfare'], .85 - 1.5 * row[phase]['shortfall_per_member_tick'],
                      'welfare and consumption shortfall')
        if indexed.keys() != expected:
            raise ValueError('Missing or unexpected scenario')
        rows[condition] = indexed
        for phase in ('drought', 'no_drought'):
            for metric, *_ in METRICS:
                value = statistics.mean(r[phase][metric] for r in indexed.values())
                close(value, data['summary'][phase][metric], condition + ' summary')
                close(value, comparison['summaries'][condition][phase][metric], condition + ' comparison')
    for condition in CONDITIONS[:2]:
        for phase in ('drought', 'no_drought'):
            for metric, *_ in METRICS:
                differences = [rows['reconstructed_greedy'][key][phase][metric] -
                               rows[condition][key][phase][metric] for key in sorted(expected)]
                saved = comparison['paired_comparisons'][condition][phase][metric]
                close(statistics.mean(differences), saved['mean_difference'], 'paired difference')
                for key, count in (('positive_cases_tolerance_1e-12', sum(d > 1e-12 for d in differences)),
                                   ('negative_cases_tolerance_1e-12', sum(d < -1e-12 for d in differences)),
                                   ('tied_cases_tolerance_1e-12', sum(abs(d) <= 1e-12 for d in differences))):
                    if count != saved[key]:
                        raise ValueError('Paired case count differs')
    return rows, manifest


def plot(rows, output):
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 10.1))
    fig.text(.08, .965, 'A simple baseline exposes an evaluation gap',
             fontsize=20, weight='bold', va='top')
    fig.text(.08, .921, 'Exploratory reconstruction · saved mechanism cases · drought outcomes',
             color=SECONDARY, fontsize=11)
    limits = ((.842, .852), (.91, 1.095), (-.07, .83), (.8449, .8485))
    ticks = ((.842, .846, .850), (.92, .98, 1.04), (0, .3, .6), (.845, .846, .847, .848))
    table = []
    for ax, (metric, heading, units), bounds, xticks in zip(axes.flat, METRICS, limits, ticks):
        ax.set_title(heading, loc='left', pad=34)
        ax.text(0, 1.065, units, transform=ax.transAxes, fontsize=9, color=SECONDARY)
        ax.set_yticks(range(3), LABELS)
        ax.set_ylim(2.5, -.7)
        ax.set_xlim(*bounds)
        ax.set_xticks(xticks)
        ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        ax.tick_params(axis='y', length=0, pad=11)
        ax.spines['left'].set_visible(False)
        ax.grid(axis='x', alpha=.7)
        for index, condition in enumerate(CONDITIONS):
            value = statistics.mean(r['drought'][metric] for r in rows[condition].values())
            ax.scatter(value, index, s=90, marker=MARKERS[index], facecolor=BACKGROUND,
                       edgecolor=INK, linewidth=1.6, zorder=4)
            ax.annotate(f'{value:.6f}', (value, index), xytext=(10, 0),
                        textcoords='offset points', va='center', fontsize=10, color=INK,
                        bbox={'facecolor': BACKGROUND, 'edgecolor': 'none', 'pad': 1.5})
            table.append({'condition': condition, 'metric': metric, 'phase': 'drought',
                          'mean': value, 'focal_scenarios': 108, 'environment_tuples': 12})
        if metric == 'welfare':
            ax.axvline(.85, color=SECONDARY, linewidth=.9, linestyle='--', zorder=2)
            ax.text(.85, -.50, '.85 ceiling', ha='center', fontsize=8.5, color=SECONDARY)
    fig.text(.08, .136, 'Means over 108 focal scenarios: 12 environment/timing tuples × 3 opponent panels × 3 identities.',
             fontsize=10, color=SECONDARY)
    fig.text(.08, .108, 'One existing evolved lineage; zero new searches. Means are not universal guarantees or uncertainty intervals.',
             fontsize=9.5, color=SECONDARY)
    fig.text(.08, .080, 'Zero raid loss excludes patch competition. Welfare = .85 − 1.5 × unmet need/member/tick; these are one outcome.',
             fontsize=9.5, color=SECONDARY)
    fig.text(.08, .052, 'Axes use separate, displayed ranges. Focal private utility includes consumption plus 0.2 × terminal wealth.',
             fontsize=9.5, color=SECONDARY)
    fig.subplots_adjust(left=.15, right=.96, top=.81, bottom=.24, wspace=.65, hspace=.66)
    paths = save(fig, output / 'baseline-outcomes')
    destination = output / 'means.csv'
    with destination.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    return [*paths, destination]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'evidence/baseline-review-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'figures/baseline-review-v1')
    args = parser.parse_args()
    rows, archive = load(args.source)
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = plot(rows, args.output)
    readme = args.output / 'README.md'
    readme.write_text('''# Simple baseline review · Chromatic Field v1

![Recorded focal and outsider outcomes](baseline-outcomes.png)

[SVG](baseline-outcomes.svg) · [PDF](baseline-outcomes.pdf) · [PNG](baseline-outcomes.png) · [Exact means](means.csv)

Recorded drought means from 108 matched focal scenarios: 12 environment/timing
tuples, three opponent panels and three focal identities. The initial and
coevolved conditions are saved programs from one existing search lineage. The
greedy condition is an exploratory reconstruction of an externally described
policy; its original source was not supplied. All four members and the focal
institution are replaced together. No new search or model call was made.

Each panel has a separate, explicitly displayed axis range. Markers identify
conditions; they do not encode society identity. Means have no uncertainty bars
and do not demonstrate universal dominance. Welfare and unmet need are the same
primitive outcome: welfare = 0.85 − 1.5 × unmet need/member/tick. Focal private
utility is (consumption + 0.2 × terminal wealth) per member per tick. Outward
raid loss counts victim losses, not all ecological effects. Other societies'
welfare decreases under the reconstructed baseline despite zero outward raids.

The evidence includes 216 new paired drought/no-drought rollouts; this figure
uses the drought half. The [archive](../../evidence/baseline-review-v1/README.md)
contains reconstruction choices, raw rows, comparisons, provenance and hashes.
The renderer reads recorded data only and checks hashes, complete paired grids,
summary arithmetic and the welfare identity before export.

Re-render from the repository root:

```bash
.venv/bin/python scripts/visualize_baseline_review.py
```
''')
    outputs.append(readme)
    paths = [args.source / 'manifest.json', *[args.source / name for name in archive['artifacts_sha256']],
             *[ROOT / name for name in archive['external_inputs_sha256']],
             Path(__file__), ROOT / 'swarm_societies/visualize.py']
    manifest = {
        'version': 'baseline-review-figures-v1', 'style': 'Chromatic Field v1',
        'rendering_runs_simulation': False,
        'sources': [{'path': str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT)
                    else str(path.resolve()), 'sha256': digest(path)} for path in paths],
        'outputs': [{'path': path.name, 'sha256': digest(path)} for path in outputs],
        'versions': {'python': platform.python_version(), 'matplotlib': matplotlib.__version__},
        'caption': 'Exploratory reconstructed policy versus saved initial and coevolved programs, '
                   'drought means over 108 focal scenarios from 12 environment/timing tuples. '
                   'One existing evolutionary lineage, zero new searches; no uncertainty or universal dominance claim. '
                   'Separate displayed axes and neutral condition markers; welfare/shortfall are one outcome.',
    }
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(f'Validated recorded grids; rendered {len(outputs)} artifacts in {args.output}')


if __name__ == '__main__':
    main()
