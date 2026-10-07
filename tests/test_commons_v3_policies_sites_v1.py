"""Local reference-wrapper checks; no consequence-map episodes run here."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from swarm_societies.commons_v3 import engine_sites_v1 as sites
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy
from swarm_societies.commons_v3.policies_sites_v1 import ReferenceForager


CAPACITIES = (20., 60., 90.)


def packet(*, tick=0, x=1, inventory=2., capacities=CAPACITIES):
    config = sites.Config(width=7, height=3, n_agents=3, n_patches=3,
                          sensing_radius=2, need=1.2, site_capacities=capacities,
                          initial_site_stocks=(16., 40., 72.))
    state = sites.initialize(config, 17)
    state = replace(state, tick=tick,
                    agents=(replace(state.agents[0], x=x, y=1, inventory=inventory),
                            replace(state.agents[1], x=1, y=1),
                            replace(state.agents[2], x=1, y=1)),
                    patches=tuple(replace(patch, x=point, y=1)
                                  for patch, point in zip(state.patches, (1, 3, 6))))
    return sites.observe(state, 0)


def injected(observation, arm, phi, fixed_capacity=None):
    result = deepcopy(observation)
    for site in result["sites"]:
        capacity = CAPACITIES[site["id"]] if arm == "R-oracle" else fixed_capacity
        site["capacity"] = 40. if arm == "R-greedy" else (phi / .5) * capacity
    return result


@pytest.mark.parametrize("arm,fixed_capacity", [
    ("R-oracle", None), ("R-fixed", 20), ("R-fixed", 30), ("R-fixed", 40),
    ("R-greedy", None),
])
@pytest.mark.parametrize("phi", [.375, .5])
def test_reference_matches_frozen_actions_and_memory_for_injected_local_packets(arm, fixed_capacity, phi):
    reference = ReferenceForager(arm, phi=phi, fixed_capacity=fixed_capacity,
                                 true_capacities=CAPACITIES if arm == "R-oracle" else None)
    baseline = ForagerPolicy(2, 0. if arm == "R-greedy" else .5, "net_yield")
    for tick, x in enumerate((1, 3, 5)):
        legal = packet(tick=tick, x=x)
        before = deepcopy(legal)
        expected = baseline(injected(legal, arm, phi, fixed_capacity))
        assert reference(legal) == expected
        assert reference.memory() == baseline.memory()
        assert json.loads(json.dumps(reference.memory())) == reference.memory()
        assert legal == before
        assert all("capacity" not in site for site in legal["sites"])


@pytest.mark.parametrize("arm,kwargs,expected", [
    ("R-oracle", {"true_capacities": CAPACITIES}, 15.),
    ("R-fixed", {"fixed_capacity": 30.}, 22.5),
    ("R-greedy", {}, 40.),
])
def test_every_call_refreshes_capacity_of_remembered_nonvisible_sites(arm, kwargs, expected):
    reference = ReferenceForager(arm, phi=.375, **kwargs)
    reference(packet())
    old = deepcopy(reference.records[0])
    reference.records[0]["capacity"] = 999.
    later = packet(tick=1, x=5)
    assert 0 not in {site["id"] for site in later["sites"]}
    reference(later)
    assert reference.records[0] == {**old, "capacity": expected}


def test_oracle_capacity_tuple_does_not_reveal_unseen_ids_or_coordinates():
    reference = ReferenceForager("R-oracle", true_capacities=CAPACITIES)
    legal = packet()
    assert {site["id"] for site in legal["sites"]} == {0, 1}
    reference(legal)
    assert set(reference.sites) == set(reference.records) == {0, 1}
    assert 2 not in {record["id"] for record in reference.memory()["records"]}
    # Changing only an unobserved capacity cannot affect the current decision.
    alternative = ReferenceForager("R-oracle", true_capacities=(20., 60., 10.))
    control = ReferenceForager("R-oracle", true_capacities=CAPACITIES)
    assert alternative(legal) == control(legal)
    assert alternative.memory() == control.memory()


def test_fixed_reference_is_independent_of_hidden_capacity_world():
    first = packet(capacities=(20., 60., 90.))
    second = packet(capacities=(30., 50., 80.))
    assert first == second
    left = ReferenceForager("R-fixed", fixed_capacity=30.)
    right = ReferenceForager("R-fixed", fixed_capacity=30.)
    assert left(first) == right(second)
    assert left.memory() == right.memory()
    with pytest.raises(ValueError, match="cannot receive true capacities"):
        ReferenceForager("R-fixed", fixed_capacity=30., true_capacities=CAPACITIES)


def test_reference_replaces_preexisting_capacity_without_mutating_input():
    legal = packet()
    for site in legal["sites"]:
        site["capacity"] = 987.
    before = deepcopy(legal)
    reference = ReferenceForager("R-fixed", phi=.375, fixed_capacity=20.)
    reference(legal)
    assert legal == before
    assert {record["capacity"] for record in reference.records.values()} == {15.}


def test_greedy_uses_native_zero_floor_request_when_crowded():
    legal = packet(inventory=0.)
    legal["sites"] = [site for site in legal["sites"] if site["id"] == 0]
    legal["sites"][0]["stock"] = 3.
    assert legal["sites"][0]["peer_count"] == 3
    reference = ReferenceForager("R-greedy")
    native = ForagerPolicy(2, 0., "net_yield", aggressive=False)
    expected = native(injected(legal, "R-greedy", .5))
    actual = reference(legal)
    assert actual == expected
    assert reference.memory() == native.memory()
    assert actual.harvest == 3.
    assert reference.stock_floor_fraction == 0.
    assert reference.aggressive is False
    assert reference.reserve_ticks == 2
    zero_capacity = deepcopy(legal)
    zero_capacity["sites"][0]["capacity"] = 0.
    different = ForagerPolicy(2, .5, "net_yield")(zero_capacity)
    assert different.harvest == 1.
    assert actual != different


@pytest.mark.parametrize("arm,kwargs", [
    ("unknown", {}), (None, {}), (True, {}), ([], {}),
    ("R-fixed", {}), ("R-fixed", {"fixed_capacity": 0}),
    ("R-fixed", {"fixed_capacity": 25}), ("R-fixed", {"fixed_capacity": True}),
    ("R-fixed", {"fixed_capacity": "30"}),
    ("R-fixed", {"fixed_capacity": float("nan")}),
    ("R-fixed", {"fixed_capacity": float("inf")}),
    ("R-oracle", {}), ("R-oracle", {"true_capacities": ()}),
    ("R-oracle", {"true_capacities": [20., 60.]}),
    ("R-oracle", {"true_capacities": (True,)}),
    ("R-oracle", {"true_capacities": (0.,)}),
    ("R-oracle", {"true_capacities": (-20.,)}),
    ("R-oracle", {"true_capacities": (float("nan"),)}),
    ("R-oracle", {"true_capacities": (float("inf"),)}),
    ("R-oracle", {"true_capacities": (1e6 + 1,)}),
    ("R-oracle", {"true_capacities": (20.,) * 4097}),
    ("R-oracle", {"true_capacities": CAPACITIES, "fixed_capacity": 30}),
    ("R-greedy", {"fixed_capacity": 40}),
    ("R-greedy", {"true_capacities": CAPACITIES}),
])
def test_invalid_reference_parameters_are_rejected(arm, kwargs):
    with pytest.raises(ValueError):
        ReferenceForager(arm, **kwargs)


@pytest.mark.parametrize("phi", [0., .25, .4, 1., True, None, ".5", float("nan"), float("inf")])
def test_invalid_floor_fraction_is_rejected(phi):
    with pytest.raises(ValueError):
        ReferenceForager("R-fixed", phi=phi, fixed_capacity=30)


def test_oracle_rejects_unknown_visible_site_before_memory_changes():
    reference = ReferenceForager("R-oracle", true_capacities=(20.,))
    before = deepcopy(reference.memory())
    with pytest.raises(ValueError, match="outside oracle capacities"):
        reference(packet())
    assert reference.memory() == before
