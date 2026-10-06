#!/usr/bin/env python3
"""Bounded replacement evaluator; this command grants no model-search budget."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.execution_v1 import ExecutionLimits
from swarm_societies.search_execution_v1 import evaluate_search


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program_path', required=True)
    parser.add_argument('--results_dir', required=True)
    parser.add_argument('--context', '--context_path', dest='context', required=True)
    parser.add_argument('--engine', choices=('legacy', 'consumption-v2'), default='consumption-v2')
    parser.add_argument('--wall-seconds', type=float, default=30.)
    parser.add_argument('--cpu-seconds', type=int, default=15)
    parser.add_argument('--memory-mib', type=int, default=768)
    args = parser.parse_args(argv)
    limits = replace(ExecutionLimits(), wall_seconds=args.wall_seconds,
                     cpu_seconds=args.cpu_seconds, memory_bytes=args.memory_mib * 1024 * 1024)
    try:
        record = evaluate_search(args.program_path, args.results_dir, args.context,
                                 engine=args.engine, limits=limits)
    except (OSError, ValueError, KeyError) as exc:
        print(f'Bounded evaluator blocked: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({key: record[key] for key in ('evaluation', 'kind', 'valid', 'accepted',
                                                 'combined_score', 'error')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
