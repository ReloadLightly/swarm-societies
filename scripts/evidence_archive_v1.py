#!/usr/bin/env python3
"""Package, verify, restore and fetch immutable evidence bundles without overwrites."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_societies.evidence_archive_v1 import DEFAULT_MAX_BYTES, fetch, package, restore, verify


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('package', 'verify', 'restore', 'fetch'):
        sub = commands.add_parser(command)
        sub.add_argument('--manifest', type=Path, required=True)
        sub.add_argument('--max-bytes', type=int, default=DEFAULT_MAX_BYTES)
        if command == 'package':
            sub.add_argument('--root', type=Path, required=True)
            sub.add_argument('--inventory', type=Path, required=True)
            sub.add_argument('--output', type=Path, required=True)
            sub.add_argument('--source-url')
        elif command == 'fetch':
            sub.add_argument('--cache', type=Path, required=True)
            sub.add_argument('--offline', action='store_true')
            sub.add_argument('--allow-http-for-tests', action='store_true',
                             help='Permit HTTP only on localhost/loopback for network tests')
        else:
            sub.add_argument('--archive', type=Path, required=True)
            if command == 'restore':
                sub.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'package':
            result = package(args.root, args.inventory, args.output, args.manifest,
                             source_url=args.source_url, max_bytes=args.max_bytes)
            result = {'version': result['version'], 'status': 'ok', 'archive': result['archive'],
                      'file_count': len(result['files']), 'total_file_bytes': result['total_file_bytes']}
        elif args.command == 'verify':
            result = verify(args.manifest, args.archive, max_bytes=args.max_bytes)
        elif args.command == 'restore':
            result = restore(args.manifest, args.archive, args.root, max_bytes=args.max_bytes)
        else:
            path = fetch(args.manifest, args.cache, offline=args.offline, max_bytes=args.max_bytes,
                         allow_http_for_tests=args.allow_http_for_tests)
            result = {'status': 'ok', 'cache_path': str(path)}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'error': f'{type(exc).__name__}: {exc}'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
