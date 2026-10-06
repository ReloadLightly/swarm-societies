#!/usr/bin/env python3
"""Freeze and evaluate a post-hoc 2 × 2 transplant of one evolved lineage.

No search or inference occurs. The original v2 simulator and selected population
are immutable. New environment seeds diagnose mechanisms conditional on that
population; they do not replicate the evolutionary procedure.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_consumption_study import aggregate, case_metrics
from swarm_societies.consumption_evaluation import file_hash, verify_frozen_sources
from swarm_societies.ecology_consumption_v2 import EcologyConfig
from swarm_societies.evaluation import ROOT, atomic_json, read_json


LABELS = ('initial', 'members_only', 'institutions_only', 'coevolution')
PANELS = ('initial', 'cooperative', 'selfish')
METRICS = ('welfare', 'post_welfare', 'shortfall_per_member_tick',
           'outward_harm_per_tick', 'utility_per_tick', 'other_welfare')
FROZEN_FILES = ('scripts/run_mechanism_study.py', 'scripts/evaluate_consumption_study.py',
                'swarm_societies/ecology_consumption_v2.py',
                'swarm_societies/consumption_study.py', 'swarm_societies/candidate.py')


def make_cases():
    """New environment namespace; 12 balanced-marginal timing tuples, not a factorial."""
    rng = random.Random(2026100601)
    horizons, fractions = [48, 60, 72] * 4, [.35, .5, .65] * 4
    rng.shuffle(horizons)
    rng.shuffle(fractions)
    cases = []
    for index, (ticks, fraction) in enumerate(zip(horizons, fractions)):
        payload = f'mechanism-v1/post-hoc-environment/20261006/{index}'.encode()
        # V2 search/fresh seeds are below 2**62; this namespace is disjoint.
        seed = (int.from_bytes(hashlib.sha256(payload).digest()[:8], 'big') & ((1 << 61)-1)) | (1 << 62)
        config = EcologyConfig(n_societies=3, members_per_society=4, ticks=ticks,
                               disturbance_tick=int(ticks*fraction))
        cases.append({'id': f'mechanism-v1-{index:02d}', 'bank': 'post-hoc-diagnostic',
                      'case_index': index, 'seed': seed, 'disturbance_fraction': fraction,
                      'config': asdict(config)})
    return cases


def prepare(directory, context):
    directory, context = Path(directory).resolve(), Path(context).resolve()
    if (directory/'manifest.json').exists():
        raise ValueError('Manifest already exists; evaluate or verify the frozen study')
    state = read_json(context)
    verify_frozen_sources(state)
    if state['condition'] != 'coevolution':
        raise ValueError('Requires the coevolution lineage')
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'programs').mkdir(exist_ok=True)

    def portable(path):
        sha = file_hash(path)
        relative = f'programs/{sha}.py'
        (directory/relative).write_bytes(Path(path).read_bytes())
        return relative

    old_i = [portable(p) for p in state['initial_institutions']]
    old_m = [[portable(p) for p in row] for row in state['initial_members']]
    new_i = [portable(p) for p in state['institutions']]
    new_m = [[portable(p) for p in row] for row in state['members']]
    manifest = {
        'schema_version': 1, 'study': 'mechanism-v1',
        'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'design': 'Post-hoc 2x2 member/institution transplant, frozen before these outcomes',
        'interpretation': 'Conditional effects of one selected coevolution lineage; not independent search replication',
        'source_context_sha256': file_hash(context),
        'source_context_reference': 'runs/consumption-v2/pair-01-coevolution/evolution_context.json',
        'source_replicates': 1, 'inference_calls': 0,
        'source_hashes': {name: file_hash(ROOT/name) for name in FROZEN_FILES},
        'populations': {
            'initial': {'institutions': old_i, 'members': old_m},
            'members_only': {'institutions': old_i, 'members': new_m},
            'institutions_only': {'institutions': new_i, 'members': old_m},
            'coevolution': {'institutions': new_i, 'members': new_m}},
        'cases': make_cases(), 'opponent_panels': list(PANELS), 'focal_societies': [0, 1, 2],
        'disturbance_interventions': [True, False],
        'n_cases_per_population': 108, 'n_rollouts_total': 864,
        'contrasts': {
            'members_at_initial_institutions': {'members_only': 1, 'initial': -1},
            'members_at_evolved_institutions': {'coevolution': 1, 'institutions_only': -1},
            'institutions_at_initial_members': {'institutions_only': 1, 'initial': -1},
            'institutions_at_evolved_members': {'coevolution': 1, 'members_only': -1},
            'interaction': {'coevolution': 1, 'members_only': -1, 'institutions_only': -1, 'initial': 1}},
        'bootstrap': {'unit': 'environment seed including all panels/focal identities',
                      'resamples': 5000, 'seed': 2026100602,
                      'meaning': 'Descriptive environmental uncertainty conditional on this lineage'},
        'unchanged_institution_societies': [i for i in range(3) if old_i[i] == new_i[i]],
        'analysis_note': 'Consumption welfare equals 0.85 minus 1.5 times shortfall/member/tick; these are not independent endpoints.',
    }
    atomic_json(directory/'manifest.json', manifest)
    return manifest


def verify_inputs(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory/'manifest.json')
    for name, sha in manifest['source_hashes'].items():
        if file_hash(ROOT/name) != sha:
            raise ValueError(f'Frozen analysis/simulator source changed: {name}')
    for population in manifest['populations'].values():
        paths = population['institutions'] + [p for row in population['members'] for p in row]
        for relative in paths:
            path = Path(relative)
            if path.is_absolute() or '..' in path.parts or file_hash(directory/path) != path.stem:
                raise ValueError(f'Portable source checksum mismatch: {relative}')
    if manifest['cases'] != make_cases():
        raise ValueError('Frozen scenario bank changed')
    return manifest


def case_key(row):
    return row['case']['id'], row['opponents'], row['focal']


def factorial_rows(populations, manifest):
    indexed = {label: {case_key(row): row for row in populations[label]} for label in LABELS}
    keys = set(indexed['initial'])
    for label in LABELS:
        if len(indexed[label]) != len(populations[label]) or set(indexed[label]) != keys:
            raise ValueError('Factorial arms must have identical, unique cases')
    output = []
    for key in sorted(keys):
        baseline = indexed['initial'][key]
        row = {'case_id': key[0], 'seed': baseline['case']['seed'], 'opponents': key[1], 'focal': key[2], 'contrasts': {}}
        for label in LABELS:
            if indexed[label][key]['case'] != baseline['case']:
                raise ValueError('Factorial scenarios differ')
        for contrast, coefficients in manifest['contrasts'].items():
            row['contrasts'][contrast] = {}
            for phase in ('drought', 'no_drought'):
                row['contrasts'][contrast][phase] = {
                    metric: sum(weight*indexed[label][key][phase][metric] for label, weight in coefficients.items())
                    for metric in METRICS}
            row['contrasts'][contrast]['drought_welfare_effect'] = sum(
                weight*indexed[label][key]['drought_welfare_effect'] for label, weight in coefficients.items())
        output.append(row)
    return output


def describe_contrasts(rows, manifest):
    result = []
    seeds = sorted({row['seed'] for row in rows})
    rng = random.Random(manifest['bootstrap']['seed'])
    draws = [[rng.randrange(len(seeds)) for _ in seeds] for _ in range(manifest['bootstrap']['resamples'])]
    for contrast in manifest['contrasts']:
        entry = {'contrast': contrast, 'n_environment_seeds': len(seeds), 'n_cases': len(rows)}
        for phase in ('drought', 'no_drought'):
            entry[phase] = {}
            for metric in METRICS:
                values = [statistics.mean(row['contrasts'][contrast][phase][metric] for row in rows if row['seed'] == seed) for seed in seeds]
                boot = sorted(statistics.mean(values[i] for i in draw) for draw in draws)
                entry[phase][metric] = {'mean_difference': statistics.mean(values),
                    'seed_cluster_bootstrap_95': [boot[int(.025*len(boot))], boot[int(.975*len(boot))]]}
        entry['drought_welfare_effect_difference'] = statistics.mean(row['contrasts'][contrast]['drought_welfare_effect'] for row in rows)
        entry['by_focal'] = {str(focal): {metric: statistics.mean(row['contrasts'][contrast]['drought'][metric] for row in rows if row['focal'] == focal)
                                         for metric in METRICS} for focal in manifest['focal_societies']}
        result.append(entry)
    return result


def evaluate(directory, workers=2):
    directory = Path(directory).resolve()
    manifest = verify_inputs(directory)
    manifest_sha = file_hash(directory/'manifest.json')
    start = time.monotonic()
    populations, summaries = {}, []
    initial = manifest['populations']['initial']

    def resolve(pop):
        return ([str(directory/p) for p in pop['institutions']],
                [[str(directory/p) for p in row] for row in pop['members']])

    initial_i, initial_m = resolve(initial)
    for label in LABELS:
        destination = directory/f'{label}.json'
        if destination.exists():
            saved = read_json(destination)
            if saved['manifest_sha256'] != manifest_sha:
                raise ValueError('Existing results have a different manifest')
            rows = saved['rows']
        else:
            institutions, members = resolve(manifest['populations'][label])
            jobs = [(case, panel, focal, institutions, members, initial_i, initial_m)
                    for case in manifest['cases'] for panel in PANELS for focal in manifest['focal_societies']]
            rows = []
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for index, row in enumerate(pool.map(case_metrics, jobs)):
                    rows.append(row)
                    if (index+1) % 18 == 0:
                        print(f'{label}: {index+1}/{len(jobs)} paired cases', flush=True)
            atomic_json(destination, {'label': label, 'manifest_sha256': manifest_sha,
                                      'summary': aggregate(rows), 'rows': rows})
        populations[label] = rows
        summaries.append({'label': label, **aggregate(rows)})
    contrasts = factorial_rows(populations, manifest)
    atomic_json(directory/'contrasts.json', {'manifest_sha256': manifest_sha, 'rows': contrasts})
    summary = {'study': manifest['study'], 'manifest_sha256': manifest_sha,
               'completed_utc': datetime.now(timezone.utc).isoformat(),
               'elapsed_seconds_this_invocation': time.monotonic()-start,
               'workers': workers, 'n_rollouts_total': sum(r['n_rollouts'] for r in summaries),
               'interpretation': manifest['interpretation'], 'source_replicates': 1,
               'results': summaries, 'contrasts': describe_contrasts(contrasts, manifest),
               'bootstrap': manifest['bootstrap'], 'analysis_note': manifest['analysis_note']}
    atomic_json(directory/'summary.json', summary)
    verify_results(directory)
    return summary


def verify_results(directory):
    directory = Path(directory).resolve()
    manifest = verify_inputs(directory)
    manifest_sha = file_hash(directory/'manifest.json')
    populations = {}
    expected = {(case['id'], panel, focal) for case in manifest['cases'] for panel in PANELS for focal in manifest['focal_societies']}
    for label in LABELS:
        data = read_json(directory/f'{label}.json')
        rows = data['rows']
        if data['manifest_sha256'] != manifest_sha or len(rows) != len(expected) or {case_key(r) for r in rows} != expected:
            raise ValueError('Incomplete or mismatched factorial cases')
        if data['summary'] != aggregate(rows):
            raise ValueError('Summary differs from case rows')
        for row in rows:
            if row['drought']['pre_welfare'] != row['no_drought']['pre_welfare']:
                raise ValueError('Disturbance pair differs before disturbance')
            for phase in ('drought', 'no_drought'):
                if abs(row[phase]['ledger_residual']) > 1e-7:
                    raise ValueError('Material conservation failed')
        populations[label] = rows
    contrasts = factorial_rows(populations, manifest)
    if read_json(directory/'contrasts.json')['rows'] != contrasts:
        raise ValueError('Stored factorial contrasts differ from case rows')
    summary = read_json(directory/'summary.json')
    if summary['contrasts'] != describe_contrasts(contrasts, manifest):
        raise ValueError('Stored contrast summary differs from case rows')
    for focal in manifest['unchanged_institution_societies']:
        for left, right in [('initial', 'institutions_only'), ('members_only', 'coevolution')]:
            for a, b in zip(populations[left], populations[right]):
                if a['focal'] == focal and a != b:
                    raise ValueError('Unchanged focal institution has a non-null effect')
    receipt = {'status': 'passed', 'checked_utc': datetime.now(timezone.utc).isoformat(),
               'n_rollouts': manifest['n_rollouts_total'], 'manifest_sha256': manifest_sha,
               'checks': ['source and scenario hashes', 'portable population references',
                          'complete paired factorial cases', 'exact raw-row summary reproduction',
                          'pre-disturbance matching', 'material conservation',
                          'unchanged-institution negative control'],
               'data_sha256': {f'{label}.json': file_hash(directory/f'{label}.json') for label in LABELS}}
    atomic_json(directory/'verification.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'evaluate', 'verify'))
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/mechanism-v1')
    parser.add_argument('--context', type=Path, default=ROOT/'runs/consumption-v2/pair-01-coevolution/evolution_context.json')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('workers must be positive')
    if args.command == 'prepare':
        result = prepare(args.output, args.context)
        print(f"Frozen {result['n_rollouts_total']} rollouts: {args.output}/manifest.json")
    elif args.command == 'evaluate':
        result = evaluate(args.output, args.workers)
        print(f"Completed {result['n_rollouts_total']} rollouts: {args.output}/summary.json")
    else:
        print(verify_results(args.output))


if __name__ == '__main__':
    main()
