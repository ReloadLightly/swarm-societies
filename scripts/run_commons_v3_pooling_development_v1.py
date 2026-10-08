#!/usr/bin/env python3
"""Run approved A1 pooling, descriptive floor replay and gated sharing only."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.commons_v3 import development_pool_sites_v1 as development


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pool-run", "pool-verify", "floors-run", "sharing-run", "sharing-verify"))
    parser.add_argument("--pool-output", type=Path, default=Path(development.POOL_ROOT))
    parser.add_argument("--sharing-output", type=Path, default=Path(development.SHARING_ROOT))
    parser.add_argument("--baseline", type=Path, default=Path(development.BASE_ROOT))
    parser.add_argument("--references", type=Path, default=Path(development.REFERENCE_ROOT))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between one and eight")
    if args.command.startswith("sharing"):
        result = development.run_sharing(args.sharing_output, args.pool_output, args.baseline,
                                         args.references, args.workers, verify=args.command == "sharing-verify")
    else:
        operation = {"pool-run": development.run_pool, "pool-verify": development.verify_pool,
                     "floors-run": development.run_floors}[args.command]
        result = operation(args.pool_output, args.baseline, args.references, args.workers)
    print(json.dumps(result, indent=2, sort_keys=True))
