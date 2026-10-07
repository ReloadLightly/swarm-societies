"""Independent checks of supplied political capabilities, not governance benefits."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from swarm_societies.commons_v3 import engine as physical
from swarm_societies.commons_v3 import politics_v1 as politics


def world(agent_rows=((0, 0, 6.), (0, 0, 6.), (1, 0, 6.)),
          patch_rows=((0, 0, 10.),), **changes):
    """Exact fixtures remove incidental growth, consumption and physical costs."""
    values = dict(width=5, height=5, n_agents=len(agent_rows),
                  n_patches=len(patch_rows), sensing_radius=1, need=0.,
                  initial_inventory=6., inventory_capacity=20., patch_capacity=20.,
                  initial_patch_stock=10., renewal_rate=0., recovery=0.,
                  weather_amplitude=0., max_harvest=10., movement_cost=0.,
                  harvest_cost_per_unit=0., message_byte_cost=0.)
    values.update(changes)
    state = politics.initialize(physical.Config(**values), seed=17)
    material = replace(state.world,
        agents=tuple(replace(agent, x=x, y=y, inventory=inventory)
                     for agent, (x, y, inventory) in zip(state.world.agents, agent_rows)),
        patches=tuple(replace(patch, x=x, y=y, stock=stock)
                      for patch, (x, y, stock) in zip(state.world.patches, patch_rows)))
    return replace(state, world=material)


def idle(state):
    return tuple(physical.Action() for _ in state.world.agents)


def advance(state, intents=None, actions=None):
    requests = tuple((intents or {}).get(i, politics.Intent())
                     for i in range(len(state.world.agents)))
    return politics.step(state, actions or idle(state), requests)


def found(state=None, charter=None):
    state = world() if state is None else state
    charter = politics.Charter() if charter is None else charter
    proposed = advance(state, {0: politics.Intent('propose', target=0, charter=charter)})
    proposal_id = proposed.state.proposals[-1].id
    formed = advance(proposed.state, {0: politics.Intent('endorse', target=proposal_id),
                                      1: politics.Intent('endorse', target=proposal_id)})
    institution = next(item for item in formed.state.institutions if item.active)
    assert institution.members == (0, 1)
    return formed.state, institution.id


def institution(state, institution_id):
    return next(item for item in state.institutions if item.id == institution_id)


def bond(state, institution_id, owner):
    return next(item for item in institution(state, institution_id).bonds if item.owner == owner)


def assert_conserved(result):
    """Check the outer budget independently of its reported residual."""
    ledger, physical_ledger = result.ledger, result.physical.ledger
    before = ledger.inventory_before + ledger.custody_before + physical_ledger.stock_before
    after = (ledger.inventory_after + ledger.custody_after + physical_ledger.stock_after
             + physical_ledger.consumption + physical_ledger.movement_cost
             + physical_ledger.message_cost + physical_ledger.harvest_cost
             + physical_ledger.waste + ledger.political_cost + ledger.forfeited)
    assert before + physical_ledger.growth == pytest.approx(after, abs=1e-10)
    assert ledger.inventory_after == pytest.approx(sum(a.inventory for a in result.state.world.agents))
    assert abs(ledger.residual) < 1e-10
    assert abs(ledger.physical_residual) < 1e-10


def test_initially_absent_politics_preserves_frozen_physical_initialization():
    config = physical.Config()
    state = politics.initialize(config, seed=61001)
    assert state.world == physical.initialize(config, seed=61001)
    packets = politics.observations(state)
    originals = physical.observations(state.world)
    assert len(packets) == len(originals)
    for packet, original in zip(packets, originals):
        assert {key: packet[key] for key in original} == original


def test_inactive_extension_reproduces_full_physical_results_exactly():
    state = world(need=.4, movement_cost=.03, harvest_cost_per_unit=.02,
                  message_byte_cost=.001, renewal_rate=.24,
                  weather_amplitude=.1)
    material = state.world
    for tick in range(6):
        actions = (physical.Action(harvest=1.3, transfers=((1, .1),),
                                   messages=((1, f'tick {tick}'),)),
                   physical.Action(harvest=.7, reserve=.2),
                   physical.Action(move=(0, 1) if tick % 2 == 0 else (0, -1)))
        expected = physical.step(material, actions)
        actual = politics.step(state, actions)
        assert actual.physical == expected
        assert actual.state.world == expected.state
        state, material = actual.state, expected.state


def test_explicit_inaction_and_omitted_intents_are_equivalent():
    state = world()
    explicit = tuple(politics.Intent() for _ in state.world.agents)
    assert politics.step(state, idle(state), explicit) == politics.step(state, idle(state))


def test_invalid_physical_action_is_atomic_with_political_state():
    state = world()
    before = politics.snapshot(state)
    actions = list(idle(state))
    actions[0] = physical.Action(move=(-1, 0))
    with pytest.raises(ValueError):
        politics.step(state, actions)
    assert politics.snapshot(state) == before


def test_checkpoint_round_trip_is_independent_and_detects_tampering():
    state = world()
    saved = politics.snapshot(state)
    assert politics.restore(saved) == state
    damaged = deepcopy(saved)
    damaged['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        politics.restore(damaged)
    assert politics.snapshot(state) == saved


def test_local_endorsement_requires_another_willing_individual_and_refusal_is_free():
    state = world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.)))
    charter = politics.Charter(bond=1.)
    proposal = advance(state, {0: politics.Intent('propose', target=0, charter=charter)})
    proposal_id = proposal.state.proposals[-1].id
    refused = advance(proposal.state, {0: politics.Intent('endorse', target=proposal_id),
                                       1: politics.Intent('refuse', target=proposal_id)})
    assert not any(item.active for item in refused.state.institutions)
    assert refused.state.world.agents[1].inventory == 6.
    formed = advance(refused.state, {0: politics.Intent('endorse', target=proposal_id),
                                     1: politics.Intent('endorse', target=proposal_id),
                                     2: politics.Intent('refuse', target=proposal_id)})
    active = next(item for item in formed.state.institutions if item.active)
    assert active.members == (0, 1)
    assert formed.state.world.agents[2].inventory == 6.
    assert bond(formed.state, active.id, 0).amount == 1.
    assert bond(formed.state, active.id, 1).amount == 1.
    assert_conserved(proposal)
    assert_conserved(refused)
    assert_conserved(formed)


def test_dues_are_voluntary_and_a_quota_does_not_clamp_harvesting():
    state, identity = found(charter=politics.Charter(quota=1., bond=1., dues=.5))
    inventories = [agent.inventory for agent in state.world.agents]
    abstained = advance(state)
    assert [agent.inventory for agent in abstained.state.world.agents] == inventories
    assert institution(abstained.state, identity).members == (0, 1)
    paid = advance(abstained.state, {0: politics.Intent('pay', target=identity, amount=.5)})
    assert institution(paid.state, identity).treasury == pytest.approx(.5)
    assert paid.state.world.agents[0].inventory == pytest.approx(inventories[0] - .5)
    actions = list(idle(paid.state))
    actions[1] = physical.Action(harvest=3.)
    violated = advance(paid.state, actions=actions)
    assert violated.physical.ledger.agents[1].harvested == 3.
    assert bond(violated.state, identity, 1).amount == 1.
    assert not violated.state.evidence
    assert_conserved(paid)
    assert_conserved(violated)


def test_paid_local_monitor_records_actual_contended_harvest_not_requests():
    state, identity = found(world(patch_rows=((0, 0, 2.),)),
                            politics.Charter(quota=1.5, bond=1.))
    actions = (physical.Action(harvest=4.), physical.Action(harvest=4.), physical.Action())
    monitored = advance(state, {0: politics.Intent('monitor', target=0)}, actions)
    actual = monitored.physical.ledger.agents[1].harvested
    assert actual == 1.
    receipts = [item for item in monitored.state.evidence if item.subject == 1]
    assert receipts and all(item.harvested == actual for item in receipts)
    assert monitored.ledger.political_cost == pytest.approx(state.config.monitoring_cost)
    assert bond(monitored.state, identity, 1).amount == 1.
    assert_conserved(monitored)


def test_monitored_violation_can_only_seize_voluntarily_committed_collateral():
    state, identity = found(charter=politics.Charter(quota=1., bond=.25, fine=4.))
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    detected = advance(state, {0: politics.Intent('monitor', target=0)}, actions)
    evidence = next(item for item in detected.state.evidence if item.subject == 1)
    private_before = detected.state.world.agents[1].inventory
    applied = advance(detected.state, {0: politics.Intent('sanction', target=evidence.id)})
    assert applied.state.world.agents[1].inventory == private_before
    assert bond(applied.state, identity, 1).amount == 0.
    assert institution(applied.state, identity).treasury == 0.
    assert applied.ledger.forfeited == .25
    assert all(item.used for item in applied.state.evidence if item.id == evidence.id)
    repeated = advance(applied.state, {0: politics.Intent('sanction', target=evidence.id)})
    assert institution(repeated.state, identity).treasury == 0.
    assert repeated.ledger.forfeited == 0.
    assert_conserved(detected)
    assert_conserved(applied)
    assert_conserved(repeated)


def test_same_tick_exit_does_not_erase_an_existing_witnessed_liability():
    state, identity = found(charter=politics.Charter(quota=1., bond=1., fine=.5))
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    detected = advance(state, {0: politics.Intent('monitor', target=0)}, actions)
    evidence = next(item for item in detected.state.evidence if item.subject == 1)
    settled = advance(detected.state, {0: politics.Intent('sanction', target=evidence.id),
                                       1: politics.Intent('exit', target=identity)})
    assert 1 not in institution(settled.state, identity).members
    claim = bond(settled.state, identity, 1)
    assert claim.amount == .5
    assert claim.release_tick is not None
    before = settled.state.world.agents[1].inventory
    premature = advance(settled.state, {1: politics.Intent('withdraw', target=identity, amount=.5)})
    assert premature.state.world.agents[1].inventory == before
    mature = advance(premature.state, {1: politics.Intent('withdraw', target=identity, amount=.5)})
    assert mature.state.world.agents[1].inventory == pytest.approx(before + .5)
    assert_conserved(settled)
    assert_conserved(premature)
    assert_conserved(mature)


def test_outsiders_remain_unbound_even_when_their_extraction_is_observed():
    state, identity = found(world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.))),
                            politics.Charter(quota=1., fine=4.))
    actions = list(idle(state))
    actions[2] = physical.Action(harvest=3.)
    detected = advance(state, {0: politics.Intent('monitor', target=0)}, actions)
    receipts = [item for item in detected.state.evidence if item.subject == 2]
    assert receipts, 'Local paid monitoring should identify the observed outsider extraction.'
    assert all(item.institution is None for item in receipts)
    before = detected.state.world.agents[2].inventory
    attempted = advance(detected.state, {0: politics.Intent('sanction', target=receipts[0].id)})
    assert attempted.state.world.agents[2].inventory == before
    assert 2 not in institution(attempted.state, identity).members
    assert attempted.ledger.forfeited == 0.
    assert_conserved(attempted)


def test_monitor_cannot_buy_remote_evidence_or_combine_it_with_movement():
    state, identity = found()
    moved = list(idle(state))
    moved[0] = physical.Action(move=(1, 0))
    moved[1] = physical.Action(harvest=3.)
    attempted = advance(state, {0: politics.Intent('monitor', target=0)}, moved)
    assert not attempted.state.evidence
    assert attempted.ledger.political_cost == 0.
    remote = advance(attempted.state, {0: politics.Intent('monitor', target=0)})
    assert not remote.state.evidence
    assert remote.ledger.political_cost == 0.
    assert bond(remote.state, identity, 1).amount == politics.Charter().bond
    assert_conserved(attempted)
    assert_conserved(remote)


def test_new_dues_cannot_finance_a_simultaneous_treasury_monitoring_action():
    state, identity = found()
    attempted = advance(state, {0: politics.Intent('monitor', target=0, funding='treasury'),
                                1: politics.Intent('pay', target=identity, amount=.5)})
    assert not attempted.state.evidence
    assert attempted.ledger.political_cost == 0.
    assert institution(attempted.state, identity).treasury == .5
    funded = advance(attempted.state, {0: politics.Intent('monitor', target=0, funding='treasury')})
    assert institution(funded.state, identity).treasury == pytest.approx(.5 - state.config.monitoring_cost)
    assert funded.ledger.political_cost == state.config.monitoring_cost
    assert_conserved(attempted)
    assert_conserved(funded)


def test_unaffordable_settlement_leaves_bond_intact():
    state, identity = found(charter=politics.Charter(quota=1., bond=1., fine=.5))
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    detected = advance(state, {0: politics.Intent('monitor', target=0)}, actions)
    receipt = next(item for item in detected.state.evidence if item.subject == 1)
    unfunded_world = replace(detected.state.world,
        agents=(replace(detected.state.world.agents[0], inventory=0.),
                *detected.state.world.agents[1:]))
    unfunded = replace(detected.state, world=unfunded_world)
    attempted = advance(unfunded, {0: politics.Intent('sanction', target=receipt.id)})
    assert bond(attempted.state, identity, 1).amount == 1.
    assert attempted.ledger.forfeited == 0.
    assert attempted.ledger.political_cost == 0.
    assert_conserved(attempted)


def test_exit_is_possible_remotely_but_withdrawal_requires_local_custody_access():
    state, identity = found()
    actions = list(idle(state))
    actions[1] = physical.Action(move=(0, 1))
    left = advance(state, {1: politics.Intent('exit', target=identity)}, actions)
    assert 1 not in institution(left.state, identity).members
    ready = advance(advance(left.state).state).state
    before = ready.world.agents[1].inventory
    remote = advance(ready, {1: politics.Intent('withdraw', target=identity, amount=1.)})
    assert remote.state.world.agents[1].inventory == before
    assert bond(remote.state, identity, 1).amount == 1.
    return_actions = list(idle(remote.state))
    return_actions[1] = physical.Action(move=(0, -1))
    returned = advance(remote.state, actions=return_actions)
    withdrawn = advance(returned.state, {1: politics.Intent('withdraw', target=identity, amount=1.)})
    assert withdrawn.state.world.agents[1].inventory == pytest.approx(before + 1.)
    assert_conserved(left)
    assert_conserved(remote)
    assert_conserved(withdrawn)


def test_amendment_requires_current_members_consent_then_replacement_and_dissolution_work():
    state, identity = found()
    revised = replace(institution(state, identity).charter, quota=.75)
    proposal = advance(state, {0: politics.Intent('amend', target=identity, charter=revised)})
    proposal_id = proposal.state.proposals[-1].id
    unilateral = advance(proposal.state, {0: politics.Intent('endorse', target=proposal_id)})
    assert institution(unilateral.state, identity).charter != revised
    amended = advance(unilateral.state, {0: politics.Intent('endorse', target=proposal_id),
                                         1: politics.Intent('endorse', target=proposal_id)})
    assert institution(amended.state, identity).charter == revised
    assert institution(amended.state, identity).revision == 1
    successor_charter = replace(revised, quota=1.25)
    replacement = advance(amended.state,
        {0: politics.Intent('replace', target=identity, charter=successor_charter)})
    replacement_id = replacement.state.proposals[-1].id
    replaced = advance(replacement.state,
        {0: politics.Intent('endorse', target=replacement_id),
         1: politics.Intent('endorse', target=replacement_id)})
    old = institution(replaced.state, identity)
    assert not old.active
    assert old.successor is not None and old.successor != identity
    successor = institution(replaced.state, old.successor)
    assert successor.active and successor.members == (0, 1)
    assert successor.charter == successor_charter
    proposed_end = advance(replaced.state,
        {0: politics.Intent('dissolve', target=successor.id)})
    end_id = proposed_end.state.proposals[-1].id
    dissolved = advance(proposed_end.state,
        {0: politics.Intent('endorse', target=end_id),
         1: politics.Intent('endorse', target=end_id)})
    assert not any(item.active for item in dissolved.state.institutions)
    assert dissolved.ledger.custody_after == dissolved.ledger.custody_before
    for result in (proposal, unilateral, amended, replacement, replaced, proposed_end, dissolved):
        assert_conserved(result)


def test_pending_proposal_and_evidence_survive_checkpoint_continuation_exactly():
    state, identity = found(charter=politics.Charter(quota=1., bond=1., fine=.5))
    proposed_charter = replace(institution(state, identity).charter, quota=2.)
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    pending = advance(state, {0: politics.Intent('monitor', target=0),
                              1: politics.Intent('amend', target=identity, charter=proposed_charter)}, actions)
    assert pending.state.proposals
    assert pending.state.evidence
    saved = politics.snapshot(pending.state)
    restored = politics.restore(saved)
    assert restored == pending.state
    receipt = next(item for item in pending.state.evidence if item.subject == 1)
    intents = {0: politics.Intent('sanction', target=receipt.id),
               1: politics.Intent('exit', target=identity)}
    assert advance(restored, intents) == advance(pending.state, intents)
    assert politics.snapshot(restored) == saved


def test_generic_local_custody_is_available_without_any_institution():
    state = world()
    deposited = advance(state, {0: politics.Intent('cache', target=0, amount=2.)})
    assert not deposited.state.institutions
    assert deposited.state.world.agents[0].inventory == 4.
    assert deposited.ledger.custody_after == 2.
    attempted_theft = advance(deposited.state, {1: politics.Intent('retrieve', target=0, amount=2.)})
    assert attempted_theft.state.world.agents[1].inventory == 6.
    assert attempted_theft.ledger.custody_after == 2.
    reclaimed = advance(attempted_theft.state, {0: politics.Intent('retrieve', target=0, amount=2.)})
    assert reclaimed.state.world.agents[0].inventory == 6.
    assert reclaimed.ledger.custody_after == 0.
    for result in (deposited, attempted_theft, reclaimed):
        assert_conserved(result)


def test_charter_change_cannot_rewrite_previously_observed_obligations():
    state, identity = found(world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.))),
                            politics.Charter(quota=1., bond=1., fine=.5))
    replacement = replace(institution(state, identity).charter, quota=10., fine=0.)
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    prepared = advance(state,
        {0: politics.Intent('amend', target=identity, charter=replacement),
         2: politics.Intent('monitor', target=0)}, actions)
    receipt = next(item for item in prepared.state.evidence if item.subject == 1)
    proposal_id = prepared.state.proposals[-1].id
    changed = advance(prepared.state,
        {0: politics.Intent('endorse', target=proposal_id),
         1: politics.Intent('endorse', target=proposal_id),
         2: politics.Intent('sanction', target=receipt.id)})
    assert institution(changed.state, identity).charter == replacement
    assert bond(changed.state, identity, 1).amount == .5
    assert changed.ledger.forfeited == .5
    assert_conserved(changed)


def test_multiple_paid_observers_do_not_multiply_one_violation_fine():
    state, identity = found(world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.))),
                            politics.Charter(quota=1., bond=2., fine=.5))
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    detected = advance(state, {0: politics.Intent('monitor', target=0),
                              2: politics.Intent('monitor', target=0)}, actions)
    receipts = {e.observer: e for e in detected.state.evidence if e.subject == 1}
    settled = advance(detected.state,
        {0: politics.Intent('sanction', target=receipts[0].id),
         2: politics.Intent('sanction', target=receipts[2].id)})
    assert bond(settled.state, identity, 1).amount == 1.5
    assert settled.ledger.forfeited == .5
    assert settled.ledger.political_cost == state.config.settlement_cost
    assert_conserved(settled)


def test_replacement_cannot_make_a_simultaneously_observed_violation_unsettleable():
    state, identity = found(world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.))),
                            politics.Charter(quota=1., bond=1., fine=.5))
    revised = replace(institution(state, identity).charter, quota=2.)
    proposed = advance(state, {0: politics.Intent('replace', target=identity, charter=revised)})
    proposal_id = proposed.state.proposals[-1].id
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    observed = advance(proposed.state,
        {0: politics.Intent('endorse', target=proposal_id),
         1: politics.Intent('endorse', target=proposal_id),
         2: politics.Intent('monitor', target=0)}, actions)
    receipt = next(item for item in observed.state.evidence if item.subject == 1)
    settled = advance(observed.state, {2: politics.Intent('sanction', target=receipt.id)})
    # Replacement may be deferred, or custody may preserve the old claim;
    # neither procedure may erase an already paid observation's obligation.
    assert settled.ledger.forfeited == .5
    assert sum(b.amount for i in settled.state.institutions for b in i.bonds if b.owner == 1) == .5
    assert_conserved(observed)
    assert_conserved(settled)


def test_remote_observations_hide_vault_balances_and_other_observers_evidence():
    state, identity = found(world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.))))
    paid = advance(state, {0: politics.Intent('pay', target=identity, amount=.25)})
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    actions[2] = physical.Action(move=(0, 1))
    observed = advance(paid.state, {0: politics.Intent('monitor', target=0)}, actions)
    packets = politics.observations(observed.state)
    assert packets[0]['politics']['evidence']
    assert packets[1]['politics']['evidence'] == []
    assert packets[2]['politics']['evidence'] == []
    assert packets[2]['politics']['institutions'] == []
    saved = politics.snapshot(observed.state)
    packets[0]['politics']['institutions'][0]['treasury'] = 999999.
    packets[0]['politics']['evidence'][0]['harvested'] = 999999.
    assert politics.snapshot(observed.state) == saved


def test_dissolution_does_not_pledge_a_members_new_treasury_share_as_collateral():
    state, identity = found(world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.))),
                            politics.Charter(quota=1., bond=.25, fine=4.))
    funded = advance(state, {0: politics.Intent('pay', target=identity, amount=2.)})
    proposal = advance(funded.state, {0: politics.Intent('dissolve', target=identity)})
    proposal_id = proposal.state.proposals[-1].id
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    dissolved = advance(proposal.state,
        {0: politics.Intent('endorse', target=proposal_id),
         1: politics.Intent('endorse', target=proposal_id),
         2: politics.Intent('monitor', target=0)}, actions)
    assert not institution(dissolved.state, identity).active
    assert bond(dissolved.state, identity, 1).amount == 1.25
    receipt = next(item for item in dissolved.state.evidence if item.subject == 1)
    settled = advance(dissolved.state, {2: politics.Intent('sanction', target=receipt.id)})
    assert settled.ledger.forfeited == .25
    assert bond(settled.state, identity, 1).amount == 1.
    assert bond(settled.state, identity, 0).amount == 1.25
    assert_conserved(dissolved)
    assert_conserved(settled)


def test_all_local_organizations_and_personal_caches_share_finite_site_capacity():
    initial = world(agent_rows=((0, 0, 6.), (0, 0, 6.), (0, 0, 6.)))
    initial = replace(initial, config=replace(initial.config, treasury_capacity=2.5))
    state, identity = found(initial)
    filled = advance(state, {0: politics.Intent('pay', target=identity, amount=.5),
                             2: politics.Intent('cache', target=0, amount=.1)})
    assert filled.ledger.custody_after == 2.5
    assert filled.state.world.agents[2].inventory == 6.
    assert not filled.state.caches
    assert_conserved(filled)


def test_refunds_wait_in_custody_when_private_inventory_is_full():
    state = world(agent_rows=((0, 0, 20.), (0, 0, 6.), (1, 0, 6.)))
    actions = list(idle(state))
    actions[0] = physical.Action(harvest=2.)
    deposited = advance(state, {0: politics.Intent('cache', target=0, amount=2.)}, actions)
    assert deposited.state.world.agents[0].inventory == 20.
    full = advance(deposited.state, {0: politics.Intent('retrieve', target=0, amount=2.)})
    assert full.state.world.agents[0].inventory == 20.
    assert full.ledger.custody_after == 2.
    assert full.physical.ledger.waste == 0.
    actions = list(idle(full.state))
    actions[0] = physical.Action(transfers=((1, 2.),))
    room_created = advance(full.state, {0: politics.Intent('retrieve', target=0, amount=2.)}, actions)
    assert room_created.state.world.agents[0].inventory == 20.
    assert room_created.state.world.agents[1].inventory == 8.
    assert room_created.ledger.custody_after == 0.
    for result in (deposited, full, room_created):
        assert_conserved(result)


def checkpoint_with_live_proposal_and_receipt():
    state, identity = found()
    charter = replace(institution(state, identity).charter, quota=1.)
    actions = list(idle(state))
    actions[1] = physical.Action(harvest=3.)
    state = advance(state,
        {0: politics.Intent('monitor', target=0),
         1: politics.Intent('amend', target=identity, charter=charter)}, actions).state
    return politics.snapshot(state)


def resign(checkpoint):
    """A recomputed public digest cannot make a malformed state admissible."""
    content = {key: checkpoint[key] for key in ('version', 'state')}
    checkpoint['sha256'] = hashlib.sha256(json.dumps(
        content, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return checkpoint


def test_actual_json_round_trip_preserves_pending_political_state():
    saved = checkpoint_with_live_proposal_and_receipt()
    serialized = json.dumps(saved, allow_nan=False)
    restored = politics.restore(json.loads(serialized))
    assert politics.snapshot(restored) == saved
    assert restored.proposals and restored.evidence


@pytest.mark.parametrize('mutation', [
    'boolean_member', 'boolean_bond_owner', 'boolean_proposal_link',
    'boolean_evidence_link', 'duplicate_institution', 'cross_collection_id',
    'multiple_memberships', 'excess_active_pledge', 'missing_member_bond',
    'active_bond_marked_released', 'nonmember_fine', 'custody_over_capacity',
    'duplicate_cache',
])
def test_recomputed_digest_does_not_admit_malformed_political_state(mutation):
    changed = checkpoint_with_live_proposal_and_receipt()
    data = changed['state']
    charter = data['institutions'][0]
    if mutation == 'boolean_member':
        charter['members'][0] = False
    elif mutation == 'boolean_bond_owner':
        charter['bonds'][0]['owner'] = False
    elif mutation == 'boolean_proposal_link':
        data['proposals'][0]['institution'] = False
    elif mutation == 'boolean_evidence_link':
        data['evidence'][0]['institution'] = False
    elif mutation == 'duplicate_institution':
        data['institutions'].append(deepcopy(charter))
    elif mutation == 'cross_collection_id':
        data['proposals'][0]['id'] = charter['id']
    elif mutation == 'multiple_memberships':
        duplicate = deepcopy(charter)
        duplicate['id'] = data['next_id']
        data['next_id'] += 1
        data['institutions'].append(duplicate)
    elif mutation == 'excess_active_pledge':
        charter['bonds'][0]['amount'] = charter['charter']['bond'] + .5
    elif mutation == 'missing_member_bond':
        charter['bonds'].pop(0)
    elif mutation == 'active_bond_marked_released':
        charter['bonds'][0]['release_tick'] = 0
    elif mutation == 'nonmember_fine':
        data['evidence'][0]['institution'] = None
        data['evidence'][0]['fine'] = 1.
    elif mutation == 'custody_over_capacity':
        charter['treasury'] = data['config']['treasury_capacity'] + 1.
    elif mutation == 'duplicate_cache':
        row = {'owner': 2, 'site_id': 0, 'amount': .25}
        data['caches'] = [row, deepcopy(row)]
    with pytest.raises(ValueError):
        politics.restore(resign(changed))


def test_successful_foundation_endorsements_cannot_be_replayed_as_a_new_organization():
    state = world()
    proposal = advance(state, {0: politics.Intent('propose', target=0, charter=politics.Charter())})
    identity = proposal.state.proposals[0].id
    votes = {0: politics.Intent('endorse', target=identity),
             1: politics.Intent('endorse', target=identity)}
    established = advance(proposal.state, votes)
    before = politics.snapshot(established.state)
    replayed = advance(established.state, votes)
    assert len(replayed.state.institutions) == 1
    assert replayed.ledger.custody_before == replayed.ledger.custody_after
    assert replayed.ledger.political_cost == 0.
    assert all(not event['ok'] for event in replayed.events)
    assert politics.snapshot(established.state) == before


def test_expired_foundation_proposal_cannot_reuse_stale_consent():
    state = world()
    state = replace(state, config=replace(state.config, proposal_lifetime=1))
    proposed = advance(state, {0: politics.Intent('propose', target=0, charter=politics.Charter())})
    identity = proposed.state.proposals[0].id
    expired = advance(proposed.state,
        {0: politics.Intent('endorse', target=identity),
         1: politics.Intent('endorse', target=identity)})
    assert expired.state.institutions == ()
    assert expired.ledger.custody_after == 0.
    assert all(not event['ok'] for event in expired.events)
