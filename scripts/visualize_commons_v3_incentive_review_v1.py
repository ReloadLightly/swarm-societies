#!/usr/bin/env python3
"""Plot the completed incentive summary only; never execute or modify a bank."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.visualize import (BACKGROUND, COLORS, INK, RULE, SECONDARY,
                                      digest, save, theme)
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

CONTROLS = ("fixed_floor", "selected")
LABELS = {"fixed_floor": "Fixed floor", "selected": "Selected"}
WEIGHTS = ("0.0", "0.05", "0.2")
CAPTION = (
    "Reference rate 0.24, need 1.2, capacity 80, 256 ticks. Each point changes "
    "only the focal policy at a fixed assignment of 0, 6, 12, 18 or 23 aggressive "
    "peers. Means and ordinary descriptive 95% seed-level Student-t intervals "
    "use 16 matched seeds, 65001–65016. All gains are aggressive minus restrained, "
    "divided by need; weight 0 is consumption only. Straight segments guide the "
    "eye between observed counts, without interpolating a tipping point. "
    "Peer prevalence is k/23; total aggressive prevalence is k/24 or (k+1)/24. "
    "These intervals are not the simultaneous qualification intervals. "
    "Conditions use explicit panel labels; no societies or institutions are present."
)
DECOMPOSITION_CAPTION = (
    "Reference zero-aggressive-peer substitution, 16 paired seeds. Bars separate "
    "mean consumption and terminal-inventory contributions to utility at the "
    "unchanged weight 0.05, divided by need. Black diamonds show their sum with "
    "ordinary descriptive 95% seed-level Student-t intervals. Capacity 8 is the "
    "frozen sensitivity. Positive inventory and negative consumption can cancel; "
    "these are not new qualification tests."
)


def path_label(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def reference_cell(summary, panel):
    return next(c for c in summary["cells"]
                if c["panel"] == panel and c["renewal_rate"] == .24 and c["need"] == 1.2)


def peer_curves(summary, output):
    cell = reference_cell(summary, "grid")
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 8.4), sharex=True, sharey=True)
    for row, control in enumerate(CONTROLS):
        pairs = cell["controls"][control]["paired_focal"]
        assert [p["peer_count"] for p in pairs] == [0, 6, 12, 18, 23]
        for col, weight in enumerate(WEIGHTS):
            ax = axes[row, col]
            x = np.array([p["peer_count"] for p in pairs])
            intervals = [p["differences"]["utility_" + weight] for p in pairs]
            if any(v["interval_kind"] != "descriptive" or v["n"] != 16 for v in intervals):
                raise ValueError("expected complete descriptive peer intervals")
            y = np.array([v["mean"] / cell["need"] for v in intervals])
            low = np.array([v["lower"] / cell["need"] for v in intervals])
            high = np.array([v["upper"] / cell["need"] for v in intervals])
            ax.axhline(0, color=SECONDARY, linewidth=.8, linestyle="--")
            ax.errorbar(x, y, yerr=[y - low, high - y], color=INK,
                        marker="o" if control == "fixed_floor" else "s",
                        markerfacecolor=BACKGROUND, markersize=5,
                        linewidth=1., capsize=3, elinewidth=1., zorder=3)
            ax.set_title(LABELS[control] + " · weight " + weight,
                         loc="left", fontsize=11)
            ax.set_xticks([0, 6, 12, 18, 23])
            ax.set_xlim(-1, 24)
            ax.set_ylim(-.36, .37)
            ax.set_yticks([-.3, -.15, 0, .15, .3])
            ax.grid(axis="y", alpha=.55)
            if row == 1:
                ax.set_xlabel("Aggressive peers k (of 23)")
            if col == 0:
                ax.set_ylabel("Focal gain / need")
    fig.text(.08, .965, "Private incentive depends on peer prevalence",
             fontsize=17, weight="bold", va="top")
    fig.text(.08, .92, "Reference · 16 paired seeds · descriptive 95% intervals · identical scales",
             fontsize=10, color=SECONDARY, va="top")
    fig.text(.08, .04,
             "Weight 0 = consumption only. Segments join observed counts; they do not locate a tipping point.\n"
             "Overall frozen qualification: FAIL. Primary region: UNRESOLVED. No institution or evolutionary claim.",
             fontsize=9, color=SECONDARY, va="bottom")
    fig.subplots_adjust(left=.08, right=.98, top=.83, bottom=.15,
                        hspace=.42, wspace=.18)
    return save(fig, output / "reference-peer-curves")


def storage_decomposition(summary, output):
    fig, axes = plt.subplots(1, 2, figsize=(12., 5.5), sharey=True)
    for ax, control in zip(axes, CONTROLS):
        for y, panel in enumerate(("grid", "small_inventory")):
            cell = reference_cell(summary, panel)
            diff = cell["controls"][control]["paired_focal"][0]["differences"]
            consumption = diff["consumption_per_tick"]["mean"] / cell["need"]
            wealth = diff["terminal_wealth_contribution_0.05"]["mean"] / cell["need"]
            total = diff["utility_0.05"]
            # Separate adjacent bars preserve the signed component amounts.
            ax.barh(y - .12, consumption, height=.18, color=COLORS[0],
                    label="Consumption" if y == 0 else None)
            ax.barh(y + .12, wealth, height=.18, color=COLORS[2],
                    label="Weighted terminal inventory" if y == 0 else None)
            ax.errorbar(total["mean"] / cell["need"], y,
                        xerr=[[(total["mean"] - total["lower"]) / cell["need"]],
                              [(total["upper"] - total["mean"]) / cell["need"]]],
                        marker="D", color=INK, markersize=4, capsize=4,
                        linewidth=1.1, linestyle="", zorder=4,
                        label="Total utility ± descriptive 95% CI" if y == 0 else None)
        ax.set_title(LABELS[control], loc="left")
        ax.axvline(0, color=SECONDARY, linestyle="--", linewidth=.8)
        ax.set_yticks([0, 1], ["Capacity 80", "Capacity 8"])
        ax.set_ylim(1.5, -.5)
        ax.set_xlim(-.029, .031)
        ax.grid(axis="x", alpha=.5)
        ax.set_xlabel("Contribution to focal utility gain / need")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, .045),
               ncol=2, fontsize=9)
    fig.text(.075, .96, "Storage changes the endpoint-inventory incentive",
             fontsize=17, weight="bold", va="top")
    fig.text(.075, .9, "Reference · zero aggressive peers · unchanged weight 0.05 · 16 paired seeds",
             fontsize=10, color=SECONDARY, va="top")
    fig.subplots_adjust(left=.09, right=.97, top=.77, bottom=.28, wspace=.2)
    return save(fig, output / "storage-decomposition")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path,
                        default=ROOT / "evidence/commons-v3-incentive-qualification-v1/summary.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "figures/commons-v3-incentive-review-v1")
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text())
    if (summary["phase"] != "incentive" or summary["episodes"] != 3360
            or summary["independent_environment_seeds"] != list(range(65001, 65017))):
        raise ValueError("expected the completed frozen incentive bank")
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    figures = peer_curves(summary, args.output) + storage_decomposition(summary, args.output)
    gallery = args.output / "README.md"
    gallery.write_text(
        "# Commons v3 incentive review figures\n\n"
        "Recorded incentive evidence only, in Chromatic Field v1. No ecology figure layer, "
        "new simulation or changed qualification verdict.\n\n"
        "![Reference peer curves](reference-peer-curves.png)\n\n" + CAPTION + "\n\n"
        "[SVG](reference-peer-curves.svg) · [PDF](reference-peer-curves.pdf)\n\n"
        "![Storage decomposition](storage-decomposition.png)\n\n" + DECOMPOSITION_CAPTION + "\n\n"
        "[SVG](storage-decomposition.svg) · [PDF](storage-decomposition.pdf)\n\n"
        "Regenerate with `.venv/bin/python scripts/visualize_commons_v3_incentive_review_v1.py`. "
        "The [manifest](manifest.json) binds source, renderer and exports.\n")
    sources = [args.summary, Path(__file__), ROOT / "swarm_societies/visualize.py",
               ROOT / "docs/visual-reference.md"]
    manifest = {
        "version": "commons-v3-incentive-review-figures-v1",
        "style": "Chromatic Field v1", "simulation_episodes": 0,
        "semantic_replay": False, "ecology_artifacts_read": False,
        "python": platform.python_version(), "matplotlib": matplotlib.__version__,
        "numpy": np.__version__,
        "sources": {path_label(p): digest(p) for p in sources},
        "outputs": {path_label(p): digest(p) for p in [*figures, gallery]},
        "captions": {"reference-peer-curves": CAPTION,
                     "storage-decomposition": DECOMPOSITION_CAPTION},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"figures": 2, "exports": len(figures), "output": path_label(args.output)}))


if __name__ == "__main__":
    main()
