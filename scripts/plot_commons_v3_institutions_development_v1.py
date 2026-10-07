#!/usr/bin/env python3
"""Render only the recorded first optional-charter development comparison."""
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
from swarm_societies.visualize import BACKGROUND, INK, MUTED, RULE, SECONDARY, digest, save, theme
import matplotlib
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

VERSION = "commons-v3-institutions-development-figures-v1"
DESIGN_VERSION = "commons-v3-institutions-development-v1"
ARMS = ("frozen", "decentralized", "charter_unmonitored", "charter_enforced")
LABELS = {"frozen": "Frozen forager", "decentralized": "Decentralized",
          "charter_unmonitored": "Charter · no monitoring", "charter_enforced": "Charter · enforced",
          "all_stubborn": "All stubborn anchor"}
SHORT = {"frozen": "Frozen", "decentralized": "Decentralized",
         "charter_unmonitored": "Unmonitored", "charter_enforced": "Enforced"}
CELLS = (("fixed_floor", 8), ("fixed_floor", 80), ("selected", 8), ("selected", 80))
CONTRASTS = (("decentralized", "frozen"), ("charter_unmonitored", "decentralized"),
             ("charter_enforced", "decentralized"), ("charter_enforced", "charter_unmonitored"))


def read(path):
    return json.loads(Path(path).read_text())


def label(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _manifest_hash(manifest, name):
    files = manifest.get("files", manifest.get("artifacts_sha256", {}))
    value = files.get(name)
    return value.get("sha256") if isinstance(value, dict) else value


def load(source):
    """Require a complete, manifest-bound saved summary; never execute policies."""
    manifest, design, summary = (read(source / name) for name in ("manifest.json", "design.json", "summary.json"))
    if manifest.get("completed") is not True:
        raise ValueError("figures require a completed sealed development bank")
    for name in ("design.json", "summary.json", "sources.json"):
        if _manifest_hash(manifest, name) != digest(source / name):
            raise ValueError(f"saved {name} hash differs from the completed bank manifest")
    if design["version"] != DESIGN_VERSION or design["counts"]["episodes"] != 144:
        raise ValueError("unsupported institutional development design")
    if design["arms"] != list(ARMS) or design["seeds"] != [93001, 93002, 93003, 93004]:
        raise ValueError("unexpected declared arms or seed panel")
    cases = {case["id"]: case for case in design["cases"]}
    episodes = summary["episodes"]
    if len(episodes) != 144 or {episode["case"]["id"] for episode in episodes} != set(cases):
        raise ValueError("the complete 144-episode bank is required")
    if any(episode["case"] != cases[episode["case"]["id"]] for episode in episodes):
        raise ValueError("saved episode case differs from its declared design")
    index = {}
    for episode in episodes:
        case = episode["case"]
        key = (case["control"], int(case["capacity"]), case["stubborn_count"], case["arm"], case["seed"])
        if key in index or episode["summary"]["ticks"] != case["horizon"]:
            raise ValueError("duplicated condition or incomplete recorded episode")
        index[key] = episode
    return design, summary, manifest, index


def records(index, control, capacity, stubborn, arm):
    return [index[control, capacity, stubborn, arm, seed] for seed in (93001, 93002, 93003, 93004)]


def consumption(episodes, late=False, cohort="population"):
    key = "late_consumption_per_tick" if late else "consumption_per_tick"
    return [episode["summary"]["cohorts"][cohort][key] / episode["case"]["config"]["need"]
            for episode in episodes]


def points(ax, values, y, *, marker="o", color=INK, fill=True, shift=0.):
    """Four environmental seed values, observed range, and arithmetic mean."""
    y += shift
    ax.plot([min(values), max(values)], [y, y], color=color, lw=1.05, zorder=2)
    offsets = (-.055, -.018, .018, .055)
    ax.scatter(values, [y + offset for offset in offsets], color=color, s=8, alpha=.48, zorder=3)
    ax.plot(statistics.mean(values), y, marker=marker, markersize=5.4,
            markerfacecolor=color if fill else BACKGROUND, markeredgecolor=color, linestyle="", zorder=4)


def tidy(ax):
    ax.grid(axis="x", zorder=0)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def consumption_figure(index, output):
    fig, axes = plt.subplots(2, 4, figsize=(18.2, 10.9))
    fig.text(.045, .97, "Optional charters against the same competent foragers", fontsize=18, weight="bold")
    fig.text(.045, .935, "144 declared development episodes · four environmental seeds · supplied policy bundles, with no selection or qualification", fontsize=11, color=SECONDARY)
    rows = [(stubborn, arm, 9 - j - (5 if stubborn else 0)) for stubborn in (0, 6) for j, arm in enumerate(ARMS)]
    contrast_rows = [(stubborn, pair, 9 - j - (5 if stubborn else 0)) for stubborn in (0, 6) for j, pair in enumerate(CONTRASTS)]
    difference_values = []
    for control, capacity in CELLS:
        for stubborn, (left, right), _ in contrast_rows:
            for late in (False, True):
                a, b = (consumption(records(index, control, capacity, stubborn, arm), late) for arm in (left, right))
                difference_values.extend(x - y for x, y in zip(a, b))
    bound = max(.002, max(abs(value) for value in difference_values)) * 1.13
    for col, (control, capacity) in enumerate(CELLS):
        upper, lower = axes[:, col]
        name = "Fixed floor" if control == "fixed_floor" else "Selected navigation"
        upper.set_title(f"{name}\nCarrying capacity {capacity}", fontsize=11.5)
        for stubborn, arm, y in rows:
            saved = records(index, control, capacity, stubborn, arm)
            points(upper, consumption(saved), y, shift=.105)
            points(upper, consumption(saved, True), y, marker="D", color=SECONDARY, fill=False, shift=-.105)
        anchor = records(index, control, capacity, 24, "all_stubborn")
        points(upper, consumption(anchor), -1, shift=.105)
        points(upper, consumption(anchor, True), -1, marker="D", color=SECONDARY, fill=False, shift=-.105)
        upper.set_yticks([y for _, _, y in rows] + [-1],
                        [f"{stubborn} · {LABELS[arm]}" for stubborn, arm, _ in rows] + ["24 · All stubborn"] if col == 0 else [""] * (len(rows) + 1))
        upper.set_ylim(-1.65, 9.65)
        upper.set_xlim(-.035, 1.055)
        upper.set_xticks([0, .25, .5, .75, 1.])
        upper.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        upper.set_xlabel("Population consumption / need")
        upper.axvline(1., color=RULE, linewidth=1.2)
        upper.axhline(5, color=RULE, lw=.7)
        upper.axhline(0, color=RULE, lw=.7)
        for stubborn, (left, right), y in contrast_rows:
            a, b = (records(index, control, capacity, stubborn, arm) for arm in (left, right))
            for late, shift, marker, color in ((False, .105, "o", INK), (True, -.105, "D", SECONDARY)):
                values = [x - y for x, y in zip(consumption(a, late), consumption(b, late))]
                points(lower, values, y, marker=marker, color=color, fill=not late, shift=shift)
        lower.set_yticks([y for _, _, y in contrast_rows],
                        [f"{stubborn} · {SHORT[left]} − {SHORT[right]}" for stubborn, (left, right), _ in contrast_rows] if col == 0 else [""] * len(contrast_rows))
        lower.set_ylim(.35, 9.65)
        lower.set_xlim(-bound, bound)
        lower.xaxis.set_major_formatter(PercentFormatter(1, decimals=1))
        lower.set_xlabel("Paired consumption change / need")
        lower.axvline(0., color=SECONDARY, lw=.8, linestyle=(0, (3, 3)))
        lower.axhline(5, color=RULE, lw=.7)
        tidy(upper)
        tidy(lower)
    legend = [Line2D([], [], marker="o", color=INK, ls="", label="All 256 ticks"),
              Line2D([], [], marker="D", color=SECONDARY, markerfacecolor=BACKGROUND, ls="", label="Final 64 ticks")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(.60, .066), ncol=2)
    fig.text(.045, .051, "Row prefix: number of stubborn individuals. Large symbols: four-seed means; small dots: each seed; lines: observed min–max, not confidence intervals.", fontsize=10, color=SECONDARY)
    fig.text(.045, .024, "The same four seeds recur across every cell. Stubborn individuals never join or respond to sanctions. Consumption already reflects paid material costs.", fontsize=10, color=SECONDARY)
    fig.subplots_adjust(left=.222, right=.982, top=.86, bottom=.16, hspace=.30, wspace=.17)
    return save(fig, output / "consumption-and-paired-effects")


def mechanism_figure(index, output):
    fig, axes = plt.subplots(2, 2, figsize=(14.4, 10.8))
    fig.text(.045, .97, "Formation, enforcement activity and material custody", fontsize=18, weight="bold")
    fig.text(.045, .935, "Original individuals retain their cohort after entry or exit · secure custody and truthful paid audits are supplied capabilities", fontsize=10.5, color=SECONDARY)
    a, b, c, d = axes.ravel()
    scenarios = [(control, capacity, stubborn) for control, capacity in CELLS for stubborn in (0, 6)]
    labels = [f"{'Fixed' if control == 'fixed_floor' else 'Selected'} · cap {capacity} · {stubborn} stubborn"
              for control, capacity, stubborn in scenarios]
    max_events = 1.
    for j, (control, capacity, stubborn) in enumerate(scenarios):
        y = 7 - j
        for arm, marker, shift in (("charter_unmonitored", "s", .13), ("charter_enforced", "^", -.13)):
            saved = records(index, control, capacity, stubborn, arm)
            members = [e["summary"]["cohorts"]["population"]["ever_members"] / e["case"]["config"]["n_agents"] for e in saved]
            points(a, members, y, marker=marker, shift=shift, fill=arm == "charter_enforced")
            costs = [(e["summary"]["political_cost"] + e["summary"]["forfeited"]) /
                     (e["case"]["config"]["n_agents"] * e["case"]["horizon"] * e["case"]["config"]["need"]) for e in saved]
            points(c, costs, y, marker=marker, shift=shift, fill=arm == "charter_enforced")
        saved = records(index, control, capacity, stubborn, "charter_enforced")
        for key, marker, shift, color in (("actual_violations", "o", .21, INK),
                                         ("observed_violations", "s", 0., SECONDARY),
                                         ("sanction_success", "D", -.21, INK)):
            values = [e["summary"]["event_counts"].get(key, 0) if key == "sanction_success"
                      else e["summary"]["cohorts"]["population"][key] for e in saved]
            max_events = max(max_events, max(values))
            points(b, values, y, marker=marker, shift=shift, fill=key == "actual_violations", color=color)
        monitors = statistics.mean(e["summary"]["event_counts"].get("monitor_success", 0) for e in saved)
        b.text(1.01, y, f"M {monitors:g}", transform=b.get_yaxis_transform(), va="center", fontsize=8.3, color=SECONDARY)
    for ax in (a, b, c):
        ax.set_yticks(list(reversed(range(8))), labels)
        ax.set_ylim(-.6, 7.6)
        tidy(ax)
    a.set_title("A  Individuals who ever join", loc="left")
    a.set_xlim(-.035, 1.035)
    a.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    a.set_xlabel("Fraction of the original population")
    b.set_title("B  Enforcement arm: observed activity", loc="left")
    b.set_xlim(-.15 if max_events < 10 else -.8, max_events * 1.15)
    if max_events > 30:
        b.set_xscale("symlog", linthresh=1)
    b.set_xlabel("Events per episode · logarithmic above 1" if max_events > 30
                 else "Violations / paid settlements per episode")
    c.set_title("C  Political fees plus forfeited collateral", loc="left")
    c.xaxis.set_major_formatter(PercentFormatter(1, decimals=2))
    c.set_xlabel("Resource cost / population need over 256 ticks")
    c.set_xlim(left=min(-.00002, c.get_xlim()[0]))
    material = (("inventory", "Carried", INK, ""), ("cache", "Own caches", RULE, ""),
                ("claims", "Collateral / claims", BACKGROUND, "////"), ("pooled_treasury", "Pooled treasury", MUTED, "xx"))
    for j, arm in enumerate(ARMS):
        saved = [episode for key, episode in index.items() if key[3] == arm]
        if len(saved) != 32:
            raise ValueError("terminal material panel requires all 32 episodes per declared arm")
        left = 0.
        for key, name, color, hatch in material:
            values = [(e["summary"]["terminal"]["active_bond"] + e["summary"]["terminal"]["released_claim"])
                      / e["case"]["config"]["n_agents"] if key == "claims" else
                      e["summary"]["terminal"][key] / e["case"]["config"]["n_agents"] for e in saved]
            width = statistics.mean(values)
            d.barh(3 - j, width, left=left, height=.52, color=color, hatch=hatch, edgecolor=INK,
                   linewidth=.5, label=name if j == 0 else None)
            left += width
    d.set_title("D  Terminal resources by ownership component", loc="left")
    d.set_yticks([3, 2, 1, 0], [LABELS[arm] for arm in ARMS])
    d.set_xlabel("Mean terminal resource units per individual")
    d.set_ylim(-.65, 3.65)
    tidy(d)
    d.legend(loc="upper center", bbox_to_anchor=(.46, -.23), ncol=2, fontsize=9)
    a.legend(handles=[Line2D([], [], marker="s", markerfacecolor=BACKGROUND, color=INK, ls="", label="Unmonitored charter"),
                      Line2D([], [], marker="^", color=INK, ls="", label="Enforced charter")],
             loc="upper center", bbox_to_anchor=(.5, -.20), ncol=2, fontsize=9)
    b.legend(handles=[Line2D([], [], marker="o", color=INK, ls="", label="Actual violation"),
                      Line2D([], [], marker="s", markerfacecolor=BACKGROUND, color=SECONDARY, ls="", label="Paid observation"),
                      Line2D([], [], marker="D", markerfacecolor=BACKGROUND, color=INK, ls="", label="Settlement")],
             loc="upper center", bbox_to_anchor=(.48, -.20), ncol=3, fontsize=8.5)
    fig.text(.045, .063, "A–C: four seed values, means and observed ranges per cell; no confidence intervals. M gives mean successful monitor purchases. Unmonitored activity is retained in the tables.", fontsize=9.2, color=SECONDARY)
    fig.text(.045, .035, "D: equally weighted mean across all 32 episodes per arm; cells reuse the four seeds. Custody is book ownership, not redeemed consumption; no terminal liquidation occurs.", fontsize=9.2, color=SECONDARY)
    fig.subplots_adjust(left=.19, right=.92, top=.86, bottom=.18, hspace=.68, wspace=.98)
    return save(fig, output / "institutions-costs-and-custody")


def write_tables(index, summary, output):
    rows = []
    for episode in index.values():
        case, saved = episode["case"], episode["summary"]
        row = {key: case[key] for key in ("id", "control", "capacity", "stubborn_count", "seed", "arm", "horizon")}
        row.update({"need": case["config"]["need"], "individuals": case["config"]["n_agents"],
                    "political_cost": saved["political_cost"], "forfeited": saved["forfeited"],
                    "institution_activations": saved["institution_activations"],
                    "institution_free_ticks": saved["institution_free_ticks"]})
        for cohort in ("population", "eligible", "stubborn"):
            data = saved["cohorts"][cohort]
            for key in ("n", "consumption_per_tick", "late_consumption_per_tick", "consumption_need_fraction",
                        "late_consumption_need_fraction", "shortfall_per_tick",
                        "shortfall_gini", "shortfall_per_tick_p90", "shortfall_per_tick_max", "message_cost",
                        "ever_members", "terminal_members", "entry_count", "exit_count", "actual_violations", "observed_violations"):
                row[cohort + "_" + key] = data[key]
        row.update({"terminal_" + key: value for key, value in saved["terminal"].items()})
        for key in ("propose_success", "endorse_success", "refuse_success", "join_success", "exit_success",
                    "monitor_success", "monitor_failure", "sanction_success", "sanction_failure", "pay_success"):
            row[key] = saved["event_counts"].get(key, 0)
        rows.append(row)
    paths = [output / "episode-outcomes.csv", output / "paired-contrasts.json"]
    with paths[0].open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    paths[1].write_text(json.dumps(summary["contrasts"], indent=2, sort_keys=True, allow_nan=False) + "\n")
    return paths


CAPTIONS = {
    "consumption-and-paired-effects": "All 144 declared episodes retain both frozen navigation backgrounds, carrying capacities 8 and 80, and original stubborn cohorts of 0 or 6 individuals, with 24-stubborn anchors. The four active-arm comparisons use identical physical starts and cohort identities within seed. Filled circles show all-256-tick consumption and open diamonds the final 64 ticks, both divided by need. Small points are individual environmental seeds; larger symbols are arithmetic means; horizontal lines are observed four-seed minima and maxima, not confidence intervals. The lower row pairs seed outcomes before averaging. These are supplied-policy bundle contrasts, not isolated effects of formal organization, qualification tests, or evidence of deterrence against stubborn outsiders.",
    "institutions-costs-and-custody": "Panels A and C compare both charter arms in every background, capacity and original stubborn cohort. Panel B shows actual charter violations, violations measured through purchased audits, successful settlements, and mean successful monitor purchases (M) in the enforcement arm; actual and observed violation counts deduplicate witnesses. Its count scale is linear from zero to one and logarithmic above one when the observed maximum exceeds 30. In A–C, each cell has four paired seeds, shown individually with their mean and observed range. Political costs in C include fees and destroyed collateral and have already affected available resources. Panel D displays equally weighted terminal material components across the 32 episodes of each declared arm: carried inventory, personal caches, active collateral plus released claims, and treasury. Mature claims are a subset of released claims and are not counted twice. This cross-cell material summary is descriptive; its 32 episodes reuse four seeds. Assigned custody ownership does not imply physical redemption, accessible consumption, or freedom from pending collateral liability. Secure custody and truthful paid audits are supplied affordances."
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/commons-v3-institutions-development-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/commons-v3-institutions-development-v1")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("figure output must be new or empty")
    design, summary, _, index = load(source)
    output.mkdir(parents=True, exist_ok=True)
    theme()
    outputs = consumption_figure(index, output) + mechanism_figure(index, output)
    outputs += write_tables(index, summary, output)
    gallery = ["# Optional-charter development · Chromatic Field v1", "",
               "Recorded-data figures for the complete prospective development bank: 144 episodes, four environment seeds, zero model calls and zero evolutionary runs. Rendering executes no policies or physics. There is no selected winner or independent institutional qualification.", ""]
    for stem, caption in CAPTIONS.items():
        gallery.extend([f"![{stem.replace('-', ' ')}]({stem}.png)", "", caption, "",
                        f"[SVG]({stem}.svg) · [PDF]({stem}.pdf) · [PNG]({stem}.png)", ""])
    gallery.extend(["The [episode table](episode-outcomes.csv) retains every declared case and original cohort, including empty cohorts as blank values. [Paired contrasts](paired-contrasts.json) retain every seed value, mean and observed range. Current membership cannot define a causal beneficiary cohort; exits and nonjoining remain in their original groups.", "",
                    "The renderer verifies the saved summary's manifest hash and complete declared case identities. Semantic replay and checkpoint continuation are verified by the separate study runner. [manifest.json](manifest.json) binds figure inputs, renderer/helper sources, software versions, exports and tables.", "",
                    "Reproduce from the restored bank into a new output directory:", "", "```bash", 
                    ".venv/bin/python scripts/plot_commons_v3_institutions_development_v1.py --output /tmp/commons-v3-institutions-figures", "```", ""])
    (output / "README.md").write_text("\n".join(gallery))
    outputs.append(output / "README.md")
    inputs = [source / name for name in ("design.json", "summary.json", "manifest.json", "sources.json") if (source / name).exists()]
    inputs += [Path(__file__).resolve(), ROOT / "swarm_societies/visualize.py"]
    manifest = {"version": VERSION, "style": "Chromatic Field v1", "counts": design["counts"],
                "captions": CAPTIONS, "sources": {label(path): digest(path) for path in inputs},
                "outputs": {label(path): digest(path) for path in outputs},
                "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__},
                "scope": "Recorded data only; four environmental seeds reused across cells; observed ranges are not confidence intervals."}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"outputs": [label(path) for path in outputs], "manifest": label(output / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
