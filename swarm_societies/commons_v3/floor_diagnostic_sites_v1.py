"""Descriptive effective-floor measurements from exact saved-case replays.

The scientific records stay unchanged. Scoped, process-local instrumentation
reads the frozen controller's capacity record after its decision and matches
it to the realized post-movement harvest site. Only positive realized harvest
agent-ticks count, once each, regardless of the amount harvested. This is a
diagnostic, not an intervention or a new experimental bank.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
import statistics as st

from . import consequence_sites_v1 as consequence
from . import development_learning_sites_v1 as development
from . import engine_sites_v1 as engine
from . import policies_sharing_sites_v1 as sharing
from .development_navigation_v1 import canonical, digest


VERSION = "commons-v3-effective-floor-diagnostic-sites-v1"
PERIODS = ("whole_run", "final_quarter")


class HarvestFloors:
    """Evaluator-only event accumulator; never supplies information to policies."""

    def __init__(self, horizon):
        if type(horizon) is not int or horizon < 1:
            raise ValueError("a positive horizon is required")
        self.horizon = horizon
        self.last_tick = 0
        self.values = {period: [] for period in PERIODS}

    def add(self, result, policies):
        state, ledger = result.state, result.ledger
        if state.tick != self.last_tick + 1 or state.tick > self.horizon:
            raise ValueError("floor measurements require consecutive physical ticks")
        if len(policies) != len(state.agents) or len(ledger.agents) != len(policies):
            raise ValueError("floor measurements require one policy and ledger per agent")
        self.last_tick = state.tick
        patch_at = {(patch.x, patch.y): patch.id for patch in state.patches}
        for agent, row, policy in zip(state.agents, ledger.agents, policies):
            if row.harvested <= 0.:
                continue
            site = patch_at.get((agent.x, agent.y))
            if site is None or site not in policy.records:
                raise ValueError("positive harvest lacks a recorded actual harvest site")
            if policy.stock_floor_fraction != .5 or policy.aggressive:
                raise ValueError("diagnostic requires the selected restrained controller")
            # This is exactly the capacity used by _available/_request during
            # the decision. In particular, use the arrived-at site rather than
            # the opening position, planned destination or all visible sites.
            floor = policy.stock_floor_fraction * policy.records[site]["capacity"]
            fraction = floor / state.config.site_capacities[site]
            if not math.isfinite(fraction) or fraction < 0.:
                raise ValueError("effective floor must be finite and nonnegative")
            self.values["whole_run"].append(fraction)
            if state.tick > 3 * self.horizon // 4:
                self.values["final_quarter"].append(fraction)

    def summary(self):
        if self.last_tick != self.horizon:
            raise ValueError("floor replay is incomplete")
        return {period: {"harvest_agent_ticks": len(values),
                         "sum_floor_over_true_capacity": math.fsum(values),
                         "mean_floor_over_true_capacity": st.mean(values) if values else None}
                for period, values in self.values.items()}


@contextmanager
def _instrument(arm, accumulator):
    """Observe the original runner without changing its returns or policy memory.

    One replay per process is required; callers parallelize using processes,
    not threads. Every module binding is restored on success or exception.
    """
    module, name = ((sharing, "LearningForager") if arm == "L0"
                    else (consequence, "ReferenceForager"))
    original_constructor, original_step = getattr(module, name), engine.step
    policies = []

    def constructor(*args, **kwargs):
        policy = original_constructor(*args, **kwargs)
        policies.append(policy)
        return policy

    def step(state, actions):
        result = original_step(state, actions)
        accumulator.add(result, policies)
        return result

    setattr(module, name, constructor)
    engine.step = step
    try:
        yield
    finally:
        engine.step = original_step
        setattr(module, name, original_constructor)


def diagnose_case(saved):
    """Replay one saved selected L0 or oracle case and verify its full record.

    The return value is a separate descriptive diagnostic. The caller owns any
    saving/aggregation; this function never writes to the original case bank.
    """
    job = saved["job"]
    arm = job["arm"]
    if (arm not in ("L0", "R-oracle") or job["phi"] != .375
            or (arm == "L0" and job["q"] != .25)):
        raise ValueError("only selected L0 and R-oracle cases may be diagnosed")
    runner = development if arm == "L0" else consequence
    if saved["version"] != runner.VERSION:
        raise ValueError("diagnostic case version differs from the original runner")
    accumulator = HarvestFloors(saved["horizon"])
    with _instrument(arm, accumulator):
        replay = runner.run_episode(job)
    if canonical(saved) != canonical(replay):
        raise ValueError("complete scientific record differs during floor replay")
    return {"version": VERSION, "job": dict(job), "horizon": saved["horizon"],
            "source_case_sha256": digest(saved), "exact_full_record_replay": True,
            "periods": accumulator.summary()}


def summarize(rows):
    """Four-seed cell means, with event-weighted results explicitly secondary."""
    expected = {(condition, need, seed, arm)
                for condition in development.CONDITIONS for need in development.NEEDS
                for seed in development.SEEDS for arm in ("L0", "R-oracle")}
    indexed = {}
    for row in rows:
        job = row["job"]
        key = tuple(job[name] for name in ("condition", "need", "seed", "arm"))
        if key in indexed:
            raise ValueError("duplicate diagnostic case")
        if (row["version"] != VERSION or not row["exact_full_record_replay"]
                or row["horizon"] != development.HORIZON):
            raise ValueError("incomplete or incompatible diagnostic record")
        indexed[key] = row
    if set(indexed) != expected:
        raise ValueError("diagnostic requires all sixteen paired L0/oracle cases")
    cells = []
    for condition in development.CONDITIONS:
        for need in development.NEEDS:
            arms = {}
            for arm in ("L0", "R-oracle"):
                group = [indexed[condition, need, seed, arm] for seed in development.SEEDS]
                arms[arm] = {}
                for period in PERIODS:
                    values = [row["periods"][period] for row in group]
                    events = sum(value["harvest_agent_ticks"] for value in values)
                    total = math.fsum(value["sum_floor_over_true_capacity"] for value in values)
                    arms[arm][period] = {
                        "equal_seed_mean": development.descriptive(
                            value["mean_floor_over_true_capacity"] for value in values),
                        "harvest_agent_ticks": events,
                        "event_weighted_mean": total / events if events else None,
                        "by_seed": [{"seed": seed, **value}
                                    for seed, value in zip(development.SEEDS, values)]}
            cells.append({"condition": condition, "need": need, "arms": arms})
    return {"version": VERSION, "scope": "descriptive replay diagnostic; no gate or intervention",
            "event_definition": "one positive realized harvest agent-tick at its post-movement site",
            "floor_definition": "0.5 times decision-time injected capacity, divided by true site capacity",
            "weighting": "equal weight to four seed-specific event means; event-weighted mean secondary",
            "episodes_replayed": len(rows), "cells": cells}
