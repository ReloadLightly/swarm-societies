"""Contract capacity totals, independent initialization, and local disclosure."""
from dataclasses import replace
import math

import pytest

from swarm_societies.commons_v3 import engine as frozen
from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3 import worlds_sites_v1 as worlds


@pytest.mark.parametrize("condition", ["moderate", "wide"])
@pytest.mark.parametrize("seed", [90001, 90002, 90003, 90004])
def test_contract_worlds_conserve_total_capacity_and_declared_multisets(condition, seed):
    capacities = worlds.capacity_world(condition, seed)
    base = list(worlds.WORLD_LEVELS[condition]) * 3 + [40.]
    factor = 1. if condition == "moderate" else 640. / sum(base)
    assert sorted(capacities) == sorted(k * factor for k in base)
    assert math.fsum(capacities) == pytest.approx(640., abs=1e-12)
    assert math.fsum(.24 * k / 4 for k in capacities) == pytest.approx(38.4)
    assert capacities == worlds.capacity_world(condition, seed)
    for need in (1.2, 1.6):
        state = worlds.initialize(condition, need, seed)
        cfg = state.config
        assert (cfg.width, cfg.height, cfg.n_agents, cfg.n_patches) == (12, 12, 24, 16)
        assert cfg.renewal_law == "logistic"
        assert (cfg.renewal_rate, cfg.recovery, cfg.weather_amplitude) == (.24, .02, .1)
        assert cfg.site_capacities == capacities
        assert cfg.initial_site_stocks == tuple(k * u for k, u in zip(capacities, worlds.initial_fractions(seed)))
        assert all(.3 <= p.stock / k <= .9 for p, k in zip(state.patches, capacities))
        assert len(set(worlds.initial_fractions(seed))) == 16
        old = frozen.initialize(frozen.Config(need=need), seed)
        assert [(a.x, a.y) for a in state.agents] == [(a.x, a.y) for a in old.agents]
        assert [(p.x, p.y) for p in state.patches] == [(p.x, p.y) for p in old.patches]


def test_initial_fractions_are_independent_of_world_and_capacity_permutation():
    moderate = worlds.configuration("moderate", 1.2, 90001)
    wide = worlds.configuration("wide", 1.6, 90001)
    assert [s / k for s, k in zip(moderate.initial_site_stocks, moderate.site_capacities)] == pytest.approx(
        [s / k for s, k in zip(wide.initial_site_stocks, wide.site_capacities)], rel=1e-15)
    assert worlds.initial_fractions(90001) != worlds.initial_fractions(90002)
    assert worlds.capacity_world("wide", 90001) != worlds.capacity_world("wide", 90002)


def test_world_condition_is_not_disclosed_and_stock_can_exceed_legacy_scalar_capacity():
    state = worlds.initialize("wide", 1.2, 90001)
    state = replace(state, config=replace(state.config, sensing_radius=24))
    packet = engine.observe(state, 0)
    assert max(p.stock for p in state.patches) > state.config.patch_capacity
    assert len(packet["sites"]) == 16
    assert all(set(site) == {"id", "x", "y", "stock", "peer_count"} for site in packet["sites"])
    assert "condition" not in packet and "seed" not in packet
    assert packet["ecology"]["capacity_prior"] == {"distribution": "log_uniform", "low": 8., "high": 100.}
    assert all("capacity" not in record for record in packet["peers"])


@pytest.mark.parametrize("condition,need,seed", [("other", 1.2, 90001), ("wide", 1., 90001),
                                               ("moderate", 1.2, True), ("wide", 1.6, -1)])
def test_invalid_world_request_is_rejected(condition, need, seed):
    with pytest.raises(ValueError):
        worlds.configuration(condition, need, seed)
