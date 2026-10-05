#!/usr/bin/env python3
"""Protected Shinka evaluator for the consumption-focused v2 study."""
import argparse
from pathlib import Path
import resource
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.consumption_evaluation import evaluate_search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--program_path', required=True)
    parser.add_argument('--results_dir', required=True)
    parser.add_argument('--context', required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    result = evaluate_search(args.program_path, args.results_dir, args.context)
    print(f"evaluation={result['evaluation']} kind={result['kind']} valid={result['valid']} "
          f"accepted={result['accepted']} score={result['combined_score']:.6g}", flush=True)


if __name__ == '__main__':
    main()
