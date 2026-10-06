#!/usr/bin/env python3
"""Render the frozen-program factorial diagnostic from recorded rows only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.visualize import (BACKGROUND, INK, RULE, SECONDARY,
                                      digest, save, society_color, theme)
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

CONDITIONS = ("initial", "institutions_only", "members_only", "coevolution")
METRICS = (
    ("welfare", "Consumption welfare", "per member per tick · higher is better", ".6f"),
    ("shortfall_per_member_tick", "Unmet consumption", "resource units per member per tick · lower is better", ".6f"),
    ("outward_harm_per_tick", "Harm to neighbours", "resource units per focal society per tick · lower is better", ".4f"),
    ("utility_per_tick", "Private utility", "per member per tick · higher is better", ".4f"),
)


def load_rows(source):
    source = Path(source)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["study"] != "mechanism-v1" or manifest["source_replicates"] != 1:
        raise ValueError("Renderer requires the single-lineage mechanism-v1 diagnostic")
    manifest_sha = digest(manifest_path)
    cases = {case["id"]: case for case in manifest["cases"]}
    expected = {(case, panel, focal) for case in cases
                for panel in manifest["opponent_panels"] for focal in manifest["focal_societies"]}
    if len(cases) != len(manifest["cases"]) or len(expected) != manifest["n_cases_per_population"]:
        raise ValueError("Manifest case count is inconsistent")
    rows = {}
    for condition in CONDITIONS:
        data = json.loads((source / f"{condition}.json").read_text())
        if data["manifest_sha256"] != manifest_sha or data["label"] != condition:
            raise ValueError(f"Manifest or condition mismatch for {condition}")
        indexed = {}
        for row in data["rows"]:
            key = (row["case"]["id"], row["opponents"], row["focal"])
            if key in indexed:
                raise ValueError(f"Duplicate case in {condition}: {key}")
            indexed[key] = row
        if indexed.keys() != expected:
            raise ValueError(f"Incomplete or unexpected case bank for {condition}")
        rows[condition] = indexed
    reference = rows["initial"]
    for condition, indexed in rows.items():
        if indexed.keys() != reference.keys():
            raise ValueError(f"Unpaired case bank for {condition}")
        for key, row in indexed.items():
            if row["case"] != cases[key[0]] or row["case"] != reference[key]["case"]:
                raise ValueError(f"Changed scenario for {condition}: {key}")
            for metric, *_ in METRICS:
                if not np.isfinite(row["drought"][metric]):
                    raise ValueError(f"Nonfinite outcome for {condition}: {key}")
    return rows


def outcome_figure(rows, output):
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 10.3))
    fig.text(.09, .967, "What changes when we swap members and institutions?",
             fontsize=19, weight="bold", va="top")
    fig.text(.09, .925, "Frozen-program diagnostic · four matched conditions · drought outcomes",
             color=SECONDARY, fontsize=11)
    cmap = LinearSegmentedColormap.from_list("chromatic_magnitude", [BACKGROUND, "#CAC9F2"])
    for ax, (metric, heading, units, fmt) in zip(axes.flat, METRICS):
        means = [statistics.mean(r["drought"][metric] for r in rows[c].values()) for c in CONDITIONS]
        values = np.asarray(means).reshape(2, 2)
        ax.imshow(values, cmap=cmap, aspect="auto", vmin=min(means), vmax=max(means) or 1)
        ax.set_xticks([0, 1], ["Original\ninstitutions", "Evolved\ninstitutions"])
        ax.set_yticks([0, 1], ["Original\nmembers", "Evolved\nmembers"])
        ax.tick_params(length=0, pad=12)
        ax.set_title(heading, loc="left", pad=33)
        ax.text(0, 1.065, units, transform=ax.transAxes, fontsize=8.6, color=SECONDARY)
        for (i, j), v in np.ndenumerate(values):
            ax.text(j, i, format(v, fmt), ha="center", va="center", fontsize=20, color=INK)
        for pos in (-.5, .5, 1.5):
            ax.axhline(pos, color=BACKGROUND, linewidth=4)
            ax.axvline(pos, color=BACKGROUND, linewidth=4)
        for spine in ax.spines.values():
            spine.set_visible(False)
    n_cases = len(rows["initial"])
    n_env = len({k[0] for k in rows["initial"]})
    fig.text(.09, .092, f"Each cell averages {n_cases} focal cases: {n_env} environments × 3 opponent panels × 3 society identities.",
             fontsize=10, color=SECONDARY)
    fig.text(.09, .066, "Welfare = 0.85 − 1.5 × unmet consumption/member/tick. These two panels encode the same outcome.",
             fontsize=9, color=SECONDARY)
    fig.text(.09, .041, "One evolved lineage; post hoc diagnostic, not an independent search replication. Darker shading means a larger value within each panel.",
             fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.13, right=.97, top=.82, bottom=.18, wspace=.42, hspace=.62)
    return save(fig, output / "factorial-outcomes")


def effects_figure(rows, output, *, harm=False):
    metric = "outward_harm_per_tick" if harm else "welfare"
    stem = "institution-harm-effects" if harm else "institution-effects"
    heading = "When does the institution enable harm to neighbours?" if harm else "Does the institution help the same members?"
    units = "outward-harm" if harm else "consumption-welfare"
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 6.9), sharey=True)
    fig.text(.075, .96, heading, fontsize=19, weight="bold", va="top")
    fig.text(.075, .905, f"Paired {units} effects · each dot is one environment averaged over opponent panels", fontsize=10.5, color=SECONDARY)
    labels = ("Institution effect\noriginal members", "Institution effect\nevolved members", "Compatibility\ninteraction")
    all_effects = []
    for sid, ax in enumerate(axes):
        keys = [k for k in rows["initial"] if k[2] == sid]
        environment_ids = sorted({k[0] for k in keys})
        grouped = []
        for env in environment_ids:
            means = {c: statistics.mean(rows[c][k]["drought"][metric] for k in keys if k[0] == env)
                     for c in CONDITIONS}
            original = means["institutions_only"] - means["initial"]
            evolved = means["coevolution"] - means["members_only"]
            grouped.append((original, evolved, evolved - original))
        for index in range(3):
            values = [g[index] for g in grouped]
            all_effects.extend(values)
            # Deterministic vertical separation exposes overlapping environment results.
            ys = index + np.linspace(-.13, .13, len(values))
            ax.scatter(values, ys, s=24, facecolor=BACKGROUND, edgecolor=society_color(sid), alpha=.65, zorder=3)
            mean = statistics.mean(values)
            ax.scatter(mean, index, s=100, marker="D", color=society_color(sid), zorder=4)
            ax.annotate(f"{mean:+.6f}", (mean, index), xytext=(0, -29), textcoords="offset points",
                        fontsize=9, ha="center", color=INK)
        ax.axvline(0, color=RULE, linewidth=1)
        ax.set_yticks(range(3), labels)
        ax.set_ylim(2.65, -.6)
        ax.set_title(f"Society {sid}", loc="left", color=society_color(sid))
        ax.set_xlabel("Change in harm / tick" if harm else "Change in welfare", labelpad=13)
        ax.tick_params(axis="y", length=0, pad=10)
        ax.ticklabel_format(axis="x", style="plain", useOffset=False)
        ax.grid(axis="x", alpha=.5)
    extent = max(max(abs(v) for v in all_effects) * 1.3, .001)
    for ax in axes:
        ax.set_xlim(-extent, extent)
        ax.set_xticks([-extent * .75, 0, extent * .75])
        ax.set_xticklabels([f"{-extent * .75:.3f}", "0", f"{extent * .75:.3f}"])
    fig.text(.075, .09, "Diamond = paired mean. Interaction = institution effect with evolved members − effect with original members.", fontsize=10, color=SECONDARY)
    fig.text(.075, .058, "These are conditional program-swap effects; environment dots are not independent evolutionary runs or confidence intervals.", fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.19, right=.97, top=.80, bottom=.22, wspace=.28)
    return save(fig, output / stem)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/mechanism-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/mechanism-v1")
    args = parser.parse_args()
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.source)
    outputs = outcome_figure(rows, args.output) + effects_figure(rows, args.output) + effects_figure(rows, args.output, harm=True)
    source_paths = [args.source / "manifest.json"] + [args.source / f"{c}.json" for c in CONDITIONS] + [Path(__file__), ROOT / "swarm_societies/visualize.py"]
    manifest = {
        "study": "mechanism-v1", "style": "Chromatic Field v1", "rendering_runs_simulation": False,
        "sources": [{"path": str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p.resolve()),
                     "sha256": digest(p)} for p in source_paths],
        "outputs": [{"path": p.name, "sha256": digest(p)} for p in outputs],
        "versions": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "captions": {
            "factorial-outcomes": "Recorded drought means on paired focal cases. Each panel has its own magnitude scale; darker is higher, not universally better. Welfare equals 0.85 minus 1.5 times unmet consumption per member tick; these are redundant endpoints.",
            "institution-effects": "Institution swaps with original/evolved members and their difference, by focal society. Diamonds are means over environments and opponent panels. Dots describe environment variation conditional on one evolved lineage, not search replication uncertainty.",
            "institution-harm-effects": "The same paired institutional contrasts for outward raid losses imposed on other societies, per tick. Positive effects mean more harm; they do not directly imply lower total welfare for outsiders. Scenario dots are conditional on a single evolved lineage.",
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Rendered {len(outputs)} exports in {args.output}")


if __name__ == "__main__":
    main()
