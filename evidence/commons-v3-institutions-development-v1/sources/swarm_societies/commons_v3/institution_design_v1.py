"""Finite, prospective development of supplied optional-charter policy bundles."""
from dataclasses import asdict, replace
from copy import deepcopy
import hashlib

from .engine import Config
from .politics_v1 import Charter, PoliticalConfig

VERSION = "commons-v3-institutions-development-v1"
SEEDS = (93001, 93002, 93003, 93004)
CONTROLS = (
    {"id": "fixed_floor", "parameters": {"reserve_ticks": 2, "stock_floor_fraction": .5, "route_mode": "net_yield"}},
    {"id": "selected", "parameters": {"reserve_ticks": 4, "stock_floor_fraction": .5, "route_mode": "nearest"}},
)
ARMS = ("frozen", "decentralized", "charter_unmonitored", "charter_enforced")
CONTRASTS = (("decentralized", "frozen"), ("charter_unmonitored", "decentralized"),
             ("charter_enforced", "decentralized"), ("charter_enforced", "charter_unmonitored"))
SELECTION_SHA256 = "4665d982a65e08ac65dc0244b341a0cf519da2f417964b65414d4e271369cadc"


def cases():
    rows = []
    for control in CONTROLS:
        for capacity in (8., 80.):
            for seed in SEEDS:
                order = sorted(range(24), key=lambda a: (
                    hashlib.sha256(f"{VERSION}|cohort|{seed}|{a}".encode()).hexdigest(), a))
                config = replace(Config(), need=1.2, initial_patch_stock=40., inventory_capacity=capacity)
                for stubborn in (0, 6, 24):
                    for arm in (("all_stubborn",) if stubborn == 24 else ARMS):
                        rows.append({"id": f"{control['id']}-cap{capacity:g}-k{stubborn:02d}-s{seed}-{arm}",
                            "control": control["id"], "parameters": deepcopy(control["parameters"]),
                            "capacity": capacity, "stubborn_count": stubborn, "seed": seed, "arm": arm,
                            "stubborn_ids": sorted(order[:stubborn]), "horizon": 256,
                            "config": asdict(config), "political_config": asdict(PoliticalConfig()),
                            "charter": asdict(Charter())})
    return rows


def design():
    return {"version": VERSION, "scope": "Prospective development of supplied policy bundles, not independent qualification or an isolated effect of organization.",
        "seeds": list(SEEDS), "controls": deepcopy(list(CONTROLS)), "arms": list(ARMS),
        "capacities": [8., 80.], "stubborn_counts": [0, 6], "anchor_stubborn_count": 24,
        "horizon": 256, "late_window": 64, "wealth_weights": [0., .05, .2],
        "contrasts": [list(c) for c in CONTRASTS], "cases": cases(),
        "counts": {"episodes": 144, "physical_ticks": 36864, "agent_decisions": 884736},
        "charter": asdict(Charter()), "political_config": asdict(PoliticalConfig()),
        "behavior": "Nonstubborn responsive rules retain aggressive=False competent navigation in every arm. Stubborn agents use aggressive=True with no reporting, custody or political action in every arm.",
        "cache": {"maximum_need_ticks": 2., "deposit_above_need_ticks": 6., "retrieve_below_need_ticks": 2.,
                  "scope": "Same conservative legal local rule in decentralized and both charter arms; frozen anchor has no added policy actions."},
        "report_period": 4, "anticipated_monitoring_probability": .5,
        "terminal_ownership": "Book value = carried inventory + own cache + own active/released collateral claims + equal share of active treasury among current members. All components separate; no world mutation or redemption, no probability discount, no claim of accessible consumption.",
        "statistics": "Four seed values, means and min/max; paired differences within each background/capacity/cohort cell. No confidence intervals, pass thresholds, optimized policy selection or pooled independent sample claim.",
        "primary_outcomes": ["population consumption/need", "population final-64-tick consumption/need",
                             "original eligible cohort consumption/need", "original stubborn cohort consumption/need"],
        "failure_rule": "Engineering failure halts and preserves work; no seed replacement or outcome-dependent extension. No institutions, ignored quotas, depleted collateral, null effects and losses are valid outcomes.",
        "experimental_model_calls": 0, "evolutionary_runs": 0, "policy_selection_runs": 0,
        "qualification_data": False}
