"""Ticket D's bounded learning development menu and Gate G3.

Both L0 quantiles run on the same sixteen development cases. One quantile is
selected globally, strengthening the asocial reference; sharing arms inherit
it unchanged. If selected L0 meets the contracted triviality condition, the
runner stops before sharing and reports the prescribed fallback requirement.
No fresh evaluation, physics change, or model-driven search belongs here.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import sys

from . import engine_sites_v1 as engine
from . import worlds_sites_v1 as worlds
from . import consequence_sites_v1 as consequence
from .development_navigation_v1 import canonical, digest, read_case, _save_json, _save_record


VERSION = "commons-v3-learning-development-sites-v1"
SEEDS = consequence.SEEDS
CONDITIONS, NEEDS = consequence.CONDITIONS, consequence.NEEDS
HORIZON, PHI, QUANTILES = 512, .375, (.25, .5)
ARMS = ("L0", "L1", "L2", "L3", "L2-biased", "L3-biased")
BIASED_IDS = (0, 6, 12, 18)
BELIEF_CHECKPOINTS = (0, 16, 32, 64, 128, 256, 384, 512)
COUNTERS = ("eligible", "clean_own", "clean_receipts", "new_relay", "duplicates",
            "confounded", "belief_messages")
PAIR_COLUMNS = ("agent", "site", "median", "lower90", "upper90", "directly_seen",
                "has_posterior", "absolute_log_error", "covered90")


def candidate_jobs(q=None, arms=("L0",)):
    if q is not None and (type(q) not in (int, float) or q not in QUANTILES):
        raise ValueError("unknown contracted quantile")
    if type(arms) not in (tuple, list) or not arms or len(set(arms)) != len(arms) or any(a not in ARMS for a in arms):
        raise ValueError("unknown or duplicate development arm")
    return [{"condition": condition, "need": need, "seed": seed, "arm": arm, "phi": PHI, "q": value}
            for arm in arms for value in (QUANTILES if q is None else (q,))
            for condition in CONDITIONS for need in NEEDS for seed in SEEDS]


def case_id(job):
    return (f"{job['condition']}-n{job['need']:g}-s{job['seed']}-{job['arm']}"
            f"-phi{job['phi']:g}-q{job['q']:g}")


def physical_initial_digest(snapshot):
    """B's unused message-count limit differs; every other field must match."""
    state = deepcopy(snapshot["state"])
    if state["config"].pop("max_messages") not in (1, 4):
        raise ValueError("unexpected initial message capability")
    return digest(state)


def _values(posterior):
    median = posterior.quantile(.5)
    lo, hi = posterior.interval(level=.9)
    if (not all(math.isfinite(v) and 8. <= v <= 100. for v in (median, lo, hi))
            or lo > hi):
        raise ValueError("invalid posterior measurement")
    return median, lo, hi


class BeliefMetrics:
    """Evaluator-only, all-site measurements with unchanged-posterior caching.

    Missing site beliefs use an external prior summary. Measuring a hidden
    site never creates a posterior inside a policy or reveals that site's
    capacity. Time-to-accuracy includes priors already accurate at tick zero.
    """

    def __init__(self, capacities, population, biased_ids=(), prior_factory=None):
        if prior_factory is None:
            from .policies_sharing_sites_v1 import new_prior
            prior_factory = new_prior
        self.capacities = tuple(capacities)
        if (not self.capacities or any(not math.isfinite(k) or not 8. <= k <= 100. for k in self.capacities)
                or type(population) is not int or population < 1):
            raise ValueError("invalid evaluator population or capacities")
        self.population, self.biased_ids = population, frozenset(biased_ids)
        if any(type(i) is not int or not 0 <= i < population for i in self.biased_ids):
            raise ValueError("invalid biased cohort")
        self.priors = {biased: _values(prior_factory(site=0, biased=biased)) for biased in (False, True)}
        self.seen = [set() for _ in range(population)]
        self.cache, self.first_accurate = {}, {}
        self.last_tick = -1

    def observe_sites(self, packets):
        if len(packets) != self.population:
            raise ValueError("one packet per individual is required")
        for identity, packet in enumerate(packets):
            if packet["self"]["id"] != identity:
                raise ValueError("packets are not in individual order")
            self.seen[identity].update(site["id"] for site in packet["sites"])

    def measure(self, policies, tick, raw=False):
        if len(policies) != self.population or type(tick) is not int or tick <= self.last_tick:
            raise ValueError("belief measurements require consecutive ordered individuals and increasing ticks")
        self.last_tick = tick
        errors, covers, widths, seen_errors, seen_covers = [], [], [], [], []
        medians_by_site = [[] for _ in self.capacities]
        pair_rows, by_cohort = [], {"biased": [], "other": []}
        has_posterior = 0
        for agent, policy in enumerate(policies):
            biased = agent in self.biased_ids
            for site, truth in enumerate(self.capacities):
                posterior = policy.posteriors.get(site)
                if posterior is None:
                    median, lo, hi = self.priors[biased]
                else:
                    has_posterior += 1
                    revision = posterior.revision
                    cached = self.cache.get((agent, site))
                    if cached is None or cached[0] is not posterior or cached[1] != revision:
                        cached = posterior, revision, _values(posterior)
                        self.cache[agent, site] = cached
                    median, lo, hi = cached[2]
                error, covered = abs(math.log(median / truth)), lo <= truth <= hi
                direct = site in self.seen[agent]
                errors.append(error)
                covers.append(covered)
                widths.append(math.log(hi / lo))
                medians_by_site[site].append(math.log(median))
                by_cohort["biased" if biased else "other"].append(error)
                if direct:
                    seen_errors.append(error)
                    seen_covers.append(covered)
                if .9 * truth <= median <= 1.1 * truth:
                    self.first_accurate.setdefault((agent, site), tick)
                if raw:
                    pair_rows.append([agent, site, median, lo, hi, direct, posterior is not None, error, covered])
        counts = {key: sum(policy.counters.get(key, 0) for policy in policies) for key in COUNTERS}
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("evidence counters must be nonnegative integers")
        frame = {"tick": tick, "agent_site_pairs": len(errors), "directly_seen_pairs": len(seen_errors),
                 "pairs_with_posterior": has_posterior,
                 "capacity_absolute_log_error": st.mean(errors), "coverage90": st.mean(covers),
                 "mean_log_interval_width": st.mean(widths),
                 "between_agent_log_median_dispersion": st.mean(st.pstdev(values) for values in medians_by_site),
                 "seen_only_absolute_log_error": st.mean(seen_errors) if seen_errors else None,
                 "seen_only_coverage90": st.mean(seen_covers) if seen_covers else None,
                 "biased_absolute_log_error": st.mean(by_cohort["biased"]) if by_cohort["biased"] else None,
                 "other_absolute_log_error": st.mean(by_cohort["other"]) if by_cohort["other"] else None,
                 "ever_within10_fraction": len(self.first_accurate) / len(errors),
                 "clean_eligible_fraction": ((counts["clean_own"] + counts["clean_receipts"]) / counts["eligible"]
                                             if counts["eligible"] else None),
                 **{"evidence_" + key: value for key, value in counts.items()}}
        return frame, pair_rows

    def first_accuracy_rows(self):
        return [[agent, site, self.first_accurate.get((agent, site))]
                for agent in range(self.population) for site in range(len(self.capacities))]


def _material_frame(result, actions, patch_at, capacities, phi):
    state, ledger = result.state, result.ledger
    food_shortfall = []
    for agent, row in zip(state.agents, ledger.agents):
        site = patch_at.get((agent.x, agent.y))
        if (site is not None and row.shortfall > 1e-12
                and ledger.patches[site].stock_after_harvest > phi * capacities[site]):
            food_shortfall.append(row.shortfall)
    attempted = [len(text.encode("utf-8")) for action in actions for _, text in action.messages]
    paid = sum(row.message_bytes for row in ledger.agents)
    delivered = sum(row.byte_count for row in ledger.messages if row.delivered)
    if paid != delivered or sum(attempted) != sum(row.byte_count for row in ledger.messages):
        raise ValueError("message actions, delivery receipts and paid bytes differ")
    return {"tick": state.tick, "consumption": ledger.consumption,
            "starvation_next_to_food_shortfall": math.fsum(food_shortfall),
            "starvation_next_to_food_agents": len(food_shortfall),
            "collapsed_sites": sum(p.stock < .1 * capacities[p.id] for p in state.patches),
            "message_attempts": len(attempted), "message_attempted_bytes": sum(attempted),
            "messages_delivered": sum(row.delivered for row in ledger.messages),
            "message_paid_bytes": paid, "message_delivered_bytes": delivered,
            "message_cost": ledger.message_cost}


def _record_episode(job, state, policies, horizon=HORIZON):
    from .observations_messages_sites_v1 import observations
    initial = engine.snapshot(state)
    capacities, population = state.config.site_capacities, len(state.agents)
    biased = tuple(identity for identity in BIASED_IDS if identity < population) if job["arm"].endswith("-biased") else ()
    measurement = BeliefMetrics(capacities, population, biased)
    trajectory = hashlib.sha256(canonical(initial) + b"\n")
    weather = hashlib.sha256()
    frames, epistemic, checkpoints = [], [], []
    late_baseline, previous_result = [0.] * population, None
    max_residual = 0.
    patch_at = {(p.x, p.y): p.id for p in state.patches}
    for tick in range(horizon + 1):
        packets = observations(state, previous_result)
        measurement.observe_sites(packets)
        if tick == horizon:
            for policy, packet in zip(policies, packets):
                policy.observe(packet)
            actions = None
        else:
            actions = tuple(policy(packet) for policy, packet in zip(policies, packets))
        frame, pairs = measurement.measure(policies, tick, raw=tick in BELIEF_CHECKPOINTS or tick == horizon)
        epistemic.append(frame)
        if pairs:
            checkpoints.append({"tick": tick, "pairs": pairs})
        if tick == horizon:
            trajectory.update(canonical({"terminal_observation_tick": tick,
                                          "updates": [policy.last_updates for policy in policies],
                                          "beliefs": frame}) + b"\n")
            break
        result = engine.step(state, actions)
        state, previous_result = result.state, result
        trajectory.update(canonical({"tick": tick, "actions": [asdict(a) for a in actions],
            "updates": [policy.last_updates for policy in policies], "beliefs": frame,
            "ledger": asdict(result.ledger)}) + b"\n")
        weather.update(canonical([p.weather for p in result.ledger.patches]) + b"\n")
        frames.append(_material_frame(result, actions, patch_at, capacities, job["phi"]))
        max_residual = max(max_residual, abs(result.ledger.residual),
                           *(abs(row.residual) for row in result.ledger.agents),
                           *(abs(row.residual) for row in result.ledger.patches))
        if state.tick == 3 * horizon // 4:
            late_baseline = [agent.consumption for agent in state.agents]
    late_ticks = horizon - 3 * horizon // 4
    agents = [{"id": a.id, "biased": a.id in biased,
               "share_of_need": a.consumption / (horizon * job["need"]),
               "final_quarter_share_of_need": (a.consumption - late_baseline[a.id]) / (late_ticks * job["need"])}
              for a in state.agents]
    denominator = population * horizon * job["need"]
    summary = {"share_of_need": st.mean(row["share_of_need"] for row in agents),
        "final_quarter_share_of_need": st.mean(row["final_quarter_share_of_need"] for row in agents),
        "first64_share_of_need": math.fsum(row["consumption"] for row in frames[:64]) / (population * min(64, horizon) * job["need"]),
        "starvation_next_to_food_share_of_need": math.fsum(f["starvation_next_to_food_shortfall"] for f in frames) / denominator,
        "starvation_next_to_food_agent_tick_fraction": sum(f["starvation_next_to_food_agents"] for f in frames) / (population * horizon),
        "local_collapse_site_tick_fraction": sum(f["collapsed_sites"] for f in frames) / (len(capacities) * horizon),
        "message_attempts": sum(f["message_attempts"] for f in frames),
        "messages_delivered": sum(f["messages_delivered"] for f in frames),
        "message_attempted_bytes": sum(f["message_attempted_bytes"] for f in frames),
        "message_paid_bytes": sum(f["message_paid_bytes"] for f in frames),
        "message_delivered_bytes": sum(f["message_delivered_bytes"] for f in frames),
        "message_cost": math.fsum(f["message_cost"] for f in frames),
        "agent_consumption_share_min": min(a["share_of_need"] for a in agents),
        "agent_consumption_share_max": max(a["share_of_need"] for a in agents),
        "agent_consumption_share_sd": st.pstdev(a["share_of_need"] for a in agents),
        "max_ledger_residual": max_residual}
    for name, predicate in (("biased", lambda a: a["biased"]), ("other", lambda a: not a["biased"])):
        cohort = [a for a in agents if predicate(a)]
        summary[name + "_share_of_need"] = st.mean(a["share_of_need"] for a in cohort) if cohort else None
        for suffix, operation in (("min", min), ("max", max), ("sd", st.pstdev)):
            summary[name + "_agent_consumption_share_" + suffix] = operation(a["share_of_need"] for a in cohort) if cohort else None
    for key in ("capacity_absolute_log_error", "coverage90", "mean_log_interval_width",
                "between_agent_log_median_dispersion", "ever_within10_fraction"):
        summary["terminal_" + key] = epistemic[-1][key]
        summary["time_mean_" + key] = st.mean(frame[key] for frame in epistemic[1:])
    summary.update({key: value for key, value in epistemic[-1].items() if key.startswith("evidence_")})
    summary["clean_eligible_fraction"] = epistemic[-1]["clean_eligible_fraction"]
    summary["first_within10_mean_tick_if_reached"] = st.mean(measurement.first_accurate.values()) if measurement.first_accurate else None
    for key in ("seen_only_absolute_log_error", "seen_only_coverage90", "biased_absolute_log_error", "other_absolute_log_error"):
        summary["terminal_" + key] = epistemic[-1][key]
    return {"version": VERSION, "job": job, "horizon": horizon,
            "initial_snapshot": initial, "final_snapshot": engine.snapshot(state),
            "initial_physical_sha256": physical_initial_digest(initial),
            "trajectory_sha256": trajectory.hexdigest(), "weather_sha256": weather.hexdigest(),
            "final_policy_memory_sha256": [digest(policy.memory()) for policy in policies],
            "summary": summary, "agents": agents, "ticks": frames, "belief_ticks": epistemic,
            "belief_pair_columns": list(PAIR_COLUMNS), "belief_checkpoints": checkpoints,
            "first_within10_columns": ["agent", "site", "first_tick_or_null"],
            "first_within10": measurement.first_accuracy_rows()}


def run_episode(job):
    if job not in candidate_jobs(arms=ARMS):
        raise ValueError("case is outside the contracted development menu")
    try:
        from .policies_sharing_sites_v1 import LearningForager
        state = worlds.initialize(job["condition"], job["need"], job["seed"])
        state = replace(state, config=replace(state.config, max_messages=4))
        base_arm = job["arm"].split("-")[0]
        policies = [LearningForager(base_arm, q=job["q"], phi=job["phi"],
                    biased=job["arm"].endswith("-biased") and agent.id in BIASED_IDS) for agent in state.agents]
        return _record_episode(job, state, policies)
    except Exception as error:
        raise RuntimeError("learning episode failed: " + case_id(job)) from error


def _require_jobs(rows, jobs):
    actual = [canonical(row["job"]) for row in rows]
    if len(actual) != len(jobs) or set(actual) != {canonical(job) for job in jobs}:
        raise ValueError("learning development case inventory differs")
    for row in rows:
        if any(value is not None and (type(value) not in (int, float) or not math.isfinite(value))
               for value in row["summary"].values()):
            raise ValueError("summary must contain finite scalar measurements or absent-cohort nulls")


def select_quantile(rows):
    candidates = [row for row in rows if row["job"]["arm"] == "L0"]
    _require_jobs(candidates, candidate_jobs())
    scores = []
    for q in QUANTILES:
        group = [row for row in candidates if row["job"]["q"] == q]
        scores.append({"q": q, "episodes": len(group),
                       "share_of_need": st.mean(row["summary"]["share_of_need"] for row in group),
                       "final_quarter_share_of_need": st.mean(row["summary"]["final_quarter_share_of_need"] for row in group)})
    winner = min(scores, key=lambda row: (-row["share_of_need"], -row["final_quarter_share_of_need"], row["q"]))
    return {"selected": winner["q"], "candidates": scores,
            "rule": "L0 equal-weight consumption over all sixteen cases; final-quarter mean then smaller q break ties; sharing inherits q"}


def descriptive(values):
    values = [value for value in values if value is not None]
    if not values:
        return {"n": 0, "mean": None, "ci95": None, "min": None, "max": None}
    mean = st.mean(values)
    half = 3.182446305284263 * st.stdev(values) / 2 if len(values) == 4 else None
    return {"n": len(values), "mean": mean, "ci95": None if half is None else [mean - half, mean + half],
            "min": min(values), "max": max(values)}


def first64(row):
    if len(row["ticks"]) < 64 or [frame["tick"] for frame in row["ticks"][:64]] != list(range(1, 65)):
        raise ValueError("G3 requires all first sixty-four physical ticks")
    population = len(row["initial_snapshot"]["state"]["agents"])
    return math.fsum(frame["consumption"] for frame in row["ticks"][:64]) / (population * 64 * row["job"]["need"])


def g3(rows, references, q):
    selected = [row for row in rows if row["job"]["arm"] == "L0" and row["job"]["q"] == q]
    _require_jobs(selected, candidate_jobs(q))
    oracle = [row for row in references if row["job"]["arm"] == "R-oracle"]
    if len(oracle) != 16:
        raise ValueError("G3 requires the sixteen saved oracle references")
    cells = []
    for condition in CONDITIONS:
        for need in NEEDS:
            keys = lambda row: (row["job"]["condition"], row["job"]["need"])
            own = {row["job"]["seed"]: first64(row) for row in selected if keys(row) == (condition, need)}
            known = {row["job"]["seed"]: first64(row) for row in oracle if keys(row) == (condition, need)}
            if set(own) != set(SEEDS) or set(known) != set(SEEDS):
                raise ValueError("G3 paired seed inventory differs")
            differences = [{"seed": seed, "oracle": known[seed], "L0": own[seed],
                            "oracle_minus_L0": known[seed] - own[seed]} for seed in SEEDS]
            # Direct comparison to the oracle-minus-margin boundary avoids
            # rounding a displayed decimal gap before applying the criterion.
            within = st.mean(own.values()) >= st.mean(known.values()) - .02
            cells.append({"condition": condition, "need": need, "paired": differences,
                          "oracle_minus_L0": descriptive(row["oracle_minus_L0"] for row in differences),
                          "within_0.02": within})
    trivial = all(cell["within_0.02"] for cell in cells)
    return {"q": q, "measurement": "cumulative consumption/need over physical ticks1..64; four-seed cell means",
            "threshold": .02, "cells": cells, "trivial": trivial, "passed": not trivial,
            "decision": "requires prescribed unknown-r fallback; do not run sharing" if trivial
                        else "nontriviality gate permits the declared sharing development cases"}


def load_references(root):
    root = Path(root)
    saved = json.loads((root / "summary.json").read_text())
    if (saved["oracle_selection"]["selected"] != PHI or saved["fixed_selection"]["selected"] != 40.
            or not saved["G1"]["passed"]):
        raise ValueError("Ticket B selection or G1 differs from the completed checkpoint")
    jobs = consequence.candidate_jobs("R-oracle")
    jobs = [job for job in jobs if job["phi"] == PHI]
    jobs += [job for job in consequence.candidate_jobs("R-fixed", PHI) if job["fixed_capacity"] == 40.]
    jobs += consequence.candidate_jobs("R-greedy", PHI)
    rows = [read_case(consequence._path(root, job)) for job in jobs]
    consequence._require_jobs(rows, jobs)
    if any(row["horizon"] != HORIZON for row in rows):
        raise ValueError("reference horizon differs")
    return rows, {"study_version": saved["version"], "summary_sha256": digest(saved),
                  "selected_cases": len(rows),
                  "case_sha256": {consequence.case_id(row["job"]): digest(row) for row in rows}}


def _paired_worlds(rows, references):
    for condition in CONDITIONS:
        for need in NEEDS:
            for seed in SEEDS:
                group = [row for row in [*rows, *references]
                         if (row["job"]["condition"], row["job"]["need"], row["job"]["seed"]) == (condition, need, seed)]
                if (len({physical_initial_digest(row["initial_snapshot"]) for row in group}) != 1
                        or len({row["weather_sha256"] for row in group}) != 1):
                    raise ValueError("paired physical initialization or weather differs")


def development_contrasts(rows):
    """Paired developmental analogues, never the evaluation Holm analysis."""
    if {row["job"]["arm"] for row in rows} == {"L0"}:
        return {"status": "sharing not run because G3 requires the fallback", "contrasts": {}}
    indexed = {(row["job"]["arm"], row["job"]["condition"], row["job"]["need"], row["job"]["seed"]): row
               for row in rows}

    def value(arm, condition, need, seed, metric):
        record = indexed[arm, condition, need, seed]
        if metric == "error_tick128":
            frame = record["belief_ticks"][128]
            if frame["tick"] != 128:
                raise ValueError("P3 requires belief measurements after observing tick128")
            return frame["capacity_absolute_log_error"]
        return record["summary"][metric]

    def difference(left, right, condition, need, seed, metric):
        return value(left, condition, need, seed, metric) - value(right, condition, need, seed, metric)

    def paired(function):
        values = [{"seed": seed, "difference": function(seed)} for seed in SEEDS]
        return {"paired": values, "statistics": descriptive(row["difference"] for row in values)}

    def pool(left, right, seed, metric):
        return st.mean(difference(left, right, "wide", need, seed, metric) for need in NEEDS)

    return {"status": "descriptive development analogues after selection; no p-values or Holm tests",
            "contrasts": {
                "P1": {"measure": "L2-L0 whole-run consumption/need, wide need1.6",
                       **paired(lambda seed: difference("L2", "L0", "wide", 1.6, seed, "share_of_need"))},
                "P2": {"measure": "wide-minus-moderate L2-L0 whole-run consumption/need, need1.6",
                       **paired(lambda seed: difference("L2", "L0", "wide", 1.6, seed, "share_of_need")
                                             - difference("L2", "L0", "moderate", 1.6, seed, "share_of_need"))},
                "P3": {"measure": "L1-L0 all-agent/all-site absolute log-median capacity error after observation128, wide",
                       "demand_pooling": "equal-weight needs1.2/1.6 within each seed, then four paired seeds",
                       **paired(lambda seed: pool("L1", "L0", seed, "error_tick128"))},
                "P4": {"measure": "L3-biased minus L2-biased whole-run consumption/need, wide need1.6",
                       **paired(lambda seed: difference("L3-biased", "L2-biased", "wide", 1.6, seed, "share_of_need"))},
                "P5": {"measure": "L3-L2 inclusive90% interval coverage, wide",
                       "demand_pooling": "equal-weight needs1.2/1.6 within each seed, then four paired seeds",
                       "endpoint_status": "both endpoints descriptive; primary time endpoint remains for the pre-freeze review",
                       "time_mean_ticks1_to512": paired(lambda seed: pool("L3", "L2", seed, "time_mean_coverage90")),
                       "terminal_tick512": paired(lambda seed: pool("L3", "L2", seed, "terminal_coverage90"))}}}


def summarize(rows, references, reference_record):
    selection = select_quantile(rows)
    q = selection["selected"]
    gates = [g3(rows, references, candidate) for candidate in QUANTILES]
    gate = next(result for result in gates if result["q"] == q)
    jobs = candidate_jobs() + ([] if gate["trivial"] else candidate_jobs(q, ARMS[1:]))
    _require_jobs(rows, jobs)
    _paired_worlds(rows, references)
    selected = [row for row in rows if row["job"]["q"] == q]
    available_arms = ("L0",) if gate["trivial"] else ARMS
    cells = []
    for condition in CONDITIONS:
        for need in NEEDS:
            group = [row for row in selected if (row["job"]["condition"], row["job"]["need"]) == (condition, need)]
            by_arm = {arm: {row["job"]["seed"]: row for row in group if row["job"]["arm"] == arm}
                      for arm in available_arms}
            contrasts = {}
            for left, right in (("L1", "L0"), ("L2", "L0"), ("L3", "L2"), ("L3-biased", "L2-biased")):
                if left not in by_arm:
                    continue
                keys = ("share_of_need", "final_quarter_share_of_need", "terminal_capacity_absolute_log_error",
                        "time_mean_capacity_absolute_log_error", "terminal_coverage90", "time_mean_coverage90")
                differences = [{"seed": seed, **{key: by_arm[left][seed]["summary"][key] - by_arm[right][seed]["summary"][key]
                                                for key in keys}} for seed in SEEDS]
                contrasts[left + "_minus_" + right] = {"paired": differences,
                    "statistics": {key: descriptive(row[key] for row in differences) for key in keys}}
            arm_series = {}
            for arm, seeds in by_arm.items():
                source = next(iter(seeds.values()))["belief_ticks"]
                if any([f["tick"] for f in row["belief_ticks"]] != list(range(HORIZON + 1)) for row in seeds.values()):
                    raise ValueError("belief trajectory lacks post-observation ticks")
                # Full per-tick scalars remain in every raw case. Compact
                # aggregates retain the declared epistemic checkpoints.
                arm_series[arm] = [{"tick": tick, **{key: descriptive(row["belief_ticks"][tick][key] for row in seeds.values())
                                  for key in source[tick] if key != "tick"}} for tick in BELIEF_CHECKPOINTS]
            refs = [row for row in references if (row["job"]["condition"], row["job"]["need"]) == (condition, need)]
            cells.append({"condition": condition, "need": need,
                          "arms": {arm: {key: descriptive(row["summary"][key] for row in seeds.values())
                                          for key in next(iter(seeds.values()))["summary"]}
                                   for arm, seeds in by_arm.items()},
                          "reference_consumption": {arm: descriptive(row["summary"]["share_of_need"] for row in refs if row["job"]["arm"] == arm)
                                                    for arm in ("R-oracle", "R-fixed", "R-greedy")},
                          "contrasts": contrasts, "belief_trajectories": arm_series})
    return {"version": VERSION, "scope": "development on four reused seeds; intervals are descriptive after selection; no evaluation Holm tests",
            "seeds": list(SEEDS), "horizon": HORIZON, "phi": PHI, "quantile_selection": selection,
            "episodes": len(rows), "selected_episodes": len(selected), "reference_episodes_reused": len(references),
            "biased_ids": list(BIASED_IDS), "references": reference_record, "G3": gate,
            "G3_both_quantiles": gates, "cells": cells, "development_contrasts": development_contrasts(selected),
            "belief_denominator": "all24 agents×all16 sites, including unseen priors; seen-only measurements are supplementary",
            "belief_timing": "tick t after observing tick-t stocks/messages and before tick-t action; terminal observation512 executes no new action",
            "first_within10_definition": "first post-observation tick median in [0.9K,1.1K], including already-accurate priors at tick0; null is right-censored",
            "clean_fraction_denominator": "own eligible consecutive on-site transitions; relayed events reported separately",
            "experimental_model_calls": 0, "evolutionary_runs": 0, "fresh_evaluation_episodes": 0}


def _path(output, job):
    return Path(output) / "cases" / (case_id(job) + ".json.gz")


def _workers(workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("workers must be between one and eight")


def _run_jobs(output, jobs, workers):
    rows = []
    # Existing complete records must replay before recovery preserves them.
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for number, (job, replay) in enumerate(zip(jobs, pool.map(run_episode, jobs)), start=1):
            path = _path(output, job)
            if path.exists():
                if canonical(read_case(path)) != canonical(replay):
                    raise ValueError("saved episode differs during recovery: " + case_id(job))
            else:
                _save_record(path, replay)
            rows.append(replay)
            print(f"completed {number}/{len(jobs)} {case_id(job)}", file=sys.stderr, flush=True)
    return rows


def _require_paths(output, jobs):
    if set((Path(output) / "cases").glob("*.json.gz")) != {_path(output, job) for job in jobs}:
        raise ValueError("saved development case paths differ from declared execution")


def run(output, reference_root="evidence/commons-v3-world-model-consequence-v1", workers=2):
    _workers(workers)
    output = Path(output)
    if (output / "summary.json").exists():
        raise ValueError("completed learning development; use verify")
    references, reference_record = load_references(reference_root)
    _paired_worlds([], references)
    print("running 32 L0 candidate episodes before global q selection and G3", file=sys.stderr, flush=True)
    rows = _run_jobs(output, candidate_jobs(), workers)
    selection = select_quantile(rows)
    _paired_worlds(rows, references)
    gate = g3(rows, references, selection["selected"])
    print(f"selected q={selection['selected']:g}; {gate['decision']}", file=sys.stderr, flush=True)
    if not gate["trivial"]:
        print("running the declared 80 sharing episodes", file=sys.stderr, flush=True)
        rows.extend(_run_jobs(output, candidate_jobs(selection["selected"], ARMS[1:]), workers))
    summary = summarize(rows, references, reference_record)
    jobs = candidate_jobs() + ([] if gate["trivial"] else candidate_jobs(selection["selected"], ARMS[1:]))
    _require_paths(output, jobs)
    _save_json(output / "summary.json", summary)
    return summary


def verify(output, reference_root="evidence/commons-v3-world-model-consequence-v1", workers=2):
    _workers(workers)
    output = Path(output)
    saved = json.loads((output / "summary.json").read_text())
    references, reference_record = load_references(reference_root)
    q = saved["quantile_selection"]["selected"]
    jobs = candidate_jobs() + ([] if saved["G3"]["trivial"] else candidate_jobs(q, ARMS[1:]))
    _require_paths(output, jobs)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for number, (job, replay) in enumerate(zip(jobs, pool.map(run_episode, jobs)), start=1):
            if canonical(read_case(_path(output, job))) != canonical(replay):
                raise ValueError("exact development replay differs: " + case_id(job))
            rows.append(replay)
            print(f"verified {number}/{len(jobs)} {case_id(job)}", file=sys.stderr, flush=True)
    summary = summarize(rows, references, reference_record)
    if canonical(summary) != canonical(saved):
        raise ValueError("development aggregate differs on replay")
    return {"version": VERSION, "exact_episodes": len(rows), "reference_cases_reused": len(references),
            "summary_sha256": digest(saved), "selected_q": q, "G3": summary["G3"]}
