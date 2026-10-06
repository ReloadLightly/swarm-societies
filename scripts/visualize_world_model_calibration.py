#!/usr/bin/env python3
"""Render recorded world-model calibration diagnostics in Chromatic Field v1.

Prior-predictive calibration, ecological task coverage, and approximation to a
batch posterior are separate questions. No renderer function trains a learner
or generates experimental observations.
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
                                      STYLE, digest, save, theme)
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.lines import Line2D
import numpy as np

RENDERER_VERSION = "world-model-calibration-v1-figures-v1"
PARAMETERS = ("r", "b", "g")
PARAMETER_LABELS = {
    "r": "Base renewal", "b": "Own infrastructure return",
    "g": "External infrastructure spillover",
}
MARKERS = ("o", "s", "^", "D", "v", "P", "X")
LINE_STYLES = ("-", "--", ":", "-.")
METHODS = ("prior", "published", "higher_compute", "reference")
LEARNERS = ("published", "higher_compute")
METHOD_LABELS = {"prior": "Frozen prior", "published": "Published SMC · 1,024 / 4",
                 "higher_compute": "Higher compute · 4,096 / 8",
                 "reference": "Batch MCMC reference"}
COHORTS = ("prior_predictive", "ecological")
COHORT_LABELS = {"prior_predictive": "Prior-predictive control",
                 "ecological": "Ecological task panel"}
QUANTITIES = (*PARAMETERS, "log_likelihood")
BOOTSTRAP_SEED = 8307
BOOTSTRAP_DRAWS = 2000


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
    fig.text(0.065, 0.97, title, fontsize=19, weight="bold", va="top")
    fig.text(0.065, 0.91, subtitle, fontsize=10.5, color=SECONDARY,
             va="top")


def method_style(index: int) -> dict:
    """Method identity uses shape and dash, never society identity colors."""
    if index < 0 or index >= len(MARKERS):
        raise ValueError("Declare distinct method markers before adding methods")
    return {"color": INK, "marker": MARKERS[index],
            "linestyle": LINE_STYLES[index % len(LINE_STYLES)],
            "markerfacecolor": BACKGROUND if index % 2 else INK,
            "markeredgecolor": INK, "linewidth": 1.35,
            "markersize": 5.5}


def method_legend(fig, methods=METHODS, *, bottom=0.035, columns=None):
    handles = [Line2D([0], [0], label=METHOD_LABELS[method],
                      **method_style(METHODS.index(method))) for method in methods]
    fig.legend(handles=handles, loc="lower center",
               bbox_to_anchor=(0.5, bottom),
               ncol=columns or min(3, len(handles)), fontsize=9.5,
               handlelength=2.6, columnspacing=2.1)


def format_axes(ax, *, grid_axis="y"):
    ax.grid(axis=grid_axis, alpha=0.55)
    ax.set_axisbelow(True)


def nominal_coverage(ax, *, horizontal=False):
    if horizontal:
        ax.axhline(0.9, color=SECONDARY, linewidth=1.0, linestyle="--")
    else:
        ax.axvline(0.9, color=SECONDARY, linewidth=1.0, linestyle="--")


def reference_status_note(ax, *, passed: int, total: int):
    """Reference failures remain explicit, even when agreement is undefined."""
    if not 0 <= passed <= total:
        raise ValueError("Invalid batch reference diagnostic counts")
    ax.text(0.0, 1.08,
            f"Reference checks: {passed}/{total} passed; {total - passed} failed",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=9,
            color=INK if passed < total else SECONDARY,
            bbox={"facecolor": MUTED, "edgecolor": RULE, "pad": 4})


def save_figure(fig, output: Path, name: str) -> list[Path]:
    return save(fig, output / name)


def select(rows, **criteria):
    return [row for row in rows if all(str(row[key]) == str(value)
                                      for key, value in criteria.items())]


def bootstrap(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"mean": None, "ci95": [None, None], "n": 0}
    if not np.isfinite(values).all():
        raise ValueError("Cannot summarize non-finite case outcomes")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = rng.integers(0, len(values), size=(BOOTSTRAP_DRAWS, len(values)))
    low, high = np.quantile(values[samples].mean(axis=1), [.025, .975])
    return {"mean": float(values.mean()), "ci95": [float(low), float(high)], "n": len(values)}


def coverage_interval(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"mean": None, "ci95": [None, None], "n": 0}
    if not np.isin(values, [0., 1.]).all():
        raise ValueError("Coverage requires one binary indicator per case")
    n, fraction, z = len(values), float(values.mean()), 1.959963984540054
    denominator = 1 + z*z/n
    center = (fraction + z*z/(2*n)) / denominator
    radius = z*np.sqrt(fraction*(1-fraction)/n + z*z/(4*n*n)) / denominator
    return {"mean": fraction, "ci95": [max(0., float(center-radius)),
                                       min(1., float(center+radius))], "n": n}


def assert_estimate(recorded, derived, label):
    if recorded["n"] != derived["n"]:
        raise ValueError(f"Summary count differs from recorded cases: {label}")
    if not derived["n"]:
        if recorded["mean"] is not None or recorded["ci95"] != [None, None]:
            raise ValueError(f"Empty summary contains an estimate: {label}")
    elif not np.allclose([recorded["mean"], *recorded["ci95"]],
                        [derived["mean"], *derived["ci95"]], rtol=1e-10, atol=1e-12):
        raise ValueError(f"Summary differs from recorded cases: {label}")


def require_grid(rows, keys, expected, label):
    actual = Counter(tuple(str(row[key]) for key in keys) for row in rows)
    if set(actual) != expected or any(count != 1 for count in actual.values()):
        raise ValueError(f"Incomplete or duplicate {label} evidence grid")


def load_study(source):
    design = json.loads((source / "design.json").read_text())
    if digest(source / "design.json") != (source / "design.sha256").read_text().strip():
        raise ValueError("Calibration design checksum mismatch")
    completion = json.loads((source / "completion.json").read_text())
    names = ("parameters.csv", "cdf.csv", "agreement.csv", "diagnostics.json", "summary.json", "design.json")
    for name in names:
        if digest(source / name) != completion["artifacts"][name]:
            raise ValueError(f"Recorded calibration artifact hash mismatch: {name}")
    if tuple(design["methods"]) != METHODS:
        raise ValueError("Declare visual encodings before adding calibration methods")
    for method, expected in (("published", (1024, 4)), ("higher_compute", (4096, 8))):
        settings = design["smc_settings"][method]
        if (settings["n_particles"], settings["rejuvenation_steps"]) != expected:
            raise ValueError("Update visual method labels before changing numerical settings")
    parameters, cdf, agreement = (read_csv(source / name) for name in names[:3])
    diagnostics = json.loads((source / "diagnostics.json").read_text())
    summary = json.loads((source / "summary.json").read_text())
    cases = {case["case_id"]: case for case in design["cases"]}
    if len(cases) != len(design["cases"]):
        raise ValueError("Duplicate independent case identities")
    require_grid(parameters, ("case_id", "method", "parameter"),
                 {(case, method, p) for case in cases for method in METHODS for p in PARAMETERS}, "parameter")
    require_grid(cdf, ("case_id", "method", "quantity"),
                 {(case, method, q) for case in cases for method in METHODS for q in QUANTITIES}, "CDF")
    require_grid(agreement, ("case_id", "method", "parameter"),
                 {(case, method, p) for case in cases for method in METHODS[:-1] for p in PARAMETERS}, "agreement")
    require_grid(diagnostics, ("case_id", "method"),
                 {(case, method) for case in cases for method in METHODS}, "diagnostic")
    reference_passes = {row["case_id"]: row["status"] == "passed"
                        for row in diagnostics if row["method"] == "reference"}
    for table in (parameters, cdf, agreement, diagnostics):
        for row in table:
            if row["cohort"] != cases[row["case_id"]]["cohort"]:
                raise ValueError("Recorded cohort does not match frozen case")
    for row in parameters:
        for key in ("truth", "mean", "sd", "q05", "q95", "width90", "covered90", "absolute_error", "cdf"):
            finite(row[key], key)
        low, high, truth = (float(row[k]) for k in ("q05", "q95", "truth"))
        if high < low or int(row["covered90"]) != int(low <= truth <= high):
            raise ValueError("Invalid recorded credible interval coverage")
        if not np.isclose(high - low, float(row["width90"]), rtol=1e-11, atol=1e-12):
            raise ValueError("Invalid recorded credible interval width")
    for row in cdf:
        if not 0 <= finite(row["cdf"], "cdf") <= 1:
            raise ValueError("Recorded posterior CDF outside [0, 1]")
    for row in agreement:
        if int(row["reference_passed"]) != int(reference_passes[row["case_id"]]):
            raise ValueError("Reference qualification differs between tables")
        for key in ("mean_gap_reference_sd", "width_ratio", "endpoint_gap_prior_width"):
            if finite(row[key], key) < 0:
                raise ValueError("Negative posterior approximation discrepancy")
        if row["reference_mean_mcse_sd"] in (None, ""):
            if int(row["reference_passed"]):
                raise ValueError("Qualified reference lacks Monte Carlo uncertainty")
        elif finite(row["reference_mean_mcse_sd"], "reference_mean_mcse_sd") < 0:
            raise ValueError("Negative reference Monte Carlo uncertainty")
    for row in diagnostics:
        if finite(row["fit_cpu_seconds"], "fit_cpu_seconds") <= 0:
            raise ValueError("Nonpositive measured CPU time")
    for row in summary["all_case_summaries"]:
        criteria = {key: row[key] for key in ("cohort", "method", "parameter")}
        raw = select(parameters, **criteria)
        matched = select(agreement, **criteria, reference_passed=1)
        assert_estimate(row["covered90"], coverage_interval([finite(r["covered90"], "covered90") for r in raw]), f"{criteria}/covered90")
        for key in ("width90", "absolute_error"):
            assert_estimate(row[key], bootstrap([finite(r[key], key) for r in raw]), f"{criteria}/{key}")
        for key in ("mean_gap_reference_sd", "width_ratio", "endpoint_gap_prior_width"):
            assert_estimate(row[key], bootstrap([finite(r[key], key) for r in matched]), f"{criteria}/{key}")
    for row in summary["compute"]:
        raw = select(diagnostics, cohort=row["cohort"], method=row["method"])
        assert_estimate(row, bootstrap([finite(r["fit_cpu_seconds"], "fit_cpu_seconds") for r in raw]), "compute")
    for row in summary["paired_higher_minus_published"]:
        subsets = {method: {r["case_id"]: r for r in select(agreement, cohort=row["cohort"],
                    parameter=row["parameter"], method=method, reference_passed=1)} for method in LEARNERS}
        paired_cases = sorted(subsets["published"])
        if set(paired_cases) != set(subsets["higher_compute"]):
            raise ValueError("Methods do not share the same qualified case subset")
        for key in ("mean_gap_reference_sd", "endpoint_gap_prior_width"):
            estimate = bootstrap([float(subsets["higher_compute"][case][key])
                                  - float(subsets["published"][case][key]) for case in paired_cases])
            assert_estimate(row[key], estimate, f"paired/{row['cohort']}/{row['parameter']}/{key}")
    for cohort in COHORTS:
        count = sum(case["cohort"] == cohort for case in cases.values())
        failed = sum(not passed for case_id, passed in reference_passes.items()
                     if cases[case_id]["cohort"] == cohort)
        if summary["cohort_counts"][cohort] != count or summary["reference_failures"][cohort] != failed:
            raise ValueError("Summary reference denominator differs from raw cases")
    return {"design": design, "completion": completion, "parameters": parameters,
            "cdf": cdf, "agreement": agreement, "diagnostics": diagnostics,
            "summary": summary, "cases": cases, "reference_passes": reference_passes}


def status(study, cohort):
    total = study["summary"]["cohort_counts"][cohort]
    failed = study["summary"]["reference_failures"][cohort]
    return total - failed, total


def status_text(study, cohort):
    passed, total = status(study, cohort)
    return f"{passed}/{total} references pass; {total - passed} fail"


def summary_row(study, cohort, method, parameter):
    rows = select(study["summary"]["all_case_summaries"], cohort=cohort, method=method, parameter=parameter)
    if len(rows) != 1:
        raise ValueError("Missing or repeated summary cell")
    return rows[0]


def error_point(ax, estimate, y, method):
    if not estimate["n"]:
        return
    style = method_style(METHODS.index(method))
    style.pop("linestyle")
    mean, (low, high) = estimate["mean"], estimate["ci95"]
    ax.errorbar(mean, y, xerr=[[max(0, mean-low)], [max(0, high-mean)]],
                capsize=0, elinewidth=1.2, zorder=4, **style)


def coverage_figure(study, output):
    fig, axes = plt.subplots(2, 3, figsize=(14.8, 8.7), squeeze=False)
    heading(fig, "Do credible intervals cover the hidden laws?",
            "Raw 90% parameter coverage on every case · 95% Wilson intervals · widths in each coefficient’s own units")
    for i, cohort in enumerate(COHORTS):
        for j, parameter in enumerate(PARAMETERS):
            ax = axes[i, j]
            for k, method in enumerate(METHODS):
                row = summary_row(study, cohort, method, parameter)
                error_point(ax, row["covered90"], k, method)
                ax.text(1.38, k, f"{row['width90']['mean']:.3f}", ha="right", va="center", fontsize=9)
            nominal_coverage(ax)
            ax.axvline(1.07, color=RULE, linewidth=.7)
            ax.text(1.38, -.65, "Mean width", ha="right", fontsize=8.5, color=SECONDARY)
            ax.set_xlim(0, 1.44)
            ax.set_ylim(3.55, -.85)
            ax.set_xticks([0, .5, .9, 1.0])
            ax.set_xticklabels(["0", "0.5", "0.9", "1"])
            ax.set_yticks(range(len(METHODS)))
            ax.set_yticklabels([METHOD_LABELS[m].replace(" · ", "\n") for m in METHODS] if j == 0 else [])
            ax.tick_params(axis="y", length=0, labelsize=8.5)
            ax.set_xlabel("Fraction of truths covered")
            ax.set_title(f"{parameter} / {PARAMETER_LABELS[parameter]}", loc="left", fontsize=10.5)
            format_axes(ax, grid_axis="x")
            if j == 0:
                ax.text(0, 1.38, f"{COHORT_LABELS[cohort]} · n={status(study, cohort)[1]}",
                        transform=ax.transAxes, fontsize=10, weight="bold")
                ax.text(0, 1.24, status_text(study, cohort), transform=ax.transAxes,
                        fontsize=9, color=SECONDARY)
    fig.text(.065, .115, "Reference failures remain in raw coverage and width. The dashed line marks nominal 90%; Wilson intervals use independent cases.",
             fontsize=9.5, color=SECONDARY)
    fig.text(.065, .068, "Only the prior-predictive panel samples laws from the learner’s full prior. Ecological coverage is task-specific and conditional on recorded features.",
             fontsize=9.3, color=SECONDARY)
    fig.subplots_adjust(left=.19, right=.975, top=.765, bottom=.205, hspace=.89, wspace=.25)
    return save_figure(fig, output, "parameter-coverage")


def agreement_figure(study, output):
    metrics = (("mean_gap_reference_sd", "Absolute mean gap / reference SD", 0),
               ("width_ratio", "90% interval width / reference width", 1),
               ("endpoint_gap_prior_width", "Maximum interval endpoint gap / prior width", 0))
    fig, axes = plt.subplots(2, 3, figsize=(14.8, 9.0), squeeze=False)
    heading(fig, "How closely does each particle posterior match the reference?",
            "Only cases whose independent batch reference passes declared checks · the same cases are paired across particle settings")
    mcse_notes = []
    for i, cohort in enumerate(COHORTS):
        for j, (key, label, target) in enumerate(metrics):
            ax = axes[i, j]
            for pidx, parameter in enumerate(PARAMETERS):
                paired_rows = {method: {r["case_id"]: r for r in select(study["agreement"],
                               cohort=cohort, method=method, parameter=parameter,
                               reference_passed=1)} for method in LEARNERS}
                paired_cases = sorted(paired_rows["published"])
                for case_id, jitter in zip(paired_cases, np.linspace(-.07, .07, len(paired_cases))):
                    ax.plot([float(paired_rows[method][case_id][key]) for method in LEARNERS],
                            [pidx-.13+jitter, pidx+.13+jitter], color=RULE,
                            linewidth=.45, alpha=.45, zorder=1)
                for offset, method in zip((-.13, .13), LEARNERS):
                    rows = sorted(select(study["agreement"], cohort=cohort, method=method,
                                         parameter=parameter, reference_passed=1), key=lambda r: r["case_id"])
                    raw = [finite(row[key], key) for row in rows]
                    if raw:
                        jitter = np.linspace(-.07, .07, len(raw))
                        style = method_style(METHODS.index(method))
                        ax.scatter(raw, pidx + offset + jitter, marker=style["marker"],
                                   color=SECONDARY, s=10, alpha=.23, linewidths=0)
                    error_point(ax, summary_row(study, cohort, method, parameter)[key], pidx+offset, method)
                if key == "mean_gap_reference_sd":
                    qualified = select(study["agreement"], cohort=cohort, method="published",
                                       parameter=parameter, reference_passed=1)
                    if qualified:
                        noise = np.mean([float(row["reference_mean_mcse_sd"]) for row in qualified])
                        ax.plot(noise, pidx, "|", color=SECONDARY, markersize=17, markeredgewidth=1.4)
            ax.axvline(target, color=RULE, linestyle="--", linewidth=1)
            ax.set_yticks(range(len(PARAMETERS)))
            ax.set_yticklabels(PARAMETERS if j == 0 else [])
            ax.set_ylim(2.5, -.55)
            ax.set_xlabel(label, fontsize=9.5)
            ax.set_title(("Posterior mean", "Credible interval width", "Credible interval endpoints")[j],
                         loc="left", fontsize=11)
            format_axes(ax, grid_axis="x")
            if key != "width_ratio":
                ax.set_xlim(left=0)
            if not status(study, cohort)[0]:
                ax.text(.5, .5, "No qualified references", transform=ax.transAxes,
                        ha="center", color=SECONDARY)
            if j == 0:
                ax.text(0, 1.38, COHORT_LABELS[cohort], transform=ax.transAxes,
                        fontsize=10, weight="bold")
                ax.text(0, 1.24, status_text(study, cohort), transform=ax.transAxes,
                        fontsize=9, color=SECONDARY)
        rows = select(study["agreement"], cohort=cohort, method="published", reference_passed=1)
        if rows:
            mcse_notes.append(f"{COHORT_LABELS[cohort]} {np.mean([float(r['reference_mean_mcse_sd']) for r in rows]):.3f}")
    fig.text(.065, .147, "Small linked marks: paired cases. Large markers and lines: means and 95% case bootstrap intervals. Lower gaps and width ratios near 1 indicate agreement.",
             fontsize=9.2, color=SECONDARY)
    fig.text(.065, .105, "Vertical ticks in mean panels: reference MCSE / posterior SD (mean across cases). " + "; ".join(mcse_notes) + ".",
             fontsize=8.9, color=SECONDARY)
    method_legend(fig, LEARNERS, bottom=.018, columns=2)
    fig.subplots_adjust(left=.09, right=.975, top=.77, bottom=.25, hspace=.85, wspace=.26)
    return save_figure(fig, output, "posterior-agreement")


def compute_case_rows(study):
    rows = []
    for cohort in COHORTS:
        for method in LEARNERS:
            for diagnostic in select(study["diagnostics"], cohort=cohort, method=method):
                case_id = diagnostic["case_id"]
                if not study["reference_passes"][case_id]:
                    continue
                match = select(study["agreement"], case_id=case_id, method=method)
                rows.append({"case_id": case_id, "cohort": cohort, "method": method,
                             "fit_cpu_seconds": float(diagnostic["fit_cpu_seconds"]),
                             "mean_gap_reference_sd": float(np.mean([float(r["mean_gap_reference_sd"]) for r in match]))})
    return rows


def compute_figure(study, output):
    fig, axes = plt.subplots(2, 2, figsize=(13.6, 9.6), squeeze=False)
    heading(fig, "How much computation buys closer posterior agreement?",
            "Measured CPU time for one dataset · pooled ecological histories · no model-generation calls or evolutionary search")
    paired = compute_case_rows(study)
    for j, cohort in enumerate(COHORTS):
        ax = axes[0, j]
        for index, method in enumerate(METHODS):
            estimate = next(row for row in study["summary"]["compute"]
                            if row["cohort"] == cohort and row["method"] == method)
            error_point(ax, estimate, index, method)
        ax.set_yticks(range(len(METHODS)))
        ax.set_yticklabels([METHOD_LABELS[m].replace(" · ", "\n") for m in METHODS], fontsize=8.5)
        ax.set_ylim(3.6, -.6)
        ax.set_xscale("log")
        ax.set_xlabel("Fitting CPU seconds · all cases, including failed references", fontsize=9.5)
        ax.set_title(f"{COHORT_LABELS[cohort]} · n={status(study, cohort)[1]}", loc="left", fontsize=11)
        format_axes(ax, grid_axis="x")
        ax = axes[1, j]
        for method in LEARNERS:
            rows = select(paired, cohort=cohort, method=method)
            if not rows:
                continue
            cpu = bootstrap([r["fit_cpu_seconds"] for r in rows])
            gap = bootstrap([r["mean_gap_reference_sd"] for r in rows])
            style = method_style(METHODS.index(method))
            ax.scatter([r["fit_cpu_seconds"] for r in rows], [r["mean_gap_reference_sd"] for r in rows],
                       marker=style["marker"], color=SECONDARY, alpha=.22, s=12, linewidths=0)
            style.pop("linestyle")
            ax.errorbar(cpu["mean"], gap["mean"],
                        xerr=[[cpu["mean"] - cpu["ci95"][0]], [cpu["ci95"][1] - cpu["mean"]]],
                        yerr=[[gap["mean"] - gap["ci95"][0]], [gap["ci95"][1] - gap["mean"]]],
                        capsize=0, elinewidth=1.2, **style)
        reference_status_note(ax, passed=status(study, cohort)[0], total=status(study, cohort)[1])
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.set_xlabel("Fitting CPU seconds · qualified-reference cases", fontsize=9.5)
        ax.set_ylabel("Mean marginal mean gap / reference SD", fontsize=9)
        format_axes(ax)
    fig.text(.065, .135, "Top: all-case cost, including reference retries. Bottom: individual cases and means on the shared qualified-reference subset; each case averages r, b and g.",
             fontsize=9.1, color=SECONDARY)
    fig.text(.065, .092, "Timing depends on the machine. Batch references have numerical error; their agreement is a computation diagnostic, not an exact-truth guarantee.",
             fontsize=9.1, color=SECONDARY)
    method_legend(fig, LEARNERS, bottom=.018, columns=2)
    fig.subplots_adjust(left=.18, right=.975, top=.805, bottom=.235, hspace=.62, wspace=.47)
    return save_figure(fig, output, "compute-accuracy")


def ecdf_deviation(values):
    """Exact piecewise-linear F_n(u)-u, preserving jumps at PIT endpoints."""
    values = np.sort(np.asarray(values, dtype=float))
    count = len(values)
    if not count:
        raise ValueError("Cannot render an empty posterior CDF diagnostic")
    x = np.concatenate(([0.], np.repeat(values, 2), [1.]))
    before = np.arange(count) / count
    after = np.arange(1, count + 1) / count
    y = np.concatenate(([0.], np.column_stack((before, after)).ravel(), [1.]))
    return x, y - x


def cdf_figure(study, output):
    fig, axes = plt.subplots(2, 4, figsize=(15.2, 9.3), squeeze=False)
    heading(fig, "Posterior CDF diagnostics separate calibration from task behavior",
            "CDF at simulator truth · one value per independent case · all cases retained, including failed reference outcomes")
    for i, cohort in enumerate(COHORTS):
        n = status(study, cohort)[1]
        epsilon = np.sqrt(np.log(2/.05) / (2*n))
        for j, quantity in enumerate(QUANTITIES):
            ax = axes[i, j]
            if cohort == "prior_predictive":
                x = np.linspace(0, 1, 101)
                ax.fill_between(x, np.maximum(-epsilon, -x), np.minimum(epsilon, 1-x),
                                color=MUTED, zorder=0)
            ax.axhline(0, color=RULE, linewidth=.8)
            for method in METHODS:
                values = [float(row["cdf"]) for row in select(study["cdf"], cohort=cohort, method=method, quantity=quantity)]
                x, y = ecdf_deviation(values)
                style = method_style(METHODS.index(method))
                style.update(markersize=3.0, linewidth=1.25, alpha=.85,
                             markevery=np.linspace(1, len(x)-2, 5, dtype=int).tolist())
                ax.plot(x, y, **style)
            ax.set_xlim(0, 1)
            ax.set_xticks([0, .5, 1])
            ax.set_xlabel("Posterior CDF at truth", fontsize=9.5)
            ax.set_title(quantity if quantity != "log_likelihood" else "Log likelihood", loc="left")
            format_axes(ax)
            if j == 0:
                ax.set_ylabel("Empirical CDF − uniform CDF")
                ax.text(0, 1.38, f"{COHORT_LABELS[cohort]} · n={n}", transform=ax.transAxes,
                        fontsize=10, weight="bold")
                ax.text(0, 1.24, status_text(study, cohort), transform=ax.transAxes,
                        fontsize=8.7, color=SECONDARY)
        for ax in axes[i]:
            # The frozen prior likelihood CDF is often near one. Preserve its
            # full range without compressing informative coefficient checks.
            maximum = max(abs(v) for v in ax.get_ylim())
            if cohort == "prior_predictive":
                maximum = max(maximum, epsilon * 1.15)
            ax.set_ylim(-maximum, maximum)
    fig.text(.065, .157, "Top gray band: 95% DKW simultaneous bound for one independent-case ECDF under uniform calibration; not a familywise test across panels or methods.",
             fontsize=9.1, color=SECONDARY)
    fig.text(.065, .117, "Bottom: descriptive task diagnostics; ecological feature generation is outside the conditional likelihood, so uniformity is not the asserted null.",
             fontsize=9.1, color=SECONDARY)
    fig.text(.065, .077, "A frozen prior can pass marginal prior-predictive checks without learning. The data-dependent likelihood statistic provides a complementary check.",
             fontsize=9.1, color=SECONDARY)
    method_legend(fig, bottom=.0, columns=4)
    fig.subplots_adjust(left=.085, right=.975, top=.77, bottom=.255, hspace=.84, wspace=.29)
    return save_figure(fig, output, "cdf-diagnostics")


def add_estimate(row, key, estimate):
    row[key] = estimate["mean"]
    row[key + "_lo95"], row[key + "_hi95"] = estimate["ci95"]


def write_table(output, name, rows):
    path = output / name
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def export_tables(study, output):
    coverage, agreement, compute, cdf, contrasts = [], [], [], [], []
    for source_row in study["summary"]["all_case_summaries"]:
        base = {key: source_row[key] for key in ("cohort", "method", "parameter")}
        passed, total = status(study, base["cohort"])
        row = {**base, "unit": "independent_case", "n_all_cases": total,
               "reference_passed": passed, "reference_failed": total-passed}
        for key in ("covered90", "width90", "absolute_error"):
            add_estimate(row, key, source_row[key])
        coverage.append(row)
        if base["method"] != "reference":
            row = {**base, "unit": "independent_case", "n_qualified_cases": passed,
                   "n_all_cases": total, "reference_failed": total-passed}
            for key in ("mean_gap_reference_sd", "width_ratio", "endpoint_gap_prior_width"):
                add_estimate(row, key, source_row[key])
            selected = select(study["agreement"], **base, reference_passed=1)
            add_estimate(row, "reference_mean_mcse_sd", bootstrap([float(r["reference_mean_mcse_sd"]) for r in selected]))
            agreement.append(row)
    paired = compute_case_rows(study)
    for source_row in study["summary"]["compute"]:
        cohort, method = source_row["cohort"], source_row["method"]
        passed, total = status(study, cohort)
        row = {"cohort": cohort, "method": method, "unit": "independent_case", "n_all_cases": total,
               "n_qualified_cases": passed, "reference_failed": total-passed}
        add_estimate(row, "cpu_all_cases", source_row)
        selected = select(paired, cohort=cohort, method=method)
        for key in ("fit_cpu_seconds", "mean_gap_reference_sd"):
            add_estimate(row, key + "_qualified", bootstrap([r[key] for r in selected]))
        compute.append(row)
    for cohort in COHORTS:
        passed, total = status(study, cohort)
        for method in METHODS:
            for quantity in QUANTITIES:
                rows = select(study["cdf"], cohort=cohort, method=method, quantity=quantity)
                _, deviation = ecdf_deviation([float(r["cdf"]) for r in rows])
                cdf.append({"cohort": cohort, "method": method, "quantity": quantity,
                            "unit": "independent_case", "n_all_cases": total,
                            "reference_passed": passed, "reference_failed": total-passed,
                            "max_absolute_ecdf_deviation": float(np.max(np.abs(deviation))),
                            "uniform_null_asserted": int(cohort == "prior_predictive"),
                            "dkw95_single_ecdf_bound": float(np.sqrt(np.log(2/.05)/(2*total))) if cohort == "prior_predictive" else None})
    for source_row in study["summary"]["paired_higher_minus_published"]:
        passed, total = status(study, source_row["cohort"])
        row = {"cohort": source_row["cohort"], "parameter": source_row["parameter"],
               "contrast": "higher_compute_minus_published", "unit": "independent_case",
               "n_qualified_cases": passed, "n_all_cases": total, "reference_failed": total-passed}
        for key in ("mean_gap_reference_sd", "endpoint_gap_prior_width"):
            add_estimate(row, key, source_row[key])
        contrasts.append(row)
    return [write_table(output, name, rows) for name, rows in
            (("coverage-statistics.csv", coverage), ("agreement-statistics.csv", agreement),
             ("compute-statistics.csv", compute), ("cdf-statistics.csv", cdf),
             ("paired-agreement-contrasts.csv", contrasts))]


CAPTIONS = {
    "parameter-coverage": "Coverage of terminal 90% marginal credible intervals against simulator coefficients, with mean interval widths printed alongside. Dots and horizontal lines give all-case coverage and 95% Wilson binomial intervals over independent cases, including nonzero uncertainty when all cases cover. Every case is retained, including failed reference outcomes. Prior-predictive controls draw true laws from the learner's full prior and have exogenous features. Ecological cases draw laws from the narrower task distribution and use pooled histories from interacting fixed-policy societies; this is coverage under the fitted conditional likelihood, not a prior-predictive calibration test. The nominal 0.90 line has different inferential meanings in those panels. Method identity uses labels and neutral markers, not society colors.",
    "posterior-agreement": "Agreement with an independently implemented batch MCMC posterior on cases passing its prespecified rank-normalized R-hat and bulk/tail effective-sample-size checks. Small linked marks pair individual cases across SMC settings; larger marks and horizontal lines show case means and 95% bootstrap intervals. Both SMC settings use the same qualified cases, and the paired-agreement-contrasts CSV reports paired budget effects. Mean discrepancies are divided by reference posterior SD; interval widths are ratios to the reference; endpoint discrepancies are divided by the public prior width. Lower discrepancies and width ratios near one indicate closer numerical agreement. Small vertical ticks in mean panels show mean reference mean-MCSE divided by posterior SD, providing numerical-noise context rather than a hard significance threshold. Passing convergence diagnostics does not prove exact computation, and differences near reference Monte Carlo uncertainty must not be overinterpreted. The failed-reference denominator remains visible; those cases are excluded only from this qualified agreement, not raw coverage or CDF diagnostics. Frozen-prior agreement is retained in the derived CSV but omitted from this scale-focused SMC comparison.",
    "compute-accuracy": "Top panels report recorded fitting CPU cost for all cases, including unsuccessful references and retry computation. Bottom panels use only the shared qualified-reference cases, plotting fitting CPU seconds against each case's average standardized marginal posterior-mean discrepancy over r, b and g. Small symbols are cases and large symbols show means with 95% case bootstrap intervals on each axis. Chains, particles and coefficients are not independent replications. Fitting CPU includes inference, reference convergence diagnostics and retries; it excludes separately timed full-data CDF scoring and is machine-dependent. SMC processes the observations sequentially, whereas the batch reference fits the complete history once at its terminal point, plus any prescribed retry. These costs describe work to reach a terminal posterior, not matched online latency or a planning benchmark. The batch reference has its own Monte Carlo error; its cost is shown without treating it as an exact zero-error ground truth. Higher computation is a sensitivity comparison, not a changed production default.",
    "cdf-diagnostics": "Empirical CDF minus uniform CDF for each method's posterior CDF evaluated at simulator truth, separately for coefficients and the data-dependent log-likelihood statistic. One value per independent case is used; failed references remain in the raw curves. Each panel has its own vertical range to retain the unupdated prior's likelihood discrepancy without compressing coefficient diagnostics. In the prior-predictive cohort only, the gray band is the 95% Dvoretzky–Kiefer–Wolfowitz simultaneous bound for one ECDF under an independent uniform null. It is not a multiplicity-adjusted bound over all methods or quantities. Finite weighted particles and correlated reference draws make these approximate CDF diagnostics, not exact exchangeable discrete SBC ranks. Ecological curves are descriptive: narrower law draws and latent-outcome-dependent feature generation prevent interpreting them as the same uniform-null test. Marginal prior-predictive checks alone can accept an unupdated prior, so the data-dependent likelihood check is also shown. A successful CDF check does not establish useful learning or accurate decisions.",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "evidence/world-model-calibration-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/world-model-calibration-v1")
    args = parser.parse_args(argv)
    study = load_study(args.source)
    theme()
    args.output.mkdir(parents=True, exist_ok=True)
    files = export_tables(study, args.output)
    for renderer in (coverage_figure, agreement_figure, compute_figure, cdf_figure):
        files.extend(renderer(study, args.output))
    readme = args.output / "README.md"
    lines = ["# World-model calibration audit", "",
             "Recorded-data Chromatic Field v1 figures. This separately versioned numerical audit preserves the published learner and its original evidence.", "",
             f"Bank: **{study['design']['bank']}**. Independent prior-predictive cases: **{status(study, 'prior_predictive')[1]}**. Independent ecological cases: **{status(study, 'ecological')[1]}**. Evolutionary runs and model-generation calls: **0**.", "",
             "Reference qualification: " + "; ".join(f"{COHORT_LABELS[c]} {status_text(study, c)}" for c in COHORTS) + ".", "",
             "Method settings are shown as particle count / rejuvenation sweeps. Methods use neutral marker and line encodings; no method is assigned a society color. Reference checks are necessary diagnostics, not proof of an exact posterior. Reference failures remain in all-case coverage, CDF and cost summaries, and are excluded only from qualified agreement.", ""]
    for name, caption in CAPTIONS.items():
        lines.extend([f"## {name}", "", f"[SVG]({name}.svg) · [PDF]({name}.pdf) · [PNG]({name}.png)", "", caption, ""])
    lines.extend(["## Derived tables and provenance", "",
                  "[Coverage](coverage-statistics.csv) · [Posterior agreement](agreement-statistics.csv) · [Paired budget effects](paired-agreement-contrasts.csv) · [Compute](compute-statistics.csv) · [CDF diagnostics](cdf-statistics.csv) · [Source/output hashes](manifest.json)", "",
                  "Cases are the independent units. Coverage uses 95% Wilson binomial intervals. Other intervals use 2,000 bootstrap draws and seed 8307; paired methods share case identities. Tables are derived from recorded primitives and checked against the frozen summary. The renderer runs no training or ecological evaluation.", "",
                  "```bash", ".venv/bin/python scripts/visualize_world_model_calibration.py", "```", ""])
    readme.write_text("\n".join(lines))
    sources = [args.source / name for name in ("design.json", "design.sha256", "completion.json", "parameters.csv", "cdf.csv", "agreement.csv", "diagnostics.json", "summary.json")]
    sources.extend((Path(__file__), ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md"))
    def portable(path):
        path = path.resolve()
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    manifest = {"schema_version": 1, "renderer_version": RENDERER_VERSION,
                "style": STYLE, "study": "world-model-calibration-v1", "bank": study["design"]["bank"],
                "sources": {portable(path): digest(path) for path in sources},
                "captions": CAPTIONS, "cohort_counts": study["summary"]["cohort_counts"],
                "reference_failures": study["summary"]["reference_failures"],
                "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED,
                              "unit": "independent case", "level": .95},
                "coverage_interval": "95% Wilson binomial interval; one coverage indicator per independent case",
                "cdf_band": "95% DKW simultaneous within each independent prior-predictive ECDF; no ecological uniform-null band; no familywise correction",
                "rendering_runs_training": False, "rendering_runs_evaluation": False,
                "independent_evolutionary_runs": 0, "model_generation_calls": 0,
                "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__},
                "artifacts": {path.name: digest(path) for path in [*files, readme]}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "figure_count": len(CAPTIONS),
                      "cohort_counts": study["summary"]["cohort_counts"],
                      "reference_failures": study["summary"]["reference_failures"]}, indent=2))


if __name__ == "__main__":
    main()
