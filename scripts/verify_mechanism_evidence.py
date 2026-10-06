#!/usr/bin/env python3
"""Audit every published mechanism-v1 summary against the frozen design and rows."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.evaluate_consumption_study import aggregate
from scripts.run_mechanism_study import (
    LABELS, PANELS, case_key, describe_contrasts, factorial_rows, verify_inputs,
)
from swarm_societies.consumption_evaluation import file_hash
from swarm_societies.evaluation import ROOT, atomic_json, read_json


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(directory):
    directory = Path(directory).resolve()
    manifest = verify_inputs(directory)
    manifest_sha = file_hash(directory/'manifest.json')
    cases = {case['id']: case for case in manifest['cases']}
    require(len(cases) == len(manifest['cases']), 'Duplicate manifest scenario')
    expected = {(case, panel, focal) for case in cases for panel in PANELS
                for focal in manifest['focal_societies']}
    require(len(expected) == manifest['n_cases_per_population'], 'Manifest case count mismatch')
    require(manifest['n_rollouts_total'] == 2*len(expected)*len(LABELS), 'Manifest rollout count mismatch')
    populations, expected_results = {}, []
    for label in LABELS:
        data = read_json(directory/f'{label}.json')
        require(data['label'] == label, 'Condition label mismatch')
        require(data['manifest_sha256'] == manifest_sha, 'Condition manifest hash mismatch')
        rows = data['rows']
        require(len(rows) == len(expected) and {case_key(row) for row in rows} == expected,
                'Missing, duplicate, or unexpected factorial case')
        for row in rows:
            case = cases[row['case']['id']]
            require(row['case'] == case, 'Raw scenario differs from frozen manifest')
            require(row['drought']['pre_welfare'] == row['no_drought']['pre_welfare'],
                    'Pre-disturbance pairing mismatch')
            for phase in ('drought', 'no_drought'):
                metric = row[phase]
                require(all(math.isfinite(value) for value in metric.values() if isinstance(value, (float, int))),
                        'Nonfinite case metric')
                require(abs(metric['ledger_residual']) < 1e-7, 'Material conservation mismatch')
                need = case['config']['consumption_need']
                require(abs(metric['welfare'] - (need - 1.5*metric['shortfall_per_member_tick'])) < 1e-12,
                        'Welfare primitive identity mismatch')
                require(abs(metric['consumption_per_member_tick'] + metric['shortfall_per_member_tick'] - need) < 1e-12,
                        'Consumption primitive identity mismatch')
                members = metric['members']
                require(len(members) == case['config']['members_per_society'] and
                        {m['member_id'] for m in members} == set(range(case['config']['members_per_society'])) and
                        all(m['society_id'] == row['focal'] for m in members), 'Member coverage mismatch')
            for name, metric in [('drought_welfare_effect', 'welfare'), ('drought_post_welfare_effect', 'post_welfare')]:
                require(row[name] == row['drought'][metric] - row['no_drought'][metric], 'Disturbance effect mismatch')
        expected_summary = aggregate(rows)
        require(data['summary'] == expected_summary, 'Condition summary mismatch')
        populations[label] = rows
        expected_results.append({'label': label, **expected_summary})

    summary = read_json(directory/'summary.json')
    require(summary['manifest_sha256'] == manifest_sha, 'Top-level manifest hash mismatch')
    require(summary['results'] == expected_results, 'Top-level results mismatch')
    require(summary['n_rollouts_total'] == manifest['n_rollouts_total'] == sum(r['n_rollouts'] for r in expected_results),
            'Top-level rollout total mismatch')
    for key in ('study', 'source_replicates', 'interpretation', 'bootstrap', 'analysis_note'):
        require(summary[key] == manifest[key], f'Top-level metadata mismatch: {key}')
    contrast_file = read_json(directory/'contrasts.json')
    require(contrast_file['manifest_sha256'] == manifest_sha, 'Contrast manifest hash mismatch')
    contrasts = factorial_rows(populations, manifest)
    require(contrast_file['rows'] == contrasts, 'Per-case contrast mismatch')
    require(summary['contrasts'] == describe_contrasts(contrasts, manifest), 'Contrast summary mismatch')
    for focal in manifest['unchanged_institution_societies']:
        for left, right in [('initial', 'institutions_only'), ('members_only', 'coevolution')]:
            a = {case_key(row): row for row in populations[left] if row['focal'] == focal}
            b = {case_key(row): row for row in populations[right] if row['focal'] == focal}
            require(a == b, 'Unchanged-institution negative control mismatch')
    receipt = read_json(directory/'verification.json')
    require(receipt['manifest_sha256'] == manifest_sha, 'Original receipt manifest hash mismatch')
    require(receipt['n_rollouts'] == manifest['n_rollouts_total'], 'Original receipt rollout count mismatch')
    require(receipt['status'] == 'passed', 'Original receipt did not pass')
    for label in LABELS:
        require(receipt['data_sha256'][f'{label}.json'] == file_hash(directory/f'{label}.json'), 'Original raw data checksum mismatch')
    files = ['manifest.json', 'summary.json', 'contrasts.json', 'verification.json'] + [f'{label}.json' for label in LABELS]
    return {'status': 'passed', 'checked_utc': datetime.now(timezone.utc).isoformat(),
            'verifier_sha256': file_hash(__file__), 'manifest_sha256': manifest_sha,
            'n_cases_per_population': len(expected), 'n_rollouts': manifest['n_rollouts_total'],
            'checks': ['frozen source and portable program checksums', 'complete factorial case coverage',
                       'every raw scenario equals its frozen definition', 'member coverage and finite metrics',
                       'consumption identities and material conservation', 'exact disturbance-pair differences',
                       'condition and top-level summaries reproduce case rows',
                       'all manifest references and rollout counts', 'paired contrasts and cluster intervals',
                       'unchanged-institution negative control', 'original raw data checksums'],
            'file_sha256': {name: file_hash(directory/name) for name in files}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT/'evidence/mechanism-v1')
    parser.add_argument('--write-receipt', action='store_true')
    args = parser.parse_args()
    result = verify(args.evidence)
    if args.write_receipt:
        atomic_json(args.evidence/'evidence-audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
