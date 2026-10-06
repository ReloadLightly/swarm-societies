"""Information-boundary, accounting and continuation controls for sharing v1."""

import copy
import json

import numpy as np
import pytest

from swarm_societies.world_model_v1.learner import RenewalSMC
from swarm_societies.world_model_v1.sharing import (
    CONDITIONS, FRAME_BYTES, MemberPort, SharingRuntime, actor_seed,
)


def packets(tick, arena="test"):
    return {patch: {
        "event_id": f"{arena}/growth:{tick}:{patch}", "tick": tick, "patch": patch,
        "phase": "before_actions", "stock_before": 2.0, "capacity": 30.0,
        "own_infrastructure": (tick + patch) % 5 / 4,
        "other_infrastructure": (2 * tick + patch + 1) % 7 / 5,
        "growth": 4.8 + 1.6 * ((tick + patch) % 5 / 4)
        + 0.4 * ((2 * tick + patch + 1) % 7 / 5), "sensor_sigma": 0.05,
    } for patch in range(3)}


def runtime(condition="complementary", **kwargs):
    return SharingRuntime(condition, seed=93,
                          learner_kwargs={"n_particles": 32, "rejuvenation_steps": 1}, **kwargs)


def test_all_private_learners_start_separately_but_same_actor_matches_across_conditions():
    first, second = runtime("isolated"), runtime("complementary")
    first_models, second_models = first.evaluator_models(), second.evaluator_models()
    assert len(first_models) == 15
    assert all(first_models[key].snapshot() == second_models[key].snapshot() for key in first_models)
    assert first_models["member:0:0"].snapshot() != first_models["member:0:1"].snapshot()
    assert not hasattr(first_models["member:0:0"], "update")
    snap = first_models["member:0:0"].snapshot()
    snap["particles"][0][0] = -100
    assert first_models["member:0:0"].snapshot()["particles"][0][0] > 0


def test_local_footprint_is_home_plus_rotating_other_and_every_copy_is_same_event():
    run = runtime("isolated")
    for tick in range(2):
        current = packets(tick)
        run.step(tick, current)
        for society in range(3):
            for member in range(4):
                visible = run.member_port(society, member).observations()
                assert [item["patch"] for item in visible] == [society, (society + 1 + (member + tick) % 2) % 3]
                assert visible == [current[item["patch"]] for item in visible]
                visible[0]["growth"] = 99
                assert run.member_port(society, member).observations()[0]["growth"] != 99
    assert run.summary()["sent_bytes"] == 0
    assert all(model.summary()["n_observations"] == (4 if key.startswith("member") else 0)
               for key, model in run.evaluator_models().items())


def test_zero_sharing_is_exactly_independent_learning_with_no_hidden_updates():
    run = runtime("isolated")
    manual = RenewalSMC(seed=actor_seed(93, "member:1:2"), n_particles=32, rejuvenation_steps=1)
    for tick in range(12):
        data = packets(tick)
        run.step(tick, data)
        for patch in (1, (1 + 1 + (2 + tick) % 2) % 3):
            manual.update(data[patch])
    assert run.evaluator_models()["member:1:2"].snapshot() == manual.snapshot()
    assert run.ledger()["frames"] == []


@pytest.mark.parametrize("condition,delay", [("complementary", 1), ("delayed_complementary", 4)])
def test_two_hop_delay_and_no_early_delivery(condition, delay):
    run = runtime(condition)
    run.step(0, packets(0))
    assert run.summary()["sent_frames"] == 6
    assert run.evaluator_models()["institution:0"].summary()["n_observations"] == 0
    for tick in range(1, 2 * delay + 1):
        run.start_tick(tick)
        if tick < delay:
            assert run.evaluator_models()["institution:0"].summary()["n_observations"] == 0
        if tick == delay:
            assert run.evaluator_models()["institution:0"].summary()["n_observations"] == 2
        if tick < 2 * delay:
            assert not [row for row in run.ledger()["updates"] if row["channel"] == "downlink"]
        else:
            received = [row for row in run.ledger()["updates"] if row["channel"] == "downlink"]
            assert len(received) == 24
            assert {row["tick"] for row in received} == {2 * delay}
        run.observe_tick(packets(tick))
        run.submit_reports()
        run.finish_tick()
    assert run.summary()["pending_frames"] > 0


def test_redundant_reports_charge_every_wire_copy_without_counting_evidence_again():
    independent, redundant = runtime("isolated"), runtime("redundant")
    for tick in range(8):
        independent.step(tick, packets(tick))
        redundant.step(tick, packets(tick))
    assert redundant.summary()["sent_frames"] == 6 * 8 + 24 * 7
    assert redundant.summary()["delivered_frames"] == 6 * 7 + 24 * 6
    for key, model in independent.evaluator_models().items():
        duplicate_model = redundant.evaluator_models()[key]
        if key.startswith("member"):
            left, right = model.snapshot(), duplicate_model.snapshot()
            # The only change is the measured duplicate counter.
            assert right["diagnostics"].pop("duplicate_events") == 12
            assert left["diagnostics"].pop("duplicate_events") == 0
            assert left == right
        else:
            assert duplicate_model.summary()["n_observations"] == 7
            assert duplicate_model.summary()["diagnostics"]["duplicate_events"] == 7
    for frame in redundant.ledger()["frames"]:
        raw = redundant.frame_bytes(frame["frame_id"])
        assert len(raw) == FRAME_BYTES
        assert len(raw.rstrip(b" ")) == frame["payload_bytes"]
        body = json.loads(raw)
        assert body["packet"] == frame["packet"]
        assert body["origin_member"] == frame["origin_member"]
        assert body["measurement_sha256"] == frame["measurement_sha256"]


def test_matched_fast_condition_bandwidth_and_bounded_sender_slots():
    runs = [runtime(condition) for condition in ("redundant", "complementary")]
    for tick in range(6):
        for run in runs:
            run.step(tick, packets(tick))
    for field in ("sent_frames", "sent_bytes", "delivered_frames", "pending_frames"):
        assert runs[0].summary()[field] == runs[1].summary()[field]
    for run in runs:
        for tick in range(6):
            uplinks = [row for row in run.ledger()["frames"] if row["channel"] == "uplink" and row["tick"] == tick]
            assert len(uplinks) == 6
            assert {row["sender"].split(":")[-1] for row in uplinks} == {"0", "1"}
        assert run.summary()["sent_bytes"] == run.summary()["sent_frames"] * 1024


def test_bound_identity_rejects_forged_cross_runtime_copied_and_plain_actor_handles():
    run, another = runtime(), runtime()
    run.start_tick(0)
    run.observe_tick(packets(0))
    event = packets(0)[1]["event_id"]
    for impostor in ("member:0:0", MemberPort(run, "member:0:0"),
                     another.member_port(0, 0), copy.copy(run.member_port(0, 0))):
        with pytest.raises(ValueError, match="trusted bound"):
            run.submit_report(impostor, event)
    assert run.summary()["sent_frames"] == 0
    assert run.summary()["rejected_reports"] == 4
    run.member_port(0, 0).submit(event)
    assert run.summary()["sent_frames"] == 1


def test_forgery_ownership_future_cross_arena_and_replay_are_rejected_without_budget_spend():
    run = runtime()
    run.start_tick(0)
    run.observe_tick(packets(0))
    port = run.member_port(0, 0)
    canonical = packets(0)[1]
    bad_payloads = [{**canonical, "growth": 999}, {**canonical, "weather": 1.0},
                    {**canonical, "sender": "member:1:0"}, {**canonical, "tick": 10}]
    for payload in bad_payloads:
        with pytest.raises(ValueError, match="canonical sensor"):
            port.submit(canonical["event_id"], payload)
    with pytest.raises(ValueError, match="does not own"):
        port.submit(packets(0)[2]["event_id"])
    with pytest.raises(ValueError, match="unknown or future"):
        port.submit(packets(1)[1]["event_id"])
    with pytest.raises(ValueError, match="unknown or future"):
        port.submit(packets(0, arena="another")[1]["event_id"])
    with pytest.raises(ValueError, match="fixed truthful"):
        port.submit(packets(0)[0]["event_id"])
    with pytest.raises(ValueError, match="sender slot"):
        run.member_port(0, 2).submit(canonical["event_id"])
    assert run.summary()["sent_bytes"] == 0
    port.submit(canonical["event_id"], canonical)
    with pytest.raises(ValueError, match="budget is exhausted"):
        port.submit(canonical["event_id"])
    assert run.summary()["sent_bytes"] == 1024
    run.finish_tick()
    run.start_tick(1)
    run.observe_tick(packets(1))
    with pytest.raises(ValueError, match="current-tick"):
        port.submit(canonical["event_id"])


@pytest.mark.parametrize("mutator", [
    lambda p: p[0].update(weather=1.0),
    lambda p: p[0].update(tick=1),
    lambda p: p[0].update(phase="after_allocation"),
    lambda p: p[0].update(patch=1),
    lambda p: p[0].update(growth=float("nan")),
    lambda p: p[0].update(sensor_sigma=.1),
    lambda p: p[0].update(stock_before=31),
    lambda p: p[1].update(event_id=p[0]["event_id"]),
])
def test_sensor_whitelist_and_contract_validate_entire_tick_before_learning(mutator):
    run = runtime()
    run.start_tick(0)
    data = packets(0)
    mutator(data)
    before = run.snapshot()
    with pytest.raises(ValueError):
        run.observe_tick(data)
    assert run.snapshot() == before


def test_explicit_arena_binding_rejects_cross_world_sensor_registration_and_survives_resume():
    run = runtime(arena_id="test")
    run.start_tick(0)
    before = run.snapshot()
    with pytest.raises(ValueError, match="another arena"):
        run.observe_tick(packets(0, arena="different"))
    assert run.snapshot() == before
    run.observe_tick(packets(0))
    run.submit_reports()
    run.finish_tick()
    restored = SharingRuntime.from_snapshot(run.snapshot())
    assert restored.arena_id == "test"
    assert restored.snapshot() == run.snapshot()


def test_numeric_failed_updates_are_recorded_and_do_not_disappear_or_trigger_callbacks():
    accepted = []
    run = runtime(on_update=lambda *args: accepted.append(args[1]))
    data = packets(0)
    for item in data.values():
        item["growth"] = 1e100
    with np.errstate(over="ignore", invalid="ignore"):
        run.step(0, data)
    assert run.summary()["failed_updates"] == 24
    assert run.summary()["unique_updates"] == 0
    assert run.summary()["sent_frames"] == 6
    assert not accepted
    assert all(row["status"] == "failed" and row["reason"] == "nonfinite_likelihood"
               for row in run.ledger()["updates"])
    assert SharingRuntime.from_snapshot(run.snapshot()).snapshot() == run.snapshot()


def test_actor_interface_contains_only_authorized_sensor_fields_and_bounded_own_summary():
    run = runtime()
    run.step(0, packets(0))
    port = run.member_port(0, 0)
    assert set(port.belief_summary()) == {"mean", "intervals_90", "n_observations"}
    assert not hasattr(port, "evaluator_models")
    assert not hasattr(port, "snapshot")
    assert not hasattr(port, "member_port")
    assert {item["patch"] for item in port.observations()} == {0, 1}
    for forbidden in ("weather", "truth", "parameters", "evaluator_seed", "stock_after"):
        assert all(forbidden not in item for item in port.observations())


def test_callback_observes_each_unique_update_before_next_evidence_and_is_read_only():
    checkpoints = []
    def callback(run, actor_key, model, status, event, channel):
        assert status["status"] == "updated"
        assert not hasattr(model, "update")
        snapshot = model.snapshot()
        model.predict(event, n_samples=8, seed=25)
        assert snapshot == model.snapshot()
        checkpoints.append((actor_key, model.summary()["n_observations"], event["event_id"], channel))
    run = runtime("redundant", on_update=callback)
    for tick in range(4):
        run.step(tick, packets(tick))
    assert len(checkpoints) == run.summary()["unique_updates"]
    for key in run.evaluator_models():
        observed = [count for actor, count, _, _ in checkpoints if actor == key]
        assert observed == list(range(1, len(observed) + 1))
    assert run.summary()["duplicate_updates"] > 0


@pytest.mark.parametrize("condition", CONDITIONS)
def test_snapshot_json_roundtrip_reproduces_all_future_learning_transport_and_rng(condition):
    uninterrupted = runtime(condition)
    for tick in range(5):
        uninterrupted.step(tick, packets(tick))
    saved = json.loads(json.dumps(uninterrupted.snapshot(), allow_nan=False))
    callback_events = []
    restored = SharingRuntime.from_snapshot(saved, on_update=lambda *args: callback_events.append(args[1]))
    assert restored.snapshot() == saved
    for tick in range(5, 10):
        uninterrupted.step(tick, packets(tick))
        restored.step(tick, packets(tick))
    assert callback_events
    assert uninterrupted.snapshot() == restored.snapshot()
    assert uninterrupted.ledger() == restored.ledger()
    assert uninterrupted.summary() == restored.summary()
    query = packets(11)[0]
    assert all(uninterrupted.evaluator_models()[key].predict(query, seed=73)
               == restored.evaluator_models()[key].predict(query, seed=73)
               for key in restored.evaluator_models())


def test_restore_mid_tick_retains_sender_quota_and_invalidates_old_capabilities():
    run = runtime()
    old_port = run.member_port(0, 0)
    run.start_tick(0)
    run.observe_tick(packets(0))
    old_port.submit(packets(0)[1]["event_id"])
    saved = run.snapshot()
    run.restore(saved)
    assert run.snapshot() == saved
    with pytest.raises(ValueError, match="trusted bound"):
        old_port.submit(packets(0)[1]["event_id"])
    with pytest.raises(ValueError, match="budget is exhausted"):
        run.member_port(0, 0).submit(packets(0)[1]["event_id"])
    run.submit_reports()
    run.finish_tick()
    assert run.summary()["sent_frames"] == 6


@pytest.mark.parametrize("corruption", ["queue", "ownership", "content", "route", "timing", "padding"])
def test_restore_rejects_transport_corruption(corruption):
    run = runtime()
    run.step(0, packets(0))
    run.step(1, packets(1))
    state = run.snapshot()
    if corruption == "queue":
        state["queue"] = []
    elif corruption == "ownership":
        state["owners"][packets(0)[2]["event_id"]].append("member:0:0")
    elif corruption == "content":
        state["frames"][0]["packet"]["growth"] += 1
    elif corruption == "route":
        state["frames"][0]["recipient"] = "institution:2"
    elif corruption == "timing":
        state["frames"][0]["delivery_tick"] = 99
    elif corruption == "padding":
        state["frames"][0]["bytes"] = 1
    with pytest.raises(ValueError):
        SharingRuntime.from_snapshot(state)


def test_union_ceiling_updates_once_per_physical_event_without_hypothetical_wire_credit():
    run = runtime("union_ceiling")
    for tick in range(5):
        run.step(tick, packets(tick))
    assert all(model.summary()["n_observations"] == 15 for model in run.evaluator_models().values())
    assert run.summary()["duplicate_updates"] == 0
    assert run.summary()["sent_bytes"] == 0
    assert run.summary()["pending_bytes"] == 0
    assert run.ledger()["frames"] == []


@pytest.mark.parametrize("condition", CONDITIONS)
def test_fixed_horizon_counts_include_pending_messages_and_never_flush(condition):
    run = SharingRuntime(condition, seed=7, learner_kwargs={"n_particles": 8, "rejuvenation_steps": 0})
    ticks = 12
    for tick in range(ticks):
        run.step(tick, packets(tick))
    member_count = {"isolated": 24, "redundant": 24, "complementary": 34,
                    "delayed_complementary": 28, "union_ceiling": 36}[condition]
    institution_count = {"isolated": 0, "redundant": 11, "complementary": 22,
                         "delayed_complementary": 16, "union_ceiling": 36}[condition]
    assert run.clock == ticks - 1
    assert all(model.summary()["n_observations"] == (member_count if key.startswith("member") else institution_count)
               for key, model in run.evaluator_models().items())
    before = run.snapshot()
    run.ledger()
    run.summary()
    assert before == run.snapshot()
    if condition in ("redundant", "complementary", "delayed_complementary"):
        delay = run.delay
        assert run.summary()["sent_frames"] == 3 * (2 * ticks + 8 * (ticks - delay))
        assert run.summary()["delivered_frames"] == 3 * (2 * (ticks - delay) + 8 * (ticks - 2 * delay))
        assert run.summary()["sent_frames"] == run.summary()["delivered_frames"] + run.summary()["pending_frames"]


def test_lifecycle_rejects_skips_repeats_reports_before_observations_and_unfinished_ticks():
    run = runtime()
    with pytest.raises(ValueError):
        run.step(1, packets(1))
    run.start_tick(0)
    with pytest.raises(ValueError):
        run.submit_reports()
    with pytest.raises(ValueError):
        run.start_tick(1)
    run.observe_tick(packets(0))
    with pytest.raises(ValueError):
        run.observe_tick(packets(0))
    run.submit_reports()
    run.finish_tick()
    with pytest.raises(ValueError):
        run.step(0, packets(0))
