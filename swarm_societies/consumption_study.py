"""Trusted scenario construction and measurements for the consumption study.

Scenario data and measured scores never enter candidate observations. Environment
and schedule randomness use different, explicitly named streams; search and fresh
environment seeds also occupy disjoint integer ranges. The simulator's material
rules remain those of the first increment, versioned separately to preserve it.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import random

from .ecology_consumption_v2 import EcologyConfig, run_episode


STUDY_VERSION = "consumption-v2"
FROZEN_V1_SIMULATOR_SHA256 = "76e4ba5a2abf4f20356c8c4710d0a5632b50cd87e97d363c27b556642508eba7"
SEARCH_SCHEDULES = ((48, .35), (48, .65), (60, .35), (60, .65), (72, .35), (72, .65))
FRESH_HORIZONS = (48, 60, 72)
FRESH_FRACTIONS = (.35, .50, .65)


def _derived_seed(domain, *values):
    payload = json.dumps([STUDY_VERSION, domain, *values], separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def _environment_seed(bank, replication_seed, index):
    # The high bit distinguishes held-out seeds regardless of replication seed.
    value = _derived_seed(f"{bank}-environment", replication_seed, index) & ((1 << 61) - 1)
    return value | ((1 << 61) if bank == "fresh" else 0)


def _scenario(bank, replication_seed, index, ticks, fraction, schedule_seed):
    config = EcologyConfig(n_societies=3, members_per_society=4, ticks=ticks,
                           disturbance_tick=math.floor(ticks * fraction))
    return {
        "id": f"{STUDY_VERSION}-{bank}-{replication_seed}-{index:02d}",
        "bank": bank,
        "replication_seed": replication_seed,
        "case_index": index,
        "seed": _environment_seed(bank, replication_seed, index),
        "schedule_seed": schedule_seed,
        "disturbance_fraction": fraction,
        "config": asdict(config),
    }


def make_search_cases(replication_seed):
    """Six search cases; each horizon occurs twice and each timing three times.

    The exact six horizon/timing combinations are fixed before search. Their order
    is shuffled with a replication-specific schedule RNG; ecology seeds come from
    a separate domain and do not depend on RNG consumption in the simulator.
    """
    if not isinstance(replication_seed, int) or isinstance(replication_seed, bool):
        raise ValueError("replication_seed must be an integer")
    schedule_seed = _derived_seed("search-schedule", replication_seed)
    schedules = list(SEARCH_SCHEDULES)
    random.Random(schedule_seed).shuffle(schedules)
    return [_scenario("search", replication_seed, index, ticks, fraction, schedule_seed)
            for index, (ticks, fraction) in enumerate(schedules)]


def make_fresh_cases():
    """Twelve shared held-out cases, balanced in horizon and disturbance fraction.

    Four copies of each horizon and fraction are independently shuffled then
    paired. The bank is fixed across arms and independent evolutionary runs.
    It is a balanced marginal design, not a complete horizon × timing crossing.
    """
    schedule_seed = _derived_seed("fresh-schedule", 0)
    horizons = list(FRESH_HORIZONS) * 4
    fractions = list(FRESH_FRACTIONS) * 4
    random.Random(_derived_seed("fresh-horizon", schedule_seed)).shuffle(horizons)
    random.Random(_derived_seed("fresh-fraction", schedule_seed)).shuffle(fractions)
    return [_scenario("fresh", 0, index, ticks, fraction, schedule_seed)
            for index, (ticks, fraction) in enumerate(zip(horizons, fractions))]


def simulate_consumption(institutions, members, scenario, replay=False, disturbance=True):
    """Execute a frozen case and expose consumption-only, duration-normalized scores.

    ``disturbance=False`` is an exact paired no-drought intervention: it disables
    only the exogenous multiplier. The same initial productivity, weather, raid
    draws and initiative are generated from the same environment seed. Candidate
    feedback may subsequently diverge. Phase windows keep the scheduled boundary.
    The scenario and input program lists are not mutated.
    """
    if not isinstance(disturbance, bool):
        raise ValueError("disturbance must be a boolean")
    config_values = dict(scenario["config"])
    config_values["enable_disturbance"] = disturbance
    config = EcologyConfig(**config_values)
    config.validate()
    result = run_episode(institutions, config, seed=scenario["seed"], replay=replay,
                         member_programs=members)
    result["raw_episode_digest"] = result.pop("digest")
    phase_ticks = {"pre": config.disturbance_tick,
                   "post": config.ticks - config.disturbance_tick,
                   "overall": config.ticks}
    for row in result["timeseries"]:
        row["welfare_with_infrastructure"] = row["welfare"] + .03 * row["infrastructure"]
    for society in result["society_metrics"]:
        for phase, ticks in phase_ticks.items():
            metric = society[phase]
            # Work directly from material totals, including unequal phase lengths.
            metric["welfare"] = (metric["consumption"] - .5 * metric["shortfall"]) / (
                config.members_per_society * ticks)
            metric["welfare_with_infrastructure"] = metric["welfare"] + .03 * metric["infrastructure"]
            metric["ticks"] = ticks
            metric["consumption_per_member_tick"] = metric["consumption"] / (config.members_per_society * ticks)
            metric["shortfall_per_member_tick"] = metric["shortfall"] / (config.members_per_society * ticks)
        society["adaptation"] = society["post"]["welfare"] - society["pre"]["welfare"]
        society["normalized_mean_individual_utility"] = society["mean_individual_utility"] / config.ticks
    for member in result["member_metrics"]:
        member["normalized_utility"] = member["utility"] / config.ticks
    societies = result["society_metrics"]
    for key, phase in (("mean_welfare", "overall"), ("pre_welfare", "pre"), ("post_welfare", "post")):
        result["aggregate"][key] = sum(s[phase]["welfare"] for s in societies) / config.n_societies
    result["aggregate"]["normalized_mean_individual_utility"] = result["aggregate"]["mean_individual_utility"] / config.ticks
    result["study"] = {
        "version": STUDY_VERSION,
        "scenario": deepcopy(scenario),
        "disturbance_enabled": disturbance,
        "phase_ticks": phase_ticks,
        "institution_objective": "(consumption - 0.5 * shortfall) / (members * ticks)",
        "member_objective": "(consumption + 0.2 * terminal_wealth) / ticks",
        "infrastructure_reward_coefficient": 0.0,
        "counterfactual_note": "No-drought phases use the same scheduled split; only the exogenous multiplier is disabled.",
    }
    result["digest"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result
