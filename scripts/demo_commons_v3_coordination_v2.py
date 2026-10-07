#!/usr/bin/env python3
"""Construct coordination and responsive-membership engineering fixtures.

These deliberately arranged states test supplied decisions and accounting.
They are not sampled environments, policy selection, or a welfare experiment.
Run from any directory; --output creates a new JSON file and never replaces it.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.commons_v3 import engine, politics_v1 as politics
from swarm_societies.commons_v3.policies_coordination_v2 import CoordinationPolicy
from swarm_societies.commons_v3.policies_membership_v2 import MembershipPolicy
from swarm_societies.commons_v3.political_episode_v1 import ScriptedPolicy
from swarm_societies.commons_v3.political_episode_v2 import Episode, restore_checkpoint


VERSION = "commons-v3-coordination-membership-engineering-demo-v2"


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _inert(schedule=None):
    plans = {tick: (engine.Action(), politics.Intent()) for tick in range(16)}
    plans.update(schedule or {})
    return ScriptedPolicy(plans)


def _member():
    return MembershipPolicy(coordinator=CoordinationPolicy(share=False))


def _local_state(*, stock=80., inventory=12., members=()):
    cfg = engine.Config(width=1, height=1, n_agents=3, n_patches=1, need=1.2,
        initial_inventory=inventory, initial_patch_stock=stock, patch_capacity=80.,
        weather_amplitude=0., renewal_rate=0., recovery=0.)
    world = engine.WorldState(cfg, 42, 0,
        tuple(engine.AgentState(i, 0, 0, inventory) for i in range(3)),
        (engine.PatchState(0, 0, 0, stock),))
    institutions = () if not members else (politics.Institution(0, 0, politics.Charter(), members,
        tuple(politics.Bond(i, 1.) for i in members)),)
    return politics.State(world, politics.PoliticalConfig(), institutions, next_id=1 if members else 0)


def _frame(episode, result):
    frame = {"tick": result.ledger.tick,
            "actions": [asdict(action) for action in episode.last_actions],
            "intents": [asdict(intent) for intent in episode.last_intents],
            "private_feedback": list(episode.private_feedback),
            "physical_ledger": asdict(result.physical.ledger),
            "political_ledger": asdict(result.ledger), "events": list(result.events),
            "agents_after": [asdict(agent) for agent in episode.state.world.agents],
            "institutions_after": [asdict(institution) for institution in episode.state.institutions],
            "policy_diagnostics": [getattr(policy, "diagnostics", {}) for policy in episode.policies]}
    return json.loads(_bytes(frame))


def _record(episode, stop_tick, checkpoint_ticks):
    start = episode.state.world.tick
    initial = episode.checkpoint()
    frames, results, checkpoints = [], [], {}
    while episode.state.world.tick < stop_tick:
        tick = episode.state.world.tick
        if tick in checkpoint_ticks:
            checkpoints[tick] = json.loads(_bytes(episode.checkpoint()))
        result = episode.advance()
        results.append(result)
        frames.append(_frame(episode, result))
    final = episode.checkpoint()
    replayed = 0
    for tick, checkpoint in checkpoints.items():
        resumed = restore_checkpoint(checkpoint)
        for offset in range(tick - start, len(results)):
            result = resumed.advance()
            if result != results[offset] or _bytes(_frame(resumed, result)) != _bytes(frames[offset]):
                raise AssertionError("fixture continuation changed a decision, receipt, or material flow")
            replayed += 1
        if resumed.checkpoint() != final:
            raise AssertionError("fixture continuation changed final policy memory or custody")
    residual = max((abs(row.ledger.residual) for row in results), default=0.)
    if residual > 1e-9:
        raise AssertionError("fixture material accounting failed")
    return {"initial_checkpoint": initial, "initial_tick": start, "stop_tick": stop_tick,
            "checkpoint_ticks": sorted(checkpoints), "replayed_continuation_ticks": replayed,
            "checkpoint_sha256": {str(tick): value["sha256"] for tick, value in checkpoints.items()},
            "final_checkpoint_sha256": final["sha256"], "max_accounting_residual": residual,
            "trace_sha256": hashlib.sha256(_bytes(frames)).hexdigest(), "trace": frames}


def _coordination():
    cfg = engine.Config(width=7, height=3, n_agents=3, n_patches=2, sensing_radius=2,
        need=1.2, initial_inventory=3., renewal_rate=0., recovery=0., weather_amplitude=0.)
    world = engine.WorldState(cfg, 42, 0,
        tuple(engine.AgentState(i, 3, 1, 3.) for i in range(3)),
        (engine.PatchState(0, 1, 1, 22.), engine.PatchState(1, 5, 1, 22.)))
    sender = Episode(politics.State(world, politics.PoliticalConfig()),
                     [CoordinationPolicy(), _inert(), _inert()])
    transmission = _record(sender, 1, (0,))
    receipt = transmission["trace"][0]["physical_ledger"]["messages"]
    if len(receipt) != 1 or not receipt[0]["delivered"] or receipt[0]["cost"] <= 0.:
        raise AssertionError("fixture must purchase and deliver a real delayed intention")
    branches = {}
    for name, messages in (("delivered", sender.state.world.messages), ("information_removed", ())):
        # Deliberate staged fixture: the sender now completes its announced
        # route using a fixed action; the recipient begins a fresh controller.
        # Both branches retain the actual earlier payment and private receipt.
        state = replace(sender.state, world=replace(sender.state.world, messages=messages))
        episode = Episode(state,
            [_inert({1: (engine.Action(move=(-1, 0), harvest=2.), politics.Intent())}),
             CoordinationPolicy(), _inert()], private_feedback=sender.private_feedback,
             feedback_origin_tick=sender.feedback_origin_tick)
        branches[name] = _record(episode, 3, (1, 2))
    informed, removed = branches["delivered"]["trace"], branches["information_removed"]["trace"]
    if tuple(informed[0]["actions"][1]["move"]) != (1, 0) or tuple(removed[0]["actions"][1]["move"]) != (-1, 0):
        raise AssertionError("paid intention did not change the constructed recipient route")
    if informed[1]["physical_ledger"]["agents"][1]["harvested"] != 2. or removed[1]["physical_ledger"]["agents"][1]["harvested"] != 0.:
        raise AssertionError("constructed route response did not reach distinct realized extraction")
    return {"interpretation": "Synthetic message intervention after a real payment; scripted sender completion and fresh recipient are explicit fixture setup, not a population benefit estimate.",
            "transmission": transmission, "branches": branches,
            "paid_message_cost": receipt[0]["cost"], "paid_message_bytes": receipt[0]["byte_count"],
            "receiver_moves_at_tick_1": {name: row["trace"][0]["actions"][1]["move"] for name, row in branches.items()},
            "receiver_harvest_at_tick_2": {name: row["trace"][1]["physical_ledger"]["agents"][1]["harvested"] for name, row in branches.items()},
            "receiver_consumption_at_tick_2": {name: row["trace"][1]["private_feedback"][1]["consumption"] for name, row in branches.items()}}


def _membership_exit():
    episode = Episode(_local_state(stock=0., inventory=2., members=(0, 1, 2)),
                      [_member(), _inert(), _inert()])
    charter = asdict(episode.state.institutions[0].charter)
    record = _record(episode, 8, (3, 5))
    exits = [frame for frame in record["trace"] if frame["intents"][0]["kind"] == "exit"]
    withdrawals = [frame for frame in record["trace"] if frame["intents"][0]["kind"] == "withdraw"]
    if len(exits) != 1 or exits[0]["tick"] != 4 or len(withdrawals) != 1 or withdrawals[0]["tick"] != 6:
        raise AssertionError("declared dissatisfaction and delayed refund fixture did not execute")
    exit_frame, withdrawal = exits[0], withdrawals[0]
    bond = next(b for b in exit_frame["institutions_after"][0]["bonds"] if b["owner"] == 0)
    private_after_exit = exit_frame["agents_after"][0]["inventory"]
    private_after_physics = exit_frame["physical_ledger"]["agents"][0]["inventory_after"]
    amount = sum(entry["amount"] for entry in withdrawal["political_ledger"]["entries"]
                 if entry["kind"] == "withdraw" and entry["actor"] == 0)
    if (bond["release_tick"] != 6 or private_after_exit != private_after_physics or amount != 1.
            or episode.state.institutions[0].charter != politics.Charter(**charter)):
        raise AssertionError("refund timing, amount, or unchanged charter differs")
    record.update({"interpretation": "Supplied dissatisfaction rule exits after own shortfall under unchanged terms; no causal attribution of shortfall to membership.",
                   "exit_tick": 4, "release_tick": bond["release_tick"], "withdrawal_tick": 6,
                   "withdrawal_amount": amount, "charter_unchanged": True,
                   "exit_is_immediate_refund": private_after_exit != private_after_physics,
                   "withdrawal_tick_consumption": withdrawal["private_feedback"][0]["consumption"]})
    return record


def run_demo(*, full_trace=False):
    coordination = _coordination()
    membership = _membership_exit()
    formation_episode = Episode(_local_state(), [_member() for _ in range(3)])
    formation = _record(formation_episode, 3, (1,))
    if formation_episode.state.institutions[0].members != (0, 1, 2):
        raise AssertionError("favorable local fixture did not form the supplied quota charter")
    formation["members"] = list(formation_episode.state.institutions[0].members)
    formation["interpretation"] = "Unscheduled supplied local entry rules in an arranged favorable state; not emergence or demonstrated useful governance."
    state = _local_state(inventory=2.)
    state = replace(state, proposals=(politics.Proposal(0, "found", 0, 0,
        charter=politics.Charter(), created_tick=0, expires_tick=8),), next_id=1)
    refusal_episode = Episode(state, [_inert(), _member(), _inert()])
    refusal = _record(refusal_episode, 1, (0,))
    if refusal["trace"][0]["intents"][1]["kind"] != "refuse" or refusal_episode.state.institutions:
        raise AssertionError("unaffordable entry fixture did not refuse the local proposal")
    refusal["reason"] = refusal_episode.policies[1].diagnostics["reason"]
    records = [coordination["transmission"], *coordination["branches"].values(), membership, formation, refusal]
    sources = {str((ROOT / "swarm_societies/commons_v3" / name).resolve().relative_to(ROOT)): sha
               for name, sha in membership["initial_checkpoint"]["payload"]["sources"].items()}
    sources[str(Path(__file__).resolve().relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output = {"version": VERSION,
              "interpretation": "Deterministic constructed engineering fixtures only; no sampled bank, independent evaluation, welfare qualification, model calls, or evolution.",
              "sources": sources, "model_calls": 0, "evolutionary_runs": 0,
              "replayed_continuation_ticks": sum(row["replayed_continuation_ticks"] for row in records),
              "max_accounting_residual": max(row["max_accounting_residual"] for row in records),
              "fixtures": {"paid_coordination": coordination, "responsive_exit": membership,
                           "optional_formation": formation, "liquidity_refusal": refusal}}
    if not full_trace:
        for record in records:
            del record["trace"]
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-trace", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("--output must name a new file; existing evidence is never replaced")
    payload = json.dumps(run_demo(full_trace=args.full_trace), indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as output:
            output.write(payload)
        print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(payload.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
