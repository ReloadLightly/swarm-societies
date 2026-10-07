#!/usr/bin/env python3
"""Render the two completed qualification banks without executing policies."""
from __future__ import annotations

import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.visualize import BACKGROUND, INK, MUTED, RULE, SECONDARY, digest, save, theme
import matplotlib
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import matplotlib.pyplot as plt
import numpy as np

VERSION = "commons-v3-qualification-figures-v1"
CONTROLS = ("fixed_floor", "selected")
LABELS = {"fixed_floor": "Fixed floor", "selected": "Selected"}
MARKERS = {"fixed_floor": "o", "selected": "s"}
PANELS = ("grid", "long_horizon", "small_inventory", "lower_stock", "keyed_priority", "additive")
PANEL_LABELS = {"grid": "Primary reference", "long_horizon": "512 ticks",
                "small_inventory": "Capacity 8", "lower_stock": "Initial stock 22",
                "keyed_priority": "Keyed priority", "additive": "Additive renewal †"}
FIGURES = ("ecological-qualification", "primary-qualification", "peer-response", "reference-sensitivities")
TABLES = ("all-endpoints.csv", "all-criteria.csv", "all-verdicts.csv", "physical-certificates.csv",
          "reference-trajectories.csv")
STATUS = {"pass": "PASS", "fail": "FAIL", "unresolved": "UNRESOLVED"}
TRACE_FIELDS = ("consumption", "shortfall", "stock", "reserves", "growth", "movement_cost",
                "harvest_cost", "waste", "off_site_agents", "hungry_off_site_agents",
                "unoccupied_stock_fraction", "mean_known_sites", "depleted_patches")


def read(path):
    return json.loads(Path(path).read_text())


def path_label(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def exact_float(quantity):
    return float(Fraction(quantity["numerator"], quantity["denominator"]))


def is_reference(cell, design):
    return all(cell[key] == value for key, value in design["reference"].items())


def grid(summary):
    return sorted((cell for cell in summary["cells"] if cell["panel"] == "grid"),
                  key=lambda cell: (cell["renewal_rate"], cell["need"]))


def reference_cells(summary, design):
    return sorted((cell for cell in summary["cells"] if is_reference(cell, design)),
                  key=lambda cell: PANELS.index(cell["panel"]))


def load(ecology, incentive):
    from swarm_societies.commons_v3 import qualification_v1 as verifier
    # Supplying the original ecology directory also checks the incentive bank's
    # copied dependency against it. Verification never performs semantic replay.
    receipts = {"ecology": verifier.verify(ecology, replay=False),
                "incentive": verifier.verify(incentive, replay=False, ecology=ecology)}
    banks = {}
    for stage, source in (("ecology", ecology), ("incentive", incentive)):
        bank = {name: read(source / (name + ".json")) for name in ("design", "summary", "manifest")}
        bank["source"] = source
        design, summary = bank["design"], bank["summary"]
        if (design["stage"] != stage or summary["phase"] != stage
                or tuple(control["id"] for control in design["controls"]) != CONTROLS
                or design["wealth_weights"] != [0., .05, .2]
                or summary["statistics"] != design["statistics"]
                or len(grid(summary)) != 9):
            raise ValueError("unsupported qualification registry or summary")
        if any(set(cell["controls"]) != set(CONTROLS) for cell in summary["cells"]):
            raise ValueError("missing frozen control")
        banks[stage] = bank
    if (len(banks["ecology"]["summary"]["cells"]) != 9
            or len(banks["incentive"]["summary"]["cells"]) != 14
            or set(banks["ecology"]["design"]["seeds"]) & set(banks["incentive"]["design"]["seeds"])):
        raise ValueError("qualification cell or seed inventory differs")
    return banks, receipts, reference_trajectories(banks, verifier)


def reference_trajectories(banks, verifier):
    """Average recorded tick fields while holding only one full case in memory."""
    result = []
    for stage, bank in banks.items():
        design = bank["design"]
        cases = [case for case in design["cases"] if case["panel"] == "grid"
                 and all(case["config"][key] == value for key, value in design["reference"].items())]
        if len(cases) != len(design["seeds"]):
            raise ValueError("incomplete reference seed inventory")
        columns = {}
        for case in cases:
            record = verifier.read_case(bank["source"] / "cases" / (case["id"] + ".json.gz"))
            cfg = case["config"]
            for episode in record["episodes"]:
                if len(episode["trajectory"]) != case["horizon"]:
                    raise ValueError("reference trajectory length differs")
                for index, row in enumerate(episode["trajectory"], 1):
                    if row["tick"] != index:
                        raise ValueError("reference tick inventory differs")
                    key = episode["control"]["id"], episode["condition"], index
                    scalars = {field: row[field] for field in TRACE_FIELDS}
                    scalars.update({
                        "consumption_fraction_of_need": row["consumption"] / (cfg["n_agents"] * cfg["need"]),
                        "stock_fraction_of_capacity": row["stock"] / (cfg["n_patches"] * cfg["patch_capacity"]),
                        "off_site_agent_fraction": row["off_site_agents"] / cfg["n_agents"],
                        "hungry_off_site_agent_fraction": row["hungry_off_site_agents"] / cfg["n_agents"],
                        "depleted_site_fraction": row["depleted_patches"] / cfg["n_patches"],
                    })
                    for cohort in ("normal", "aggressive"):
                        scalars.update({cohort + "_" + field: row["cohorts"][cohort][field]
                                        for field in ("n", "consumption", "shortfall", "inventory")})
                    target = columns.setdefault(key, {field: [] for field in scalars})
                    for field, value in scalars.items():
                        target[field].append(value)
        for (control, condition, tick), values in sorted(columns.items()):
            if any(len(value) != len(cases) for value in values.values()):
                raise ValueError("reference tick has missing seeds")
            result.append({"stage": stage, "control": control, "condition": condition,
                           "tick": tick, "seed_count": len(cases),
                           **{field: statistics.mean(value) for field, value in values.items()}})
    return result


def table(path, rows):
    if not rows:
        raise ValueError("cannot export empty evidence table")
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({key: json.dumps(value, separators=(",", ":"), allow_nan=False)
                          if isinstance(value, (dict, list)) else value for key, value in row.items()}
                         for row in rows)
    return path


def descriptors(value, path=()):
    if isinstance(value, dict):
        if {"mean", "lower", "upper", "seeds", "values"} <= value.keys():
            yield path, value
        else:
            for key, item in sorted(value.items()):
                yield from descriptors(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            label = ("peers" + str(item["peer_count"]) if isinstance(item, dict)
                     and "peer_count" in item else str(index))
            yield from descriptors(item, (*path, label))


def export_tables(banks, trajectories, output):
    endpoints, criteria, verdicts, certificates = [], [], [], []
    for stage, bank in banks.items():
        for cell in bank["summary"]["cells"]:
            base = {"stage": stage, "cell": cell["id"], "panel": cell["panel"],
                    "renewal_rate": cell["renewal_rate"], "need": cell["need"], "horizon": cell["horizon"]}
            verdicts.append({**base, "scope": "cell", "status": cell["status"],
                             "feasibility": cell.get("feasibility")})
            for control, data in cell["controls"].items():
                verdicts.append({**base, "control": control, "scope": "control", "status": data["status"]})
                for path, row in descriptors(data):
                    item = {**base, "control": control, "endpoint": "/".join(path), **row}
                    endpoints.append(item)
                    if "status" in row:
                        criteria.append(item)
            for by_seed in cell.get("feasibility_certificates", []):
                for certificate in by_seed["certificates"]:
                    record = {**base, "seed": by_seed["seed"], "certificate_horizon": certificate["horizon"],
                              "window_start": certificate["window_start"], "window_ticks": certificate["window"]["ticks"],
                              "target_fraction": certificate["target_fraction"], "status": certificate["status"],
                              "limiting_bounds": certificate["limiting_bounds"]}
                    for name, value in certificate["bounds"].items():
                        if value is not None:
                            record[name] = exact_float(value)
                            record[name + "_numerator"] = value["numerator"]
                            record[name + "_denominator"] = value["denominator"]
                    certificates.append(record)
    summary = banks["incentive"]["summary"]
    verdicts.append({"stage": "combined", "scope": "primary_adjacent_pair",
                     "status": summary["primary_gate"]["status"]})
    for pair in summary["primary_gate"]["pairs"]:
        verdicts.append({"stage": "combined", "scope": "adjacent_pair", "cells": pair["cells"], **pair})
    for weight, row in summary["reference_robustness_by_weight"].items():
        verdicts.append({"stage": "incentive", "scope": "reference_robustness", "weight": weight, **row})
    verdicts.append({"stage": "combined", "scope": "overall_canonical_weight",
                     "status": summary["qualification_status"]})
    if len(criteria) != 194:
        raise ValueError("renderer expected the complete frozen 194-interval family")
    return [table(output / name, rows) for name, rows in zip(
        TABLES, (endpoints, criteria, verdicts, certificates, trajectories))]


def interval_point(ax, row, y, *, marker="o", scale=1., color=INK, filled=False, size=4):
    lower, mean, upper = (row[key] * scale for key in ("lower", "mean", "upper"))
    ax.plot([lower, upper], [y, y], color=color, linewidth=.85, zorder=2)
    ax.plot(mean, y, marker=marker, color=color, markerfacecolor=color if filled else BACKGROUND,
            linestyle="", markersize=size, markeredgewidth=1., zorder=3)


def legend_item(label, marker, *, style="", color=INK):
    return Line2D([], [], marker=marker, linestyle=style, color=color,
                  markerfacecolor=BACKGROUND, linewidth=.9, markersize=4, label=label)


def cell_rows(ax, cells, design):
    labels = [f"r {cell['renewal_rate']:.2f} · need {cell['need']:.1f}" for cell in cells]
    for index, cell in enumerate(cells):
        if is_reference(cell, design):
            ax.axhspan(index - .49, index + .49, color=MUTED, zorder=0)
            labels[index] += " *"
    ax.set_yticks(range(len(cells)), labels)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.set_ylim(len(cells) - .55, -.55)
    ax.grid(axis="x")


def certificate_bound(cell):
    records = [row for by_seed in cell["feasibility_certificates"] for row in by_seed["certificates"]
               if row["horizon"] == 512 and row["window_start"] == 0 and row["target_fraction"] == .95]
    if len(records) != 16:
        raise ValueError("missing complete-horizon certificates")
    values = [row["bounds"]["fraction_of_need"] for row in records]
    if any(value != values[0] for value in values):
        raise ValueError("seed-invariant configuration has different physical bounds")
    return exact_float(values[0])


def ecology_plot(banks, output):
    bank = banks["ecology"]
    design, summary = bank["design"], bank["summary"]
    cells = grid(summary)
    fig, axes = plt.subplots(2, 2, figsize=(15.6, 12.6))
    fig.text(.06, .973, "Ecological qualification under two frozen local controls", fontsize=19, weight="bold", va="top")
    fig.text(.06, .938, "512 ticks · 16 independent seeds · recorded outcomes and conservative physical bounds",
             fontsize=11, color=SECONDARY)
    for ax, control in zip(axes[0], CONTROLS):
        ax.set_title(LABELS[control] + " · five simultaneous criteria", loc="left", fontsize=12, pad=16)
        for cell in cells:
            x, y = design["rates"].index(cell["renewal_rate"]), design["needs"].index(cell["need"])
            row = cell["controls"][control]
            ax.add_patch(Rectangle((x - .48, y - .48), .96, .96,
                                   facecolor=MUTED if is_reference(cell, design) else BACKGROUND,
                                   edgecolor=RULE, linewidth=.7))
            values = row["summary"]
            ax.text(x, y + .27, STATUS[row["status"]], ha="center", va="center", fontsize=11, weight="bold")
            ax.text(x, y + .03, f"C {values['consumption_per_agent_tick']['mean']/cell['need']:.3f}"
                    f" · Q4 {values['late_consumption_per_agent_tick']['mean']/cell['need']:.3f}",
                    ha="center", va="center", fontsize=9.4)
            ax.text(x, y - .20, f"stock {values['late_stock_fraction']['mean']:.3f}"
                    f" · depleted {values['late_depleted_patch_time_fraction']['mean']:.3f}",
                    ha="center", va="center", fontsize=8.8, color=SECONDARY)
        ax.set_xticks(range(3), [f"{rate:g}" for rate in design["rates"]])
        ax.set_yticks(range(3), [f"{need:g}" for need in design["needs"]])
        ax.set_xlim(-.5, 2.5)
        ax.set_ylim(-.5, 2.5)
        ax.set_xlabel("Renewal rate")
        ax.set_ylabel("Need / agent-tick")
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(False)
    ax = axes[1, 0]
    ax.set_title("Recorded consumption and the physical upper bound", loc="left", fontsize=12, pad=16)
    ax.axvline(.95, color=SECONDARY, linestyle=":", linewidth=.9)
    for y, cell in enumerate(cells):
        for control, offset in zip(CONTROLS, (-.15, .15)):
            interval_point(ax, cell["controls"][control]["summary"]["consumption_per_agent_tick"],
                           y + offset, marker=MARKERS[control], scale=1 / cell["need"])
        ax.plot(certificate_bound(cell), y, marker="|", markersize=11, color=INK, linestyle="")
    cell_rows(ax, cells, design)
    ax.set_xlabel("Consumption / need · bound is not an attainable policy")
    ax.legend(handles=[legend_item(LABELS[c], MARKERS[c]) for c in CONTROLS]
              + [legend_item("Exact certificate upper bound", "|")],
              loc="upper left", bbox_to_anchor=(0, -.17), fontsize=9)
    ax = axes[1, 1]
    ax.set_title("Physical interpretation of each grid cell", loc="left", fontsize=12, pad=16)
    for y, cell in enumerate(cells):
        text = {"witnessed_viable": "Witnessed viable", "certified_insufficient": "Certified insufficient",
                "feasibility_unresolved": "Feasibility unresolved"}[cell["feasibility"]]
        winners = [LABELS[c] for c in CONTROLS if cell["controls"][c]["status"] == "pass"]
        ax.text(.02, y, text + (" · " + ", ".join(winners) if winners else ""), va="center", fontsize=9.5)
    cell_rows(ax, cells, design)
    ax.set_xticks([])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Complete-horizon 0.95 target; other certificates in CSV")
    ax.grid(False)
    fig.text(.06, .085, "C and Q4 are mean and final-quarter consumption / need. Stock and depleted are final-quarter fractions of site capacity and site-time.",
             fontsize=9.3, color=SECONDARY)
    fig.text(.06, .058, "Map verdicts use five simultaneous bounds. Consumption whiskers below are ordinary descriptive 95% intervals; * marks the fixed reference.",
             fontsize=9.3, color=SECONDARY)
    fig.text(.06, .031, "A permissive bound or an unsuccessful controller leaves feasibility unresolved. Witnessed viability is finite-horizon evidence, not indefinite sustainability.",
             fontsize=9.3, color=SECONDARY)
    fig.subplots_adjust(left=.11, right=.98, top=.875, bottom=.22, hspace=.57, wspace=.49)
    return save(fig, output / FIGURES[0])


def primary_plot(banks, output):
    bank = banks["incentive"]
    design, summary = bank["design"], bank["summary"]
    cells = grid(summary)
    names = ("focal_utility_gain_fraction", "population_consumption_loss_fraction",
             "population_late_consumption_loss_fraction")
    titles = ("A  One focal aggressive · utility gain", "B  All aggressive · population mean loss",
              "C  All aggressive · final-quarter loss")
    fig, axes = plt.subplots(1, 3, figsize=(17.5, 9.2))
    fig.text(.055, .965, "Primary incentive margins across all nine environments", fontsize=19, weight="bold", va="top")
    fig.text(.055, .913, f"Common adjacent ecological/incentive pair: {STATUS[summary['primary_gate']['status']]}"
             f" · broader canonical-weight qualification: {STATUS[summary['qualification_status']]}",
             fontsize=11, color=SECONDARY)
    for ax, metric, title in zip(axes, names, titles):
        ax.set_title(title, loc="left", fontsize=11.5, pad=17)
        margin = design["incentive_thresholds"][metric]
        ax.axvline(0, color=RULE, linewidth=.8)
        ax.axvline(margin, color=SECONDARY, linestyle=":", linewidth=1)
        for y, cell in enumerate(cells):
            for control, offset in zip(CONTROLS, (-.16, .16)):
                interval_point(ax, cell["controls"][control]["criteria"][metric],
                               y + offset, marker=MARKERS[control])
        cell_rows(ax, cells, design)
        ax.set_xlabel(f"Difference / need · required lower bound ≥ {margin:g}")
        ax.legend(handles=[legend_item(LABELS[c], MARKERS[c]) for c in CONTROLS], loc="upper center",
                  bbox_to_anchor=(.5, -.11), ncol=2, fontsize=9)
    fig.text(.055, .143, "Whiskers are the frozen simultaneous Student-t intervals (194-interval Bonferroni family; approximate seed-level coverage).",
             fontsize=9.6, color=SECONDARY)
    fig.text(.055, .105, "A uses 0 aggressive peers and wealth weight 0.05. B–C compare all restrained minus all aggressive. Vertical dotted lines are material-effect margins.",
             fontsize=9.6, color=SECONDARY)
    fig.text(.055, .067, "Both controls, all three margins and ecological viability must pass in the same adjacent pair containing the shaded reference. Every cell remains visible.",
             fontsize=9.6, color=SECONDARY)
    fig.text(.055, .029, "Agents, ticks and repeated parameter cells are not independent replicates. There are 16 independent incentive seeds and no new numerical selection.",
             fontsize=9.6, color=SECONDARY)
    fig.subplots_adjust(left=.125, right=.985, top=.80, bottom=.27, wspace=.72)
    return save(fig, output / FIGURES[1])


def curve(ax, x, rows, *, scale=1., marker="o", linestyle="-", color=INK, label):
    if any(row is None for row in rows):
        indices = [index for index, row in enumerate(rows) if row is not None]
        x, rows = [x[index] for index in indices], [rows[index] for index in indices]
    if not rows:
        return
    means = [row["mean"] * scale for row in rows]
    ax.plot(x, means, linestyle=linestyle, marker=marker, color=color, markerfacecolor=BACKGROUND,
            markersize=4, linewidth=.9, label=label)
    for point, row in zip(x, rows):
        ax.plot([point, point], [row["lower"] * scale, row["upper"] * scale],
                color=color, linewidth=.75)


def peer_plot(banks, output):
    bank = banks["incentive"]
    design = bank["design"]
    cell = next(cell for cell in grid(bank["summary"]) if is_reference(cell, design))
    fig, axes = plt.subplots(3, 2, figsize=(15.2, 13.8))
    fig.text(.06, .972, "Matched focal changes across the frozen peer populations", fontsize=19, weight="bold", va="top")
    fig.text(.06, .939, "Fixed primary reference · rate 0.24 · need 1.2 · 256 ticks · 16 paired seeds",
             fontsize=11, color=SECONDARY)
    for col, control in enumerate(CONTROLS):
        data = cell["controls"][control]
        paired = data["paired_focal"]
        x = [row["peer_fraction"] for row in paired]
        if [row["peer_count"] for row in paired] != design["peer_counts"]:
            raise ValueError("missing predeclared intermediate peer contrast")
        specifications = (
            (("consumption_per_tick", "Consumption", "o", "-"),
             ("utility_0.05", "Utility · weight 0.05", "s", "--"),
             ("terminal_wealth_contribution_0.05", "Weighted terminal inventory", "^", ":")),
            (("peer_consumption_per_tick", "All unchanged peers", "o", "-"),
             ("normal_peer_consumption_per_tick", "Restrained peers", "s", "--"),
             ("aggressive_peer_consumption_per_tick", "Aggressive peers", "^", ":")),
        )
        for row_index, specs in enumerate(specifications):
            ax = axes[row_index, col]
            for field, label, marker, style in specs:
                curve(ax, x, [row["differences"][field] for row in paired], scale=1 / cell["need"],
                      marker=marker, linestyle=style, label=label)
            ax.axhline(0, color=RULE, linewidth=.8)
            ax.set_title(LABELS[control] + (" · focal decomposition" if row_index == 0 else " · unchanged-peer effects"),
                         loc="left", fontsize=11.5)
            ax.set_ylabel("Paired change / need")
            ax.legend(loc="upper center", bbox_to_anchor=(.5, -.23), ncol=3, fontsize=8.2, columnspacing=1.1)
        ax = axes[2, col]
        for focal, label, marker in ((False, "Focal restrained", "o"), (True, "Focal aggressive", "s")):
            conditions = [data["conditions"][f"peers{count:02d}-focal{'A' if focal else 'R'}"]
                          for count in design["peer_counts"]]
            for field, suffix, style in (("consumption_per_agent_tick", " · mean", "-"),
                                         ("late_consumption_per_agent_tick", " · final quarter", "--")):
                curve(ax, x, [row["summary"][field] for row in conditions], scale=1 / cell["need"],
                      marker=marker, linestyle=style, label=label + suffix)
        ax.set_title(LABELS[control] + " · population consumption", loc="left", fontsize=11.5)
        ax.set_ylabel("Consumption / need")
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.23), ncol=2, fontsize=8.2, columnspacing=1.1)
        for ax in axes[:, col]:
            ax.set_xticks(x, ["0", "6/23", "12/23", "18/23", "23/23"])
            ax.set_xlabel("Aggressive share among the 23 peers")
            ax.grid(axis="y")
    fig.text(.06, .066, "Each focal pair changes only the focal policy at initialization; the same nested peer identities remain assigned. Realized movement and ecology may differ.",
             fontsize=9.2, color=SECONDARY)
    fig.text(.06, .041, "Whiskers are descriptive 95% seed-level intervals. Empty peer cohorts are omitted. Population prevalence is k/24 or (k+1)/24, distinct from the peer axis.",
             fontsize=9.2, color=SECONDARY)
    fig.text(.06, .016, "Only this predeclared reference is plotted here. The complete grid, all conditions, all weights and every retained seed value are exported in all-endpoints.csv.",
             fontsize=9.2, color=SECONDARY)
    fig.subplots_adjust(left=.095, right=.98, top=.875, bottom=.16, wspace=.30, hspace=1.0)
    return save(fig, output / FIGURES[2])


def stress_plot(banks, output):
    bank = banks["incentive"]
    design, summary = bank["design"], bank["summary"]
    cells = reference_cells(summary, design)
    if tuple(cell["panel"] for cell in cells) != PANELS:
        raise ValueError("missing reference sensitivity panel")
    fig, axes = plt.subplots(2, 3, figsize=(17.8, 11.0))
    fig.text(.055, .97, "Reference sensitivities retain utility and material outcomes", fontsize=19, weight="bold", va="top")
    verdicts = summary["reference_robustness_by_weight"]
    fig.text(.055, .925, "Logistic reference robustness: " + " · ".join(
        f"weight {weight:g}: {STATUS[verdicts[str(weight)]['status']]}" for weight in design["wealth_weights"]),
        fontsize=11, color=SECONDARY)
    for row_index, control in enumerate(CONTROLS):
        for col, title in enumerate(("Focal utility · three wealth weights", "Focal utility decomposition · weight 0.05",
                                     "All restrained minus all aggressive")):
            ax = axes[row_index, col]
            ax.set_title(LABELS[control] + " · " + title, loc="left", fontsize=10.7, pad=16)
            ax.axhspan(-.49, .49, color=MUTED, zorder=0)
            ax.axhline(4.5, color=RULE, linewidth=.8)
            ax.axvline(0, color=RULE, linewidth=.8)
            for y, cell in enumerate(cells):
                data = cell["controls"][control]
                focal = next(row["differences"] for row in data["paired_focal"] if row["peer_count"] == 0)
                if col == 0:
                    for weight, offset, marker in zip(design["wealth_weights"], (-.21, 0, .21), ("o", "s", "^")):
                        field = "focal_utility_gain_fraction_" + str(weight)
                        descriptor = data["robustness_criteria"].get(field)
                        interval_point(ax, descriptor or focal["utility_" + str(weight)], y + offset,
                                       marker=marker, scale=1. if descriptor else 1 / cell["need"])
                elif col == 1:
                    for field, offset, marker in (("consumption_per_tick", -.13, "o"),
                                                  ("terminal_wealth_contribution_0.05", .13, "^")):
                        interval_point(ax, focal[field], y + offset, marker=marker, scale=1 / cell["need"])
                else:
                    for criterion, raw, offset, marker in (
                            ("population_consumption_loss_fraction", "consumption_per_agent_tick", -.13, "o"),
                            ("population_late_consumption_loss_fraction", "late_consumption_per_agent_tick", .13, "s")):
                        descriptor = data["robustness_criteria"].get(criterion)
                        if descriptor is None:
                            source = data["all_aggressive_minus_all_restrained"][raw]
                            descriptor = {**source, "mean": -source["mean"] / cell["need"],
                                          "lower": -source["upper"] / cell["need"],
                                          "upper": -source["lower"] / cell["need"]}
                        interval_point(ax, descriptor, y + offset, marker=marker)
            if col != 1:
                ax.axvline(.01 if col == 0 else .05, color=SECONDARY, linestyle=":", linewidth=.9)
            ax.set_yticks(range(len(cells)), [PANEL_LABELS[cell["panel"]] for cell in cells])
            ax.tick_params(axis="y", labelsize=8.8, length=0)
            ax.set_ylim(len(cells) - .55, -.55)
            ax.set_xlabel("Difference / need")
            ax.grid(axis="x")
            labels = ([(f"weight {weight:g}", marker) for weight, marker in zip(design["wealth_weights"], ("o", "s", "^"))]
                      if col == 0 else [("Consumption", "o"), ("Weighted inventory", "^")] if col == 1
                      else [("Mean", "o"), ("Final quarter", "s")])
            ax.legend(handles=[legend_item(label, marker) for label, marker in labels],
                      loc="upper center", bbox_to_anchor=(.5, -.13), ncol=len(labels), fontsize=8.8)
    fig.text(.055, .104, "Left and right: simultaneous intervals for the five logistic panels; † additive renewal uses descriptive 95% intervals and is excluded from every robustness gate.",
             fontsize=9.4, color=SECONDARY)
    fig.text(.055, .075, "Middle: descriptive decomposition; mean consumption gain plus weighted terminal inventory equals mean utility gain. Interval endpoints do not add.",
             fontsize=9.4, color=SECONDARY)
    fig.text(.055, .046, "Each stress panel changes one declared setting and retains the same incentive seeds. Only the three endpoint arms are run outside the primary grid.",
             fontsize=9.4, color=SECONDARY)
    fig.text(.055, .017, "A failed or unresolved canonical-weight sensitivity blocks the broader qualification. Utility reweighting uses the same trajectories and cannot rescue that verdict.",
             fontsize=9.4, color=SECONDARY)
    fig.subplots_adjust(left=.12, right=.985, top=.82, bottom=.21, wspace=.76, hspace=.68)
    return save(fig, output / FIGURES[3])


def render(ecology, incentive, output):
    ecology, incentive, output = (Path(path).resolve() for path in (ecology, incentive, output))
    for source in (ecology, incentive):
        if output == source or output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("gallery must be separate from both evidence banks")
    banks, receipts, trajectories = load(ecology, incentive)
    evidence_hashes = {stage: row["manifest_sha256"] for stage, row in receipts.items()}
    allowed = {"README.md", "manifest.json", *TABLES,
               *(f"{stem}.{ext}" for stem in FIGURES for ext in ("svg", "pdf", "png"))}
    if output.exists() and any(path.name not in allowed or not path.is_file() for path in output.iterdir()):
        raise ValueError("gallery contains unrelated artifacts")
    if (output / "manifest.json").exists():
        prior = read(output / "manifest.json")
        if prior.get("version") != VERSION or prior.get("evidence_manifest_sha256") != evidence_hashes:
            raise ValueError("existing gallery belongs to different evidence")
    output.mkdir(parents=True, exist_ok=True)
    theme()
    outputs = export_tables(banks, trajectories, output)
    for plot in (ecology_plot, primary_plot, peer_plot, stress_plot):
        outputs.extend(plot(banks, output))
    summary = banks["incentive"]["summary"]
    readme = output / "README.md"
    readme.write_text(f"""# Frozen-control qualification · Chromatic Field v1

These figures use the completed ecological and incentive records. Rendering
executes no policies or physics. Ecology and incentives use separate sets of
16 independent seeds; repeated controls, cells, individuals and ticks are not
additional independent replicates. There are no model calls, evolutionary
runs, new parameter selection, institutions or optimal-policy claims.

The saved primary adjacent-pair verdict is **{summary['primary_gate']['status']}**.
The broader qualification, including every logistic reference sensitivity at
wealth weight 0.05, is **{summary['qualification_status']}**. These verdicts are
copied from verified evidence, not chosen by figure thresholds.

![Ecological qualification](ecological-qualification.png)

[SVG](ecological-qualification.svg) · [PDF](ecological-qualification.pdf) · [PNG](ecological-qualification.png)

**Ecology caption.** Both frozen controls are shown on all nine 512-tick cells.
Map status uses all five prespecified simultaneous criteria. Map numbers show
mean and final-quarter consumption divided by need, final-quarter stock divided
by capacity, and depleted-site-time fraction. Depletion means stock strictly
below 10% of capacity after renewal. The lower consumption plot uses ordinary
descriptive 95% seed-level intervals and the exact rational certificate's
complete-horizon upper bound, converted to a float only for display. The dotted
line is the 0.95 consumption target. The physical classification names a
witnessing frozen control when one passes; the stricter ecological gate requires
both. A permissive upper bound or controller failure does not establish physical
feasibility or infeasibility. All horizon/window/target certificates remain in
the table. Shading and * identify the fixed reference.

![Primary material margins](primary-qualification.png)

[SVG](primary-qualification.svg) · [PDF](primary-qualification.pdf) · [PNG](primary-qualification.png)

**Primary caption.** The three columns show zero-aggressive-peer focal utility
gain at wealth weight 0.05, all-restrained minus all-aggressive population mean
consumption, and the same loss during the final quarter, each divided by need.
Points are 16-seed paired means; whiskers are simultaneous approximate Student-t
intervals from the frozen 194-named-interval Bonferroni family, not descriptive
intervals. Required lower-bound margins are 0.01, 0.05 and 0.05. Qualification
requires one common adjacent pair containing the reference to pass every
ecological and incentive criterion for both controls. All cells and adverse
outcomes are retained. These are supplied whole-policy substitutions, not
extraction-only mechanisms, best responses or equilibrium tests.

![Matched peer populations](peer-response.png)

[SVG](peer-response.svg) · [PDF](peer-response.pdf) · [PNG](peer-response.png)

**Peer-response caption.** Only the predeclared primary reference is plotted.
At each peer count 0/6/12/18/23, the two branches have the same initial physical
state and nested peer identities; only the focal assignment changes. The upper
row separates focal consumption, weighted terminal inventory and utility. The
middle row retains effects on all unchanged peers and each nonempty assigned
peer cohort. The lower row shows both branches' population mean and final-quarter
consumption. Whiskers are descriptive 95% seed-level intervals and do not add
new gates. Empty cohorts are omitted, not treated as measured zero. The peer
denominator is 23; the full population aggressive share is k/24 or (k+1)/24.
The CSV retains every grid cell, prevalence, cohort, utility weight and seed.

![Reference sensitivities](reference-sensitivities.png)

[SVG](reference-sensitivities.svg) · [PDF](reference-sensitivities.pdf) · [PNG](reference-sensitivities.png)

**Sensitivity caption.** All six reference panels remain visible for both
controls. The left column rescores the same focal trajectories at weights
0/0.05/0.2. The middle column decomposes canonical-weight utility into consumption
and weighted terminal inventory; those whiskers are descriptive 95% intervals.
The right column retains mean and final-quarter population consumption losses.
Left/right whiskers for five logistic panels are simultaneous bounds. Additive
renewal, marked †, has descriptive intervals and is excluded from robustness
gates. A nonsignificant additive effect is not proof of no effect. Only three
endpoint arms are recorded in sensitivity panels, so no intermediate-peer
stress curves are inferred. Reference stress evidence does not establish
robustness throughout the grid or under arbitrary deviations.

Complete tables:

- [Every recorded endpoint, paired contrast and retained seed value](all-endpoints.csv)
- [All 194 simultaneous criteria, exact saved verdicts and thresholds](all-criteria.csv)
- [Control, cell, common-pair, robustness and combined verdicts](all-verdicts.csv)
- [Every physical certificate, including exact numerators and denominators](physical-certificates.csv)
- [Unsmoothed primary-reference tick means for all conditions in both banks](reference-trajectories.csv)

Endpoint paths identify the complete saved summary structure. List-valued CSV
columns use JSON, preserving paired seed order and all observations. No raw seed
is dropped because its effect is negative. Reference trajectories average each
recorded tick over all 16 seeds; the initial state is not synthesized as tick
zero. Cohort consumption/shortfall/inventory trajectory columns are cohort totals,
and n is the cohort count. Access and depletion columns are evaluator diagnostics
and do not enter policy packets. Consumption and shortfall are complementary,
not independent welfare outcomes.

Intervals use fixed Student-t critical values from the prospective registry.
Six primary-reference entries recur in the robustness family: 194 named
interval slots cover 188 distinct designated estimand intervals. The frozen
Bonferroni denominator stays 194.
Coverage is approximate and model-based; Bonferroni does not make it
distribution-free. Empty or zero-variance samples do not establish universal
invariance. Exact saved comparisons determine every gate, without tolerance.

Before plotting, qualification_v1.verify(replay=False) checks both complete banks
and binds the incentive copy to the original ecology. It validates inventories,
source/artifact hashes and recomputed saved aggregates without executing
episodes. Semantic replay is a separate validation step. The manifest pins all
input artifacts, renderer/helper sources, library versions and output hashes.
Same-runtime deterministic exports do not promise identical bytes across
software versions.

```bash
.venv/bin/python scripts/visualize_commons_v3_qualification_v1.py \\
  --ecology {path_label(ecology)} \\
  --incentive {path_label(incentive)} \\
  --output figures/commons-v3-qualification-v1
```
""")
    outputs.append(readme)
    inputs = [Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"]
    for bank in banks.values():
        inputs.extend([bank["source"] / "manifest.json",
                       *(bank["source"] / name for name in sorted(bank["manifest"]["artifacts_sha256"]))])
    result = {"version": VERSION, "style": "Chromatic Field v1", "rendering_runs_simulation": False,
              "evidence_manifest_sha256": evidence_hashes, "verification": receipts,
              "primary_gate": summary["primary_gate"], "qualification_status": summary["qualification_status"],
              "reference_robustness_by_weight": summary["reference_robustness_by_weight"],
              "sources": [{"path": path_label(path), "sha256": digest(path)} for path in inputs],
              "outputs": [{"path": path.name, "sha256": digest(path)} for path in outputs],
              "versions": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
              "reference_trajectory_selection": {
                  stage: {"reference": bank["design"]["reference"], "seeds": bank["design"]["seeds"],
                          "smoothing": False, "includes_all_conditions": True} for stage, bank in banks.items()},
              "caption": "Two frozen legal local controls, disjoint ecology/incentive seed banks, complete prospective "
                         "criteria, physical bounds, matched peer effects and reference sensitivities. Approximate "
                         "seed-level intervals; finite-horizon qualification only. No new selection or model calls."}
    (output / "manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ecology", type=Path, default=ROOT / "evidence/commons-v3-ecology-qualification-v1")
    parser.add_argument("--incentive", type=Path, default=ROOT / "evidence/commons-v3-incentive-qualification-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/commons-v3-qualification-v1")
    args = parser.parse_args()
    try:
        result = render(args.ecology, args.incentive, args.output)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.exit(1, f"Could not render verified qualification evidence: {error}\n")
    print(json.dumps({"version": VERSION, "figures": len(FIGURES), "outputs": len(result["outputs"]),
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
