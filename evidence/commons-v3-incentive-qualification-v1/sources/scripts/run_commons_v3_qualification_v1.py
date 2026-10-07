#!/usr/bin/env python3
"""Freeze, run or exactly replay separately versioned qualification banks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.commons_v3.qualification_v1 import prepare, run, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("ecology", "incentive"), help="Required only for prepare")
    parser.add_argument("--ecology", type=Path, help="Completed ecology bank for incentive run or dependency verification")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--hashes-only", action="store_true", help="Verify artifacts/aggregates without semantic replay")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.receipt and args.receipt.exists():
        parser.error("receipt must be a new path")
    if args.command == "prepare" and (args.stage is None or args.ecology is not None or args.hashes_only):
        parser.error("prepare requires --stage and accepts neither --ecology nor --hashes-only")
    if args.command != "prepare" and args.stage is not None:
        parser.error("--stage applies only to prepare")
    if args.command != "verify" and args.hashes_only:
        parser.error("--hashes-only applies only to verify")
    if not 1 <= args.workers <= 16:
        parser.error("workers must be between 1 and 16")
    started = time.perf_counter()
    if args.command == "prepare":
        result = prepare(args.output, args.stage)
    elif args.command == "run":
        summary = run(args.output, workers=args.workers, ecology=args.ecology)
        result = {"version": summary["version"], "stage": summary.get("stage", summary.get("phase")),
                  "completed": True, "summary_path": str(args.output / "summary.json"),
                  **{key: summary[key] for key in ("configurations", "episodes", "physical_ticks", "agent_decisions",
                                                   "max_ledger_residual", "qualification_status")}}
    else:
        result = verify(args.output, replay=not args.hashes_only, workers=args.workers, ecology=args.ecology)
    result = {**result, "elapsed_seconds": time.perf_counter() - started, "workers": args.workers,
              "timing_scope": "this invocation only, including any verification of recovered cases"}
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
