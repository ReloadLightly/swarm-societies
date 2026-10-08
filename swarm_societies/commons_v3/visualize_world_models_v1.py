"""Chromatic Field figures from a validated, recorded development comparison.

This module does not load evidence, run simulations, import policies, select
parameters, or recalculate statistical intervals. ``render_figures(data, path)``
returns ``[{"id": str, "caption": str, "files": list[Path]}, ...]``. The caller
owns source/output hashing and persistence using the existing report tooling.

The input contains ``stage``, ``summary`` (the unchanged comparison summary),
``rows`` (selected learner/pool records), ``references`` (selected reference
records), and ``reference_statistics``. The latter is a list of
``{condition, need, arms: {arm: {metric: descriptive_statistics}}}`` cells, with
whole-run and final-quarter consumption statistics. All supplied intervals
must be the existing descriptive intervals over the four reused seeds.
"""
from __future__ import annotations

import math
from pathlib import Path

from swarm_societies.visualize import (
    BACKGROUND, INK, RULE, SECONDARY, plt, save, theme,
)
from matplotlib.lines import Line2D


_STAGES = {
    "known-rate-pooling": "Known renewal rate · private learning and perfect pooling",
    "unknown-rate-pooling": "Unknown renewal rate · private learning and perfect pooling",
    "unknown-rate-sharing": "Unknown renewal rate · receipts, evidence relay and belief exchange",
}
_ARM_ORDER = ("L0", "L1", "L2", "L3", "L2-biased", "L3-biased", "R-pool")
_REFERENCE_ORDER = ("R-oracle", "R-fixed", "R-greedy")
_SOCIAL_ARMS = ("L2", "L3", "L2-biased", "L3-biased")
# Reserve society colors for society identities. Conditions use neutral tones,
# explicit labels and distinct markers/dashes, including biased variants.
_STYLES = {
    "L0": (SECONDARY, "o", "-"),
    "L1": (SECONDARY, "v", "-."),
    "L2": (INK, "o", "-"),
    "L3": (SECONDARY, "s", "--"),
    "L2-biased": (INK, "^", "--"),
    "L3-biased": (SECONDARY, "D", ":"),
    "R-pool": (INK, "D", "--"),
    "R-oracle": (INK, "*", "-"),
    "R-fixed": (SECONDARY, "P", "-"),
    "R-greedy": (SECONDARY, "X", "-"),
}
_LABELS = {
    "L0": "L0 · private", "L1": "L1 · receipts", "L2": "L2 · evidence relay",
    "L3": "L3 · belief exchange", "L2-biased": "L2 · biased minority",
    "L3-biased": "L3 · biased minority", "R-pool": "R-pool · perfect pooling",
}


def _cells(data):
    return sorted(data["summary"]["cells"], key=lambda c: (c["condition"], c["need"]))


def _arms(data):
    present = set(_cells(data)[0]["arms"])
    return [arm for arm in _ARM_ORDER if arm in present]


def _number(value):
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)


def _statistics(stats):
    """Keep missing values missing, including undefined clean fractions at zero."""
    mean = stats["mean"]
    if not _number(mean):
        return None
    interval = stats["ci95"]
    if interval is not None:
        if (len(interval) != 2 or not all(_number(value) for value in interval)
                or not interval[0] <= mean <= interval[1]):
            raise ValueError("invalid descriptive interval supplied to plot")
        return mean, interval[0], interval[1]
    return mean, None, None


def _rows(data, cell, arm, *, reference=False):
    source = data["references"] if reference else data["rows"]
    return sorted((row for row in source
                   if (row["job"]["condition"], row["job"]["need"], row["job"]["arm"])
                   == (cell["condition"], cell["need"], arm)),
                  key=lambda row: row["job"]["seed"])


def _header(fig, title, data):
    fig.text(.065, .976, title, va="top", fontsize=17, weight="bold", color=INK)
    fig.text(.065, .939, "DEVELOPMENT · four reused seeds · descriptive 95% intervals",
             va="top", fontsize=10, weight="bold", color=SECONDARY)
    fig.text(.065, .912, _STAGES[data["stage"]], va="top", fontsize=10, color=SECONDARY)


def _legend(fig, arms, *, y=.858, scatter=False):
    handles = [Line2D([], [], color=_STYLES[arm][0], marker=_STYLES[arm][1],
                      markerfacecolor=BACKGROUND if scatter and not arm.endswith("-biased") else _STYLES[arm][0],
                      linestyle="" if scatter else _STYLES[arm][2], linewidth=1.6, markersize=5,
                      label=_LABELS.get(arm, arm)) for arm in arms]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(.06, y),
               ncol=min(3, len(arms)), columnspacing=2.4, handlelength=2.7,
               fontsize=9, borderaxespad=0)


def _panel_title(cell):
    return f"{cell['condition'].capitalize()} capacities · need {cell['need']:g}"


def _grid(ax, *, axis="y"):
    ax.grid(axis=axis, color=RULE, alpha=.72, zorder=0)
    ax.tick_params(length=0, pad=6)


def _line(ax, trajectory, metric, arm):
    color, marker, linestyle = _STYLES[arm]
    ticks, means, lower, upper = [], [], [], []
    for point in trajectory:
        stats = _statistics(point[metric])
        ticks.append(point["tick"])
        means.append(float("nan") if stats is None else stats[0])
        lower.append(float("nan") if stats is None or stats[1] is None else stats[1])
        upper.append(float("nan") if stats is None or stats[2] is None else stats[2])
    ax.fill_between(ticks, lower, upper, color=color, alpha=.09, linewidth=0, zorder=1)
    ax.plot(ticks, means, color=color, marker=marker, linestyle=linestyle,
            linewidth=1.5, markersize=3.8, markeredgewidth=.4, zorder=3)


def _same_limits(axes, *, lower=None, upper=None):
    limits = [axis.get_ylim() for axis in axes]
    low = min(value[0] for value in limits)
    high = max(value[1] for value in limits)
    if lower is not None:
        low = min(low, lower)
    if upper is not None:
        high = max(high, upper)
    for axis in axes:
        axis.set_ylim(low, high)


def learning_figure(data, output):
    cells, arms = _cells(data), _arms(data)
    fig, axes = plt.subplots(3, len(cells), figsize=(16.8, 11.4), squeeze=False,
                             gridspec_kw={"height_ratios": (1.25, 1.1, .78)})
    _header(fig, "Learning site capacities", data)
    _legend(fig, arms, y=.851)
    metrics = (("capacity_absolute_log_error", "Capacity error\nmean |log(median / true K)|"),
               ("coverage90", "90% interval coverage\nagent–site fraction"),
               ("clean_eligible_fraction", "Clean / eligible evidence\ncumulative fraction"))
    horizon = data["summary"]["horizon"]
    for column, cell in enumerate(cells):
        for row, (metric, label) in enumerate(metrics):
            ax = axes[row, column]
            for arm in arms:
                _line(ax, cell["belief_trajectories"][arm], metric, arm)
            _grid(ax)
            ax.set_xlim(0, horizon)
            ax.set_xticks([0, horizon // 4, horizon // 2, 3 * horizon // 4, horizon])
            if row == 0:
                ax.set_title(_panel_title(cell), fontsize=10.5)
            if row == 1:
                ax.axhline(.9, linestyle=":", color=SECONDARY, linewidth=.8, zorder=2)
            if row == 2:
                ax.set_xlabel("Observation tick")
            else:
                ax.tick_params(labelbottom=False)
            if column == 0:
                ax.set_ylabel(label, labelpad=10)
    _same_limits(axes[0], lower=0.)
    _same_limits(axes[1], lower=0., upper=1.02)
    _same_limits(axes[2], lower=0., upper=1.02)
    fig.text(.065, .045,
             "All agent–site pairs, including priors for unseen sites. Dotted line: nominal 90% coverage.\n"
             "Bands are descriptive intervals over reused seeds; fraction intervals are shown without clipping. Undefined clean fractions are omitted.",
             fontsize=9, color=SECONDARY, va="bottom", linespacing=1.5)
    fig.subplots_adjust(left=.09, right=.985, top=.801, bottom=.123, hspace=.30, wspace=.28)
    caption = (
        "Learning in all four development cells. Points are the recorded observation checkpoints "
        "(tick zero through the terminal observation); segments join checkpoints without implying "
        "additional measurements. Capacity error is the within-episode mean absolute log ratio of "
        "posterior median to true site capacity over all agent–site pairs, including prior beliefs "
        "for sites an individual has not seen. Coverage is the fraction of those pairs whose 90% "
        "posterior interval contains true capacity; the dotted line is 0.90. The bottom panels show "
        "the recorded cumulative (clean own transitions + clean receipts) / eligible-transition "
        "fraction; an undefined denominator is omitted. For R-pool, receipt counters are privileged "
        "pooled transitions counted per recipient, not paid messages. Lines show four-seed means "
        "and bands the saved descriptive 95% Student-t intervals, without clipping them to fraction "
        "bounds. The same four reused development worlds occur in each arm; these are not fresh "
        "evaluation intervals or independent evolutionary runs."
    )
    return {"id": "learning", "caption": caption, "files": save(fig, output / "learning")}


def _dot(ax, position, stats, values, arm):
    color, marker, _ = _STYLES[arm]
    estimate = _statistics(stats)
    if estimate is None:
        ax.text(.015, position, "unavailable", color=SECONDARY, fontsize=8,
                transform=ax.get_yaxis_transform(), va="center")
        return
    mean, low, high = estimate
    jitter = [(.22 * (index / (len(values) - 1) - .5) if len(values) > 1 else 0.)
              for index in range(len(values))]
    ax.scatter(values, [position + offset for offset in jitter], s=16,
               color=color, alpha=.35, edgecolors="none", zorder=3)
    if low is not None:
        ax.plot([low, high], [position, position], color=color, linewidth=1.2, zorder=4)
        ax.plot([low, low], [position - .07, position + .07], color=color, linewidth=.8)
        ax.plot([high, high], [position - .07, position + .07], color=color, linewidth=.8)
    ax.scatter([mean], [position], marker=marker, s=43, facecolor=BACKGROUND,
               edgecolor=color, linewidth=1.4, zorder=5)


def consequences_figure(data, output):
    cells, learner_arms = _cells(data), _arms(data)
    arms = [*learner_arms, *_REFERENCE_ORDER]
    ref_stats = {(cell["condition"], cell["need"]): cell["arms"]
                 for cell in data["reference_statistics"]}
    fig, axes = plt.subplots(2, len(cells), figsize=(16.8, 9.9), squeeze=False)
    _header(fig, "Material consequences of learning", data)
    horizon = data["summary"]["horizon"]
    metrics = ("share_of_need", "final_quarter_share_of_need")
    for column, cell in enumerate(cells):
        for row, metric in enumerate(metrics):
            ax = axes[row, column]
            for position, arm in enumerate(arms):
                reference = arm in _REFERENCE_ORDER
                statistics = ref_stats[(cell["condition"], cell["need"])][arm] if reference else cell["arms"][arm]
                values = [record["summary"][metric] for record in _rows(data, cell, arm, reference=reference)]
                _dot(ax, position, statistics[metric], values, arm)
            ax.axhline(len(learner_arms) - .5, color=RULE, linewidth=.8)
            ax.axvline(1., color=SECONDARY, linestyle=":", linewidth=.8)
            ax.set_yticks(range(len(arms)), labels=arms if column == 0 else [])
            ax.set_ylim(len(arms) - .4, -.6)
            low, high = ax.get_xlim()
            ax.set_xlim(min(-.025, low), max(1.04, high))
            _grid(ax, axis="x")
            ax.set_xlabel("Share of need met")
            if row == 0:
                ax.set_title(_panel_title(cell), fontsize=10.5)
    # Preserve every interval, with common scales for all cells and periods.
    limits = [ax.get_xlim() for row in axes for ax in row]
    low, high = min(value[0] for value in limits), max(value[1] for value in limits)
    for row in axes:
        for ax in row:
            ax.set_xlim(low, high)
    fig.text(.065, .854, f"Whole run · physical ticks 1–{horizon}", weight="bold", fontsize=11)
    fig.text(.065, .474, f"Final quarter · physical ticks {3 * horizon // 4 + 1}–{horizon}", weight="bold", fontsize=11)
    fig.text(.065, .045,
             "Hollow markers: means and descriptive 95% intervals. Small dots: individual seeds; vertical offsets identify seeds consistently.\n"
             "Reference rows use the saved oracle, selected fixed-capacity controller and greedy controller. Dotted line: all need met.",
             fontsize=9, color=SECONDARY, va="bottom", linespacing=1.5)
    fig.subplots_adjust(left=.1, right=.985, top=.805, bottom=.14, hspace=.43, wspace=.19)
    caption = (
        f"Mean share of material need met over physical ticks 1–{horizon} (top) and "
        f"{3 * horizon // 4 + 1}–{horizon} (bottom), shown separately in all capacity-width and "
        "need cells. Each raw dot is an episode's total consumption divided by population, ticks "
        "and individual need. Hollow markers and whiskers give means and saved descriptive 95% "
        "Student-t intervals over four reused development seeds. Deterministic vertical jitter "
        "follows seed order, so the same seed has the same offset in each arm. Reference rows "
        "come from the selected, preserved consequence-map cases; the oracle is the supplied "
        "known-capacity policy, not an optimal controller or a consumption upper bound. Whole-run "
        "and final-quarter measures are never substituted for each other. The dotted line marks "
        "one unit of consumption per unit of need. No fresh evaluation or Holm-adjusted tests "
        "are represented."
    )
    return {"id": "consequences", "caption": caption, "files": save(fig, output / "consequences")}


def social_figure(data, output):
    cells = _cells(data)
    fig, axes = plt.subplots(3, len(cells), figsize=(16.8, 11.5), squeeze=False,
                             gridspec_kw={"height_ratios": (1.25, 1., 1.)})
    _header(fig, "Belief exchange, consensus and consumption", data)
    _legend(fig, _SOCIAL_ARMS, y=.851, scatter=True)
    for column, cell in enumerate(cells):
        ax = axes[0, column]
        for arm in _SOCIAL_ARMS:
            color, marker, _ = _STYLES[arm]
            for record in _rows(data, cell, arm):
                metrics = record["summary"]
                dispersion = metrics["terminal_between_agent_log_median_dispersion"]
                error = metrics["terminal_capacity_absolute_log_error"]
                width = metrics["terminal_mean_log_interval_width"]
                if not all(_number(value) for value in (dispersion, error, width)):
                    raise ValueError("social scatter requires complete terminal epistemic metrics")
                # Marker area, not radius, is linear in the recorded log interval width.
                ax.scatter([dispersion], [error], s=30 + 60 * width, marker=marker,
                           facecolor=color if arm.endswith("-biased") else BACKGROUND,
                           edgecolor=color, linewidth=1.1, alpha=.8, zorder=3)
        ax.set_title(_panel_title(cell), fontsize=10.5)
        ax.set_xlabel("Between-agent dispersion\nSD of log medians, site mean", fontsize=9)
        _grid(ax)
        if column == 0:
            ax.set_ylabel("Terminal capacity error\nmean |log(median / true K)|")
        for row, (metric, label) in enumerate((
                ("share_of_need", "Whole-run share of need met"),
                ("starvation_next_to_food_share_of_need", "Shortfall next to food / total need")), start=1):
            ax = axes[row, column]
            for position, arm in enumerate(_SOCIAL_ARMS):
                values = [record["summary"][metric] for record in _rows(data, cell, arm)]
                _dot(ax, position, cell["arms"][arm][metric], values, arm)
            ax.set_yticks(range(len(_SOCIAL_ARMS)), labels=_SOCIAL_ARMS if column == 0 else [])
            ax.set_ylim(len(_SOCIAL_ARMS) - .4, -.6)
            ax.set_xlabel(label, fontsize=9)
            ax.axvline(0., color=SECONDARY, linewidth=.6)
            _grid(ax, axis="x")
    _same_limits(axes[0], lower=0.)
    for row in axes:
        limits = [ax.get_xlim() for ax in row]
        low, high = min(0., *(value[0] for value in limits)), max(value[1] for value in limits)
        for ax in row:
            ax.set_xlim(low, high)
    # Show exact marker-size examples for posterior width without claiming that
    # low dispersion alone establishes confidence or harmful herding.
    size_handles = [Line2D([], [], linestyle="", marker="o", markerfacecolor=BACKGROUND,
                          markeredgecolor=SECONDARY, markersize=math.sqrt(30 + 60 * width),
                          label=f"{width:g}") for width in (0., .5, 1.)]
    fig.legend(handles=size_handles, title="Terminal mean log interval width (marker area)",
               loc="lower left", bbox_to_anchor=(.064, .041), ncol=3,
               fontsize=8, title_fontsize=9, columnspacing=2., borderaxespad=0)
    fig.text(.48, .051,
             "Scatter: one recorded episode per point. Filled markers: biased minority.\n"
             "Lower rows: all agents, seed dots, means and descriptive 95% intervals.\n"
             "Low dispersion alone does not establish confident wrong consensus.",
             fontsize=8.6, color=SECONDARY, va="bottom", linespacing=1.45)
    fig.subplots_adjust(left=.1, right=.985, top=.802, bottom=.149, hspace=.55, wspace=.28)
    caption = (
        "Evidence relay (L2) and belief exchange (L3), with and without the contracted biased "
        "minority, in every development cell. Each top-row point is a saved episode at the "
        "terminal observation: horizontal position is the mean across sites of the population "
        "standard deviation of log posterior medians; vertical position is mean absolute log "
        "capacity error over all agent–site pairs. Marker area is 30 + 60 times the terminal "
        "mean log 90% interval width, in points squared; the size key gives examples. Smaller "
        "width, smaller dispersion and larger error together are relevant to confident wrong "
        "consensus; dispersion alone is insufficient, and this scatter does not identify its "
        "cause. Filled markers denote arms with biased agents. Middle and bottom rows show "
        "all-population whole-run consumption/need and starvation-next-to-food shortfall divided "
        "by population × horizon × need. The latter counts shortfall for an agent standing at a "
        "site at its post-movement position whose stock after harvest exceeds the oracle floor "
        "phi × true capacity; its threshold and shortfall are the saved physical measurements. "
        "Hollow mean markers and whiskers retain the recorded descriptive 95% Student-t "
        "intervals; small dots show the four reused seeds with consistent vertical offsets. "
        "This implements the contract's 'When sharing hurts' comparison without presuming harm."
    )
    return {"id": "sharing", "caption": caption, "files": save(fig, output / "sharing")}


def render_figures(data, output):
    """Render two pool figures or all three sharing figures from recorded data.

    Input validation and exact reconstruction belong to the caller. Minimal
    shape checks here reject mislabeled stages and partial condition/arm grids
    instead of silently manufacturing a figure for missing results.
    """
    if data["stage"] not in _STAGES:
        raise ValueError("unknown recorded-results stage")
    summary = data["summary"]
    if len(summary["seeds"]) != 4 or len(set(summary["seeds"])) != 4:
        raise ValueError("development figures require four reused seeds")
    cells = _cells(data)
    if len(cells) != 4 or len({(cell["condition"], cell["need"]) for cell in cells}) != 4:
        raise ValueError("development figures require the complete four-cell comparison")
    arms = set(_arms(data))
    expected = set(_ARM_ORDER[:-1]) if data["stage"] == "unknown-rate-sharing" else {"L0", "R-pool"}
    if arms != expected or any(set(cell["arms"]) != expected for cell in cells):
        raise ValueError("recorded arm grid does not match the stated stage")
    if summary["rate_known"] != (data["stage"] == "known-rate-pooling"):
        raise ValueError("recorded rate contract does not match the stated stage")
    theme()
    output = Path(output)
    figures = [learning_figure(data, output), consequences_figure(data, output)]
    if data["stage"] == "unknown-rate-sharing":
        figures.append(social_figure(data, output))
    return figures
