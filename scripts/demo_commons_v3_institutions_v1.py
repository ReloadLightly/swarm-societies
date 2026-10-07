#!/usr/bin/env python3
"""Exercise the optional political lifecycle as a fixed engineering fixture.

Run from any directory. This is not an experimental bank or a formation,
deterrence, or welfare comparison. It emits a deterministic summary to stdout;
--full-trace additionally includes every step's commitments and local events.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swarm_societies.commons_v3.engine import Action, Config
from swarm_societies.commons_v3 import politics_v1 as politics
from swarm_societies.commons_v3.political_episode_v1 import Episode, ScriptedPolicy, restore_checkpoint


VERSION = "commons-v3-institutions-engineering-demo-v1"
HORIZON = 17
CHECKPOINT_TICKS = (1, 4, 5, 7, 10, 14)


def build_fixture():
    config = Config(width=3, height=1, n_agents=3, n_patches=1, need=0.,
                    initial_inventory=10., inventory_capacity=20., initial_patch_stock=40.,
                    renewal_rate=0., recovery=0., weather_amplitude=0.)
    state = politics.initialize(config, seed=0)
    world = replace(state.world, agents=tuple(replace(a, x=0, y=0) for a in state.world.agents),
                    patches=(replace(state.world.patches[0], x=0, y=0),))
    state = replace(state, world=world)
    schedules = [{tick: (Action(), politics.Intent()) for tick in range(HORIZON)} for _ in world.agents]

    def plan(actor, tick, kind="none", target=None, charter=None, amount=0., funding="private", physical=None):
        schedules[actor][tick] = (Action() if physical is None else physical,
                                 politics.Intent(kind, target, charter, amount, funding))

    plan(0, 0, "propose", 0, politics.Charter())
    plan(0, 1, "endorse", 0)
    plan(1, 1, "endorse", 0)
    plan(2, 1, "refuse", 0)
    plan(0, 2, "pay", 0, amount=1.)
    plan(2, 2, "join", 0)
    plan(0, 3, "monitor", 0, funding="treasury")
    plan(1, 3, physical=Action(harvest=3.))
    plan(2, 3, physical=Action(harvest=3.))
    plan(0, 4, "sanction", 2, funding="treasury")
    plan(1, 4, physical=Action(harvest=3.))  # No monitoring: violation is undetected.
    plan(2, 4, "exit", 0)
    plan(0, 5, physical=Action(harvest=3.))
    plan(1, 5, "monitor", 0)
    plan(2, 5, "pay", 0, amount=.1)  # Former member: rejected.
    plan(0, 6, "amend", 0, politics.Charter(quota=1.5))
    plan(1, 6, "sanction", 4, physical=Action(move=(1, 0)))  # Cannot settle remotely.
    plan(2, 6, "withdraw", 0, amount=1.)
    plan(1, 7, physical=Action(move=(-1, 0)))
    plan(0, 8, "endorse", 7)
    plan(1, 8, "endorse", 7)
    plan(0, 9, "replace", 0, politics.Charter(quota=1.5))
    plan(0, 10, "endorse", 8)
    plan(1, 10, "endorse", 8)
    plan(1, 11, "exit", 8)
    plan(0, 12, "dissolve", 8)
    plan(0, 13, "endorse", 9)
    plan(1, 13, "withdraw", 8, amount=20.)
    plan(0, 14, "withdraw", 8, amount=20.)  # Still locked: rejected.
    plan(2, 14, "cache", 0, amount=1.)
    plan(0, 15, "withdraw", 8, amount=20.)
    plan(2, 15, "retrieve", 0, amount=1.)
    return Episode(state, [ScriptedPolicy(schedule) for schedule in schedules])


def run_demo(*, full_trace=False):
    episode = build_fixture()
    checkpoints, results, frames = {}, [], []
    for _ in range(HORIZON):
        result = episode.advance()
        results.append(result)
        frames.append({"tick": episode.state.world.tick,
                       "actions": [asdict(a) for a in episode.last_actions],
                       "intents": [asdict(i) for i in episode.last_intents],
                       "events": list(result.events), "ledger": asdict(result.ledger),
                       "institutions": [asdict(i) for i in episode.state.institutions]})
        if episode.state.world.tick in CHECKPOINT_TICKS:
            checkpoints[episode.state.world.tick] = json.loads(json.dumps(episode.checkpoint()))
    replayed = 0
    for tick, checkpoint in checkpoints.items():
        resumed = restore_checkpoint(checkpoint)
        for expected in results[tick:]:
            if resumed.advance() != expected:
                raise AssertionError("full political checkpoint continuation differs")
            replayed += 1
        if resumed.checkpoint() != episode.checkpoint():
            raise AssertionError("final controller memories differ after checkpoint continuation")
    events = [event for result in results for event in result.events]
    successful = {kind: sum(e["kind"] == kind and e["ok"] for e in events)
                  for kind in sorted({e["kind"] for e in events})}
    expected_successes = {"amend": 1, "cache": 1, "dissolve": 1, "endorse": 7,
                          "exit": 2, "join": 1, "monitor": 2, "pay": 1,
                          "propose": 1, "refuse": 1, "replace": 1, "retrieve": 1,
                          "sanction": 1, "withdraw": 3}
    failures = [(e["tick"], e["actor"], e["kind"]) for e in events if not e["ok"]]
    if successful != expected_successes or failures != [(5, 2, "pay"), (6, 1, "sanction"), (14, 0, "withdraw")]:
        raise AssertionError("fixture did not execute the declared lifecycle and failure cases")
    if any(i.active for i in episode.state.institutions) or politics.custody(episode.state) != 0.:
        raise AssertionError("fixture did not finish dissolution and local custody settlement")
    trace_bytes = json.dumps(frames, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    summary = {"version": VERSION,
               "interpretation": "Scripted lifecycle and checkpoint validation only; no scientific qualification or model calls.",
               "ticks": HORIZON, "individuals": len(episode.state.world.agents),
               "checkpoint_ticks": list(CHECKPOINT_TICKS), "replayed_continuation_ticks": replayed,
               "successful_events": successful,
               "failed_events": [e for e in events if not e["ok"]],
               "final_active_institutions": sum(i.active for i in episode.state.institutions),
               "final_custody": politics.custody(episode.state),
               "political_operating_cost": episode.state.political_cost,
               "forfeited_collateral": episode.state.forfeited,
               "max_accounting_residual": max(abs(result.ledger.residual) for result in results),
               "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
               "final_checkpoint_sha256": episode.checkpoint()["sha256"]}
    if full_trace:
        summary["trace"] = frames
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-trace", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_demo(full_trace=args.full_trace), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
