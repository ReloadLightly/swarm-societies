#!/usr/bin/env python3
"""Shinka-compatible trusted evaluator; candidates only enter the policy API."""
import argparse
import os
from pathlib import Path
import resource
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.evaluation import evaluate_search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--program_path', required=True)
    parser.add_argument('--results_dir', required=True)
    parser.add_argument('--context', default=os.environ.get('SWARM_CONTEXT'))
    args = parser.parse_args()
    if not args.context:
        parser.error('--context or SWARM_CONTEXT is required')
    # Simulator is stdlib-only; hard limits also bound malicious allocation/loops.
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    record = evaluate_search(args.program_path, args.results_dir, args.context)
    print(f"evaluation={record['evaluation']} kind={record['kind']} valid={record['valid']} "
          f"accepted={record['accepted']} score={record['combined_score']:.6g}", flush=True)


if __name__ == '__main__':
    main()
