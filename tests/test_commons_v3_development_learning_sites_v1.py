"""Selection/measurement fixtures; no declared learning arena executes here."""
from copy import deepcopy
from dataclasses import replace
import math
from types import SimpleNamespace

import pytest

from swarm_societies.commons_v3 import development_learning_sites_v1 as development
from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3.development_navigation_v1 import _save_record


def row(job, *, share=.8, late=.8, early=.7, messages=4):
    need = job["need"]
    initial = {"state": {"seed": job["seed"], "condition": job["condition"],
        "config": {"max_messages": messages, "need": need},
        "agents": [{"id": i} for i in range(24)]}}
    summary = {"share_of_need": share, "final_quarter_share_of_need": late,
               "terminal_capacity_absolute_log_error": .2, "time_mean_capacity_absolute_log_error": .3,
               "terminal_coverage90": .85, "time_mean_coverage90": .9}
    return {"version": development.VERSION, "job": job, "horizon": 512,
            "initial_snapshot": initial, "weather_sha256": f"weather-{job['seed']}",
            "summary": summary,
            "ticks": [{"tick": t, "consumption": 24 * need * early} for t in range(1, 513)],
            "belief_ticks": [{"tick": t, "coverage90": .85, "capacity_absolute_log_error": .2}
                             for t in range(513)]}


def candidates(early=.7):
    return [row(job, share=.8 if job["q"] == .25 else .7, early=early)
            for job in development.candidate_jobs()]


def references(early=.9):
    result = []
    for job in development.candidate_jobs(.25):
        for arm in ("R-oracle", "R-fixed", "R-greedy"):
            actual = {key: value for key, value in job.items() if key != "q"}
            actual.update(arm=arm, fixed_capacity=40. if arm == "R-fixed" else None)
            result.append(row(actual, share=.9, early=early, messages=1))
    return result


def test_bounded_menu_is_32_asocial_then_80_sharing_with_one_common_quantile():
    initial = development.candidate_jobs()
    following = development.candidate_jobs(.25, development.ARMS[1:])
    assert len(initial) == 32 and len(following) == 80
    assert {j["q"] for j in following} == {.25}
    assert {j["seed"] for j in initial + following} == {90001, 90002, 90003, 90004}
    assert len({development.case_id(j) for j in initial + following}) == 112
    assert development.BIASED_IDS == (0, 6, 12, 18)


@pytest.mark.parametrize("q,arms", [(0., ("L0",)), (True, ("L0",)), (.25, ("L0", "L0")), (.5, ("evaluation",))])
def test_outside_or_duplicate_choices_are_rejected(q, arms):
    with pytest.raises(ValueError):
        development.candidate_jobs(q, arms)


def test_quantile_selection_is_global_and_consumption_precedes_late_tiebreak():
    rows = candidates()
    # One cell favors .5 strongly; the other twelve cases favor .25.
    for record in rows:
        if record["job"]["q"] == .5 and record["job"]["condition"] == "wide" and record["job"]["need"] == 1.6:
            record["summary"]["share_of_need"] = 1.
            record["summary"]["final_quarter_share_of_need"] = 1.
    assert development.select_quantile(rows)["selected"] == .25
    for record in rows:
        record["summary"]["share_of_need"] = .8
        record["summary"]["final_quarter_share_of_need"] = .9 if record["job"]["q"] == .5 else .8
    assert development.select_quantile(rows)["selected"] == .5
    for record in rows:
        record["summary"]["final_quarter_share_of_need"] = .8
    assert development.select_quantile(rows)["selected"] == .25


def test_selection_requires_every_declared_case_once_and_finite_scores():
    rows = candidates()
    for damaged in (rows[:-1], [*rows[:-1], rows[0]]):
        with pytest.raises(ValueError, match="inventory"):
            development.select_quantile(damaged)
    rows[0]["summary"]["share_of_need"] = math.nan
    with pytest.raises(ValueError, match="finite"):
        development.select_quantile(rows)


def test_g3_uses_first64_not_whole_horizon_and_requires_all_four_cells():
    rows, refs = candidates(early=.88), references(early=.9)
    gate = development.g3(rows, refs, .25)
    assert gate["trivial"] and not gate["passed"]
    assert len(gate["cells"]) == 4
    assert all(cell["within_0.02"] for cell in gate["cells"])
    # Whole-horizon consumption in these records remains .8: not the gate.
    for record in rows:
        if record["job"]["q"] == .25 and record["job"]["condition"] == "wide" and record["job"]["need"] == 1.6:
            record["ticks"][0]["consumption"] -= .001
    gate = development.g3(rows, refs, .25)
    assert not gate["trivial"] and gate["passed"]
    assert sum(cell["within_0.02"] for cell in gate["cells"]) == 3


def test_g3_better_than_oracle_counts_as_trivial_and_missing_tick_is_invalid():
    rows, refs = candidates(early=1.), references()
    assert development.g3(rows, refs, .25)["trivial"]
    rows[0]["ticks"][0]["tick"] = 0
    with pytest.raises(ValueError, match="sixty-four"):
        development.g3(rows, refs, .25)


class FakePosterior:
    def __init__(self, median=20., interval=(10., 90.)):
        self.median, self.bounds, self.revision, self.calls = median, interval, 0, 0

    def quantile(self, q):
        assert q == .5
        self.calls += 1
        return self.median

    def interval(self, level=.9):
        assert level == .9
        self.calls += 1
        return self.bounds


def prior_factory(site=0, biased=False):
    assert site == 0
    return FakePosterior(80., (50., 95.)) if biased else FakePosterior()


def test_all_pairs_include_unseen_priors_and_seen_only_is_supplementary():
    policies = [SimpleNamespace(posteriors={}, counters={"eligible": 2, "clean_own": 1}),
                SimpleNamespace(posteriors={}, counters={"eligible": 4, "clean_receipts": 1, "new_relay": 100})]
    measurement = development.BeliefMetrics((20., 80.), 2, biased_ids=(1,), prior_factory=prior_factory)
    measurement.observe_sites([{"self": {"id": 0}, "sites": [{"id": 0}]},
                               {"self": {"id": 1}, "sites": []}])
    frame, pairs = measurement.measure(policies, 0, raw=True)
    assert frame["agent_site_pairs"] == 4 and frame["directly_seen_pairs"] == 1
    assert frame["capacity_absolute_log_error"] == pytest.approx(math.log(4.) / 2)
    assert frame["seen_only_absolute_log_error"] == 0.
    assert frame["between_agent_log_median_dispersion"] == pytest.approx(math.log(4.) / 2)
    assert frame["clean_eligible_fraction"] == pytest.approx(2 / 6)
    assert frame["evidence_new_relay"] == 100
    assert frame["ever_within10_fraction"] == .5
    assert len(pairs) == 4 and len(pairs[0]) == len(development.PAIR_COLUMNS)
    assert measurement.first_accuracy_rows() == [[0, 0, 0], [0, 1, None], [1, 0, None], [1, 1, 0]]
    assert all(not policy.posteriors for policy in policies)  # No hidden-site instantiation.


def test_measurement_reuses_summary_until_posterior_revision_changes():
    posterior = FakePosterior()
    policy = SimpleNamespace(posteriors={0: posterior}, counters={})
    measurement = development.BeliefMetrics((20.,), 1, prior_factory=prior_factory)
    measurement.measure([policy], 0)
    assert posterior.calls == 2
    measurement.measure([policy], 1)
    assert posterior.calls == 2
    posterior.median, posterior.revision = 40., 1
    changed, _ = measurement.measure([policy], 2)
    assert posterior.calls == 4
    assert changed["capacity_absolute_log_error"] == pytest.approx(math.log(2.))
    with pytest.raises(ValueError, match="increasing"):
        measurement.measure([policy], 2)


def _message_world():
    cfg = engine.Config(width=3, height=3, n_agents=2, n_patches=1, sensing_radius=0,
                        need=1.2, site_capacities=(40.,), initial_site_stocks=(20.,))
    return engine.WorldState(cfg, 42, 0, (engine.AgentState(0, 1, 1, 3.), engine.AgentState(1, 1, 1, 3.)),
                             (engine.PatchState(0, 1, 1, 20.),))


def test_material_measurements_distinguish_attempts_paid_delivery_and_postharvest_food():
    state = _message_world()
    actions = (engine.Action(messages=((1, "abc"),), reserve=3.), engine.Action())
    result = engine.step(state, actions)
    frame = development._material_frame(result, actions, {(1, 1): 0}, (40.,), .375)
    assert frame["message_attempted_bytes"] == frame["message_paid_bytes"] == frame["message_delivered_bytes"] == 3
    assert frame["message_cost"] == .003
    assert frame["starvation_next_to_food_agents"] == 1
    assert frame["starvation_next_to_food_shortfall"] == 1.2
    actions = (actions[0], engine.Action(move=(1, 0)))
    result = engine.step(state, actions)
    frame = development._material_frame(result, actions, {(1, 1): 0}, (40.,), .375)
    assert frame["message_attempted_bytes"] == 3
    assert frame["message_paid_bytes"] == frame["message_delivered_bytes"] == 0
    assert frame["message_cost"] == 0.


def test_initial_world_pairing_ignores_only_the_unused_message_limit():
    record = candidates()[0]
    same = deepcopy(record["initial_snapshot"])
    same["state"]["config"]["max_messages"] = 1
    assert development.physical_initial_digest(same) == development.physical_initial_digest(record["initial_snapshot"])
    same["state"]["agents"][0]["inventory"] = 99.
    assert development.physical_initial_digest(same) != development.physical_initial_digest(record["initial_snapshot"])


def test_summary_retains_both_quantiles_and_paired_losses_without_evaluation_claims():
    rows = candidates()
    rows += [row(job, share=.75) for job in development.candidate_jobs(.25, development.ARMS[1:])]
    summary = development.summarize(rows, references(), {"selected_cases": 48})
    assert summary["episodes"] == 112 and summary["selected_episodes"] == 96
    assert len(summary["G3_both_quantiles"]) == 2
    contrast = summary["cells"][0]["contrasts"]["L2_minus_L0"]["statistics"]["share_of_need"]
    assert contrast["mean"] == pytest.approx(-.05)
    assert summary["fresh_evaluation_episodes"] == 0
    assert "descriptive" in summary["scope"]
    assert len(summary["cells"][0]["belief_trajectories"]["L0"]) == len(development.BELIEF_CHECKPOINTS)
    contrasts = summary["development_contrasts"]["contrasts"]
    assert set(contrasts) == {"P1", "P2", "P3", "P4", "P5"}
    assert contrasts["P1"]["statistics"]["mean"] == pytest.approx(-.05)
    assert contrasts["P2"]["statistics"]["mean"] == 0.
    assert "within each seed" in contrasts["P3"]["demand_pooling"]
    assert contrasts["P5"]["terminal_tick512"]["statistics"]["n"] == 4
    assert "primary time endpoint remains" in contrasts["P5"]["endpoint_status"]


def test_demand_pooling_occurs_within_seed_before_paired_statistics():
    rows = [row(job) for job in development.candidate_jobs(.25, development.ARMS)]
    for record in rows:
        if record["job"]["arm"] == "L1":
            record["belief_ticks"][128]["capacity_absolute_log_error"] = .1 if record["job"]["need"] == 1.2 else .5
        if record["job"]["arm"] == "L3":
            record["summary"]["time_mean_coverage90"] = .6 if record["job"]["need"] == 1.2 else .8
    contrasts = development.development_contrasts(rows)["contrasts"]
    assert contrasts["P3"]["statistics"]["mean"] == pytest.approx(.1)
    assert len(contrasts["P3"]["paired"]) == 4
    assert contrasts["P5"]["time_mean_ticks1_to512"]["statistics"]["mean"] == pytest.approx(-.2)


def test_unmatched_weather_or_starting_world_cannot_enter_aggregate():
    rows = candidates(early=.9)
    refs = references()
    rows[0]["weather_sha256"] = "different weather"
    with pytest.raises(ValueError, match="initialization or weather"):
        development.summarize(rows, refs, {})


@pytest.mark.parametrize("early,expected_batches", [(.9, [32]), (.7, [32, 80])])
def test_execution_stops_before_sharing_exactly_when_g3_requires_fallback(monkeypatch, tmp_path, early, expected_batches):
    batches = []

    def fake_run(output, jobs, workers):
        batches.append(len(jobs))
        return [row(job, share=.8 if job["q"] == .25 else .7, early=early) for job in jobs]

    monkeypatch.setattr(development, "load_references", lambda _: (references(), {}))
    monkeypatch.setattr(development, "_run_jobs", fake_run)
    monkeypatch.setattr(development, "_require_paths", lambda *_: None)
    result = development.run(tmp_path, workers=1)
    assert batches == expected_batches
    assert result["episodes"] == sum(expected_batches)
    with pytest.raises(ValueError, match="completed"):
        development.run(tmp_path, workers=1)
    assert batches == expected_batches


def test_pairing_failure_stops_before_sharing_is_submitted(monkeypatch, tmp_path):
    batches = []

    def fake_run(output, jobs, workers):
        batches.append(len(jobs))
        rows = candidates()
        rows[0]["weather_sha256"] = "mismatched"
        return rows

    monkeypatch.setattr(development, "load_references", lambda _: (references(), {}))
    monkeypatch.setattr(development, "_run_jobs", fake_run)
    with pytest.raises(ValueError, match="initialization or weather"):
        development.run(tmp_path, workers=1)
    assert batches == [32]


class ImmediatePool:
    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def map(self, function, jobs):
        return map(function, jobs)


def test_recovery_replays_and_preserves_existing_case_bytes(monkeypatch, tmp_path):
    jobs = development.candidate_jobs()[:2]
    monkeypatch.setattr(development, "ProcessPoolExecutor", ImmediatePool)
    monkeypatch.setattr(development, "run_episode", row)
    original = row(jobs[0])
    path = development._path(tmp_path, jobs[0])
    _save_record(path, original)
    before = path.read_bytes()
    actual = development._run_jobs(tmp_path, jobs, 1)
    assert len(actual) == 2 and path.read_bytes() == before
    monkeypatch.setattr(development, "run_episode", lambda job: row(job, share=.1))
    with pytest.raises(ValueError, match="recovery"):
        development._run_jobs(tmp_path, jobs, 1)
    assert path.read_bytes() == before


def test_episode_failure_preserves_case_identity_and_original_cause(monkeypatch, capsys):
    job = development.candidate_jobs()[0]

    def fail(*args):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(development.worlds, "initialize", fail)
    with pytest.raises(RuntimeError, match=development.case_id(job)) as caught:
        development.run_episode(job)
    assert isinstance(caught.value.__cause__, ValueError)
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"failed {development.case_id(job)}: ValueError('synthetic failure')\n"


def test_full_horizon_worker_heartbeats_print_only_declared_ticks_to_stderr(capsys):
    job = development.candidate_jobs()[0]
    for tick in (0, 1, 127, 128, 129, 255, 256, 384, 511, 512):
        development._worker_heartbeat(job, tick, development.HORIZON)
    # Engineering fixtures and arbitrary shorter episodes have no heartbeat.
    development._worker_heartbeat(job, 128, 128)
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.splitlines() == [f"progress {development.case_id(job)} tick {tick}/512"
                                     for tick in (128, 256, 384, 512)]


@pytest.mark.parametrize("arm", ["L0", "L1", "L2", "L3", "L2-biased", "L3-biased"])
def test_short_nonpanel_fixture_records_actual_postobservation_beliefs_and_replays(arm):
    from swarm_societies.commons_v3.policies_sharing_sites_v1 import LearningForager
    cfg = engine.Config(width=6, height=3, n_agents=4, n_patches=2, need=1.2,
                        max_messages=4, site_capacities=(20., 60.), initial_site_stocks=(12., 36.))
    state = engine.initialize(cfg, seed=42)
    job = {"arm": arm, "need": 1.2, "phi": .375, "q": .25, "seed": 42, "condition": "unit fixture"}

    def execute():
        policies = [LearningForager(arm.split("-")[0], q=.25, biased=arm.endswith("-biased") and i == 0)
                    for i in range(4)]
        return development._record_episode(job, state, policies, horizon=8)

    recorded = execute()
    assert recorded == execute()
    assert recorded["horizon"] == 8 and len(recorded["ticks"]) == 8
    assert [frame["tick"] for frame in recorded["belief_ticks"]] == list(range(9))
    assert recorded["belief_checkpoints"][-1]["tick"] == 8
    assert len(recorded["belief_checkpoints"][-1]["pairs"]) == 8
    assert recorded["summary"]["max_ledger_residual"] < 1e-10


@pytest.mark.parametrize("workers", [True, 0, 9])
def test_worker_limits_are_explicit(workers):
    with pytest.raises(ValueError):
        development._workers(workers)
