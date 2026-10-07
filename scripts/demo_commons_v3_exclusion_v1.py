#!/usr/bin/env python3
"""Small constructed physical-exclusion checks, not a sampled development bank.

Run from any directory. Prints outcomes directly; creates no archive, evidence
receipt or audit layer. Affiliations and actions are supplied, not emergent.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.commons_v3 import engine, politics_v1 as politics
from swarm_societies.commons_v3 import exclusion_v1 as exclusion
from swarm_societies.commons_v3.exclusion_measurement_v1 import summarize_step


def local_state(stock=2., inventories=(1.5, 0., .3), groups=((0, 1),)):
    """Arranged resource competition with all growth disabled for clarity."""
    config = engine.Config(width=1, height=1, n_agents=len(inventories), n_patches=1,
        need=1.2, initial_inventory=0., inventory_capacity=80., patch_capacity=80.,
        initial_patch_stock=stock, max_harvest=4., movement_cost=0.,
        harvest_cost_per_unit=0., weather_amplitude=0., renewal_rate=0., recovery=0.)
    world = engine.WorldState(config, 42, 0,
        tuple(engine.AgentState(i, 0, 0, balance) for i, balance in enumerate(inventories)),
        (engine.PatchState(0, 0, 0, stock),))
    charter = politics.Charter(bond=0., dues=0., fine=0.)
    institutions = tuple(politics.Institution(i, 0, charter, members,
        tuple(politics.Bond(a, 0.) for a in members)) for i, members in enumerate(groups))
    political = politics.State(world, politics.PoliticalConfig(), institutions, next_id=len(groups))
    return exclusion.State(political)


def paired_fixture(state, requests, forces, original_members=(0, 1)):
    actions = tuple(engine.Action(harvest=request) for request in requests)
    base = exclusion.step(state, actions)
    treatment = exclusion.step(state, actions, forces=forces)
    assert base.political == politics.step(state.political, actions)
    summaries = {"no_force": summarize_step(state, base, original_members),
                 "force": summarize_step(state, treatment, original_members)}
    summaries["force_minus_no_force"] = {
        group: {name: summaries["force"]["cohorts"][group][name]
                       - summaries["no_force"]["cohorts"][group][name]
                for name in ("consumption", "shortfall", "harvested", "inventory_after")}
        for group in ("population", "original_members", "original_outsiders")}
    assert max(abs(base.ledger.residual), abs(treatment.ledger.residual)) < 1e-9
    return summaries


def run_demo():
    guard = (exclusion.Force(guard=1.), exclusion.Force(), exclusion.Force())
    scarce = paired_fixture(local_state(), (1., 4., 4.), guard)
    abundant = paired_fixture(local_state(20., (.4, .4, .4)), (4., 4., 4.), guard)
    resistant = paired_fixture(local_state(), (1., 4., 4.),
        (exclusion.Force(guard=1.), exclusion.Force(), exclusion.Force(resist=1.)))
    rival = paired_fixture(local_state(2., (.4, 0., .4, 0.), ((0, 1), (2, 3))),
        (0., 4., 0., 4.), (exclusion.Force(guard=1.), exclusion.Force(),
                            exclusion.Force(guard=1.), exclusion.Force()))

    assert scarce["force_minus_no_force"]["original_members"]["consumption"] > 0
    assert scarce["force_minus_no_force"]["original_outsiders"]["consumption"] < 0
    assert abundant["force_minus_no_force"]["original_members"]["consumption"] < 0
    assert (resistant["force"]["cohorts"]["original_outsiders"]["harvested"]
            > scarce["force"]["cohorts"]["original_outsiders"]["harvested"])
    assert rival["force_minus_no_force"]["population"]["consumption"] < 0

    # State continuation regenerates physical transitions from supplied actions.
    # This is deliberately not a claim of adaptive-controller continuation.
    state = local_state(20., (3., 3., 3.))
    actions = tuple(engine.Action(harvest=2.) for _ in range(3))
    state = exclusion.step(state, actions, forces=guard).state
    resumed = exclusion.restore(json.loads(json.dumps(exclusion.snapshot(state))))
    for _ in range(4):
        left = exclusion.step(state, actions, forces=guard)
        right = exclusion.step(resumed, actions, forces=guard)
        assert left == right
        state, resumed = left.state, right.state
    return {"kind": "constructed engineering fixtures; no emergence or sampled welfare estimate",
            "scarce_site": scarce, "abundant_site": abundant, "paid_resistance": resistant,
            "rival_claims": rival, "continued_physical_ticks": 4,
            "model_calls": 0, "sampled_development_episodes": 0}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, allow_nan=False))
