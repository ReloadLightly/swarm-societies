"""Prospective, nonadaptive ecological and incentive qualification registry."""
from __future__ import annotations

from dataclasses import asdict, replace
from copy import deepcopy
import hashlib

from .engine import Config

VERSION = "commons-v3-qualification-v1"
CONTROLS = (
    {"id": "fixed_floor", "parameters": {"reserve_ticks": 2, "stock_floor_fraction": .5, "route_mode": "net_yield"}},
    {"id": "selected", "parameters": {"reserve_ticks": 4, "stock_floor_fraction": .5, "route_mode": "nearest"}},
)
RATES = (.12, .24, .36)
NEEDS = (.8, 1.2, 1.6)
PEER_COUNTS = (0, 6, 12, 18, 23)
WEALTH_WEIGHTS = (0., .05, .2)
REFERENCE = {"renewal_rate": .24, "need": 1.2}
SENSITIVITIES = (
    ("long_horizon", {}, 512),
    ("small_inventory", {"inventory_capacity": 8.}, 256),
    ("lower_stock", {"initial_patch_stock": 22.}, 256),
    ("keyed_priority", {"contention": "keyed_priority"}, 256),
    ("additive", {"renewal_law": "additive"}, 256),
)
SELECTION_SHA256 = "4665d982a65e08ac65dc0244b341a0cf519da2f417964b65414d4e271369cadc"


def focal_and_peers(seed, index, n=24):
    """Evaluator-only, outcome-independent identities; nested peer sets."""
    focal = (7 * index) % n
    peers = sorted((i for i in range(n) if i != focal), key=lambda i: (
        hashlib.sha256(f"commons-v3-qualification-peer-v1|{seed}|{i}".encode()).hexdigest(), i))
    return focal, peers


def cases(stage):
    if stage not in ("ecology", "incentive"):
        raise ValueError("unknown qualification stage")
    seeds = list(range(64001, 64017)) if stage == "ecology" else list(range(65001, 65017))
    base = Config(initial_patch_stock=40., need=1.2)
    rows = []

    def append(panel, cfg, horizon):
        for index, seed in enumerate(seeds):
            focal, peers = focal_and_peers(seed, index, cfg.n_agents)
            label = f"grid-r{cfg.renewal_rate:.2f}-n{cfg.need:.1f}" if panel == "grid" else panel
            rows.append({"id": f"{label}-s{seed}", "panel": panel, "seed": seed,
                         "focal_id": focal, "peer_order": peers, "horizon": horizon, "config": asdict(cfg)})

    for rate in RATES:
        for need in NEEDS:
            append("grid", replace(base, renewal_rate=rate, need=need), 512 if stage == "ecology" else 256)
    if stage == "incentive":
        for panel, updates, horizon in SENSITIVITIES:
            append(panel, replace(base, **updates), horizon)
    return rows


def conditions(stage, case):
    """Each arm specifies an exact focal/peer intervention, never inferred from outcomes."""
    if stage == "ecology":
        return [{"id": "all_restrained", "peer_count": 0, "focal_aggressive": False, "aggressive_ids": []}]
    if stage != "incentive":
        raise ValueError("unknown qualification stage")
    pairs = [(k, focal) for k in PEER_COUNTS for focal in (False, True)] if case["panel"] == "grid" else [
        (0, False), (0, True), (23, True)]
    return [{"id": f"peers{k:02d}-focal{'A' if focal else 'R'}", "peer_count": k,
             "focal_aggressive": focal,
             "aggressive_ids": sorted(case["peer_order"][:k] + ([case["focal_id"]] if focal else []))}
            for k, focal in pairs]


def design(stage):
    physical = cases(stage)
    episodes = sum(len(CONTROLS) * len(conditions(stage, case)) for case in physical)
    ticks = sum(case["horizon"] * len(CONTROLS) * len(conditions(stage, case)) for case in physical)
    # t quantiles frozen before any qualification episode, SciPy 1.18.1, df=15.
    # Replays use these literals; library quantile drift cannot change a gate.
    return deepcopy({
        "version": VERSION, "stage": stage,
        "scope": "Prospective finite-horizon qualification of two frozen local controllers and one supplied aggressive variant; no institutional or evolutionary claim.",
        "controls": list(CONTROLS), "selected_navigation_selection_sha256": SELECTION_SHA256,
        "seeds": sorted({case["seed"] for case in physical}), "cases": physical,
        "rates": list(RATES), "needs": list(NEEDS), "reference": REFERENCE,
        "wealth_weights": list(WEALTH_WEIGHTS), "peer_counts": list(PEER_COUNTS),
        "condition_registry": {case["id"]: conditions(stage, case) for case in physical},
        "statistics": {"seed_count": 16, "degrees_of_freedom": 15, "alpha": .05,
                       "simultaneous_family_size": 194, "simultaneous_t_critical": 4.750567324005865,
                       "descriptive_t_critical": 2.131449545559776,
                       "family_components": {"ecology": 90, "primary_incentive": 54, "reference_robustness": 50},
                       "method": "Seed-level paired or single-condition Student-t intervals; two-sided Bonferroni union of 194 predeclared scalar intervals; approximate model-based coverage.",
                       "quantile_provenance": "scipy.stats.t.ppf(1-.05/(2*194),15) and t.ppf(.975,15); SciPy 1.18.1",
                       "pass_rule": "lower-bound endpoint: lower>=margin passes, upper<margin fails, otherwise unresolved; reverse inequalities for upper-bound endpoints; exact float comparison, no tolerance"},
        "ecology_thresholds": {"consumption_fraction": .95, "late_consumption_fraction": .95,
                               "late_minus_third_quarter_fraction": -.02, "late_stock_fraction": .20,
                               "late_depleted_patch_time_fraction_max": .10},
        "incentive_thresholds": {"focal_utility_gain_fraction": .01, "population_consumption_loss_fraction": .05,
                                 "population_late_consumption_loss_fraction": .05, "primary_wealth_weight": .05},
        "depletion_diagnostic": {"site_stock_below_capacity_fraction": .10, "minimum_sites_fraction": .5,
                                 "window": "latter_half", "minimum_consecutive_horizon_fraction": .125,
                                 "use": "descriptive; never an alternative route to passing consumption harm"},
        "adjacency": {"rule": "one horizontal or vertical step in the declared 3x3 grid", "must_include_reference": True,
                      "same_pair_both_controls_and_ecology_and_incentive": True},
        "robustness_panels": ["grid", "long_horizon", "small_inventory", "lower_stock", "keyed_priority"],
        "additive_control": "descriptive negative control, excluded from logistic robustness gates",
        "feasibility_targets": [1., .95], "ecology_horizons_for_certificates": [256, 512],
        "ledger_relative_tolerance": 1e-9, "maximum_tick_extraction_waste": 1e-9,
        "reference_frames_case": f"grid-r0.24-n1.2-s{64001 if stage == 'ecology' else 65001}",
        "counts": {"configurations": len(physical), "episodes": episodes, "physical_ticks": ticks,
                   "agent_decisions": sum(case["config"]["n_agents"] * case["horizon"] * len(CONTROLS) * len(conditions(stage, case)) for case in physical)},
        "failure_rule": "halt and preserve the bank on unexpected engineering or data failure; no dropping/replacement of cases; adverse scientific outcomes are valid complete results",
        "experimental_model_calls": 0, "evolutionary_runs": 0, "new_numerical_selection_runs": 0,
        "qualification_data": True,
    })
