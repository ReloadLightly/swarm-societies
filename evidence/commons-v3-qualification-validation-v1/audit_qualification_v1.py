#!/usr/bin/env python3
"""Independent stdlib reconstruction of recorded commons-v3 qualification data.

No project implementation is imported and no policies or worlds execute.
Numerical tolerance applies only to independently calculated diagnostics;
bindings, counts, exact resource comparisons and gate decisions are strict.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

ENGINE = "commons-v3-physical-v1"
VERSION = "commons-v3-independent-qualification-audit-v1"
WEIGHTS = (0., .05, .2)
FIELDS = ("consumption", "shortfall", "movement_cost", "message_cost", "harvested",
          "harvest_cost", "waste", "transfer_in", "transfer_out")
ENDPOINTS = ("consumption_per_tick", "shortfall_per_tick", "late_consumption_per_tick",
             "late_shortfall_per_tick", "terminal_inventory")
RELATIVE = 2e-12
ABSOLUTE = 2e-10


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def chronological(values):
    total = 0.
    for value in values:
        total += value
    return total


def exact_mean(values):
    values = list(values)
    return float(sum(map(Fraction, values), Fraction()) / len(values))


def conjunction(states):
    values = list(states)
    if not values or set(values) - {"pass", "fail", "unresolved"}:
        raise AssertionError("invalid conjunction")
    return "fail" if "fail" in values else "unresolved" if "unresolved" in values else "pass"


def disjunction(states):
    values = list(states)
    return "pass" if "pass" in values else "unresolved" if "unresolved" in values else "fail"


class Audit:
    def __init__(self):
        self.exact_checks = self.numeric_checks = self.inequality_checks = 0
        self.intervals = self.simultaneous_intervals = self.episodes = self.ticks = 0
        self.max_numeric_error = 0.
        self.where = "initialization"
        self.certificate_cache = set()

    def equal(self, actual, expected, label):
        if type(actual) is not type(expected):
            raise AssertionError(f"{self.where}/{label}: type {type(actual)} != {type(expected)}")
        if isinstance(expected, dict):
            if set(actual) != set(expected):
                raise AssertionError(f"{self.where}/{label}: dictionary keys differ")
            for key in expected:
                self.equal(actual[key], expected[key], label + "/" + str(key))
        elif isinstance(expected, (list, tuple)):
            if len(actual) != len(expected):
                raise AssertionError(f"{self.where}/{label}: lengths differ")
            for left, right in zip(actual, expected):
                self.equal(left, right, label)
        else:
            self.exact_checks += 1
            if actual != expected:
                raise AssertionError(f"{self.where}/{label}: {actual!r} != {expected!r}")

    def near(self, actual, expected, label):
        if actual is None or expected is None:
            return self.equal(actual, expected, label)
        self.numeric_checks += 1
        if type(actual) not in (int, float) or not math.isfinite(actual):
            raise AssertionError(f"{self.where}/{label}: invalid number")
        error = abs(actual - expected)
        self.max_numeric_error = max(self.max_numeric_error, error)
        if error > ABSOLUTE + RELATIVE * max(abs(actual), abs(expected)):
            raise AssertionError(f"{self.where}/{label}: {actual!r} != {expected!r} (error {error})")

    def require(self, condition, label):
        self.inequality_checks += 1
        if not condition:
            raise AssertionError(f"{self.where}/{label}")

    def exact_record(self, record):
        self.require(type(record["numerator"]) is int and type(record["denominator"]) is int
                     and record["denominator"] > 0, "rational fields")
        value = Fraction(record["numerator"], record["denominator"])
        out = float(value)
        if Fraction(out) < value:
            out = math.nextafter(out, math.inf)
        self.equal(record["upper_float"], out, "outward rational display")
        return value

    def initial(self, case):
        c, seed = case["config"], case["seed"]
        n, p, w, h = (c[k] for k in ("n_agents", "n_patches", "width", "height"))
        columns = min(w, max(1, math.ceil(math.sqrt(p*w/h))))
        if math.ceil(p / columns) > h:
            columns = math.ceil(p/h)
        rows = math.ceil(p/columns)
        sites = [{"id": i, "x": int((i % columns + .5)*w/columns),
                  "y": int((i // columns + .5)*h/rows)} for i in range(p)]
        checker = sorted(range(p), key=lambda i: (((i//columns)+(i % columns)) % 2, i))
        offsets = ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1))
        slots = []
        for i in range(n):
            site = sites[i if i < p else checker[i % p]]
            dx, dy = offsets[(i//p) % 5]
            x, y = site["x"] + dx, site["y"] + dy
            slots.append([x, y] if 0 <= x < w and 0 <= y < h else [site["x"], site["y"]])
        event = lambda kind, tick, identity: int.from_bytes(hashlib.sha256(
            f"{ENGINE}|{seed}|{kind}|{tick}|{identity}".encode()).digest()[:8], "big")
        order = sorted(range(n), key=lambda i: (event("initial-slot", 0, i), i))
        positions = [slots[order[i]] for i in range(n)]
        state = {"config": c, "seed": seed, "tick": 0, "messages": [],
                 "agents": [{"id": i, "x": positions[i][0], "y": positions[i][1],
                             "inventory": float(c["initial_inventory"]),
                             **{key: 0. for key in FIELDS}} for i in range(n)],
                 "patches": [{**site, "stock": float(c["initial_patch_stock"]),
                               "cumulative_growth": 0., "cumulative_harvest": 0., "growth_waste": 0.}
                              for site in sites]}
        initial_hash = digest({"version": "commons-v3-snapshot-v1", "engine_version": ENGINE, "state": state})
        weather, stream = [], hashlib.sha256()
        for tick in range(case["horizon"]):
            row = []
            for i in range(p):
                value = 1. + c["weather_amplitude"] * (2.*(event("weather", tick, i)/2**64)-1.)
                row.append(value)
                stream.update(canonical([f"{ENGINE}/seed-{seed}/tick-{tick}/patch-{i}/weather", value]))
            weather.append(row)
        return sites, positions, initial_hash, weather, stream.hexdigest()

    def episode(self, episode, case, control, intervention, specification, initial):
        self.where = f"{case['id']}/{control['id']}/{intervention['id']}"
        c, h = case["config"], case["horizon"]
        n, p = c["n_agents"], c["n_patches"]
        sites, start_positions, initial_hash, weather, weather_hash = initial
        self.equal(episode["case"], case, "case binding")
        self.equal(episode["control"], control, "control binding")
        self.equal(episode["intervention"], intervention, "intervention binding")
        self.equal(episode["condition"], intervention["id"], "condition")
        self.equal(episode["aggressive_ids"], intervention["aggressive_ids"], "aggressive ids")
        self.equal(episode["aggressive_count"], len(intervention["aggressive_ids"]), "aggressive count")
        self.equal(episode["input_sha256"], digest({key: episode[key] for key in ("case", "control", "aggressive_ids")}), "input digest")
        self.equal(episode["site_layout"], sites, "site geometry")
        self.equal(episode["initial_state_sha256"], initial_hash, "initial state digest")
        self.equal(episode["weather_sha256"], weather_hash, "independent keyed weather digest")
        trajectory = episode["trajectory"]
        self.equal(len(trajectory), h, "trajectory length")
        site_cells = {(s["x"], s["y"]) for s in sites}
        site_indices = {(s["x"], s["y"]): s["id"] for s in sites}
        previous_positions = start_positions
        previous_inventory = [float(c["initial_inventory"])]*n
        previous_stock = [float(c["initial_patch_stock"])]*p
        known = [set() for _ in range(n)]
        totals = {key: [0.]*n for key in FIELDS}
        late_n = max(1, h//4)
        late_start, quarter_start = h-late_n, h//2
        late_c, late_s, quarter, prelate = ([0.]*n for _ in range(4))
        moves = [0]*n
        prefix = None
        flow = sum(previous_inventory) + sum(previous_stock)
        max_residual = max_relative = 0.
        members = {kind: [i for i in range(n) if (i in intervention["aggressive_ids"]) == (kind == "aggressive")]
                   for kind in ("normal", "aggressive")}
        consumptions = {(256, 0): Counter(), (512, 0): Counter(), (512, 384): Counter()}
        for t, row in enumerate(trajectory):
            self.equal(row["tick"], t+1, "tick order")
            vectors = {key: row["agent_"+key] for key in FIELDS + ("residual", "inventory", "moved", "known_sites", "positions")}
            for key, values in vectors.items():
                self.equal(len(values), n, "agent vector size " + key)
            self.equal(len(row["site_stock"]), p, "site vector size")
            at_sites = defaultdict(list)
            off, hungry, unaffordable = [], [], 0
            for i in range(n):
                before, after = previous_positions[i], vectors["positions"][i]
                for site in sites:
                    if abs(before[0]-site["x"])+abs(before[1]-site["y"]) <= c["sensing_radius"]:
                        known[i].add((site["x"], site["y"]))
                self.equal(vectors["known_sites"][i], len(known[i]), "local discovery count")
                self.require(all(type(v) is int for v in after) and len(after) == 2
                             and 0 <= after[0] < c["width"] and 0 <= after[1] < c["height"], "position domain")
                distance = abs(after[0]-before[0])+abs(after[1]-before[1])
                self.equal(vectors["moved"][i], distance == 1, "movement flag")
                self.require(distance <= 1, "cardinal local move")
                self.equal(vectors["movement_cost"][i], float(c["movement_cost"]) if distance else 0., "movement payment")
                self.require(not distance or previous_inventory[i] >= c["movement_cost"], "affordable movement")
                for key in ("message_cost", "transfer_in", "transfer_out"):
                    self.equal(vectors[key][i], 0., "supplied policy has no " + key)
                meal, short = vectors["consumption"][i], vectors["shortfall"][i]
                inv, harvest = vectors["inventory"][i], vectors["harvested"][i]
                self.require(0 <= meal <= min(c["need"], c["inventory_capacity"]), "consumption cap")
                self.equal(short, c["need"]-meal, "need balance")
                self.require(0 <= inv <= c["inventory_capacity"] and 0 <= harvest <= c["max_harvest"], "material caps")
                self.equal(vectors["harvest_cost"][i], harvest*c["harvest_cost_per_unit"], "obligatory gross cost")
                point = tuple(after)
                if point in site_cells:
                    at_sites[site_indices[point]].append(harvest)
                else:
                    self.equal(harvest, 0., "no offsite extraction")
                    off.append(i)
                    if short > 0:
                        hungry.append(i)
                    if known[i]:
                        return_distance = min(abs(after[0]-x)+abs(after[1]-y) for x, y in known[i])
                        unaffordable += int(inv < c["movement_cost"]*return_distance)
                balance = (previous_inventory[i] - vectors["movement_cost"][i] - vectors["message_cost"][i]
                           - vectors["transfer_out"][i] + vectors["transfer_in"][i] + harvest
                           - vectors["harvest_cost"][i] - meal - vectors["waste"][i])
                self.equal(vectors["residual"][i], inv-balance, "agent material residual")
                for key in FIELDS:
                    totals[key][i] += vectors[key][i]
                moves[i] += int(distance == 1)
                if t >= late_start:
                    late_c[i] += meal
                    late_s[i] += short
                if quarter_start <= t < late_start:
                    quarter[i] += meal
                if 192 <= t < 256:
                    prelate[i] += meal
            growths, growth_waste, patch_residual = [], [], []
            for i, stock in enumerate(previous_stock):
                extracted = math.fsum(at_sites[i])
                remaining = max(0., stock-extracted)
                production = (c["renewal_rate"]*remaining*(1.-remaining/c["patch_capacity"])
                              if c["renewal_law"] == "logistic" else c["renewal_rate"]*c["patch_capacity"]/4.)
                potential = (production+c["recovery"])*weather[t][i]
                growth = min(max(0., c["patch_capacity"]-remaining), potential)
                resulting = remaining+growth
                self.equal(row["site_stock"][i], resulting, "site renewal reconstruction")
                growths.append(growth)
                growth_waste.append(max(0., potential-growth))
                patch_residual.append(resulting-(stock-extracted+growth))
            self.equal(row["site_residual"], patch_residual, "site residual vector")
            self.equal(row["growth"], math.fsum(growths), "renewal total")
            self.equal(row["growth_waste"], math.fsum(growth_waste), "unrealized renewal")
            for name in ("consumption", "movement_cost", "message_cost", "harvest_cost", "waste"):
                self.equal(row[name], math.fsum(vectors[name]), "tick " + name)
            self.near(row["shortfall"], math.fsum(vectors["shortfall"]), "tick shortfall")
            self.equal(row["stock"], math.fsum(row["site_stock"]), "site total")
            self.equal(row["reserves"], math.fsum(vectors["inventory"]), "inventory total")
            self.equal(row["moves"], sum(vectors["moved"]), "movement total")
            self.equal(row["off_site_agents"], len(off), "offsite count")
            self.equal(row["hungry_off_site_agents"], len(hungry), "hungry offsite count")
            self.equal(row["unaffordable_known_returns"], unaffordable, "known return count")
            self.equal(unaffordable, 0, "known return engineering gate")
            occupied = set(map(tuple, vectors["positions"]))
            unused = sum(row["site_stock"][site["id"]] for site in sites if (site["x"], site["y"]) not in occupied)
            self.near(row["unoccupied_stock_fraction"], unused/(p*c["patch_capacity"]), "unused stock fraction")
            self.near(row["mean_known_sites"], sum(map(len, known))/n, "known sites mean")
            self.equal(row["depleted_patches"], sum(s < .1*c["patch_capacity"] for s in row["site_stock"]), "depletion count")
            for kind, ids in members.items():
                self.equal(row["cohorts"][kind]["n"], len(ids), "tick cohort count")
                for field in ("consumption", "shortfall", "inventory"):
                    self.near(row["cohorts"][kind][field], math.fsum(vectors[field][i] for i in ids), "tick cohort " + field)
            residual = (row["reserves"]+row["stock"]-math.fsum(previous_inventory)-math.fsum(previous_stock)-row["growth"]
                        + row["consumption"]+row["movement_cost"]+row["message_cost"]+row["harvest_cost"]+row["waste"])
            self.equal(row["accounting_residual"], residual, "global material residual")
            flow += row["growth"]+row["consumption"]+row["movement_cost"]+row["message_cost"]+row["harvest_cost"]+row["waste"]
            self.near(row["accounting_cumulative_flow"], flow, "flow scaling")
            residual = max(abs(residual), *map(abs, vectors["residual"]), *map(abs, patch_residual))
            max_residual = max(max_residual, residual)
            max_relative = max(max_relative, residual/max(1., flow))
            self.require(residual <= specification["ledger_relative_tolerance"]*max(1., flow), "accounting engineering gate")
            self.require(row["waste"] <= specification["maximum_tick_extraction_waste"], "extraction waste engineering gate")
            if t == 255:
                prefix = (exact_mean(value/256 for value in totals["consumption"]),
                          exact_mean(value/64 for value in prelate), row["stock"]/(p*c["patch_capacity"]))
            for (stop, start), histogram in consumptions.items():
                if start <= t < stop:
                    histogram.update(vectors["consumption"])
            previous_positions, previous_inventory, previous_stock = vectors["positions"], vectors["inventory"], row["site_stock"]
        rebuilt_agents = []
        for i, saved in enumerate(episode["agents"]):
            self.equal(saved["id"], i, "agent identity")
            agent = {"id": i, "policy": "aggressive" if i in intervention["aggressive_ids"] else "normal",
                     **{key: totals[key][i] for key in FIELDS},
                     "consumption_per_tick": totals["consumption"][i]/h,
                     "shortfall_per_tick": totals["shortfall"][i]/h,
                     "quarter3_consumption": quarter[i],
                     "quarter3_consumption_per_tick": quarter[i]/(late_start-quarter_start) if late_start > quarter_start else None,
                     "late_consumption": late_c[i], "late_shortfall": late_s[i],
                     "late_consumption_per_tick": late_c[i]/late_n, "late_shortfall_per_tick": late_s[i]/late_n,
                     "terminal_inventory": previous_inventory[i], "movement_steps": moves[i], "terminal_known_sites": len(known[i]),
                     "utility": {str(w): (totals["consumption"][i]+w*previous_inventory[i])/h for w in WEIGHTS}}
            self.equal(saved, agent, "cumulative agent reconstruction")
            rebuilt_agents.append(agent)
        cohorts = {}
        for kind, ids in members.items():
            cohort = {"n": len(ids), "consumption": math.fsum(totals["consumption"][i] for i in ids),
                      "shortfall": math.fsum(totals["shortfall"][i] for i in ids),
                      "inventory": math.fsum(previous_inventory[i] for i in ids),
                      **{key: exact_mean(rebuilt_agents[i][key] for i in ids) if ids else None for key in ENDPOINTS},
                      "utility": {str(w): exact_mean(rebuilt_agents[i]["utility"][str(w)] for i in ids) if ids else None for w in WEIGHTS}}
            for key in cohort:
                if key == "utility":
                    for w in WEIGHTS:
                        self.near(episode["cohorts"][kind][key][str(w)], cohort[key][str(w)], "cohort utility")
                elif key == "n":
                    self.equal(episode["cohorts"][kind][key], cohort[key], "cohort n")
                else:
                    self.near(episode["cohorts"][kind][key], cohort[key], "cohort endpoint")
            cohorts[kind] = cohort
        getmean = lambda key: exact_mean(agent[key] for agent in rebuilt_agents)
        longest = running = 0
        for row in trajectory[h//2:]:
            running = running+1 if row["depleted_patches"]*2 >= p else 0
            longest = max(longest, running)
        summary = {
            "consumption_per_agent_tick": getmean("consumption_per_tick"), "shortfall_per_agent_tick": getmean("shortfall_per_tick"),
            "quarter3_consumption_per_agent_tick": getmean("quarter3_consumption_per_tick") if late_start > quarter_start else None,
            "late_consumption_per_agent_tick": getmean("late_consumption_per_tick"), "late_shortfall_per_agent_tick": getmean("late_shortfall_per_tick"),
            "terminal_inventory_per_agent": getmean("terminal_inventory"), "terminal_stock_fraction": trajectory[-1]["stock"]/(p*c["patch_capacity"]),
            "late_stock_fraction": exact_mean(row["stock"]/(p*c["patch_capacity"]) for row in trajectory[-late_n:]),
            "depleted_patch_time_fraction": sum(row["depleted_patches"] for row in trajectory)/(h*p),
            "late_depleted_patch_time_fraction": sum(row["depleted_patches"] for row in trajectory[-late_n:])/(late_n*p),
            "persistent_depletion_longest_ticks": longest, "persistent_depletion_threshold_ticks": h/8,
            "movement_steps_per_agent": getmean("movement_steps"),
            **{"total_"+key: math.fsum(totals[key]) for key in ("movement_cost", "message_cost", "harvest_cost", "waste")},
            "max_tick_waste": max(row["waste"] for row in trajectory), "max_unaffordable_known_returns": 0,
            "mean_off_site_agent_fraction": exact_mean(row["off_site_agents"]/n for row in trajectory),
            "mean_hungry_off_site_agent_fraction": exact_mean(row["hungry_off_site_agents"]/n for row in trajectory),
            "terminal_unoccupied_stock_fraction": trajectory[-1]["unoccupied_stock_fraction"],
            "terminal_mean_known_sites": trajectory[-1]["mean_known_sites"],
            "max_ledger_residual": max_residual, "max_relative_ledger_residual": max_relative,
            **{key: prefix[i] if prefix else None for i, key in enumerate(("prefix256_consumption_per_agent_tick",
                 "prefix256_late_consumption_per_agent_tick", "prefix256_terminal_stock_fraction"))}}
        self.equal(set(summary), set(episode["summary"]), "summary field inventory")
        for key, value in summary.items():
            self.near(episode["summary"][key], value, "summary " + key)
        spatial = case["id"] == specification["reference_frames_case"]
        self.equal(episode["checkpoint_continuation_checked"], spatial, "continuation selection")
        self.equal(episode["checkpoint_continuation"]["verified"], spatial, "continuation status")
        self.equal(episode["checkpoint_continuation"]["future_ticks_checked"], h-h//2 if spatial else 0, "continuation ticks")
        expected_frame_ticks = sorted({0, h//4, h//2, h}) if spatial else []
        self.equal([frame["tick"] for frame in episode["spatial_frames"]], expected_frame_ticks, "frame inventory")
        for frame in episode["spatial_frames"]:
            tick = frame["tick"]
            positions = trajectory[tick-1]["agent_positions"] if tick else start_positions
            inventories = trajectory[tick-1]["agent_inventory"] if tick else [float(c["initial_inventory"])]*n
            stocks = trajectory[tick-1]["site_stock"] if tick else [float(c["initial_patch_stock"])]*p
            self.equal(frame["agents"], [{"id": i, "x": positions[i][0], "y": positions[i][1], "inventory": inventories[i],
                                          "policy": rebuilt_agents[i]["policy"]} for i in range(n)], "frame agents")
            self.equal(frame["sites"], [{**site, "stock": stocks[site["id"]]} for site in sites], "frame stocks")
        self.episodes += 1
        self.ticks += h
        return {"case": case, "control": control, "condition": intervention["id"], "intervention": intervention,
                "aggressive_ids": intervention["aggressive_ids"], "aggressive_count": len(intervention["aggressive_ids"]),
                "agents": rebuilt_agents, "cohorts": cohorts, "summary": summary,
                "exact_consumption": {key: sum((Fraction(value)*count for value, count in histogram.items()), Fraction())
                                      for key, histogram in consumptions.items()}}

    def certificates(self, records, case, episodes):
        self.equal([(r["horizon"], r["window_start"], r["target_fraction"]) for r in records],
                   [(256, 0, 1.), (256, 0, .95), (512, 0, 1.), (512, 0, .95), (512, 384, 1.), (512, 384, .95)],
                   "certificate scope inventory")
        for record in records:
            self.equal(record["config"], case["config"], "certificate configuration")
            signature = digest(record)
            if signature not in self.certificate_cache:
                c = {key: Fraction(value) for key, value in case["config"].items() if type(value) in (int, float)}
                n, p = c["n_agents"], c["n_patches"]
                H, start = record["horizon"], record["window_start"]
                L, r, K, a, w = H-start, c["renewal_rate"], c["patch_capacity"], c["recovery"], c["weather_amplitude"]
                B, d, harvest, net = c["inventory_capacity"], c["need"], c["max_harvest"], 1-c["harvest_cost_per_unit"]
                u, eta = Fraction(1, 2**53), Fraction(1, 2**1074)
                lattice = lambda x: Fraction(-(-(x.numerator*2**128)//x.denominator), 2**128)
                up = lambda x: lattice(x*(1+u)+eta) if x else Fraction()
                weather = up(1+w) if w else Fraction(1)
                production = (up(r*K/4 + 2*r*K*(u+eta) + u*r*K+eta) if r else Fraction()) if case["config"]["renewal_law"] == "logistic" else up(up(r*K)/4)
                growth = min(K, up(up(production+a)*weather))
                magnitude = 16*(n+p+1)*(B+K+harvest+d+a+1)
                E = lattice(8*u*magnitude)
                eI, eS = n*(2*n+6)*E, p*(n+3)*E
                I0 = n*(B if start else c["initial_inventory"])
                S0 = p*(K if start else c["initial_patch_stock"])
                limits = {"consumption_cap_total": n*L*min(d, B),
                          "resource_total": I0+net*(S0+(L-1)*p*growth+L*eS)+L*eI,
                          "harvest_rate_total": I0+net*L*n*harvest+L*eI}
                bound, demand = min(limits.values()), n*L*d
                values = {**limits, "consumption_total": bound, "demand_total": demand,
                          "initial_inventory_total": I0, "initial_stock_total": S0,
                          "consumption_per_agent_tick": bound/(n*L),
                          "growth_per_patch_tick": growth, "weather_multiplier": weather,
                          "exact_real_growth_per_patch_tick": min(K, (r*K/4+a)*(1+w))}
                for key, expected in values.items():
                    self.equal(self.exact_record(record["bounds"][key]), expected, "rational bound " + key)
                if demand:
                    self.equal(self.exact_record(record["bounds"]["fraction_of_need"]), bound/demand, "need fraction")
                target = Fraction(95, 100) if record["target_fraction"] == .95 else Fraction(1)
                self.equal(self.exact_record(record["target_fraction_exact"]), target, "rational target")
                self.equal(self.exact_record(record["target_consumption_total"]), target*demand, "target consumption")
                self.equal(record["status"], "proven_insufficient" if bound < target*demand else "unresolved", "exact resource verdict")
                for key, expected in {"single_operation_allowance": E, "agent_material_allowance_per_tick": eI,
                                      "patch_material_allowance_per_tick": eS, "operation_magnitude_bound": magnitude}.items():
                    self.equal(self.exact_record(record["roundoff"][key]), expected, "rounding account " + key)
                sustainable = min(n*min(d, B), net*(p*growth+eS)+eI, net*n*harvest+eI)
                self.equal(self.exact_record(record["sustainable_ceiling"]["consumption_per_tick"]), sustainable, "sustainable ceiling")
                self.equal(record["scope"]["policy_optimality_claim"], False, "no optimality claim")
                self.equal(record["scope"]["executed_episodes"], 0, "no certificate simulations")
                self.certificate_cache.add(signature)
            key = (record["horizon"], record["window_start"])
            if key[0] <= case["horizon"]:
                upper = self.exact_record(record["bounds"]["consumption_total"])
                for episode in episodes:
                    self.require(episode["exact_consumption"][key] <= upper, "exact ledger sum <= certified resource ceiling")

    def interval(self, saved, values, seeds, specification, *, threshold=None, direction="lower"):
        self.intervals += 1
        simultaneous = threshold is not None
        self.simultaneous_intervals += int(simultaneous)
        self.equal(saved["seeds"], seeds, "interval seed order")
        self.equal(saved["n"], len(values), "interval n")
        self.equal(len(saved["values"]), len(values), "interval observations")
        for left, right in zip(saved["values"], values):
            self.near(left, right, "interval raw endpoint")
        fractions = list(map(Fraction, values))
        mean_q = sum(fractions, Fraction())/len(values)
        variance_q = sum(((x-mean_q)**2 for x in fractions), Fraction())/(len(values)-1)
        mean, se = float(mean_q), math.sqrt(float(variance_q))/math.sqrt(len(values))
        critical = specification["statistics"]["simultaneous_t_critical" if simultaneous else "descriptive_t_critical"]
        lower, upper = mean-critical*se, mean+critical*se
        for key, value in {"mean": mean, "standard_error": se, "lower": lower, "upper": upper,
                           "min": min(values), "max": max(values)}.items():
            self.near(saved[key], value, "independent interval " + key)
        self.equal(saved["critical"], critical, "frozen critical value")
        self.equal(saved["interval_kind"], "simultaneous" if simultaneous else "descriptive", "interval family kind")
        self.equal(saved["family_size"], specification["statistics"]["simultaneous_family_size"] if simultaneous else None, "multiplicity family")
        for key, count in (("positive", sum(x > 0 for x in values)), ("negative", sum(x < 0 for x in values)), ("zero", sum(x == 0 for x in values))):
            self.equal(saved[key], count, "sign count " + key)
        self.equal(saved["sign_count_threshold"], 0., "sign threshold")
        if simultaneous:
            self.equal(saved["threshold"], threshold, "prospective threshold")
            self.equal(saved["direction"], direction, "gate direction")
            verdict = lambda lo, hi: ("pass" if lo >= threshold else "fail" if hi < threshold else "unresolved") if direction == "lower" else ("pass" if hi <= threshold else "fail" if lo > threshold else "unresolved")
            self.equal(saved["status"], verdict(saved["lower"], saved["upper"]), "strict saved-endpoint gate")
            self.equal(saved["status"], verdict(lower, upper), "strict independently calculated gate")
            return saved["status"]

    def columns(self, saved, rows, seeds, specification):
        self.equal(set(saved), set(rows[0]), "scalar columns")
        for key in saved:
            values = [row[key] for row in rows]
            if all(v is None for v in values):
                self.equal(saved[key], None, "empty cohort column")
            else:
                self.require(all(v is not None for v in values), "complete endpoint column")
                self.interval(saved[key], values, seeds, specification)

    def condition(self, saved, episodes, cases, specification):
        seeds = [case["seed"] for case in cases]
        self.equal(saved["condition"], episodes[0]["condition"], "condition summary id")
        self.equal(saved["intervention"], {key: episodes[0]["intervention"][key] for key in ("peer_count", "focal_aggressive")}, "condition summary roles")
        self.equal(saved["identities_by_seed"], [{"seed": case["seed"], "focal_id": case["focal_id"], "aggressive_ids": ep["aggressive_ids"]}
                                                for case, ep in zip(cases, episodes)], "per-seed identity summary")
        self.equal(saved["aggressive_count"], episodes[0]["aggressive_count"], "condition aggressive count")
        self.near(saved["aggressive_fraction"], episodes[0]["aggressive_count"]/cases[0]["config"]["n_agents"], "aggressive fraction")
        self.columns(saved["summary"], [e["summary"] for e in episodes], seeds, specification)
        endpoints = lambda agent: {**{key: agent[key] for key in ENDPOINTS}, **{"utility_"+str(w): agent["utility"][str(w)] for w in WEIGHTS}}
        self.columns(saved["focal"], [endpoints(e["agents"][case["focal_id"]]) for e, case in zip(episodes, cases)], seeds, specification)
        for kind in ("normal", "aggressive"):
            self.equal(saved["cohorts"][kind]["n"], episodes[0]["cohorts"][kind]["n"], "condition cohort count")
            self.columns(saved["cohorts"][kind]["endpoints"], [endpoints(e["cohorts"][kind]) for e in episodes], seeds, specification)
        self.equal(saved["persistent_depletion_seed_count"], sum(e["summary"]["persistent_depletion_longest_ticks"] >= e["summary"]["persistent_depletion_threshold_ticks"] for e in episodes), "persistent depletion seed count")

    def focal_difference(self, before, after, case):
        focal = case["focal_id"]
        left, right = before["agents"][focal], after["agents"][focal]
        result = {key: right[key]-left[key] for key in ENDPOINTS}
        peer_sets = {"peer": [i for i in range(case["config"]["n_agents"]) if i != focal],
                     **{kind+"_peer": [agent["id"] for agent in before["agents"] if agent["id"] != focal and agent["policy"] == kind]
                        for kind in ("normal", "aggressive")}}
        for group, ids in peer_sets.items():
            for field in ("consumption_per_tick", "late_consumption_per_tick"):
                result[group+"_"+field] = exact_mean(after["agents"][i][field]-before["agents"][i][field] for i in ids) if ids else None
        for field in ("consumption_per_agent_tick", "late_consumption_per_agent_tick", "terminal_stock_fraction",
                      "depleted_patch_time_fraction", "late_stock_fraction", "late_depleted_patch_time_fraction"):
            result["world_"+field] = after["summary"][field]-before["summary"][field]
        for weight in WEIGHTS:
            result["utility_"+str(weight)] = right["utility"][str(weight)]-left["utility"][str(weight)]
            result["terminal_wealth_contribution_"+str(weight)] = weight*(right["terminal_inventory"]-left["terminal_inventory"])/case["horizon"]
        return result

    def summary(self, summary, groups, specification, ecology=None):
        self.where = specification["stage"] + "/aggregate"
        self.equal(summary["statistics"], specification["statistics"], "analysis registry")
        self.equal(summary["independent_environment_seeds"], specification["seeds"], "independent seeds")
        for key in ("configurations", "episodes", "physical_ticks", "agent_decisions"):
            self.equal(summary[key], specification["counts"][key], "design count " + key)
        for key in ("experimental_model_calls", "evolutionary_runs", "new_numerical_selection_runs"):
            self.equal(summary[key], 0, "budget " + key)
        self.equal(len(summary["cells"]), len(groups), "cell count")
        reconstructed = {}
        before_gates = self.simultaneous_intervals
        for cell in summary["cells"]:
            key = cell["panel"], cell["renewal_rate"], cell["need"]
            self.where = specification["stage"] + "/" + cell["id"]
            rows = sorted(groups[key], key=lambda r: r["case"]["seed"])
            cases = [r["case"] for r in rows]
            seeds = [c["seed"] for c in cases]
            self.equal(seeds, specification["seeds"], "complete seed cell")
            self.equal(cell["id"], f"{key[0]}-r{key[1]:.2f}-n{key[2]:.1f}", "cell identifier")
            self.equal(cell["horizon"], cases[0]["horizon"], "cell horizon")
            lookup = [{(e["control"]["id"], e["condition"]): e for e in r["episodes"]} for r in rows]
            statuses, robust_statuses = {}, {}
            for control in specification["controls"]:
                cid = control["id"]
                saved = cell["controls"][cid]
                need = key[2]
                if specification["stage"] == "ecology":
                    episodes = [arms[cid, "all_restrained"] for arms in lookup]
                    self.condition(saved, episodes, cases, specification)
                    series = {
                        "consumption_fraction": [e["summary"]["consumption_per_agent_tick"]/need for e in episodes],
                        "late_consumption_fraction": [e["summary"]["late_consumption_per_agent_tick"]/need for e in episodes],
                        "late_minus_third_quarter_fraction": [(e["summary"]["late_consumption_per_agent_tick"]-e["summary"]["quarter3_consumption_per_agent_tick"])/need for e in episodes],
                        "late_stock_fraction": [e["summary"]["late_stock_fraction"] for e in episodes],
                        "late_depleted_patch_time_fraction_max": [e["summary"]["late_depleted_patch_time_fraction"] for e in episodes]}
                    verdicts = [self.interval(saved["criteria"][name], values, seeds, specification,
                                             threshold=specification["ecology_thresholds"][name], direction="upper" if name.endswith("_max") else "lower")
                                for name, values in series.items()]
                    statuses[cid] = conjunction(verdicts)
                else:
                    arms = specification["condition_registry"][cases[0]["id"]]
                    for arm in arms:
                        self.condition(saved["conditions"][arm["id"]], [table[cid, arm["id"]] for table in lookup], cases, specification)
                    role = {(arm["peer_count"], arm["focal_aggressive"]): arm["id"] for arm in arms}
                    focal_zero = None
                    self.equal([row["peer_count"] for row in saved["paired_focal"]], sorted(k for k, f in role if not f and (k, True) in role), "paired intervention counts")
                    for pair in saved["paired_focal"]:
                        k = pair["peer_count"]
                        self.equal(pair["before_condition"], role[k, False], "before intervention")
                        self.equal(pair["after_condition"], role[k, True], "after intervention")
                        differences = [self.focal_difference(table[cid, role[k, False]], table[cid, role[k, True]], case)
                                       for table, case in zip(lookup, cases)]
                        self.columns(pair["differences"], differences, seeds, specification)
                        if k == 0:
                            focal_zero = differences
                    widespread = []
                    for table, case in zip(lookup, cases):
                        left, right = table[cid, role[0, False]]["summary"], table[cid, role[case["config"]["n_agents"]-1, True]]["summary"]
                        widespread.append({field: right[field]-left[field] for field in left if left[field] is not None})
                    self.columns(saved["all_aggressive_minus_all_restrained"], widespread, seeds, specification)
                    weight = str(specification["incentive_thresholds"]["primary_wealth_weight"])
                    series = {"focal_utility_gain_fraction": [row["utility_"+weight]/need for row in focal_zero],
                              "population_consumption_loss_fraction": [-row["consumption_per_agent_tick"]/need for row in widespread],
                              "population_late_consumption_loss_fraction": [-row["late_consumption_per_agent_tick"]/need for row in widespread]}
                    verdicts = []
                    if key[0] == "grid":
                        for name, values in series.items():
                            verdicts.append(self.interval(saved["criteria"][name], values, seeds, specification,
                                                          threshold=specification["incentive_thresholds"][name]))
                    else:
                        self.equal(saved["criteria"], {}, "sensitivity excluded from primary")
                    statuses[cid] = conjunction(verdicts) if verdicts else "not_primary"
                    expected_robust = {}
                    if key[0] in specification["robustness_panels"] and key[1] == specification["reference"]["renewal_rate"] and key[2] == specification["reference"]["need"]:
                        for w in WEIGHTS:
                            name = "focal_utility_gain_fraction_"+str(w)
                            expected_robust[name] = self.interval(saved["robustness_criteria"][name], [row["utility_"+str(w)]/need for row in focal_zero], seeds, specification,
                                                                 threshold=specification["incentive_thresholds"]["focal_utility_gain_fraction"])
                        for name in ("population_consumption_loss_fraction", "population_late_consumption_loss_fraction"):
                            expected_robust[name] = self.interval(saved["robustness_criteria"][name], series[name], seeds, specification,
                                                                 threshold=specification["incentive_thresholds"][name])
                    self.equal(set(saved["robustness_criteria"]), set(expected_robust), "robustness field inventory")
                    robust_statuses[cid] = expected_robust
                self.equal(saved["status"], statuses[cid], "control gate conjunction")
            combined = conjunction(statuses.values()) if key[0] == "grid" else "not_primary"
            self.equal(cell["status"], combined, "both control gate")
            if specification["stage"] == "ecology":
                self.equal(cell["feasibility_certificates"], [{"seed": row["case"]["seed"], "certificates": row["certificates"]} for row in rows], "aggregate resource certificate binding")
                impossible = all(next(cert for cert in row["certificates"] if cert["horizon"] == 512 and cert["window_start"] == 0 and cert["target_fraction"] == .95)["status"] == "proven_insufficient" for row in rows)
                feasible = "pass" in statuses.values()
                self.require(not (feasible and impossible), "no contradictory feasibility claims")
                self.equal(cell["feasibility"], "witnessed_viable" if feasible else "certified_insufficient" if impossible else "feasibility_unresolved", "physical interpretation")
            reconstructed[key] = {"id": cell["id"], "controls": statuses, "robust": robust_statuses, "status": combined}
        self.where = specification["stage"] + "/overall"
        grid = {key: value for key, value in reconstructed.items() if key[0] == "grid"}
        pair_rows = []
        reference = (specification["reference"]["renewal_rate"], specification["reference"]["need"])
        for left in sorted(grid):
            for right in sorted(grid):
                distance = abs(specification["rates"].index(left[1])-specification["rates"].index(right[1])) + abs(specification["needs"].index(left[2])-specification["needs"].index(right[2]))
                if left >= right or distance != 1 or (specification["adjacency"]["must_include_reference"] and reference not in (left[1:], right[1:])):
                    continue
                if ecology is None:
                    requirements = {grid[key]["id"]+"/"+control["id"]: grid[key]["controls"][control["id"]] for key in (left, right) for control in specification["controls"]}
                else:
                    requirements = {grid[key]["id"]+"/"+control["id"]+"/"+stage: source[key]["controls"][control["id"]]
                                    for key in (left, right) for control in specification["controls"] for stage, source in (("ecology", ecology), ("incentive", grid))}
                pair_rows.append({"cells": [grid[left]["id"], grid[right]["id"]], "requirements": requirements, "status": conjunction(requirements.values())})
        gate_name = "ecological_adjacent_pairs" if ecology is None else "primary_gate"
        self.equal(summary[gate_name]["pairs"], pair_rows, "adjacent-cell gate requirements")
        primary = disjunction(row["status"] for row in pair_rows)
        self.equal(summary[gate_name]["status"], primary, "adjacent pair verdict")
        if ecology is not None:
            reference_cells = {key: value for key, value in reconstructed.items() if key[0] in specification["robustness_panels"] and key[1:] == reference}
            self.equal({key[0] for key in reference_cells}, set(specification["robustness_panels"]), "robustness panel inventory")
            robust_overall = {}
            for w in WEIGHTS:
                requirements = {key[0]+"/"+cid+"/"+name: value["robust"][cid][name]
                                for key, value in reference_cells.items() for cid in value["controls"]
                                for name in ("focal_utility_gain_fraction_"+str(w), "population_consumption_loss_fraction", "population_late_consumption_loss_fraction")}
                robust_overall[str(w)] = conjunction(requirements.values())
                self.equal(summary["reference_robustness_by_weight"][str(w)], {"status": robust_overall[str(w)], "requirements": requirements}, "weight-specific robustness")
            self.equal(summary["qualification_status"], conjunction([primary, robust_overall[str(specification["incentive_thresholds"]["primary_wealth_weight"])]]), "overall incentive verdict")
        else:
            self.equal(summary["qualification_status"], "ecology_only", "ecology scope")
        reconstructed_count = self.simultaneous_intervals-before_gates
        declared = summary["simultaneous_scalar_intervals"]
        self.equal(reconstructed_count, sum(declared.values()) if isinstance(declared, dict) else declared, "simultaneous interval count")
        return reconstructed

    def bank(self, path, *, ecology=None, repo_root=None):
        path = Path(path)
        specification, manifest, summary = (load(path/name) for name in ("design.json", "manifest.json", "summary.json"))
        self.where = specification["stage"]+"/inventory"
        pins = load(path/"sources.json")
        expected = {"design.json", "sources.json", "summary.json", *("sources/"+name for name in pins),
                    *("cases/"+case["id"]+".json.gz" for case in specification["cases"])}
        if specification["stage"] == "incentive":
            expected.add("ecology-input.json")
        self.equal(set(manifest["artifacts_sha256"]), expected, "manifest inventory")
        present = {str(file.relative_to(path)) for file in path.rglob("*") if file.is_file()}
        self.equal(present, expected | {"manifest.json"}, "bank file inventory")
        for name, sha in manifest["artifacts_sha256"].items():
            self.equal(file_hash(path/name), sha, "artifact hash " + name)
        for name, sha in pins.items():
            self.equal(file_hash(path/"sources"/name), sha, "copied source hash")
            if repo_root is not None:
                self.equal(file_hash(Path(repo_root)/name), sha, "current frozen source hash")
        for name in ("design", "sources"):
            self.equal(manifest[name+"_sha256"], file_hash(path/(name+".json")), "manifest binding")
            self.equal(summary[name+"_sha256"], file_hash(path/(name+".json")), "summary binding")
        selection = load(path/"sources/evidence/commons-v3-navigation-v1/selection.json")
        self.equal(next(row["parameters"] for row in specification["controls"] if row["id"] == "selected"), selection["candidate"]["parameters"], "prior selected controller binding")
        self.equal(pins["evidence/commons-v3-navigation-v1/selection.json"], specification["selected_navigation_selection_sha256"], "prior selection hash")
        self.require(len(set(specification["seeds"])) == len(specification["seeds"]), "unique independent seeds")
        groups = defaultdict(list)
        phase_episodes = phase_ticks = phase_decisions = 0
        for index, case in enumerate(specification["cases"]):
            with gzip.open(path/"cases"/(case["id"]+".json.gz"), "rt") as stream:
                record = json.load(stream)
            self.equal(record["case"], case, "case inventory binding")
            arms = specification["condition_registry"][case["id"]]
            n = case["config"]["n_agents"]
            self.equal(sorted(case["peer_order"]), sorted(set(range(n))-{case["focal_id"]}), "peer identity permutation")
            expected_arms = [(control, arm) for control in specification["controls"] for arm in arms]
            self.equal(len(record["episodes"]), len(expected_arms), "complete arm inventory")
            for arm in arms:
                self.equal(arm["aggressive_ids"], sorted(case["peer_order"][:arm["peer_count"]]+([case["focal_id"]] if arm["focal_aggressive"] else [])), "outcome-independent nested mixture")
            initial = self.initial(case)
            rebuilt = [self.episode(saved, case, control, arm, specification, initial)
                       for saved, (control, arm) in zip(record["episodes"], expected_arms)]
            if specification["stage"] == "ecology":
                self.certificates(record["feasibility_certificates"], case, rebuilt)
            groups[(case["panel"], case["config"]["renewal_rate"], case["config"]["need"])].append(
                {"case": case, "episodes": rebuilt, "certificates": record.get("feasibility_certificates", [])})
            phase_episodes += len(rebuilt)
            phase_ticks += len(rebuilt)*case["horizon"]
            phase_decisions += len(rebuilt)*case["horizon"]*n
            if (index+1) % 8 == 0:
                print(json.dumps({"stage": specification["stage"], "audited_cases": index+1,
                                  "total_cases": len(specification["cases"])}), flush=True)
        for key, count in {"configurations": len(specification["cases"]), "episodes": phase_episodes,
                           "physical_ticks": phase_ticks, "agent_decisions": phase_decisions}.items():
            self.equal(manifest[key], count, "reconstructed manifest count")
        if specification["stage"] == "incentive":
            dependency = load(path/"ecology-input.json")
            self.equal(summary["ecology_input_sha256"], file_hash(path/"ecology-input.json"), "bound ecology dependency")
            self.equal(hashlib.sha256(canonical(dependency["summary"])+b"\n").hexdigest(), dependency["summary_sha256"], "copied ecology hash")
            self.require(ecology is not None, "independently audited ecology required")
            self.require(set(specification["seeds"]).isdisjoint(ecology["seeds"]), "separate ecology/incentive seeds")
            self.equal(dependency["summary"], ecology["summary"], "original audited ecology summary")
        verdicts = self.summary(summary, groups, specification, ecology["cells"] if ecology else None)
        return {"path": str(path), "stage": specification["stage"], "seeds": specification["seeds"],
                "counts": {"cases": len(specification["cases"]), "episodes": phase_episodes,
                           "physical_ticks": phase_ticks, "agent_decisions": phase_decisions},
                "manifest_sha256": file_hash(path/"manifest.json"), "summary_sha256": file_hash(path/"summary.json"),
                "qualification_status": summary["qualification_status"], "summary": summary, "cells": verdicts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecology", type=Path, required=True)
    parser.add_argument("--incentive", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        parser.error("receipt already exists")
    started = time.perf_counter()
    audit = Audit()
    ecology = audit.bank(args.ecology, repo_root=args.repo_root)
    banks = [ecology]
    if args.incentive:
        banks.append(audit.bank(args.incentive, ecology=ecology, repo_root=args.repo_root))
    receipt = {"version": VERSION, "verified": True,
               "script_sha256": file_hash(__file__),
               "banks": [{key: value for key, value in bank.items() if key not in ("summary", "cells", "seeds")} for bank in banks],
               "checks": {"exact": audit.exact_checks, "numerical": audit.numeric_checks,
                          "inequalities": audit.inequality_checks, "intervals": audit.intervals,
                          "simultaneous_intervals": audit.simultaneous_intervals,
                          "unique_resource_certificates": len(audit.certificate_cache)},
               "numerical_diagnostics_only": {"absolute_tolerance": ABSOLUTE, "relative_tolerance": RELATIVE,
                                              "maximum_observed_absolute_difference": audit.max_numeric_error},
               "qualification_decisions": "strict comparisons, independently reconstructed intervals and exact rational resource decisions; no tolerance changes gates",
               "scope": "Raw material/movement/renewal/weather/discovery/cumulative/cohort/utility/quarter summaries, saved-source/hash/input bindings, intervals, paired interventions and verdicts. No policy execution, model calls, or engine replay.",
               "limitations": "Final full physical-snapshot hashes and exact policy/private-memory behavior are left to the separately recorded semantic replay; the audit rebuilds supplied raw states and material flows. Frozen t critical constants are checked against their design binding, not re-estimated.",
               "elapsed_seconds": time.perf_counter()-started}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
