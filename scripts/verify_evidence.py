#!/usr/bin/env python3
"""Verify compact evidence independently of ignored checkpoints or the Shinka DB.

Default: check every archived source, frozen engine/protocol identity, common fresh
cases and means, accepted-update accounting, and exact replay regeneration.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.ecology import EcologyConfig, run_episode
from swarm_societies.experiment import METRICS


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def load(path):
    require(path.is_file(), f'Missing evidence: {path}')
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected, label, tolerance=1e-12):
    require(isinstance(actual, (int, float)) and math.isfinite(actual), f'Nonfinite/missing metric: {label}')
    require(math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance),
            f'Metric mismatch {label}: recorded={actual}, computed={expected}')


def case_key(row):
    return row['seed'], row['opponents'], row['focal']


def verify_evidence(directory, *, repo_root=ROOT, rerun_replay=True, require_final=False):
    directory, repo_root = Path(directory), Path(repo_root)
    summary = load(directory/'summary.json')
    state = load(directory/'final_population.json')
    panel = load(directory/'fresh_cases.json')
    replay = load(directory/'replay.json')
    checks = []
    if require_final:
        require(summary['status'] not in ('running', 'not_started', 'interrupted'),
                'Evidence is an interim snapshot, not completed search evidence')
    sources = list((directory/'programs').glob('*.py'))
    require(bool(sources), 'No archived source programs')
    for source in sources:
        require(len(source.stem) == 64 and sha(source) == source.stem, f'Source checksum mismatch: {source}')
    def resolve(recorded):
        # Never prefer a mutable local run over the compact published source.
        target = directory/'programs'/Path(recorded).name
        require(target.is_file(), f'Unarchived population source: {recorded}')
        require(sha(target) == target.stem, f'Source checksum mismatch: {target}')
        return str(target)
    for key in ('institutions', 'initial_institutions'):
        state[key] = [resolve(path) for path in state[key]]
    for key in ('members', 'initial_members'):
        state[key] = [[resolve(path) for path in row] for row in state[key]]
    checks.append('all archived source checksums and population dependencies')
    frozen_files = {'protocol_sha256':'docs/protocol.md',
                    'simulator_sha256':'swarm_societies/ecology.py',
                    'candidate_runtime_sha256':'swarm_societies/candidate.py'}
    for key, path in frozen_files.items():
        require(key in state, f'Missing frozen identity: {key}')
        require(sha(repo_root/path) == state[key], f'Frozen source changed: {path}')
    checks.append('frozen protocol, simulator, and candidate runtime hashes')

    keys = [case_key(case) for case in panel['cases']]
    require(len(keys) == len(set(keys)), 'Duplicate protected fresh-case keys')
    seed_set = {key[0] for key in keys}
    require(seed_set.isdisjoint(state['search_seeds']), 'Fresh and search environment seeds overlap')
    n = state['config']['n_societies']
    expected_keys = {(seed, opponent, focal) for seed in seed_set
                     for opponent in ('initial','cooperative','selfish') for focal in range(n)}
    require(set(keys) == expected_keys, 'Fresh panel is not the declared crossed design')
    require(len(seed_set) == 12 or not require_final, 'Final first-run evidence requires 12 fresh environment seeds')
    manifest = load(directory/'fresh_manifest.json') if (directory/'fresh_manifest.json').exists() else None
    if manifest:
        for name, reference_hash in manifest['reference_program_hashes'].items():
            require((directory/'programs'/f'{reference_hash}.py').is_file(), f'Missing frozen reference source: {name}')
    rows_by_treatment, summaries = {}, {}
    for key in ('initial_population','fixed_institution','descendant','members_only','institutions_only'):
        path = directory/f'{key}.json'
        if not path.exists():
            continue
        evidence = load(path)
        if manifest:
            require(key in manifest['treatments'], f'Stale treatment artifact: {key}')
            require(evidence.get('fingerprint') == manifest['fingerprints'][key], f'Treatment fingerprint mismatch: {key}')
        rows = evidence['rows']
        actual_keys = [case_key(row) for row in rows]
        require(len(actual_keys) == len(set(actual_keys)), f'Duplicate fresh-case row in {key}')
        require(set(actual_keys) == expected_keys, f'Unpaired or missing fresh cases in {key}')
        recorded = evidence['summary']
        require(recorded['n'] == len(rows), f'Incorrect case count in {key}')
        require(recorded['label'] == evidence['label'], f'Incorrect treatment label in {key}')
        for metric in METRICS:
            expected = statistics.mean(row[metric] for row in rows)
            close(recorded.get(metric), expected, f'{key}.{metric}')
        for row in rows:
            close(row['ledger_residual'], 0., f'{key}.{case_key(row)}.conservation', tolerance=1e-7)
            if 'focal_members' in row:
                require(len(row['focal_members']) == state['config']['members_per_society'], 'Missing focal member outcomes')
                close(row['individual_utility'], statistics.mean(member['utility'] for member in row['focal_members']),
                      f'{key}.{case_key(row)}.individual_utility')
                close(row['shortfall'], sum(member['shortfall'] for member in row['focal_members']),
                      f'{key}.{case_key(row)}.shortfall')
            pre_ticks = state['config']['disturbance_tick']
            post_ticks = state['config']['ticks'] - pre_ticks
            close(row['welfare'], (row['pre_welfare']*pre_ticks+row['post_welfare']*post_ticks)/(pre_ticks+post_ticks), f'{key}.phase_average')
            need = state['config'].get('consumption_need', 0.85)
            for phase, ticks in [('pre',pre_ticks),('post',post_ticks)]:
                close(row[f'{phase}_consumption']+row[f'{phase}_shortfall'], ticks*state['config']['members_per_society']*need, f'{key}.{phase}.needs')
            close(row['adaptation'], row['post_welfare']-row['pre_welfare'], f'{key}.adaptation')
            close(row['within_cooperation'], row['voluntary_contribution']+row['tax'], f'{key}.pooling')
        rows_by_treatment[key] = {case_key(row):row for row in rows}
        summaries[evidence['label']] = recorded
    require({'initial_population','fixed_institution'} <= set(rows_by_treatment), 'Missing initial or fixed-institution reference')
    require(len(summary['results']) == len(summaries), 'Published results table has missing or extra treatments')
    for row in summary['results']:
        require(row['label'] in summaries, f'Unknown result-table treatment: {row["label"]}')
        require(row == summaries[row['label']], f'Result-table row differs from raw-case mean: {row["label"]}')
    checks.append('disjoint seeds, complete common-case crossing, exact treatment means, and member outcomes')

    comparisons = load(directory/'comparisons.json')
    for comparison in comparisons:
        left, right = comparison['contrast'].split(' - ')
        require(left in rows_by_treatment and right in rows_by_treatment, 'Unknown paired comparison treatment')
        require(comparison['n_cases'] == len(keys), 'Paired comparison case count mismatch')
        require(comparison['n_environment_seeds'] == len(seed_set), 'Paired comparison cluster count mismatch')
        for metric in METRICS:
            by_seed = {}
            for key in keys:
                by_seed.setdefault(key[0], []).append(rows_by_treatment[left][key][metric]-rows_by_treatment[right][key][metric])
            expected = statistics.mean(statistics.mean(values) for values in by_seed.values())
            close(comparison[metric]['mean_difference'], expected, f'{comparison["contrast"]}.{metric}')
            interval = comparison[metric]['seed_cluster_bootstrap_95']
            require(len(interval)==2 and all(math.isfinite(x) for x in interval) and interval[0]<=interval[1], 'Invalid descriptive interval')
    checks.append('paired differences calculated across environment-seed clusters')

    evaluations = load(directory/'search_evaluations.json')
    require(evaluations == state['evaluations'], 'Published search records differ from final population checkpoint')
    counts = summary['search_counts']
    for kind in ('member','institution'):
        number = sum(row['valid'] and row['accepted'] and row['kind']==kind for row in evaluations)
        require(number == state[f'accepted_{kind}_updates'] == counts[f'accepted_{kind}_updates'],
                f'Accepted {kind} update count mismatch')
    require(counts['evaluator_jobs'] == len(evaluations), 'Evaluator job count mismatch')
    require(counts['unique_evaluated_programs'] == len({ev['program_sha256'] for ev in evaluations}), 'Unique candidate count mismatch')
    require(counts['valid_evaluator_jobs'] == sum(ev['valid'] for ev in evaluations), 'Valid candidate count mismatch')
    require(counts['invalid_evaluator_jobs'] == sum(not ev['valid'] for ev in evaluations), 'Invalid candidate count mismatch')
    lineage = summary.get('lineage', [])
    node_ids = {node['id'] for node in lineage}
    require(len(node_ids)==len(lineage), 'Duplicate lineage node ID')
    for node in lineage:
        require((directory/'programs'/f'{node["program_sha256"]}.py').is_file(), 'Lineage source missing')
        for key in ('parent_id','ecological_predecessor_id'):
            require(node.get(key) is None or node[key] in node_ids, f'Dangling lineage edge: {key}')
    checks.append('search accounting and archived lineage dependencies')

    require(replay['config'] == asdict(EcologyConfig(**state['config'])), 'Replay configuration differs from population checkpoint')
    payload = {key:value for key,value in replay.items() if key not in ('digest','population_label')}
    expected_digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    require(replay['digest'] == expected_digest, 'Recorded replay digest does not match its own data')
    initial = replay.get('population_label','').startswith('Initial')
    inst = state['initial_institutions'] if initial else state['institutions']
    members = state['initial_members'] if initial else state['members']
    require(replay['program_hashes'] == [Path(path).stem for path in inst], 'Replay institution population differs from checkpoint')
    require(replay['member_program_hashes'] == [[Path(path).stem for path in row] for row in members], 'Replay member population differs from checkpoint')
    if rerun_replay:
        regenerated = run_episode(inst, replay['config'], replay['seed'], replay=True, member_programs=members)
        require(regenerated['digest'] == replay['digest'],
                'Replay regeneration digest mismatch; check frozen source and recorded Python version')
        checks.append('exact deterministic replay regenerated from archived programs and recorded seed')
    else:
        checks.append('replay content checksum and population identity (regeneration skipped)')
    return {'status':'passed','evidence':str(directory),'python':platform.python_version(),
            'checks':checks,'source_programs':len(sources),'fresh_cases_per_treatment':len(keys),
            'treatments':len(rows_by_treatment),'replay_digest':replay['digest']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,default=ROOT/'evidence/experiment')
    parser.add_argument('--no-rerun-replay',action='store_true')
    parser.add_argument('--require-final',action='store_true')
    args = parser.parse_args(argv)
    try:
        result=verify_evidence(args.evidence,rerun_replay=not args.no_rerun_replay,require_final=args.require_final)
    except (EvidenceError, KeyError, ValueError) as exc:
        print(f'Evidence verification failed: {exc}',file=sys.stderr)
        return 1
    print(json.dumps(result,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
