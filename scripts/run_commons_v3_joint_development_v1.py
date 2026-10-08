#!/usr/bin/env python3
"""Run/replay the approved A2 fallback after joint G2; never fresh evaluation."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.commons_v3 import development_joint_sites_v1 as development
from swarm_societies.commons_v3 import development_pool_sites_v1 as pool


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--output", type=Path, default=Path(development.FALLBACK_ROOT))
    parser.add_argument("--pool", type=Path, default=Path(pool.POOL_ROOT))
    parser.add_argument("--baseline", type=Path, default=Path(pool.BASE_ROOT))
    parser.add_argument("--references", type=Path, default=Path(pool.REFERENCE_ROOT))
    parser.add_argument("--calibration", type=Path, default=Path(development.CALIBRATION_ROOT))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between one and eight")
    result = development.run(args.output, pool_root=args.pool, baseline_root=args.baseline,
                             reference_root=args.references, calibration_root=args.calibration,
                             workers=args.workers, verify=args.command == "verify")
    print(json.dumps(result, indent=2, sort_keys=True))
