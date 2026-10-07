"""Small engineering fixtures for own feedback and paid delayed messages."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
import struct

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import observations_messages_sites_v1 as adapter
from swarm_societies.commons_v3.evidence_receipts_sites_v1 import ReceiptEvidence
from swarm_societies.commons_v3.messages_sites_v1 import (
    BeliefSummary, GrowthEvidence, HarvestReceipt, decode, encode,
    schedule_messages, social_recipient,
)


def world(*, positions=(1, 1, 1, 5), inventories=None, stock=30., radius=1):
    config = engine.Config(width=7, height=3, n_agents=len(positions), n_patches=2,
                           sensing_radius=radius, need=1.2, initial_inventory=5.,
                           max_messages=4, site_capacities=(40., 60.),
                           initial_site_stocks=(stock, 40.))
    state = engine.initialize(config, 17)
    inventories = inventories or (5.,) * len(positions)
    return replace(state,
                    agents=tuple(replace(agent, x=x, y=1, inventory=inventory)
                                 for agent, x, inventory in zip(state.agents, positions, inventories)),
                    patches=(replace(state.patches[0], x=1, y=1),
                             replace(state.patches[1], x=5, y=1)))


def prepared_shared(*, inventories=None):
    state = world(inventories=inventories)
    tracker = ReceiptEvidence()
    tracker.observe(adapter.observations(state)[0])
    actions = (engine.Action(harvest=4.), engine.Action(harvest=2.), engine.Action(), engine.Action())
    result = engine.step(state, actions)
    packets = adapter.observations(result.state, result)
    batch = tracker.observe(packets[0], actions[0])
    assert batch.growth == ()
    return tracker, result, packets


def direct_message(sender, text, *, tick=2):
    return {"sender": sender, "recipient": 0, "sent_tick": tick - 1,
            "delivery_tick": tick, "text": text}


def test_private_feedback_is_own_only_exact_and_equally_available_to_all_agents():
    state = world()
    initial = adapter.observations(state)
    assert all(packet["private_harvest"] is None for packet in initial)
    result = engine.step(state, (engine.Action(harvest=4.), engine.Action(harvest=2.),
                                 engine.Action(), engine.Action(harvest=1.)))
    receipts = adapter.private_harvest_receipts(result)
    packets = adapter.observations(result.state, result)
    assert packets == adapter.observations(result.state, receipts)
    base = engine.observations(result.state)
    for identity, packet in enumerate(packets):
        assert packet["adapter_version"] == adapter.VERSION
        assert packet["observation_version"] == engine.OBSERVATION_VERSION
        receipt = packet["private_harvest"]
        assert receipt == {"version": adapter.RECEIPT_VERSION, "tick": 0, "agent": identity,
                           "harvested": result.ledger.agents[identity].harvested}
        assert {key: value for key, value in packet.items()
                if key not in ("private_harvest", "adapter_version")} == base[identity]
    packets[0]["private_harvest"]["harvested"] = 999.
    assert receipts[0]["harvested"] == result.ledger.agents[0].harvested
    assert packets[1]["private_harvest"]["harvested"] == receipts[1]["harvested"]


@pytest.mark.parametrize("change", [
    {"tick": 1}, {"agent": 1}, {"harvested": -1.}, {"harvested": 4.1},
    {"harvested": float("nan")}, {"harvested": True}, {"version": "wrong"}, {"peer_harvest": 2.},
])
def test_private_receipt_wrong_time_identity_or_hidden_extra_fields_are_rejected(change):
    result = engine.step(world(), (engine.Action(),) * 4)
    packet = engine.observe(result.state, 0)
    receipt = {**adapter.private_harvest_receipts(result)[0], **change}
    with pytest.raises(ValueError):
        adapter.attach_private_harvest(packet, receipt)


def test_adapter_rejects_unrelated_result_and_missing_continuation_receipt():
    result = engine.step(world(), (engine.Action(),) * 4)
    with pytest.raises(ValueError, match="does not produce"):
        adapter.observations(world(), result)
    with pytest.raises(ValueError, match="every own receipt"):
        adapter.observations(result.state, (None,) * 4)


@pytest.mark.parametrize("record,length", [
    (HarvestReceipt(15, 511, 0.), 30),
    (HarvestReceipt(65535, 2**32 - 1, 1.2345678901234567), 30),
    (GrowthEvidence(15, 511, 23.45678901234567, 25.67890123456789), 96),
    (BeliefSummary(15, 31.123456789012345, 0.), 96), (None, 96),
])
def test_codec_has_fixed_ascii_lengths_and_exact_float_roundtrip(record, length):
    text = encode(record)
    assert text.isascii() and len(text.encode("utf-8")) == length
    receipt, social = decode(text)
    returned = receipt if isinstance(record, HarvestReceipt) else social
    assert returned == record
    assert encode(returned) == text
    if record is not None:
        for field, value in asdict(record).items():
            if isinstance(value, float):
                assert struct.pack(">d", getattr(returned, field)) == struct.pack(">d", value)


def test_combined_receipt_and_social_frame_are_126_bytes():
    receipt = HarvestReceipt(0, 3, 0.)
    for social in (GrowthEvidence(0, 0, 20., 22.42), BeliefSummary(0, 40., 10.), None):
        text = encode(receipt) + encode(social)
        assert len(text) == 126
        assert decode(text) == (receipt, social)


@pytest.mark.parametrize("text", ["", "N1", "R1" + "z" * 28,
                                      "N1" + "." * 93 + "x", "λ" * 96,
                                      "E1" + "0" * 44 + "." * 49 + "x"])
def test_malformed_noncanonical_frames_are_rejected(text):
    with pytest.raises(ValueError):
        decode(text)


@pytest.mark.parametrize("record", [HarvestReceipt(-1, 0, 0.), HarvestReceipt(0, -1, 0.),
                                       HarvestReceipt(0, 0, float("nan")),
                                       GrowthEvidence(0, 0, 2., 1.),
                                       BeliefSummary(0, 0., 1.), BeliefSummary(0, 2., -1.)])
def test_invalid_wire_values_are_rejected(record):
    with pytest.raises(ValueError):
        encode(record)


def test_scheduler_reserves_social_slot_matches_bytes_and_keeps_recipients_unique_visible():
    # Agent 2 is visible but outside the extraction cohort; it is the fixed
    # tick-4 social recipient, so one of four receipt slots must be displaced.
    state = replace(world(positions=(1, 1, 2, 1, 1, 1)), tick=4)
    packet = adapter.attach_private_harvest(engine.observe(state, 0),
        {"version": adapter.RECEIPT_VERSION, "tick": 3, "agent": 0, "harvested": 0.})
    receipt, cohort = HarvestReceipt(0, 3, 0.), (0, 1, 3, 4, 5)
    before = deepcopy(packet)
    assert social_recipient(packet) == 2
    messages_l2 = schedule_messages(packet, arm="L2", receipt=receipt, cohort=cohort,
                                    social=GrowthEvidence(0, 0, 20., 22.42))
    messages_l3 = schedule_messages(packet, arm="L3", receipt=receipt, cohort=cohort,
                                    social=BeliefSummary(0, 40., 10.))
    assert [(peer, len(text)) for peer, text in messages_l2] == [(peer, len(text)) for peer, text in messages_l3]
    assert len(messages_l2) == len({peer for peer, _ in messages_l2}) == 4
    assert all(peer in {p["id"] for p in packet["peers"]} for peer, _ in messages_l2)
    assert decode(dict(messages_l2)[2])[0] is None
    assert sum(decode(text)[0] is not None for _, text in messages_l2) == 3
    assert all(len(text) <= 128 for _, text in messages_l2)
    assert len(schedule_messages(packet, arm="L1", receipt=receipt, cohort=cohort)) == 4
    assert packet == before


def test_scheduler_combines_receipt_and_social_and_sends_paid_filler_without_content():
    state = replace(world(), tick=4)
    packet = adapter.attach_private_harvest(engine.observe(state, 0),
        {"version": adapter.RECEIPT_VERSION, "tick": 3, "agent": 0, "harvested": 1.})
    receipt = HarvestReceipt(0, 3, 1.)
    left = schedule_messages(packet, arm="L2", receipt=receipt, cohort=(0, 1, 2))
    right = schedule_messages(packet, arm="L3", receipt=receipt, cohort=(0, 1, 2))
    assert left == right
    assert len(dict(left)[social_recipient(packet)]) == 126
    assert decode(dict(left)[social_recipient(packet)]) == (receipt, None)
    later = deepcopy(packet)
    later["tick"] = 5
    later["private_harvest"]["tick"] = 4
    assert social_recipient(later) is None
    assert all(len(text) == 30 for _, text in schedule_messages(
        later, arm="L2", receipt=HarvestReceipt(0, 4, 1.), cohort=(0, 1, 2)))


def test_scheduler_cannot_send_another_site_amount_or_incomplete_cohort_as_own_receipt():
    _, _, packets = prepared_shared()
    packet = packets[0]
    for receipt, cohort in ((HarvestReceipt(1, 0, 4.), (0, 1, 2)),
                            (HarvestReceipt(0, 0, 3.), (0, 1, 2)),
                            (HarvestReceipt(0, 0, 4.), (0, 1))):
        with pytest.raises(ValueError):
            schedule_messages(packet, arm="L1", receipt=receipt, cohort=cohort)


@pytest.mark.parametrize("send_zero", [False, True])
def test_shared_transition_resolves_at_t_plus_two_only_with_every_receipt_including_zero(send_zero):
    tracker, first, packets = prepared_shared()
    event = tracker.events[(0, 0)]
    assert event["cohort"] == (0, 1, 2)
    assert event["own_harvest"] == 4. and event["total_harvest"] is None
    assert event["resolved"] is False
    assert tracker.counters["confounded"] == 1
    outgoing = [engine.Action() for _ in range(4)]
    outgoing[1] = engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 2.))),))
    if send_zero:
        outgoing[2] = engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 0.))),))
    second = engine.step(first.state, tuple(outgoing))
    packet = adapter.observations(second.state, second)[0]
    original = deepcopy(packet)
    batch = tracker.observe(packet, outgoing[0])
    assert packet == original
    assert all(row.sent_tick == 1 and row.delivery_tick == 2 for row in second.state.messages)
    assert second.ledger.message_cost == pytest.approx(.03 * (1 + send_zero))
    if send_zero:
        row = first.ledger.patches[0]
        assert batch.growth == (GrowthEvidence(0, 0, row.stock_after_harvest, row.stock_after),)
        assert event["resolved"] and event["total_harvest"] == row.harvested == 6.
        assert event["own_harvest"] == 4.
        assert tracker.counters["clean_receipts"] == 1
        assert tracker.counters["clean_own"] == 0
    else:
        assert batch.growth == ()
        assert event["resolved"] is False and event["total_harvest"] is None
    memory = deepcopy(tracker.memory())
    duplicate = tracker.observe(deepcopy(packet), outgoing[0])
    assert duplicate.growth == duplicate.bounds == duplicate.beliefs == ()
    assert tracker.memory() == memory
    assert json.loads(json.dumps(memory)) == memory


def test_receipt_sent_before_its_harvest_cannot_complete_a_same_step_event():
    state = world()
    tracker = ReceiptEvidence()
    tracker.observe(adapter.observations(state)[0])
    actions = (engine.Action(harvest=4.),
               engine.Action(harvest=2., messages=((0, encode(HarvestReceipt(0, 0, 2.))),)),
               engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 0.))),)), engine.Action())
    result = engine.step(state, actions)
    batch = tracker.observe(adapter.observations(result.state, result)[0], actions[0])
    assert batch.growth == ()
    assert tracker.events[(0, 0)]["receipts"] == {0: 4.}


def test_post_commit_movement_can_drop_receipts_without_cleaning_the_archive():
    tracker, first, _ = prepared_shared()
    actions = (engine.Action(move=(-1, 0)),
               engine.Action(move=(1, 0), messages=((0, encode(HarvestReceipt(0, 0, 2.))),)),
               engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 0.))),)), engine.Action())
    result = engine.step(first.state, actions)
    assert result.ledger.messages[0].reason == "out_of_range"
    assert result.ledger.messages[0].cost == 0.
    batch = tracker.observe(adapter.observations(result.state, result)[0], actions[0])
    assert batch.growth == ()
    assert tracker.events[(0, 0)]["resolved"] is False
    assert tracker.events[(0, 0)]["receipts"] == {0: 4., 2: 0.}


def test_unaffordable_zero_harvest_receipt_leaves_shared_event_unresolved():
    tracker, first, _ = prepared_shared(inventories=(5., 5., 0., 5.))
    actions = (engine.Action(), engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 2.))),)),
               engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 0.))),)), engine.Action())
    result = engine.step(first.state, actions)
    assert result.ledger.messages[1].reason == "insufficient_inventory"
    tracker.observe(adapter.observations(result.state, result)[0], actions[0])
    assert tracker.events[(0, 0)]["resolved"] is False


def test_solitary_growth_uses_exact_own_receipt_without_waiting_for_messages():
    state = world(positions=(1, 3, 4, 5))
    tracker = ReceiptEvidence()
    tracker.observe(adapter.observations(state)[0])
    actions = (engine.Action(harvest=4.), engine.Action(), engine.Action(), engine.Action())
    result = engine.step(state, actions)
    batch = tracker.observe(adapter.observations(result.state, result)[0], actions[0])
    row = result.ledger.patches[0]
    assert batch.growth == (GrowthEvidence(0, 0, row.stock_after_harvest, row.stock_after),)
    assert tracker.counters["eligible"] == tracker.counters["clean_own"] == 1
    assert tracker.counters["clean_receipts"] == tracker.counters["confounded"] == 0


@pytest.mark.parametrize("relay,beliefs", [(True, True), (True, False), (False, True), (False, False)])
def test_social_type_flags_filter_payloads_but_keep_combined_receipts(relay, beliefs):
    tracker, first, _ = prepared_shared()
    tracker.accept_relay, tracker.accept_beliefs = relay, beliefs
    growth = GrowthEvidence(1, 0, 20., 22.42)
    summary = BeliefSummary(1, 40., 10.)
    actions = (engine.Action(),
               engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 2.)) + encode(growth)),)),
               engine.Action(messages=((0, encode(HarvestReceipt(0, 0, 0.)) + encode(summary)),)), engine.Action())
    result = engine.step(first.state, actions)
    batch = tracker.observe(adapter.observations(result.state, result)[0], actions[0])
    assert tracker.events[(0, 0)]["resolved"]
    assert ((1, 0) in tracker.known) is relay
    assert bool(batch.beliefs) is beliefs
    assert tracker.counters["new_relay"] == int(relay)
    assert tracker.counters["belief_messages"] == int(beliefs)


def test_relay_provenance_deduplicates_physical_events_across_immediate_senders():
    state = replace(world(), tick=2)
    packet = adapter.observations(state)[0]
    record = GrowthEvidence(1, 0, 20., 22.42)
    packet["messages"] = [direct_message(1, encode(record)), direct_message(2, encode(record))]
    tracker = ReceiptEvidence()
    batch = tracker.observe(packet)
    assert batch.growth == (record,)
    assert tracker.known == {(1, 0): record}
    assert tracker.counters["new_relay"] == tracker.counters["duplicates"] == 1


def test_foreign_sender_cannot_fill_a_missing_member_receipt():
    tracker, first, _ = prepared_shared()
    second = engine.step(first.state, (engine.Action(),) * 4)
    packet = adapter.observations(second.state, second)[0]
    packet["messages"] = [direct_message(3, encode(HarvestReceipt(0, 0, 0.)))]
    tracker.observe(packet, engine.Action())
    assert tracker.events[(0, 0)]["receipts"] == {0: 4.}
    assert not tracker.events[(0, 0)]["resolved"]
