#!/usr/bin/env python3
"""Plot the saved finite-forager selection and fresh commons-v3 comparisons."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.visualize import BACKGROUND, INK, MUTED, SECONDARY, digest, save, theme
import matplotlib
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np

VERSION = "commons-v3-navigation-figures-v1"
EVIDENCE_VERSION = "commons-v3-navigation-development-v1"
CONDITIONS = ("legacy_need2", "fixed_forager", "fixed_floor", "selected",
              "focal_aggressive_selected", "all_aggressive")
ANCHORS = CONDITIONS[:3]
WEIGHTS = (0., .05, .2)
WEIGHT_MARKERS = ("o", "s", "D")
LABELS = {"legacy_need2": "Legacy need-2", "fixed_forager": "Fixed forager",
          "fixed_floor": "Fixed floor", "selected": "Selected candidate",
          "focal_aggressive_selected": "One focal aggressive", "all_aggressive": "All aggressive"}
MARKERS = dict(zip(CONDITIONS, ("o", "s", "^", "D", "+", "x")))
LINES = dict(zip(CONDITIONS, (":", "--", "-.", "-", (0, (5, 1, 1, 1)), (0, (2, 1)))))
SENSITIVITIES = ("long_horizon", "keyed_priority", "lower_stock", "additive", "small_inventory")
PANEL_LABELS = {"long_horizon": "Long horizon · 512 ticks", "keyed_priority": "Keyed priority",
                "lower_stock": "Initial site stock 22", "additive": "Additive renewal",
                "small_inventory": "Carrying capacity 8"}
FIGURES = ("candidate-selection", "evaluation-performance", "aggressive-effects")
TABLES = ("candidate-scores.csv", "tuning-case-scores.csv", "condition-means.csv",
          "selected-effects.csv", "focal-effects.csv", "widespread-effects.csv", "reference-trajectories.csv")


def read(path):
    return json.loads(Path(path).read_text())


def path_label(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def cell_key(cell):
    panel = cell["panel"]
    return (0 if panel == "grid" else 1 + SENSITIVITIES.index(panel), cell["renewal_rate"], cell["need"])


def ordered_cells(summary):
    cells = sorted(summary["cells"], key=cell_key)
    if len(cells) != 14 or len({cell_key(c) for c in cells}) != 14:
        raise ValueError("expected all nine grid cells and five separate sensitivity cells")
    return cells


def load(source):
    from swarm_societies.commons_v3 import development_navigation_v1 as verifier
    receipt = verifier.verify(source, replay=False)
    design, summary, archive, tuning, selection = (read(source / name) for name in (
        "design.json", "summary.json", "manifest.json", "tuning/summary.json", "selection.json"))
    if (archive["version"] != EVIDENCE_VERSION or design["evaluation"]["conditions"] != list(CONDITIONS)
            or design["wealth_weights"] != list(WEIGHTS) or len(design["candidates"]) != 18):
        raise ValueError("unsupported navigation archive or condition registry")
    if set(design["tuning"]["seeds"]) & set(design["evaluation"]["seeds"]):
        raise ValueError("tuning and evaluation seeds overlap")
    candidate_ids = [c["id"] for c in design["candidates"]]
    if [c["id"] for c in tuning["candidates"]] != candidate_ids:
        raise ValueError("tuning score registry differs from the frozen design")
    scores = sorted(tuning["candidates"], key=lambda c: (-c["score"], -c["late_score"], c["id"]))
    if scores[0]["id"] != selection["candidate"]["id"] or scores[0]["id"] != tuning["selected_candidate_id"]:
        raise ValueError("selected candidate differs from exact frozen ranking")
    cells = ordered_cells(summary)
    if any(set(c["conditions"]) != set(CONDITIONS) or c["paired_configurations"] != 4 for c in cells):
        raise ValueError("evaluation summary has missing conditions or seed counts")
    selected_case = next(c for c in design["evaluation"]["cases"]
                         if c["id"] == design["evaluation"]["reference_frames_case"])
    reference_cases = [c for c in design["evaluation"]["cases"] if c["panel"] == "grid"
                       and c["config"]["renewal_rate"] == selected_case["config"]["renewal_rate"]
                       and c["config"]["need"] == selected_case["config"]["need"]]
    reference = [verifier.read_case(source / "evaluation/cases" / (c["id"] + ".json.gz")) for c in reference_cases]
    tuning_rows = []
    for case in design["tuning"]["cases"]:
        for candidate in design["candidates"]:
            record = verifier.read_case(source / verifier.tuning_path(case, candidate))
            values = record["episode"]["summary"]
            tuning_rows.append({"candidate_id": candidate["id"], **candidate["parameters"], "case_id": case["id"],
                                "seed": case["seed"], "renewal_rate": case["config"]["renewal_rate"],
                                "need": case["config"]["need"], "horizon": case["horizon"], **values,
                                "consumption_fraction_of_need": values["consumption_per_agent_tick"] / case["config"]["need"],
                                "late_consumption_fraction_of_need": values["late_consumption_per_agent_tick"] / case["config"]["need"]})
    return design, summary, archive, tuning, selection, selected_case, trajectory_means(reference), tuning_rows, receipt


def trajectory_means(reference):
    if len(reference) != 4 or len({r["case"]["horizon"] for r in reference}) != 1:
        raise ValueError("expected four complete reference trajectories of the same length")
    rows, horizon = [], reference[0]["case"]["horizon"]
    for condition in CONDITIONS:
        episodes = [next(e for e in record["episodes"] if e["condition"] == condition) for record in reference]
        if any(len(e["trajectory"]) != horizon for e in episodes):
            raise ValueError("incomplete reference trajectory")
        for index in range(horizon):
            saved = [episode["trajectory"][index] for episode in episodes]
            if any(row["tick"] != index + 1 for row in saved):
                raise ValueError("noncanonical reference trajectory tick")
            raw_means = {"mean_" + key: statistics.mean(row[key] for row in saved) for key in saved[0] if key != "tick"}
            cfg = reference[0]["case"]["config"]
            if any(record["case"]["config"] != cfg for record in reference):
                raise ValueError("reference configurations differ beyond seeds")
            rows.append({"condition": condition, "tick": index + 1, "configurations": len(reference), **raw_means,
                         "consumption_fraction_of_need": raw_means["mean_consumption"] / (cfg["n_agents"] * cfg["need"]),
                         "stock_fraction_of_capacity": raw_means["mean_stock"] / (cfg["n_patches"] * cfg["patch_capacity"]),
                         "off_site_agent_fraction": raw_means["mean_off_site_agents"] / cfg["n_agents"],
                         "hungry_off_site_agent_fraction": raw_means["mean_hungry_off_site_agents"] / cfg["n_agents"],
                         "known_sites_fraction": raw_means["mean_mean_known_sites"] / cfg["n_patches"]})
    return rows


def table(path, rows):
    if not rows:
        raise ValueError("cannot export an empty table")
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    return path


def export_tables(summary, tuning, selection, trajectories, tuning_rows, output):
    ranking = sorted(tuning["candidates"], key=lambda c: (-c["score"], -c["late_score"], c["id"]))
    candidates = [{"selection_rank": rank, "candidate_id": candidate["id"], **candidate["parameters"],
                   **{k: v for k, v in candidate.items() if k not in ("id", "parameters")},
                   "selected": candidate["id"] == selection["candidate"]["id"]}
                  for rank, candidate in enumerate(ranking, 1)]
    means, selected, focal, widespread = [], [], [], []
    for cell in ordered_cells(summary):
        base = {"panel": cell["panel"], "renewal_rate": cell["renewal_rate"], "need": cell["need"],
                "paired_configurations": cell["paired_configurations"]}
        for condition in CONDITIONS:
            values = cell["conditions"][condition]
            means.append({**base, "condition": condition, **values,
                          "consumption_fraction_of_need": values["consumption_per_agent_tick"] / cell["need"],
                          "late_consumption_fraction_of_need": values["late_consumption_per_agent_tick"] / cell["need"]})
        for anchor in ANCHORS:
            for outcome, values in sorted(cell["selected_minus_fixed"][anchor].items()):
                selected.append({**base, "contrast": "selected_minus_" + anchor, "outcome": outcome, **values})
        for outcome, values in sorted(cell["focal_deviation"].items()):
            focal.append({**base, "contrast": "focal_aggressive_minus_selected", "outcome": outcome, **values})
        for outcome, values in sorted(cell["all_aggressive_minus_selected"].items()):
            widespread.append({**base, "contrast": "all_aggressive_minus_selected", "outcome": outcome, **values})
    values = (candidates, tuning_rows, means, selected, focal, widespread, trajectories)
    return [table(output / name, rows) for name, rows in zip(TABLES, values)]


def candidate_plot(tuning, selection, output):
    scores = sorted(tuning["candidates"], key=lambda c: (-c["score"], -c["late_score"], c["id"]))
    selected_id = selection["candidate"]["id"]
    fig, axes = plt.subplots(1, 2, figsize=(15.8, 10.4))
    fig.text(.065, .973, "A finite numerical comparison of 18 local foragers", fontsize=19, weight="bold", va="top")
    fig.text(.065, .929, f"Selected: {selected_id} · one declared sweep · tuning seeds 62001–62002", fontsize=11, color=SECONDARY)
    fields = (("score", "late_score"), ("worst_case_score", "worst_cell_score"))
    titles = ("A  Mean consumption and final-quarter consumption", "B  Retained worst environment and worst cell")
    keys = (("Selection objective", "Final-quarter tie-break"), ("Worst single environment", "Worst two-seed cell mean"))
    for ax, names, title, labels in zip(axes, fields, titles, keys):
        ax.set_title(title, loc="left", fontsize=12, pad=20)
        ax.axhspan(-.48, .48, color=MUTED, zorder=0)
        for y, score in enumerate(scores):
            values = [score[key] for key in names]
            ax.plot(values, [y, y], color=SECONDARY, linewidth=.7, zorder=1)
            for value, offset, marker in zip(values, (-.11, .11), ("o", "s")):
                ax.plot(value, y + offset, marker=marker, color=INK, markerfacecolor=BACKGROUND,
                        linestyle="", markersize=5, markeredgewidth=1.1, zorder=2)
        ax.set_yticks(range(len(scores)), [c["id"] + (" *" if c["id"] == selected_id else "") for c in scores])
        ax.tick_params(axis="y", labelsize=9, length=0)
        ax.set_ylim(len(scores) - .5, -.5)
        ax.set_xlim(-.02, 1.035)
        ax.set_xlabel("Consumption / declared need")
        ax.grid(axis="x", alpha=.6)
        ax.legend(handles=[Line2D([], [], marker=marker, linestyle="", color=INK, markerfacecolor=BACKGROUND, label=label)
                           for marker, label in zip(("o", "s"), labels)], loc="upper center",
                  bbox_to_anchor=(.5, -.085), fontsize=9.5)
    fig.text(.065, .117, "* Shaded selected row. Ranking: highest equally weighted mean; then highest final-quarter mean; then smallest candidate ID.", fontsize=9.5, color=SECONDARY)
    fig.text(.065, .083, "Each candidate: nine rate/need cells × two tuning seeds = 18 environments. Entire sweep: 324 episodes; no adaptive proposals.", fontsize=9.5, color=SECONDARY)
    fig.text(.065, .049, "Worst-environment and worst-cell values are diagnostics, not selection criteria. All candidates and adverse outcomes are retained.", fontsize=9.5, color=SECONDARY)
    fig.text(.065, .015, "A supplied-family population baseline; no private optimum, equilibrium, global optimum or independent evolutionary replication is implied.", fontsize=9.5, color=SECONDARY)
    fig.subplots_adjust(left=.17, right=.98, top=.845, bottom=.25, wspace=.77)
    return save(fig, output / FIGURES[0])


def cell_axis(ax, cells, reference):
    labels = []
    for index, cell in enumerate(cells):
        is_reference = cell["panel"] == "grid" and cell["renewal_rate"] == reference["config"]["renewal_rate"] and cell["need"] == reference["config"]["need"]
        label = (f"r {cell['renewal_rate']:.2f} · need {cell['need']:.1f}"
                 if cell["panel"] == "grid" else PANEL_LABELS[cell["panel"]])
        labels.append(label + (" *" if is_reference else ""))
        if is_reference:
            ax.axhspan(index - .49, index + .49, color=MUTED, zorder=0)
    ax.set_yticks(range(len(cells)), labels)
    ax.tick_params(axis="y", labelsize=8.6, length=0)
    ax.set_ylim(len(cells) - .5, -.5)
    ax.axhline(8.5, color=SECONDARY, linewidth=.8)
    ax.grid(axis="x", alpha=.6)


def limits(values):
    lower, upper = min(0., min(values)), max(0., max(values))
    margin = max((upper - lower) * .1, .002)
    return lower - margin, upper + margin


def paired_point(ax, values, y, marker, divisor=1.):
    mean, lower, upper = (values[key] / divisor for key in ("mean", "min", "max"))
    ax.errorbar(mean, y, xerr=[[max(0., mean - lower)], [max(0., upper - mean)]], fmt=marker,
                color=INK, markerfacecolor=BACKGROUND, markersize=4.3, linewidth=.8, capsize=1.8)


def condition_legend():
    return [Line2D([], [], color=INK, marker=MARKERS[c], markerfacecolor=BACKGROUND,
                   linestyle=LINES[c], linewidth=1.1, label=LABELS[c]) for c in CONDITIONS]


def reference_plot(ax, trajectories, field, title, ylabel, reference, *, subtitle=None):
    ax.set_title(title, loc="left", pad=26)
    text = subtitle or f"Reference r {reference['config']['renewal_rate']:.2f} · need {reference['config']['need']:g}; mean across four fresh seeds"
    ax.text(0, 1.045, text, transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    for index, condition in enumerate(CONDITIONS):
        rows = [row for row in trajectories if row["condition"] == condition]
        ax.plot([row["tick"] for row in rows], [row[field] for row in rows], color=INK,
                marker=MARKERS[condition], markerfacecolor=BACKGROUND, markersize=4.3,
                markevery=(index * 5, 36), linewidth=1.1, linestyle=LINES[condition], label=LABELS[condition])
    ax.set_xlim(0, reference["horizon"])
    ax.set_ylim(-.025, 1.055)
    ax.set_xlabel("Completed tick")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=.6)


def evaluation_plot(summary, trajectories, reference, output):
    cells = ordered_cells(summary)
    fig, axes = plt.subplots(3, 2, figsize=(16.0, 16.4))
    fig.text(.065, .977, "Fresh-seed evaluation: consumption, stock and local access", fontsize=18, weight="bold", va="top")
    fig.text(.065, .948, "Four paired seeds 63001–63004 · nine grid cells plus all five sensitivities · six declared conditions", fontsize=10.6, color=SECONDARY)
    ax = axes[0, 0]
    ax.set_title("A  Population consumption in all 14 cells", loc="left", pad=26)
    ax.text(0, 1.045, "Four baseline populations; symbols are vertically offset", transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    cell_axis(ax, cells, reference)
    for index, condition in enumerate(CONDITIONS[:4]):
        for y, cell in enumerate(cells):
            value = cell["conditions"][condition]["consumption_per_agent_tick"] / cell["need"]
            ax.plot(value, y + (index - 1.5) * .16, marker=MARKERS[condition], color=INK,
                    markerfacecolor=BACKGROUND, markersize=4.8, linestyle="", zorder=2)
    ax.set_xlim(-.025, 1.045)
    ax.set_xlabel("Consumption / declared need")
    ax = axes[0, 1]
    ax.set_title("B  Selected minus each paired baseline", loc="left", pad=26)
    ax.text(0, 1.045, "Mean and observed min–max; not confidence intervals", transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    cell_axis(ax, cells, reference)
    values = []
    for index, anchor in enumerate(ANCHORS):
        for y, cell in enumerate(cells):
            effect = cell["selected_minus_fixed"][anchor]["consumption_per_agent_tick"]
            paired_point(ax, effect, y + (index - 1) * .2, MARKERS[anchor], cell["need"])
            values.extend(effect[key] / cell["need"] for key in ("min", "max"))
    ax.set_xlim(*limits(values))
    ax.axvline(0, color=SECONDARY, linestyle="--", linewidth=.8)
    ax.set_xlabel("Selected Δ consumption / declared need")
    reference_plot(axes[1, 0], trajectories, "consumption_fraction_of_need", "C  Reference consumption trajectory",
                   "Consumption / declared need", reference)
    reference_plot(axes[1, 1], trajectories, "stock_fraction_of_capacity", "D  Reference total ecological stock",
                   "Stock / total site capacity", reference)
    reference_plot(axes[2, 0], trajectories, "hungry_off_site_agent_fraction", "E  Shortfall while ending off-site",
                   "Affected individuals / population", reference,
                   subtitle="Positive tick shortfall and ending away from a resource site")
    reference_plot(axes[2, 1], trajectories, "mean_unoccupied_stock_fraction", "F  Stock at unoccupied sites",
                   "Unoccupied stock / total site capacity", reference,
                   subtitle="Evaluator-only diagnostic; neither reachability nor sustainable yield")
    fig.legend(handles=condition_legend(), loc="lower center", bbox_to_anchor=(.54, .078), ncol=3,
               fontsize=9.3, columnspacing=2.1, handlelength=3.1)
    fig.text(.065, .054, "* Shaded reference row. Sensitivities retain reference settings except their named change. Reference curves are unsmoothed tick means.", color=SECONDARY, fontsize=9.2)
    fig.text(.065, .034, "336 evaluation episodes; repeated seeds across cells and conditions are dependent. Off-site shortfall and unoccupied stock are distinct diagnostics.", color=SECONDARY, fontsize=9.2)
    fig.text(.065, .014, "Fresh evaluation compares the frozen selection with anchors; it does not complete ecological/incentive qualification or establish institutional usefulness.", color=SECONDARY, fontsize=9.2)
    fig.subplots_adjust(left=.165, right=.98, top=.889, bottom=.155, hspace=.66, wspace=.73)
    return save(fig, output / FIGURES[1])


def aggressive_plot(summary, reference, output):
    cells = ordered_cells(summary)
    fig, axes = plt.subplots(2, 2, figsize=(16.0, 13.8))
    fig.text(.065, .974, "Aggressive substitutions: focal incentives and population effects", fontsize=18, weight="bold", va="top")
    fig.text(.065, .940, "Same selected routing parameters; inventories, navigation and ecological paths may change · all 14 evaluation cells", fontsize=10.6, color=SECONDARY)
    for ax in axes.flat:
        cell_axis(ax, cells, reference)
        ax.axvline(0, color=SECONDARY, linestyle="--", linewidth=.8)
    ax = axes[0, 0]
    ax.set_title("A  Focal private utility", loc="left", pad=27)
    ax.text(0, 1.043, "One aggressive replacement; weight 0 is consumption alone", transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    values = []
    for index, (weight, marker) in enumerate(zip(WEIGHTS, WEIGHT_MARKERS)):
        for y, cell in enumerate(cells):
            effect = cell["focal_deviation"]["utility_" + str(weight)]
            paired_point(ax, effect, y + (index - 1) * .20, marker, cell["need"])
            values.extend(effect[key] / cell["need"] for key in ("min", "max"))
    ax.set_xlim(*limits(values))
    ax.set_xlabel("Focal Δ private utility / declared need")
    ax.legend(handles=[Line2D([], [], color=INK, marker=m, markerfacecolor=BACKGROUND, linestyle="", label=f"Weight {w:g}")
                       for w, m in zip(WEIGHTS, WEIGHT_MARKERS)], loc="upper center", bbox_to_anchor=(.5, -.13), ncol=3, fontsize=8.6)
    ax = axes[0, 1]
    ax.set_title("B  Consumption among the unchanged peers", loc="left", pad=27)
    ax.text(0, 1.043, "One aggressive replacement; average over the other 23 agents", transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    values = []
    for y, cell in enumerate(cells):
        effect = cell["focal_deviation"]["peer_consumption"]
        paired_point(ax, effect, y, "o", cell["need"])
        values.extend(effect[key] / cell["need"] for key in ("min", "max"))
    ax.set_xlim(*limits(values))
    ax.set_xlabel("Peer Δ consumption per tick / declared need")
    ax = axes[1, 0]
    ax.set_title("C  Everyone switches: consumption", loc="left", pad=27)
    ax.text(0, 1.043, "All aggressive minus all selected; population means", transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    values = []
    for index, (field, marker) in enumerate((("consumption_per_agent_tick", "o"), ("late_consumption_per_agent_tick", "s"))):
        for y, cell in enumerate(cells):
            effect = cell["all_aggressive_minus_selected"][field]
            paired_point(ax, effect, y + (index - .5) * .23, marker, cell["need"])
            values.extend(effect[key] / cell["need"] for key in ("min", "max"))
    ax.set_xlim(*limits(values))
    ax.set_xlabel("Population Δ consumption / declared need")
    ax.legend(handles=[Line2D([], [], color=INK, marker=m, markerfacecolor=BACKGROUND, linestyle="", label=label)
                       for m, label in (("o", "All ticks"), ("s", "Final quarter"))],
              loc="upper center", bbox_to_anchor=(.5, -.13), ncol=2, fontsize=9)
    ax = axes[1, 1]
    ax.set_title("D  Everyone switches: ecological stock", loc="left", pad=27)
    ax.text(0, 1.043, "All aggressive minus all selected; terminal stock", transform=ax.transAxes, fontsize=8.8, color=SECONDARY)
    values = []
    for y, cell in enumerate(cells):
        effect = cell["all_aggressive_minus_selected"]["terminal_stock_fraction"]
        paired_point(ax, effect, y, "o")
        values.extend(effect[key] for key in ("min", "max"))
    ax.set_xlim(*limits(values))
    ax.set_xlabel("Δ resource stock / total site capacity")
    fig.text(.065, .083, "* Shaded reference row. Points are four-seed means; whiskers are observed minimum–maximum paired differences, not confidence intervals.", fontsize=9.2, color=SECONDARY)
    fig.text(.065, .060, "Utility = (cumulative consumption + weight × terminal inventory) / horizon. Weighted endpoint wealth remains separate from consumption gains.", fontsize=9.2, color=SECONDARY)
    fig.text(.065, .037, "These are whole-policy substitutions. Mean off-site shortfall, terminal inventory and every fixed sensitivity remain in the companion tables.", fontsize=9.2, color=SECONDARY)
    fig.text(.065, .014, "No equilibrium, robust dilemma or institutional conclusion follows from this four-seed comparison. Zero evolutionary runs or experimental model calls.", fontsize=9.2, color=SECONDARY)
    fig.subplots_adjust(left=.165, right=.98, top=.875, bottom=.18, hspace=.67, wspace=.73)
    return save(fig, output / FIGURES[2])


def render(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("figure output must be separate from evidence")
    design, summary, archive, tuning, selection, reference, trajectories, tuning_rows, receipt = load(source)
    allowed = {"README.md", "manifest.json", *TABLES, *(f"{stem}.{ext}" for stem in FIGURES for ext in ("svg", "pdf", "png"))}
    if output.exists() and any(path.name not in allowed or not path.is_file() for path in output.iterdir()):
        raise ValueError("figure directory contains unrelated artifacts")
    if (output / "manifest.json").exists():
        prior = read(output / "manifest.json")
        if prior.get("version") != VERSION or prior.get("evidence_manifest_sha256") != receipt["manifest_sha256"]:
            raise ValueError("existing gallery belongs to another archive")
    output.mkdir(parents=True, exist_ok=True)
    theme()
    outputs = export_tables(summary, tuning, selection, trajectories, tuning_rows, output)
    outputs += candidate_plot(tuning, selection, output)
    outputs += evaluation_plot(summary, trajectories, reference, output)
    outputs += aggressive_plot(summary, reference, output)
    identical_anchors = [anchor for anchor in ("fixed_forager", "fixed_floor")
                         if design[anchor] == selection["candidate"]["parameters"]]
    duplicate_note = ("The selected parameters match " + ", ".join(identical_anchors) +
                      "; these named controls remain displayed separately and are not independent evidence."
                      if identical_anchors else "The selected parameters differ from both fixed anchor settings.")
    readme = output / "README.md"
    readme.write_text(f"""# Purposeful local navigation · Chromatic Field v1

All figures use the completed recorded numerical-selection and fresh-evaluation
bank. No figure rendering executes policies or physics. There is one declared
finite numerical sweep, zero independent evolutionary runs and zero experimental
model calls. Selection and evaluation are separate, and neither is the larger
ecological/incentive qualification gate.

![All candidate scores](candidate-selection.png)

[SVG](candidate-selection.svg) · [PDF](candidate-selection.pdf) · [PNG](candidate-selection.png)

**Selection caption.** All 18 supplied combinations of reserve 0/2/4 needs,
voluntary stock floor 0/0.25/0.5, and nearest/net-yield routing are retained.
Each candidate runs on nine grid cells and tuning seeds 62001–62002, yielding
18 environments and 324 total episodes. Panel A shows mean consumption divided
by case need (the primary objective) and mean final-quarter consumption divided
by need (the exact-tie secondary criterion). Rows follow descending primary,
then secondary score, then ascending candidate ID. The shaded starred candidate
`{selection['candidate']['id']}` was selected before evaluation. Panel B retains
the worst single environment and worst two-seed cell mean; neither diagnostic
enters selection. Vertical marker offsets reveal coincident values. A numerical
baseline from this finite family is not a private optimum or global optimum.

![Fresh evaluation and access diagnostics](evaluation-performance.png)

[SVG](evaluation-performance.svg) · [PDF](evaluation-performance.pdf) · [PNG](evaluation-performance.png)

**Evaluation caption.** The 56 fresh configurations use seeds 63001–63004,
disjoint from tuning and previous development banks. Panel A includes all nine
grid cells and five fixed sensitivities: longer horizon, keyed priority, lower
starting stocks, additive renewal and carrying capacity 8. Four baseline
populations are compared on identical physical starts. Panel B uses paired
selected-minus-legacy/fixed-forager/fixed-floor consumption differences;
symbols identify the subtracted baseline. Points are four-seed means and
whiskers are observed min–max, **not confidence intervals**. The shaded starred
row is the predeclared reference, r={reference['config']['renewal_rate']:g},
need={reference['config']['need']:g}, {reference['horizon']} ticks. Panels C–F
show all six conditions' unsmoothed mean reference trajectories over four seeds.
Panel E counts individuals with positive current-tick shortfall who end that
tick off-site; panel F reports stock at sites unoccupied at tick end, divided
by total site capacity. These are evaluator-only diagnostics. Unoccupied stock
does not establish reachability or sustainable harvest. Conditions use labels,
markers and neutral line styles; society colors are not assigned. {duplicate_note}

![Focal and widespread aggressive substitutions](aggressive-effects.png)

[SVG](aggressive-effects.svg) · [PDF](aggressive-effects.pdf) · [PNG](aggressive-effects.png)

**Aggressive-substitution caption.** Panels A and B replace one predeclared
selected focal agent with the aggressive version while its 23 peers retain
the selected baseline. Focal private utility is `(consumption + weight ×
terminal inventory) / horizon`, then divided by need; weight zero measures
consumption alone. Peer effects average over peers before pairing across seeds.
Panels C and D substitute the aggressive controller for everyone and show
population consumption (all ticks and final quarter) and terminal-stock
differences from the all-selected population. All 14 cells and all wealth
weights are retained. Whiskers again show the observed four-seed min–max,
not confidence intervals. Aggressive controllers retain selected routing
parameters but realized navigation, inventory and ecological paths can differ;
these are whole-policy interventions, not isolated harvesting mechanisms.

Complete recorded tables:

- [All candidate scores, parameters and exact selection rank](candidate-scores.csv)
- [Every tuning environment/candidate outcome](tuning-case-scores.csv)
- [All six evaluation condition means in every cell](condition-means.csv)
- [All paired selected-minus-baseline diagnostics](selected-effects.csv)
- [All focal effects, including terminal inventory](focal-effects.csv)
- [All widespread-aggressive effects](widespread-effects.csv)
- [All six reference trajectories and saved diagnostic means](reference-trajectories.csv)

Effect tables retain the original units in their field names; focal terminal
inventory is an unnormalized endpoint. Reference columns prefixed `mean_`
are four-seed means of the named recorded tick field; normalized plotting
columns explicitly name their denominator. Consumption and shortfall are
complementary outcomes, not independent welfare measures. The same environment
seeds recur across cells and conditions, so agents, ticks and parameter cells
are not independent replications. Evaluation contains {summary['episodes']}
episodes; tuning and evaluation together contain
{summary['total_tuning_and_evaluation']['episodes']} episodes. No curve uses
earlier-bank means from unmatched seeds. Once inspected, evaluation outcomes
are available to later development and are not untouched for a later study.

The renderer first calls `development_navigation_v1.verify(source, replay=False)`.
That verifies the source freeze, complete inventories and hashes, exact tuning
selection, selection bindings and recomputed saved aggregates, without semantic
replay. Full semantic replay remains the study verifier's separate job. The
figure manifest pins every input artifact, renderer/helper source, software
version and output hash. Same-runtime rerenders are deterministic; byte identity
across software versions is not asserted.

```bash
.venv/bin/python scripts/visualize_commons_v3_navigation_v1.py \\
  --source {path_label(source)} \\
  --output {path_label(output)}
```
""")
    outputs.append(readme)
    inputs = [source / "manifest.json", *(source / name for name in sorted(archive["artifacts_sha256"])),
              Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"]
    result = {"version": VERSION, "style": "Chromatic Field v1", "rendering_runs_simulation": False,
              "evidence_version": archive["version"], "evidence_manifest_sha256": receipt["manifest_sha256"],
              "study_status": "one finite numerical selection and fresh-seed comparison; not ecological or incentive qualification",
              "verification": receipt, "selected_candidate": selection["candidate"],
              "selected_matches_fixed_controls": identical_anchors,
              "sources": [{"path": path_label(path), "sha256": digest(path)} for path in inputs],
              "outputs": [{"path": path.name, "sha256": digest(path)} for path in outputs],
              "versions": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
              "reference_selection": {"case": reference["id"], "seeds": design["evaluation"]["seeds"],
                                      "ticks": [1, reference["horizon"]], "conditions": list(CONDITIONS), "smoothing": False},
              "caption": "All 18 declared tuning candidates; paired evaluation of six conditions on 56 fresh configurations. "
                         "All 14 evaluation cells, reference access/stock/consumption trajectories and focal/widespread aggressive "
                         "effects retained. Four-seed min–max ranges are not confidence intervals. One finite numerical sweep, "
                         "zero evolutionary runs and model calls; no optimality, equilibrium, qualification or institutional claim."}
    (output / "manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/commons-v3-navigation-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/commons-v3-navigation-v1")
    args = parser.parse_args()
    try:
        result = render(args.source, args.output)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.exit(1, f"Could not render verified navigation evidence: {error}\n")
    print(json.dumps({"version": VERSION, "figures": len(FIGURES), "outputs": len(result["outputs"]),
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
