#!/usr/bin/env python3
"""Render the saved development gate, separately from decision evaluation."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.visualize_world_model_decision import equal, load_study
from swarm_societies.visualize import (
    BACKGROUND, INK, MUTED, RULE, SECONDARY, STYLE, digest, save, society_color, theme,
)
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

VERSION = 'world-model-decision-development-figures-v1'
CAPTION = (
    'Development evidence only: six designed law/environment arenas, each contributing three dependent '
    'focal-state comparisons. Left: the same legal observation and forecast randomness are used twice, '
    'substituting low versus high local infrastructure return b while keeping the other supplied '
    'coefficients fixed. Markers show the predicted private-utility advantage of investing all over '
    'redistributing all. Horizontal bars are declared gate tolerances, max(0.005, 3 times the paired '
    'planning Monte Carlo standard error); they are not 95% confidence intervals. Right: the realized '
    'paired evaluator-branch advantage under each arena’s actual planted law. The narrow gray band '
    'marks the ±0.005 material-value threshold, not uncertainty. Colors identify focal societies; '
    'marker shapes distinguish substituted laws and realized values. Labels list development case '
    'and society IDs. These cases were designed for task development, are not an IID evaluation law '
    'sample, and supply no estimate of general performance. No development result is pooled into '
    'the subsequent evaluation panel. Positive utility can reflect terminal wealth rather than '
    'additional consumption. All comparisons use the same 32-tick window and three-action menu.'
)


def checked_gate(source):
    study = load_study(source)
    if study['design']['bank'] != 'development':
        raise ValueError('Gate figure requires the separate development bank')
    completion = json.loads((source / 'completion.json').read_text())
    if digest(source / 'gate.json') != completion['artifact_hashes'].get('gate.json'):
        raise ValueError('Development gate artifact hash mismatch')
    gate = json.loads((source / 'gate.json').read_text())
    if gate['bank'] != 'development' or gate['n_arenas'] != study['n_arenas']:
        raise ValueError('Gate bank/count disagrees with its design')
    rows = {(row['arena_id'], int(row['focal'])): row for row in gate['states']}
    expected = {(arena, sid) for arena in study['arenas'] for sid in range(3)}
    if len(rows) != len(gate['states']) or set(rows) != expected or gate['n_states'] != len(rows):
        raise ValueError('Incomplete or duplicate development-state grid')
    for arena in study['arenas']:
        with gzip.open(source / f'cases/{arena}/case.json.gz', 'rt') as handle:
            case = json.load(handle)
        for item in case['gate_forecasts']:
            sid = int(item['focal'])
            row = rows[arena, sid]
            for label in ('low', 'high'):
                if item[label]['status'] != 'ok':
                    if row[label + '_gap'] is not None or row[label + '_tolerance'] is not None:
                        raise ValueError('Failed development forecast has numerical gate values')
                    continue
                contrast = next(value for value in item[label]['paired'] if value['public_fraction'] == 1.)
                equal(row[label + '_gap'], contrast['minus_redistribute'], 'gate forecast gap')
                equal(row[label + '_tolerance'], max(gate['rules']['absolute_tolerance'],
                      gate['rules']['mcse_multiplier'] * contrast['paired_mcse']), 'gate tolerance')
            low, high = item['low'], item['high']
            rank_switch = (low['status'] == high['status'] == 'ok' and low['action'] == 0.
                           and high['action'] == 1. and row['low_gap'] < -row['low_tolerance']
                           and row['high_gap'] > row['high_tolerance'])
            if row['rank_switch'] != rank_switch:
                raise ValueError('Development action-rank qualification disagrees')
            delta = (float(study['branch_index'][arena, sid, 1.]['utility']) -
                     float(study['branch_index'][arena, sid, 0.]['utility']))
            equal(row['realized_one_minus_zero'], delta, 'development realized action value')
    for key, count in gate['counts'].items():
        if sum(bool(row[key]) for row in gate['states']) != count:
            raise ValueError('Gate count differs from recorded states: ' + key)
    if bool(gate['passed']) != all(gate['checks'].values()):
        raise ValueError('Gate pass status differs from declared checks')
    return study, gate


def render(study, gate, output):
    cases = {case['arena_id']: case for case in study['design']['cases']}
    rows = sorted(gate['states'], key=lambda row: (row['arena_id'], row['focal']))
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 10.4), sharey=True,
                             gridspec_kw={'width_ratios': [1.55, 1]})
    fig.text(.065, .97, 'Does coefficient knowledge change the decision?',
             fontsize=18, weight='bold', va='top')
    fig.text(.065, .927,
             f"DEVELOPMENT ONLY · {gate['n_arenas']} designed arenas · {gate['n_states']} dependent focal-state comparisons · gate {'passed' if gate['passed'] else 'failed'}",
             fontsize=10.3, color=SECONDARY, va='top')
    positions = np.arange(len(rows))[::-1]
    for index, (row, position) in enumerate(zip(rows, positions)):
        color = society_color(row['focal'])
        if (index // 3) % 2 == 0:
            for ax in axes:
                ax.axhspan(position - .5, position + .5, color=MUTED, alpha=.5, zorder=0)
        for label, offset, marker in (('low', .16, 'o'), ('high', -.16, '^')):
            if row[label + '_gap'] is None:
                continue
            axes[0].errorbar(row[label + '_gap'], position + offset,
                            xerr=row[label + '_tolerance'], fmt=marker, color=color,
                            markerfacecolor=BACKGROUND if label == 'low' else color,
                            markersize=5, linewidth=1, capsize=2)
        axes[1].plot(row['realized_one_minus_zero'], position, marker='D', color=color,
                     markersize=5, linestyle='')
    labels = [f"{row['arena_id'].rsplit('-', 1)[-1]} · S{row['focal']}" for row in rows]
    axes[0].set_yticks(positions, labels)
    axes[0].set_ylabel('Development case · focal society')
    axes[0].set_title('Same state, substituted coefficient', loc='left')
    axes[1].set_title('Actual planted law, paired branches', loc='left')
    tolerance = gate['rules']['absolute_tolerance']
    axes[1].axvspan(-tolerance, tolerance, color=RULE, alpha=.55, zorder=0)
    for ax in axes:
        ax.axvline(0, color=SECONDARY, linestyle='--', linewidth=.85)
        ax.set_ylim(-.65, len(rows) - .35)
        ax.set_xlabel('Utility per member: invest all − redistribute', fontsize=9.7)
        ax.grid(axis='x', alpha=.4)
        ax.set_axisbelow(True)
    low, high = study['design']['gate']['counterfactual_b']
    fig.legend(handles=[Line2D([], [], marker='o', markerfacecolor=BACKGROUND, color=INK,
                              linestyle='', label=f'Forecast with b = {low:g}'),
                        Line2D([], [], marker='^', color=INK, linestyle='', label=f'Forecast with b = {high:g}'),
                        Line2D([], [], marker='D', color=INK, linestyle='', label='Realized branch difference')],
               loc='lower center', bbox_to_anchor=(.5, .121), ncol=3, fontsize=9.4)
    fig.legend(handles=[Line2D([], [], marker='o', color=society_color(sid), linestyle='',
                              label=f'Society {sid}') for sid in range(3)],
               loc='lower center', bbox_to_anchor=(.5, .086), ncol=3, fontsize=9.1)
    planted = [f"{arena.rsplit('-', 1)[-1]}: r={cases[arena]['world_parameters']['r']:g}, b={cases[arena]['world_parameters']['b']:g}"
               for arena in sorted(cases)]
    fig.text(.065, .080, 'Planted laws: ' + '  ·  '.join(planted[:3]), fontsize=8.9, color=SECONDARY)
    fig.text(.065, .056, '                     ' + '  ·  '.join(planted[3:]) + '  ·  g=0.3 throughout',
             fontsize=8.9, color=SECONDARY)
    fig.text(.065, .028, 'Bars show gate tolerances, not 95% intervals. Designed development states are excluded from final evaluation.',
             fontsize=9.2, color=SECONDARY)
    fig.subplots_adjust(left=.135, right=.975, top=.845, bottom=.225, wspace=.22)
    return save(fig, output / 'action-ranking-gate')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'evidence/world-model-decision-development-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'figures/world-model-decision-development-v1')
    args = parser.parse_args(argv)
    study, gate = checked_gate(args.source)
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    files = render(study, gate, args.output)
    table = args.output / 'development-states.csv'
    with table.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(gate['states'][0]))
        writer.writeheader()
        writer.writerows(gate['states'])
    readme = args.output / 'README.md'
    readme.write_text('# Development action-ranking gate\n\n'
        'This is designed development evidence, separate from the final evaluation panel.\n\n'
        '[SVG](action-ranking-gate.svg) · [PDF](action-ranking-gate.pdf) · [PNG](action-ranking-gate.png)\n\n'
        + CAPTION + '\n\n'
        f"Gate **{'passed' if gate['passed'] else 'failed'}**. Recorded qualification counts: "
        + ', '.join(f'{key}={value}' for key, value in gate['counts'].items()) + '.\n\n'
        '[Recorded state table](development-states.csv) · [Source/output hashes](manifest.json)\n\n'
        'The renderer checks completed-study hashes, committed forecast gaps, stated Monte Carlo tolerances, '
        'action-rank qualification and realized branch arithmetic. No new forecasts, learning or rollouts occur. '
        'Colors follow Chromatic Field v1. All three exports are generated from the same saved state rows.\n\n'
        '```bash\n.venv/bin/python scripts/visualize_world_model_decision_gate.py\n```\n')
    sources = [*study['inputs'], args.source / 'gate.json', args.source / 'completion.json',
               args.source / 'design.sha256', Path(__file__),
               ROOT / 'scripts/visualize_world_model_decision.py', ROOT / 'swarm_societies/visualize.py',
               ROOT / 'docs/visual-reference.md']
    def portable(path):
        path = path.resolve()
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    manifest = {'schema_version': 1, 'renderer_version': VERSION, 'style': STYLE,
                'bank': 'development', 'designed_arenas': gate['n_arenas'],
                'dependent_focal_states': gate['n_states'], 'bootstrap_intervals_displayed': False,
                'uncertainty_bars': 'gate tolerance max(.005, 3 paired planning MCSE), not confidence intervals',
                'caption': CAPTION, 'sources': {portable(path): digest(path) for path in sources},
                'artifacts': {path.name: digest(path) for path in [*files, table, readme]},
                'rendering_runs_training': False, 'rendering_runs_evaluation': False,
                'independent_evolutionary_runs': 0, 'model_generation_calls': 0,
                'software': {'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
                             'numpy': np.__version__}}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'development_arenas': gate['n_arenas'],
                      'states': gate['n_states'], 'gate_passed': gate['passed']}))


if __name__ == '__main__':
    main()
