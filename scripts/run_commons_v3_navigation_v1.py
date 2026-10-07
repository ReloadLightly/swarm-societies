#!/usr/bin/env python3
"""Freeze, tune, evaluate or replay the bounded commons v3 forager grid."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.commons_v3.development_navigation_v1 import prepare, tune, evaluate, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "tune", "evaluate", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "tuning", "evaluation"), default="all",
                        help="Verification phase only; evaluation verification does not replay tuning")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.phase != "all" and args.command != "verify":
        parser.error("--phase applies only to verify")
    if args.receipt and args.receipt.exists():
        parser.error("receipt must be a new path")
    if args.command == "prepare":
        prepare(args.output)
        result = {"prepared": str(args.output)}
    elif args.command in ("tune", "evaluate"):
        summary = tune(args.output) if args.command == "tune" else evaluate(args.output)
        result = {key: summary[key] for key in ("configurations", "episodes", "physical_ticks", "agent_decisions", "max_ledger_residual")}
        if args.command == "tune":
            result["selected_candidate_id"] = summary["selected_candidate_id"]
        else:
            result["selected_candidate"] = summary["selected_candidate"]
            result["total_tuning_and_evaluation"] = summary["total_tuning_and_evaluation"]
    else:
        result = verify(args.output, phase=args.phase)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
