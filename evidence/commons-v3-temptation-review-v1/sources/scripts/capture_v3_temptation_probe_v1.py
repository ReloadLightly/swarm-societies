#!/usr/bin/env python3
"""Capture/replay the user-supplied temptation probe without changing its source.

The capture hook saves record_episode's unchanged return value, then returns
it to the original caller. The original script runs through runpy as __main__.
This Linux/fork launcher leaves the original ProcessPoolExecutor unchanged;
CPU affinity may be bounded externally with taskset.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stdout
import gzip
import hashlib
import io
import json
import math
import multiprocessing
import os
from pathlib import Path
import runpy
import shutil
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_societies.commons_v3 import qualification_episode_v1 as recorder
import v3_temptation_probe as probe

VERSION = "commons-v3-temptation-probe-capture-v1"
ORIGINAL = recorder.record_episode
OUTPUT = None
CORE = ("swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py",
        "swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/policies_navigation_v1.py",
        "swarm_societies/commons_v3/qualification_design_v1.py", "swarm_societies/commons_v3/qualification_episode_v1.py")
SOURCES = (*CORE, "scripts/v3_temptation_probe.py", "scripts/capture_v3_temptation_probe_v1.py")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else canonical(value) + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def capture_episode(case, control, aggressive_ids, *, spatial=False):
    result = ORIGINAL(case, control, aggressive_ids, spatial=spatial)
    name = f"cap{int(case['config']['inventory_capacity']):02d}-s{case['seed']}-aggressive{len(aggressive_ids):02d}.json.gz"
    save(OUTPUT / "cases" / name, gzip.compress(canonical(result) + b"\n", mtime=0))
    return result


def declared_seeds(value):
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if (key == "seed" or key.endswith("_seed")) and type(item) is int:
                found.add(item)
            if (key == "seeds" or key.endswith("_seeds")) and isinstance(item, list):
                found.update(x for x in item if type(x) is int)
            found.update(declared_seeds(item))
    elif isinstance(value, list):
        for item in value:
            found.update(declared_seeds(item))
    return found


def prepare(output):
    if output.exists():
        raise ValueError("capture requires a new output directory")
    frozen = read(ROOT / "evidence/commons-v3-incentive-qualification-v1/sources.json")
    for name in CORE:
        if sha(ROOT / name) != frozen[name]:
            raise ValueError(f"frozen execution source changed: {name}")
    checks = []
    designs = sorted((ROOT / "evidence").glob("*/design.json"))
    for path in designs:
        seeds = declared_seeds(read(path))
        overlap = sorted(seeds.intersection(probe.SEEDS))
        if overlap:
            raise ValueError(f"probe seeds overlap {path}: {overlap}")
        checks.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path),
                       "declared_seeds": sorted(seeds), "overlap": overlap})
    output.mkdir(parents=True)
    pins = {}
    for name in (*SOURCES, *(str(p.relative_to(ROOT)) for p in designs)):
        target = output / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        pins[name] = sha(target)
    save(output / "sources.json", pins)
    save(output / "design.json", {
        "version": VERSION, "status": "exploratory reproduction of supplied external review probe",
        "original_script": "scripts/v3_temptation_probe.py", "original_sha256": pins["scripts/v3_temptation_probe.py"],
        "execution": "Execute supplied source unchanged via runpy; save each unchanged recorder return value before returning it to the original caller.",
        "seeds": list(probe.SEEDS), "seed_disjointness": checks,
        "control": probe.CONTROL, "focal_id": probe.FOCAL, "need": probe.NEED,
        "panels": probe.PANELS, "horizon": 256, "aggressive_peer_counts": [0, 23],
        "wealth_weights": [0., .05, .2], "descriptive_t_critical_df7": 2.365,
        "counts": {"episodes": 64, "physical_ticks": 16384, "agent_decisions": 393216, "independent_seeds": 8},
        "qualification_data": False, "experimental_model_calls": 0, "evolutionary_runs": 0,
        "numerical_selection_runs": 0,
        "limits": "Ordinary descriptive intervals; supplied whole-policy substitution, one control and one focal identity; no best-response, equilibrium or formal game-type qualification.",
    })


def check_sources(output):
    for name, expected in read(output / "sources.json").items():
        if sha(ROOT / name) != expected or sha(output / "sources" / name) != expected:
            raise ValueError(f"source changed: {name}")


def interval(values):
    mean = statistics.mean(values)
    half = 2.365 * statistics.stdev(values) / math.sqrt(len(values))
    return {"mean": mean, "lower": mean - half, "upper": mean + half, "seed_values": values}


def summarize(output):
    lines, panels = [], []
    for panel, updates in probe.PANELS.items():
        capacity = int(updates.get("inventory_capacity", 80))
        rows = {}
        for seed in probe.SEEDS:
            for count in (0, 1, 23, 24):
                with gzip.open(output / "cases" / f"cap{capacity:02d}-s{seed}-aggressive{count:02d}.json.gz", "rt") as stream:
                    episode = json.load(stream)
                rows[seed, count] = {"focal": episode["agents"][probe.FOCAL],
                    "population": episode["summary"], "initial_state_sha256": episode["initial_state_sha256"],
                    "weather_sha256": episode["weather_sha256"],
                    "peer_consumption_per_tick": statistics.mean(a["consumption_per_tick"] for a in episode["agents"] if a["id"] != probe.FOCAL)}
        base = statistics.mean(rows[seed, 0]["focal"]["consumption_per_tick"] for seed in probe.SEEDS) / probe.NEED
        lines.append(f"\n== {panel}: restrained focal among restrained peers consumes {base:.2%} of need")
        contrasts = []
        for peers, label, pair in ((0, "0 aggressive peers", (0, 1)), (23, "23 aggressive peers", (23, 24))):
            matched = [(rows[seed, pair[0]], rows[seed, pair[1]]) for seed in probe.SEEDS]
            if any(a["initial_state_sha256"] != b["initial_state_sha256"] or a["weather_sha256"] != b["weather_sha256"] for a, b in matched):
                raise ValueError("paired initialization/weather changed")
            weights = {}
            for w in ("0.0", "0.05", "0.2"):
                gains = [(b["focal"]["utility"][w] - a["focal"]["utility"][w]) / probe.NEED for a, b in matched]
                inventory = [float(w) * (b["focal"]["terminal_inventory"] - a["focal"]["terminal_inventory"]) / (256 * probe.NEED) for a, b in matched]
                lines.append(f"  {label:20} weight {w:4}: focal gain / need {probe.interval(gains)}")
                weights[w] = {"focal_gain_fraction": interval(gains), "terminal_inventory_contribution_fraction": interval(inventory),
                    "inventory_share_of_mean_gain": sum(inventory) / sum(gains) if sum(gains) else None}
            contrasts.append({"aggressive_peers": peers, "peer_prevalence": peers / 23, "weights": weights,
                "peer_consumption_change_fraction": interval([(b["peer_consumption_per_tick"] - a["peer_consumption_per_tick"]) / probe.NEED for a, b in matched]),
                "seed_rows": [{"seed": seed, "restrained": a, "aggressive": b} for seed, (a, b) in zip(probe.SEEDS, matched)]})
        panels.append({"panel": panel, "inventory_capacity": capacity, "restrained_focal_consumption_fraction": base, "contrasts": contrasts})
    return {"version": VERSION, "panels": panels, "design_sha256": sha(output / "design.json"),
            "sources_sha256": sha(output / "sources.json"), "episodes": 64,
            "experimental_model_calls": 0, "evolutionary_runs": 0, "numerical_selection_runs": 0}, "\n".join(lines) + "\n"


def replay(path):
    with gzip.open(path, "rt") as stream:
        saved = json.load(stream)
    result = ORIGINAL(saved["case"], saved["control"], saved["aggressive_ids"])
    if canonical(result) != canonical(saved):
        raise ValueError(f"episode replay differs: {path}")
    return path.name


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capture", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    if args.receipt and args.receipt.exists():
        parser.error("receipt must be a new path")
    if args.command == "capture":
        if multiprocessing.get_start_method() != "fork":
            raise ValueError("transparent capture requires Linux fork start method")
        prepare(OUTPUT)
        text = io.StringIO()
        recorder.record_episode = capture_episode
        try:
            with redirect_stdout(text):
                runpy.run_path(str(ROOT / "scripts/v3_temptation_probe.py"), run_name="__main__")
        finally:
            recorder.record_episode = ORIGINAL
        save(OUTPUT / "original-stdout.txt", text.getvalue().encode())
        check_sources(OUTPUT)
        summary, reconstructed = summarize(OUTPUT)
        if reconstructed != text.getvalue():
            raise ValueError("captured original stdout differs from raw-record recomputation")
        save(OUTPUT / "summary.json", summary)
        paths = sorted((OUTPUT / "cases").glob("*.json.gz"))
        if len(paths) != 64:
            raise ValueError("wrong episode count")
        save(OUTPUT / "manifest.json", {"version": VERSION,
            "files": {str(p.relative_to(OUTPUT)): {"sha256": sha(p), "bytes": p.stat().st_size}
                      for p in [OUTPUT / name for name in ("design.json", "sources.json", "summary.json", "original-stdout.txt")] + paths}})
        print(text.getvalue(), end="")
        result = {"episodes_captured": len(paths), "stdout_recomputed_exactly": True, "manifest_sha256": sha(OUTPUT / "manifest.json")}
    else:
        check_sources(OUTPUT)
        manifest = read(OUTPUT / "manifest.json")
        for name, pin in manifest["files"].items():
            if sha(OUTPUT / name) != pin["sha256"] or (OUTPUT / name).stat().st_size != pin["bytes"]:
                raise ValueError(f"manifest mismatch: {name}")
        paths = sorted((OUTPUT / "cases").glob("*.json.gz"))
        if len(paths) != 64:
            raise ValueError("wrong episode count")
        with ProcessPoolExecutor(max_workers=2) as pool:
            replayed = list(pool.map(replay, paths))
        summary, stdout = summarize(OUTPUT)
        if canonical(summary) != canonical(read(OUTPUT / "summary.json")) or stdout != (OUTPUT / "original-stdout.txt").read_text():
            raise ValueError("summary or original stdout differs")
        result = {"episodes_exactly_replayed": len(replayed), "stdout_recomputed_exactly": True,
                  "summary_recomputed_exactly": True, "source_hashes_verified": True,
                  "manifest_sha256": sha(OUTPUT / "manifest.json")}
    if args.receipt:
        save(args.receipt, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
