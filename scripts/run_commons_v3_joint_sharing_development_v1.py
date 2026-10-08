#!/usr/bin/env python3
"""Run or replay unknown-rate sharing only after the completed A2 gate passes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.commons_v3 import development_joint_sharing_sites_v1 as sharing


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--output", type=Path, default=Path(sharing.SHARING_ROOT))
    parser.add_argument("--fallback", type=Path, default=Path(sharing.joint.FALLBACK_ROOT))
    parser.add_argument("--pool", type=Path, default=Path(sharing.pool.POOL_ROOT))
    parser.add_argument("--baseline", type=Path, default=Path(sharing.pool.BASE_ROOT))
    parser.add_argument("--references", type=Path, default=Path(sharing.pool.REFERENCE_ROOT))
    parser.add_argument("--calibration", type=Path, default=Path(sharing.joint.CALIBRATION_ROOT))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between one and eight")
    result = sharing.run(args.output, fallback_root=args.fallback, pool_root=args.pool,
                         baseline_root=args.baseline, reference_root=args.references,
                         calibration_root=args.calibration, workers=args.workers,
                         verify=args.command == "verify")
    print(json.dumps(result, indent=2, sort_keys=True))
