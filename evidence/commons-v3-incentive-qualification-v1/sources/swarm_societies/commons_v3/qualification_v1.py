"""Frozen, recoverable execution and exact replay of qualification banks.

Only audited built-in policies run. Parallelism changes execution order, never
case identity, random events, aggregation order or scientific decisions.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from fractions import Fraction
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

from .engine import Config
from .feasibility_v1 import consumption_certificate, exact_quantity
from .qualification_analysis_v1 import aggregate_ecology, aggregate_incentives, scalar_record
from .qualification_design_v1 import VERSION, SELECTION_SHA256, design
from .qualification_episode_v1 import record_episode

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "swarm_societies/__init__.py", "swarm_societies/commons_v3/__init__.py",
    "swarm_societies/commons_v3/engine.py", "swarm_societies/commons_v3/policies_navigation_v1.py",
    "swarm_societies/commons_v3/feasibility_v1.py", "swarm_societies/commons_v3/qualification_design_v1.py",
    "swarm_societies/commons_v3/qualification_episode_v1.py", "swarm_societies/commons_v3/qualification_analysis_v1.py",
    "swarm_societies/commons_v3/qualification_v1.py", "scripts/run_commons_v3_qualification_v1.py",
    "docs/commons-v3-foundation-protocol.md", "docs/commons-v3-foundation-protocol-v2.md",
    "docs/commons-v3-navigation-protocol-v1.md", "docs/commons-v3-feasibility-v1.md",
    "docs/commons-v3-ecology-qualification-protocol-v1.md", "docs/commons-v3-incentive-qualification-protocol-v1.md",
    "evidence/commons-v3-navigation-v1/selection.json",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def read_case(path):
    with gzip.open(path, "rt") as stream:
        return json.load(stream)


def _publish_bytes(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def _save_json(path, value):
    payload = canonical(value) + b"\n"
    if Path(path).exists():
        if Path(path).read_bytes() != payload:
            raise ValueError("existing JSON differs: " + str(path))
    else:
        _publish_bytes(path, payload)


def prepare(output, stage):
    specification = design(stage)
    if sha(ROOT / "evidence/commons-v3-navigation-v1/selection.json") != SELECTION_SHA256:
        raise ValueError("prior selected-policy record differs")
    selected = read_json(ROOT / "evidence/commons-v3-navigation-v1/selection.json")["candidate"]["parameters"]
    if canonical(next(control["parameters"] for control in specification["controls"] if control["id"] == "selected")) != canonical(selected):
        raise ValueError("selected parameters differ from prior selection")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    pins = {}
    for name in SOURCES:
        destination = output / "sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
        pins[name] = sha(destination)
    _save_json(output / "sources.json", pins)
    _save_json(output / "design.json", specification)
    (output / "cases").mkdir()
    return {"version": VERSION, "stage": stage, "prepared": str(output),
            "design_sha256": sha(output / "design.json"), "sources_sha256": sha(output / "sources.json"),
            **specification["counts"]}


def check_sources(output):
    output = Path(output)
    specification = read_json(output / "design.json")
    if canonical(specification) != canonical(design(specification["stage"])):
        raise ValueError("saved design differs from the frozen registry")
    pins = read_json(output / "sources.json")
    if set(pins) != set(SOURCES):
        raise ValueError("source inventory differs")
    for name, expected in pins.items():
        if sha(ROOT / name) != expected or sha(output / "sources" / name) != expected:
            raise ValueError("frozen source differs: " + name)
    if pins["evidence/commons-v3-navigation-v1/selection.json"] != SELECTION_SHA256:
        raise ValueError("prior selection binding differs")
    return specification


def _expected(specification):
    result = {"design.json", "sources.json", "summary.json", *("sources/" + name for name in SOURCES),
              *("cases/" + case["id"] + ".json.gz" for case in specification["cases"])}
    if specification["stage"] == "incentive":
        result.add("ecology-input.json")
    return result


def _preflight(output, specification):
    if any(Path(output).glob("*-failure.json")):
        raise FileExistsError("failed qualification bank is preserved; use a new version")
    present = {str(path.relative_to(output)) for path in Path(output).rglob("*") if path.is_file()}
    unexpected = present - (_expected(specification) | {"manifest.json"})
    if unexpected:
        raise ValueError("unexpected evidence inventory: " + repr(sorted(unexpected)))


def _manifest(output, specification):
    return {"version": VERSION, "stage": specification["stage"], "complete": True,
            **specification["counts"], "design_sha256": sha(output / "design.json"),
            "sources_sha256": sha(output / "sources.json"),
            "artifacts_sha256": {name: sha(output / name) for name in sorted(_expected(specification))}}


def _certificates(case):
    cfg = Config(**case["config"])
    return [consumption_certificate(cfg, horizon, window_start=start, target_fraction=target)
            for horizon, start in ((256, 0), (512, 0), (512, 384))
            for target in (Fraction(1), Fraction(95, 100))]


def case_record(case, specification):
    episodes = []
    spatial = case["id"] == specification["reference_frames_case"]
    for control in specification["controls"]:
        for intervention in specification["condition_registry"][case["id"]]:
            episode = record_episode(case, control, intervention["aggressive_ids"], spatial=spatial)
            episodes.append({**episode, "condition": intervention["id"], "intervention": intervention})
    if len({episode["weather_sha256"] for episode in episodes}) != 1:
        raise ValueError("paired weather differs")
    if len({episode["initial_state_sha256"] for episode in episodes}) != 1:
        raise ValueError("paired initial state differs")
    record = {"version": VERSION, "stage": specification["stage"], "case": case, "episodes": episodes}
    if specification["stage"] == "ecology":
        record["feasibility_certificates"] = _certificates(case)
        # Compare canonical ledger consumption, not rounded cumulative counters.
        consumption_by_window = {}
        for certificate in record["feasibility_certificates"]:
            start, stop = certificate["window_start"], certificate["horizon"]
            if stop > case["horizon"]:
                continue
            upper = exact_quantity(certificate["bounds"]["consumption_total"])
            if (start, stop) not in consumption_by_window:
                consumption_by_window[start, stop] = [sum((Fraction(x) for row in episode["trajectory"][start:stop]
                                                          for x in row["agent_consumption"]), Fraction())
                                                       for episode in episodes]
            for actual in consumption_by_window[start, stop]:
                if actual > upper:
                    raise ValueError("recorded ledger consumption exceeds physical certificate")
    return record


def _packed_case(case, specification):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as stream:
        stream.write(canonical(case_record(case, specification)))
    return buffer.getvalue()


def _case_binding(saved, case, specification):
    if (saved.get("version") != VERSION or saved.get("stage") != specification["stage"]
            or canonical(saved["case"]) != canonical(case)):
        raise ValueError("case binding differs")
    expected = [(control, intervention) for control in specification["controls"]
                for intervention in specification["condition_registry"][case["id"]]]
    if len(saved["episodes"]) != len(expected):
        raise ValueError("episode inventory differs")
    for episode, (control, intervention) in zip(saved["episodes"], expected):
        if (canonical(episode["case"]) != canonical(case) or canonical(episode["control"]) != canonical(control)
                or episode["condition"] != intervention["id"] or canonical(episode["intervention"]) != canonical(intervention)
                or canonical(episode["aggressive_ids"]) != canonical(intervention["aggressive_ids"])):
            raise ValueError("episode binding differs")
    if specification["stage"] == "ecology" and canonical(saved["feasibility_certificates"]) != canonical(_certificates(case)):
        raise ValueError("physical certificate differs")


def _save_case(output, case, specification, payload, *, verify_only):
    path = output / "cases" / (case["id"] + ".json.gz")
    unpacked = gzip.decompress(payload)
    record = json.loads(unpacked)
    _case_binding(record, case, specification)
    existed = path.exists()
    if existed:
        if canonical(read_case(path)) != unpacked:
            raise ValueError("exact semantic replay differs: " + case["id"])
    elif verify_only:
        raise FileNotFoundError(path)
    else:
        _publish_bytes(path, payload)
    print(json.dumps({"stage": specification["stage"], "case": case["id"],
                      "status": "replayed" if existed else "recorded"}), flush=True)


def _failure(output, label, error):
    _save_json(output / (label + "-failure.json"),
               {"version": VERSION, "label": label, "error": type(error).__name__, "detail": str(error)})


def _execute_cases(output, specification, workers, *, verify_only=False):
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError("workers must be an integer from 1 to 16")
    if workers == 1:
        for case in specification["cases"]:
            try:
                _save_case(output, case, specification, _packed_case(case, specification), verify_only=verify_only)
            except Exception as error:
                if not verify_only:
                    _failure(output, case["id"], error)
                raise
        return
    # Bounded in-flight work prevents completed raw records accumulating in RAM.
    # On failure, stop admission but retain results of all already-running jobs.
    cases = iter(specification["cases"])
    first_error = None
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = {}
        for _ in range(workers):
            case = next(cases, None)
            if case is not None:
                pending[pool.submit(_packed_case, case, specification)] = case
        while pending:
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                case = pending.pop(future)
                try:
                    _save_case(output, case, specification, future.result(), verify_only=verify_only)
                except Exception as error:
                    if not verify_only:
                        _failure(output, case["id"], error)
                    if first_error is None:
                        first_error = error
                if first_error is None:
                    following = next(cases, None)
                    if following is not None:
                        pending[pool.submit(_packed_case, following, specification)] = following
    if first_error is not None:
        raise first_error


def _projections(output, specification):
    records = []
    for case in specification["cases"]:
        record = read_case(output / "cases" / (case["id"] + ".json.gz"))
        _case_binding(record, case, specification)
        records.append(scalar_record(record))
    return records


def _ecology_input(ecology, *, verify_dependency):
    if ecology is None:
        raise ValueError("incentive completion requires the separately completed ecology bank")
    ecology = Path(ecology)
    if read_json(ecology / "design.json")["stage"] != "ecology":
        raise ValueError("dependency is not ecology")
    if verify_dependency:
        verify(ecology, replay=False)
    return {"version": VERSION, "design_sha256": sha(ecology / "design.json"),
            "sources_sha256": sha(ecology / "sources.json"), "manifest_sha256": sha(ecology / "manifest.json"),
            "summary_sha256": sha(ecology / "summary.json"), "summary": read_json(ecology / "summary.json")}


def _aggregate(output, specification):
    rows = _projections(output, specification)
    if specification["stage"] == "ecology":
        summary = aggregate_ecology(rows, specification)
    else:
        dependency = read_json(output / "ecology-input.json")
        if hashlib.sha256(canonical(dependency["summary"]) + b"\n").hexdigest() != dependency["summary_sha256"]:
            raise ValueError("copied ecology summary binding differs")
        summary = aggregate_incentives(rows, specification, dependency["summary"])
        summary["ecology_input_sha256"] = sha(output / "ecology-input.json")
    return {**summary, "design_sha256": sha(output / "design.json"), "sources_sha256": sha(output / "sources.json")}


def run(output, *, workers=1, ecology=None):
    output = Path(output)
    specification = check_sources(output)
    _preflight(output, specification)
    if (output / "manifest.json").exists():
        raise FileExistsError("completed qualification bank is preserved; use verify")
    if specification["stage"] == "incentive":
        _save_json(output / "ecology-input.json", _ecology_input(ecology, verify_dependency=True))
    elif ecology is not None:
        raise ValueError("ecology bank does not accept an ecology dependency")
    _execute_cases(output, specification, workers)
    try:
        check_sources(output)
        result = _aggregate(output, specification)
        _save_json(output / "summary.json", result)
        _save_json(output / "manifest.json", _manifest(output, specification))
    except Exception as error:
        _failure(output, "completion", error)
        raise
    return result


def verify(output, *, replay=True, workers=1, ecology=None):
    output = Path(output)
    specification = check_sources(output)
    _preflight(output, specification)
    present = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    if present != _expected(specification) | {"manifest.json"}:
        raise ValueError("complete evidence inventory differs")
    if canonical(read_json(output / "manifest.json")) != canonical(_manifest(output, specification)):
        raise ValueError("completion manifest differs")
    if specification["stage"] == "incentive":
        # The copied bound summary makes standalone restored-bank verification
        # possible. Supplying ecology additionally validates the original bank.
        if ecology is not None and canonical(read_json(output / "ecology-input.json")) != canonical(_ecology_input(ecology, verify_dependency=True)):
            raise ValueError("original ecology dependency differs")
    elif ecology is not None:
        raise ValueError("ecology bank does not accept an ecology dependency")
    if replay:
        _execute_cases(output, specification, workers, verify_only=True)
    summary = _aggregate(output, specification)
    if canonical(summary) != canonical(read_json(output / "summary.json")):
        raise ValueError("exact aggregate or qualification verdict differs")
    return {"version": VERSION, "stage": specification["stage"], "verified": True,
            "semantic_replay": replay, "manifest_sha256": sha(output / "manifest.json"),
            **specification["counts"], "ecology_original_verified": ecology is not None,
            "experimental_model_calls": 0, "evolutionary_runs": 0}
