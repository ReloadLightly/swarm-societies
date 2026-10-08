"""A2 authorization/stopping fixtures; no scientific episode runs here."""
from copy import deepcopy

import pytest

from swarm_societies.commons_v3 import development_joint_sites_v1 as development


def rows(pool_share=.81):
    return [{"version": development.VERSION, "job": job, "horizon": 512,
             "rate_known": False, "rate_prior": dict(development.RATE_PRIOR),
             "summary": {"share_of_need": pool_share if job["arm"] == "R-pool" else .8}}
            for job in development.fallback_jobs()]


def isolate_descriptive_aggregation(monkeypatch):
    monkeypatch.setattr(development.base, "_paired_worlds", lambda *args: None)
    monkeypatch.setattr(development.pool, "comparison_cells", lambda *args, **kwargs: [])


def test_fallback_is_exactly_selected_L0_and_pool_on_the_original_four_seeds():
    jobs = development.fallback_jobs()
    assert len(jobs) == 32
    assert {job["arm"] for job in jobs} == {"L0", "R-pool"}
    assert {job["seed"] for job in jobs} == {90001, 90002, 90003, 90004}
    assert {job["phi"] for job in jobs} == {.375}
    assert {job["q"] for job in jobs} == {.25}


@pytest.mark.parametrize("a1_passed,g2_passed", [(True, True), (False, False)])
def test_fallback_requires_failed_A1_and_passed_joint_G2(a1_passed, g2_passed):
    with pytest.raises(ValueError):
        development.summarize(rows(), [], {"G3_prime": {"passed": a1_passed}},
                              {"G2": {"passed": g2_passed}})


@pytest.mark.parametrize("damage", ["known", "prior", "version", "missing", "duplicate"])
def test_wrong_model_or_case_inventory_is_rejected(damage):
    records = rows()
    if damage == "known":
        records[0]["rate_known"] = True
    elif damage == "prior":
        records[0]["rate_prior"]["high"] = .96
    elif damage == "version":
        records[0]["version"] = "known-rate"
    elif damage == "missing":
        records.pop()
    else:
        records[-1] = deepcopy(records[0])
    with pytest.raises(ValueError):
        development.summarize(records, [], {"G3_prime": {"passed": False}}, {"G2": {"passed": True}})


@pytest.mark.parametrize("pool_share,passed", [(.81, False), (.83, True)])
def test_second_gate_preserves_threshold_and_has_no_further_fallback(monkeypatch, pool_share, passed):
    isolate_descriptive_aggregation(monkeypatch)
    result = development.summarize(rows(pool_share), [], {"G3_prime": {"passed": False}},
                                   {"G2": {"passed": True}})
    assert result["G3_prime"]["passed"] is passed
    assert result["G3_prime"]["threshold"] == .02
    assert result["G3_prime"]["condition"] == "wide"
    assert result["G3_prime"]["need"] == 1.6
    assert result["fresh_evaluation_episodes"] == 0
    if passed:
        assert "sharing development" in result["decision"]
    else:
        assert result["decision"] == "stop the contracted design; no further fallback"


def test_completed_fallback_cannot_restart(tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    with pytest.raises(ValueError, match="completed fallback"):
        development.run(tmp_path)


def test_prerequisite_rejection_prevents_all_episode_submissions(monkeypatch, tmp_path):
    def blocked(*args):
        raise ValueError("joint G2 has not passed")
    monkeypatch.setattr(development, "_load_prerequisites", blocked)
    monkeypatch.setattr(development.pool, "_run_jobs", lambda *a, **k: pytest.fail("submitted a case before G2"))
    with pytest.raises(ValueError, match="G2"):
        development.run(tmp_path)


def test_no_other_arm_or_new_seed_is_accepted_before_runtime_import():
    job = development.fallback_jobs()[0]
    for mutation in ({"arm": "L2"}, {"seed": 90005}, {"q": .5}):
        with pytest.raises(ValueError, match="single approved fallback"):
            development.run_episode({**job, **mutation})


@pytest.mark.parametrize("arm", ["L0", "R-pool"])
def test_tiny_unknown_rate_episode_replays_at_calibrated_resolution(monkeypatch, arm):
    from swarm_societies.commons_v3 import engine_sites_v1 as engine
    from swarm_societies.commons_v3 import observations_joint_sites_v1 as adapter
    from swarm_societies.commons_v3.calibration_joint_sites_v1 import RESOLUTION
    from swarm_societies.commons_v3.development_navigation_v1 import digest
    from swarm_societies.commons_v3.policies_joint_sites_v1 import (
        UnknownForager, UnknownPoolCoordinator, UnknownPoolForager,
    )

    config = engine.Config(width=6, height=3, n_agents=2, n_patches=2,
                           need=1.2, max_messages=1, sensing_radius=0,
                           site_capacities=(20., 60.), initial_site_stocks=(12., 36.))
    state = engine.WorldState(
        config, 42, 0,
        (engine.AgentState(0, 1, 1, 3.), engine.AgentState(1, 4, 1, 3.)),
        (engine.PatchState(0, 1, 1, 12.), engine.PatchState(1, 4, 1, 36.)),
    )
    job = {"arm": arm, "need": 1.2, "phi": .375, "q": .25,
           "seed": 42, "condition": "unit fixture"}
    original_observations = adapter.observations
    observed_ticks = []

    def checked_observations(current, previous_result=None):
        packets = original_observations(current, previous_result)
        observed_ticks.append(current.tick)
        for packet in packets:
            assert "renewal_rate" not in packet["ecology"]
            assert packet["ecology"]["renewal_rate_prior"] == development.RATE_PRIOR
            assert all("capacity" not in site for site in packet["sites"])
        return packets

    monkeypatch.setattr(adapter, "observations", checked_observations)

    def execute():
        coordinator = UnknownPoolCoordinator(**RESOLUTION) if arm == "R-pool" else None
        policies = ([UnknownPoolForager(coordinator, identity) for identity in range(2)]
                    if coordinator else [UnknownForager(**RESOLUTION) for _ in range(2)])
        for policy in policies:
            assert {key: getattr(policy.joint, key) for key in RESOLUTION} == RESOLUTION
        result = development._record_unknown_episode(job, state, policies, coordinator, horizon=4)
        return result, coordinator, policies

    recorded, coordinator, policies = execute()
    assert recorded == execute()[0]
    assert observed_ticks == list(range(5)) * 2
    assert recorded["rate_known"] is False and recorded["rate_prior"] == development.RATE_PRIOR
    assert recorded["horizon"] == 4 and len(recorded["ticks"]) == 4
    assert [frame["tick"] for frame in recorded["belief_ticks"]] == list(range(5))
    assert recorded["belief_checkpoints"][-1]["tick"] == 4
    assert len(recorded["belief_checkpoints"][-1]["pairs"]) == 4
    assert recorded["summary"]["max_ledger_residual"] < 1e-10
    for key in ("message_attempts", "messages_delivered", "message_attempted_bytes",
                "message_paid_bytes", "message_delivered_bytes", "message_cost"):
        assert recorded["summary"][key] == 0
    assert recorded["final_policy_memory_sha256"] == [digest(policy.memory()) for policy in policies]
    assert all(policy._observed_tick == 4 and policy._acted_tick == 3 for policy in policies)
    assert all(not policy.last_action.messages for policy in policies)
    assert any(update["kind"] == "growth" and update["tick"] == 3
               for policy in policies for update in policy.last_updates)
    if coordinator:
        assert coordinator.tick == 4
        assert recorded["final_pool_memory_sha256"] == digest(coordinator.memory())
        assert all(policy.joint is coordinator.joint for policy in policies)
    else:
        assert recorded["final_pool_memory_sha256"] is None
        assert policies[0].joint is not policies[1].joint
