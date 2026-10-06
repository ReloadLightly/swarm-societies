#!/usr/bin/env python3
"""Fetch and restore hash-pinned study evidence listed in the repository catalog."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.evidence_archive_v1 import fetch, load_manifest, restore, verify


def load_catalog(path):
    path = Path(path).resolve()
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Evidence catalog exceeds 1 MiB')
    catalog = json.loads(path.read_text())
    if (type(catalog) is not dict or catalog.get('version') != 'evidence-catalog-v1' or
            type(catalog.get('studies')) is not list or not 1 <= len(catalog['studies']) <= 128):
        raise ValueError('Unsupported evidence catalog')
    seen = set()
    for row in catalog['studies']:
        if (type(row) is not dict or type(row.get('id')) is not str or
                not row['id'] or row['id'] == 'all' or row['id'] in seen):
            raise ValueError('Missing or duplicated study identity')
        seen.add(row['id'])
        relative = row.get('manifest')
        if (type(relative) is not str or not relative or '\\' in relative or
                PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts):
            raise ValueError('Manifest path must be relative and remain inside the catalog directory')
        manifest = (path.parent / relative).resolve()
        if not manifest.is_relative_to(path.parent) or manifest.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('Invalid manifest path or size')
        actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
        if actual != row['manifest_sha256']:
            raise ValueError('Manifest checksum mismatch for ' + row['id'])
        payload = load_manifest(manifest)
        if any(not item['path'].startswith('evidence/') for item in payload['files']):
            raise ValueError('Study archives may restore only evidence/ files')
    return catalog


def check_restored(manifest_path, root):
    """Check every bulk file in a study without requiring an archive or network."""
    manifest = load_manifest(manifest_path)
    root = Path(root).resolve()
    for row in manifest['files']:
        path = root / row['path']
        for item in (path, *path.parents):
            if item == root:
                break
            if item.is_symlink():
                raise ValueError('Symlink in restored evidence path: ' + row['path'])
        if not path.exists():
            raise FileNotFoundError('Evidence missing: ' + row['path'])
        if not path.is_file() or path.stat().st_size != row['size']:
            raise ValueError('Restored evidence size/type differs: ' + row['path'])
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        if digest.hexdigest() != row['sha256']:
            raise ValueError('Restored evidence checksum differs: ' + row['path'])
    return {'status': 'ok', 'file_count': len(manifest['files']),
            'total_file_bytes': manifest['total_file_bytes'],
            'restored': 0, 'existing': len(manifest['files']), 'checked_worktree': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'artifacts/evidence-v1/catalog.json')
    parser.add_argument('--study', nargs='+', default=['all'],
                        help='Study identifiers, or all (default)')
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='Repository checkout to restore, default this checkout')
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache/evidence-v1')
    parser.add_argument('--offline', action='store_true', help='Require already verified cached archives')
    parser.add_argument('--verify-only', action='store_true', help='Verify archives without restoring files')
    parser.add_argument('--check', action='store_true', help='Check existing evidence files; no download or write')
    parser.add_argument('--receipt', type=Path, help='New JSON receipt file; existing files are not replaced')
    args = parser.parse_args(argv)
    try:
        if args.receipt and (args.receipt.exists() or args.receipt.is_symlink()):
            raise FileExistsError('Receipt already exists')
        if args.check and args.verify_only:
            raise ValueError('--check and --verify-only are separate operations')
        catalog = load_catalog(args.catalog)
        known = {row['id'] for row in catalog['studies']}
        requested = set(args.study)
        if requested == {'all'}:
            requested = known
        elif not requested or not requested <= known:
            raise ValueError('Unknown study; available: ' + ', '.join(sorted(known)))
        results = []
        for row in catalog['studies']:
            if row['id'] not in requested:
                continue
            manifest = args.catalog.resolve().parent / row['manifest']
            if args.verify_only:
                archive = fetch(manifest, args.cache, offline=args.offline)
                result = verify(manifest, archive)
            else:
                try:
                    result = check_restored(manifest, args.root)
                except FileNotFoundError:
                    if args.check:
                        raise
                    archive = fetch(manifest, args.cache, offline=args.offline)
                    result = restore(manifest, archive, args.root)
            results.append({'study': row['id'], **result})
            print(json.dumps(results[-1], sort_keys=True), flush=True)
        receipt = {'version': 'evidence-restoration-v1', 'status': 'ok',
                   'catalog_sha256': hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
                   'root': str(args.root.resolve()), 'offline': args.offline,
                   'verify_only': args.verify_only, 'check': args.check, 'studies': results}
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            with args.receipt.open('x') as stream:
                json.dump(receipt, stream, indent=2, sort_keys=True)
                stream.write('\n')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Evidence restoration failed: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
