"""Additive CLI for bounded fresh episodes, replay, batches and tick checkpoints.

All candidate compilation occurs in execution_v1's limited child. This module
does not change the frozen study entry points or authorize a new search budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .execution_v1 import (
    ExecutionLimits, atomic_write_receipt, bounded_read_json, execute_job,
    read_source,
)

ENGINES = {
    'legacy': 'legacy_episode',
    'consumption-v2': 'consumption_episode',
    'world-model-v1': 'world_model_episode',
    'stepwise-v1': 'stepwise_episode',
}


def _program(path, budget):
    source = read_source(path)
    name = Path(path).name
    # Account repeated descriptors too: each copy is serialized in the job.
    # The encoder later enforces the precise escaped JSON size. This earlier
    # bound prevents path expansion from allocating an unbounded parent job.
    budget[0] -= len(source.encode('utf-8')) + len(name.encode('utf-8'))
    if budget[0] < 0:
        raise ValueError('Inline policy sources exceed request byte limit')
    return {'source': source, 'name': name}


def _summary(receipt):
    keys = ('version', 'status', 'job_sha256', 'wall_seconds', 'error')
    return {key: receipt[key] for key in keys if key in receipt}


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limits', type=Path,
                        help='JSON object overriding ExecutionLimits defaults')
    commands = parser.add_subparsers(dest='command', required=True)
    job = commands.add_parser('job', help='Execute one allowlisted inline-source JSON job')
    job.add_argument('--input', required=True, type=Path)
    job.add_argument('--receipt', required=True, type=Path)
    batch = commands.add_parser('batch', help='Execute a JSON list of independent jobs')
    batch.add_argument('--input', required=True, type=Path)
    batch.add_argument('--output', required=True, type=Path,
                       help='New directory for individual receipts and batch summary')
    episode = commands.add_parser('episode', help='Evaluate supplied policy files, optionally with replay')
    episode.add_argument('--engine', choices=ENGINES, default='consumption-v2')
    episode.add_argument('--programs', nargs='+', required=True, type=Path)
    episode.add_argument('--members', type=Path,
                         help='JSON society-by-member matrix of paths relative to this JSON file')
    episode.add_argument('--config', type=Path, help='JSON ecology configuration')
    episode.add_argument('--world-parameters', type=Path, help='JSON world-model law parameters')
    episode.add_argument('--observation-mode', choices=('local', 'full_observation_control'))
    episode.add_argument('--seed', type=int, default=0)
    episode.add_argument('--replay', action='store_true')
    episode.add_argument('--receipt', required=True, type=Path)
    advance = commands.add_parser('advance', help='Advance a saved stepwise snapshot by whole ticks')
    advance.add_argument('--snapshot', type=Path, required=True,
                         help='Raw evaluator snapshot JSON (not a policy observation)')
    advance.add_argument('--steps', type=int, default=1)
    advance.add_argument('--receipt', type=Path, required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        settings = bounded_read_json(args.limits, 16384) if args.limits else {}
        if type(settings) is not dict:
            raise ValueError('Limits must be a JSON object')
        limits = ExecutionLimits(**settings).validate()
        if args.command == 'batch':
            jobs = bounded_read_json(args.input, limits.request_bytes)
            if type(jobs) is not list or not 1 <= len(jobs) <= 1000:
                raise ValueError('Batch must contain 1 to 1000 jobs within the request byte limit')
            # Never reuse a previous run directory or overwrite a completed case.
            args.output.mkdir(parents=True, exist_ok=False)
            records = []
            for index, job in enumerate(jobs):
                path = args.output / f'{index:04d}.json'
                receipt = execute_job(job, limits=limits, receipt_path=path)
                record = {**_summary(receipt), 'index': index, 'receipt': path.name,
                          'receipt_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                records.append(record)
                print(json.dumps(record, allow_nan=False), flush=True)
            summary = {'version': 'bounded-batch-v1', 'jobs': len(records),
                       'succeeded': sum(row['status'] == 'ok' for row in records),
                       'failed': sum(row['status'] != 'ok' for row in records),
                       'receipts': records}
            atomic_write_receipt(args.output / 'summary.json', summary)
            return int(summary['failed'] != 0)
        if args.command == 'job':
            job = bounded_read_json(args.input, limits.request_bytes)
        elif args.command == 'advance':
            job = {'kind': 'stepwise_advance',
                   'snapshot': bounded_read_json(args.snapshot, limits.request_bytes),
                   'steps': args.steps}
        else:
            if not 2 <= len(args.programs) <= 64:
                raise ValueError('Episode requires 2 to 64 institution programs')
            config = (bounded_read_json(args.config, 16384) if args.config else
                      {'n_societies': len(args.programs)})
            if type(config) is not dict:
                raise ValueError('Config must be a JSON object')
            societies = config.get('n_societies', len(args.programs))
            member_count = config.get('members_per_society', 6)
            if type(societies) is not int or societies != len(args.programs):
                raise ValueError('Institution count differs from config')
            if type(member_count) is not int or not 2 <= member_count <= 256:
                raise ValueError('Member count must be an integer in [2, 256]')
            members = None
            if args.members:
                members = bounded_read_json(args.members, limits.request_bytes)
                if (type(members) is not list or len(members) != societies or
                        any(type(row) is not list or len(row) != member_count for row in members)):
                    raise ValueError('Member path matrix dimensions must match config')
                if any(type(path) is not str for row in members for path in row):
                    raise ValueError('Member policy paths must be strings')
            budget = [limits.request_bytes]
            programs = [_program(path, budget) for path in args.programs]
            job = {'kind': ENGINES[args.engine], 'programs': programs,
                   'config': config, 'seed': args.seed, 'replay': args.replay}
            if members is not None:
                job['member_programs'] = [
                    [_program(args.members.parent / path, budget) for path in row] for row in members]
            if args.world_parameters or args.observation_mode:
                if args.engine not in ('world-model-v1', 'stepwise-v1'):
                    raise ValueError('World parameters and observation mode require a world-model engine')
                if args.world_parameters:
                    job['world_parameters'] = bounded_read_json(args.world_parameters, 16384)
                if args.observation_mode:
                    job['observation_mode'] = args.observation_mode
        # The parent reads files only. execute_job validates the plain JSON job;
        # syntax checks, source compilation and all policy calls occur in child.
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt = execute_job(job, limits=limits, receipt_path=args.receipt)
        print(json.dumps(_summary(receipt), allow_nan=False))
        return int(receipt['status'] != 'ok')
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(json.dumps({'status': 'error', 'error': {
            'kind': 'input_or_publication_error', 'message': str(exc)[:2048]}},
            allow_nan=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
