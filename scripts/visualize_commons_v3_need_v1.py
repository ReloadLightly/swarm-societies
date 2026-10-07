#!/usr/bin/env python3
"""Render recorded need-targeted development evidence and frozen v2 comparisons."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.visualize import BACKGROUND, INK, MUTED, RULE, SECONDARY, digest, save, theme
import matplotlib
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np

VERSION = "commons-v3-need-figures-v1"
EVIDENCE_VERSION = "commons-v3-need-development-v1"
V2_VERSION = "commons-v3-foundation-development-v2"
V2_MANIFEST_SHA256 = "efc863872d0872ca3089628980c20cfacf1efe2eb2cca05c260d8a3906800947"
V2_FIGURE_MANIFEST_SHA256 = "08b46c4ac6972099277ad1e810bc6e379268925dbc2bf2295f426b70aa20e711"
BASELINES = ("need_0", "need_2")
CONDITIONS = (*BASELINES, "focal_greedy_need_0", "focal_greedy_need_2")
V2_CONDITIONS = ("restraint", "greedy", "focal_greedy", "half_greedy")
POPULATIONS = ("restraint", "greedy", "need_0", "need_2")
LABELS = {"restraint": "Saved v2 restraint", "greedy": "Saved v2 greedy",
          "need_0": "Need-targeted · reserve 0", "need_2": "Need-targeted · reserve 2"}
MARKERS = {"restraint": "o", "greedy": "x", "need_0": "s", "need_2": "^"}
LINESTYLES = {"restraint": ":", "greedy": "--", "need_0": "-.", "need_2": "-"}
WEIGHTS = (0., .05, .2)
WEIGHT_MARKERS = ("o", "s", "D")
FIGURES = ("baseline-comparison", "focal-effects")
TABLES = ("condition-means.csv", "focal-effects.csv", "reserve-effects.csv", "reference-trajectories.csv")


def read(path):
    return json.loads(Path(path).read_text())


def identity(cell):
    return cell["panel"], cell["renewal_rate"], cell["need"]


def path_label(path):
    resolved = Path(path).resolve()
    return str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(resolved)


def checked_digest(path, expected):
    if digest(path) != expected:
        raise ValueError(f"source hash mismatch: {path_label(path)}")


def load(source, comparison, comparison_figures):
    """Verify the new raw bank; old comparisons need only frozen compact artifacts."""
    from swarm_societies.commons_v3 import development_need_v1 as verifier
    receipt = verifier.verify(source, replay=False)
    design, summary, archive = (read(source / name) for name in ("design.json", "summary.json", "manifest.json"))
    if (archive["version"] != EVIDENCE_VERSION or design["conditions"] != list(CONDITIONS)
            or design["wealth_weights"] != list(WEIGHTS)):
        raise ValueError("unsupported need-targeted development archive")

    checked_digest(comparison / "manifest.json", V2_MANIFEST_SHA256)
    old_archive = read(comparison / "manifest.json")
    if old_archive.get("version") != V2_VERSION or old_archive.get("complete") is not True:
        raise ValueError("comparison must be the complete frozen v2 development bank")
    for name in ("design.json", "summary.json"):
        checked_digest(comparison / name, old_archive["artifacts_sha256"][name])
    old_design, old_summary = (read(comparison / name) for name in ("design.json", "summary.json"))
    if (old_design["conditions"] != list(V2_CONDITIONS)
            or old_design["wealth_weights"] != list(WEIGHTS)
            or design["cases"] != old_design["cases"]
            or design["reference_frames_case"] != old_design["reference_frames_case"]):
        raise ValueError("need-targeted cases do not exactly match the frozen v2 cases")
    new_cells = {identity(c): c for c in summary["cells"]}
    old_cells = {identity(c): c for c in old_summary["cells"]}
    if (len(new_cells) != len(summary["cells"]) or set(new_cells) != set(old_cells)
            or any(new_cells[key]["paired_configurations"] != old_cells[key]["paired_configurations"]
                   for key in new_cells)):
        raise ValueError("comparison cells or paired configuration counts differ")

    # The frozen gallery already exported its verified reference means. Reuse
    # that hash-bound projection without restoring or simulating any v2 cases.
    checked_digest(comparison_figures / "manifest.json", V2_FIGURE_MANIFEST_SHA256)
    old_gallery = read(comparison_figures / "manifest.json")
    if (old_gallery["evidence_manifest_sha256"] != V2_MANIFEST_SHA256
            or old_gallery["frame_selection"]["case"] != design["reference_frames_case"]):
        raise ValueError("saved v2 trajectories belong to a different evidence bank or reference case")
    old_trajectory_path = comparison_figures / "reference-trajectories.csv"
    trajectory_hash = next(row["sha256"] for row in old_gallery["outputs"] if row["path"] == old_trajectory_path.name)
    checked_digest(old_trajectory_path, trajectory_hash)
    with old_trajectory_path.open(newline="") as stream:
        old_trajectories = [{"study": V2_VERSION, "condition": row["condition"], "tick": int(row["tick"]),
                             "configurations": int(row["configurations"]),
                             "consumption_fraction_of_need": float(row["consumption_fraction_of_need"]),
                             "stock_fraction_of_capacity": float(row["stock_fraction_of_capacity"])}
                            for row in csv.DictReader(stream)]

    selected = next(c for c in design["cases"] if c["id"] == design["reference_frames_case"])
    reference_cases = [c for c in design["cases"] if c["panel"] == "grid"
                       and c["config"]["renewal_rate"] == selected["config"]["renewal_rate"]
                       and c["config"]["need"] == selected["config"]["need"]]
    reference = [verifier.read_case(source / "cases" / (c["id"] + ".json.gz")) for c in reference_cases]
    trajectories = trajectory_means(reference) + old_trajectories
    for study, conditions in ((EVIDENCE_VERSION, CONDITIONS), (V2_VERSION, V2_CONDITIONS)):
        for condition in conditions:
            rows = [row for row in trajectories if row["study"] == study and row["condition"] == condition]
            if ([row["tick"] for row in rows] != list(range(1, selected["horizon"] + 1))
                    or any(row["configurations"] != len(reference_cases) for row in rows)
                    or any(not math.isfinite(row[k]) for row in rows
                           for k in ("consumption_fraction_of_need", "stock_fraction_of_capacity"))):
                raise ValueError("incomplete or invalid saved reference trajectories")
    return design, summary, archive, old_summary, trajectories, selected, receipt


def trajectory_means(reference):
    if not reference or len({r["case"]["horizon"] for r in reference}) != 1:
        raise ValueError("reference cases have inconsistent horizons")
    rows = []
    horizon = reference[0]["case"]["horizon"]
    for condition in CONDITIONS:
        episodes = [next(e for e in record["episodes"] if e["condition"] == condition) for record in reference]
        if any(len(e["trajectory"]) != horizon for e in episodes):
            raise ValueError("incomplete reference trajectory")
        for tick in range(horizon):
            consumption, stock = [], []
            for record, episode in zip(reference, episodes):
                cfg, saved = record["case"]["config"], episode["trajectory"][tick]
                if saved["tick"] != tick + 1:
                    raise ValueError("noncanonical trajectory ticks")
                consumption.append(saved["consumption"] / (cfg["n_agents"] * cfg["need"]))
                stock.append(saved["stock"] / (cfg["n_patches"] * cfg["patch_capacity"]))
            rows.append({"study": EVIDENCE_VERSION, "condition": condition, "tick": tick + 1,
                         "configurations": len(reference), "consumption_fraction_of_need": statistics.mean(consumption),
                         "stock_fraction_of_capacity": statistics.mean(stock)})
    return rows


def table(path, rows):
    if not rows:
        raise ValueError("cannot export an empty table")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def summaries(summary, old_summary, trajectories, output):
    means, effects, reserves = [], [], []
    for study, saved in ((EVIDENCE_VERSION, summary), (V2_VERSION, old_summary)):
        for cell in sorted(saved["cells"], key=identity):
            base = {"study": study, "panel": cell["panel"], "renewal_rate": cell["renewal_rate"],
                    "need": cell["need"], "paired_configurations": cell["paired_configurations"]}
            for condition, values in sorted(cell["conditions"].items()):
                means.append({**base, "condition": condition, **values,
                              "consumption_fraction_of_need": values["consumption_per_agent_tick"] / cell["need"]})
            deviations = cell["focal_deviation"] if study == EVIDENCE_VERSION else {"restraint": cell["focal_deviation"]}
            for baseline, outcomes in sorted(deviations.items()):
                for outcome, values in sorted(outcomes.items()):
                    effects.append({**base, "baseline": baseline, "contrast": "focal_greedy_minus_baseline",
                                    "outcome": outcome, **values})
            if study == EVIDENCE_VERSION:
                for outcome, values in sorted(cell["reserve_comparison"].items()):
                    reserves.append({**base, "contrast": "all_need_2_minus_all_need_0", "outcome": outcome, **values})
    return [table(output / TABLES[0], means), table(output / TABLES[1], effects),
            table(output / TABLES[2], reserves), table(output / TABLES[3], trajectories)]


def grid_cells(summary):
    grid = sorted((c for c in summary["cells"] if c["panel"] == "grid"), key=identity)
    rates, needs = {c["renewal_rate"] for c in grid}, {c["need"] for c in grid}
    if len(grid) != len(rates) * len(needs) or len({identity(c) for c in grid}) != len(grid):
        raise ValueError("incomplete ecological grid")
    return grid


def grid_axis(ax, grid, selected):
    labels = []
    for index, cell in enumerate(grid):
        reference = (cell["renewal_rate"] == selected["config"]["renewal_rate"]
                     and cell["need"] == selected["config"]["need"])
        labels.append(f"r {cell['renewal_rate']:.2f} · need {cell['need']:.1f}" + (" *" if reference else ""))
        if reference:
            ax.axhspan(index - .48, index + .48, color=MUTED, zorder=0)
    ax.set_yticks(range(len(grid)), labels)
    ax.set_ylim(len(grid) - .5, -.5)
    ax.grid(axis="x", alpha=.65)
    ax.tick_params(axis="y", length=0)


def comparison_plot(summary, old_summary, trajectories, selected, output):
    grid, old_cells = grid_cells(summary), {identity(c): c for c in old_summary["cells"]}
    fig, axes = plt.subplots(2, 2, figsize=(15.2, 11.4))
    fig.text(.07, .968, "Need-targeted harvesting on the reused development panel", fontsize=18, weight="bold", va="top")
    fig.text(.07, .931, "Zero or two needs of soft reserve · unchanged physical engine · saved v2 comparisons", fontsize=11, color=SECONDARY)
    for ax, field, title, xlabel in (
        (axes[0, 0], "consumption_per_agent_tick", "A  Population consumption", "Consumption / declared need"),
        (axes[0, 1], "terminal_stock_fraction", "B  Terminal ecological stock", "Resource stock / site capacity"),
    ):
        ax.set_title(title, loc="left", pad=29)
        ax.text(0, 1.045, "Four paired seeds per cell; separate markers prevent overlap", transform=ax.transAxes, fontsize=9, color=SECONDARY)
        grid_axis(ax, grid, selected)
        for index, condition in enumerate(POPULATIONS):
            for y, cell in enumerate(grid):
                saved = old_cells[identity(cell)] if condition in V2_CONDITIONS else cell
                value = saved["conditions"][condition][field]
                if field == "consumption_per_agent_tick":
                    value /= cell["need"]
                ax.plot(value, y + (index - 1.5) * .17, marker=MARKERS[condition], markersize=5.5,
                        color=INK, markerfacecolor=BACKGROUND, markeredgewidth=1.05, linestyle="", zorder=3)
        ax.set_xlim(-.025, 1.045)
        ax.set_xlabel(xlabel)
        ax.axvline(1, color=SECONDARY, linewidth=.8, linestyle=":")
    for ax, field, title, ylabel in (
        (axes[1, 0], "consumption_fraction_of_need", "C  Reference consumption trajectory", "Consumption / declared need"),
        (axes[1, 1], "stock_fraction_of_capacity", "D  Reference ecological trajectory", "Resource stock / site capacity"),
    ):
        ax.set_title(title, loc="left", pad=29)
        ax.text(0, 1.045, f"r {selected['config']['renewal_rate']:.2f} · need {selected['config']['need']:g} · means of four recorded seeds",
                transform=ax.transAxes, fontsize=9, color=SECONDARY)
        for index, condition in enumerate(POPULATIONS):
            rows = [r for r in trajectories if r["condition"] == condition]
            ax.plot([r["tick"] for r in rows], [r[field] for r in rows], color=INK,
                    linestyle=LINESTYLES[condition], marker=MARKERS[condition], markerfacecolor=BACKGROUND,
                    markersize=4.5, markevery=(8 * index, 32), linewidth=1.2, label=LABELS[condition])
        ax.set_xlim(0, selected["horizon"])
        ax.set_ylim(-.025, 1.055)
        ax.set_xlabel("Completed tick")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=.65)
    handles = [Line2D([], [], color=INK, marker=MARKERS[c], markerfacecolor=BACKGROUND,
                      linestyle=LINESTYLES[c], linewidth=1.2, label=LABELS[c]) for c in POPULATIONS]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.53, .112), ncol=2, fontsize=10,
               columnspacing=3., handlelength=3.2)
    fig.text(.07, .072, "* Shaded reference row. Same 56 configurations and four reused seeds per bank; 224 new and 224 previously saved episodes.", color=SECONDARY, fontsize=9.5)
    fig.text(.07, .046, "Consumption loss and global ecological stock are distinct. Curves show recorded tick means without smoothing.", color=SECONDARY, fontsize=9.5)
    fig.text(.07, .020, "Exploratory development, not independent qualification. Zero evolutionary runs or experimental model calls.", color=SECONDARY, fontsize=9.5)
    fig.subplots_adjust(left=.145, right=.975, top=.845, bottom=.23, wspace=.68, hspace=.58)
    return save(fig, output / FIGURES[0])


def effect_limits(values):
    lower, upper = min(0., min(values)), max(0., max(values))
    margin = max((upper - lower) * .12, .002)
    return lower - margin, upper + margin


def focal_plot(summary, selected, output):
    grid = grid_cells(summary)
    fig, axes = plt.subplots(2, 2, figsize=(15.2, 11.4))
    fig.text(.07, .969, "One focal individual switches from need-targeting to greedy", fontsize=18, weight="bold", va="top")
    fig.text(.07, .931, "Identical paired physical starts · peers retain the named baseline · descriptive ranges over four reused seeds", fontsize=10.5, color=SECONDARY)
    utility_limits = effect_limits([cell["focal_deviation"][baseline]["utility_" + str(weight)][bound] / cell["need"]
                                   for cell in grid for baseline in BASELINES for weight in WEIGHTS for bound in ("min", "max")])
    peer_limits = effect_limits([cell["focal_deviation"][baseline]["peer_consumption"][bound] / cell["need"]
                                for cell in grid for baseline in BASELINES for bound in ("min", "max")])
    for column, baseline in enumerate(BASELINES):
        reserve = baseline.rsplit("_", 1)[1]
        for row in (0, 1):
            ax = axes[row, column]
            grid_axis(ax, grid, selected)
            ax.axvline(0, color=SECONDARY, linestyle="--", linewidth=.8)
        ax = axes[0, column]
        ax.set_title(f"{'AB'[column]}  Focal private utility · reserve {reserve}", loc="left", pad=29)
        ax.text(0, 1.045, "Mean and observed min–max; these are not confidence intervals", transform=ax.transAxes, color=SECONDARY, fontsize=8.9)
        for index, (weight, marker) in enumerate(zip(WEIGHTS, WEIGHT_MARKERS)):
            for y, cell in enumerate(grid):
                values = cell["focal_deviation"][baseline]["utility_" + str(weight)]
                mean, lower, upper = (values[k] / cell["need"] for k in ("mean", "min", "max"))
                ax.errorbar(mean, y + (index - 1) * .19,
                            xerr=[[max(0., mean - lower)], [max(0., upper - mean)]], fmt=marker,
                            color=INK, markerfacecolor=BACKGROUND, markersize=4.7, linewidth=.9, capsize=2)
        ax.set_xlim(*utility_limits)
        ax.set_xlabel("Focal Δ private utility / declared need")
        ax = axes[1, column]
        ax.set_title(f"{'CD'[column]}  Peer consumption · reserve {reserve}", loc="left", pad=29)
        ax.text(0, 1.045, "Average over the 23 peers, then paired across four seeds", transform=ax.transAxes, color=SECONDARY, fontsize=9)
        for y, cell in enumerate(grid):
            values = cell["focal_deviation"][baseline]["peer_consumption"]
            mean, lower, upper = (values[k] / cell["need"] for k in ("mean", "min", "max"))
            ax.errorbar(mean, y, xerr=[[max(0., mean - lower)], [max(0., upper - mean)]], fmt="o",
                        color=INK, markerfacecolor=BACKGROUND, markersize=5, linewidth=1, capsize=2)
        ax.set_xlim(*peer_limits)
        ax.set_xlabel("Peer Δ consumption per tick / declared need")
    handles = [Line2D([], [], color=INK, marker=m, markerfacecolor=BACKGROUND, linestyle="", label=f"Wealth weight {w:g}")
               for w, m in zip(WEIGHTS, WEIGHT_MARKERS)]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.53, .113), ncol=3, fontsize=10)
    fig.text(.07, .077, "* Shaded reference row. Utility = (cumulative consumption + weight × terminal inventory) / horizon.", color=SECONDARY, fontsize=9.5)
    fig.text(.07, .051, "Weight 0 is focal consumption. Larger weights additionally value terminal inventory; they do not imply greater consumption.", color=SECONDARY, fontsize=9.5)
    fig.text(.07, .025, "Reused development seeds; no untouched test or institutional outcomes. All sensitivities and raw effect units are retained in the CSV tables.", color=SECONDARY, fontsize=9.5)
    fig.subplots_adjust(left=.145, right=.975, top=.845, bottom=.20, wspace=.68, hspace=.56)
    return save(fig, output / FIGURES[1])


def render(source, comparison, comparison_figures, output):
    source, comparison, comparison_figures, output = (Path(p).resolve() for p in (source, comparison, comparison_figures, output))
    for protected in (source, comparison, comparison_figures):
        if output == protected or output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError("figure output must be separate from every evidence and comparison directory")
    design, summary, archive, old_summary, trajectories, selected, receipt = load(source, comparison, comparison_figures)
    allowed = {"README.md", "manifest.json", *TABLES, *(f"{stem}.{ext}" for stem in FIGURES for ext in ("svg", "pdf", "png"))}
    if output.exists() and any(path.name not in allowed or not path.is_file() for path in output.iterdir()):
        raise ValueError("figure directory contains unrelated artifacts")
    if (output / "manifest.json").exists():
        prior = read(output / "manifest.json")
        if prior.get("version") != VERSION or prior.get("evidence_manifest_sha256") != receipt["manifest_sha256"]:
            raise ValueError("existing figure gallery belongs to another archive")
    output.mkdir(parents=True, exist_ok=True)
    theme()
    outputs = summaries(summary, old_summary, trajectories, output)
    outputs += comparison_plot(summary, old_summary, trajectories, selected, output)
    outputs += focal_plot(summary, selected, output)
    readme = output / "README.md"
    readme.write_text(f"""# Need-targeted physical development · Chromatic Field v1

Recorded exploratory development on the same four seeds and 56 configurations
as the saved v2 foundation bank. This is **not untouched qualification**.
The new bank has {summary['episodes']} episodes and adds need-targeted harvest
policies with zero or two needs of soft inventory reserve, plus one focal
greedy replacement for each baseline. Inventory capacity is 80 in the grid;
the separately declared small-inventory sensitivity remains 8. No institutions,
evolutionary runs or experimental model calls enter these comparisons.

![Population comparison](baseline-comparison.png)

[SVG](baseline-comparison.svg) · [PDF](baseline-comparison.pdf) · [PNG](baseline-comparison.png)

**Population caption.** Panels A and B compare means over four paired seeds for
the two new all-need-targeted populations and the saved v2 all-restraint and
all-greedy populations, across the complete nine-cell ecological grid.
Condition markers have small vertical offsets to expose coincident values;
horizontal positions retain the data values. Consumption is divided by
declared need; terminal ecological stock is divided by total site capacity.
Consumption failure and loss of the entire ecological stock are distinct.
Panels C and D show unsmoothed per-tick means over the four seeds of the
predeclared reference cell, r={selected['config']['renewal_rate']:g},
need={selected['config']['need']:g}; its row is shaded and starred above.
Line styles and markers identify conditions. No society colors are assigned.
The v2 curves are loaded from the hash-checked frozen figure table; old cases
are neither restored nor rerun by this renderer.

![Paired focal effects](focal-effects.png)

[SVG](focal-effects.svg) · [PDF](focal-effects.pdf) · [PNG](focal-effects.png)

**Focal-effects caption.** One predeclared focal individual switches to the
frozen v2 greedy policy while the other 23 agents retain need-targeting with
the indicated reserve. Each point is the mean paired difference across four
seeds; whiskers are observed minimum–maximum differences, **not confidence
intervals**. The two columns share scales within each row. Panels A and B
show `(consumption + wealth_weight × terminal_inventory) / horizon`, divided
by declared need. Weight 0 therefore represents consumption alone. Panels C
and D show per-peer mean consumption differences divided by need. Focal IDs
vary with seed; agents and ticks are not independent replicates. The focal
replacement changes a policy bundle, including navigation and harvesting,
so its effects do not identify an isolated mechanism. Four seeds are reused
across parameter cells, sensitivities and the preceding development banks.

Tables retain all saved cells, including the five declared sensitivities:

- [All condition means, including saved v2 conditions](condition-means.csv)
- [Paired focal effects, terminal inventory and utility weights](focal-effects.csv)
- [Paired reserve-2 minus reserve-0 effects](reserve-effects.csv)
- [Reference trajectories for every new and saved v2 condition](reference-trajectories.csv)

Effect-table values retain their original units. Focal consumption and utility
are per individual per tick; peer consumption is per peer per tick; terminal
inventory is an unnormalized endpoint. Population summary fields retain the
units declared in their names. Blank fields represent absent old diagnostics,
not zero measurements. Consumption and shortfall are complementary accounting
outcomes and must not be counted as independent welfare results.

The renderer calls `development_need_v1.verify(source, replay=False)` before
reading new data. This checks the source freeze, hashes, inventory and saved
aggregate without running policies or physics. Full semantic replay belongs
to the separate study verifier. Frozen v2 manifest hashes are pinned in this
renderer; the v2 design and summary must match their artifact hashes and all
new case configurations exactly. The old trajectory CSV must match its frozen
gallery manifest and evidence-manifest binding. This verifies a saved compact
projection; it does not repeat the v2 aggregate or semantic verification.

The manifest records all new evidence source hashes, the compact v2 comparison
inputs, renderer/helper hashes, software versions and exported file hashes.
Same-runtime rerenders are deterministic; cross-version byte identity is not
asserted. Every SVG, PDF and PNG export is retained.

```bash
.venv/bin/python scripts/visualize_commons_v3_need_v1.py \\
  --source {path_label(source)} \\
  --comparison {path_label(comparison)} \\
  --comparison-figures {path_label(comparison_figures)} \\
  --output {path_label(output)}
```
""")
    outputs.append(readme)
    inputs = [source / "manifest.json", *(source / name for name in sorted(archive["artifacts_sha256"])),
              *(comparison / name for name in ("manifest.json", "design.json", "summary.json")),
              comparison_figures / "manifest.json", comparison_figures / "reference-trajectories.csv",
              Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"]
    result = {"version": VERSION, "style": "Chromatic Field v1", "rendering_runs_simulation": False,
              "evidence_version": archive["version"], "study_status": "exploratory development on reused seeds; not qualification",
              "evidence_manifest_sha256": receipt["manifest_sha256"], "verification": receipt,
              "comparison": {"version": V2_VERSION, "manifest_sha256": V2_MANIFEST_SHA256,
                             "figure_manifest_sha256": V2_FIGURE_MANIFEST_SHA256,
                             "exact_case_configurations_match": True, "raw_cases_loaded": False,
                             "verification_scope": "pinned manifests, artifact hashes, exact designs and saved reference projection"},
              "sources": [{"path": path_label(path), "sha256": digest(path)} for path in inputs],
              "outputs": [{"path": path.name, "sha256": digest(path)} for path in outputs],
              "versions": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
              "reference_selection": {"case": design["reference_frames_case"], "seed_count": 4,
                                      "ticks": [1, selected["horizon"]], "smoothing": False},
              "caption": "Need-targeted development with zero or two needs of soft reserve; frozen v2 population comparisons, "
                         "paired focal greedy utility and peer consumption effects. Four reused seeds; min–max ranges are not "
                         "confidence intervals. No institutions, model calls or evolutionary runs; no qualification claim."}
    (output / "manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/commons-v3-need-v1")
    parser.add_argument("--comparison", type=Path, default=ROOT / "evidence/commons-v3-foundation-v2")
    parser.add_argument("--comparison-figures", type=Path, default=ROOT / "figures/commons-v3-foundation-v2")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/commons-v3-need-v1")
    args = parser.parse_args()
    try:
        result = render(args.source, args.comparison, args.comparison_figures, args.output)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.exit(1, f"Could not render verified need-targeted evidence: {error}\n")
    print(json.dumps({"version": VERSION, "outputs": len(result["outputs"]), "figures": len(FIGURES),
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
