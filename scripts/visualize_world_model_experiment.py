#!/usr/bin/env python3
"""Render recorded costed-experiment evidence; never fit, select or simulate."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.visualize import (
    BACKGROUND, INK, MUTED, RULE, SECONDARY, STYLE, digest, save, society_color, theme,
)
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

VERSION = 'costed-experiment-figures-v1'
SCHEDULES = ('early', 'late', 'split')
PATHS = (*SCHEDULES, 'redistribute')
STRATEGIES = ('active', 'fixed', 'random')
BELIEFS = ('frozen', 'updated', 'known')
MARKERS = {'early': 'o', 'late': '^', 'split': 's', 'redistribute': 'D'}
TABLES = ('acquisition.csv', 'selections.csv', 'paths.csv', 'decisions.csv', 'scores.csv', 'contrasts.csv')


def read_csv(path):
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f'Empty recorded table: {path}')
    return rows


def number(row, key):
    value = float(row[key])
    if not np.isfinite(value):
        raise ValueError(f'Nonfinite recorded {key}')
    return value


def equal(left, right, name):
    if not np.isclose(float(left), float(right), rtol=1e-10, atol=1e-11):
        raise ValueError(f'Recorded arithmetic differs: {name}')


def index(rows, keys, expected, label):
    counts = Counter(tuple(str(row[key]) for key in keys) for row in rows)
    if set(counts) != expected or any(value != 1 for value in counts.values()):
        raise ValueError(f'Incomplete or duplicate {label} grid')
    return {tuple(str(row[key]) for key in keys): row for row in rows}


def load(source):
    design = json.loads((source / 'design.json').read_text())
    if digest(source / 'design.json') != (source / 'design.sha256').read_text().strip():
        raise ValueError('Design checksum differs')
    completion = json.loads((source / 'completion.json').read_text())
    for name, expected in completion['artifact_hashes'].items():
        if digest(source / name) != expected:
            raise ValueError('Completion artifact hash differs: ' + name)
    for name in (*TABLES, 'design.json', 'summary.json'):
        if name not in completion['artifact_hashes']:
            raise ValueError('Missing committed input: ' + name)
    if design['bootstrap'] != {'draws': 2000, 'seed': 9501, 'level': .95}:
        raise ValueError('Undeclared bootstrap settings')
    arenas = sorted(case['arena_id'] for case in design['cases'])
    states = [(arena, str(sid)) for arena in arenas for sid in range(3)]
    tables = {name.removesuffix('.csv'): read_csv(source / name) for name in TABLES}
    acq = index(tables['acquisition'], ('arena_id', 'focal', 'schedule'),
                {(*state, schedule) for state in states for schedule in SCHEDULES}, 'acquisition')
    selections = index(tables['selections'], ('arena_id', 'focal', 'strategy'),
                       {(*state, strategy) for state in states for strategy in STRATEGIES}, 'selection')
    paths = index(tables['paths'], ('arena_id', 'focal', 'schedule'),
                  {(*state, schedule) for state in states for schedule in PATHS}, 'probe path')
    decisions = index(tables['decisions'], ('arena_id', 'focal', 'schedule', 'belief'),
                      {(*state, schedule, belief) for state in states for schedule in PATHS
                       for belief in BELIEFS}, 'downstream decision')
    scores = index(tables['scores'], ('arena_id', 'focal', 'strategy', 'belief'),
                   {(*state, strategy, belief) for state in states
                    for strategy in (*STRATEGIES, 'redistribute') for belief in BELIEFS}, 'strategy score')
    contrasts = index(tables['contrasts'], ('arena_id', 'focal', 'contrast'),
                      {(*state, 'active_minus_' + other) for state in states
                       for other in ('random', 'fixed', 'redistribute')}, 'paired contrast')
    for state in states:
        values = [number(acq[*state, name], 'proxy_score') for name in SCHEDULES]
        active = SCHEDULES[int(np.argmax(values))]
        if selections[*state, 'active']['schedule'] != active:
            raise ValueError('Active choice differs from committed scores')
        if selections[*state, 'fixed']['schedule'] != 'split':
            raise ValueError('Fixed schedule changed')
        escrow = number(paths[*state, 'early'], 'escrow')
        if escrow <= 0:
            raise ValueError('Nonpositive experimental escrow')
        for schedule in PATHS:
            path = paths[*state, schedule]
            equal(number(path, 'escrow'), escrow, 'shared escrow')
            equal(number(path, 'actual_experiment_investment'),
                  escrow if schedule in SCHEDULES else 0., 'actual experiment investment')
            for metric in ('sent_bytes', 'delivered_bytes', 'own_unique_events_added'):
                equal(number(path, metric), number(paths[*state, 'early'], metric), metric)
            for belief in BELIEFS:
                row = decisions[*state, schedule, belief]
                equal(number(row, 'total_utility'), number(row, 'utility') +
                      number(path, 'probe_consumption_per_member'), 'total utility')
                equal(number(row, 'total_consumption_per_member'),
                      number(row, 'consumption_per_member') +
                      number(path, 'probe_consumption_per_member'), 'total consumption')
                equal(number(row, 'total_utility'), number(row, 'total_consumption_per_member') +
                      .2 * number(row, 'terminal_wealth_per_member'), 'utility primitives')
        for strategy in (*STRATEGIES, 'redistribute'):
            schedule = selections[*state, strategy]['schedule'] if strategy in STRATEGIES else 'redistribute'
            if schedule not in PATHS:
                raise ValueError('Unknown selected schedule')
            for belief in BELIEFS:
                for metric in ('action', 'total_utility', 'utility', 'total_consumption_per_member',
                               'terminal_wealth_per_member', 'actual_experiment_investment'):
                    equal(number(scores[*state, strategy, belief], metric),
                          number(decisions[*state, schedule, belief], metric), 'selected ' + metric)
        for other in ('random', 'fixed', 'redistribute'):
            row = contrasts[*state, 'active_minus_' + other]
            updated = number(scores[*state, 'active', 'updated'], 'total_utility') - number(scores[*state, other, 'updated'], 'total_utility')
            frozen = number(scores[*state, 'active', 'frozen'], 'total_utility') - number(scores[*state, other, 'frozen'], 'total_utility')
            equal(number(row, 'total_utility_difference'), updated, 'updated-policy contrast')
            equal(number(row, 'frozen_total_utility_difference'), frozen, 'frozen-policy contrast')
            equal(number(row, 'update_value_difference'), updated - frozen, 'posterior-update contrast')
            equal(number(row, 'decomposition_residual'), 0., 'decomposition residual')
    summary = json.loads((source / 'summary.json').read_text())
    for condition in summary['conditions']:
        for metric, saved in condition['metrics'].items():
            values = [np.mean([number(scores[arena, str(sid), condition['strategy'], condition['belief']], metric)
                               for sid in range(3)]) for arena in arenas]
            result = estimate(values)
            equal(saved['mean'], result['mean'], 'summary condition mean')
            equal(saved['ci95'][0], result['low'], 'summary condition interval')
            equal(saved['ci95'][1], result['high'], 'summary condition interval')
    for contrast in summary['paired_contrasts']:
        for metric, saved in contrast['metrics'].items():
            values = [np.mean([number(contrasts[arena, str(sid), contrast['contrast']], metric)
                               for sid in range(3)]) for arena in arenas]
            result = estimate(values)
            equal(saved['mean'], result['mean'], 'summary paired mean')
            equal(saved['ci95'][0], result['low'], 'summary paired interval')
            equal(saved['ci95'][1], result['high'], 'summary paired interval')
    gate = None
    if design['bank'] == 'development':
        gate = json.loads((source / 'gate.json').read_text())
        if bool(gate['passed']) != all(gate['checks'].values()):
            raise ValueError('Development gate status differs')
        if gate['rules'] != design['gate'] or gate['n_states'] != len(states):
            raise ValueError('Development gate contract/count differs')
        gate_states = index(gate['states'], ('arena_id', 'focal'), set(states), 'gate state')
        for state in states:
            selected = selections[*state, 'active']
            if gate_states[state]['active_schedule'] != selected['schedule']:
                raise ValueError('Gate active schedule differs')
            equal(gate_states[state]['proxy_minus_split'], selected['proxy_minus_split'], 'gate proxy advantage')
        distinct = len({selections[*state, 'active']['schedule'] for state in states})
        advantages = sum(selections[*state, 'active']['schedule'] != 'split' and
                         number(selections[*state, 'active'], 'proxy_minus_split') > design['gate']['proxy_tolerance']
                         for state in states)
        changes = [(*state, schedule) for state in states for schedule in PATHS
                   if number(decisions[*state, schedule, 'updated'], 'action') != number(decisions[*state, schedule, 'frozen'], 'action')]
        counts = {'distinct_active_schedules': distinct, 'nonfixed_proxy_advantages': advantages,
                  'costed_update_action_changes': sum(schedule in SCHEDULES for _, _, schedule in changes),
                  'all_update_action_changes': len(changes)}
        if gate['counts'] != counts:
            raise ValueError('Development qualification counts differ')
        expected_checks = {
            'multiple_active_schedules': distinct >= design['gate']['minimum_distinct_active_schedules'],
            'nonfixed_proxy_advantages': advantages >= design['gate']['minimum_nonfixed_advantages'],
            'costed_update_action_changes': counts['costed_update_action_changes'] >= design['gate']['minimum_costed_action_changes'],
        }
        if any(gate['checks'][key] != value for key, value in expected_checks.items()):
            raise ValueError('Development qualification criteria differ')
    return {'design': design, 'arenas': arenas, 'states': states, 'tables': tables,
            'acquisition': acq, 'selections': selections, 'paths': paths,
            'decisions': decisions, 'scores': scores, 'contrasts': contrasts,
            'gate': gate, 'source': source, 'summary': summary}


def estimate(values, development=False):
    values = np.asarray(values, dtype=float)
    result = {'mean': float(values.mean()), 'n_arenas': len(values)}
    if not development:
        indices = np.random.default_rng(9501).integers(len(values), size=(2000, len(values)))
        result['low'], result['high'] = map(float, np.quantile(values[indices].mean(axis=1), [.025, .975]))
    return result


def arena_values(study, function, sid=None):
    return [np.mean([function((arena, str(s))) for s in (range(3) if sid is None else [sid])])
            for arena in study['arenas']]


def heading(fig, title, subtitle):
    fig.text(.05, .97, title, fontsize=18, weight='bold', va='top')
    fig.text(.05, .915, subtitle, fontsize=10, color=SECONDARY, va='top')


def key(fig, y=.02):
    fig.legend(handles=[Line2D([], [], color=society_color(sid), marker='o', linestyle='',
                              label=f'Society {sid}') for sid in range(3)],
               loc='lower center', bbox_to_anchor=(.5, y), ncol=3, fontsize=9)


def selection_figure(study, output):
    development = study['design']['bank'] == 'development'
    if development:
        fig, axes = plt.subplots(1, 2, figsize=(12.8, 9.8), sharey=True)
        heading(fig, 'Which experiment does the information proxy select?',
                f"DEVELOPMENT ONLY · {len(study['arenas'])} designed arenas · gate {'passed' if study['gate']['passed'] else 'failed'}")
        positions = np.arange(len(study['states']))[::-1]
        for state, y in zip(study['states'], positions):
            color = society_color(int(state[1]))
            selected = study['selections'][*state, 'active']['schedule']
            baseline = number(study['acquisition'][*state, 'split'], 'proxy_score')
            for schedule, offset in zip(SCHEDULES, (-.19, 0., .19)):
                score = number(study['acquisition'][*state, schedule], 'proxy_score') - baseline
                axes[0].plot(score, y + offset, marker=MARKERS[schedule], linestyle='',
                             color=color, markerfacecolor=color if schedule == selected else BACKGROUND,
                             markersize=5)
                delta = number(study['decisions'][*state, schedule, 'updated'], 'total_utility') - number(study['decisions'][*state, schedule, 'frozen'], 'total_utility')
                axes[1].plot(delta, y + offset, marker=MARKERS[schedule], linestyle='',
                             color=color, markersize=5)
        axes[0].set_yticks(positions, [f'{arena.rsplit("-", 1)[-1]} · S{sid}' for arena, sid in study['states']])
        axes[0].set_title('Predicted score advantage over Split', loc='left')
        axes[1].set_title('Realized value of posterior updates', loc='left')
        axes[0].set_xlabel('Joint information proxy difference')
        axes[1].set_xlabel('Updated − frozen utility per member')
        axes[0].set_ylabel('Development arena · focal society')
        for ax in axes:
            ax.axvline(0, color=SECONDARY, ls='--', lw=.8)
            ax.grid(axis='x', alpha=.4)
            ax.set_axisbelow(True)
        fig.legend(handles=[Line2D([], [], color=INK, marker=MARKERS[s], linestyle='', label=s.title())
                            for s in SCHEDULES], loc='lower center', bbox_to_anchor=(.5, .10), ncol=3)
        fig.text(.05, .085, 'Filled score markers identify the selected schedule. No confidence intervals: these are designed development states.',
                 fontsize=9, color=SECONDARY)
        fig.text(.05, .055, 'Proxy units are not utility. Updated and frozen coefficients receive the same current legal state on each physical path.',
                 fontsize=9, color=SECONDARY)
        key(fig, y=.008)
        fig.subplots_adjust(left=.13, right=.975, top=.825, bottom=.18, wspace=.28)
    else:
        fig, axes = plt.subplots(1, 3, figsize=(12.6, 5.8), sharey=True)
        heading(fig, 'Recorded experiment choices at equal investment budgets',
                f"{len(study['arenas'])} independent arenas · one schedule per focal institution · early, late or split escrow")
        for sid, ax in enumerate(axes):
            bottom = np.zeros(3)
            for schedule, fill, hatch in zip(SCHEDULES, (BACKGROUND, SECONDARY, MUTED), ('', '', '////')):
                counts = [sum(study['selections'][arena, str(sid), strategy]['schedule'] == schedule for arena in study['arenas'])
                          / len(study['arenas']) * 100 for strategy in STRATEGIES]
                ax.bar(range(3), counts, bottom=bottom, color=fill, edgecolor=SECONDARY,
                       hatch=hatch, linewidth=.6, width=.65, label=schedule.title())
                bottom += counts
            ax.set_title(f'Society {sid}', loc='left', color=society_color(sid))
            ax.set_xticks(range(3), ['Active', 'Fixed', 'Random'])
            ax.set_ylim(0, 100)
            ax.grid(axis='y', alpha=.4)
            ax.set_axisbelow(True)
        axes[0].set_ylabel('Share of focal choices (%)')
        fig.legend(*axes[0].get_legend_handles_labels(), loc='lower center', bbox_to_anchor=(.5, .04), ncol=3)
        fig.text(.05, .14, 'All three schedules invest the same escrow B. Equal spending does not imply equal material outcomes or opportunity costs.',
                 fontsize=9, color=SECONDARY)
        fig.subplots_adjust(left=.08, right=.975, top=.75, bottom=.26, wspace=.24)
    return save(fig, output / 'experiment-selection')


def effects_figure(study, output):
    development = study['design']['bank'] == 'development'
    fig, axes = plt.subplots(2, 2, figsize=(13.3, 8.6))
    heading(fig, 'Separate the value of updating from the material path',
            ('DEVELOPMENT ONLY · descriptive means, no confidence intervals' if development else
             f"{len(study['arenas'])} independent arenas · paired whole-arena 95% intervals"))
    metrics = [('update_value_difference', 'Posterior-update value · primary'),
               ('total_utility_difference', 'Total utility under updated beliefs'),
               ('frozen_total_utility_difference', 'Total utility under frozen coefficients'),
               ('consumption', 'Consumption under updated beliefs')]
    exported = []
    for ax, (metric, title) in zip(axes.flat, metrics):
        for y, other in enumerate(('fixed', 'random')):
            def difference(state):
                if metric == 'consumption':
                    return number(study['scores'][*state, 'active', 'updated'], 'total_consumption_per_member') - number(study['scores'][*state, other, 'updated'], 'total_consumption_per_member')
                return number(study['contrasts'][*state, 'active_minus_' + other], metric)
            for sid, offset in zip((0, 1, 2, None), (-.21, -.07, .07, .21)):
                result = estimate(arena_values(study, difference, sid), development)
                color, marker = (INK, 'D') if sid is None else (society_color(sid), 'o')
                if not development:
                    ax.plot([result['low'], result['high']], [y + offset] * 2, color=color, lw=1)
                ax.plot(result['mean'], y + offset, color=color, marker=marker, linestyle='', markersize=4.5)
                exported.append({'contrast': 'active_minus_' + other, 'metric': metric,
                                 'society': 'mean' if sid is None else sid, **result})
        ax.set_title(title, loc='left')
        ax.set_yticks([0, 1], ['Active − fixed', 'Active − random'])
        ax.set_ylim(-.5, 1.5)
        ax.axvline(0, color=SECONDARY, ls='--', lw=.8)
        ax.set_xlabel('Difference per member over probe + decision windows', fontsize=9)
        ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        ax.grid(axis='x', alpha=.4)
        ax.set_axisbelow(True)
    fig.text(.05, .12, 'Total updated-policy difference = posterior-update-value difference + frozen-coefficient path difference.',
             fontsize=9.3, color=SECONDARY)
    fig.text(.05, .075, 'Utility = consumption + 0.2 terminal wealth. Investment is already charged through the material ledger; it is not subtracted twice.',
             fontsize=9.1, color=SECONDARY)
    key(fig, y=.013)
    fig.subplots_adjust(left=.16, right=.975, top=.80, bottom=.21, wspace=.45, hspace=.58)
    return save(fig, output / 'experiment-effects'), exported


def opportunity_figure(study, output):
    development = study['design']['bank'] == 'development'
    fig, axes = plt.subplots(2, 2, figsize=(13.3, 8.8))
    heading(fig, 'What does investing the escrow change?',
            ('DEVELOPMENT ONLY · descriptive contrasts against redistributing B' if development else
             'Paired contrasts against redistributing B · this baseline is outside the matched-investment comparison'))
    metrics = [('total_utility', 'Total utility under updated beliefs'),
               ('post_crps_uncapped', 'Held-out prediction error after the probe'),
               ('total_consumption_per_member', 'Consumption over probe + decision windows'),
               ('terminal_wealth_per_member', 'Terminal wealth')]
    exported = []
    for ax, (metric, title) in zip(axes.flat, metrics):
        for y, strategy in enumerate(reversed(STRATEGIES)):
            def difference(state):
                return number(study['scores'][*state, strategy, 'updated'], metric) - number(study['scores'][*state, 'redistribute', 'updated'], metric)
            for sid, offset in zip((0, 1, 2, None), (-.21, -.07, .07, .21)):
                result = estimate(arena_values(study, difference, sid), development)
                color, marker = (INK, 'D') if sid is None else (society_color(sid), 'o')
                if not development:
                    ax.plot([result['low'], result['high']], [y + offset] * 2, color=color, lw=1)
                ax.plot(result['mean'], y + offset, color=color, marker=marker, linestyle='', markersize=4.5)
                exported.append({'contrast': strategy + '_minus_redistribute', 'metric': metric,
                                 'society': 'mean' if sid is None else sid, **result})
        ax.set_title(title, loc='left')
        ax.set_yticks([0, 1, 2], ['Random', 'Fixed', 'Active'])
        ax.set_ylim(-.5, 2.5)
        ax.axvline(0, color=SECONDARY, ls='--', lw=.8)
        ax.set_xlabel('CRPS difference · lower is better' if metric == 'post_crps_uncapped'
                      else 'Difference per member · strategy minus redistribution', fontsize=9)
        ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        ax.grid(axis='x', alpha=.4)
        ax.set_axisbelow(True)
    fig.text(.05, .13, 'Investing and redistributing B create different physical paths. Both use updated beliefs and receive the same reporting opportunities.',
             fontsize=9.1, color=SECONDARY)
    fig.text(.05, .083, 'These contrasts include both material and learning effects. Better prediction or more terminal wealth need not increase consumption.',
             fontsize=9.1, color=SECONDARY)
    key(fig, y=.014)
    fig.subplots_adjust(left=.105, right=.975, top=.80, bottom=.22, wspace=.35, hspace=.58)
    return save(fig, output / 'experiment-opportunity-cost'), exported


CAPTIONS = {
    'experiment-selection': 'Recorded experiment choices and acquisition diagnostics. Active selection maximizes a joint Gaussian moment information proxy; fixed selects Split; random makes a precommitted uniform choice. These scores are not exact expected information gain or decision value. Early, Late and Split invest the same reserved resources and use identical reporting opportunities. In development, filled markers identify the active choice and the right panel shows downstream updated-minus-frozen utility on each identical physical path. Development cases are designed states and have no population confidence intervals. In evaluation, bars describe dependent focal choices clustered within independent arenas.',
    'experiment-effects': 'The primary contrast is active minus random in the value of posterior updating. Within each physical path, the updated and frozen-coefficient planners receive the same latest legal state; their comparison withholds coefficient updates, not all new information. Total updated-policy utility differences decompose exactly into this update-value difference and the difference under frozen coefficients. Across schedules, information value can interact with different material states. Black diamonds average focal societies within arena; society colors preserve identities. Evaluation intervals use 2,000 paired whole-arena bootstrap draws with seed 9501. Development shows descriptive means only. Secondary intervals have no multiplicity adjustment. Consumption and terminal wealth are distinct; utility includes both.',
    'experiment-opportunity-cost': 'Opportunity-cost comparison against redistributing the escrow at the first probe tick without investing it. All displayed planners use updated beliefs. This baseline spends zero on probe investment and is outside the equal-investment Active/Fixed/Random comparison. Contrasts include changes in both material paths and subsequent learning. Held-out CRPS uses the common uncapped queries and lower values indicate better predictions. Utility, consumption and terminal wealth retain distinct meanings. Evaluation intervals resample whole independent arenas after averaging focal societies; designed development cases show descriptive means without intervals. All secondary intervals are unadjusted.',
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'evidence/world-model-experiment-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'figures/world-model-experiment-v1')
    args = parser.parse_args(argv)
    study = load(args.source)
    args.output.mkdir(parents=True, exist_ok=True)
    theme()
    files = selection_figure(study, args.output)
    images, rows = effects_figure(study, args.output)
    files.extend(images)
    images, opportunity_rows = opportunity_figure(study, args.output)
    files.extend(images)
    rows.extend(opportunity_rows)
    table = args.output / 'paired-estimates.csv'
    with table.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    files.append(table)
    development = study['design']['bank'] == 'development'
    endpoints = []
    for condition in study['summary']['conditions']:
        for metric, value in condition['metrics'].items():
            row = {'strategy': condition['strategy'], 'belief': condition['belief'],
                   'metric': metric, 'mean': value['mean'], 'n_arenas': len(study['arenas'])}
            if not development:
                row.update(low=value['ci95'][0], high=value['ci95'][1])
            endpoints.append(row)
    endpoint_table = args.output / 'absolute-endpoints.csv'
    with endpoint_table.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(endpoints[0]))
        writer.writeheader()
        writer.writerows(endpoints)
    files.append(endpoint_table)
    lines = ['# Costed investment experiments', '',
             f"Bank: **{study['design']['bank']}**. Arenas: **{len(study['arenas'])}**. Three dependent focal societies per arena. Zero evolutionary runs or model-generation calls.", '',
             'Recorded-data Chromatic Field figures. Rendering runs no learning, acquisition selection or physical evaluation.', '']
    if development:
        lines += [f"Development gate **{'passed' if study['gate']['passed'] else 'failed'}**. These designed cases are separate from prospective evaluation.", '']
    for name, caption in CAPTIONS.items():
        lines += [f'## {name}', '', f'[SVG]({name}.svg) · [PDF]({name}.pdf) · [PNG]({name}.png)', '', caption, '']
    lines += ['[Paired estimates](paired-estimates.csv) · [Absolute endpoints](absolute-endpoints.csv) · [Source/output hashes](manifest.json)', '',
              'Prediction and communication metrics describe the underlying probe path and repeat across downstream belief rows. Post-probe CRPS scores the updated institutional learner; it is not a new frozen- or known-coefficient prediction score. Repeated metrics are not additional observations.', '',
              'The renderer checks artifact hashes, complete grids, selected-path identities, matched investment and traffic, utility primitives, the exact contrast decomposition and independently recomputed summary means/intervals. The redistribution opportunity baseline is outside the matched-investment comparison.', '']
    readme = args.output / 'README.md'
    readme.write_text('\n'.join(lines))
    files.append(readme)
    sources = [args.source / name for name in (*TABLES, 'design.json', 'design.sha256', 'completion.json', 'summary.json')]
    if development:
        sources.append(args.source / 'gate.json')
    sources += [Path(__file__), ROOT / 'swarm_societies/visualize.py', ROOT / 'docs/visual-reference.md']
    def portable(path):
        path = path.resolve()
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    manifest = {'renderer_version': VERSION, 'style': STYLE, 'bank': study['design']['bank'],
                'arenas': len(study['arenas']), 'designed_development_cases': development,
                'bootstrap_intervals_displayed': not development,
                'rendering_runs_training': False, 'rendering_runs_evaluation': False,
                'captions': CAPTIONS, 'sources': {portable(p): digest(p) for p in sources},
                'artifacts': {p.name: digest(p) for p in files},
                'software': {'python': platform.python_version(), 'numpy': np.__version__,
                             'matplotlib': matplotlib.__version__}}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'figures': len(CAPTIONS), 'bank': study['design']['bank']}))


if __name__ == '__main__':
    main()
