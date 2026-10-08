#!/usr/bin/env python3
"""Run or exactly replay amendment A2's joint-rate synthetic Gate G2 check."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.commons_v3.calibration_joint_sites_v1 import run, verify


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--output", type=Path, default=Path("evidence/commons-v3-joint-site-calibration-v1"))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between one and eight")
    result = {"run": run, "verify": verify}[args.command](args.output, args.workers)
    print(json.dumps(result, indent=2, sort_keys=True))
