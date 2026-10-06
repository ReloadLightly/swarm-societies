#!/usr/bin/env python3
"""Render recorded world-model-v1 controls in Chromatic Field style."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.visualize import (BACKGROUND, INK, MUTED, RULE, SECONDARY,
                                      STYLE, digest, save, society_color, theme)
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

RENDERER_VERSION = "world-model-v1-figures-v1"
BOOTSTRAP_SEED = 7301
CONDITIONS = ("prior", "private", "pooled")
CONDITION_LABELS = {
    "prior": "Frozen prior", "private": "Private observations",
    "pooled": "Pooled evidence reference",
}
CONDITION_STYLES = {"prior": ":", "private": "-", "pooled": "--"}
PARAMETER_LABELS = {
    "r": "Base renewal", "b": "Own infrastructure return",
    "g": "External infrastructure spillover",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Recorded table is empty: {path}")
    return rows


def finite(value, label):
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"Non-finite recorded {label}: {value}")
    return number


def heading(fig, title, subtitle):
    fig.text(0.075, 0.97, title, fontsize=19, weight="bold", va="top")
    fig.text(0.075, 0.915, subtitle, fontsize=10.5, color=SECONDARY, va="top")


def condition_legend(fig, *, bottom=0.035):
    handles = [Line2D([0], [0], color=SECONDARY, linestyle=CONDITION_STYLES[c],
                      linewidth=1.8, label=CONDITION_LABELS[c]) for c in CONDITIONS]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, bottom),
               ncol=3, fontsize=10, handlelength=3.5, columnspacing=2.3)


def arena_curve(rows, value_key, *, arena_key="arena_id", tick_key="tick"):
    """Average within an arena first; resample complete arena trajectories."""
    arenas = sorted({row[arena_key] for row in rows})
    ticks = sorted({int(row[tick_key]) for row in rows})
    if not arenas or not ticks:
        raise ValueError("Cannot summarize an empty recorded learning curve")
    matrix = np.empty((len(arenas), len(ticks)))
    for i, arena in enumerate(arenas):
        for j, tick in enumerate(ticks):
            values = [finite(row[value_key], value_key) for row in rows
                      if row[arena_key] == arena and int(row[tick_key]) == tick]
            if not values:
                raise ValueError(f"Incomplete arena trajectory: {arena}, tick {tick}")
            matrix[i, j] = np.mean(values)
    means = matrix.mean(axis=0)
    if len(arenas) == 1:
        return np.asarray(ticks), means, None, None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = rng.integers(0, len(arenas), size=(2000, len(arenas)))
    boot = matrix[samples].mean(axis=1)
    low, high = np.quantile(boot, [0.025, 0.975], axis=0)
    return np.asarray(ticks), means, low, high


def draw_curve(ax, rows, value_key, society, condition, *, shade=True):
    ticks, means, low, high = arena_curve(rows, value_key)
    color = society_color(society)
    ax.plot(ticks, means, color=color, linestyle=CONDITION_STYLES[condition],
            linewidth=1.85 if condition == "private" else 1.4)
    if shade and low is not None:
        ax.fill_between(ticks, low, high, color=color,
                        alpha=0.09 if condition == "private" else 0.035, linewidth=0)
    ax.grid(axis="y", alpha=0.55)
    ax.set_axisbelow(True)


def select(rows, *, society=None, condition=None, parameter=None, tick=None):
    return [r for r in rows
            if (society is None or int(r["society"]) == society)
            and (condition is None or r["condition"] == condition)
            and (parameter is None or r["parameter"] == parameter)
            and (tick is None or int(r["tick"]) == tick)]


def load_study(source: Path):
    design = json.loads((source / "design.json").read_text())
    summary = json.loads((source / "summary.json").read_text())
    checkpoints = read_csv(source / "checkpoints.csv")
    parameters = read_csv(source / "parameters.csv")
    arenas = sorted({r["arena_id"] for r in checkpoints})
    societies = sorted({int(r["society"]) for r in checkpoints})
    ticks = sorted({int(r["tick"]) for r in checkpoints})
    actual = Counter((r["arena_id"], int(r["society"]), r["condition"], int(r["tick"]))
                     for r in checkpoints)
    expected = {(a, s, c, t) for a in arenas for s in societies
                for c in CONDITIONS for t in ticks}
    if set(actual) != expected or any(v != 1 for v in actual.values()):
        raise ValueError("Checkpoint evidence is incomplete or contains duplicates")
    actual_parameters = Counter((r["arena_id"], int(r["society"]), r["condition"],
                                 int(r["tick"]), r["parameter"]) for r in parameters)
    expected_parameters = {(*cell, p) for cell in expected for p in PARAMETER_LABELS}
    if set(actual_parameters) != expected_parameters or any(v != 1 for v in actual_parameters.values()):
        raise ValueError("Parameter evidence is incomplete or contains duplicates")
    for row in checkpoints:
        for key in ("probe_crps", "probe_mse", "coverage_90", "interval_width_90",
                    "parameter_nrmse", "unique_observations"):
            finite(row[key], key)
    for row in parameters:
        row["absolute_error"] = abs(finite(row["posterior_mean"], "posterior_mean")
                                     - finite(row["true_value"], "true_value"))
        lower, upper = finite(row["lo90"], "lo90"), finite(row["hi90"], "hi90")
        if upper < lower:
            raise ValueError("Reversed recorded parameter credible interval")
        row["parameter_covered_90"] = float(lower <= float(row["true_value"]) <= upper)
        row["parameter_width_90"] = upper - lower
    return {"design": design, "summary": summary, "checkpoints": checkpoints,
            "parameters": parameters, "arenas": arenas, "societies": societies,
            "ticks": ticks, "n_arenas": len(arenas)}


def learning_figure(study, output):
    societies = study["societies"]
    fig, axes = plt.subplots(2, len(societies), figsize=(13.4, 9.0), squeeze=False, sharey=True)
    heading(fig, "How quickly does prediction improve?",
            "Instrumented parameter-learning control · fixed policies · 32 common uncapped probes per arena")
    for col_index, sid in enumerate(societies):
        ax = axes[0, col_index]
        for condition in CONDITIONS:
            draw_curve(ax, select(study["checkpoints"], society=sid, condition=condition),
                       "probe_crps", sid, condition)
        ax.set_title(f"Society {sid}", color=society_color(sid), loc="left")
        ax.set_xlabel("Completed world ticks")
        ax.set_xlim(min(study["ticks"]), max(study["ticks"]))
        ax.set_ylim(bottom=0)
        ax.set_xticks([t for t in study["ticks"] if t == 0 or t >= max(study["ticks"]) / 4])
        evidence_ax = axes[1, col_index]
        evidence_ends = []
        for condition in ("private", "pooled"):
            rows = select(study["checkpoints"], society=sid, condition=condition)
            ticks, means, low, high = arena_curve(rows, "probe_crps")
            counts = []
            for tick in ticks:
                observed = {finite(r["unique_observations"], "unique_observations") for r in rows if int(r["tick"]) == tick}
                if len(observed) != 1:
                    raise ValueError("Evidence-axis curves require equal observation counts across arenas at a checkpoint")
                counts.append(observed.pop())
            evidence_ends.append(max(counts))
            color = society_color(sid)
            evidence_ax.plot(counts, means, color=color, linestyle=CONDITION_STYLES[condition],
                             linewidth=1.85 if condition == "private" else 1.4, marker="o", markersize=3)
            if low is not None:
                evidence_ax.fill_between(counts, low, high, color=color,
                                         alpha=0.09 if condition == "private" else 0.035, linewidth=0)
        prior_rows = select(study["checkpoints"], society=sid, condition="prior")
        _, prior_means, _, _ = arena_curve(prior_rows, "probe_crps")
        if not np.allclose(prior_means, prior_means[0], atol=1e-12, rtol=1e-12):
            raise ValueError("Frozen-prior score changed across checkpoints; cannot draw a single reference")
        evidence_ax.axhline(prior_means[0], color=society_color(sid), linestyle=":", linewidth=1.4)
        overlap = min(evidence_ends)
        evidence_ax.axvspan(0, overlap, color=MUTED, alpha=0.7, zorder=0)
        evidence_ax.axvline(overlap, color=RULE, linewidth=0.8)
        evidence_ax.text(0.98, 0.94, f"Common range: 0–{overlap:.0f}", transform=evidence_ax.transAxes,
                         ha="right", va="top", fontsize=8.7, color=SECONDARY)
        evidence_ax.set_xlabel("Unique observations assimilated")
        evidence_ax.set_xlim(0, max(evidence_ends) * 1.025)
        evidence_ax.set_xticks(sorted({0, overlap, max(evidence_ends) * 2 / 3, max(evidence_ends)}))
        evidence_ax.grid(axis="y", alpha=0.55)
        evidence_ax.set_axisbelow(True)
    axes[0, 0].set_ylabel("Probe CRPS · resource units\nBy elapsed time")
    axes[1, 0].set_ylabel("Probe CRPS · resource units\nBy unique evidence")
    fig.text(0.075, 0.145,
             f"{study['n_arenas']} independent arenas. Shading around curves: pointwise 95% arena bootstrap intervals. Lower CRPS is better.",
             fontsize=9.5, color=SECONDARY)
    fig.text(0.075, 0.105,
             "Bottom: gray marks the common evidence range; dots are recorded checkpoints. The frozen prior is a horizontal reference.",
             fontsize=9.0, color=SECONDARY)
    condition_legend(fig, bottom=0.025)
    fig.subplots_adjust(left=0.085, right=0.965, top=0.815, bottom=0.23, wspace=0.17, hspace=0.38)
    return save(fig, output / "learning-curves")


def parameter_figure(study, output):
    societies = study["societies"]
    params = list(PARAMETER_LABELS)
    fig, axes = plt.subplots(len(societies), len(params), figsize=(13.4, 10.2), squeeze=False,
                             sharex=True, sharey="col")
    heading(fig, "Parameter recovery remains a separate test",
            "Absolute posterior-mean error against hidden simulator truth · supplied linear renewal family")
    for row_index, sid in enumerate(societies):
        for col_index, parameter in enumerate(params):
            ax = axes[row_index, col_index]
            for condition in CONDITIONS:
                rows = select(study["parameters"], society=sid, condition=condition, parameter=parameter)
                draw_curve(ax, rows, "absolute_error", sid, condition)
            ax.set_ylim(bottom=0)
            ax.set_xlim(min(study["ticks"]), max(study["ticks"]))
            ax.set_xticks([t for t in study["ticks"] if t == 0 or t >= max(study["ticks"]) / 4])
            if row_index == 0:
                ax.set_title(f"{parameter}  /  {PARAMETER_LABELS[parameter]}", fontsize=11, loc="left")
            if col_index == 0:
                ax.set_ylabel(f"Society {sid}\nMean absolute error", color=society_color(sid))
            if row_index == len(societies) - 1:
                ax.set_xlabel("Completed world ticks")
    fig.text(0.075, 0.125,
             "Panels use each coefficient's own units. Low predictive error can coexist with uncertain or inaccurate coefficients.",
             fontsize=9.5, color=SECONDARY)
    condition_legend(fig, bottom=0.025)
    fig.subplots_adjust(left=0.09, right=0.965, top=0.82, bottom=0.205, wspace=0.23, hspace=0.32)
    return save(fig, output / "parameter-recovery")


def arena_values(rows, key):
    arenas = sorted({r["arena_id"] for r in rows})
    values = np.asarray([np.mean([finite(r[key], key) for r in rows if r["arena_id"] == a])
                         for a in arenas])
    return arenas, values


def interval(values):
    values = np.asarray(values, dtype=float)
    if len(values) == 1:
        return float(values.mean()), None, None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.integers(0, len(values), size=(2000, len(values)))
    lo, hi = np.quantile(values[draws].mean(axis=1), [0.025, 0.975])
    return float(values.mean()), float(lo), float(hi)


def calibration_figure(study, output):
    fig, axes = plt.subplots(1, 2, figsize=(13.4, 6.0))
    heading(fig, "Are uncertainty intervals useful?",
            f"32 common uncapped probes at tick {max(study['ticks'])} · 90% predictive intervals · fixed-law evaluation")
    for ax, key, name in zip(axes, ("coverage_90", "interval_width_90"),
                              ("Observed coverage", "Mean interval width · resource units")):
        for index, condition in enumerate(CONDITIONS):
            for offset, sid in zip(np.linspace(-0.17, 0.17, len(study["societies"])), study["societies"]):
                rows = select(study["checkpoints"], society=sid, condition=condition,
                              tick=max(study["ticks"]))
                _, values = arena_values(rows, key)
                mean, lo, hi = interval(values)
                ax.scatter([mean], [index + offset], color=society_color(sid), s=35, zorder=3)
                if lo is not None:
                    ax.plot([lo, hi], [index + offset] * 2, color=society_color(sid), linewidth=1.4)
        ax.set_yticks(range(len(CONDITIONS)), [CONDITION_LABELS[c] for c in CONDITIONS])
        ax.invert_yaxis()
        ax.set_ylim(2.55, -0.55)
        ax.set_xlabel(name)
        ax.set_title(name, loc="left", fontsize=11)
        ax.grid(axis="x", alpha=0.55)
        ax.set_axisbelow(True)
        ax.set_xlim(left=0)
    axes[0].axvline(0.9, color=SECONDARY, linestyle="--", linewidth=0.9)
    axes[0].set_xlim(0, 1.03)
    axes[0].text(0.9, 1.02, "Nominal 90%", transform=axes[0].get_xaxis_transform(),
                 ha="center", va="bottom", color=SECONDARY, fontsize=9)
    handles = [Line2D([0], [0], marker="o", linestyle="", color=society_color(s), label=f"Society {s}")
               for s in study["societies"]]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.025), ncol=len(handles))
    fig.text(0.075, 0.15,
             "Dots: arena means. Lines: 95% arena bootstrap intervals. Coverage and width must be interpreted together.",
             fontsize=9.5, color=SECONDARY)
    fig.text(0.075, 0.105,
             "Prior and pooled references are repeated by society for comparison; these copies are not independent evidence.",
             fontsize=9.0, color=SECONDARY)
    fig.subplots_adjust(left=0.20, right=0.96, top=0.73, bottom=0.29, wspace=0.68)
    return save(fig, output / "calibration-width")


def parameter_statistics(study):
    """Parameter summaries use one mean per arena, never society copies as N."""
    result = []
    metrics = (("absolute_error", "mae"), ("parameter_covered_90", "coverage90"),
               ("parameter_width_90", "mean_width90"))
    for condition in CONDITIONS:
        for parameter in PARAMETER_LABELS:
            rows = select(study["parameters"], condition=condition, parameter=parameter,
                          tick=max(study["ticks"]))
            item = {"condition": condition, "parameter": parameter,
                    "endpoint_tick": max(study["ticks"]), "unit": "arena",
                    "count_independent_arenas": len({r["arena_id"] for r in rows}),
                    "societies_averaged_within_arena": len(study["societies"])}
            for field, metric in metrics:
                _, values = arena_values(rows, field)
                mean, lo, hi = interval(values)
                item.update({metric: mean, f"{metric}_lo95": lo, f"{metric}_hi95": hi})
            result.append(item)
    return result


def parameter_uncertainty_figure(study, output):
    statistics = parameter_statistics(study)
    path = output / "parameter-statistics.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(statistics[0]))
        writer.writeheader()
        writer.writerows(statistics)
    fig, axes = plt.subplots(2, len(PARAMETER_LABELS), figsize=(13.4, 9.0), squeeze=False)
    heading(fig, "Parameter uncertainty needs its own calibration check",
            f"Terminal 90% credible intervals at tick {max(study['ticks'])} · hidden coefficient values · {study['n_arenas']} independent arenas")
    for col_index, parameter in enumerate(PARAMETER_LABELS):
        for row_index, field in enumerate(("parameter_covered_90", "parameter_width_90")):
            ax = axes[row_index, col_index]
            for condition_index, condition in enumerate(CONDITIONS):
                for offset, sid in zip(np.linspace(-0.17, 0.17, len(study["societies"])), study["societies"]):
                    rows = select(study["parameters"], society=sid, condition=condition,
                                  parameter=parameter, tick=max(study["ticks"]))
                    _, values = arena_values(rows, field)
                    mean, lo, hi = interval(values)
                    y = condition_index + offset
                    ax.scatter([mean], [y], color=society_color(sid), s=29, zorder=3)
                    if lo is not None:
                        ax.plot([lo, hi], [y, y], color=society_color(sid), linewidth=1.25)
            ax.set_yticks(range(len(CONDITIONS)),
                          [CONDITION_LABELS[c] for c in CONDITIONS] if col_index == 0 else [])
            ax.set_ylim(2.55, -0.55)
            ax.grid(axis="x", alpha=0.55)
            ax.set_axisbelow(True)
            ax.set_xlim(left=0)
            if row_index == 0:
                ax.set_title(f"{parameter}  /  {PARAMETER_LABELS[parameter]}", fontsize=10.8, loc="left")
                ax.axvline(0.9, color=SECONDARY, linestyle="--", linewidth=0.9)
                ax.set_xlim(0, 1.04)
                ax.set_xlabel("Fraction of true values covered", fontsize=9.5)
            else:
                ax.set_xlabel(f"Mean credible-interval width · {parameter} units", fontsize=9.5)
    handles = [Line2D([0], [0], marker="o", linestyle="", color=society_color(s), label=f"Society {s}")
               for s in study["societies"]]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.025), ncol=len(handles))
    fig.text(0.075, 0.155,
             "Dots: society estimates across arenas. Lines: 95% arena bootstrap intervals. Dashed line: nominal 90% coverage.",
             fontsize=9.2, color=SECONDARY)
    pooled_g = next(r for r in statistics if r["condition"] == "pooled" and r["parameter"] == "g")
    fig.text(0.075, 0.115,
             f"Pooled spillover coverage: {pooled_g['coverage90']:.1%} [95% interval {pooled_g['coverage90_lo95']:.1%}, {pooled_g['coverage90_hi95']:.1%}]. "
             "Parameter calibration needs further validation.", fontsize=9.2, color=SECONDARY)
    fig.text(0.075, 0.075,
             "Forecast coverage and coefficient coverage are different. Repeated prior and pooled copies add no independent evidence.",
             fontsize=9.0, color=SECONDARY)
    fig.subplots_adjust(left=0.20, right=0.965, top=0.81, bottom=0.245, wspace=0.28, hspace=0.43)
    return [*save(fig, output / "parameter-uncertainty"), path]


def endpoint_estimates(study):
    rows = study["checkpoints"]
    last_tick = max(study["ticks"])
    _, reference = arena_values(select(rows, condition="private", tick=last_tick), "probe_crps")
    def areas(condition, arenas):
        values = []
        for arena in arenas:
            sequence = [np.mean([finite(r["probe_crps"], "probe_crps") for r in rows
                                 if r["arena_id"] == arena and r["condition"] == condition
                                 and int(r["tick"]) == tick]) for tick in study["ticks"]]
            curve = np.asarray(sequence)
            area = np.sum((curve[1:] + curve[:-1]) * np.diff(study["ticks"]) / 2)
            values.append(float(area) / (study["ticks"][-1] - study["ticks"][0]))
        return np.asarray(values)
    area_reference = areas("private", study["arenas"])
    result = []
    for condition in CONDITIONS:
        endpoint = select(rows, condition=condition, tick=last_tick)
        arenas, values = arena_values(endpoint, "probe_crps")
        mean, low, high = interval(values)
        delta, delta_low, delta_high = interval(values - reference)
        _, receipts = arena_values(endpoint, "unique_observations")
        area_values = areas(condition, arenas)
        area_mean, area_lo, area_hi = interval(area_values)
        area_delta, area_delta_lo, area_delta_hi = interval(area_values - area_reference)
        for metric, estimate in (("probe_crps", (mean, low, high)),
                                 ("crps_aulc_ticks", (area_mean, area_lo, area_hi))):
            recorded = study["summary"]["conditions"][condition][metric]
            if not np.allclose(estimate, [recorded["mean"], *recorded["ci95"]], atol=1e-12, rtol=1e-12):
                raise ValueError(f"Figure arithmetic differs from recorded summary: {condition}, {metric}")
        if condition != "private":
            key = "pooled_minus_private" if condition == "pooled" else "private_minus_prior"
            recorded = study["summary"]["paired_contrasts"][key]["crps_aulc_ticks"]
            authoritative = [recorded["mean"], *recorded["ci95"]]
            if condition == "prior":
                authoritative = [-authoritative[0], -authoritative[2], -authoritative[1]]
            if not np.allclose([area_delta, area_delta_lo, area_delta_hi], authoritative, atol=1e-12, rtol=1e-12):
                raise ValueError(f"Figure contrast differs from recorded summary: {condition}")
        result.append({"condition": condition, "n_arenas": len(arenas), "endpoint_tick": last_tick,
                       "mean_crps": mean, "lo95": low, "hi95": high,
                       "delta_vs_private": delta, "delta_lo95": delta_low, "delta_hi95": delta_high,
                       "mean_unique_observations": float(receipts.mean()),
                       "time_average_crps": area_mean,
                       "time_average_lo95": area_lo, "time_average_hi95": area_hi,
                       "time_average_delta_vs_private": area_delta,
                       "time_average_delta_lo95": area_delta_lo,
                       "time_average_delta_hi95": area_delta_hi})
    return result


def endpoint_figure(study, output):
    estimates = endpoint_estimates(study)
    path = output / "endpoint-contrasts.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(estimates[0]))
        writer.writeheader()
        writer.writerows(estimates)
    fig, ax = plt.subplots(figsize=(13.4, 5.6))
    ax.set_axis_off()
    heading(fig, "Learning with private and pooled evidence",
            f"{study['n_arenas']} independent arenas · each arena contributes one mean across its interacting societies")
    table_rows = []
    for r in estimates:
        delta = "Reference" if r["condition"] == "private" else f"{r['time_average_delta_vs_private']:+.4f}"
        bounds = "—" if r["condition"] == "private" else f"[{r['time_average_delta_lo95']:+.4f}, {r['time_average_delta_hi95']:+.4f}]"
        table_rows.append([CONDITION_LABELS[r["condition"]], f"{r['time_average_crps']:.4f}", delta, bounds,
                           f"{r['mean_crps']:.4f}", f"{r['mean_unique_observations']:.0f}"])
    cols = ["Condition", "Time-average\nCRPS", "Difference\nvs private", "Paired 95%\narena interval",
            "Final probe\nCRPS", "Unique receipts\nper model"]
    table = ax.table(cellText=table_rows, colLabels=cols, colLoc="right", cellLoc="right",
                     colWidths=[0.26, 0.12, 0.12, 0.20, 0.14, 0.16], bbox=[0, 0.14, 1, 0.68])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(RULE)
        cell.set_linewidth(0.55)
        cell.set_facecolor(MUTED if row == 0 else BACKGROUND)
        if row == 0:
            cell.set_text_props(weight="bold", color=INK)
        if col == 0:
            cell.set_text_props(ha="left")
    fig.text(0.075, 0.205,
             "Negative differences favor that condition. Time-average CRPS is the trapezoidal area divided by the observed tick span.",
             fontsize=9.5, color=SECONDARY)
    fig.text(0.075, 0.145,
             "All arms use the same fixed numerical learner. Pooled evidence receives more observations; sharing rules are not learned.",
             fontsize=9.5, color=SECONDARY)
    fig.text(0.075, 0.085,
             "This control estimates parameters in supplied mechanisms. It does not test structure discovery, active experiments or evolved learning.",
             fontsize=9.0, color=SECONDARY)
    fig.subplots_adjust(left=0.075, right=0.96, top=0.77, bottom=0.27)
    return [*save(fig, output / "endpoint-comparison"), path]


CAPTIONS = {
    "learning-curves": "Recorded CRPS on 32 common guaranteed-uncapped same-law probes per arena. Top: completed world ticks. Bottom: the same evaluated checkpoints against unique observations assimilated; dots identify observed points, and gray marks the overlap of observed private/pooled count ranges. No curve is extrapolated beyond its evidence range. The frozen prior assimilates zero observations and is shown only as a horizontal reference in the bottom row. Lower is better. Lines join checkpoints; shading around curves gives pointwise 95% percentile bootstrap intervals resampling independent whole arenas. Prior and pooled references are repeated across society panels for comparison, not counted as independent replicates. Pooled gains per tick can reflect more evidence; neither faster learning nor sample efficiency establishes learned communication. Another 32 limited-headroom probes are recorded but excluded from this prespecified primary endpoint.",
    "parameter-recovery": "Mean absolute error of each coefficient's posterior mean against hidden simulator truth, by society and checkpoint. Base renewal r is in resource units per tick; returns b and g are in resource units per infrastructure unit per tick. Each column has its own scale; columns must not be ranked by vertical height. The same conditions and arena bootstrap as the predictive curves are used. These are numerical parameters of a supplied renewal mechanism, not recovered equation structures. Predictive accuracy does not imply all coefficients are identified.",
    "calibration-width": "Final-checkpoint 90% predictive-interval coverage and mean width on 32 common guaranteed-uncapped same-law probes per arena. Dots are means across independent arenas; horizontal lines are 95% percentile arena bootstrap intervals. The nominal coverage reference is 0.90. Width is in renewal resource units and must be considered alongside coverage. Repeated prior and pooled references are not additional independent samples.",
    "endpoint-comparison": "Each independent arena contributes one mean across its three interacting societies. Time-average CRPS and paired differences from private evidence with 95% arena bootstrap intervals are the primary comparison; final probe CRPS and unique receipts per model provide context. Time-average CRPS is the trapezoidal area divided by the checkpoint time span. Scores use the 32 guaranteed-uncapped common probes per arena. Differences compare fixed estimators with different evidence access, not evolved learning algorithms. All negative and null results are retained.",
    "parameter-uncertainty": "Terminal coverage and mean width of 90% credible intervals for the hidden renewal coefficients, not predictive intervals for future outcomes. Society colors identify separate private estimates; prior and pooled copies are repeated only for comparison. Lines give 95% percentile bootstrap intervals over independent arenas. The parameter-statistics CSV averages societies within each arena before computing means and intervals, retaining {arenas} independent arena units. Observed pooled spillover coverage is {coverage} in this panel. Its interval reflects the limited arena sample; this finding calls for additional parameter-calibration validation and does not identify particle approximation as its cause. Approximately nominal forecast coverage does not establish calibrated coefficient beliefs.",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/world-model-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/world-model-v1")
    args = parser.parse_args(argv)
    study = load_study(args.source)
    captions = dict(CAPTIONS)
    pooled_g = next(r for r in parameter_statistics(study) if r["condition"] == "pooled" and r["parameter"] == "g")
    captions["parameter-uncertainty"] = captions["parameter-uncertainty"].format(
        arenas=study["n_arenas"], coverage=f"{pooled_g['coverage90']:.1%}")
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    files = []
    for renderer in (learning_figure, parameter_figure, calibration_figure, endpoint_figure,
                     parameter_uncertainty_figure):
        files.extend(renderer(study, args.output))
    readme = args.output / "README.md"
    lines = ["# World-model parameter-learning control", "",
             "Recorded evidence in Chromatic Field v1. This is an instrumented passive control with fixed policies and a supplied linear renewal family; no structural discovery or evolutionary learning is implied.", "",
             f"Independent arenas: **{study['n_arenas']}**. Interacting societies per arena: **{len(study['societies'])}**. Independent evolutionary runs: **0**.", "",
             "Society colors are stable; line styles distinguish frozen prior, private observations, and pooled evidence reference. Pooled and prior copies across society panels are not extra replicates.", ""]
    for name, caption in captions.items():
        lines.extend([f"## {name}", "", f"[SVG]({name}.svg) · [PDF]({name}.pdf) · [PNG]({name}.png)", "", caption, ""])
    lines.extend(["[Endpoint contrasts as CSV](endpoint-contrasts.csv) · [Parameter statistics as CSV](parameter-statistics.csv) · [Source/output provenance](manifest.json)", "",
                  "Source evidence: [design](../../evidence/world-model-v1/design.json), [summary](../../evidence/world-model-v1/summary.json), [checkpoints](../../evidence/world-model-v1/checkpoints.csv), and [parameter estimates](../../evidence/world-model-v1/parameters.csv).", "",
                  "```bash", ".venv/bin/python scripts/visualize_world_model_study.py", "```", ""])
    readme.write_text("\n".join(lines))
    source_paths = [args.source / name for name in ("design.json", "summary.json", "checkpoints.csv", "parameters.csv")]
    source_paths.extend([Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"])
    def portable(path):
        return str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path.resolve())
    manifest = {"schema_version": 1, "renderer_version": RENDERER_VERSION,
                "style": STYLE, "study": "world-model-v1", "sources": {portable(p): digest(p) for p in source_paths},
                "captions": captions, "independent_arenas": study["n_arenas"],
                "societies_per_arena": len(study["societies"]), "independent_evolutionary_runs": 0,
                "bootstrap": {"method": "percentile; paired whole-arena draws", "seed": BOOTSTRAP_SEED,
                              "resamples": 2000, "level": 0.95, "curve_intervals": "pointwise"},
                "rendering_runs_training": False, "rendering_runs_evaluation": False,
                "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
                "artifacts": {p.name: digest(p) for p in [*files, readme]}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "independent_arenas": study["n_arenas"],
                      "exports": sum(p.suffix in (".svg", ".pdf", ".png") for p in files),
                      "figure_count": len(CAPTIONS)}, indent=2))


if __name__ == "__main__":
    main()
