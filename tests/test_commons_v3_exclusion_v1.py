"""Physical exclusion fixtures; these do not qualify useful institutions."""

from copy import deepcopy
from dataclasses import replace
import json
import math

import pytest

from swarm_societies.commons_v3 import engine as physical
from swarm_societies.commons_v3 import politics_v1 as politics
from swarm_societies.commons_v3 import exclusion_v1 as exclusion


def world(rows=((0, 0, 2.), (0, 0, 2.), (0, 0, 2.)), patches=((0, 0, 12.),), **updates):
    values = dict(width=4, height=4, n_agents=len(rows), n_patches=len(patches),
        sensing_radius=1, need=0., initial_inventory=2., inventory_capacity=80.,
        patch_capacity=40., initial_patch_stock=12., renewal_rate=0., recovery=0.,
        weather_amplitude=0., max_harvest=8., movement_cost=.2,
        harvest_cost_per_unit=0., message_byte_cost=.01)
    values.update(updates)
    state = exclusion.initialize(physical.Config(**values), seed=42)
    physical_state = replace(state.political.world,
        agents=tuple(replace(a, x=x, y=y, inventory=inventory)
                     for a, (x, y, inventory) in zip(state.political.world.agents, rows)),
        patches=tuple(replace(p, x=x, y=y, stock=stock)
                      for p, (x, y, stock) in zip(state.political.world.patches, patches)))
    return replace(state, political=replace(state.political, world=physical_state))


def affiliated(state, members=(0, 1), identity=0, site=0):
    institution = politics.Institution(identity, site, politics.Charter(), tuple(members),
                                      tuple(politics.Bond(a, 1.) for a in members))
    return replace(state, political=replace(state.political,
        institutions=(*state.political.institutions, institution), next_id=identity + 1))


def advance(state, requests=None, forces=None, intents=None):
    n = state.political.world.config.n_agents
    actions = [physical.Action(harvest=(requests or {}).get(a, 0.)) for a in range(n)]
    return exclusion.step(state, actions,
        [(intents or {}).get(a, politics.Intent()) for a in range(n)],
        [(forces or {}).get(a, exclusion.Force()) for a in range(n)])


def assert_balance(before, result):
    p = result.political.physical.ledger
    start = sum(a.inventory for a in before.political.world.agents) + politics.custody(before.political)
    end = sum(a.inventory for a in result.state.political.world.agents) + politics.custody(result.state.political)
    assert start + p.stock_before + p.growth == pytest.approx(
        end + p.stock_after + p.consumption + p.movement_cost + p.message_cost
        + p.harvest_cost + p.waste + result.political.ledger.political_cost
        + result.political.ledger.forfeited + result.ledger.guard_cost
        + result.ledger.resistance_cost, abs=1e-10)
    assert abs(result.ledger.residual) < 1e-10


@pytest.mark.parametrize("contention", ["proportional", "keyed_priority"])
def test_disabled_extension_exactly_matches_political_transition(contention):
    state = world(contention=contention, renewal_rate=.2, need=1.2)
    old = state.political
    for _ in range(5):
        actions = [physical.Action(harvest=2.), physical.Action(harvest=4.), physical.Action()]
        reference = politics.step(old, actions)
        result = exclusion.step(state, actions)
        assert result.political == reference
        assert result.state.political == reference.state
        assert result.ledger.guard_cost == result.ledger.resistance_cost == 0.
        assert_balance(state, result)
        state, old = result.state, reference.state


def test_claim_without_guards_grants_no_priority():
    state = affiliated(world(patches=((0, 0, 3.),)))
    result = advance(state, {0: 3., 1: 3., 2: 3.})
    assert [row.harvested for row in result.ledger.agents] == [1., 1., 1.]
    assert [row.pressure for row in result.ledger.agents] == [0., 0., 0.]


def test_member_guard_cost_opportunity_cost_and_outsider_pressure():
    state = affiliated(world(patches=((0, 0, 6.),)))
    result = advance(state, {0: 4., 1: 4., 2: 4.}, {0: exclusion.Force(guard=2.)})
    rows = result.ledger.agents
    assert rows[0].guard_cost == .2
    assert rows[0].guard_foregone_request == 4.
    assert rows[0].effective_harvest == rows[0].harvested == 0.
    assert rows[1].effective_harvest == 4.
    assert rows[2].pressure == 2.
    assert rows[2].effective_harvest == pytest.approx(4. / 3.)
    assert rows[2].blocked_request == pytest.approx(8. / 3.)
    assert rows[0].coalition == rows[1].coalition == ("institution", 0)
    assert rows[2].coalition == ("individual", 2)
    assert_balance(state, result)


def test_solo_occupation_uses_same_physical_capability_and_finite_effort():
    state = world()
    result = advance(state, {1: 4., 2: 4.}, {0: exclusion.Force(guard=2.)})
    assert [row.pressure for row in result.ledger.agents] == [0., 1., 1.]
    assert [row.harvested for row in result.ledger.agents] == [0., 2., 2.]
    assert result.ledger.agents[0].coalition == ("individual", 0)
    assert_balance(state, result)


def test_resistance_restores_some_access_at_real_private_cost():
    state = affiliated(world())
    simple = advance(state, {2: 4.}, {0: exclusion.Force(guard=2.)})
    resisting = advance(state, {2: 4.}, {0: exclusion.Force(guard=2.), 2: exclusion.Force(resist=2.)})
    assert simple.ledger.agents[2].harvested == pytest.approx(4. / 3.)
    assert resisting.ledger.agents[2].harvested == pytest.approx(12. / 5.)
    assert resisting.ledger.agents[2].resistance_cost == .2
    assert resisting.state.resistance_cost == .2
    assert_balance(state, resisting)


def test_zero_pressure_does_not_change_resisting_harvest_but_still_costs():
    state = world()
    result = advance(state, {2: 4.}, {2: exclusion.Force(resist=2.)})
    assert result.ledger.agents[2].harvested == 4.
    assert result.ledger.agents[2].blocked_request == 0.
    assert result.ledger.resistance_cost == .2
    assert_balance(state, result)


def test_unopposed_guard_still_pays_and_forgoes_requested_harvest():
    state = world()
    result = advance(state, {0: 4.}, {0: exclusion.Force(guard=1.)})
    assert result.ledger.guard_cost == .1
    assert result.ledger.agents[0].harvested == 0.
    assert result.state.political.world.agents[0].inventory == 1.9


def test_rival_coalitions_contest_each_other_and_split_pressure_on_unaffiliated():
    state = world(rows=((0, 0, 2.),) * 5)
    state = affiliated(affiliated(state, (0, 1), 0), (2, 3), 1)
    result = advance(state, {1: 4., 3: 4., 4: 4.},
                     {0: exclusion.Force(guard=2.), 2: exclusion.Force(guard=2.)})
    rows = result.ledger.agents
    assert rows[1].pressure == rows[3].pressure == 1.
    assert rows[4].pressure == 2.
    assert math.fsum(row.pressure for row in rows) == 4.
    assert_balance(state, result)


def test_empty_stock_and_full_inventory_do_not_refund_committed_cost():
    state = world(rows=((0, 0, 80.), (0, 0, 80.), (0, 0, 80.)), patches=((0, 0, 0.),))
    result = advance(state, {2: 4.}, {0: exclusion.Force(guard=2.), 2: exclusion.Force(resist=2.)})
    assert result.ledger.guard_cost == result.ledger.resistance_cost == .2
    assert result.ledger.agents[2].harvested == 0.
    assert_balance(state, result)


@pytest.mark.parametrize("force", [exclusion.Force(guard=1.), exclusion.Force(resist=1.)])
def test_unaffordable_force_has_no_cost_or_effect_and_harvest_remains(force):
    state = world(rows=((0, 0, .05), (0, 0, 2.), (0, 0, 2.)))
    result = advance(state, {0: 4., 1: 4.}, {0: force})
    row = result.ledger.agents[0]
    assert not row.force_ok and row.reason == "insufficient_inventory"
    assert row.effective_harvest == row.harvested == 4.
    assert result.ledger.guard_cost == result.ledger.resistance_cost == 0.


def test_incoming_transfer_cannot_finance_guarding():
    state = world(rows=((0, 0, 0.), (0, 0, 2.), (0, 0, 2.)))
    result = exclusion.step(state, [physical.Action(), physical.Action(transfers=((0, 1.),)), physical.Action()],
                            forces=[exclusion.Force(guard=1.), exclusion.Force(), exclusion.Force()])
    assert result.ledger.agents[0].reason == "insufficient_inventory"
    assert result.state.political.world.agents[0].inventory == 1.


@pytest.mark.parametrize("move,rows", [((1, 0), ((0, 0, 2.), (0, 0, 2.), (0, 0, 2.))),
    ((0, 0), ((1, 0, 2.), (0, 0, 2.), (0, 0, 2.)))])
def test_guard_must_be_opening_local_and_commit_stationary(move, rows):
    state = world(rows=rows)
    result = exclusion.step(state, [physical.Action(move=move), physical.Action(harvest=4.), physical.Action()],
                            forces=[exclusion.Force(guard=1.), exclusion.Force(), exclusion.Force()])
    assert result.ledger.agents[0].reason == "not_stationary_at_site"
    assert result.ledger.guard_cost == 0.


def test_resistance_requires_positive_request():
    result = advance(world(), forces={0: exclusion.Force(resist=1.)})
    assert result.ledger.agents[0].reason == "no_harvest_request"
    assert result.ledger.resistance_cost == 0.


def test_arriving_outsider_is_contested_using_actual_position():
    state = affiliated(world(rows=((0, 0, 2.), (0, 0, 2.), (1, 0, 2.))))
    result = exclusion.step(state, [physical.Action(), physical.Action(), physical.Action(move=(-1, 0), harvest=4.)],
                            forces=[exclusion.Force(guard=2.), exclusion.Force(), exclusion.Force(resist=2.)])
    assert result.ledger.agents[2].reason == "not_stationary_at_site"
    assert result.ledger.agents[2].pressure == 2.
    assert result.ledger.agents[2].harvested == pytest.approx(4. / 3.)
    assert_balance(state, result)


def test_failed_move_does_not_create_remote_pressure():
    state = affiliated(world(rows=((0, 0, 2.), (0, 0, 2.), (1, 0, .05)),
                             patches=((0, 0, 12.), (1, 0, 12.))))
    result = exclusion.step(state, [physical.Action(), physical.Action(), physical.Action(move=(-1, 0), harvest=4.)],
                            forces=[exclusion.Force(guard=2.), exclusion.Force(), exclusion.Force()])
    assert result.ledger.agents[2].pressure == 0.
    assert result.ledger.agents[2].harvested == 4.
    assert_balance(state, result)


def test_member_returning_to_own_site_is_protected():
    state = affiliated(world(rows=((0, 0, 2.), (1, 0, 2.), (0, 0, 2.))))
    result = exclusion.step(state, [physical.Action(), physical.Action(move=(-1, 0), harvest=4.), physical.Action(harvest=4.)],
                            forces=[exclusion.Force(guard=2.), exclusion.Force(), exclusion.Force()])
    assert result.ledger.agents[1].pressure == 0.
    assert result.ledger.agents[1].coalition == ("institution", 0)
    assert result.ledger.agents[2].pressure == 2.


def test_members_at_another_site_have_no_remote_coalition_immunity():
    state = affiliated(world(rows=((1, 0, 2.), (1, 0, 2.), (0, 0, 2.)),
                             patches=((0, 0, 12.), (1, 0, 12.))))
    result = advance(state, {1: 4.}, {0: exclusion.Force(guard=2.)})
    assert result.ledger.agents[1].coalition == ("individual", 1)
    assert result.ledger.agents[1].pressure == 2.


def test_same_tick_join_cannot_buy_retrospective_immunity():
    state = affiliated(world())
    first = advance(state, {2: 4.}, {0: exclusion.Force(guard=2.)},
                    {2: politics.Intent("join", target=0)})
    assert 2 in first.state.political.institutions[0].members
    assert first.ledger.agents[2].pressure == 2.
    second = advance(first.state, {2: 4.}, {0: exclusion.Force(guard=2.)})
    assert second.ledger.agents[2].pressure == 0.
    assert_balance(state, first)


def test_exit_retains_opening_immunity_for_current_tick_only():
    state = affiliated(world())
    first = advance(state, {1: 4.}, {0: exclusion.Force(guard=2.)},
                    {1: politics.Intent("exit", target=0)})
    assert first.ledger.agents[1].pressure == 0.
    second = advance(first.state, {1: 4.}, {0: exclusion.Force(guard=2.)})
    assert second.ledger.agents[1].pressure == 2.
    assert_balance(state, first)


def test_force_payment_precedes_political_fees_and_can_prevent_proposal():
    state = world(rows=((0, 0, .15), (0, 0, 2.), (0, 0, 2.)))
    result = advance(state, forces={0: exclusion.Force(guard=1.)},
                     intents={0: politics.Intent("propose", target=0, charter=politics.Charter())})
    assert result.ledger.guard_cost == .1
    assert not result.state.political.proposals
    assert result.political.ledger.political_cost == 0.
    assert_balance(state, result)


def test_consumption_stock_custody_growth_and_cost_accounting():
    state = affiliated(world(need=1.2, renewal_rate=.24, recovery=.02,
                             harvest_cost_per_unit=.02, weather_amplitude=.1))
    actions = [physical.Action(messages=((1, "guard"),)), physical.Action(harvest=4.), physical.Action(harvest=4.)]
    result = exclusion.step(state, actions,
        [politics.Intent("pay", target=0, amount=.3), politics.Intent(), politics.Intent()],
        [exclusion.Force(guard=2.), exclusion.Force(), exclusion.Force(resist=1.)])
    assert result.political.ledger.custody_after == pytest.approx(2.3)
    assert result.ledger.agents[0].consumption == 1.2
    assert result.political.physical.ledger.message_cost == .05
    assert_balance(state, result)


def test_paid_audit_records_final_contested_harvest_and_only_one_fee():
    state = affiliated(world())
    result = advance(state, {2: 4.}, {0: exclusion.Force(guard=2.)},
                     {1: politics.Intent("monitor", target=0)})
    evidence = next(row for row in result.state.political.evidence if row.subject == 2)
    assert evidence.harvested == result.ledger.agents[2].harvested == pytest.approx(4. / 3.)
    assert result.political.ledger.political_cost == state.political.config.monitoring_cost
    assert len(result.state.political.evidence) == 3
    assert_balance(state, result)


def test_exclusion_does_not_seize_outsider_inventory_or_automatically_enforce_quota():
    state = affiliated(world())
    result = advance(state, {1: 4., 2: 4.}, {0: exclusion.Force(guard=2.)})
    assert result.ledger.agents[1].harvested > state.political.institutions[0].charter.quota
    assert result.political.ledger.forfeited == 0.
    assert result.state.political.world.agents[2].inventory == pytest.approx(
        state.political.world.agents[2].inventory + result.ledger.agents[2].harvested)


def test_observation_adds_only_public_config_no_force_or_global_payoff_information():
    state = world(rows=((0, 0, 2.), (3, 3, 71.), (0, 0, 2.)))
    packet = exclusion.observe(state, 0)
    original = politics.observe(state.political, 0)
    assert packet.pop("exclusion") == {"version": exclusion.VERSION, "config": {
        "guard_unit_cost": .1, "resistance_unit_cost": .1, "max_effort": 4.}}
    assert packet == original
    assert exclusion.observations(state)[0] == exclusion.observe(state, 0)


def test_snapshot_round_trip_and_continuation_with_membership_and_costs():
    state = affiliated(world())
    first = advance(state, {1: 4., 2: 4.}, {0: exclusion.Force(guard=2.), 2: exclusion.Force(resist=1.)})
    wire = json.loads(json.dumps(exclusion.snapshot(first.state)))
    restored = exclusion.restore(wire)
    assert restored == first.state
    for _ in range(4):
        left = advance(first.state, {1: 2., 2: 2.}, {0: exclusion.Force(guard=1.)})
        right = advance(restored, {1: 2., 2: 2.}, {0: exclusion.Force(guard=1.)})
        assert left == right
        first, restored = left, right.state


@pytest.mark.parametrize("field,value", [("guard_unit_cost", 0.), ("guard_unit_cost", -1.),
    ("guard_unit_cost", True), ("resistance_unit_cost", float("nan")), ("max_effort", 0.),
    ("max_effort", float("inf"))])
def test_invalid_config_rejected(field, value):
    with pytest.raises(ValueError):
        exclusion.ExclusionConfig(**{field: value})


@pytest.mark.parametrize("values", [{"guard": -1.}, {"resist": True}, {"guard": float("nan")},
    {"resist": float("inf")}, {"guard": 1., "resist": 1.}])
def test_invalid_force_rejected(values):
    with pytest.raises(ValueError):
        exclusion.Force(**values)


@pytest.mark.parametrize("forces", [[], [exclusion.Force()] * 2, [None] * 3,
    [exclusion.Force(guard=5.), exclusion.Force(), exclusion.Force()]])
def test_joint_force_validation_is_atomic(forces):
    state = world()
    before = exclusion.snapshot(state)
    with pytest.raises(ValueError):
        exclusion.step(state, [physical.Action()] * 3, forces=forces)
    assert exclusion.snapshot(state) == before


@pytest.mark.parametrize("mutation", ["digest", "version", "field", "config", "cost", "nested"])
def test_checkpoint_corruption_and_invalid_resigned_states_rejected(mutation):
    wire = deepcopy(exclusion.snapshot(world()))
    if mutation == "digest":
        wire["sha256"] = "incorrect"
    elif mutation == "version":
        wire["version"] = "other"
    elif mutation == "field":
        wire["state"]["extra"] = 1
    elif mutation == "config":
        del wire["state"]["config"]["max_effort"]
    elif mutation == "cost":
        wire["state"]["guard_cost"] = -1.
    elif mutation == "nested":
        wire["state"]["political"]["state"]["next_id"] = 99
    if mutation != "digest":
        wire["sha256"] = exclusion._digest({key: wire[key] for key in ("version", "state")})
    with pytest.raises(ValueError):
        exclusion.restore(wire)
