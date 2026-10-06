#!/usr/bin/env python3
"""Render completed, recorded allocation decisions in Chromatic Field v1.

Only saved tables and committed forecast records enter these figures. This
module runs no learner, planner, simulator, or evaluation branch.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.visualize import (
    BACKGROUND, INK, MUTED, RULE, SECONDARY, STYLE, digest, save,
    society_color, theme,
)
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np

RENDERER_VERSION = 'world-model-decision-v1-figures-v1'
CONDITIONS = ('prior', 'learned', 'known')
LABELS = {'prior': 'Frozen prior', 'learned': 'Learned belief', 'known': 'Known law'}
SHORT = {'prior': 'Prior', 'learned': 'Learned', 'known': 'Known law'}
MARKERS = {'prior': 'o', 'learned': 's', 'known': '^'}
CONTRASTS = (('learned', 'prior'), ('known', 'prior'), ('learned', 'known'))
MENU = (0., .5, 1.)
BOOTSTRAP_SEED = 9401
BOOTSTRAP_DRAWS = 2000
ENDPOINTS = ('utility', 'consumption_per_member', 'focal_welfare',
             'terminal_wealth_per_member', 'regret', 'shortfall_per_member',
             'investment', 'external_harm', 'other_society_welfare',
             'other_society_utility', 'utility_absolute_error',
             'budget_absolute_error', 'menu_forecast_mae')


def read_csv(path):
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f'Empty recorded table: {path}')
    return rows


def finite(value, label):
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f'Nonfinite recorded {label}')
    return number


def equal(actual, expected, label):
    if not np.isclose(float(actual), float(expected), rtol=1e-10, atol=1e-12):
        raise ValueError(f'Recorded arithmetic disagrees: {label}')


def require_grid(rows, keys, expected, label):
    actual = Counter(tuple(str(row[key]) for key in keys) for row in rows)
    if set(actual) != expected or any(count != 1 for count in actual.values()):
        raise ValueError(f'Incomplete or duplicate {label} grid')


def bootstrap(values):
    values = np.asarray(values, dtype=float)
    valid = int(np.isfinite(values).sum())
    if valid != len(values):
        return {'mean': None, 'ci95': None,
                'n_arenas': len(values), 'valid_arenas': valid}
    indices = np.random.default_rng(BOOTSTRAP_SEED).integers(
        0, len(values), size=(BOOTSTRAP_DRAWS, len(values)))
    low, high = np.quantile(values[indices].mean(axis=1), [.025, .975])
    return {'mean': float(values.mean()), 'ci95': [float(low), float(high)],
            'n_arenas': len(values), 'valid_arenas': valid}


def check_estimate(saved, actual, label):
    for key in ('n_arenas', 'valid_arenas'):
        if saved[key] != actual[key]:
            raise ValueError(f'Summary count disagrees: {label}/{key}')
    if actual['mean'] is None:
        if saved['mean'] is not None or saved['ci95'] is not None:
            raise ValueError(f'Incomplete panel has an estimate: {label}')
    else:
        for left, right in zip([saved['mean'], *saved['ci95']],
                               [actual['mean'], *actual['ci95']]):
            equal(left, right, label)


def arena_values(study, condition, metric, society=None):
    societies = study['societies'] if society is None else [society]
    result = []
    for arena in study['arenas']:
        rows = [study['score_index'][arena, sid, condition] for sid in societies]
        if any(row['status'] != 'ok' for row in rows):
            result.append(np.nan)
        else:
            result.append(np.mean([finite(row[metric], metric) for row in rows]))
    return np.asarray(result)


def load_study(source):
    design = json.loads((source / 'design.json').read_text())
    if digest(source / 'design.json') != (source / 'design.sha256').read_text().strip():
        raise ValueError('Decision design checksum mismatch')
    completion = json.loads((source / 'completion.json').read_text())
    required = ['design.json', 'scores.csv', 'branches.csv', 'arenas.csv', 'summary.json']
    required.extend(f"cases/{case['arena_id']}/case.json.gz" for case in design['cases'])
    for name in required:
        if name not in completion['artifact_hashes'] or digest(source / name) != completion['artifact_hashes'][name]:
            raise ValueError(f'Recorded decision artifact hash mismatch: {name}')
    if tuple(design['conditions']) != CONDITIONS:
        raise ValueError('Declare visual encodings before changing conditions')
    if design['bootstrap'] != {'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED, 'level': .95}:
        raise ValueError('Figure bootstrap differs from frozen design')
    scores, branches, aggregated = (read_csv(source / name) for name in required[1:4])
    arenas = sorted(case['arena_id'] for case in design['cases'])
    societies = list(range(3))
    require_grid(scores, ('arena_id', 'focal', 'condition'),
                 {(arena, str(sid), condition) for arena in arenas
                  for sid in societies for condition in CONDITIONS}, 'decision score')
    require_grid(branches, ('arena_id', 'focal', 'public_fraction'),
                 {(arena, str(sid), str(action)) for arena in arenas
                  for sid in societies for action in MENU}, 'evaluation branch')
    require_grid(aggregated, ('arena_id', 'condition'),
                 {(arena, condition) for arena in arenas for condition in CONDITIONS}, 'arena')
    score_index = {(row['arena_id'], int(row['focal']), row['condition']): row for row in scores}
    branch_index = {(row['arena_id'], int(row['focal']), float(row['public_fraction'])): row
                    for row in branches}
    summary = json.loads((source / 'summary.json').read_text())
    study = {'design': design, 'summary': summary, 'scores': scores, 'branches': branches,
             'aggregated': aggregated, 'score_index': score_index, 'branch_index': branch_index,
             'arenas': arenas, 'societies': societies, 'n_arenas': len(arenas),
             'horizon': design['horizon'], 'inputs': [source / name for name in required],
             'failed_plans': sum(row['status'] != 'ok' for row in scores)}
    forecast_index = {}
    for arena in arenas:
        with gzip.open(source / f'cases/{arena}/case.json.gz', 'rt') as handle:
            case = json.load(handle)
        for forecast in case['forecasts']:
            identity = (arena, int(forecast['focal']), forecast['condition'])
            if identity in forecast_index:
                raise ValueError('Duplicate committed forecast identity')
            forecast_index[identity] = forecast
    if set(forecast_index) != set(score_index):
        raise ValueError('Committed forecasts do not cover decision scores')
    study['forecast_index'] = forecast_index
    for key, row in score_index.items():
        forecast = forecast_index[key]
        if row['status'] != forecast['status']:
            raise ValueError('Forecast status disagrees with score')
        if row['status'] != 'ok':
            continue
        action = finite(row['action'], 'chosen action')
        if action not in MENU:
            raise ValueError('Chosen action outside frozen menu')
        actual = branch_index[key[0], key[1], action]
        for metric in ENDPOINTS[:10]:
            if metric == 'regret':
                continue
            equal(row[metric], actual[metric], 'chosen branch ' + metric)
        equal(row['utility'], float(row['consumption_per_member']) +
              .2 * float(row['terminal_wealth_per_member']), 'private utility')
        equal(row['focal_welfare'], design['config']['consumption_need'] -
              1.5 * float(row['shortfall_per_member']) / study['horizon'], 'welfare decomposition')
        best = max(float(branch_index[key[0], key[1], option]['utility']) for option in MENU)
        equal(row['regret'], best - float(row['utility']), 'finite menu regret')
        equal(row['actual_budget'], actual['initial_budget'], 'eventual budget')
        options = {float(option['public_fraction']): option for option in forecast['actions']}
        if set(options) != set(MENU):
            raise ValueError('Committed forecast menu differs from branch menu')
        equal(row['forecast_utility'], options[action]['utility'], 'committed utility')
        equal(row['forecast_budget'], options[action]['initial_budget'], 'committed budget')
        equal(row['utility_prediction_error'], float(row['forecast_utility']) -
              float(row['utility']), 'utility forecast error')
        equal(row['budget_prediction_error'], float(row['forecast_budget']) -
              float(row['actual_budget']), 'budget forecast error')
        row['investment_advantage_actual'] = (
            float(branch_index[key[0], key[1], 1.]['utility']) -
            float(branch_index[key[0], key[1], 0.]['utility']))
        row['investment_advantage_forecast'] = options[1.]['utility'] - options[0.]['utility']
        row['investment_advantage_absolute_error'] = abs(
            row['investment_advantage_forecast'] - row['investment_advantage_actual'])
    for saved in summary['conditions']:
        for metric, estimate in saved['metrics'].items():
            check_estimate(estimate, bootstrap(arena_values(study, saved['condition'], metric)),
                           saved['condition'] + '/' + metric)
    for saved in summary['paired_contrasts']:
        for metric, estimate in saved['metrics'].items():
            values = (arena_values(study, saved['left'], metric) -
                      arena_values(study, saved['right'], metric))
            check_estimate(estimate, bootstrap(values), saved['contrast'] + '/' + metric)
    primary = bootstrap(arena_values(study, 'learned', 'utility') -
                        arena_values(study, 'prior', 'utility'))
    check_estimate(summary['primary'], primary, 'primary endpoint')
    for row in aggregated:
        for metric in summary['conditions'][0]['metrics']:
            values = arena_values(study, row['condition'], metric)
            value = values[arenas.index(row['arena_id'])]
            if np.isfinite(value):
                equal(row[metric], value, 'arena aggregate ' + metric)
    return study


def heading(fig, title, subtitle):
    fig.text(.055, .97, title, fontsize=18, weight='bold', va='top')
    fig.text(.055, .91, subtitle, fontsize=10.2, color=SECONDARY, va='top')


def interval(ax, estimate, position, *, color=INK, marker='o', horizontal=True):
    if estimate['mean'] is None:
        return
    mean, (low, high) = estimate['mean'], estimate['ci95']
    if horizontal:
        ax.plot([low, high], [position, position], color=color, linewidth=1.2)
        ax.plot(mean, position, marker=marker, color=color, linestyle='', markersize=4.5)
    else:
        ax.plot([position, position], [low, high], color=color, linewidth=1.2)
        ax.plot(position, mean, marker=marker, color=color, linestyle='', markersize=4.5)


def society_legend(fig, *, bottom=.025, overall=True):
    handles = [Line2D([], [], marker='o', linestyle='', color=society_color(sid),
                      label=f'Society {sid}') for sid in range(3)]
    if overall:
        handles.append(Line2D([], [], marker='D', linestyle='', color=INK,
                              label='Mean of three focal societies'))
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, bottom),
               ncol=len(handles), fontsize=9.2)


def effects_figure(study, output):
    fig, axes = plt.subplots(2, 2, figsize=(13.1, 8.7))
    heading(fig, 'What changes when the allocation planner learns?',
            'Paired decision outcomes · identical planner and legal inputs · learned belief, frozen prior, known coefficients')
    metrics = [('utility', 'Private utility · primary endpoint', 'Difference per member over the decision window'),
               ('consumption_per_member', 'Consumption', 'Difference in units consumed per member'),
               ('focal_welfare', 'Mean material welfare', 'Difference per member per tick'),
               ('terminal_wealth_per_member', 'Terminal wealth', 'Difference in remaining wealth per member')]
    for ax, (metric, title, label) in zip(axes.flat, metrics):
        for index, (left, right) in enumerate(CONTRASTS):
            base = 2 - index
            for sid, offset in zip(study['societies'], (-.21, -.07, .07)):
                difference = (arena_values(study, left, metric, sid) -
                              arena_values(study, right, metric, sid))
                interval(ax, bootstrap(difference), base + offset, color=society_color(sid))
            difference = arena_values(study, left, metric) - arena_values(study, right, metric)
            interval(ax, bootstrap(difference), base + .21, marker='D')
        ax.axvline(0, color=SECONDARY, linewidth=.85, linestyle='--')
        ax.set_yticks([2, 1, 0], ['Learned − prior', 'Known law − prior', 'Learned − known law'])
        ax.set_ylim(-.52, 2.52)
        ax.set_title(title, loc='left')
        ax.set_xlabel(label, fontsize=9.2)
        ax.grid(axis='x', alpha=.5)
        ax.set_axisbelow(True)
        ax.ticklabel_format(axis='x', style='plain', useOffset=False)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    fig.text(.055, .135,
             f"{study['n_arenas']} independent arenas; three focal societies averaged within arena. Bars: 95% paired arena intervals.",
             fontsize=9.4, color=SECONDARY)
    fig.text(.055, .092,
             'Private utility = window consumption + 0.2 terminal wealth. A utility gain need not imply more consumption or welfare.',
             fontsize=9.2, color=SECONDARY)
    society_legend(fig)
    fig.subplots_adjust(left=.175, right=.97, top=.80, bottom=.23, wspace=.57, hspace=.55)
    return save(fig, output / 'paired-decision-effects')


def choices_figure(study, output):
    fig, axes = plt.subplots(1, 4, figsize=(14.6, 6.2),
                             gridspec_kw={'width_ratios': [1, 1, 1, 1.55]})
    heading(fig, 'Allocation choices and regret within the fixed menu',
            'One public-investment fraction per focal decision · subsequent public investment is fixed at zero')
    fills, hatches = (BACKGROUND, MUTED, SECONDARY), ('', '///', '')
    for sid, ax in zip(study['societies'], axes[:3]):
        bottoms = np.zeros(len(CONDITIONS))
        for action, fill, hatch in zip(MENU, fills, hatches):
            percentages = [100 * sum(row['status'] == 'ok' and float(row['action']) == action
                          for row in study['scores'] if int(row['focal']) == sid and
                          row['condition'] == condition) / study['n_arenas'] for condition in CONDITIONS]
            ax.bar(range(3), percentages, bottom=bottoms, width=.68, color=fill,
                   edgecolor=SECONDARY, linewidth=.8, hatch=hatch)
            bottoms += percentages
        if study['failed_plans']:
            ax.bar(range(3), 100 - bottoms, bottom=bottoms, width=.68,
                   color=BACKGROUND, edgecolor=INK, linewidth=.8, hatch='xxx')
        ax.set_title(f'Society {sid}', color=society_color(sid), loc='left')
        ax.set_xticks(range(3), [SHORT[c] for c in CONDITIONS], rotation=22, ha='right')
        ax.set_ylim(0, 100)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.grid(axis='y', alpha=.4)
        ax.set_axisbelow(True)
    axes[0].set_ylabel('Share of focal decisions (%)')
    ax = axes[3]
    for condition_index, condition in enumerate(CONDITIONS):
        for sid, offset in zip(study['societies'], (-.21, -.07, .07)):
            interval(ax, bootstrap(arena_values(study, condition, 'regret', sid)),
                     condition_index + offset, color=society_color(sid), horizontal=False)
        interval(ax, bootstrap(arena_values(study, condition, 'regret')),
                 condition_index + .21, marker='D', horizontal=False)
    ax.set_title('Realized menu regret', loc='left')
    ax.set_xticks(range(3), [SHORT[c] for c in CONDITIONS], rotation=22, ha='right')
    ax.set_ylabel('Utility forgone per member')
    ax.set_ylim(bottom=0)
    ax.grid(axis='y', alpha=.4)
    ax.set_axisbelow(True)
    action_handles = [Patch(facecolor=fill, edgecolor=SECONDARY, hatch=hatch,
                            label=f'{int(action * 100)}% invested')
                      for action, fill, hatch in zip(MENU, fills, hatches)]
    if study['failed_plans']:
        action_handles.append(Patch(facecolor=BACKGROUND, edgecolor=INK, hatch='xxx', label='Failed plan'))
    fig.legend(handles=action_handles,
               loc='lower left', bbox_to_anchor=(.055, .07), ncol=3, fontsize=9.2)
    fig.text(.055, .20,
             'Regret is relative to the best of three realized paired branches in this finite window; it is not a globally optimal policy.',
             fontsize=9.2, color=SECONDARY)
    fig.text(.055, .158,
             f"Menu: 0%, 50%, 100% invested. Failed plans retained: {study['failed_plans']}. Confidence intervals resample whole arenas.",
             fontsize=9.2, color=SECONDARY)
    society_legend(fig, bottom=.015)
    fig.subplots_adjust(left=.06, right=.97, top=.77, bottom=.36, wspace=.40)
    return save(fig, output / 'choices-and-regret')


def forecasts_figure(study, output):
    fig, axes = plt.subplots(2, 3, figsize=(13.1, 9.1))
    heading(fig, 'Forecasts committed before evaluation',
            'Budget estimates use lagged measurements; action-value contrasts expose decision-relevant forecast errors')
    panels = [('actual_budget', 'forecast_budget', 'Actual allocation budget', 'Forecast allocation budget'),
              ('investment_advantage_actual', 'investment_advantage_forecast',
               'Realized utility: invest all − redistribute', 'Forecast utility: invest all − redistribute')]
    valid = [row for row in study['scores'] if row['status'] == 'ok']
    for row_index, (xkey, ykey, xlabel, ylabel) in enumerate(panels):
        all_values = [float(row[key]) for row in valid for key in (xkey, ykey)]
        if not all_values:
            for ax in axes[row_index]:
                ax.text(.5, .5, 'No valid committed forecasts', ha='center', transform=ax.transAxes)
                ax.set_axis_off()
            continue
        lower, upper = min(all_values), max(all_values)
        padding = max((upper - lower) * .06, .01)
        lower, upper = lower - padding, upper + padding
        for sid, ax in zip(study['societies'], axes[row_index]):
            for condition in CONDITIONS:
                points = [row for row in valid if int(row['focal']) == sid and row['condition'] == condition]
                ax.scatter([float(row[xkey]) for row in points], [float(row[ykey]) for row in points],
                           s=25, marker=MARKERS[condition], alpha=.72,
                           edgecolors=society_color(sid), linewidths=.85,
                           facecolors='none' if condition == 'learned' else society_color(sid))
            ax.plot([lower, upper], [lower, upper], color=SECONDARY, linewidth=.9, linestyle='--')
            if row_index:
                ax.axhline(0, color=RULE, linewidth=.7)
                ax.axvline(0, color=RULE, linewidth=.7)
            ax.set_xlim(lower, upper)
            ax.set_ylim(lower, upper)
            ax.set_xlabel(xlabel, fontsize=9.2)
            if sid == 0:
                ax.set_ylabel(ylabel, fontsize=9.4)
            if row_index == 0:
                ax.set_title(f'Society {sid}', color=society_color(sid), loc='left')
            ax.grid(alpha=.3)
            ax.set_axisbelow(True)
    fig.text(.055, .115,
             'Each point is one arena, focal society and belief condition. Repeated branches and forecasts are dependent observations.',
             fontsize=9.2, color=SECONDARY)
    fig.text(.055, .078,
             'Dashed line: exact agreement. Known coefficients retain the same unit-productivity and external-infrastructure approximations.',
             fontsize=9.1, color=SECONDARY)
    fig.legend(handles=[Line2D([], [], linestyle='', color=SECONDARY, marker=MARKERS[condition],
                              markerfacecolor=BACKGROUND if condition == 'learned' else SECONDARY,
                              label=LABELS[condition]) for condition in CONDITIONS],
               loc='lower center', bbox_to_anchor=(.5, .012), ncol=3, fontsize=9.3)
    fig.subplots_adjust(left=.085, right=.97, top=.805, bottom=.20, wspace=.28, hspace=.38)
    return save(fig, output / 'forecast-diagnostics')


def write_table(path, rows):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def estimate_fields(estimate):
    interval = estimate['ci95'] if estimate['ci95'] is not None else [None, None]
    return {'mean': estimate['mean'], 'lo95': interval[0], 'hi95': interval[1],
            'n_arenas': estimate['n_arenas'], 'valid_arenas': estimate['valid_arenas']}


def export_tables(study, output):
    endpoints, contrasts, choices, forecasts = [], [], [], []
    for society in (None, *study['societies']):
        identity = {'society': 'all' if society is None else society, 'unit': 'independent_arena'}
        for condition in CONDITIONS:
            for metric in ENDPOINTS:
                endpoints.append({**identity, 'condition': condition, 'metric': metric,
                                  **estimate_fields(bootstrap(arena_values(study, condition, metric, society)))})
            for metric in ('budget_absolute_error', 'utility_absolute_error', 'menu_forecast_mae',
                           'investment_advantage_absolute_error'):
                forecasts.append({**identity, 'condition': condition, 'metric': metric,
                                  **estimate_fields(bootstrap(arena_values(study, condition, metric, society)))})
            selected = [row for row in study['scores'] if row['condition'] == condition and
                        (society is None or int(row['focal']) == society)]
            for action in MENU:
                count = sum(row['status'] == 'ok' and float(row['action']) == action for row in selected)
                choices.append({**identity, 'condition': condition, 'public_fraction': action,
                                'decisions': count, 'total_including_failed': len(selected),
                                'fraction': count / len(selected),
                                'failed_plans': sum(row['status'] != 'ok' for row in selected)})
        for left, right in CONTRASTS:
            for metric in ENDPOINTS:
                values = arena_values(study, left, metric, society) - arena_values(study, right, metric, society)
                contrasts.append({**identity, 'contrast': left + '_minus_' + right, 'metric': metric,
                                  **estimate_fields(bootstrap(values))})
    return [write_table(output / name, rows) for name, rows in (
        ('endpoint-statistics.csv', endpoints), ('paired-contrasts.csv', contrasts),
        ('choice-counts.csv', choices), ('forecast-statistics.csv', forecasts))]


CAPTIONS = {
    'paired-decision-effects':
        'Paired realized outcome differences under the same fixed allocation planner supplied with a frozen prior, '
        'a learned institutional posterior, or known coefficients. Black diamonds average the three focal societies '
        'within each arena; colors retain society identity. Lines are 95% percentile intervals from 2,000 whole-arena '
        'bootstrap draws with seed 9401. The primary contrast is learned minus prior private utility per member, '
        'defined as decision-window consumption plus 0.2 terminal wealth. Consumption and terminal wealth are '
        'reported separately. Mean welfare is consumption minus half unmet need per member per tick; its contrast '
        'is a rescaling of consumption here, not an independent endpoint. Secondary intervals are descriptive and '
        'have no familywise multiplicity adjustment. Known coefficients do not reveal hidden state or future weather.',
    'choices-and-regret':
        'Recorded choices from the fixed public-investment menu of 0, 0.5 and 1. Stacked bars use neutral fills '
        'and hatching for allocation fractions; society titles retain the established colors. Regret is the highest '
        'realized utility among three paired evaluator branches minus utility of the chosen branch, within the '
        'declared 32-tick window and fixed subsequent policy. This realized finite-menu benchmark uses the sampled '
        'future trajectory and is not an expected-value optimum, full-state oracle or globally optimal policy. '
        'Regret marks and intervals retain arena-level replication; focal rotations and menu branches are nested '
        'observations. All attempted plans remain in choice denominators.',
    'forecast-diagnostics':
        'Top: committed forecast of eventual institutional allocation budget versus its realized post-harvest '
        'value. Bottom: committed forecast utility difference between investing all and redistributing all versus '
        'the realized paired branch difference. Points show each recorded arena/focal/condition combination, not '
        'independent replications. Conditions use marker shapes and societies use fixed colors. The diagonal '
        'denotes exact agreement. Every planner receives the same legal current institution observation and '
        'one-tick-lagged home measurement, assumes unit member productivity, reconstructs previous terminal stock '
        'from noisy growth, and forecasts external infrastructure by decay only. The known-law condition retains '
        'these approximations. Future weather, RNG state, realized current taxes and branch outcomes enter no forecast.',
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'evidence/world-model-decision-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'figures/world-model-decision-v1')
    args = parser.parse_args(argv)
    study = load_study(args.source)
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    files = export_tables(study, args.output)
    for renderer in (effects_figure, choices_figure, forecasts_figure):
        files.extend(renderer(study, args.output))
    readme = args.output / 'README.md'
    lines = ['# Fixed-planner allocation decisions', '',
             'Recorded-data figures in Chromatic Field v1. No renderer operation trains a model, selects an action or evaluates a branch.', '',
             f"Bank: **{study['design']['bank']}**. Independent arenas: **{study['n_arenas']}**. Focal societies per arena: **3**. "
             f"Decision horizon: **{study['horizon']} ticks**. Failed plans: **{study['failed_plans']}**. Independent evolutionary runs and model-generation calls: **0**.", '',
             'Societies retain cobalt, magenta and orange. Conditions use labels and neutral marker shapes. Whole independent arenas are resampled after averaging the three dependent focal decisions.', '']
    for name, caption in CAPTIONS.items():
        lines.extend([f'## {name}', '', f'[SVG]({name}.svg) · [PDF]({name}.pdf) · [PNG]({name}.png)', '', caption, ''])
    lines.extend(['## Tables and provenance', '',
                  '[Absolute endpoints](endpoint-statistics.csv) · [Paired differences](paired-contrasts.csv) · '
                  '[Choice counts](choice-counts.csv) · [Forecast errors](forecast-statistics.csv) · [Source/output hashes](manifest.json)', '',
                  'All interval tables use 2,000 percentile bootstrap draws with seed 9401. The primary endpoint is learned-minus-prior '
                  'private utility. Welfare, consumption, terminal wealth, spillovers and forecast errors remain separate. A gain in '
                  'terminal wealth does not by itself establish improved consumption, welfare, inference efficiency or governance.', '',
                  'The renderer checks completion-manifest input hashes, complete decision/branch grids, chosen-branch accounting, '
                  'forecast links, finite-menu regret, and independently recomputed whole-arena statistics against the saved summary. '
                  'Development exploration and the action-ranking gate are not pooled into these evaluation figures.', '',
                  '```bash', '.venv/bin/python scripts/visualize_world_model_decision.py', '```', ''])
    readme.write_text('\n'.join(lines))
    sources = [*study['inputs'], args.source / 'design.sha256', args.source / 'completion.json',
               Path(__file__), ROOT / 'swarm_societies/visualize.py', ROOT / 'docs/visual-reference.md']
    def portable(path):
        path = path.resolve()
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    manifest = {'schema_version': 1, 'renderer_version': RENDERER_VERSION, 'style': STYLE,
                'study': 'world-model-decision-v1', 'bank': study['design']['bank'],
                'independent_arenas': study['n_arenas'], 'focal_societies_per_arena': 3,
                'bootstrap': {'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED, 'level': .95,
                              'unit': 'independent arena', 'contrasts': 'paired arena differences'},
                'rendering_runs_training': False, 'rendering_runs_evaluation': False,
                'independent_evolutionary_runs': 0, 'model_generation_calls': 0,
                'captions': CAPTIONS, 'sources': {portable(path): digest(path) for path in sources},
                'software': {'python': platform.python_version(), 'matplotlib': matplotlib.__version__,
                             'numpy': np.__version__},
                'artifacts': {path.name: digest(path) for path in [*files, readme]}}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'output': str(args.output), 'figures': len(CAPTIONS),
                      'tables': 4, 'independent_arenas': study['n_arenas']}))


if __name__ == '__main__':
    main()
