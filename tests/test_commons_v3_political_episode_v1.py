"""Full decisions regenerate after restoring state, policy memory, and plans."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from swarm_societies.commons_v3.engine import Action, Config
from swarm_societies.commons_v3 import politics_v1 as politics
from swarm_societies.commons_v3.policies_institutions_v1 import (
    CoordinatingForager, VoluntaryCharterPolicy,
)
from swarm_societies.commons_v3.political_episode_v1 import (
    Episode, ScriptedPolicy, restore_checkpoint,
)


def local_world():
    cfg = Config(width=3, height=1, n_agents=3, n_patches=1, need=0.,
                 initial_inventory=10., inventory_capacity=20.,
                 initial_patch_stock=40., weather_amplitude=0.,
                 renewal_rate=0., recovery=0.)
    state = politics.initialize(cfg, 18262)
    physical = replace(state.world, agents=tuple(replace(a, x=0, y=0) for a in state.world.agents),
                       patches=(replace(state.world.patches[0], x=0, y=0),))
    return replace(state, world=physical)


def scripted_episode():
    schedules = [{tick: (Action(), politics.Intent()) for tick in range(12)} for _ in range(3)]
    schedules[0][0] = (Action(), politics.Intent("propose", 0, politics.Charter()))
    schedules[0][1] = (Action(), politics.Intent("endorse", 0))
    schedules[1][1] = (Action(), politics.Intent("endorse", 0))
    schedules[2][1] = (Action(), politics.Intent("refuse", 0))
    schedules[0][2] = (Action(), politics.Intent("pay", 0, amount=1.))
    schedules[0][3] = (Action(), politics.Intent("monitor", 0, funding="treasury"))
    schedules[1][3] = (Action(harvest=3.), politics.Intent())
    schedules[0][4] = (Action(), politics.Intent("sanction", 2, funding="treasury"))
    schedules[1][4] = (Action(), politics.Intent("exit", 0))
    schedules[0][5] = (Action(), politics.Intent("amend", 0, politics.Charter(quota=1.5)))
    schedules[0][6] = (Action(), politics.Intent("endorse", 4))
    schedules[1][6] = (Action(), politics.Intent("withdraw", 0, amount=1.))
    schedules[0][7] = (Action(), politics.Intent("dissolve", 0))
    schedules[0][8] = (Action(), politics.Intent("endorse", 5))
    return Episode(local_world(), [ScriptedPolicy(schedule) for schedule in schedules])


@pytest.mark.parametrize("checkpoint_tick", [1, 4, 5, 6])
def test_scripted_full_checkpoint_regenerates_pending_political_and_physical_decisions(checkpoint_tick):
    original = scripted_episode()
    for _ in range(checkpoint_tick):
        original.advance()
    checkpoint = json.loads(json.dumps(original.checkpoint()))
    resumed = restore_checkpoint(checkpoint)
    assert resumed.checkpoint() == original.checkpoint()
    for _ in range(12 - checkpoint_tick):
        expected, actual = original.advance(), resumed.advance()
        assert actual == expected
        assert original.last_actions == resumed.last_actions
        assert original.last_intents == resumed.last_intents
        assert [p.memory() for p in original.policies] == [p.memory() for p in resumed.policies]
        assert resumed.checkpoint() == original.checkpoint()


def test_live_coordinator_checkpoint_recomputes_future_policy_decisions():
    cfg = Config(n_agents=4, n_patches=4, width=6, height=6, need=1.2)
    original = Episode(politics.initialize(cfg, 8316), [CoordinatingForager() for _ in range(4)])
    for _ in range(13):
        original.advance()
    resumed = restore_checkpoint(json.loads(json.dumps(original.checkpoint())))
    for _ in range(17):
        assert original.advance() == resumed.advance()
        assert original.last_actions == resumed.last_actions
        assert original.checkpoint() == resumed.checkpoint()


def test_every_future_script_action_is_bound_and_tamper_is_detected():
    episode = scripted_episode()
    checkpoint = episode.checkpoint()
    changed = deepcopy(checkpoint)
    changed["payload"]["policies"][0]["schedule"][-1]["physical"]["harvest"] = 3.
    with pytest.raises(ValueError, match="checksum"):
        restore_checkpoint(changed)


def rehash(checkpoint):
    checkpoint["sha256"] = hashlib.sha256(json.dumps(checkpoint["payload"], sort_keys=True,
                                                       separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return checkpoint


def test_registry_rejects_unknown_code_even_with_recomputed_checksum():
    checkpoint = scripted_episode().checkpoint()
    checkpoint["payload"]["policies"][0] = {"version": "custom", "source": "print('untrusted')"}
    with pytest.raises(ValueError, match="audited registry"):
        restore_checkpoint(rehash(checkpoint))


def test_source_closure_mismatch_refuses_to_silently_resume_different_rules():
    checkpoint = scripted_episode().checkpoint()
    checkpoint["payload"]["sources"]["politics_v1.py"] = "0" * 64
    with pytest.raises(ValueError, match="source closure"):
        restore_checkpoint(rehash(checkpoint))


def test_invalid_action_rolls_back_controller_memories_as_well_as_world():
    episode = Episode(local_world(), [ScriptedPolicy({0: (Action(move=(-1, 0)), politics.Intent())}),
                                     CoordinatingForager(), CoordinatingForager()])
    checkpoint = episode.checkpoint()
    with pytest.raises(ValueError):
        episode.advance()
    assert episode.checkpoint() == checkpoint


def test_runner_refuses_external_policy_objects_and_subclasses():
    class External(CoordinatingForager):
        pass
    with pytest.raises(ValueError, match="audited"):
        Episode(local_world(), [External(), CoordinatingForager(), CoordinatingForager()])


def test_supplied_voluntary_heuristic_is_restorable_and_preserves_zero_institution_world():
    # With no colocated peer it can forage but cannot silently create a polity.
    cfg = Config(n_agents=1, n_patches=1, width=3, height=1, need=1.2)
    original = Episode(politics.initialize(cfg, 9202), [VoluntaryCharterPolicy()])
    for _ in range(3):
        original.advance()
    resumed = restore_checkpoint(original.checkpoint())
    for _ in range(5):
        assert original.advance() == resumed.advance()
        assert original.last_intents[0].kind == "none"


def test_nonscripted_local_formation_with_need_and_midmembership_checkpoint():
    # A supplied local-rule integration fixture. These colocated individuals
    # are deliberately not a sampled population or a governance-benefit test.
    state = local_world()
    state = replace(state, world=replace(state.world, config=replace(state.world.config, need=1.2)))
    original = Episode(state, [VoluntaryCharterPolicy() for _ in state.world.agents])
    assert not original.state.institutions
    original.advance()
    assert [intent.kind for intent in original.last_intents] == ["propose", "none", "none"]
    original.advance()
    assert [intent.kind for intent in original.last_intents] == ["endorse"] * 3
    assert original.state.institutions[0].members == (0, 1, 2)
    assert all(agent.consumption > 0. for agent in original.state.world.agents)
    for _ in range(2):
        original.advance()
    assert original.state.institutions[0].treasury > 0.
    assert original.state.evidence, "paid monitoring must leave evidence in this checkpoint"
    resumed = restore_checkpoint(json.loads(json.dumps(original.checkpoint())))
    for _ in range(8):
        assert resumed.advance() == original.advance()
        assert resumed.last_actions == original.last_actions
        assert resumed.last_intents == original.last_intents
        assert resumed.checkpoint() == original.checkpoint()


def test_executable_demo_covers_settlement_and_replacement_through_full_continuation():
    from scripts.demo_commons_v3_institutions_v1 import run_demo
    summary = run_demo(full_trace=True)
    assert summary["replayed_continuation_ticks"] == 61
    assert summary["final_active_institutions"] == 0
    assert summary["final_custody"] == 0.
    assert summary["forfeited_collateral"] == .5
    assert summary["political_operating_cost"] == pytest.approx(.52)
    assert summary["max_accounting_residual"] < 1e-12
    assert {event["kind"] for event in summary["failed_events"]} == {"pay", "sanction", "withdraw"}
    # A quota violation with no paid observer remains physically possible and
    # yields no later receipt. Refusal precedes the same actor's voluntary join.
    assert summary["trace"][4]["actions"][1]["harvest"] == 3.
    assert all(event["kind"] != "monitor" for event in summary["trace"][4]["events"])
    assert summary["trace"][1]["intents"][2]["kind"] == "refuse"
    assert summary["trace"][2]["intents"][2]["kind"] == "join"
