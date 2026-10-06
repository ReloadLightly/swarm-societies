#!/usr/bin/env python3
"""Render the proposed world-model architecture; no experimental data or runs."""
from __future__ import annotations

import argparse
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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

DESIGN_VERSION = "world-model-design-v1"
PROPOSAL = ROOT / "docs/world-model-proposal.md"
CAPTION = (
    "Proposed architecture, not experimental evidence. One trusted shared world "
    "exposes only authorized observations and versioned receipts. Each society "
    "has separate member and institutional beliefs; governed sharing preserves "
    "evidence provenance and avoids duplicate updates. Beliefs distinguish "
    "physical mechanisms, hidden state, and other societies' behavior. Forecasts "
    "are issued before outcomes; later phases may select experiments and actions. "
    "A protected evaluator uses hidden truth and common held-out same-law probes "
    "with learner updates frozen. Probe answers never enter training. Stage 1 "
    "estimates unknown parameters within supplied mechanisms; Stage 2 compares "
    "and discovers rule structures within a declared hypothesis language. Colors "
    "identify societies 0, 1, and 2; position is schematic and not physical space."
)


def box(ax, x, y, width, height, *, fill=BACKGROUND, edge=RULE):
    ax.add_patch(FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=0.85, edgecolor=edge, facecolor=fill, zorder=2))


def label(ax, x, y, text, *, size=10.5, color=INK, weight="normal", ha="left"):
    ax.text(x, y, text, fontsize=size, color=color, weight=weight,
            va="top", ha=ha, linespacing=1.6, zorder=5)


def arrow(ax, start, end, *, dashed=False, color=SECONDARY):
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=12, linewidth=1.0,
        linestyle="--" if dashed else "-", color=color,
        shrinkA=0, shrinkB=0, zorder=4))


def render(output: Path):
    theme()
    fig, ax = plt.subplots(figsize=(16.2, 10.7))
    ax.set_position([0.02, 0.035, 0.96, 0.94])
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10.4)
    ax.set_axis_off()

    label(ax, 0.35, 10.22, "Learning the laws of a shared world", size=24, weight="bold")
    label(ax, 0.35, 9.76, "PROPOSED ARCHITECTURE  /  Chromatic Field v1  /  No experimental results",
          size=10, color=SECONDARY)

    box(ax, 0.35, 8.05, 7.35, 1.15, fill=MUTED)
    label(ax, 0.58, 8.99, "01  PARAMETER LEARNING", size=11, weight="bold")
    label(ax, 0.58, 8.62, "Supplied mechanisms → uncertain coefficients, hidden state and regime", size=10.4)
    box(ax, 8.00, 8.05, 7.65, 1.15, fill=MUTED)
    label(ax, 8.23, 8.99, "02  STRUCTURE DISCOVERY", size=11, weight="bold")
    label(ax, 8.23, 8.62, "Competing terms and rules → hypotheses tested through interventions", size=10.4)

    # Neutral substrate and observation cards: society colors identify actors only.
    box(ax, 0.35, 4.30, 2.85, 3.18)
    label(ax, 0.58, 7.20, "Shared world", size=14, weight="bold")
    label(ax, 0.58, 6.72, "Hidden law draw\nResources and infrastructure\nWeather and regime\nInteracting society actions", size=10.1)
    ax.plot([0.58, 2.95], [5.10, 5.10], color=RULE, linewidth=0.8, zorder=3)
    label(ax, 0.58, 4.92, "Trusted simulator owns\nmaterial consequences", size=9.8, color=SECONDARY)

    box(ax, 3.72, 4.30, 2.85, 3.18)
    label(ax, 3.95, 7.20, "Authorized evidence", size=13.2, weight="bold")
    label(ax, 3.95, 6.72, "Private observations\nVersioned outcome receipts\nPermitted patch sensors\nPhase, time and source IDs", size=10.1)
    ax.plot([3.95, 6.32], [5.10, 5.10], color=RULE, linewidth=0.8, zorder=3)
    label(ax, 3.95, 4.92, "Explicit permissions\nand measurement costs", size=9.8, color=SECONDARY)

    box(ax, 7.08, 4.30, 4.38, 3.18)
    label(ax, 7.31, 7.20, "Separate society models", size=13.2, weight="bold")
    for sid in range(3):
        y = 6.69 - 0.41 * sid
        color = society_color(sid)
        ax.scatter([7.39], [y - 0.065], s=36, color=color, zorder=5)
        label(ax, 7.57, y + 0.025, f"{sid}", size=10.2, color=color, weight="bold")
        label(ax, 7.93, y + 0.025, "Member beliefs ↔ Institution belief", size=10.0)
    label(ax, 7.31, 5.34, "Governed sharing · provenance · deduplication", size=9.5, weight="bold")
    ax.plot([7.31, 11.20], [5.05, 5.05], color=RULE, linewidth=0.8, zorder=3)
    label(ax, 7.31, 4.89, "Mechanisms  /  Hidden state  /  Other actions", size=9.1, color=SECONDARY)
    label(ax, 7.31, 4.60, "Uncertainty stays attached to each prediction", size=9.2, color=SECONDARY)

    box(ax, 11.98, 4.30, 3.67, 3.18)
    label(ax, 12.21, 7.20, "Predict, then learn", size=13.2, weight="bold")
    label(ax, 12.21, 6.72, "Forecast before the outcome\nScore the saved forecast\nUpdate from completed events", size=10.1)
    ax.plot([12.21, 15.40], [5.34, 5.34], color=RULE, linewidth=0.8, zorder=3)
    label(ax, 12.21, 5.13, "LATER: ACTIVE LEARNING", size=9.7, weight="bold")
    label(ax, 12.21, 4.82, "Choose experiments and actions\nusing the learned model", size=9.9, color=SECONDARY)

    for start, end in ((3.20, 3.72), (6.57, 7.08), (11.46, 11.98)):
        arrow(ax, (start + 0.04, 6.01), (end - 0.04, 6.01))

    # Later active control is deliberately a separate dashed feedback path.
    ax.plot([12.79, 12.79, 2.50], [4.27, 3.69, 3.69],
            color=SECONDARY, linewidth=1.0, linestyle="--", zorder=3)
    arrow(ax, (2.50, 3.69), (2.50, 4.27), dashed=True)
    label(ax, 7.65, 3.52, "Later active phase: experiments and actions have resource costs",
          size=9.8, color=SECONDARY, ha="center")

    # Only evaluation receives hidden truth and sealed probe answers.
    ax.plot([0.35, 15.65], [3.02, 3.02], color=RULE, linewidth=1.1,
            linestyle=(0, (4, 3)), zorder=1)
    arrow(ax, (1.05, 4.27), (1.05, 2.45))
    arrow(ax, (15.11, 4.27), (15.11, 2.45))
    label(ax, 1.91, 2.85, "PROTECTED EVALUATOR", size=10, weight="bold")
    label(ax, 14.52, 2.85, "Probe answers never enter learner updates", size=10,
          color=SECONDARY, ha="right")

    box(ax, 0.35, 0.43, 15.30, 1.97, fill=MUTED)
    for x in (4.62, 10.06):
        ax.plot([x, x], [0.67, 2.15], color=RULE, linewidth=0.8, zorder=3)
    label(ax, 0.59, 2.17, "Hidden truth", size=12, weight="bold")
    label(ax, 0.59, 1.73, "True parameters and rule structure\nRecorded outcomes and interventions\nEvaluator-only reference models", size=10.2)
    label(ax, 4.86, 2.17, "Common held-out same-law probes", size=12, weight="bold")
    label(ax, 4.86, 1.73, "Identical state and action questions\nLearning frozen while probes are scored\nTransfer tested separately on changed laws", size=10.2)
    label(ax, 10.30, 2.17, "Knowledge quality and learning speed", size=12, weight="bold")
    label(ax, 10.30, 1.73, "Proper scores · calibration · rule recovery\nUnique evidence · ticks · bytes · compute\nIndependent arenas are the replication unit", size=10.2)
    label(ax, 0.35, 0.16, "Schematic information flow, not physical space. Society colors are identities; no performance or learning curves are implied.",
          size=9.0, color=SECONDARY)
    return save(fig, output / "architecture")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "figures/world-model-design")
    parser.add_argument("--include-proposal-hash", action="store_true",
                        help="Hash the design proposal after its editing handoff is complete.")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    files = render(args.output)
    readme = args.output / "README.md"
    readme.write_text(
        "# Proposed world-model architecture\n\n"
        "[SVG](architecture.svg) · [PDF](architecture.pdf) · [PNG](architecture.png)\n\n"
        + CAPTION + "\n\n"
        "Design source: [world-model proposal](../../docs/world-model-proposal.md), "
        "supported by the [research review](../../docs/world-model-literature.md). "
        "This is an authored design schematic. No empirical observations, training, "
        "evaluation, or evolutionary search are represented.\n\n"
        "The renderer reuses the [Chromatic Field theme and export helpers]"
        "(../../swarm_societies/visualize.py). Source/output hashes, version, "
        "and software information are recorded in [manifest.json](manifest.json).\n\n"
        "```bash\n.venv/bin/python scripts/visualize_world_model_design.py "
        "--include-proposal-hash\n```\n")
    source_paths = [Path(__file__), ROOT / "swarm_societies/visualize.py",
                    ROOT / "docs/visual-reference.md"]
    sources = {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    if args.include_proposal_hash:
        sources[str(PROPOSAL.relative_to(ROOT))] = digest(PROPOSAL)
        literature = ROOT / "docs/world-model-literature.md"
        sources[str(literature.relative_to(ROOT))] = digest(literature)
    manifest = {
        "schema_version": 1,
        "design_version": DESIGN_VERSION,
        "style": STYLE,
        "kind": "proposed_architecture_schematic",
        "data_basis": "authored design; no empirical observations or quantitative encodings",
        "design_attribution": {
            "proposal": "docs/world-model-proposal.md",
            "literature": "docs/world-model-literature.md",
            "proposal_hash_included": args.include_proposal_hash,
            "proposal_hash_status": "final editing handoff" if args.include_proposal_hash else "omitted while proposal is being edited",
        },
        "caption": CAPTION,
        "sources": sources,
        "training_performed": False,
        "evaluation_performed": False,
        "evolution_performed": False,
        "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                     "numpy": np.__version__},
        "artifacts": {p.name: digest(p) for p in [*files, readme]},
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "exports": len(files),
                      "proposal_hash_included": args.include_proposal_hash}))


if __name__ == "__main__":
    main()
