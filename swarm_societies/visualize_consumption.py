"""Render recorded consumption-v2 pilot evidence in the Chromatic Field style.

Build the portable evidence bundle and figures from completed fresh results::

    python -m swarm_societies.visualize_consumption --fresh runs/consumption-v2/fresh

Re-render the published bundle without run archives, simulation, or inference::

    python -m swarm_societies.visualize_consumption

This renderer deliberately requires one matched run pair. Environmental cases
describe the saved populations; they are never treated as replicated searches.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import statistics
from pathlib import Path

from .visualize import (
    BACKGROUND, INK, RULE, SECONDARY, digest, save, society_color, theme,
)
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("initial", "pair-01-fixed_institution", "pair-01-coevolution")
DISPLAY = ("Initial population", "Fixed institutions", "Coevolution")
PHASES = ("drought", "no_drought")
METRICS = (
    "welfare", "post_welfare", "pre_welfare", "utility_per_tick",
    "raw_individual_utility", "final_mean_wealth", "shortfall_per_member_tick",
    "post_shortfall_per_member_tick", "consumption_per_member_tick",
    "outward_harm_per_tick", "voluntary_contribution_per_tick", "tax_per_tick",
    "between_aid_per_tick", "within_conflict_per_tick", "infrastructure", "other_welfare",
)
CAPTIONS = {
    "outcome-tradeoffs": (
        "Equal-weight means over 108 common disturbed fresh cases per population. "
        "The one matched run pair has higher welfare and less shortfall under "
        "coevolution, but lower private utility and more outward harm than under "
        "fixed institutions. Welfare and utility axes are explicitly zoomed. "
        "Welfare equals consumption minus half the consumption shortfall, both "
        "per member-tick. With consumption need fixed at 0.85, welfare equals "
        "0.85 minus 1.5 times shortfall per member-tick; welfare and shortfall are "
        "therefore not independent endpoints. "
        "Private utility also includes terminal wealth. No independent search replication."
    ),
    "matched-drought-effects": (
        "Left: observed welfare under drought and its exact matched no-drought "
        "counterfactual, averaged over the same 108 cases. Right: twelve environment/"
        "schedule tuple means of the paired drought effect, each averaging all three "
        "focal societies and all three opponent panels. Large diamonds are the full "
        "panel means; dots are conditional environmental variation, not search-level "
        "replicates or confidence intervals. The effect contrast is coevolution minus "
        "fixed institutions. A positive contrast means less modeled drought damage."
    ),
    "society-tradeoffs": (
        "Coevolution minus fixed-institution means under drought, conditional on "
        "the single saved run pair. Each society mean averages 36 matched fresh cases. "
        "Persistent society colors identify focal societies, not search conditions. "
        "Welfare improvement is concentrated in society 0; the other two societies "
        "have small negative welfare contrasts. Private utility decreases in all "
        "three societies, while outward harm increases in societies 1 and 2. "
        "These descriptive contrasts do not isolate causal effects of institutional changes."
    ),
}


def named_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def close(actual: float, expected: float, context: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12):
        raise ValueError(f"Evidence mismatch: {context}: {actual} != {expected}")


def make_bundle(fresh: Path) -> dict:
    """Retain every scalar case outcome, stripping member logs and duplicate config."""
    summary_path = fresh / "summary.json"
    summary = json.loads(summary_path.read_text())
    sources = {named_path(summary_path): digest(summary_path)}
    populations = []
    cases = {}
    for label in LABELS:
        path = fresh / f"{label}.json"
        full = json.loads(path.read_text())
        if full["label"] != label:
            raise ValueError(f"Population label mismatch: {path}")
        sources[named_path(path)] = digest(path)
        population = {"label": label, "fingerprint": full["fingerprint"], "rows": []}
        for row in full["rows"]:
            case = row["case"]
            if case["id"] in cases and cases[case["id"]] != case:
                raise ValueError("Case IDs refer to inconsistent scenario definitions")
            cases[case["id"]] = case
            for metric in ("welfare", "post_welfare"):
                close(row[f"drought_{metric}_effect"],
                      row["drought"][metric] - row["no_drought"][metric], label)
            population["rows"].append([
                case["id"], row["opponents"], row["focal"],
                *[[row[phase][metric] for metric in METRICS] for phase in PHASES],
            ])
        matching = next(r for r in summary["results"] if r["label"] == label)
        if full["summary"] != {k: v for k, v in matching.items() if k != "label"}:
            raise ValueError(f"Per-population and campaign summaries disagree: {label}")
        populations.append(population)
    for path in (fresh.parent / "campaign.json", fresh.parent / "protected_fresh_cases.json",
                 ROOT / "docs/protocol-consumption-v2.md",
                 ROOT / "scripts/evaluate_consumption_study.py",
                 ROOT / "swarm_societies/consumption_study.py",
                 ROOT / "swarm_societies/ecology_consumption_v2.py"):
        if path.exists():
            sources[named_path(path)] = digest(path)
    return {
        "schema_version": 1, "study": "consumption-v2", "summary": summary,
        "row_columns": ["case_id", "opponents", "focal", "drought", "no_drought"],
        "metric_columns": list(METRICS), "cases": cases, "populations": populations,
        "source_sha256": sources,
        "note": "Recorded scalar outcomes only; member logs omitted. No simulated or inferred data.",
    }


def unpack(bundle: dict) -> dict:
    metrics = bundle["metric_columns"]
    return {p["label"]: [
        {"case_id": r[0], "opponents": r[1], "focal": r[2],
         "drought": dict(zip(metrics, r[3], strict=True)),
         "no_drought": dict(zip(metrics, r[4], strict=True))}
        for r in p["rows"]] for p in bundle["populations"]}


def validate(bundle: dict) -> dict:
    """Fail on missing/misaligned cases, nonfinite data, or changed plotted means."""
    if bundle["schema_version"] != 1 or bundle["study"] != "consumption-v2":
        raise ValueError("Unsupported evidence bundle")
    summary = bundle["summary"]
    if summary["replicates_per_condition"] != 1:
        raise ValueError("This pilot renderer requires exactly one matched run pair")
    if set(bundle["metric_columns"]) != set(METRICS):
        raise ValueError("Unexpected metric columns")
    rows = unpack(bundle)
    if set(rows) != set(LABELS) or len(bundle["populations"]) != len(LABELS):
        raise ValueError("Expected initial, fixed-institution, and coevolution populations")
    if len(bundle["cases"]) != 12:
        raise ValueError("Expected twelve environment/schedule tuples")
    expected = {(case_id, panel, sid) for case_id in bundle["cases"]
                for panel in ("initial", "cooperative", "selfish") for sid in range(3)}
    results = {r["label"]: r for r in summary["results"]}
    for label, group in rows.items():
        keys = {(r["case_id"], r["opponents"], r["focal"]) for r in group}
        if keys != expected or len(group) != len(expected):
            raise ValueError(f"Missing or duplicate common cases: {label}")
        if results[label]["n_cases"] != 108 or results[label]["n_rollouts"] != 216:
            raise ValueError("Unexpected case counts")
        for phase in PHASES:
            for metric in METRICS:
                values = [r[phase][metric] for r in group]
                if not all(math.isfinite(v) for v in values):
                    raise ValueError(f"Nonfinite outcome: {label}/{phase}/{metric}")
                close(statistics.mean(values), results[label][phase][metric],
                      f"{label}/{phase}/{metric}")
        for row in group:
            close(row["drought"]["pre_welfare"], row["no_drought"]["pre_welfare"],
                  "Pre-disturbance paired outcomes")
            need = bundle["cases"][row["case_id"]]["config"]["consumption_need"]
            close(need, .85, "Welfare ceiling")
            for phase in PHASES:
                outcome = row[phase]
                close(outcome["welfare"], outcome["consumption_per_member_tick"] -
                      .5 * outcome["shortfall_per_member_tick"], "Welfare definition")
        for metric in ("welfare", "post_welfare"):
            effect = statistics.mean(r["drought"][metric] - r["no_drought"][metric] for r in group)
            close(effect, results[label][f"drought_{metric}_effect"], "Matched effect")
    paired = summary["paired_run_differences"]
    if len(paired) != 1:
        raise ValueError("Expected one run-level paired contrast")
    co, fixed = (results[k] for k in LABELS[2:0:-1])
    for key, expected_value in {
        "welfare_difference": co["drought"]["welfare"] - fixed["drought"]["welfare"],
        "post_welfare_difference": co["drought"]["post_welfare"] - fixed["drought"]["post_welfare"],
        "drought_effect_difference": co["drought_welfare_effect"] - fixed["drought_welfare_effect"],
    }.items():
        close(paired[0][key], expected_value, key)
    return rows


def heading(fig, title: str, subtitle: str) -> None:
    fig.text(.07, .96, title, fontsize=18, weight="bold", va="top")
    fig.text(.07, .905, subtitle, fontsize=10, color=SECONDARY, va="top")


def condition_axis(ax) -> None:
    ax.set_yticks([2, 1, 0], DISPLAY)
    ax.set_ylim(-.5, 2.5)
    ax.tick_params(axis="y", length=0, pad=10, labelcolor=INK)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", alpha=.65)
    ax.xaxis.set_major_locator(MaxNLocator(4))


def outcomes(bundle: dict, output: Path) -> list[Path]:
    results = {r["label"]: r for r in bundle["summary"]["results"]}
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.2))
    heading(fig, "Consumption gains come with tradeoffs",
            "CONSUMPTION V2   /   One matched search pair · 108 common drought cases per population")
    panels = (
        ("welfare", "A   Collective welfare ↑", "Consumption welfare / member-tick · zoomed axis", 1., 5),
        ("shortfall_per_member_tick", "B   Consumption shortfall ↓", "Unmet consumption / 1,000 member-ticks", 1000., 3),
        ("utility_per_tick", "C   Private utility ↑", "Mean member utility / tick · zoomed axis", 1., 5),
        ("outward_harm_per_tick", "D   Outward harm ↓", "Harm imposed on other societies / tick", 1., 5),
    )
    for ax, (metric, title, xlabel, scale, digits) in zip(axes.flat, panels, strict=True):
        values = [results[label]["drought"][metric] * scale for label in LABELS]
        condition_axis(ax)
        ax.set_title(title, loc="left", fontsize=12)
        ax.set_xlabel(xlabel, fontsize=9, labelpad=10)
        if metric == "welfare":
            ax.set_xlim(.84, .8508)
            ax.axvline(.85, color=SECONDARY, linestyle="--", lw=.8)
            ax.text(.85, 2.65, "ceiling 0.85", ha="center", color=SECONDARY, fontsize=8)
        elif metric == "utility_per_tick":
            ax.set_xlim(.92, .99)
        else:
            ax.set_xlim(0, max(values) * 1.15)
        for index, (y, val) in enumerate(zip([2, 1, 0], values, strict=True)):
            ax.scatter(val, y, marker=("o", "s", "D")[index], color=INK, s=45, zorder=3)
            ax.text(1.04, y, f"{val:.{digits}f}", ha="left", va="center", fontsize=10,
                    transform=ax.get_yaxis_transform(), weight="bold" if index == 2 else "normal")
    fig.text(.07, .09, "Welfare = (consumption − 0.5 × shortfall) / (members × ticks); infrastructure has no direct welfare bonus.",
             fontsize=10, color=INK)
    fig.text(.07, .053, "Private utility = (consumption + 0.2 × terminal wealth) / episode length. Arrows mark preferred direction.",
             fontsize=9, color=SECONDARY)
    fig.text(.07, .021, "Exploratory pilot: fresh cases describe these populations; they are not independent evolutionary runs.",
             fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.195, right=.88, top=.79, bottom=.20, hspace=.70, wspace=.98)
    return save(fig, output / "outcome-tradeoffs")


def disturbance(bundle: dict, rows: dict, output: Path) -> list[Path]:
    results = {r["label"]: r for r in bundle["summary"]["results"]}
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 6.0))
    heading(fig, "An exact counterfactual for drought damage",
            "Same programs, initial conditions and exogenous draws · only the regeneration shock is disabled")
    left, right = axes
    for ax in axes:
        condition_axis(ax)
    left.set_title("A   Overall welfare with and without drought", loc="left", fontsize=11)
    for y, label in zip([2, 1, 0], LABELS, strict=True):
        lo, hi = (results[label][phase]["welfare"] for phase in PHASES)
        left.plot([lo, hi], [y, y], color=RULE, linewidth=2.5)
        left.scatter(hi, y, facecolor=BACKGROUND, edgecolor=INK, s=60, zorder=3)
        left.scatter(lo, y, color=INK, s=45, zorder=4)
    left.set_xlim(.84, .851)
    left.set_xlabel("Consumption welfare / member-tick · zoomed axis", fontsize=9)
    left.legend(handles=[Line2D([], [], marker="o", linestyle="", color=INK, label="Drought"),
                         Line2D([], [], marker="o", linestyle="", markerfacecolor=BACKGROUND,
                                color=INK, label="No drought")], loc="lower left", bbox_to_anchor=(-.02, -.39), ncol=2)
    right.set_title("B   Drought effect by environment/schedule tuple", loc="left", fontsize=11)
    case_ids = sorted(bundle["cases"])
    for y, label in zip([2, 1, 0], LABELS, strict=True):
        effects = [statistics.mean(r["drought"]["welfare"] - r["no_drought"]["welfare"]
                                   for r in rows[label] if r["case_id"] == case_id) * 1000
                   for case_id in case_ids]
        offsets = np.linspace(-.20, .20, len(case_ids))
        right.scatter(effects, y + offsets, s=23, facecolor=BACKGROUND, edgecolor=SECONDARY,
                      linewidth=.8, zorder=3)
        mean = results[label]["drought_welfare_effect"] * 1000
        right.scatter(mean, y, marker="D", s=55, color=INK, zorder=4)
        right.text(1.03, y, f"{mean:+.3f}", ha="left", va="center", fontsize=10,
                   transform=right.get_yaxis_transform())
    right.axvline(0, color=SECONDARY, linestyle="--", linewidth=.8)
    right.set_xlim(right.get_xlim()[0], .7)
    right.set_xlabel("Drought − no drought welfare × 1,000 · less negative is better", fontsize=9)
    right.legend(handles=[Line2D([], [], marker="o", linestyle="", markerfacecolor=BACKGROUND,
                                 color=SECONDARY, label="12 environment means"),
                          Line2D([], [], marker="D", linestyle="", color=INK, label="Panel mean")],
                 loc="lower left", bbox_to_anchor=(-.02, -.39), ncol=1)
    effect = bundle["summary"]["paired_run_differences"][0]["drought_effect_difference"]
    fig.text(.07, .15, f"Coevolution − fixed-institution drought-effect contrast: {effect:+.6f} welfare / member-tick.",
             fontsize=11, weight="bold")
    fig.text(.07, .095, "Each environment mean groups 3 focal societies × 3 opponent panels. Dots show conditional variation, not confidence intervals.",
             fontsize=9, color=SECONDARY)
    fig.text(.07, .055, "One matched search pair; a less negative drought effect does not establish disturbance recognition or general adaptive learning.",
             fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.185, right=.90, top=.76, bottom=.39, wspace=.98)
    return save(fig, output / "matched-drought-effects")


def society_contrasts(rows: dict, output: Path) -> list[Path]:
    fig, axes = plt.subplots(1, 4, figsize=(13.3, 5.7))
    heading(fig, "The aggregate gain is uneven across societies",
            "Coevolution − fixed institutions · drought cases · 36 matched cases per focal society · one run pair")
    panels = (
        ("welfare", "Collective welfare", "Welfare difference × 1,000", 1000.),
        ("utility_per_tick", "Private utility", "Utility / tick difference", 1.),
        ("outward_harm_per_tick", "Outward harm", "Harm / tick difference", 1.),
        ("tax_per_tick", "Compulsory pooling", "Tax / tick difference", 1.),
    )
    for ax, (metric, title, xlabel, scale) in zip(axes, panels, strict=True):
        values = []
        for sid in range(3):
            avg = [statistics.mean(r["drought"][metric] for r in rows[label] if r["focal"] == sid)
                   for label in (LABELS[2], LABELS[1])]
            difference = (avg[0] - avg[1]) * scale
            values.append(difference)
            ax.plot([0, difference], [2-sid, 2-sid], color=society_color(sid), alpha=.4, lw=2.5)
            ax.scatter(difference, 2-sid, color=society_color(sid), s=50, zorder=4)
            ax.text(.98, 2-sid+.30, f"{difference:+.3f}" if difference else "0.000", ha="right",
                    color=society_color(sid), fontsize=10, transform=ax.get_yaxis_transform())
        spread = max(max(values)-min(values), max(abs(v) for v in values), .01)
        ax.set_xlim(min(min(values), 0) - spread*.15, max(max(values), 0) + spread*.20)
        ax.axvline(0, color=SECONDARY, lw=.8, linestyle="--")
        ax.set_ylim(-.5, 2.7)
        ax.set_yticks([2, 1, 0], ["Society 0", "Society 1", "Society 2"] if ax is axes[0] else [])
        ax.tick_params(axis="y", length=0, pad=10)
        ax.spines["left"].set_visible(False)
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_xlabel(xlabel, fontsize=9, labelpad=12)
        ax.xaxis.set_major_locator(MaxNLocator(4))
        ax.grid(axis="x", alpha=.65)
    for label, sid in zip(axes[0].get_yticklabels(), range(3), strict=True):
        label.set_color(society_color(sid))
    fig.text(.07, .19, "Society 0 accounts for the net welfare advantage. Societies 1 and 2 have slightly lower welfare and greater outward harm.",
             fontsize=10)
    fig.text(.07, .13, "Tax is compulsory pooling, separate from voluntary contribution. A lower tax transfer is not itself a welfare improvement.",
             fontsize=9, color=SECONDARY)
    fig.text(.07, .075, "Recorded population contrasts do not isolate the effects of individual institutional edits; targeted counterfactuals are still needed.",
             fontsize=9, color=SECONDARY)
    fig.subplots_adjust(left=.135, right=.965, top=.77, bottom=.34, wspace=.5)
    return save(fig, output / "society-tradeoffs")


def tables(bundle: dict, rows: dict, output: Path) -> list[Path]:
    results_path = output / "results.csv"
    with results_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["population", "phase", "n_cases", *METRICS])
        writer.writeheader()
        for result in bundle["summary"]["results"]:
            for phase in PHASES:
                writer.writerow({"population": result["label"], "phase": phase,
                                 "n_cases": result["n_cases"], **result[phase]})
    stratified = output / "society-opponent-means.csv"
    with stratified.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["population", "focal", "opponents", "phase", "n_cases", *METRICS])
        writer.writeheader()
        for label in LABELS:
            for sid in range(3):
                for opponents in ("initial", "cooperative", "selfish"):
                    group = [r for r in rows[label] if r["focal"] == sid and r["opponents"] == opponents]
                    for phase in PHASES:
                        writer.writerow({"population": label, "focal": sid, "opponents": opponents,
                                         "phase": phase, "n_cases": len(group),
                                         **{k: statistics.mean(r[phase][k] for r in group) for k in METRICS}})
    return [results_path, stratified]


def render(bundle: dict, output: Path) -> dict:
    rows = validate(bundle)
    output.mkdir(parents=True, exist_ok=True)
    data_path = output / "plot-data.json"
    data_path.write_text(json.dumps(bundle, sort_keys=True, separators=(",", ":")) + "\n")
    theme()
    paths = [data_path]
    paths += outcomes(bundle, output)
    paths += disturbance(bundle, rows, output)
    paths += society_contrasts(rows, output)
    paths += tables(bundle, rows, output)
    manifest = {
        "schema_version": 1, "style": "Chromatic Field v1", "study": "consumption-v2",
        "replication_unit": "Independent evolutionary run", "n_independent_run_pairs": 1,
        "n_common_cases_per_population": 108, "n_rollouts_per_population": 216,
        "interpretation": bundle["summary"]["interpretation"],
        "source_sha256": bundle["source_sha256"],
        "render_source_sha256": {named_path(Path(__file__)): digest(Path(__file__)),
                                 "swarm_societies/visualize.py": digest(ROOT / "swarm_societies/visualize.py")},
        "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "command": ".venv/bin/python -m swarm_societies.visualize_consumption --data figures/consumption-v2/plot-data.json --output figures/consumption-v2",
        "captions": CAPTIONS,
        "files": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in paths},
        "validation": "All 324 case pairs checked against published summaries; matched case identities, finite outcomes, pre-shock equality, welfare definitions and run contrasts verified.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--fresh", type=Path, help="Completed fresh-results directory; build portable evidence bundle")
    inputs.add_argument("--data", type=Path, default=Path("figures/consumption-v2/plot-data.json"),
                        help="Portable recorded-evidence bundle")
    parser.add_argument("--output", type=Path, default=Path("figures/consumption-v2"))
    args = parser.parse_args()
    bundle = make_bundle(args.fresh) if args.fresh else json.loads(args.data.read_text())
    manifest = render(bundle, args.output)
    print(json.dumps({"output": str(args.output), "files": len(manifest["files"]),
                      "validation": manifest["validation"]}, indent=2))


if __name__ == "__main__":
    main()
