#!/usr/bin/env python3
"""Render recorded bounded-sharing experiments in Chromatic Field v1.

All summaries treat complete arenas as independent units. This renderer reads
archived observations of learning; it never trains a model or runs a world.
"""
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
from matplotlib.ticker import MaxNLocator
import numpy as np

RENDERER_VERSION = "world-model-sharing-v1-figures-v1"
CONDITIONS = ("isolated", "redundant", "complementary",
              "delayed_complementary", "union_ceiling")
LABELS = {"isolated": "Isolated", "redundant": "Redundant reports",
          "complementary": "Complementary reports",
          "delayed_complementary": "Delayed complementary",
          "union_ceiling": "Legal-union reference"}
SHORT_LABELS = {"isolated": "Isolated", "redundant": "Redundant",
                "complementary": "Complementary",
                "delayed_complementary": "Delayed", "union_ceiling": "Union reference"}
STYLES = {"isolated": ("-", "o"), "redundant": ("--", "s"),
          "complementary": ((0, (5, 1.3)), "^"),
          "delayed_complementary": (":", "D"),
          "union_ceiling": ("-.", "v")}
PARAMETERS = {"r": "Base renewal", "b": "Own infrastructure return",
              "g": "External infrastructure spillover"}
BOOTSTRAP_SEED = 9301
BOOTSTRAP_DRAWS = 2000


def read_csv(path):
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Empty recorded table: {path}")
    return rows


def finite(value, label):
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"Non-finite recorded {label}: {value}")
    return number


def select(rows, **criteria):
    return [row for row in rows if all(str(row[key]) == str(value)
                                      for key, value in criteria.items())]


def bootstrap(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError("Bootstrap requires finite independent arena values")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, len(values), size=(BOOTSTRAP_DRAWS, len(values)))
    low, high = np.quantile(values[indices].mean(axis=1), [.025, .975])
    return {"mean": float(values.mean()), "ci95": [float(low), float(high)],
            "n_arenas": len(values)}


def arena_values(rows, key, arenas):
    values = []
    for arena in arenas:
        subset = select(rows, arena_id=arena)
        if not subset:
            raise ValueError(f"Missing arena {arena} in {key} summary")
        # Every declared society contributes equally; members are nested units.
        societies = sorted({int(row["society"]) for row in subset})
        values.append(np.mean([np.mean([finite(row[key], key) for row in subset
                                       if int(row["society"]) == society])
                               for society in societies]))
    return np.asarray(values)


def curve(rows, key, axis, study):
    points = sorted({int(row[axis]) for row in rows})
    matrix = np.asarray([arena_values(select(rows, **{axis: point}), key,
                                     study["arenas"]) for point in points]).T
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, len(matrix), size=(BOOTSTRAP_DRAWS, len(matrix)))
    low, high = np.quantile(matrix[indices].mean(axis=1), [.025, .975], axis=0)
    return np.asarray(points), matrix.mean(axis=0), low, high


def heading(fig, title, subtitle):
    fig.text(.065, .97, title, fontsize=19, weight="bold", va="top")
    fig.text(.065, .915, subtitle, fontsize=10.2, color=SECONDARY, va="top")


def format_axes(ax, *, axis="y"):
    ax.grid(axis=axis, alpha=.55)
    ax.set_axisbelow(True)


def condition_legend(fig, *, bottom=.025):
    handles = [Line2D([0], [0], color=SECONDARY, linestyle=STYLES[c][0],
                      marker=STYLES[c][1], markerfacecolor=BACKGROUND,
                      linewidth=1.5, markersize=4.4, label=LABELS[c])
               for c in CONDITIONS]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, bottom),
               ncol=3, fontsize=9.1, handlelength=3.1, columnspacing=2.0)


def society_legend(fig, societies, *, bottom=.025):
    handles = [Line2D([0], [0], color=society_color(s), marker="o", linestyle="",
                      label=f"Society {s}") for s in societies]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, bottom),
               ncol=len(societies), fontsize=9.5)


def draw_curve(ax, rows, axis, society, condition, study):
    x, mean, low, high = curve(rows, "probe_crps", axis, study)
    ax.plot(x, mean, color=society_color(society), linestyle=STYLES[condition][0],
            marker=STYLES[condition][1], markerfacecolor=BACKGROUND,
            markeredgewidth=.8, markersize=3.8,
            linewidth=1.7 if condition == "complementary" else 1.25)
    ax.fill_between(x, low, high, color=society_color(society), alpha=.035,
                    linewidth=0)
    ax._sharing_maximum = max(getattr(ax, "_sharing_maximum", 0.), float(high.max()))
    format_axes(ax)


def write_table(output, name, rows):
    if not rows:
        raise ValueError(f"No rows for {name}")
    path = output / name
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def member_figure(study, output):
    fig, axes = plt.subplots(2, len(study["societies"]), figsize=(13.8, 9.1),
                             sharey=True, squeeze=False)
    heading(fig, "When does truthful sharing improve members' predictions?",
            "Private beliefs · fixed report rules · common held-out, guaranteed-uncapped probes")
    for column, society in enumerate(study["societies"]):
        for row, (table, axis, label) in enumerate((
                ("checkpoints", "tick", "Completed world ticks"),
                ("evidence_checkpoints", "unique_observations", "Unique events admitted per member"))):
            ax = axes[row, column]
            for condition in CONDITIONS:
                rows = select(study[table], role="member", society=society,
                              condition=condition)
                draw_curve(ax, rows, axis, society, condition, study)
            points = sorted({int(r[axis]) for r in study[table]})
            ax.set_xlim(0, max(points))
            ax.set_ylim(bottom=0)
            ax.set_xlabel(label, fontsize=10)
            ax.set_xticks([0, max(points)//4, max(points)//2, max(points)])
            if row == 0:
                ax.set_title(f"Society {society}", color=society_color(society), loc="left")
        axes[0, 0].set_ylabel("Member mean probe CRPS\nBy elapsed time")
        axes[1, 0].set_ylabel("Member mean probe CRPS\nAt exact evidence checkpoints")
    axes[0, 0].set_ylim(0, max(ax._sharing_maximum for ax in axes.flat)*1.075)
    fig.text(.065, .155,
             f"{study['n_arenas']} independent arenas; four members averaged within each society. Shading: pointwise 95% arena intervals.",
             fontsize=9.2, color=SECONDARY)
    fig.text(.065, .118,
             "Isolated and redundant states coincide. Equal evidence counts can contain different events; lower CRPS is better.",
             fontsize=9.1, color=SECONDARY)
    condition_legend(fig)
    fig.subplots_adjust(left=.08, right=.97, top=.815, bottom=.245, wspace=.17, hspace=.40)
    return save(fig, output / "member-learning")


def institutional_figure(study, output):
    fig, axes = plt.subplots(1, len(study["societies"]), figsize=(13.8, 5.7),
                             sharey=True, squeeze=False)
    heading(fig, "Institutional knowledge is a separate outcome",
            "Institutions learn from reports; the legal-union reference supplies events directly")
    for column, society in enumerate(study["societies"]):
        ax = axes[0, column]
        for condition in CONDITIONS:
            draw_curve(ax, select(study["checkpoints"], role="institution",
                                 society=society, condition=condition),
                       "tick", society, condition, study)
        ax.set_title(f"Society {society}", color=society_color(society), loc="left")
        ax.set_xlabel("Completed world ticks")
        ax.set_xlim(0, max(study["ticks"]))
        ax.set_ylim(bottom=0)
        horizon = max(study["ticks"])
        ax.set_xticks([0, horizon//4, horizon//2, horizon])
    axes[0, 0].set_ylabel("Institution probe CRPS")
    axes[0, 0].set_ylim(0, max(ax._sharing_maximum for ax in axes.flat)*1.075)
    fig.text(.065, .18,
             "Home reports repeat members' evidence but train the institution. Complementary reports supply two patch histories.",
             fontsize=9.3, color=SECONDARY)
    fig.text(.065, .135,
             "No-sharing institutions retain the prior. The unrestricted union is an information reference, with no matched channel cost.",
             fontsize=9.0, color=SECONDARY)
    condition_legend(fig)
    fig.subplots_adjust(left=.08, right=.97, top=.755, bottom=.31, wspace=.17)
    return save(fig, output / "institutional-learning")


def interval_mark(ax, estimate, y, *, color=INK, marker="o", size=4.5):
    mean, (low, high) = estimate["mean"], estimate["ci95"]
    ax.plot([low, high], [y, y], color=color, linewidth=1.3)
    ax.plot([mean], [y], color=color, marker=marker, markersize=size,
            markerfacecolor=BACKGROUND if marker == "D" else color, linestyle="")


def endpoint_values(study, condition, role="member", society=None):
    cache = study.setdefault("_endpoint_values", {})
    cache_key = (condition, role, society)
    if cache_key in cache:
        return cache[cache_key]
    criteria = {"condition": condition, "role": role}
    if society is not None:
        criteria["society"] = society
    rows = select(study["checkpoints"], **criteria)
    ticks = np.asarray(study["ticks"])
    matrix = np.asarray([arena_values(select(rows, tick=tick), "probe_crps",
                                     study["arenas"]) for tick in ticks])
    result = {"time_average_crps": np.trapezoid(matrix, ticks, axis=0) / ticks[-1],
              "terminal_crps": matrix[-1]}
    if role == "member":
        points = np.asarray(study["evidence_points"])
        evidence = select(study["evidence_checkpoints"], **criteria)
        matrix = np.asarray([arena_values(select(evidence, unique_observations=point),
                                         "probe_crps", study["arenas"])
                             for point in points])
        result["evidence_average_crps"] = np.trapezoid(matrix, points, axis=0) / points[-1]
    terminal = select(rows, tick=ticks[-1])
    for key in ("coverage_90", "interval_width_90", "unique_observations",
                "parameter_nrmse", "failed_updates"):
        result[key] = arena_values(terminal, key, study["arenas"])
    cache[cache_key] = result
    return result


CONTRASTS = (("complementary", "redundant", "Complementary − redundant\nPrimary content contrast"),
             ("complementary", "isolated", "Complementary − isolated\nSharing versus no sharing"),
             ("delayed_complementary", "complementary", "Delayed − complementary\nLatency contrast"))


def contrast_figure(study, output):
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 7.0), sharey=True)
    heading(fig, "Separate report content from delivery delay",
            "Paired changes in member prediction error · identical worlds and learner seeds within each arena")
    metrics = (("time_average_crps", "Time-average CRPS\nPrimary learning endpoint"),
               ("evidence_average_crps", f"Evidence-average CRPS\nExact common range: 0–{max(study['evidence_points'])} events"),
               ("terminal_crps", f"Terminal CRPS\nAfter {max(study['ticks'])} completed ticks"))
    offsets = {None: -.21, 0: -.07, 1: .07, 2: .21}
    for column, (metric, title) in enumerate(metrics):
        ax = axes[column]
        ax.axvline(0, color=SECONDARY, linewidth=.9, linestyle="--")
        for row, (left, right, _) in enumerate(CONTRASTS):
            y = len(CONTRASTS) - 1 - row
            if row == 0:
                ax.axhspan(y-.38, y+.38, facecolor=MUTED, zorder=0)
            for society in (None, *study["societies"]):
                l = endpoint_values(study, left, society=society)[metric]
                r = endpoint_values(study, right, society=society)[metric]
                interval_mark(ax, bootstrap(l-r), y+offsets[society],
                              color=INK if society is None else society_color(society),
                              marker="D" if society is None else "o", size=4.8)
        ax.set_title(title, fontsize=11, loc="left")
        ax.set_xlabel("CRPS difference · resource units", fontsize=10)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.set_yticks(range(len(CONTRASTS)))
        ax.set_ylim(-.6, len(CONTRASTS)-.4)
        format_axes(ax, axis="x")
    axes[0].set_yticklabels([item[2] for item in reversed(CONTRASTS)], fontsize=9.6)
    handles = [Line2D([0], [0], color=INK, marker="D", markerfacecolor=BACKGROUND,
                      linestyle="", label="Mean across all members")]
    handles.extend(Line2D([0], [0], color=society_color(s), marker="o", linestyle="",
                          label=f"Society {s}") for s in study["societies"])
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.57, .035), ncol=4, fontsize=9)
    fig.text(.065, .175,
             f"Points: means over {study['n_arenas']} independent arenas. Lines: paired 95% arena bootstrap intervals. Negative is better for the first arm.",
             fontsize=9.2, color=SECONDARY)
    fig.text(.065, .13,
             "Complementary versus redundant matches sent bytes. Delay matches channel capacity, with fewer broadcasts before the horizon.",
             fontsize=9.0, color=SECONDARY)
    fig.subplots_adjust(left=.245, right=.975, top=.765, bottom=.27, wspace=.26)
    return save(fig, output / "paired-effects")


def parameter_figure(study, output):
    fig, axes = plt.subplots(2, 3, figsize=(14.0, 8.8), squeeze=False, sharey=True)
    heading(fig, "Member uncertainty after the same interaction horizon",
            f"90% marginal credible intervals · supplied renewal-law family · {max(study['ticks'])} completed ticks")
    terminal = select(study["parameters"], role="member", tick=max(study["ticks"]))
    for column, parameter in enumerate(PARAMETERS):
        for index, condition in enumerate(CONDITIONS):
            y = len(CONDITIONS) - 1 - index
            for society in study["societies"]:
                rows = select(terminal, condition=condition, society=society, parameter=parameter)
                for row, key in enumerate(("covered90", "width90")):
                    estimate = bootstrap(arena_values(rows, key, study["arenas"]))
                    interval_mark(axes[row, column], estimate, y+(society-1)*.16,
                                  color=society_color(society), size=4.4)
        for row in range(2):
            ax = axes[row, column]
            ax.set_yticks(range(len(CONDITIONS)))
            ax.set_ylim(-.5, len(CONDITIONS)-.5)
            ax.set_xlim(left=0)
            format_axes(ax, axis="x")
        axes[0, column].axvline(.9, color=SECONDARY, linestyle="--", linewidth=.9)
        axes[0, column].set_xlim(0, 1.035)
        axes[0, column].set_title(f"{parameter} / {PARAMETERS[parameter]}", loc="left", fontsize=10.8)
        axes[0, column].set_xlabel("Fraction of true coefficients covered", fontsize=9.6)
        axes[1, column].set_xlabel(f"Mean interval width · {parameter} units", fontsize=9.6)
    for row in range(2):
        axes[row, 0].set_yticklabels([SHORT_LABELS[c] for c in reversed(CONDITIONS)], fontsize=9.5)
    fig.text(.065, .145,
             "Each arena contributes its mean over four members per society. Lines: 95% whole-arena bootstrap intervals; 90% nominal line dashed.",
             fontsize=9.0, color=SECONDARY)
    fig.text(.065, .105,
             "These conditional ecological beliefs retain the calibration audit's limitations. Narrow intervals alone do not establish useful knowledge.",
             fontsize=9.0, color=SECONDARY)
    society_legend(fig, study["societies"], bottom=.03)
    fig.subplots_adjust(left=.17, right=.975, top=.805, bottom=.23, wspace=.24, hspace=.40)
    return save(fig, output / "member-uncertainty")


def communication_figure(study, output):
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 7.0), sharey=True)
    heading(fig, "Charged communication is not the same as new evidence",
            "Finite-horizon accounting per society · 1,024-byte frames · all recipient copies charged")
    for index, condition in enumerate(CONDITIONS):
        y = len(CONDITIONS)-1-index
        rows = select(study["transport"], condition=condition)
        delivered = float(arena_values(rows, "delivered_bytes", study["arenas"]).mean()) / 1024
        pending = float(arena_values(rows, "pending_bytes", study["arenas"]).mean()) / 1024
        axes[0].barh(y, delivered, height=.48, color=SECONDARY)
        axes[0].barh(y, pending, left=delivered, height=.48,
                     color=MUTED, edgecolor=SECONDARY, hatch="///", linewidth=.6)
        label = f"{delivered+pending:,.0f}" if delivered+pending else "No channel"
        axes[0].text(delivered+pending+25, y, label, va="center", fontsize=9, color=SECONDARY)
        for society in study["societies"]:
            subset = select(rows, society=society)
            for metric, marker, dy in (("novel_member_updates", "o", -.04),
                                       ("duplicate_member_reports", "x", .04)):
                values = arena_values(subset, metric, study["arenas"]) / study["members_per_society"]
                interval_mark(axes[1], bootstrap(values), y+(society-1)*.16+dy,
                              color=society_color(society), marker=marker, size=4.5)
            for role, marker, dy in (("member", "o", -.04), ("institution", "s", .04)):
                values = endpoint_values(study, condition, role, society)["unique_observations"]
                interval_mark(axes[2], bootstrap(values), y+(society-1)*.16+dy,
                              color=society_color(society), marker=marker, size=4.5)
    axes[0].set_title("Actual wire bytes sent\nDelivered plus still in flight", fontsize=11, loc="left")
    axes[0].set_xlabel("KiB sent per society", fontsize=10)
    axes[0].set_xlim(0, max(float(r["sent_bytes"]) for r in study["transport"])/1024*1.24 or 1)
    axes[1].set_title("Delivered member reports\nNew versus already known events", fontsize=11, loc="left")
    axes[1].set_xlabel("Downlink arrivals per member", fontsize=10)
    axes[2].set_title("Total unique events admitted\nMembers versus their institution", fontsize=11, loc="left")
    axes[2].set_xlabel("Unique events per model", fontsize=10)
    for ax in axes:
        ax.set_xlim(left=0)
        ax.set_ylim(-.65, len(CONDITIONS)-.4)
        ax.set_yticks(range(len(CONDITIONS)))
        format_axes(ax, axis="x")
    axes[0].set_yticklabels([SHORT_LABELS[c] for c in reversed(CONDITIONS)], fontsize=10)
    axes[0].legend(handles=[plt.Rectangle((0, 0), 1, 1, facecolor=SECONDARY, label="Delivered"),
                            plt.Rectangle((0, 0), 1, 1, facecolor=MUTED, edgecolor=SECONDARY,
                                          hatch="///", label="Still in flight")],
                   loc="lower left", bbox_to_anchor=(-.02, -.22), ncol=2, fontsize=8.7)
    for ax, labels in ((axes[1], (("o", "New"), ("x", "Duplicate"))),
                       (axes[2], (("o", "Member"), ("s", "Institution")))):
        ax.legend(handles=[Line2D([0], [0], color=INK, marker=m, linestyle="", label=label)
                           for m, label in labels], loc="lower left", bbox_to_anchor=(-.02, -.22),
                  ncol=2, fontsize=8.7)
    fig.text(.065, .155,
             "Redundant and complementary arms match sent bytes. Delayed delivery leaves more frames in flight and fewer downlinks sent.",
             fontsize=9.1, color=SECONDARY)
    fig.text(.065, .112,
             "The union reference receives the legal sensor union directly; its zero charged bytes do not describe a feasible free reporting channel.",
             fontsize=9.0, color=SECONDARY)
    society_legend(fig, study["societies"], bottom=.035)
    fig.subplots_adjust(left=.17, right=.97, top=.76, bottom=.32, wspace=.30)
    return save(fig, output / "communication-accounting")


METRIC_KEYS = {"time_average_crps": "crps_aulc_ticks", "terminal_crps": "probe_crps",
               "evidence_average_crps": "crps_aulc_evidence"}


def assert_estimate(recorded, derived, label):
    if recorded["n_arenas"] != derived["n_arenas"] or not np.allclose(
            [recorded["mean"], *recorded["ci95"]],
            [derived["mean"], *derived["ci95"]], rtol=1e-10, atol=1e-12):
        raise ValueError(f"Figure arithmetic differs from frozen summary: {label}")


def require_grid(rows, keys, expected, label):
    actual = Counter(tuple(str(row[k]) for k in keys) for row in rows)
    if set(actual) != expected or any(count != 1 for count in actual.values()):
        raise ValueError(f"Incomplete or duplicated {label} evidence grid")


def load_study(source):
    design = json.loads((source / "design.json").read_text())
    if digest(source / "design.json") != (source / "design.sha256").read_text().strip():
        raise ValueError("Sharing design checksum mismatch")
    completion = json.loads((source / "completion.json").read_text())
    source_names = ("checkpoints.csv", "parameters.csv", "transport.csv", "costs.csv", "summary.json", "design.json")
    for name in source_names:
        if digest(source / name) != completion["artifacts"][name]:
            raise ValueError(f"Recorded sharing artifact hash mismatch: {name}")
    if tuple(design["conditions"]) != CONDITIONS:
        raise ValueError("Declare visual encodings before changing conditions")
    if design["bootstrap"] != {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED, "level": .95}:
        raise ValueError("Renderer bootstrap differs from frozen design")
    arenas = [case["arena_id"] for case in design["cases"]]
    if len(set(arenas)) != len(arenas):
        raise ValueError("Repeated independent arena identity")
    societies = list(range(design["config"]["n_societies"]))
    members = design["config"]["members_per_society"]
    if societies != [0, 1, 2] or members != 4:
        raise ValueError("Update figure layouts before changing social composition")
    actors = [f"member:{s}:{m}" for s in societies for m in range(members)]
    institutions = [f"institution:{s}" for s in societies]
    points = [(actor, "ticks", str(t)) for actor in actors+institutions for t in design["checkpoints"]]
    points.extend((actor, "evidence", str(n)) for actor in actors for n in design["evidence_checkpoints"])
    expected = {(a, c, *point) for a in arenas for c in CONDITIONS for point in points}
    all_checkpoints = read_csv(source / "checkpoints.csv")
    all_parameters = read_csv(source / "parameters.csv")
    transport, costs = (read_csv(source / name) for name in ("transport.csv", "costs.csv"))
    identity = ("arena_id", "condition", "actor", "axis", "coordinate")
    require_grid(all_checkpoints, identity, expected, "checkpoint")
    require_grid(all_parameters, (*identity, "parameter"),
                 {(*point, p) for point in expected for p in PARAMETERS}, "parameter")
    require_grid(transport, ("arena_id", "condition", "society"),
                 {(a, c, str(s)) for a in arenas for c in CONDITIONS for s in societies}, "transport")
    require_grid(costs, ("arena_id", "condition"), {(a, c) for a in arenas for c in CONDITIONS}, "cost")
    for row in all_checkpoints + all_parameters:
        parts = row["actor"].split(":")
        if row["actor_type"] != parts[0] or int(row["society"]) != int(parts[1]):
            raise ValueError("Actor identity disagrees with recorded ownership")
        if int(row["member"]) != (int(parts[2]) if parts[0] == "member" else -1):
            raise ValueError("Member identity disagrees with recorded owner")
        row["role"] = row["actor_type"]
        row["tick"] = row["coordinate"] if row["axis"] == "ticks" else row["completed_ticks"]
    for row in all_checkpoints:
        for key in ("probe_crps", "probe_mse", "coverage_90", "interval_width_90",
                    "parameter_nrmse", "unique_observations", "duplicate_events", "failed_updates", "ess"):
            if finite(row[key], key) < 0:
                raise ValueError(f"Negative recorded {key}")
        if float(row["coverage_90"]) > 1:
            raise ValueError("Predictive coverage exceeds one")
        if row["axis"] == "evidence" and int(row["coordinate"]) != int(row["unique_observations"]):
            raise ValueError("Recorded evidence checkpoint is not exact")
    for row in all_parameters:
        low, high, truth, mean = [finite(row[k], k) for k in ("lo90", "hi90", "true_value", "posterior_mean")]
        if high < low or int(row["covered90"]) != int(low <= truth <= high):
            raise ValueError("Invalid recorded coefficient coverage")
        if not np.allclose([float(row["width90"]), float(row["absolute_error"])],
                           [high-low, abs(mean-truth)], rtol=1e-11, atol=1e-12):
            raise ValueError("Invalid recorded coefficient width or error")
    for row in transport:
        for key in row.keys() - {"arena_id", "condition", "society"}:
            if finite(row[key], key) < 0:
                raise ValueError(f"Negative transport metric {key}")
        if int(row["sent_bytes"]) != int(row["sent_frames"]) * design["frame_bytes"]:
            raise ValueError("Wire charge differs from fixed frame size")
        if int(row["sent_bytes"]) != int(row["delivered_bytes"]) + int(row["pending_bytes"]):
            raise ValueError("Delivered and in-flight bytes do not conserve sent bytes")
    study = {"design": design, "summary": json.loads((source / "summary.json").read_text()),
             "checkpoints": select(all_checkpoints, axis="ticks"),
             "evidence_checkpoints": select(all_checkpoints, axis="evidence"),
             "parameters": select(all_parameters, axis="ticks"), "transport": transport,
             "costs": costs, "arenas": arenas, "n_arenas": len(arenas),
             "societies": societies, "members_per_society": members,
             "ticks": design["checkpoints"], "evidence_points": design["evidence_checkpoints"]}
    isolated = {(r["arena_id"], r["actor"], r["axis"], r["coordinate"]): r
                for r in all_checkpoints if r["condition"] == "isolated" and r["role"] == "member"}
    for row in all_checkpoints:
        if row["condition"] == "redundant" and row["role"] == "member":
            control = isolated[row["arena_id"], row["actor"], row["axis"], row["coordinate"]]
            for key in ("probe_crps", "coverage_90", "interval_width_90", "unique_observations"):
                if row[key] != control[key]:
                    raise ValueError("Isolated and redundant member outcomes do not coincide")
    for arena in arenas:
        for society in societies:
            left, right = [select(transport, arena_id=arena, society=society, condition=c)[0]
                           for c in ("redundant", "complementary")]
            if left["sent_bytes"] != right["sent_bytes"]:
                raise ValueError("Report-content contrast does not match charged bytes")
    for row in study["summary"]["conditions"]:
        for key, values in endpoint_values(study, row["condition"], row["actor_type"]).items():
            assert_estimate(row[METRIC_KEYS.get(key, key)], bootstrap(values), f"{row['condition']} / {row['actor_type']} / {key}")
    for row in study["summary"]["paired_contrasts"]:
        left, right = row["contrast"].split("_minus_")
        l = endpoint_values(study, left, row["actor_type"])
        r = endpoint_values(study, right, row["actor_type"])
        for key, source_key in METRIC_KEYS.items():
            if key in l:
                assert_estimate(row[source_key], bootstrap(l[key]-r[key]), row["contrast"]+key)
    for row in study["summary"]["transport"]:
        rows = select(transport, condition=row["condition"])
        for key in row.keys() - {"condition"}:
            values = [sum(float(r[key]) for r in select(rows, arena_id=arena)) for arena in arenas]
            assert_estimate(row[key], bootstrap(values), row["condition"]+key)
    return study


def add_estimate(row, prefix, estimate):
    row[prefix+"_mean"] = estimate["mean"]
    row[prefix+"_lo95"], row[prefix+"_hi95"] = estimate["ci95"]


def export_tables(study, output):
    endpoints, contrasts, parameters, communication, compute = [], [], [], [], []
    for condition in CONDITIONS:
        for role in ("member", "institution"):
            for society in (None, *study["societies"]):
                identity = {"condition": condition, "actor_type": role,
                            "society": "all" if society is None else society,
                            "n_arenas": study["n_arenas"], "unit": "independent_arena"}
                for key, values in endpoint_values(study, condition, role, society).items():
                    row = {**identity, "metric": METRIC_KEYS.get(key, key)}
                    add_estimate(row, "estimate", bootstrap(values))
                    endpoints.append(row)
                for parameter in PARAMETERS:
                    selected = select(study["parameters"], condition=condition, role=role,
                                      parameter=parameter, tick=max(study["ticks"]))
                    if society is not None:
                        selected = select(selected, society=society)
                    row = {**identity, "parameter": parameter}
                    for key in ("covered90", "width90", "absolute_error"):
                        add_estimate(row, key, bootstrap(arena_values(selected, key, study["arenas"])))
                    parameters.append(row)
        for society in (None, *study["societies"]):
            selected = select(study["transport"], condition=condition)
            if society is not None:
                selected = select(selected, society=society)
            row = {"condition": condition, "society": "mean_across_societies" if society is None else society,
                   "n_arenas": study["n_arenas"], "unit": "independent_arena"}
            for key in sorted(selected[0].keys() - {"arena_id", "condition", "society"}):
                add_estimate(row, key, bootstrap(arena_values(selected, key, study["arenas"])))
            ratios = []
            for arena in study["arenas"]:
                values = select(selected, arena_id=arena)
                sent = sum(float(r["sent_bytes"]) for r in values)
                novel = sum(float(r["novel_member_updates"]) for r in values)
                if sent:
                    ratios.append(novel/(sent/1024))
            if ratios:
                add_estimate(row, "novel_member_updates_per_sent_KiB", bootstrap(ratios))
            else:
                row.update({"novel_member_updates_per_sent_KiB_mean": None,
                            "novel_member_updates_per_sent_KiB_lo95": None,
                            "novel_member_updates_per_sent_KiB_hi95": None})
            communication.append(row)
        rows = select(study["costs"], condition=condition)
        row = {"condition": condition, "n_arenas": study["n_arenas"], "unit": "independent_arena"}
        for key in ("runtime_cpu_seconds", "scoring_cpu_seconds"):
            values = [finite(r[key], key) for r in rows]
            estimate = bootstrap(values)
            reference = next(r for r in study["summary"]["compute"] if r["condition"] == condition)
            assert_estimate(reference[key], estimate, condition+key)
            add_estimate(row, key, estimate)
        compute.append(row)
    for source_row in study["summary"]["paired_contrasts"]:
        left, right = source_row["contrast"].split("_minus_")
        role = source_row["actor_type"]
        for society in (None, *study["societies"]):
            l, r = (endpoint_values(study, c, role, society) for c in (left, right))
            for key, metric in METRIC_KEYS.items():
                if key not in l:
                    continue
                row = {"contrast": source_row["contrast"], "actor_type": role,
                       "society": "all" if society is None else society, "metric": metric,
                       "n_arenas": study["n_arenas"], "unit": "independent_arena"}
                add_estimate(row, "difference", bootstrap(l[key]-r[key]))
                contrasts.append(row)
    return [write_table(output, name, rows) for name, rows in (
        ("endpoint-statistics.csv", endpoints), ("paired-contrasts.csv", contrasts),
        ("parameter-statistics.csv", parameters), ("communication-statistics.csv", communication),
        ("compute-statistics.csv", compute))]


CAPTIONS = {
    "member-learning": "Member predictive CRPS on the 32 common guaranteed-uncapped probes per arena, averaged over four private models within each society. Top: recorded completed-tick checkpoints. Bottom: exact states immediately after 0, 8, 16, 32, 64, 128 and 256 unique-event admissions, before any following event is processed. Curves are means over independent arenas; shading gives pointwise 95% whole-arena bootstrap intervals. Isolated and redundant private states coincide, so their lines overlap. Equal evidence counts need not identify equal examples or orders and therefore do not isolate inference efficiency. The legal-union arm is an unrestricted information reference, not a matched-bandwidth institution. Colors identify societies; markers and dashes identify conditions.",
    "institutional-learning": "Recorded institutional predictive CRPS, one separately owned institution model per society and condition. Institutions receive no direct private sensor stream in the ordinary conditions; they learn only from authenticated uplink arrivals. Redundant member reports still train the institutional model once per event, while duplicate envelopes add no likelihood. The isolated institution remains at its prior. Legal-union institutions are supplied all legal events directly as an information reference. Curves and pointwise 95% intervals resample complete independent arenas, not societies or forecasts. These models are distinct from members' personal beliefs; institutional performance alone does not establish member learning.",
    "paired-effects": "Paired arena differences for the prospectively declared report-content contrast (complementary minus redundant), sharing contrast (complementary minus isolated), and delay contrast (delayed minus ordinary complementary). Black diamonds average four members within each society and three societies within each arena. Colored points retain society-specific estimates, each still based on independent arenas. Lines are 95% percentile intervals from 2,000 paired arena bootstrap draws. The primary endpoint is tick-integrated CRPS divided by the 128-tick horizon. Evidence-normalized integration uses the exact common range of 0–256 unique events and remains descriptive because event contents and order differ. The terminal endpoint scores the final physical horizon, without flushing in-flight reports. The report-content contrast matches actual wire bytes; the delay contrast matches channel capacity and origin schedule but may send fewer downlinks before the horizon. Secondary intervals have no familywise multiplicity adjustment.",
    "member-uncertainty": "Terminal member-model coefficient coverage and marginal 90% credible-interval width, shown separately for each society and supplied law coefficient. Each independent arena contributes an average over its four dependent members before bootstrap resampling; model copies are not treated as independent calibration cases. Dots and lines show means and 95% arena bootstrap intervals. The nominal 0.90 line is descriptive for this interior-law ecological task panel; it is not the full-prior, exogenous-feature calibration control. Particle approximation and conditioning on latent-outcome-dependent ecological features retain the earlier audit's limitations. The unrestricted union and truthful sharing conditions need not have identical numerical trajectories, and narrow uncertainty alone does not establish learning quality. Institution statistics are retained separately in the accompanying parameter table.",
    "communication-accounting": "Finite-horizon communication and evidence accounting, averaged over independent arenas. Left: bytes sent per society, split into delivered versus still-in-flight frames; each frame is 1,024 charged bytes, including provenance and padding, and every broadcast recipient copy is charged separately. Middle: delivered downlink arrivals per member, distinguished as novel accepted physical events versus duplicates of known events. Right: total unique-event counts in member and institutional models, including legal local sensor inputs. Colored points retain society identity; circle/square/cross meanings are panel-specific and labeled. Redundant and complementary conditions match actual bytes, sender schedule and delay. The longer-delay condition matches origin schedule and channel capacity but can send fewer downlinks within 128 ticks; pending frames are not flushed. The union reference has no charged communication because its legal sensor union is supplied directly as an unrestricted information reference. Its zero channel charge is not evidence of free achievable information transmission.",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/world-model-sharing-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/world-model-sharing-v1")
    args = parser.parse_args(argv)
    study = load_study(args.source)
    captions = {name: caption.replace("128 ticks", f"{max(study['ticks'])} ticks")
                .replace("128-tick horizon", f"{max(study['ticks'])}-tick horizon")
                .replace("0–256 unique events", f"0–{max(study['evidence_points'])} unique events")
                .replace("0, 8, 16, 32, 64, 128 and 256", ", ".join(map(str, study["evidence_points"])))
                for name, caption in CAPTIONS.items()}
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    files = export_tables(study, args.output)
    for renderer in (member_figure, institutional_figure, contrast_figure,
                     communication_figure, parameter_figure):
        files.extend(renderer(study, args.output))
    readme = args.output / "README.md"
    lines = ["# Private beliefs and bounded truthful sharing", "",
             "Recorded-data Chromatic Field v1 figures. The experiment changes report content and delivery timing while preserving the world, private measurements and numerical learner.", "",
             f"Bank: **{study['design']['bank']}**. Independent arenas: **{study['n_arenas']}**. Societies per arena: **3**. Private members per society: **4**. Independent evolutionary runs and model-generation calls: **0**.", "",
             "Colors identify societies consistently. Condition markers and line styles do not represent different societies. Whole arenas, not members, societies, forecasts, messages or particles, are resampled for uncertainty intervals.", ""]
    for name in ("member-learning", "institutional-learning", "paired-effects", "communication-accounting", "member-uncertainty"):
        lines.extend([f"## {name}", "", f"[SVG]({name}.svg) · [PDF]({name}.pdf) · [PNG]({name}.png)", "", captions[name], ""])
    lines.extend(["## Derived tables and provenance", "",
                  "[Endpoint statistics](endpoint-statistics.csv) · [Paired effects](paired-contrasts.csv) · [Parameter coverage and width](parameter-statistics.csv) · [Communication accounting](communication-statistics.csv) · [CPU cost](compute-statistics.csv) · [Source/output hashes](manifest.json)", "",
                  "Derived tables retain society-level means as well as whole-arena means. Communication-table 'mean_across_societies' rows describe mean per-society cost, not the sum over an arena. Novelty per KiB counts accepted recipient updates, not independent physical events, and is undefined in arms with no channel. Bootstrap intervals use 2,000 whole-arena draws and seed 9301; all reported contrasts are paired. The primary content contrast is complementary minus redundant on member time-average CRPS. Secondary intervals are descriptive and have no familywise multiplicity adjustment.", "",
                  "The renderer checks design and input hashes, ownership/checkpoint grids, recorded interval arithmetic, and learning/contrast/CPU statistics against the frozen study summary. It runs no inference or ecological evaluation. The study's semantic verifier separately reconstructs routing and saved predictions.", "",
                  "```bash", ".venv/bin/python scripts/visualize_world_model_sharing.py", "```", ""])
    readme.write_text("\n".join(lines))
    sources = [args.source / name for name in ("design.json", "design.sha256", "completion.json", "checkpoints.csv", "parameters.csv", "transport.csv", "costs.csv", "summary.json")]
    sources.extend((Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"))
    def portable(path):
        path = path.resolve()
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    manifest = {"schema_version": 1, "renderer_version": RENDERER_VERSION,
                "style": STYLE, "study": "world-model-sharing-v1", "bank": study["design"]["bank"],
                "sources": {portable(path): digest(path) for path in sources},
                "captions": captions, "independent_arenas": study["n_arenas"],
                "societies_per_arena": len(study["societies"]), "members_per_society": study["members_per_society"],
                "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED,
                              "unit": "independent arena", "level": .95, "curve_intervals": "pointwise",
                              "contrasts": "paired arena differences", "secondary_multiplicity_adjustment": False},
                "rendering_runs_training": False, "rendering_runs_evaluation": False,
                "independent_evolutionary_runs": 0, "model_generation_calls": 0,
                "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
                "artifacts": {path.name: digest(path) for path in [*files, readme]}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps({"output": str(args.output), "figure_count": len(CAPTIONS),
                      "independent_arenas": study["n_arenas"], "tables": 5}, indent=2))


if __name__ == "__main__":
    main()
