#!/usr/bin/env python3
"""Render verified, recorded commons-v3 development data without simulation."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.visualize import BACKGROUND, INK, MUTED, RULE, SECONDARY, digest, save, theme
import matplotlib
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np

VERSION = "commons-v3-development-figures-v2"
LABELS = {"restraint": "All restraint", "greedy": "All greedy",
          "focal_greedy": "Focal greedy", "half_greedy": "Half greedy"}
LINESTYLES = {"restraint": "-", "greedy": "--", "focal_greedy": ":", "half_greedy": "-."}
CONDITIONS = tuple(LABELS)
WEIGHTS = (0., .05, .2)
WEIGHT_MARKERS = ("o", "s", "D")
FIGURES = ("development-outcomes", "recorded-spatial-states")
TABLES = ("condition-means.csv", "focal-effects.csv", "reference-trajectories.csv", "spatial-frames.csv")


def read(path):
    return json.loads(Path(path).read_text())


def load(source):
    """The numerical verifier checks the full inventory and aggregate first."""
    archive_version = read(source / "manifest.json").get("version")
    if archive_version == "commons-v3-foundation-development-v1":
        from swarm_societies.commons_v3 import development as verifier
    elif archive_version == "commons-v3-foundation-development-v2":
        from swarm_societies.commons_v3 import development_v2 as verifier
    else:
        raise ValueError("unsupported development archive version")
    receipt = verifier.verify(source, replay=False)
    specification = read(source / "design.json")
    summary = read(source / "summary.json")
    manifest = read(source / "manifest.json")
    if specification["conditions"] != list(CONDITIONS) or specification["wealth_weights"] != list(WEIGHTS):
        raise ValueError("unsupported condition or utility grid")
    selected = next(c for c in specification["cases"] if c["id"] == specification["reference_frames_case"])
    reference_cases = [c for c in specification["cases"] if c["panel"] == "grid"
                       and c["config"]["renewal_rate"] == selected["config"]["renewal_rate"]
                       and c["config"]["need"] == selected["config"]["need"]]
    reference = [verifier.read_case(source / "cases" / (c["id"] + ".json.gz")) for c in reference_cases]
    if not reference or len({r["case"]["horizon"] for r in reference}) != 1:
        raise ValueError("reference trajectories have inconsistent horizons")
    spatial = next(r for r in reference if r["case"]["id"] == selected["id"])
    for episode in spatial["episodes"]:
        frames = episode["spatial_frames"]
        if not frames or frames[0]["tick"] != 0 or frames[-1]["tick"] != selected["horizon"]:
            raise ValueError("predeclared initial/final spatial frames are missing")
        for frame in (frames[0], frames[-1]):
            if len(frame["agents"]) != selected["config"]["n_agents"] or len(frame["sites"]) != selected["config"]["n_patches"]:
                raise ValueError("incomplete spatial frame")
    return specification, summary, manifest, reference, spatial, receipt


def table(path, rows):
    if not rows:
        raise ValueError("cannot export an empty evidence table")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def summaries(summary, output):
    conditions, effects = [], []
    for cell in sorted(summary["cells"], key=lambda c: (c["panel"], c["renewal_rate"], c["need"])):
        identity = {"panel": cell["panel"], "renewal_rate": cell["renewal_rate"], "need": cell["need"],
                    "paired_configurations": cell["paired_configurations"]}
        for condition in CONDITIONS:
            values = cell["conditions"][condition]
            conditions.append({**identity, "condition": condition, **values,
                               "consumption_fraction_of_need": values["consumption_per_agent_tick"] / cell["need"]})
        for outcome, values in sorted(cell["focal_deviation"].items()):
            effects.append({**identity, "contrast": "focal_greedy_minus_restraint", "outcome": outcome, **values,
                            "mean_fraction_of_need": values["mean"] / cell["need"],
                            "min_fraction_of_need": values["min"] / cell["need"],
                            "max_fraction_of_need": values["max"] / cell["need"]})
        values = cell["widespread_greedy_consumption_difference"]
        effects.append({**identity, "contrast": "all_greedy_minus_all_restraint", "outcome": "population_consumption", **values,
                        "mean_fraction_of_need": values["mean"] / cell["need"],
                        "min_fraction_of_need": values["min"] / cell["need"],
                        "max_fraction_of_need": values["max"] / cell["need"]})
    return [table(output / TABLES[0], conditions), table(output / TABLES[1], effects)]


def trajectory_means(reference):
    rows = []
    horizon = reference[0]["case"]["horizon"]
    for condition in CONDITIONS:
        episodes = [next(e for e in r["episodes"] if e["condition"] == condition) for r in reference]
        if any(len(e["trajectory"]) != horizon for e in episodes):
            raise ValueError("incomplete reference trajectory")
        for tick in range(horizon):
            normalized_consumption, normalized_stock = [], []
            for record, episode in zip(reference, episodes):
                cfg, saved = record["case"]["config"], episode["trajectory"][tick]
                if saved["tick"] != tick + 1:
                    raise ValueError("noncanonical trajectory ticks")
                normalized_consumption.append(saved["consumption"] / (cfg["n_agents"] * cfg["need"]))
                normalized_stock.append(saved["stock"] / (cfg["n_patches"] * cfg["patch_capacity"]))
            rows.append({"condition": condition, "tick": tick + 1, "configurations": len(reference),
                         "consumption_fraction_of_need": statistics.mean(normalized_consumption),
                         "stock_fraction_of_capacity": statistics.mean(normalized_stock)})
    return rows


def quantitative(summary, reference, output, status):
    grid = sorted((cell for cell in summary["cells"] if cell["panel"] == "grid"),
                  key=lambda c: (c["renewal_rate"], c["need"]))
    rates, needs = sorted({c["renewal_rate"] for c in grid}), sorted({c["need"] for c in grid})
    if len(grid) != len(rates) * len(needs) or len({(c["renewal_rate"], c["need"]) for c in grid}) != len(grid):
        raise ValueError("incomplete ecological grid")
    ticks = list(range(len(grid)))
    row_labels = [f"r {c['renewal_rate']:.2f} · need {c['need']:.1f}" for c in grid]
    fig, axes = plt.subplots(2, 2, figsize=(14.8, 11.4))
    fig.text(.075, .967, "Physical commons development, before qualification", fontsize=19, weight="bold", va="top")
    fig.text(.075, .930, status + " · fixed local policies · descriptive paired comparisons", fontsize=11, color=SECONDARY)
    ax = axes[0, 0]
    ax.set_title("A  Consumption across the ecological grid", loc="left", pad=34)
    ax.text(0, 1.065, "Means across four paired seeds; row labels declare need", transform=ax.transAxes, color=SECONDARY, fontsize=9)
    for y, cell in enumerate(grid):
        values = [cell["conditions"][c]["consumption_per_agent_tick"] / cell["need"] for c in ("restraint", "greedy")]
        ax.plot(values, [y, y], color=RULE, linewidth=2, zorder=1)
        for value, marker in zip(values, ("o", "s")):
            ax.scatter(value, y, marker=marker, s=48, facecolor=BACKGROUND, edgecolor=INK, linewidth=1.3, zorder=3)
    ax.set_yticks(ticks, row_labels)
    ax.set_ylim(len(grid) - .5, -.5)
    ax.set_xlim(-.025, 1.045)
    ax.set_xlabel("Consumption / declared need")
    ax.axvline(1, color=SECONDARY, linestyle=":", linewidth=.8)
    ax.grid(axis="x", alpha=.7)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[Line2D([], [], color=INK, marker=m, markerfacecolor=BACKGROUND, linestyle="", label=LABELS[c])
                       for m, c in zip(("o", "s"), ("restraint", "greedy"))],
              loc="upper center", bbox_to_anchor=(.5, -.20), ncol=2, fontsize=9)

    ax = axes[0, 1]
    ax.set_title("B  One focal agent switches to greedy", loc="left", pad=34)
    ax.text(0, 1.065, "Mean and observed min–max over four seeds; not confidence intervals", transform=ax.transAxes, color=SECONDARY, fontsize=9)
    for index, (weight, marker) in enumerate(zip(WEIGHTS, WEIGHT_MARKERS)):
        for y, cell in enumerate(grid):
            result = cell["focal_deviation"]["utility_" + str(weight)]
            mean, lower, upper = (result[k] / cell["need"] for k in ("mean", "min", "max"))
            offset = y + (index - 1) * .19
            ax.errorbar(mean, offset, xerr=[[max(0., mean - lower)], [max(0., upper - mean)]],
                        fmt=marker, color=INK, markerfacecolor=BACKGROUND, markersize=4.6,
                        linewidth=.9, capsize=2, zorder=3)
    ax.set_yticks(ticks, row_labels)
    ax.set_ylim(len(grid) - .5, -.5)
    ax.axvline(0, color=SECONDARY, linestyle="--", linewidth=.8)
    ax.set_xlabel("Focal Δ private utility / declared need")
    ax.grid(axis="x", alpha=.7)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[Line2D([], [], color=INK, marker=m, markerfacecolor=BACKGROUND, linestyle="", label=f"Wealth weight {w:g}")
                       for w, m in zip(WEIGHTS, WEIGHT_MARKERS)],
              loc="upper center", bbox_to_anchor=(.5, -.20), ncol=3, fontsize=8.5, handletextpad=.5, columnspacing=1.)

    trajectories = trajectory_means(reference)
    horizon = reference[0]["case"]["horizon"]
    reference_cfg = reference[0]["case"]["config"]
    for ax, key, title, ylabel in (
        (axes[1, 0], "consumption_fraction_of_need", "C  Reference consumption trajectory", "Consumption / declared need"),
        (axes[1, 1], "stock_fraction_of_capacity", "D  Reference ecological trajectory", "Resource stock / site capacity"),
    ):
        ax.set_title(title, loc="left", pad=33)
        ax.text(0, 1.065, f"r {reference_cfg['renewal_rate']:.2f} · need {reference_cfg['need']:g} · mean across four recorded seeds",
                transform=ax.transAxes, color=SECONDARY, fontsize=9)
        for condition in CONDITIONS:
            rows = [r for r in trajectories if r["condition"] == condition]
            ax.plot([r["tick"] for r in rows], [r[key] for r in rows], color=INK,
                    linestyle=LINESTYLES[condition], linewidth=1.35, label=LABELS[condition])
        ax.set_xlim(0, horizon)
        ax.set_ylim(-.025, 1.055)
        ax.set_xlabel("Completed tick")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=.65)
    handles = [Line2D([], [], color=INK, linestyle=LINESTYLES[c], linewidth=1.5, label=LABELS[c]) for c in CONDITIONS]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.53, .115), ncol=4, fontsize=10)
    fig.text(.075, .070, f"{summary['configurations']} configurations × four conditions = {summary['episodes']} episodes; reused seeds across parameters are dependent.", color=SECONDARY, fontsize=9.5)
    fig.text(.075, .046, "Utility = (cumulative consumption + weight × terminal inventory) / horizon. Four seeds; zero evolutionary runs or model calls.", color=SECONDARY, fontsize=9.5)
    fig.text(.075, .022, "This is development evidence, not a qualified social dilemma. All declared sensitivities remain in the CSV tables and archive.", color=SECONDARY, fontsize=9.5)
    fig.subplots_adjust(left=.14, right=.975, top=.835, bottom=.205, wspace=.64, hspace=.80)
    return [*save(fig, output / FIGURES[0]), table(output / TABLES[2], trajectories)]


def spatial_plot(record, output, status):
    case, episodes = record["case"], record["episodes"]
    cfg = case["config"]
    cmap = LinearSegmentedColormap.from_list("commons-resource-stock", [BACKGROUND, MUTED, SECONDARY])
    norm = Normalize(0, 1)
    fig, axes = plt.subplots(2, len(CONDITIONS), figsize=(14.6, 8.7))
    fig.text(.055, .971, "Recorded locations and stocks in the preselected reference case", fontsize=18, weight="bold", va="top")
    fig.text(.055, .926, f"{status} · seed {case['seed']} · actual grid cells; no inferred paths", color=SECONDARY, fontsize=10.5)
    spatial_rows = []
    for column, condition in enumerate(CONDITIONS):
        episode = next(e for e in episodes if e["condition"] == condition)
        for row, frame in enumerate((episode["spatial_frames"][0], episode["spatial_frames"][-1])):
            ax = axes[row, column]
            ax.set_title(f"{LABELS[condition]}\n{'Initial' if row == 0 else 'Final'} · tick {frame['tick']}", fontsize=10, pad=10)
            sites = frame["sites"]
            stock_colors = [p["stock"] / cfg["patch_capacity"] for p in sites]
            ax.scatter([p["x"] for p in sites], [p["y"] for p in sites], c=stock_colors,
                       cmap=cmap, norm=norm, marker="s", s=160, linewidth=.7, edgecolors=SECONDARY, zorder=2)
            counts = Counter((agent["x"], agent["y"]) for agent in frame["agents"])
            ax.scatter([p[0] for p in counts], [p[1] for p in counts], marker="o", s=56,
                       facecolors=BACKGROUND, edgecolors=INK, linewidth=.9, zorder=3)
            for (x, y), count in counts.items():
                ax.text(x, y, str(count), ha="center", va="center", fontsize=5.5, color=INK, zorder=4)
            ax.set_xlim(-.5, cfg["width"] - .5)
            ax.set_ylim(cfg["height"] - .5, -.5)
            ax.set_aspect("equal")
            ax.set_xticks(range(0, cfg["width"], 3))
            ax.set_yticks(range(0, cfg["height"], 3))
            ax.set_xticks(np.arange(-.5, cfg["width"], 1), minor=True)
            ax.set_yticks(np.arange(-.5, cfg["height"], 1), minor=True)
            ax.grid(which="minor", color=RULE, alpha=.7, linewidth=.45)
            ax.tick_params(which="minor", length=0)
            ax.tick_params(which="major", labelsize=8, length=0)
            if row == 1:
                ax.set_xlabel("Grid x", fontsize=9)
            if column == 0:
                ax.set_ylabel("Grid y", fontsize=9)
            for agent in frame["agents"]:
                spatial_rows.append({"condition": condition, "tick": frame["tick"], "kind": "agent", "id": agent["id"],
                                     "x": agent["x"], "y": agent["y"], "inventory": agent["inventory"], "stock": "",
                                     "capacity": "", "policy": agent["policy"]})
            for site in sites:
                spatial_rows.append({"condition": condition, "tick": frame["tick"], "kind": "site", "id": site["id"],
                                     "x": site["x"], "y": site["y"], "inventory": "", "stock": site["stock"],
                                     "capacity": cfg["patch_capacity"], "policy": ""})
    bar_ax = fig.add_axes([.78, .093, .165, .016])
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=bar_ax, orientation="horizontal")
    bar.set_ticks([0, .5, 1])
    bar.ax.tick_params(labelsize=8)
    bar.set_label("Square fill: stock / capacity", fontsize=8, labelpad=2)
    fig.text(.055, .107, "Squares mark resource sites. Circles mark occupied cells; numerals count co-located agents.", color=SECONDARY, fontsize=9.5)
    fig.text(.055, .077, "Identical initial physical states are repeated for comparison. No society identity, affiliation, or travel path is encoded.", color=SECONDARY, fontsize=9)
    fig.text(.055, .046, "One predeclared seed illustrates spatial states; quantitative comparisons use the complete saved grid and seed panel.", color=SECONDARY, fontsize=9)
    fig.subplots_adjust(left=.055, right=.965, top=.835, bottom=.185, wspace=.28, hspace=.37)
    return [*save(fig, output / FIGURES[1]), table(output / TABLES[3], spatial_rows)]


def path_label(path):
    resolved = path.resolve()
    return str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(resolved)


def render(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    specification, summary, archive, reference, spatial, receipt = load(source)
    revision = "v1" if archive["version"] == "commons-v3-foundation-development-v1" else "v2"
    status = ("v1 failed navigation control" if revision == "v1" else "v2 development after reserve-arithmetic repair")
    revision_note = ("This v1 bank is retained as a failed navigation control: floating-point fuel comparisons can strand agents. "
                     "Its outcomes cannot qualify the intended navigation baseline."
                     if revision == "v1" else
                     "This v2 bank repeats the declared development panel after the reserve-arithmetic repair. "
                     "The failed v1 navigation control remains preserved separately; the physical engine is unchanged.")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("figure output must be separate from the evidence directory")
    allowed = {"README.md", "manifest.json", *TABLES, *(f"{stem}.{ext}" for stem in FIGURES for ext in ("svg", "pdf", "png"))}
    if output.exists() and any(path.name not in allowed or not path.is_file() for path in output.iterdir()):
        raise ValueError("figure directory contains unrelated artifacts")
    if (output / "manifest.json").exists():
        prior = read(output / "manifest.json")
        if prior.get("version") != VERSION or prior.get("evidence_manifest_sha256") != receipt["manifest_sha256"]:
            raise ValueError("existing figure gallery belongs to a different archive")
    output.mkdir(parents=True, exist_ok=True)
    theme()
    outputs = summaries(summary, output)
    outputs += quantitative(summary, reference, output, status)
    outputs += spatial_plot(spatial, output, status)
    readme = output / "README.md"
    readme.write_text(f"""# Physical commons development · Chromatic Field v1

**{status}.** {revision_note} Neither bank is a completed qualification.

![Recorded development outcomes](development-outcomes.png)

[SVG](development-outcomes.svg) · [PDF](development-outcomes.pdf) · [PNG](development-outcomes.png)

**Quantitative caption.** Panel A compares mean consumption divided by declared
need for all-restraint and all-greedy populations across the full ecological
grid. Panel B replaces one focal policy, leaving peers unchanged, and shows
the mean and observed minimum–maximum paired utility difference over four seeds.
These ranges are descriptive, **not confidence intervals**. Wealth weights
0, 0.05 and 0.2 are separately marked. Utility is `(consumption + weight ×
terminal inventory) / horizon`, then divided by need for the plot. Focal IDs
vary with seed, not as independent replicates. Both extraction and navigation
may change with the focal policy. Panels C and D use the predeclared reference
cell and show per-tick means over all four saved seeds, without smoothing.
Conditions use neutral markers and line styles; no society colors are assigned.

![Recorded initial and final spatial states](recorded-spatial-states.png)

[SVG](recorded-spatial-states.svg) · [PDF](recorded-spatial-states.pdf) · [PNG](recorded-spatial-states.png)

**Spatial caption.** Actual initial and final frames from the preselected case
`{specification['reference_frames_case']}` show sites as squares, stock/capacity
as a common grayscale, and occupied agent cells as circles with co-location
counts. Agent positions are not jittered. The same initial physical state is
repeated across four conditions; no trajectories, affiliations or unrecorded
interactions are inferred. This single case is an illustration, not the
quantitative replication unit.

The archive contains {summary['configurations']} configurations and {summary['episodes']} episodes,
including the complete declared sensitivities. Four environment seeds are reused
across parameter cells and sensitivities, so these comparisons are dependent.
There are zero evolutionary runs and zero experimental model calls. This is
exploratory physical development, not a completed social-dilemma qualification
or evidence that institutions are useful. Consumption and unmet need are
complementary accounting outcomes, not independent welfare measures.

Recorded tables:

- [All condition means and sensitivities](condition-means.csv)
- [All paired effects, wealth sensitivities and descriptive ranges](focal-effects.csv)
- [Reference-cell mean trajectories](reference-trajectories.csv)
- [Exact plotted spatial coordinates, stocks and inventories](spatial-frames.csv)

The renderer dispatches explicitly on the archive version to
`development.verify(source, replay=False)` for v1 or
`development_v2.verify(source, replay=False)` for v2 before loading plot data.
Unknown versions are rejected. It validates the source freeze, artifact hashes, full case inventory,
and recomputed aggregate; it does not rerun policies or physics. Full semantic
replay is the separate study verifier's responsibility. The figure manifest
pins every evidence artifact, renderer/helper source, software version and
output. Same-runtime rerenders are deterministic; cross-version rendering
identity is not asserted.

Re-render from the repository root:

```bash
.venv/bin/python scripts/visualize_commons_v3_development.py \\
  --source {path_label(source)} \\
  --output figures/commons-v3-foundation-{revision}
```
""")
    outputs.append(readme)
    inputs = [source / "manifest.json", *(source / name for name in sorted(archive["artifacts_sha256"])),
              Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"]
    result = {"version": VERSION, "style": "Chromatic Field v1", "rendering_runs_simulation": False,
              "evidence_version": archive["version"], "study_status": status,
              "evidence_manifest_sha256": receipt["manifest_sha256"], "verification": receipt,
              "sources": [{"path": path_label(path), "sha256": digest(path)} for path in inputs],
              "outputs": [{"path": path.name, "sha256": digest(path)} for path in outputs],
              "versions": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
              "frame_selection": {"case": specification["reference_frames_case"], "ticks": [0, spatial["case"]["horizon"]],
                                  "conditions": list(CONDITIONS)},
              "caption": status + ". " + revision_note + " Exploratory physical development: consumption, paired focal utility and reference trajectories; "
                         "four reused seeds, descriptive min–max ranges, no confidence intervals. Actual recorded spatial "
                         "frames; no affiliation colors or inferred paths. Zero searches and model calls; not qualification."}
    (output / "manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/commons-v3-foundation-v2")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/commons-v3-foundation-v2")
    args = parser.parse_args()
    try:
        result = render(args.source, args.output)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.exit(1, f"Could not render verified development evidence: {error}\n")
    print(json.dumps({"version": VERSION, "outputs": len(result["outputs"]),
                      "figures": len(FIGURES), "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
