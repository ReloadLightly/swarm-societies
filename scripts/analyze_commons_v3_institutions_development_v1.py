#!/usr/bin/env python3
"""Read-only retrospective diagnostics from the completed institutional bank.

Checks every input against the completed manifest and reads one raw episode at
a time. It executes no policy or simulation and never changes the sealed bank.
These are descriptive counts, not a causal or independent qualification test.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path


VERSION = "commons-v3-institutions-recorded-diagnostics-v1"
REPO = Path(__file__).resolve().parents[1]
COUNTS = (
    "episodes", "report_attempts", "paid_report_sends", "failed_report_attempts",
    "paid_report_bytes", "message_cost", "reports_available_before_final_decision",
    "terminal_pending_reports", "episodes_with_report_attempt", "episodes_with_paid_report",
    "cache_attempts", "cache_successes", "retrieve_attempts", "retrieve_successes",
    "exit_attempts", "exit_successes", "member_ticks", "at_affiliated_site_member_ticks",
    "overquota_committed_requests", "actual_violation_ticks", "observed_violation_ticks",
    "self_only_observed_violation_ticks", "externally_observed_violation_ticks",
    "paid_monitor_operations", "audit_subject_receipts", "audit_nonmember_receipts",
    "audit_other_institution_receipts", "sanction_attempts", "successful_sanctions",
    "forfeited_material", "episodes_with_successful_sanction", "terminal_active_zero_bonds",
    "institution_activations", "institution_deactivations", "episodes_without_institution_formation",
    "terminal_active_institutions", "terminal_members", "terminal_cache_material",
    "terminal_released_claims", "political_cost",
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def episode_diagnostics(episode):
    """Count saved commitments and realized outcomes, with explicit zero fields."""
    case, frames, summary = episode["case"], episode["frames"], episode["summary"]
    counts = Counter({key: 0 for key in COUNTS})
    counts["episodes"] = 1
    byte_cost = case["config"]["message_byte_cost"]
    if byte_cost <= 0 or case["config"]["max_messages"] != 1:
        raise ValueError("diagnostic requires the declared positive byte charge and one-message limit")
    for frame in frames:
        measurement = frame["measurement"]
        tick = measurement["tick"]
        agents, actions, intents = measurement["agents"], frame["actions"], frame["intents"]
        if not len(agents) == len(actions) == len(intents) == case["config"]["n_agents"]:
            raise ValueError("decision arrays differ from the declared population")
        monitors = defaultdict(list)
        for event in measurement["events"]:
            if event["kind"] == "monitor" and event["ok"]:
                monitors[event["site"]].append(event["actor"])
                counts["paid_monitor_operations"] += 1
            if event["kind"] in ("cache", "retrieve", "exit") and event["ok"]:
                counts[event["kind"] + "_successes"] += 1
            if event["kind"] == "sanction" and event["ok"]:
                counts["successful_sanctions"] += 1
        for agent, action, intent in zip(agents, actions, intents):
            messages = action["messages"]
            if len(messages) > 1:
                raise ValueError("saved action exceeds the declared one-message limit")
            counts["report_attempts"] += len(messages)
            if messages:
                size = len(messages[0][1].encode("utf-8"))
                paid = agent["message_cost"] > 0.
                if paid and not math.isclose(agent["message_cost"], size * byte_cost, rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError("paid report cost does not match its committed payload")
                counts["paid_report_sends"] += paid
                counts["failed_report_attempts"] += not paid
                counts["paid_report_bytes"] += size if paid else 0
                counts["message_cost"] += agent["message_cost"]
                counts["reports_available_before_final_decision"] += paid and tick < case["horizon"] - 1
                counts["terminal_pending_reports"] += paid and tick == case["horizon"] - 1
            elif agent["message_cost"] != 0.:
                raise ValueError("message cost without a committed report")
            if intent["kind"] in ("cache", "retrieve", "exit", "sanction"):
                counts[intent["kind"] + "_attempts"] += 1
            counts["member_ticks"] += agent["membership_before"] is not None
            bound = agent["bound_quota"] is not None
            counts["at_affiliated_site_member_ticks"] += bound
            counts["overquota_committed_requests"] += bound and action["harvest"] > agent["bound_quota"] + 1e-12
            counts["actual_violation_ticks"] += agent["actual_violation"]
            counts["observed_violation_ticks"] += agent["observed_violation"]
            if agent["actual_violation"]:
                witnesses = monitors.get(agent["site_after"], [])
                if bool(witnesses) != agent["observed_violation"]:
                    raise ValueError("observed violation differs from purchased local monitoring")
                if witnesses:
                    counts["self_only_observed_violation_ticks"] += all(observer == agent["id"] for observer in witnesses)
                    counts["externally_observed_violation_ticks"] += any(observer != agent["id"] for observer in witnesses)
        for site, observers in monitors.items():
            local = [agent for agent in agents if agent["site_after"] == site]
            counts["audit_subject_receipts"] += len(local) * len(observers)
            counts["audit_nonmember_receipts"] += sum(agent["membership_before"] is None for agent in local) * len(observers)
            counts["audit_other_institution_receipts"] += sum(agent["membership_before"] is not None
                and agent["bound_quota"] is None for agent in local) * len(observers)
    final = episode["final_checkpoint"]["payload"]["state"]["state"]
    counts["terminal_active_zero_bonds"] = sum(bond["release_tick"] is None and bond["amount"] == 0.
        for institution in final["institutions"] for bond in institution["bonds"])
    counts["episodes_with_report_attempt"] = int(counts["report_attempts"] > 0)
    counts["episodes_with_paid_report"] = int(counts["paid_report_sends"] > 0)
    counts["episodes_with_successful_sanction"] = int(counts["successful_sanctions"] > 0)
    counts["forfeited_material"] = summary["forfeited"]
    counts["political_cost"] = summary["political_cost"]
    counts["institution_activations"] = summary["institution_activations"]
    counts["institution_deactivations"] = summary["institution_deactivations"]
    counts["episodes_without_institution_formation"] = int(summary["institution_activations"] == 0)
    counts["terminal_active_institutions"] = summary["terminal"]["active_institutions"]
    counts["terminal_members"] = summary["cohorts"]["population"]["terminal_members"]
    counts["terminal_cache_material"] = summary["terminal"]["cache"]
    counts["terminal_released_claims"] = summary["terminal"]["released_claim"]
    if (not math.isclose(counts["message_cost"], summary["cohorts"]["population"]["message_cost"], rel_tol=1e-12, abs_tol=1e-12)
            or counts["actual_violation_ticks"] != summary["cohorts"]["population"]["actual_violations"]
            or counts["observed_violation_ticks"] != summary["cohorts"]["population"]["observed_violations"]):
        raise ValueError("raw diagnostics disagree with saved episode summary")
    return dict(counts)


def analyze(bank):
    bank = Path(bank).resolve()
    manifest_path = bank / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if not manifest["completed"] or manifest["counts"]["episodes"] != 144:
        raise ValueError("requires the completed 144-episode development bank")

    def checked(relative):
        path = (bank / relative).resolve()
        if not path.is_relative_to(bank) or relative not in manifest["files"]:
            raise ValueError("input is outside the sealed artifact manifest")
        if sha256(path) != manifest["files"][relative]:
            raise ValueError(f"sealed input hash differs: {relative}")
        return path

    summary = json.loads(checked("summary.json").read_text())
    if len(summary["episodes"]) != 144 or summary["counts"] != manifest["counts"]:
        raise ValueError("completed summary counts differ from manifest")
    episodes, by_arm, by_context = [], defaultdict(Counter), defaultdict(Counter)
    seen = set()
    for record in summary["episodes"]:
        case = record["case"]
        if case["id"] in seen:
            raise ValueError("duplicate episode identity")
        seen.add(case["id"])
        relative = "episodes/" + case["id"] + ".json.gz"
        with gzip.open(checked(relative), "rt") as stream:
            episode = json.load(stream)
        if episode["case"] != case or episode["summary"] != record["summary"]:
            raise ValueError("raw episode bindings or summary differ from aggregate")
        counts = episode_diagnostics(episode)
        episodes.append({"id": case["id"], "control": case["control"], "capacity": case["capacity"],
            "stubborn_count": case["stubborn_count"], "seed": case["seed"], "arm": case["arm"],
            "raw_sha256": manifest["files"][relative], "counts": counts})
        by_arm[case["arm"]].update(counts)
        by_context[case["control"], case["capacity"], case["stubborn_count"], case["arm"]].update(counts)
        del episode
    return {"version": VERSION,
        "interpretation": "Retrospective descriptive diagnostics of saved records. Repeated seeds and treatments are not independent replications. Counts do not establish mechanism causality or deterrence.",
        "source_sha256": sha256(Path(__file__)), "manifest_sha256": sha256(manifest_path),
        "summary_sha256": manifest["files"]["summary.json"], "checked_raw_episodes": len(episodes),
        "delivery_scope": "A positive material message charge identifies a successful send under the frozen engine. Its one-tick delivery contract determines availability at the next decision; this does not establish that the recipient used or benefited from the report.",
        "response_scope": "Bound-member ticks and committed over-quota requests are observable. The pre-response forager request and alternative responses are not recorded; these counts do not estimate response causality or deterrence.",
        "observation_scope": "Observed violation counts deduplicate subjects per tick. Self-only means every purchased witness is the violator; external means at least one different individual bought a local audit.",
        "exit_scope": "No exit under static acceptable supplied charters does not demonstrate voluntary stability or tested exit responsiveness.",
        "by_arm": {arm: dict(counts) for arm, counts in sorted(by_arm.items())},
        "by_context": [{"control": key[0], "capacity": key[1], "stubborn_count": key[2], "arm": key[3], "counts": dict(counts)}
                       for key, counts in sorted(by_context.items())],
        "episodes": episodes, "simulation_executions": 0, "experimental_model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=REPO / "evidence/commons-v3-institutions-development-v1")
    parser.add_argument("--output", type=Path, required=True, help="New output file outside the sealed bank")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be a new file")
    if args.output.resolve().is_relative_to(args.bank.resolve()):
        parser.error("diagnostic output must remain outside the sealed bank")
    result = analyze(args.bank)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output),
                      "checked_raw_episodes": result["checked_raw_episodes"]}, sort_keys=True))


if __name__ == "__main__":
    main()
