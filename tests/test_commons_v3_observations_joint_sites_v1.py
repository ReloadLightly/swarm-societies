"""Unknown-rate observation fixtures; no declared experiment seed executes."""
from copy import deepcopy
from dataclasses import replace

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import observations_joint_sites_v1 as unknown
from swarm_societies.commons_v3 import observations_messages_sites_v1 as known


def fixture():
    config = engine.Config(width=5, height=3, n_agents=2, n_patches=2,
                           site_capacities=(20., 60.), initial_site_stocks=(12., 36.))
    return engine.initialize(config, seed=37)


def test_true_rate_is_absent_and_initial_observations_do_not_depend_on_it():
    state = fixture()
    packets = unknown.observations(state)
    for rate in (.12, .48):
        changed = replace(state, config=replace(state.config, renewal_rate=rate))
        assert unknown.observations(changed) == packets
    for packet in packets:
        assert "renewal_rate" not in packet["ecology"]
        assert packet["ecology"]["renewal_rate_prior"] == {
            "distribution": "log_uniform", "low": .12, "high": .48,
            "shared_across_sites": True,
        }
        assert all(set(site) == {"id", "x", "y", "stock", "peer_count"}
                   for site in packet["sites"])
        unknown.validate_ecology(packet)


def test_only_declared_rate_information_changes_and_packets_are_detached():
    state = fixture()
    original = known.observations(state)
    saved = deepcopy(original)
    projected = tuple(unknown.hide_rate(packet) for packet in original)
    assert original == saved
    for before, after in zip(original, projected):
        restored = deepcopy(after)
        restored.pop("unknown_rate_adapter_version")
        restored["ecology"].pop("renewal_rate_prior")
        restored["ecology"]["renewal_rate"] = state.config.renewal_rate
        assert restored == before
    projected[0]["ecology"]["renewal_rate_prior"]["low"] = .01
    projected[0]["sites"][0]["stock"] = -1.
    assert original == saved
    assert projected[1]["ecology"]["renewal_rate_prior"]["low"] == .12
    assert unknown.RATE_PRIOR["low"] == .12


def test_private_feedback_retains_exact_own_amount_and_delivery_tick():
    state = fixture()
    result = engine.step(state, [engine.Action(harvest=1.), engine.Action(harvest=2.)])
    before = known.observations(result.state, result)
    after = unknown.observations(result.state, result)
    assert [p["private_harvest"] for p in after] == [p["private_harvest"] for p in before]
    assert all(p["adapter_version"] == known.VERSION for p in after)
    assert [p["private_harvest"]["harvested"] for p in after] == [r.harvested for r in result.ledger.agents]
    assert all(p["private_harvest"]["tick"] == 0 and p["tick"] == 1 for p in after)
    receipts = known.private_harvest_receipts(result)
    assert unknown.observations(result.state, receipts) == after


@pytest.mark.parametrize("change", ["truth", "support", "independent_rates", "law", "capacity", "derived", "marker"])
def test_observation_contract_rejects_hidden_information_and_changed_assumptions(change):
    packet = deepcopy(unknown.observations(fixture())[0])
    if change == "truth":
        packet["ecology"]["renewal_rate"] = .24
    elif change == "support":
        packet["ecology"]["renewal_rate_prior"]["low"] = .06
    elif change == "independent_rates":
        packet["ecology"]["renewal_rate_prior"]["shared_across_sites"] = False
    elif change == "law":
        packet["ecology"]["renewal_law"] = "additive"
    elif change in ("capacity", "derived"):
        packet["sites"][0]["capacity" if change == "capacity" else "growth_potential"] = 40.
    else:
        packet.pop("unknown_rate_adapter_version")
    with pytest.raises(ValueError):
        unknown.validate_ecology(packet)


def test_known_rate_packets_are_not_accepted_by_unknown_rate_validation():
    with pytest.raises(ValueError, match="unknown-rate observation"):
        unknown.validate_ecology(known.observations(fixture())[0])
