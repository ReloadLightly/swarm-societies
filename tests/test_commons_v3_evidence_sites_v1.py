"""Legal L0 evidence fixtures; evaluator ledgers are test oracles only."""

from copy import deepcopy
from dataclasses import asdict, replace
import json

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3.evidence_sites_v1 import CleanTransition, LocalEvidence


def world(*, agents=((1, 1, 2.), (4, 1, 2.)), stock=5., radius=2,
          weather=.1, capacity=10.):
    config = engine.Config(width=5, height=3, n_agents=2, n_patches=2,
                           sensing_radius=radius, need=1.2, inventory_capacity=20.,
                           site_capacities=(capacity, 20.), initial_site_stocks=(stock, 8.),
                           weather_amplitude=weather)
    state = engine.initialize(config, 17)
    return replace(state,
                    agents=tuple(replace(agent, x=x, y=y, inventory=inventory)
                                 for agent, (x, y, inventory) in zip(state.agents, agents)),
                    patches=(replace(state.patches[0], x=1, y=1),
                             replace(state.patches[1], x=4, y=1)))


def extract(state, action, other=engine.Action()):
    evidence = LocalEvidence()
    before = engine.observe(state, 0)
    initial = evidence.observe(before)
    result = engine.step(state, (action, other))
    after = engine.observe(result.state, 0)
    batch = evidence.observe(after, action)
    return evidence, initial, batch, result, before, after


@pytest.mark.parametrize("stock,harvest_request", [(0., 0.), (2., 0.), (2., 1.), (2., 4.), (5., 4.)])
def test_solitary_extraction_matches_physical_ledger_using_only_local_packets(stock, harvest_request):
    action = engine.Action(harvest=harvest_request)
    _, _, batch, result, _, _ = extract(world(stock=stock), action)
    assert batch.reason == "clean"
    assert len(batch.transitions) == 1
    transition = batch.transitions[0]
    row = result.ledger.patches[0]
    assert transition.site == 0
    assert transition.tick == 0
    assert transition.own_harvest == pytest.approx(result.ledger.agents[0].harvested, abs=1e-14)
    assert transition.stock_before == row.stock_before
    assert transition.z == pytest.approx(row.stock_after_harvest, abs=1e-14)
    assert transition.stock_next == row.stock_after
    assert transition.stock_next - transition.z == pytest.approx(row.growth, abs=1e-14)


def test_move_into_a_previously_visible_site_uses_actual_extraction_location():
    state = world(agents=((0, 1, 2.), (4, 1, 2.)))
    _, _, batch, result, before, after = extract(state, engine.Action(move=(1, 0), harvest=2.))
    assert (before["self"]["x"], after["self"]["x"]) == (0, 1)
    assert result.ledger.agents[0].moved
    assert batch.transitions == (CleanTransition(0, 0, 3., result.state.patches[0].stock, 5., 2.),)


def test_unaffordable_failed_move_keeps_evidence_for_the_actual_old_site():
    state = world(agents=((1, 1, 0.), (4, 1, 2.)))
    _, _, batch, result, _, after = extract(state, engine.Action(move=(1, 0), harvest=2.))
    assert not result.ledger.agents[0].moved
    assert (after["self"]["x"], after["self"]["y"]) == (1, 1)
    assert batch.reason == "clean"
    assert batch.transitions[0].own_harvest == result.ledger.agents[0].harvested == 2.


def test_departing_observer_does_not_use_an_adjacent_site_transition():
    _, _, batch, result, _, after = extract(world(), engine.Action(move=(1, 0), harvest=2.))
    assert any(site["id"] == 0 for site in after["sites"])
    assert result.ledger.patches[0].harvested == 0.
    assert batch.reason == "off_site"
    assert batch.transitions == ()
    assert 0 in {bound.site for bound in batch.bounds}


def test_adjacent_empty_site_is_bounds_only_despite_known_zero_extraction():
    state = world(agents=((0, 1, 2.), (4, 1, 2.)))
    _, _, batch, result, _, _ = extract(state, engine.Action())
    assert result.ledger.patches[0].harvested == 0.
    assert batch.reason == "off_site"
    assert batch.transitions == ()
    assert batch.bounds[0].stock == result.state.patches[0].stock


@pytest.mark.parametrize("radius", [0, 2])
def test_arriving_peer_confounds_the_transition_even_if_not_visible_before(radius):
    state = world(agents=((1, 1, 2.), (2, 1, 2.)), radius=radius)
    _, _, batch, result, before, after = extract(
        state, engine.Action(harvest=3.), engine.Action(move=(-1, 0), harvest=3.))
    assert before["sites"][0]["peer_count"] == 1
    assert after["sites"][0]["peer_count"] == 2
    if radius == 0:
        assert before["peers"] == []
    assert result.ledger.agents[1].harvested > 0.
    assert batch.reason == "shared"
    assert batch.transitions == ()


def test_peer_departure_before_extraction_permits_solitary_transition():
    state = world(agents=((1, 1, 2.), (1, 1, 2.)))
    _, _, batch, result, before, after = extract(
        state, engine.Action(harvest=2.), engine.Action(move=(1, 0), harvest=3.))
    assert before["sites"][0]["peer_count"] == 2
    assert after["sites"][0]["peer_count"] == 1
    assert result.ledger.agents[1].harvested == 0.
    assert batch.reason == "clean"
    assert batch.transitions[0].own_harvest == result.ledger.patches[0].harvested == 2.


def test_shared_site_is_rejected_even_when_peer_happens_to_request_zero():
    state = world(agents=((1, 1, 2.), (1, 1, 2.)))
    _, _, batch, result, _, _ = extract(state, engine.Action(harvest=2.))
    assert result.ledger.agents[1].harvested == 0.
    assert batch.reason == "shared"
    assert batch.transitions == ()


def test_receipt_like_messages_do_not_make_shared_transitions_clean_in_l0():
    state = world(agents=((1, 1, 2.), (1, 1, 2.)))
    _, _, batch, _, _, after = extract(
        state, engine.Action(harvest=2.),
        engine.Action(harvest=1., messages=((0, '{"site":0,"tick":0,"harvest":1}'),)))
    assert after["messages"]
    assert batch.reason == "shared"
    assert batch.transitions == ()


def test_first_arrival_without_previous_stock_observation_has_only_a_bound():
    state = world(agents=((0, 1, 2.), (4, 1, 2.)), radius=0)
    _, initial, batch, result, before, _ = extract(state, engine.Action(move=(1, 0), harvest=2.))
    assert before["sites"] == []
    assert initial.bounds == ()
    assert batch.reason == "not_observed_before"
    assert batch.transitions == ()
    assert batch.bounds[0].stock == result.state.patches[0].stock


def test_empty_site_with_zero_request_supplies_recovery_transition():
    _, _, batch, result, _, _ = extract(world(stock=0., weather=0.), engine.Action())
    transition = batch.transitions[0]
    assert transition.z == transition.own_harvest == transition.stock_before == 0.
    assert transition.stock_next == result.ledger.patches[0].growth == .02


def test_clipped_transition_has_no_privileged_saturation_label():
    _, _, batch, result, _, _ = extract(world(stock=9.99, weather=0.), engine.Action())
    assert result.ledger.patches[0].growth_waste > 0.
    transition = batch.transitions[0]
    assert transition.stock_next == 10.
    assert asdict(transition) == {"site": 0, "tick": 0, "z": 9.99,
                                  "stock_next": 10., "stock_before": 9.99, "own_harvest": 0.}
    assert batch.bounds[0].stock == transition.stock_next


def test_costs_transfers_and_inventory_overflow_do_not_change_gross_harvest_inference():
    state = world(agents=((1, 1, 19.), (2, 1, 10.)))
    _, _, batch, result, before, after = extract(
        state, engine.Action(harvest=4., transfers=((1, 1.),), messages=((1, "paid"),)),
        engine.Action(transfers=((0, 2.),)))
    row = result.ledger.agents[0]
    assert row.message_cost > 0 and row.transfer_in > 0 and row.transfer_out > 0 and row.waste > 0
    assert after["self"]["inventory"] - before["self"]["inventory"] != row.harvested
    assert batch.transitions[0].own_harvest == row.harvested == 4.


def test_stock_bounds_cover_every_visible_site_and_never_decrease():
    state = world(agents=((2, 1, 2.), (4, 1, 2.)))
    evidence = LocalEvidence()
    initial = evidence.observe(engine.observe(state, 0))
    assert [(bound.site, bound.stock) for bound in initial.bounds] == [(0, 5.), (1, 8.)]
    result = engine.step(state, (engine.Action(), engine.Action(harvest=4.)))
    batch = evidence.observe(engine.observe(result.state, 0), engine.Action())
    assert batch.reason == "off_site"
    assert batch.transitions == ()
    assert evidence.max_stock[1] == 8.
    assert 1 not in {bound.site for bound in batch.bounds}
    assert evidence.max_stock[0] == result.state.patches[0].stock > 5.


def test_gap_emits_no_transition_and_resets_to_current_observation():
    state = world()
    evidence = LocalEvidence()
    evidence.observe(engine.observe(state, 0))
    action = engine.Action(harvest=1.)
    for _ in range(2):
        state = engine.step(state, (action, engine.Action())).state
    gap = evidence.observe(engine.observe(state, 0), action)
    assert gap.reason == "skipped_ticks"
    assert gap.transitions == ()
    state = engine.step(state, (action, engine.Action())).state
    resumed = evidence.observe(engine.observe(state, 0), action)
    assert resumed.transitions[0].tick == 2
    assert evidence.seen == {(0, 2)}


def test_repeated_observation_cannot_apply_the_same_physical_event_twice():
    evidence, _, batch, _, _, after = extract(world(), engine.Action(harvest=1.))
    before = deepcopy(evidence.memory())
    assert batch.transitions[0].tick == 0
    duplicate = evidence.observe(deepcopy(after), engine.Action(harvest=1.))
    assert duplicate.reason == "repeated_observation"
    assert duplicate.bounds == duplicate.transitions == ()
    assert evidence.seen == {(0, 0)}
    assert evidence.memory() == before


def test_missing_previous_action_does_not_infer_harvest_from_inventory():
    state = world()
    evidence = LocalEvidence()
    evidence.observe(engine.observe(state, 0))
    state = engine.step(state, (engine.Action(harvest=2.), engine.Action())).state
    batch = evidence.observe(engine.observe(state, 0))
    assert batch.reason == "missing_action"
    assert batch.transitions == ()
    assert evidence.seen == set()


def test_input_packets_and_returned_memory_cannot_mutate_cached_evidence():
    state = world()
    before = engine.observe(state, 0)
    before_copy = deepcopy(before)
    evidence = LocalEvidence()
    evidence.observe(before)
    result = engine.step(state, (engine.Action(harvest=1.), engine.Action()))
    after = engine.observe(result.state, 0)
    after_copy = deepcopy(after)
    evidence.observe(after, engine.Action(harvest=1.))
    assert before == before_copy and after == after_copy
    memory = evidence.memory()
    assert json.loads(json.dumps(memory)) == memory
    after["sites"][0]["stock"] = 999.
    memory["previous"]["sites"][0]["stock"] = 888.
    assert evidence.memory()["previous"]["sites"][0]["stock"] == after_copy["sites"][0]["stock"]
    assert set(evidence.memory()["previous"]) == {"tick", "self", "sites", "peers"}
    assert "ecology" not in evidence.memory()["previous"]


def test_unused_message_ecology_and_evaluator_like_fields_are_not_read_or_cached():
    class Unreadable:
        def __iter__(self):
            raise AssertionError("unnecessary privileged input was accessed")

        def __deepcopy__(self, memo):
            raise AssertionError("unnecessary privileged input was copied")

    observation = engine.observe(world(), 0)
    for key in ("messages", "ecology", "ledger", "weather", "true_capacities"):
        observation[key] = Unreadable()
    evidence = LocalEvidence()
    batch = evidence.observe(observation)
    assert batch.reason == "initial"
    json.dumps(evidence.memory())


@pytest.mark.parametrize("change", [
    lambda packet: packet.update(tick=-1),
    lambda packet: packet.update(observation_version="wrong"),
    lambda packet: packet["sites"][0].update(stock=float("nan")),
    lambda packet: packet["sites"][0].update(peer_count=2),
    lambda packet: packet["self"].update(id=True),
    lambda packet: packet["sites"].append(deepcopy(packet["sites"][0])),
])
def test_invalid_local_packet_is_rejected_without_changing_memory(change):
    evidence = LocalEvidence()
    before = evidence.memory()
    observation = engine.observe(world(), 0)
    change(observation)
    with pytest.raises(ValueError):
        evidence.observe(observation)
    assert evidence.memory() == before


def test_wrong_observer_or_conflicting_same_tick_is_rejected():
    state = world()
    evidence = LocalEvidence()
    evidence.observe(engine.observe(state, 0))
    before = evidence.memory()
    with pytest.raises(ValueError, match="different observer"):
        evidence.observe(engine.observe(state, 1))
    conflicting = engine.observe(state, 0)
    conflicting["sites"][0]["stock"] += .1
    with pytest.raises(ValueError, match="conflicting"):
        evidence.observe(conflicting)
    assert evidence.memory() == before


@pytest.mark.parametrize("action", [
    {}, engine.Action(move=(1, 1)), engine.Action(harvest=float("nan")), engine.Action(harvest=5.),
    engine.Action(move=(1, 0)),
])
def test_invalid_or_inconsistent_previous_action_does_not_change_evidence(action):
    state = world()
    evidence = LocalEvidence()
    evidence.observe(engine.observe(state, 0))
    state = engine.step(state, (engine.Action(), engine.Action())).state
    before = evidence.memory()
    with pytest.raises(ValueError):
        evidence.observe(engine.observe(state, 0), action)
    assert evidence.memory() == before
