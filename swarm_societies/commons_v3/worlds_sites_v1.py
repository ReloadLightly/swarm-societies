"""The two site-capacity worlds in paper contract v1, section 4.

Capacity permutations use the scratch probes' seed-shuffled site order.
Initial fractions use separate keyed draws, shared across arms and demand
levels; neither operation changes the frozen weather or agent-slot keys.
This module supplies evaluator configuration, never a policy observation.
"""
from __future__ import annotations

import random

from . import engine_sites_v1 as engine


WORLD_LEVELS = {
    "moderate": (20., 30., 40., 50., 60.),
    "wide": (10., 20., 40., 60., 90.),
}


def capacity_world(condition: str, seed: int) -> tuple[float, ...]:
    if condition not in WORLD_LEVELS:
        raise ValueError("condition must be moderate or wide")
    engine._integer(seed, "seed", 0, 2**64 - 1)
    capacities = list(WORLD_LEVELS[condition]) * 3 + [40.]
    if condition == "wide":
        capacities = [capacity * (640. / sum(capacities)) for capacity in capacities]
    random.Random(seed).shuffle(capacities)
    return tuple(capacities)


def initial_fractions(seed: int) -> tuple[float, ...]:
    engine._integer(seed, "seed", 0, 2**64 - 1)
    return tuple(.3 + .6 * (engine._event(seed, "initial-site-fraction", 0, site) / 2**64)
                 for site in range(16))


def configuration(condition: str, need: float, seed: int) -> engine.Config:
    if type(need) not in (int, float) or need not in (1.2, 1.6):
        raise ValueError("contract demand must be 1.2 or 1.6")
    capacities = capacity_world(condition, seed)
    return engine.Config(need=float(need), site_capacities=capacities,
                         initial_site_stocks=tuple(k * u for k, u in zip(capacities, initial_fractions(seed))))


def initialize(condition: str, need: float, seed: int) -> engine.WorldState:
    return engine.initialize(configuration(condition, need, seed), seed)
