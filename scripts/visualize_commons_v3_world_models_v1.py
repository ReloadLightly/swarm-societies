#!/usr/bin/env python3
"""Report complete recorded world-model development banks without simulation.

Known-rate pooling, the single unknown-rate fallback, and gated sharing retain
separate outputs. Failed gates are reportable. Incomplete banks are not results.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import platform
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm_societies.commons_v3 import development_joint_sites_v1 as joint
from swarm_societies.commons_v3 import development_joint_sharing_sites_v1 as sharing
from swarm_societies.commons_v3 import development_learning_sites_v1 as base
from swarm_societies.commons_v3 import development_pool_sites_v1 as pool
from swarm_societies.commons_v3.development_navigation_v1 import canonical, digest as record_digest, read_case
from swarm_societies.commons_v3.visualize_world_models_v1 import render_figures
from swarm_societies.visualize import digest
import matplotlib
import numpy as np

VERSION = "commons-v3-world-model-development-figures-v1"
STAGES = ("known-rate-pooling", "unknown-rate-pooling", "unknown-rate-sharing")
LABELS = dict(zip(STAGES, ("Known-rate pooling", "Unknown-rate pooling", "Unknown-rate sharing")))


def _summary(root):
    path = Path(root) / "summary.json"
    if not path.is_file():
        raise ValueError("incomplete recorded bank: " + str(root))
    return json.loads(path.read_text())


def _matching(saved, reconstructed, label):
    if canonical(saved) != canonical(reconstructed):
        raise ValueError(label + " aggregate differs from recorded cases")


def _require_known_complete(row, job, version):
    """Reject truncated legacy records without running an episode or replay."""
    try:
        initial = base.engine.restore(row["initial_snapshot"])
        final = base.engine.restore(row["final_snapshot"])
        checks = (
            row["job"] == job, row["version"] == version,
            row["horizon"] == base.HORIZON,
            initial.tick == 0, initial.seed == job["seed"],
            final.tick == base.HORIZON, final.seed == initial.seed,
            final.config == initial.config,
            [a.id for a in final.agents] == [a.id for a in initial.agents],
            [p.id for p in final.patches] == [p.id for p in initial.patches],
            [frame["tick"] for frame in row["ticks"]] == list(range(1, base.HORIZON + 1)),
            [frame["tick"] for frame in row["belief_ticks"]] == list(range(base.HORIZON + 1)),
            all(set(frame) == sharing.MATERIAL_FIELDS for frame in row["ticks"]),
            all(set(frame) == sharing.BELIEF_FIELDS for frame in row["belief_ticks"]),
            set(row["summary"]) == sharing.SUMMARY_FIELDS,
        )
        if not all(checks):
            raise ValueError("incomplete terminal record")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("incomplete or mismatched known-rate record: " + base.case_id(job)) from error


def _reference_statistics(references):
    return [{"condition": condition, "need": need, "arms": {
        arm: {metric: base.descriptive(row["summary"][metric] for row in references
            if (row["job"]["condition"], row["job"]["need"], row["job"]["arm"])
            == (condition, need, arm))
            for metric in ("share_of_need", "final_quarter_share_of_need")}
        for arm in ("R-oracle", "R-fixed", "R-greedy")}}
        for condition in base.CONDITIONS for need in base.NEEDS]


def load(stage, *, pool_root=pool.POOL_ROOT, baseline_root=pool.BASE_ROOT,
         reference_root=pool.REFERENCE_ROOT, calibration_root=joint.CALIBRATION_ROOT,
         fallback_root=joint.FALLBACK_ROOT, sharing_root=sharing.SHARING_ROOT):
    if stage not in STAGES:
        raise ValueError("unknown recorded study stage")
    main_root = {STAGES[0]: pool_root, STAGES[1]: fallback_root, STAGES[2]: sharing_root}[stage]
    saved = _summary(main_root)  # Reject an incomplete stage before any output.
    pool_root, baseline_root, reference_root = map(Path, (pool_root, baseline_root, reference_root))
    calibration_root, fallback_root, sharing_root = map(Path, (calibration_root, fallback_root, sharing_root))
    sources = [baseline_root / "summary.json", reference_root / "summary.json", pool_root / "summary.json"]
    sources += [base._path(baseline_root, job) for job in base.candidate_jobs()]
    sources += [base._path(pool_root, job) for job in pool.pool_jobs()]
    if stage == STAGES[0]:
        try:
            l0, references, baseline = pool.load_baseline(baseline_root, reference_root)
            pooled, summary = pool._load_pool(pool_root, l0, references, baseline)
        except IndexError as error:
            raise ValueError("incomplete known-rate observations in recorded aggregate") from error
        _matching(saved, summary, "known-rate pooling")
        rows, arms = [*l0, *pooled], ("L0", "R-pool")
        for row in rows:
            _require_known_complete(row, row["job"],
                                    pool.VERSION if row["job"]["arm"] == "R-pool" else base.VERSION)
    else:
        sources += [calibration_root / "cases.json", calibration_root / "summary.json",
                    fallback_root / "summary.json"]
        sources += [base._path(fallback_root, job) for job in joint.fallback_jobs()]
        if stage == STAGES[1]:
            jobs = joint.fallback_jobs()
            base._require_paths(fallback_root, jobs)
            rows = [read_case(base._path(fallback_root, job)) for job in jobs]
            for row, job in zip(rows, jobs):
                sharing._require_complete(row, job, joint.VERSION)
            references, known, calibration = joint._load_prerequisites(
                pool_root, baseline_root, reference_root, calibration_root)
            summary = joint.summarize(rows, references, known, calibration)
            _matching(saved, summary, "unknown-rate pooling")
            arms = ("L0", "R-pool")
        else:
            l0, references, fallback = sharing.load_fallback(
                fallback_root, pool_root, baseline_root, reference_root, calibration_root)
            jobs = sharing.sharing_jobs()
            base._require_paths(sharing_root, jobs)
            social = [read_case(base._path(sharing_root, job)) for job in jobs]
            summary = sharing.summarize(social, l0, references, fallback)
            _matching(saved, summary, "unknown-rate sharing")
            rows, arms = [*l0, *social], base.ARMS
            sources += [sharing_root / "summary.json", *(base._path(sharing_root, job) for job in jobs)]
    sources += [base.consequence._path(reference_root, row["job"]) for row in references]
    return {"stage": stage, "summary": summary, "rows": rows, "references": references,
            "seeds": list(base.SEEDS), "arms": list(arms),
            "reference_statistics": _reference_statistics(references),
            "sources": sorted(set(sources), key=str)}


def _write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _statistics(value):
    interval = value.get("ci95")
    return {"n": value["n"], "mean": value["mean"],
            "lower95": interval[0] if interval is not None else None,
            "upper95": interval[1] if interval is not None else None}


def export_tables(data, output):
    output = Path(output)
    means, trajectories, paired = [], [], []
    for cell in data["summary"]["cells"]:
        context = {key: cell[key] for key in ("condition", "need")}
        for arm, metrics in cell["arms"].items():
            means.extend({**context, "arm": arm, "metric": metric, **_statistics(value)}
                         for metric, value in sorted(metrics.items()))
        for arm, frames in cell["belief_trajectories"].items():
            for frame in frames:
                trajectories.extend({**context, "arm": arm, "tick": frame["tick"],
                    "metric": metric, **_statistics(value)}
                    for metric, value in sorted(frame.items()) if metric != "tick")
        for contrast, estimates in cell["contrasts"].items():
            for row in estimates["paired"]:
                paired.extend({**context, "contrast": contrast, "seed": row["seed"],
                    "metric": metric, "difference": value}
                    for metric, value in sorted(row.items()) if metric != "seed")
    for cell in data["reference_statistics"]:
        means.extend({"condition": cell["condition"], "need": cell["need"], "arm": arm,
                      "metric": metric, **_statistics(value)}
                     for arm, metrics in cell["arms"].items() for metric, value in metrics.items())
    stats = ["n", "mean", "lower95", "upper95"]
    paths = [
        _write_csv(output / "condition-means.csv", ["condition", "need", "arm", "metric", *stats], means),
        _write_csv(output / "learning-trajectories.csv", ["condition", "need", "arm", "tick", "metric", *stats], trajectories),
        _write_csv(output / "paired-effects.csv", ["condition", "need", "contrast", "seed", "metric", "difference"], paired),
    ]
    contrasts = data["summary"].get("development_contrasts", {}).get("contrasts")
    if contrasts:
        rows = []
        for contrast, specification in contrasts.items():
            endpoints = {"declared": specification} if "paired" in specification else {
                key: value for key, value in specification.items()
                if isinstance(value, dict) and "paired" in value}
            for endpoint, value in endpoints.items():
                rows.extend({"contrast": contrast, "endpoint": endpoint,
                             "seed": row["seed"], "difference": row["difference"]}
                            for row in value["paired"])
        paths.append(_write_csv(output / "development-contrasts.csv",
                               ["contrast", "endpoint", "seed", "difference"], rows))
    return paths


def _number(value):
    return "—" if value is None else f"{value:.6f}"


def write_report(data, output, figures):
    summary, stage = data["summary"], data["stage"]
    gate = summary["G3_prime"]
    target = next(cell for cell in gate["cells"] if cell["condition"] == "wide" and cell["need"] == 1.6)
    lines = [f"# {LABELS[stage]}: recorded development results", "",
        "Four reused development seeds; descriptive comparisons after selection. "
        "These are not fresh evaluation results.", "",
        f"G3-prime **{'passes' if gate['passed'] else 'fails'}**: paired R-pool minus L0 "
        f"in the wide/need-1.6 cell is **{target['pool_minus_L0']['mean']:+.6f} of need**, "
        "against the fixed +0.02 criterion. For sharing reports, this is the prerequisite A2 result.", "",
        f"Recorded decision: {summary['decision'] if 'decision' in summary else gate['decision']}.", "",
        "| World | Need | L0 need met | R-pool need met | Paired difference |",
        "|:--|--:|--:|--:|--:|"]
    for cell in gate["cells"]:
        rows = cell["paired"]
        lines.append(f"| {cell['condition']} | {cell['need']:g} | "
                     f"{_number(mean(row['L0'] for row in rows))} | "
                     f"{_number(mean(row['R-pool'] for row in rows))} | "
                     f"{_number(cell['pool_minus_L0']['mean'])} |")
    lines += ["", "The oracle is a true-capacity heuristic, not a consumption ceiling. "
        "Inference accuracy and consumption are reported separately. No evolutionary runs or "
        "experimental model calls are represented.", ""]
    for figure in figures:
        image = next(path for path in figure["files"] if path.suffix == ".png")
        lines += [f"![{figure['id']}]({image.name})", "", figure["caption"], ""]
    if stage != STAGES[2]:
        lines += ["The belief-versus-evidence figure is unavailable at this stage: "
                  "this bank contains no L2/L3 or biased-minority sharing outcomes.", ""]
    lines += ["[Condition means and intervals](condition-means.csv) · "
              "[Recorded learning checkpoints](learning-trajectories.csv) · "
              "[Paired seed differences](paired-effects.csv)", ""]
    if "development_contrasts" in summary:
        lines += ["[Descriptive P1–P5 contrasts](development-contrasts.csv) retain both P5 "
                  "time-average and terminal coverage endpoints. No evaluation endpoint, "
                  "p-value or Holm test is chosen here.", ""]
    lines += ["The loader reconstructs saved aggregates and checks their declared inventories "
              "and prerequisites; rendering runs no episodes, policies or physical transitions and is not an episode "
              "replay. SVG, PDF and PNG exports use Chromatic Field v1. The existing-style "
              "figure manifest connects recorded inputs, rendering sources and outputs. "
              "Use a new output directory for another rendering; prior exports are preserved.", ""]
    path = output / "README.md"
    path.write_text("\n".join(lines))
    return path


def _label(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(Path(path).resolve())


def render(stage, output, **roots):
    data = load(stage, **roots)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory is not empty; preserve existing figures and choose a new directory")
    output.mkdir(parents=True, exist_ok=True)
    figures = render_figures(data, output)
    outputs = [path for figure in figures for path in figure["files"]]
    outputs += export_tables(data, output)
    outputs.append(write_report(data, output, figures))
    helpers = [Path(__file__), ROOT / "swarm_societies/commons_v3/visualize_world_models_v1.py",
               ROOT / "swarm_societies/visualize.py", ROOT / "docs/visual-reference.md",
               *(Path(module.__file__) for module in (base, pool, joint, sharing, base.consequence, base.engine))]
    sources = sorted(set([*data["sources"], *helpers]), key=lambda path: _label(path))
    manifest = {"version": VERSION, "style": "Chromatic Field v1", "stage": stage,
        "study_status": "development; four reused seeds; descriptive intervals after selection",
        "rendering_runs_simulation": False, "evidence_version": data["summary"]["version"],
        "summary_sha256": record_digest(data["summary"]), "seeds": data["seeds"],
        "verification": "saved aggregate reconstruction and declared prerequisite/inventory checks; not episode replay",
        "sources": [{"path": _label(path), "sha256": digest(path)} for path in sources],
        "outputs": [{"path": path.name, "sha256": digest(path)} for path in sorted(outputs)],
        "figures": [{**figure, "files": [path.name for path in figure["files"]]} for figure in figures],
        "versions": {"python": platform.python_version(), "matplotlib": matplotlib.__version__, "numpy": np.__version__}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--output", type=Path, required=True)
    for name, default in (("pool", pool.POOL_ROOT), ("baseline", pool.BASE_ROOT),
                          ("reference", pool.REFERENCE_ROOT), ("calibration", joint.CALIBRATION_ROOT),
                          ("fallback", joint.FALLBACK_ROOT), ("sharing", sharing.SHARING_ROOT)):
        parser.add_argument("--" + name, type=Path, default=Path(default))
    args = parser.parse_args()
    roots = {name + "_root": getattr(args, name) for name in
             ("pool", "baseline", "reference", "calibration", "fallback", "sharing")}
    try:
        result = render(args.stage, args.output, **roots)
    except (OSError, ValueError, KeyError, StopIteration) as error:
        parser.exit(1, f"Could not render recorded development results: {error}\n")
    print(json.dumps({"stage": result["stage"], "figures": len(result["figures"]),
                      "output": str(args.output)}, sort_keys=True))
