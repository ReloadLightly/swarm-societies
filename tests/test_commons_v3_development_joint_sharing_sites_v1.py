"""Unknown-rate sharing authorization fixtures; no development episode runs."""
from copy import deepcopy
from dataclasses import replace

import pytest

from scripts import resume_commons_v3_joint_development_v1 as recovery
from swarm_societies.commons_v3 import development_joint_sites_v1 as joint
from swarm_societies.commons_v3 import development_joint_sharing_sites_v1 as development
from swarm_societies.commons_v3.development_navigation_v1 import (
    _save_json, _save_record, canonical, digest,
)


def complete_record(job, *, version=joint.VERSION, share=.8):
    """Complete synthetic topology, without executing the declared worlds."""
    state = joint.worlds.initialize(job["condition"], job["need"], job["seed"])
    state = replace(state, config=replace(state.config, max_messages=4))
    initial = joint.engine.snapshot(state)
    pairs = [[agent.id, patch.id] for agent in state.agents for patch in state.patches]
    summary = dict.fromkeys(recovery.SUMMARY_KEYS, .8)
    summary["share_of_need"] = share
    return {
        "version": version, "job": deepcopy(job), "horizon": joint.HORIZON,
        "rate_known": False, "rate_prior": dict(joint.RATE_PRIOR),
        "initial_snapshot": initial,
        "initial_physical_sha256": joint.physical_initial_digest(initial),
        "final_snapshot": joint.engine.snapshot(replace(state, tick=joint.HORIZON)),
        "trajectory_sha256": "0" * 64, "weather_sha256": "1" * 64,
        "final_policy_memory_sha256": ["2" * 64] * len(state.agents),
        "final_pool_memory_sha256": "3" * 64 if job["arm"] == "R-pool" else None,
        "ticks": [{**dict.fromkeys(recovery.MATERIAL_KEYS, 0), "tick": tick}
                  for tick in range(1, joint.HORIZON + 1)],
        "belief_ticks": [{**dict.fromkeys(recovery.BELIEF_KEYS, .2), "tick": tick}
                         for tick in range(joint.HORIZON + 1)],
        "belief_pair_columns": list(joint.PAIR_COLUMNS),
        "belief_checkpoints": [{"tick": tick, "pairs": [pair + [0] * 7 for pair in pairs]}
                               for tick in joint.BELIEF_CHECKPOINTS],
        "agents": [{"id": agent.id} for agent in state.agents],
        "first_within10_columns": ["agent", "site", "first_tick_or_null"],
        "first_within10": [pair + [None] for pair in pairs],
        "summary": summary,
    }


def fallback_bank(monkeypatch, root, *, passed=True):
    """Stub older prerequisites, retaining the actual A2 aggregate and gate."""
    references, known, calibration = [], {"G3_prime": {"passed": False}}, {"G2": {"passed": True}}
    monkeypatch.setattr(joint, "_load_prerequisites", lambda *args: (references, known, calibration))
    monkeypatch.setattr(joint.base, "_paired_worlds", lambda *args: None)
    # A2 descriptive metrics are separately covered by pool tests. Its gate is real.
    monkeypatch.setattr(joint.pool, "comparison_cells", lambda *args, **kwargs: [])
    records = [complete_record(job, share=(.83 if passed else .81) if job["arm"] == "R-pool" else .8)
               for job in joint.fallback_jobs()]
    for record in records:
        _save_record(joint.base._path(root, record["job"]), record)
    summary = joint.summarize(records, references, known, calibration)
    _save_json(root / "summary.json", summary)
    return records, summary


def load_fallback(root):
    return development.load_fallback(root, "unused-pool", "unused-baseline", "unused-references", "unused-calibration")


def test_exactly_eighty_declared_sharing_cases_reuse_the_selected_quantile_and_seeds():
    jobs = development.sharing_jobs()
    assert len(jobs) == len({joint.base.case_id(job) for job in jobs}) == 80
    assert {job["arm"] for job in jobs} == {"L1", "L2", "L3", "L2-biased", "L3-biased"}
    assert {job["seed"] for job in jobs} == {90001, 90002, 90003, 90004}
    assert {(job["condition"], job["need"]) for job in jobs} == {
        ("moderate", 1.2), ("moderate", 1.6), ("wide", 1.2), ("wide", 1.6),
    }
    assert {job["q"] for job in jobs} == {.25}
    assert {job["phi"] for job in jobs} == {.375}


@pytest.mark.parametrize("mutation", [{"arm": "L0"}, {"arm": "R-pool"}, {"seed": 90005},
                                     {"q": .5}, {"phi": .5}, {"need": 2.}])
def test_outside_menu_is_rejected_before_initializing_a_world(monkeypatch, mutation):
    monkeypatch.setattr(joint.worlds, "initialize", lambda *args: pytest.fail("initialized an unauthorized world"))
    with pytest.raises(ValueError):
        development.run_episode({**development.sharing_jobs()[0], **mutation})


def test_loader_reconstructs_passed_gate_and_reuses_exactly_the_sixteen_unknown_L0_records(monkeypatch, tmp_path):
    records, summary = fallback_bank(monkeypatch, tmp_path)
    before = {path.name: path.read_bytes() for path in (tmp_path / "cases").iterdir()}
    l0, references, loaded = load_fallback(tmp_path)
    assert l0 == [record for record in records if record["job"]["arm"] == "L0"]
    assert references == [] and loaded == summary
    assert loaded["G3_prime"]["passed"]
    assert before == {path.name: path.read_bytes() for path in (tmp_path / "cases").iterdir()}


@pytest.mark.parametrize("damage", ["missing", "material", "belief", "terminal", "prior", "version", "summary"])
def test_incomplete_or_changed_fallback_records_cannot_authorize_workers(monkeypatch, tmp_path, damage):
    root = tmp_path / "fallback"
    records, _ = fallback_bank(monkeypatch, root)
    record = deepcopy(records[0])
    path = joint.base._path(root, record["job"])
    path.unlink()
    if damage in ("material", "belief"):
        record["ticks" if damage == "material" else "belief_ticks"].pop()
    elif damage == "terminal":
        record["final_snapshot"]["state"]["tick"] -= 1
    elif damage == "prior":
        record["rate_prior"]["high"] = .96
    elif damage == "version":
        record["version"] = "known-rate"
    elif damage == "summary":
        record["summary"].pop("message_cost")
    if damage != "missing":
        _save_record(path, record)
    monkeypatch.setattr(joint.pool, "_run_jobs", lambda *a, **kw: pytest.fail("submitted before valid A2 gate"))
    with pytest.raises(ValueError):
        development.run(tmp_path / "sharing", fallback_root=root)
    assert not (tmp_path / "sharing" / "summary.json").exists()


@pytest.mark.parametrize("forge_saved_pass", [False, True])
def test_failed_or_forged_fallback_gate_submits_no_sharing_jobs(monkeypatch, tmp_path, forge_saved_pass):
    root = tmp_path / "fallback"
    _, saved = fallback_bank(monkeypatch, root, passed=False)
    if forge_saved_pass:
        saved["G3_prime"]["passed"] = True
        (root / "summary.json").write_bytes(canonical(saved))
    monkeypatch.setattr(joint.pool, "_run_jobs", lambda *a, **kw: pytest.fail("submitted after failed or forged gate"))
    with pytest.raises(ValueError):
        development.run(tmp_path / "sharing", fallback_root=root)


def test_completed_sharing_bank_is_not_restarted_or_changed(monkeypatch, tmp_path):
    path = tmp_path / "summary.json"
    path.write_text("{}")
    monkeypatch.setattr(development, "load_fallback", lambda *a: pytest.fail("restarted completed sharing"))
    with pytest.raises(ValueError, match="completed"):
        development.run(tmp_path)
    assert path.read_text() == "{}"


def test_pending_fallback_without_aggregate_cannot_start_sharing(monkeypatch, tmp_path):
    monkeypatch.setattr(joint.pool, "_run_jobs", lambda *a, **kw: pytest.fail("submitted while A2 is pending"))
    monkeypatch.setattr(joint, "_load_prerequisites", lambda *a: pytest.fail("pending fallback accepted"))
    with pytest.raises(ValueError, match="incomplete"):
        development.run(tmp_path / "sharing", fallback_root=tmp_path / "pending")
    assert not (tmp_path / "sharing").exists()


def test_sharing_summary_preserves_real_descriptive_contrasts_and_stops_at_review():
    shares = {"L0": .8, "L1": .81, "L2": .84, "L3": .85, "L2-biased": .82, "L3-biased": .79}
    l0 = [complete_record(job) for job in joint.base.candidate_jobs(.25)]
    rows = [complete_record(job, version=development.VERSION, share=shares[job["arm"]])
            for job in development.sharing_jobs()]
    fallback = {"version": joint.VERSION, "rate_known": False,
                "rate_prior": dict(joint.RATE_PRIOR), "G3_prime": {"passed": True},
                "joint_calibration": {"G2": {"passed": True}}}
    before = digest([l0, fallback])
    summary = development.summarize(rows, l0, [], fallback)
    assert summary["episodes"] == 80 and summary["L0_episodes_reused"] == 16
    assert summary["rate_known"] is False and summary["rate_prior"] == joint.RATE_PRIOR
    assert summary["fresh_evaluation_episodes"] == summary["experimental_model_calls"] == summary["evolutionary_runs"] == 0
    assert summary["decision"] == "stop at development review and report; no freeze or fresh evaluation"
    assert len(summary["cells"]) == 4
    for cell in summary["cells"]:
        contrasts = cell["contrasts"]
        assert contrasts["L2_minus_L0"]["statistics"]["share_of_need"]["mean"] == pytest.approx(.04)
        assert contrasts["L3-biased_minus_L2-biased"]["statistics"]["share_of_need"]["mean"] == pytest.approx(-.03)
    assert "descriptive" in summary["development_contrasts"]["status"]
    assert summary["development_contrasts"]["contrasts"]["P1"]["statistics"]["mean"] == pytest.approx(.04)
    assert summary["development_contrasts"]["contrasts"]["P4"]["statistics"]["mean"] == pytest.approx(-.03)
    assert digest([l0, fallback]) == before


@pytest.mark.parametrize("arm", ["L1", "L2", "L3-biased"])
def test_dispatch_uses_calibrated_joint_policy_and_only_the_declared_biased_members(monkeypatch, arm):
    from swarm_societies.commons_v3.calibration_joint_sites_v1 import RESOLUTION
    from swarm_societies.commons_v3.policies_joint_sharing_sites_v1 import UnknownSharingForager

    job = next(job for job in development.sharing_jobs() if job["arm"] == arm)
    captured = {}

    def capture(job, state, policies, coordinator=None):
        captured.update(state=state, policies=policies, coordinator=coordinator)
        return {"version": joint.VERSION, "job": job}

    monkeypatch.setattr(joint, "_record_unknown_episode", capture)
    record = development.run_episode(job)
    assert record["version"] == development.VERSION
    assert captured["coordinator"] is None
    assert captured["state"].config.max_messages == 4
    assert len(captured["policies"]) == 24
    for agent, policy in zip(captured["state"].agents, captured["policies"]):
        assert isinstance(policy, UnknownSharingForager)
        assert policy.arm == arm.split("-")[0]
        assert policy.q == .25 and policy.phi == .375
        assert policy.biased == (arm.endswith("-biased") and agent.id in joint.BIASED_IDS)
        assert {key: getattr(policy.joint, key) for key in RESOLUTION} == RESOLUTION


@pytest.mark.parametrize("arm", ["L1", "L2", "L3", "L3-biased"])
def test_tiny_paid_sharing_recorder_replays_with_terminal_assimilation_at_calibrated_resolution(monkeypatch, arm):
    from swarm_societies.commons_v3 import observations_joint_sites_v1 as adapter
    from swarm_societies.commons_v3.calibration_joint_sites_v1 import RESOLUTION
    from swarm_societies.commons_v3.policies_joint_sharing_sites_v1 import UnknownSharingForager

    # The frozen communicating contract requires four available message slots,
    # and engine.Config therefore requires at least four agents.
    config = joint.engine.Config(width=6, height=3, n_agents=4, n_patches=2,
        need=1.2, sensing_radius=2, max_messages=4,
        site_capacities=(20., 60.), initial_site_stocks=(12., 36.))
    state = joint.engine.WorldState(config, 42, 0,
        (joint.engine.AgentState(0, 1, 1, 3.), joint.engine.AgentState(1, 1, 1, 3.),
         joint.engine.AgentState(2, 4, 1, 3.), joint.engine.AgentState(3, 4, 1, 3.)),
        (joint.engine.PatchState(0, 1, 1, 12.), joint.engine.PatchState(1, 4, 1, 36.)))
    job = {"arm": arm, "need": 1.2, "phi": .375, "q": .25,
           "seed": 42, "condition": "unit fixture"}
    original_observations = adapter.observations
    observed_ticks = []

    def checked_observations(current, previous_result=None):
        packets = original_observations(current, previous_result)
        observed_ticks.append(current.tick)
        for packet in packets:
            assert "renewal_rate" not in packet["ecology"]
            assert packet["ecology"]["renewal_rate_prior"] == joint.RATE_PRIOR
            assert all("capacity" not in site for site in packet["sites"])
        return packets

    monkeypatch.setattr(adapter, "observations", checked_observations)

    def execute():
        policies = [UnknownSharingForager(arm.split("-")[0], phi=.375, q=.25,
                    biased=arm.endswith("-biased") and agent.id in joint.BIASED_IDS,
                    **RESOLUTION) for agent in state.agents]
        for policy in policies:
            assert {key: getattr(policy.joint, key) for key in RESOLUTION} == RESOLUTION
        return joint._record_unknown_episode(job, state, policies, horizon=4), policies

    recorded, policies = execute()
    assert recorded == execute()[0]
    assert observed_ticks == list(range(5)) * 2
    assert recorded["rate_known"] is False and recorded["rate_prior"] == joint.RATE_PRIOR
    assert recorded["horizon"] == len(recorded["ticks"]) == 4
    assert [frame["tick"] for frame in recorded["belief_ticks"]] == list(range(5))
    assert recorded["belief_checkpoints"][-1]["tick"] == 4
    assert len(recorded["belief_checkpoints"][-1]["pairs"]) == 8
    assert recorded["summary"]["max_ledger_residual"] < 1e-10
    assert recorded["summary"]["message_cost"] > 0
    assert recorded["summary"]["message_paid_bytes"] > 0
    assert recorded["summary"]["messages_delivered"] > 0
    assert all(policy._observed_tick == 4 and policy._acted_tick == 3 for policy in policies)
    assert recorded["final_policy_memory_sha256"] == [digest(policy.memory()) for policy in policies]
    assert recorded["final_pool_memory_sha256"] is None
    assert policies[0].joint is not policies[1].joint
    if arm.endswith("-biased"):
        assert [agent["id"] for agent in recorded["agents"] if agent["biased"]] == [0]
        assert recorded["summary"]["biased_share_of_need"] is not None
        assert recorded["summary"]["terminal_biased_absolute_log_error"] is not None
    else:
        assert not any(agent["biased"] for agent in recorded["agents"])
        assert recorded["summary"]["biased_share_of_need"] is None
