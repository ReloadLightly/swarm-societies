#!/usr/bin/env python3
"""Render the saved external temptation probe; never execute policies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.visualize import BACKGROUND, INK, RULE, SECONDARY, digest, save, theme
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/commons-v3-temptation-review-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/commons-v3-temptation-review-v1")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("figure output must be new or empty")
    summary = json.loads((source / "summary.json").read_text())
    manifest = json.loads((source / "manifest.json").read_text())
    if digest(source / "summary.json") != manifest["files"]["summary.json"]["sha256"]:
        raise ValueError("saved summary hash differs")
    theme()
    fig, axes = plt.subplots(2, 2, figsize=(11.4, 7.1), sharex=True, sharey=True)
    fig.text(.065, .955, "Storage changes the incentive to abandon restraint", fontsize=17, weight="bold")
    fig.text(.065, .912, "Exact reproduction of the external review probe · fixed-floor controller · focal identity 0", fontsize=10, color=SECONDARY)
    weights, markers = ("0.0", "0.05", "0.2"), ("o", "s", "^")
    plotted = []
    for row, panel in enumerate(summary["panels"]):
        for col, contrast in enumerate(panel["contrasts"]):
            ax = axes[row, col]
            capacity, peers = panel["inventory_capacity"], contrast["aggressive_peers"]
            ax.set_title(f"Storage {capacity} · {peers} aggressive peers", loc="left", fontsize=12)
            ax.axvline(0, color=SECONDARY, linestyle=(0, (3, 3)), linewidth=.8, zorder=1)
            ax.grid(axis="x", zorder=0)
            for index, (weight, marker) in enumerate(zip(weights, markers)):
                data = contrast["weights"][weight]["focal_gain_fraction"]
                y = 2 - index
                ax.plot([data["lower"], data["upper"]], [y, y], color=INK, linewidth=1.35, zorder=3)
                ax.plot(data["mean"], y, marker=marker, markersize=6, markerfacecolor=BACKGROUND,
                        markeredgecolor=INK, linestyle="", zorder=4)
                plotted.append({"capacity": capacity, "aggressive_peers": peers, "weight": weight, **data})
            ax.set_yticks([2, 1, 0], ["Weight 0", "Weight 0.05", "Weight 0.2"])
            ax.set_ylim(-.55, 2.6)
            ax.set_xlim(-.09, .10)
            ax.set_xticks([-.08, -.04, 0, .04, .08])
            ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
            ax.spines["left"].set_visible(False)
            ax.tick_params(axis="y", length=0, labelleft=True)
            ax.tick_params(axis="x", labelbottom=True)
            ax.set_xlabel("Focal gain as a fraction of need")
            if (row, col) == (0, 0):
                note = "89.4% of mean weight-0.05 gain is terminal inventory."
            elif (row, col) == (0, 1):
                note = "Consumption-only gain: +7.06% of need."
            elif (row, col) == (1, 0):
                note = "Mean weight-0.05 gain falls to +0.22% of need."
            else:
                note = "Consumption-only gain: −0.17%; sign unresolved."
            ax.text(0, -.53, note, transform=ax.transAxes, fontsize=9.3, color=SECONDARY)
    fig.text(.065, .055, "Points: matched restrained → aggressive focal changes. Bars: ordinary 95% t intervals across eight seeds (descriptive).", fontsize=9.5, color=SECONDARY)
    fig.text(.065, .026, "256 ticks · seeds 90001–90008 · same scale in every panel · whole-policy substitutions, not equilibrium tests", fontsize=9.5, color=SECONDARY)
    fig.subplots_adjust(left=.115, right=.975, top=.81, bottom=.22, hspace=1.1, wspace=.37)
    outputs = save(fig, output / "temptation-storage")
    caption = ("Focal private gain from switching the frozen fixed-floor controller to its supplied aggressive variant, "
               "divided by need, at storage capacities 80 and 8 and with 0 or 23 aggressive peers. Utility weights 0, "
               "0.05 and 0.2 rescore identical trajectories. Points are eight-seed means; bars are the supplied probe's "
               "ordinary descriptive 95% Student-t intervals (critical value 2.365, df=7). Weight 0 is consumption only. "
               "At capacity 80 with restrained peers, 89.4% of mean weight-0.05 gain is terminal inventory. At capacity "
               "8 with aggressive peers, the consumption-only sign is unresolved. Focal identity is fixed at 0; these "
               "64 episodes do not establish a private optimum or a formal assurance-game classification.")
    inputs = [source / name for name in ("summary.json", "design.json", "manifest.json", "original-stdout.txt", "replay-receipt.json")]
    inputs += [Path(__file__).resolve(), ROOT / "swarm_societies/visualize.py"]
    label = lambda path: str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    provenance = {"version": "commons-v3-temptation-review-figure-v1", "style": "Chromatic Field v1",
                  "caption": caption, "sources": {label(p): digest(p) for p in inputs},
                  "outputs": {label(p): digest(p) for p in outputs}, "plotted_values": plotted,
                  "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__}}
    (output / "manifest.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    (output / "README.md").write_text("# External temptation probe, 7 October 2026\n\n" + caption + "\n\n"
        "![Storage and aggression](temptation-storage.png)\n\n"
        "Exports: [SVG](temptation-storage.svg), [PDF](temptation-storage.pdf), [PNG](temptation-storage.png). "
        "Source and output hashes are in [manifest.json](manifest.json).\n")
    print(json.dumps({"outputs": [label(p) for p in outputs], "manifest": label(output / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
