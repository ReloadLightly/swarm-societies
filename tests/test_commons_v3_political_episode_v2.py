"""Regenerate decisions from complete private feedback and political state."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from swarm_societies.commons_v3.engine import Action, Config
from swarm_societies.commons_v3 import politics_v1 as politics
from swarm_societies.commons_v3.own_feedback_v2 import FIELDS, feedback_from_result
from swarm_societies.commons_v3.policies_coordination_v2 import CoordinationPolicy
from swarm_societies.commons_v3.policies_membership_v2 import MembershipPolicy
from swarm_societies.commons_v3.policies_institutions_v1 import CoordinatingForager
from swarm_societies.commons_v3.political_episode_v1 import ScriptedPolicy
from swarm_societies.commons_v3 import political_episode_v2 as runtime


def local_world(n_agents=3, need=0.):
    cfg = Config(width=3, height=1, n_agents=n_agents, n_patches=1, need=need,
                 initial_inventory=10., inventory_capacity=20.,
                 initial_patch_stock=40., weather_amplitude=0.,
                 renewal_rate=0., recovery=0.)
    state = politics.initialize(cfg, 18262)
    physical = replace(state.world, agents=tuple(replace(a, x=0, y=0) for a in state.world.agents),
                       patches=(replace(state.world.patches[0], x=0, y=0),))
    return replace(state, world=physical)


def scripted_episode():
    schedules = [{tick: (Action(), politics.Intent()) for tick in range(12)} for _ in range(3)]
    schedules[0][0] = (Action(messages=((2, "private receipt integration"),)),
                       politics.Intent("propose", 0, politics.Charter()))
    schedules[0][1] = (Action(), politics.Intent("endorse", 0))
    schedules[1][1] = (Action(), politics.Intent("endorse", 0))
    schedules[2][1] = (Action(), politics.Intent("refuse", 0))
    schedules[0][2] = (Action(), politics.Intent("pay", 0, amount=1.))
    schedules[0][3] = (Action(), politics.Intent("monitor", 0, funding="treasury"))
    schedules[1][3] = (Action(harvest=3.), politics.Intent())
    schedules[0][4] = (Action(), politics.Intent("sanction", 2, funding="treasury"))
    schedules[1][4] = (Action(), politics.Intent("exit", 0))
    schedules[0][5] = (Action(), politics.Intent("dissolve", 0))
    schedules[0][6] = (Action(), politics.Intent("endorse", 4))
    schedules[1][6] = (Action(), politics.Intent("withdraw", 0, amount=1.))
    schedules[0][8] = (Action(), politics.Intent("withdraw", 0, amount=2.))
    return runtime.Episode(local_world(), [ScriptedPolicy(schedule) for schedule in schedules])


def rehash(checkpoint):
    checkpoint["sha256"] = hashlib.sha256(json.dumps(checkpoint["payload"], sort_keys=True,
                                                       separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return checkpoint


@pytest.mark.parametrize("checkpoint_tick", [1, 4, 5, 6])
def test_full_political_and_feedback_continuation_regenerates_every_decision(checkpoint_tick):
    original = scripted_episode()
    for _ in range(checkpoint_tick):
        original.advance()
    if checkpoint_tick == 5:
        assert any(bond.owner == 1 and bond.release_tick is not None and bond.amount > 0.
                   for institution in original.state.institutions for bond in institution.bonds)
    resumed = runtime.restore_checkpoint(json.loads(json.dumps(original.checkpoint())))
    assert resumed.checkpoint() == original.checkpoint()
    for _ in range(12 - checkpoint_tick):
        assert original.advance() == resumed.advance()
        assert original.last_actions == resumed.last_actions
        assert original.last_intents == resumed.last_intents
        assert original.private_feedback == resumed.private_feedback
        assert original.checkpoint() == resumed.checkpoint()
    assert all(not institution.active for institution in original.state.institutions)
    assert politics.custody(original.state) == 0.


def test_mixed_registry_continuation_recomputes_live_coordination_and_membership():
    original = runtime.Episode(local_world(4, need=1.2),
        [CoordinationPolicy(), MembershipPolicy(), CoordinatingForager(),
         ScriptedPolicy({0: (Action(messages=((0, "pending at checkpoint"),)), politics.Intent())})])
    original.advance()
    assert original.state.world.messages
    resumed = runtime.restore_checkpoint(json.loads(json.dumps(original.checkpoint())))
    for _ in range(20):
        assert resumed.advance() == original.advance()
        assert resumed.last_actions == original.last_actions
        assert resumed.last_intents == original.last_intents
        assert resumed.checkpoint() == original.checkpoint()


def test_private_receipts_assign_own_costs_and_forfeitures_to_the_correct_individual():
    episode = scripted_episode()
    first = episode.advance()
    assert episode.private_feedback[0]["political_fee_private"] == .1
    assert episode.private_feedback[0]["message_cost"] > 0.
    assert episode.private_feedback[1]["political_fee_private"] == 0.
    for row, physical in zip(episode.private_feedback, first.physical.ledger.agents):
        assert set(row) == FIELDS
        assert row["agent"] == physical.id
        assert row["consumption"] == physical.consumption
        assert row["shortfall"] == physical.shortfall
    episode.advance()
    episode.advance()
    assert episode.private_feedback[0]["dues_contribution"] == 1.
    episode.advance()
    assert episode.private_feedback[0]["political_fee_private"] == 0., "treasury spending is not private spending"
    result = episode.advance()
    assert episode.private_feedback == feedback_from_result(result)
    assert episode.private_feedback[0]["collateral_forfeited"] == 0.
    assert episode.private_feedback[1]["collateral_forfeited"] == .5
    assert episode.private_feedback[0]["political_fee_private"] == 0.


def test_all_registry_types_receive_the_same_private_receipt_affordance(monkeypatch):
    observed = []
    for policy_type in (CoordinationPolicy, MembershipPolicy, CoordinatingForager, ScriptedPolicy):
        original = policy_type.__call__

        def capture(self, observation, call=original):
            observed.append((type(self), observation["self"]["id"], deepcopy(observation["private_feedback"])))
            return call(self, observation)

        monkeypatch.setattr(policy_type, "__call__", capture)
    episode = runtime.Episode(local_world(4, need=1.2),
                              [CoordinationPolicy(), MembershipPolicy(), CoordinatingForager(), ScriptedPolicy()])
    episode.advance()
    assert all(receipt is None for _, _, receipt in observed)
    observed.clear()
    previous = deepcopy(episode.private_feedback)
    episode.advance()
    assert {kind for kind, _, _ in observed} == {CoordinationPolicy, MembershipPolicy, CoordinatingForager, ScriptedPolicy}
    assert all(receipt == previous[identity] for _, identity, receipt in observed)


@pytest.mark.parametrize("field,value", [("agent", 1), ("tick", 99), ("consumption", -1.),
                                         ("shortfall", 10.), ("harvested", 100.),
                                         ("message_cost", 100.), ("harvest_cost", .123),
                                         ("political_fee_private", 100.), ("version", "other")])
def test_feedback_schema_and_physical_context_reject_rehashed_tampering(field, value):
    episode = scripted_episode()
    episode.advance()
    checkpoint = episode.checkpoint()
    checkpoint["payload"]["private_feedback"][0][field] = value
    with pytest.raises(ValueError, match="private feedback"):
        runtime.restore_checkpoint(rehash(checkpoint))


def test_a_continuation_cannot_silently_discard_private_feedback():
    episode = scripted_episode()
    episode.advance()
    checkpoint = episode.checkpoint()
    checkpoint["payload"]["private_feedback"] = [None] * 3
    with pytest.raises(ValueError, match="require prior-step"):
        runtime.restore_checkpoint(rehash(checkpoint))


def test_explicit_fresh_start_at_later_physical_tick_preserves_absent_feedback():
    state = local_world(2, need=1.2)
    for _ in range(3):
        state = politics.step(state, (Action(), Action())).state
    episode = runtime.Episode(state, [CoordinationPolicy(), MembershipPolicy()])
    assert episode.private_feedback == (None, None)
    assert episode.feedback_origin_tick == 3
    resumed = runtime.restore_checkpoint(episode.checkpoint())
    assert episode.advance() == resumed.advance()
    assert all(row["tick"] == 3 for row in episode.private_feedback)


def test_mutating_a_receipt_changes_the_bound_checkpoint_checksum():
    episode = scripted_episode()
    episode.advance()
    checkpoint = episode.checkpoint()
    checkpoint["payload"]["private_feedback"][0]["message_cost"] = 0.
    with pytest.raises(ValueError, match="checksum"):
        runtime.restore_checkpoint(checkpoint)


@pytest.mark.parametrize("source", ["engine.py", "policies_coordination_v2.py", "policies_membership_v2.py",
                                    "own_feedback_v2.py", "political_episode_v2.py"])
def test_runtime_and_information_affordance_are_source_bound(source):
    checkpoint = scripted_episode().checkpoint()
    checkpoint["payload"]["sources"][source] = "0" * 64
    with pytest.raises(ValueError, match="source closure"):
        runtime.restore_checkpoint(rehash(checkpoint))


def test_unknown_code_and_subclasses_do_not_enter_the_registry():
    checkpoint = scripted_episode().checkpoint()
    checkpoint["payload"]["policies"][0] = {"version": "external", "source": "raise RuntimeError"}
    with pytest.raises(ValueError, match="audited registry"):
        runtime.restore_checkpoint(rehash(checkpoint))

    class External(CoordinationPolicy):
        pass

    with pytest.raises(ValueError, match="audited"):
        runtime.Episode(local_world(1), [External()])


def test_noncanonical_future_schedule_cannot_change_after_restoration():
    checkpoint = scripted_episode().checkpoint()
    checkpoint["payload"]["policies"][0]["schedule"].reverse()
    with pytest.raises(ValueError, match="canonical"):
        runtime.restore_checkpoint(rehash(checkpoint))


@pytest.mark.parametrize("policy_index", [0, 1])
def test_new_policy_identity_is_bound_to_its_individual_slot(policy_index):
    episode = runtime.Episode(local_world(2, need=1.2), [CoordinationPolicy(), MembershipPolicy()])
    episode.advance()
    checkpoint = episode.checkpoint()
    checkpoint["payload"]["policies"][policy_index]["owner"] = 1 - policy_index
    with pytest.raises(ValueError):
        runtime.restore_checkpoint(rehash(checkpoint))


def test_new_navigation_memory_coordinates_are_bounded_by_the_checkpoint_grid():
    episode = runtime.Episode(local_world(1), [CoordinationPolicy()])
    episode.advance()
    checkpoint = episode.checkpoint()
    checkpoint["payload"]["policies"][0]["forager"]["seen"].append([9, 0])
    with pytest.raises(ValueError, match="outside episode"):
        runtime.restore_checkpoint(rehash(checkpoint))


def test_reset_membership_history_cannot_hide_a_used_nested_controller():
    episode = runtime.Episode(local_world(1), [MembershipPolicy()])
    episode.advance()
    checkpoint = episode.checkpoint()
    old_coordinator = checkpoint["payload"]["policies"][0]["coordinator"]
    checkpoint["payload"]["policies"][0] = MembershipPolicy().memory()
    checkpoint["payload"]["policies"][0]["coordinator"] = old_coordinator
    with pytest.raises(ValueError):
        runtime.restore_checkpoint(rehash(checkpoint))


def test_failed_physical_step_rolls_back_memory_feedback_and_last_outputs():
    episode = runtime.Episode(local_world(2),
        [ScriptedPolicy({1: (Action(move=(-1, 0)), politics.Intent())}), CoordinationPolicy()])
    episode.advance()
    before, actions, intents = episode.checkpoint(), episode.last_actions, episode.last_intents
    with pytest.raises(ValueError):
        episode.advance()
    assert episode.checkpoint() == before
    assert episode.last_actions == actions
    assert episode.last_intents == intents


def test_post_step_receipt_failure_also_rolls_back_complete_boundary(monkeypatch):
    episode = runtime.Episode(local_world(2, need=1.2), [CoordinationPolicy(), MembershipPolicy()])
    episode.advance()
    before = episode.checkpoint()

    def fail(_):
        raise ValueError("receipt failure")

    monkeypatch.setattr(runtime, "feedback_from_result", fail)
    with pytest.raises(ValueError, match="receipt failure"):
        episode.advance()
    assert episode.checkpoint() == before


def test_episode_owns_detached_policy_memories_and_checkpoint_data():
    policy = CoordinationPolicy()
    episode = runtime.Episode(local_world(1), [policy])
    policy.forager.visits[(0, 0)] = 10
    assert episode.policies[0].forager.visits == {}
    checkpoint = episode.checkpoint()
    checkpoint["payload"]["policies"].clear()
    assert len(episode.checkpoint()["payload"]["policies"]) == 1


def test_engineering_demo_links_paid_information_to_route_flows_and_private_feedback_to_exit():
    from scripts.demo_commons_v3_coordination_v2 import run_demo
    report = run_demo(full_trace=True)
    assert report["model_calls"] == report["evolutionary_runs"] == 0
    assert report["replayed_continuation_ticks"] == 18
    assert report["max_accounting_residual"] < 1e-12
    coordination = report["fixtures"]["paid_coordination"]
    assert coordination["paid_message_cost"] == .021
    assert coordination["receiver_moves_at_tick_1"] == {"delivered": [1, 0], "information_removed": [-1, 0]}
    assert coordination["receiver_harvest_at_tick_2"] == {"delivered": 2., "information_removed": 0.}
    exit_ = report["fixtures"]["responsive_exit"]
    assert exit_["exit_tick"] == 4 and exit_["release_tick"] == exit_["withdrawal_tick"] == 6
    assert exit_["withdrawal_amount"] == 1. and exit_["charter_unchanged"]
    assert not exit_["exit_is_immediate_refund"]
    assert exit_["withdrawal_tick_consumption"] == 0.
    assert report["fixtures"]["optional_formation"]["members"] == [0, 1, 2]
    assert report["fixtures"]["liquidity_refusal"]["reason"] == "outside_or_liquidity_preferred"
    assert "scripts/demo_commons_v3_coordination_v2.py" in report["sources"]


def test_engineering_demo_refuses_to_overwrite_an_existing_output(tmp_path, monkeypatch):
    from scripts.demo_commons_v3_coordination_v2 import main
    target = tmp_path / "existing.json"
    target.write_text("preserve this evidence\n")
    monkeypatch.setattr("sys.argv", ["demo", "--output", str(target)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert target.read_text() == "preserve this evidence\n"
