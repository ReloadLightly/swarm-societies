"""Read-only floor reconstruction fixtures; no development bank executes."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from swarm_societies.commons_v3 import consequence_sites_v1 as consequence
from swarm_societies.commons_v3 import development_learning_sites_v1 as development
from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import floor_diagnostic_sites_v1 as diagnostic
from swarm_societies.commons_v3 import policies_sharing_sites_v1 as sharing


def _result(tick, harvested=(.01, 10., 0.)):
    return SimpleNamespace(
        state=SimpleNamespace(tick=tick,
            config=SimpleNamespace(site_capacities=(10., 100.)),
            patches=(SimpleNamespace(id=0, x=0, y=0), SimpleNamespace(id=1, x=1, y=0)),
            agents=(SimpleNamespace(x=0, y=0), SimpleNamespace(x=1, y=0),
                    SimpleNamespace(x=2, y=0))),
        ledger=SimpleNamespace(agents=tuple(SimpleNamespace(harvested=h) for h in harvested)))


def _policies():
    # Each agent's other remembered site's capacity is deliberately different.
    # Only the realized post-movement location should enter the diagnostic.
    return [SimpleNamespace(stock_floor_fraction=.5, aggressive=False,
                            records={0: {"capacity": 20.}, 1: {"capacity": 180.}}),
            SimpleNamespace(stock_floor_fraction=.5, aggressive=False,
                            records={0: {"capacity": 100.}, 1: {"capacity": 20.}}),
            SimpleNamespace(stock_floor_fraction=.5, aggressive=False, records={})]


def test_positive_actual_harvest_events_use_arrival_site_and_equal_event_weights():
    accumulator = diagnostic.HarvestFloors(4)
    policies = _policies()
    accumulator.add(_result(1), policies)
    accumulator.add(_result(2, (0., 0., 0.)), policies)
    accumulator.add(_result(3, (0., 0., 0.)), policies)
    # Quantiles can change over time; the current decision-time record matters.
    policies[1].records[1]["capacity"] = 60.
    accumulator.add(_result(4, (0., 1., 0.)), policies)
    rows = accumulator.summary()
    assert rows["whole_run"]["harvest_agent_ticks"] == 3
    assert rows["whole_run"]["sum_floor_over_true_capacity"] == pytest.approx(1.4)
    assert rows["whole_run"]["mean_floor_over_true_capacity"] == pytest.approx(1.4 / 3)
    assert rows["final_quarter"] == {"harvest_agent_ticks": 1,
        "sum_floor_over_true_capacity": .3, "mean_floor_over_true_capacity": .3}


def test_empty_period_is_explicit_null_and_incomplete_or_unrecorded_harvest_rejected():
    accumulator = diagnostic.HarvestFloors(1)
    with pytest.raises(ValueError, match="incomplete"):
        accumulator.summary()
    accumulator.add(_result(1, (0., 0., 0.)), _policies())
    assert accumulator.summary()["whole_run"]["mean_floor_over_true_capacity"] is None
    accumulator = diagnostic.HarvestFloors(1)
    with pytest.raises(ValueError, match="actual harvest site"):
        accumulator.add(_result(1, (0., 0., 1.)), _policies())


@pytest.mark.parametrize("tick", [0, 2])
def test_nonconsecutive_ticks_fail(tick):
    with pytest.raises(ValueError, match="consecutive"):
        diagnostic.HarvestFloors(4).add(_result(tick), _policies())


def _short_world(condition, need, seed):
    cfg = engine.Config(width=3, height=3, n_agents=4, n_patches=2,
                        sensing_radius=1, need=need,
                        site_capacities=(20., 60.), initial_site_stocks=(15., 40.))
    return engine.WorldState(cfg, seed, 0,
        (engine.AgentState(0, 0, 0, 3.), engine.AgentState(1, 1, 1, 3.),
         engine.AgentState(2, 0, 1, 3.), engine.AgentState(3, 2, 1, 3.)),
        (engine.PatchState(0, 0, 0, 15.), engine.PatchState(1, 1, 1, 40.)))


@pytest.mark.parametrize("arm", ["L0", "R-oracle"])
def test_instrumented_short_original_runner_reproduces_complete_saved_record(monkeypatch, arm):
    monkeypatch.setattr(development.worlds, "initialize", _short_world)
    if arm == "L0":
        original = development._record_episode
        monkeypatch.setattr(development, "_record_episode",
                            lambda job, state, policies: original(job, state, policies, horizon=8))
        job, runner = development.candidate_jobs(.25)[0], development
    else:
        monkeypatch.setattr(consequence, "HORIZON", 8)
        job, runner = consequence.candidate_jobs("R-oracle")[0], consequence
    saved = runner.run_episode(job)
    original_step, original_learning = engine.step, sharing.LearningForager
    original_reference = consequence.ReferenceForager
    report = diagnostic.diagnose_case(saved)
    assert report["exact_full_record_replay"]
    assert report["source_case_sha256"] == diagnostic.digest(saved)
    assert report["periods"]["whole_run"]["harvest_agent_ticks"] > 0
    if arm == "R-oracle":
        assert report["periods"]["whole_run"]["mean_floor_over_true_capacity"] == .375
    assert engine.step is original_step
    assert sharing.LearningForager is original_learning
    assert consequence.ReferenceForager is original_reference

    changed = deepcopy(saved)
    changed["summary"]["share_of_need"] += .001
    with pytest.raises(ValueError, match="complete scientific record"):
        diagnostic.diagnose_case(changed)
    assert engine.step is original_step
    assert sharing.LearningForager is original_learning
    assert consequence.ReferenceForager is original_reference


def test_instrumentation_restores_bindings_after_engine_exception(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("fixture failure")
    monkeypatch.setattr(engine, "step", broken)
    constructor = sharing.LearningForager
    with pytest.raises(RuntimeError, match="fixture failure"):
        with diagnostic._instrument("L0", diagnostic.HarvestFloors(1)):
            engine.step(None, None)
    assert engine.step is broken
    assert sharing.LearningForager is constructor


@pytest.mark.parametrize("arm,q,phi", [("L1", .25, .375), ("L0", .5, .375),
                                      ("R-oracle", None, .5)])
def test_unselected_cases_are_rejected_before_running(arm, q, phi):
    with pytest.raises(ValueError, match="selected"):
        diagnostic.diagnose_case({"job": {"arm": arm, "q": q, "phi": phi}})


def _diagnostics():
    rows = []
    for job in development.candidate_jobs(.25):
        for arm in ("L0", "R-oracle"):
            count = job["seed"] - 90000
            mean = count / 10 if arm == "L0" else .375
            rows.append({"version": diagnostic.VERSION, "job": {**job, "arm": arm},
                         "horizon": 512, "exact_full_record_replay": True,
                         "periods": {period: {"harvest_agent_ticks": count,
                             "sum_floor_over_true_capacity": count * mean,
                             "mean_floor_over_true_capacity": mean}
                                     for period in diagnostic.PERIODS}})
    return rows


def test_aggregation_keeps_equal_seed_and_event_weighted_means_distinct():
    summary = diagnostic.summarize(_diagnostics())
    assert summary["episodes_replayed"] == 32
    assert len(summary["cells"]) == 4
    for cell in summary["cells"]:
        period = cell["arms"]["L0"]["whole_run"]
        assert period["equal_seed_mean"]["n"] == 4
        assert period["equal_seed_mean"]["mean"] == .25
        assert period["event_weighted_mean"] == pytest.approx(.3)
        assert period["harvest_agent_ticks"] == 10
        assert cell["arms"]["R-oracle"]["whole_run"]["equal_seed_mean"]["mean"] == .375


def test_aggregation_rejects_missing_duplicate_and_unverified_records():
    rows = _diagnostics()
    with pytest.raises(ValueError, match="sixteen paired"):
        diagnostic.summarize(rows[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        diagnostic.summarize([*rows[:-1], rows[0]])
    rows[0]["exact_full_record_replay"] = False
    with pytest.raises(ValueError, match="incomplete"):
        diagnostic.summarize(rows)
