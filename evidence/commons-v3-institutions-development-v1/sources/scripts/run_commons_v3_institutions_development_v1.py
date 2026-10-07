#!/usr/bin/env python3
"""Prepare, record/recover or verify the declared optional-charter development bank."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.commons_v3.institutions_development_v1 import prepare, run, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--hashes-only", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.receipt and args.receipt.exists():
        parser.error("receipt must be a new file")
    if args.hashes_only and args.command != "verify":
        parser.error("hashes-only applies only to verify")
    started = time.monotonic()
    if args.command == "prepare":
        result = prepare(args.output)
    elif args.command == "run":
        result = run(args.output, workers=args.workers)
    else:
        result = verify(args.output, workers=args.workers, replay=not args.hashes_only)
    result.update(elapsed_seconds=time.monotonic() - started, workers=args.workers)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open("x") as stream:
            stream.write(text)
    print(text, end="")


if __name__ == "__main__":
    main()
