"""Exploratory reproduction of a supplied external claim; zero model calls."""
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import statistics
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.run_mechanism_study import verify_inputs, case_key
from scripts.evaluate_consumption_study import case_metrics, aggregate

HERE = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence/mechanism-v1'
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
def main():
    manifest = verify_inputs(EVIDENCE)
    initial = manifest['populations']['initial']
    inst = [str(EVIDENCE / p) for p in initial['institutions']]
    members = [[str(EVIDENCE / p) for p in row] for row in initial['members']]
    baseline = str(HERE / 'policy.py')
    provenance = {
        'status': 'exploratory reconstructed baseline, not prospective test',
        'reviewer_source_supplied': False,
        'claim': 'Fullest visible patch, zero tax, never raid',
        'implementation_choices': 'Always effort 1; zero public/defense/reserve; equal redistribution; empty memory and messages; ties follow sorted visible patch order; raid permission false.',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'model_generation_calls': 0,
        'new_evolutionary_runs': 0,
        'independent_environment_tuples': 12,
        'focal_panel_cases': 108,
        'paired_rollouts': 216,
        'sources_sha256': {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__), Path(baseline))},
        'frozen_manifest_sha256': digest(EVIDENCE / 'manifest.json'),
        'frozen_source_hashes': manifest['source_hashes'],
        'saved_comparator_sha256': {name: digest(EVIDENCE / f'{name}.json') for name in ('initial', 'coevolution')},
        'cases': manifest['cases'],
        'opponent_panels': manifest['opponent_panels'],
        'focal_societies': manifest['focal_societies'],
    }
    write(HERE / 'provenance.json', provenance)
    jobs = [(case, panel, focal, [baseline]*3, [[baseline]*4 for _ in range(3)], inst, members)
            for case in manifest['cases'] for panel in manifest['opponent_panels'] for focal in manifest['focal_societies']]
    with ProcessPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(case_metrics, jobs))
    write(HERE / 'baseline.json', {'summary': aggregate(rows), 'rows': rows})
    summaries = {'reconstructed_greedy': aggregate(rows)}
    comparisons = {}
    for name in ('initial', 'coevolution'):
        saved = json.loads((EVIDENCE / f'{name}.json').read_text())
        summaries[name] = aggregate(saved['rows'])
        indexed = {case_key(r): r for r in saved['rows']}
        comparisons[name] = {}
        for phase in ('drought', 'no_drought'):
            comparisons[name][phase] = {}
            for metric in ('welfare', 'shortfall_per_member_tick', 'outward_harm_per_tick', 'utility_per_tick', 'other_welfare'):
                delta = [r[phase][metric] - indexed[case_key(r)][phase][metric] for r in rows]
                comparisons[name][phase][metric] = {
                    'mean_difference': statistics.mean(delta),
                    'positive_cases_tolerance_1e-12': sum(d > 1e-12 for d in delta),
                    'negative_cases_tolerance_1e-12': sum(d < -1e-12 for d in delta),
                    'tied_cases_tolerance_1e-12': sum(abs(d) <= 1e-12 for d in delta),
                    'minimum_difference': min(delta), 'maximum_difference': max(delta),
                }
    output = {'summaries': summaries, 'paired_comparisons': comparisons,
              'baseline_ceiling_cases': {phase: sum(abs(r[phase]['welfare']-.85) < 1e-12 for r in rows) for phase in ('drought','no_drought')},
              'max_abs_ledger_residual': max(abs(r[phase]['ledger_residual']) for r in rows for phase in ('drought','no_drought')),
              'frozen_inputs_still_match': verify_inputs(EVIDENCE) == manifest,
              'diagnostic_file_sha256': {name: digest(HERE/name) for name in ('policy.py','audit.py','provenance.json','baseline.json')},
              'interpretation': 'Same existing mechanism cases, opponents, focal identities; no independent search replication. Reconstructed source is not the absent reviewer source. Lower outward harm means zero counted raid victim losses, not zero ecological externality.'}
    write(HERE / 'comparison.json', output)
    print(json.dumps({'summaries': summaries, 'paired_comparisons': comparisons, 'baseline_ceiling_cases': output['baseline_ceiling_cases'], 'max_abs_ledger_residual': output['max_abs_ledger_residual']}, indent=2))
if __name__ == '__main__':
    main()
