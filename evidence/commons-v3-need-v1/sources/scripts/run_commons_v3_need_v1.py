#!/usr/bin/env python3
"""Prepare, run or replay exploratory need-targeted commons v3 baselines."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.commons_v3.development_need_v1 import prepare, run, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.receipt and args.receipt.exists():
        parser.error("receipt must be a new path")
    if args.command == "prepare":
        prepare(args.output)
        result = {"prepared": str(args.output)}
    elif args.command == "run":
        summary = run(args.output)
        result = {key: summary[key] for key in ("configurations", "episodes", "agent_decisions", "max_ledger_residual")}
    else:
        result = verify(args.output)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
