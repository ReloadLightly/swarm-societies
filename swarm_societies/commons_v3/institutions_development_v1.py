"""Source-bound execution, recovery and replay of the first political panel.

The prior political runner/registry is untouched. This runner admits exactly
the newly audited DevelopmentPolicy and records complete decision state.
"""
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .engine import Config
from . import politics_v1 as politics
from .political_episode_v1 import _validate_context
from .policies_institutions_development_v1 import DevelopmentPolicy
from .institution_design_v1 import VERSION, CONTRASTS, SELECTION_SHA256, design
from .institution_measurement_v1 import record_tick, summarize

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py",
    "swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/policies_navigation_v1.py",
    "swarm_societies/commons_v3/politics_v1.py", "swarm_societies/commons_v3/policies_institutions_v1.py",
    "swarm_societies/commons_v3/political_episode_v1.py",
    "swarm_societies/commons_v3/policies_institutions_development_v1.py",
    "swarm_societies/commons_v3/institution_design_v1.py",
    "swarm_societies/commons_v3/institution_measurement_v1.py",
    "swarm_societies/commons_v3/institutions_development_v1.py",
    "scripts/run_commons_v3_institutions_development_v1.py",
    "docs/commons-v3-institutions-development-protocol-v1.md",
    "evidence/commons-v3-navigation-v1/selection.json",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pins():
    return {name: sha(ROOT / name) for name in SOURCES}


def _publish(path, data):
    """Publish once; interruptions cannot make a completed but truncated file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def _json(path, value):
    encoded = canonical(value) + b"\n"
    path = Path(path)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != encoded:
            raise ValueError("existing evidence differs: " + str(path))
    else:
        _publish(path, encoded)


class Episode:
    def __init__(self, state, policies, *, pins=None):
        politics.snapshot(state)
        if (type(policies) not in (list, tuple) or len(policies) != state.world.config.n_agents
                or any(type(policy) is not DevelopmentPolicy for policy in policies)):
            raise ValueError("one audited DevelopmentPolicy per individual is required")
        self.state = state
        self.policies = tuple(DevelopmentPolicy.restore(policy.memory()) for policy in policies)
        for policy in self.policies:
            _validate_context(state, policy)
        self.pins = source_pins() if pins is None else dict(pins)
        self.last_actions = self.last_intents = None

    def advance(self):
        previous = [policy.memory() for policy in self.policies]
        try:
            decisions = [policy(packet) for policy, packet in zip(self.policies, politics.observations(self.state))]
            actions, intents = zip(*decisions)
            result = politics.step(self.state, actions, intents)
        except Exception:
            self.policies = tuple(DevelopmentPolicy.restore(memory) for memory in previous)
            raise
        self.state, self.last_actions, self.last_intents = result.state, tuple(actions), tuple(intents)
        return result

    def checkpoint(self):
        payload = json.loads(canonical({"version": VERSION + "-checkpoint", "sources": self.pins,
            "state": politics.snapshot(self.state), "policies": [policy.memory() for policy in self.policies]}))
        return {"payload": payload, "sha256": digest(payload)}


def restore_checkpoint(saved, *, pins=None):
    if type(saved) is not dict or set(saved) != {"payload", "sha256"} or digest(saved["payload"]) != saved["sha256"]:
        raise ValueError("checkpoint envelope/checksum differs")
    payload = saved["payload"]
    current = source_pins() if pins is None else pins
    if (type(payload) is not dict or set(payload) != {"version", "sources", "state", "policies"}
            or payload["version"] != VERSION + "-checkpoint" or payload["sources"] != current
            or type(payload["policies"]) is not list):
        raise ValueError("checkpoint version/source closure differs")
    return Episode(politics.restore(payload["state"]),
                   [DevelopmentPolicy.restore(memory) for memory in payload["policies"]], pins=current)


def _build(case, pins):
    state = politics.initialize(Config(**case["config"]), case["seed"], politics.PoliticalConfig(**case["political_config"]))
    policies = [DevelopmentPolicy(arm="frozen" if case["arm"] == "all_stubborn" else case["arm"],
                                  behavior="stubborn" if a.id in case["stubborn_ids"] else "responsive",
                                  charter=politics.Charter(**case["charter"]), **case["parameters"])
                for a in state.world.agents]
    return Episode(state, policies, pins=pins)


def _frame(episode):
    before = episode.state
    result = episode.advance()
    return json.loads(canonical({"actions": [asdict(a) for a in episode.last_actions],
        "intents": [asdict(i) for i in episode.last_intents],
        "measurement": record_tick(before, result, episode.last_actions, episode.last_intents)}))


def _summarize(case, initial, final, frames):
    stubborn = case["stubborn_ids"]
    cohorts = {"eligible": [a for a in range(case["config"]["n_agents"]) if a not in stubborn], "stubborn": stubborn}
    return summarize(initial, final, [frame["measurement"] for frame in frames],
                     cohorts=cohorts, late_window=min(64, len(frames)))


def record_episode(case, *, pins=None):
    pins = source_pins() if pins is None else pins
    episode = _build(case, pins)
    initial, initial_checkpoint = episode.state, episode.checkpoint()
    frames, midpoint = [], None
    for tick in range(case["horizon"]):
        frames.append(_frame(episode))
        if tick + 1 == case["horizon"] // 2:
            midpoint = episode.checkpoint()
    final = episode.checkpoint()
    return json.loads(canonical({"version": VERSION + "-episode", "case": case,
        "initial_checkpoint": initial_checkpoint, "midpoint_checkpoint": midpoint, "final_checkpoint": final,
        "frames": frames, "summary": _summarize(case, initial, episode.state, frames)}))


def check_episode(saved, case, pins, *, replay=False):
    if (type(saved) is not dict or saved.get("version") != VERSION + "-episode"
            or saved.get("case") != case or len(saved.get("frames", [])) != case["horizon"]):
        raise ValueError("episode identity/horizon differs")
    initial = restore_checkpoint(saved["initial_checkpoint"], pins=pins)
    final = restore_checkpoint(saved["final_checkpoint"], pins=pins)
    midpoint = restore_checkpoint(saved["midpoint_checkpoint"], pins=pins)
    if initial.checkpoint() != _build(case, pins).checkpoint():
        raise ValueError("initial state/policies differ from case")
    if (midpoint.state.world.tick != case["horizon"] // 2 or final.state.world.tick != case["horizon"]):
        raise ValueError("checkpoint timing differs")
    expected_summary = _summarize(case, initial.state, final.state, saved["frames"])
    if canonical(expected_summary) != canonical(saved["summary"]):
        raise ValueError("saved measurement summary differs")
    if replay:
        for tick, frame in enumerate(saved["frames"]):
            if _frame(initial) != frame:
                raise ValueError(f"full decision replay differs at tick {tick}")
            if tick + 1 == case["horizon"] // 2 and initial.checkpoint() != saved["midpoint_checkpoint"]:
                raise ValueError("midpoint policy/state differs")
        if initial.checkpoint() != saved["final_checkpoint"]:
            raise ValueError("final policy/state differs")
        for tick in range(case["horizon"] // 2, case["horizon"]):
            if _frame(midpoint) != saved["frames"][tick]:
                raise ValueError("restored midpoint decisions differ")
        if midpoint.checkpoint() != saved["final_checkpoint"]:
            raise ValueError("midpoint continuation final state differs")
    return saved["summary"]


def prepare(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    pins = source_pins()
    if pins["evidence/commons-v3-navigation-v1/selection.json"] != SELECTION_SHA256:
        raise ValueError("frozen selected navigation identity differs")
    for name, expected in pins.items():
        target = output / "sources" / name
        _publish(target, (ROOT / name).read_bytes())
        if sha(target) != expected:
            raise ValueError("source changed during preparation")
    _json(output / "sources.json", pins)
    _json(output / "design.json", design())
    (output / "episodes").mkdir()
    return {"prepared": True, "version": VERSION, "sources_sha256": sha(output / "sources.json"),
            "design_sha256": sha(output / "design.json"), **design()["counts"]}


def check_sources(output):
    output = Path(output)
    specification = json.loads((output / "design.json").read_text())
    pins = json.loads((output / "sources.json").read_text())
    if specification != design() or pins != source_pins():
        raise ValueError("frozen executable design/source closure differs")
    for name, expected in pins.items():
        if sha(output / "sources" / name) != expected:
            raise ValueError("saved frozen source differs")
    return specification, pins


def read_episode(path):
    if Path(path).is_symlink():
        raise ValueError("episode cannot be a symbolic link")
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def _worker(job):
    path, case, pins, replay, allow_record = job
    path = Path(path)
    if path.exists():
        summary = check_episode(read_episode(path), case, pins, replay=replay or allow_record)
        status = "replayed" if replay else "preserved"
    elif not allow_record:
        raise FileNotFoundError(path)
    else:
        saved = record_episode(case, pins=pins)
        _publish(path, gzip.compress(canonical(saved) + b"\n", mtime=0))
        summary, status = saved["summary"], "recorded"
    return {"case": case, "summary": summary}, status


def aggregate(rows):
    rows = sorted(rows, key=lambda row: row["case"]["id"])
    lookup = {(r["case"]["control"], r["case"]["capacity"], r["case"]["stubborn_count"],
               r["case"]["seed"], r["case"]["arm"]): r["summary"] for r in rows}
    contrasts = []
    # Do not pool repeated arms/backgrounds as independent environmental seeds.
    contexts = sorted({(r["case"]["control"], r["case"]["capacity"], r["case"]["stubborn_count"])
                       for r in rows if r["case"]["arm"] != "all_stubborn"})
    for control, capacity, stubborn in contexts:
        seeds = sorted({r["case"]["seed"] for r in rows if
                        (r["case"]["control"], r["case"]["capacity"], r["case"]["stubborn_count"])
                        == (control, capacity, stubborn)})
        for left, right in CONTRASTS:
            values = []
            for seed in seeds:
                l = lookup[control, capacity, stubborn, seed, left]["cohorts"]
                r = lookup[control, capacity, stubborn, seed, right]["cohorts"]
                row = {"seed": seed}
                for name, cohort, metric in (("population", "population", "consumption_need_fraction"),
                    ("late_population", "population", "late_consumption_need_fraction"),
                    ("eligible", "eligible", "consumption_need_fraction"),
                    ("stubborn", "stubborn", "consumption_need_fraction")):
                    lv, rv = l[cohort][metric], r[cohort][metric]
                    row[name] = None if lv is None else lv - rv
                values.append(row)
            result = {"control": control, "capacity": capacity, "stubborn_count": stubborn,
                      "left": left, "right": right, "seed_values": values}
            for label, reducer in (("mean", lambda v: sum(v) / len(v)), ("min", min), ("max", max)):
                result[label] = {name: None if values[0][name] is None else reducer([v[name] for v in values])
                                 for name in ("population", "late_population", "eligible", "stubborn")}
            contrasts.append(result)
    return {"version": VERSION + "-summary", "episodes": rows, "contrasts": contrasts,
        "counts": {"episodes": len(rows), "physical_ticks": sum(r["case"]["horizon"] for r in rows),
                   "agent_decisions": sum(r["case"]["horizon"] * r["case"]["config"]["n_agents"] for r in rows)},
        "interpretation": "Four-seed supplied-policy development; means and ranges are descriptive, no qualification or selection.",
        "experimental_model_calls": 0, "evolutionary_runs": 0, "policy_selection_runs": 0}


def _jobs(output, specification, pins, replay, allow_record=False):
    expected = {case["id"] + ".json.gz" for case in specification["cases"]}
    found = {path.name for path in (output / "episodes").iterdir() if not path.name.startswith(".pending-")}
    if found - expected:
        raise ValueError("unexpected episode identity in bank")
    return [(str(output / "episodes" / (case["id"] + ".json.gz")), case, pins, replay, allow_record)
            for case in specification["cases"]]


def _collect(jobs, workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("workers must be between 1 and 8")
    rows = []
    if workers == 1:
        results = map(_worker, jobs)
        for row, status in results:
            print(json.dumps({"case": row["case"]["id"], "status": status}), flush=True)
            rows.append(row)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            iterator = iter(jobs)
            pending = {pool.submit(_worker, job) for job in [next(iterator, None) for _ in range(workers)] if job is not None}
            try:
                while pending:
                    finished, pending = wait(pending, return_when=FIRST_COMPLETED)
                    # Inspect the complete ready batch before admitting more
                    # work; a failed episode never launches a follow-on case.
                    batch = [future.result() for future in finished]
                    for row, status in batch:
                        print(json.dumps({"case": row["case"]["id"], "status": status}), flush=True)
                        rows.append(row)
                    for _ in batch:
                        job = next(iterator, None)
                        if job is not None:
                            pending.add(pool.submit(_worker, job))
            except BaseException:
                for future in pending:
                    future.cancel()
                raise
    return rows


def run(output, *, workers=4):
    output = Path(output)
    specification, pins = check_sources(output)
    if (output / "manifest.json").exists():
        raise ValueError("completed bank is sealed; use verify instead of run")
    # A POSIX exclusive lock prevents competing resume processes without
    # depending on process IDs being visible across execution namespaces.
    import fcntl
    with (output / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = _collect(_jobs(output, specification, pins, False, True), workers)
        check_sources(output)
        summary = aggregate(rows)
        if summary["counts"] != specification["counts"]:
            raise ValueError("completed episode inventory differs")
        _json(output / "summary.json", summary)
        files = {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*"))
                 if path.is_file() and path.name not in (".run.lock", "manifest.json") and not path.name.startswith(".pending-")}
        _json(output / "manifest.json", {"version": VERSION + "-completion", "files": files,
                                        "counts": summary["counts"], "completed": True})
        return {"completed": True, **summary["counts"], "manifest_sha256": sha(output / "manifest.json")}


def verify(output, *, workers=4, replay=True):
    output = Path(output)
    specification, pins = check_sources(output)
    manifest = json.loads((output / "manifest.json").read_text())
    files = {str(path.relative_to(output)): sha(path) for path in sorted(output.rglob("*"))
             if path.is_file() and path.name not in (".run.lock", "manifest.json") and not path.name.startswith(".pending-")}
    if manifest != {"version": VERSION + "-completion", "files": files,
                    "counts": specification["counts"], "completed": True}:
        raise ValueError("sealed artifact manifest differs")
    jobs = _jobs(output, specification, pins, replay)
    if any(not Path(job[0]).is_file() for job in jobs):
        raise ValueError("completed bank is missing a declared episode")
    rows = _collect(jobs, workers)
    summary = aggregate(rows)
    if canonical(summary) + b"\n" != (output / "summary.json").read_bytes():
        raise ValueError("exact aggregate reconstruction differs")
    return {"version": VERSION, "verified": True, "semantic_replay": replay,
        "midpoint_policy_continuation": replay, **specification["counts"],
        "manifest_sha256": sha(output / "manifest.json"), "experimental_model_calls": 0, "evolutionary_runs": 0}
