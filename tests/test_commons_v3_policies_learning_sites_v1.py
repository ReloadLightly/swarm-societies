"""Static legal-packet L0 fixtures; no closed-loop arena is executed here."""

from copy import deepcopy
import json

import pytest

from swarm_societies.commons_v3.evidence_sites_v1 import CleanTransition
from swarm_societies.commons_v3.policies_learning_sites_v1 import AsocialForager
from swarm_societies.commons_v3.policies_navigation_v1 import ForagerPolicy
from swarm_societies.commons_v3.posterior_sites_v1 import SitePosterior


def packet(*, tick=0, stock=20., inventory=10., x=1, peers=(), site_rows=None):
    """A prescribed observation, independent of any simulated policy rollout."""
    me = {"id": 0, "x": x, "y": 1, "inventory": inventory,
          "width": 7, "height": 3, "need": 1.2, "inventory_capacity": 80.,
          "max_harvest": 4., "sensing_radius": 2, "movement_cost": .02,
          "harvest_cost_per_unit": .02, "message_byte_cost": .001,
          "max_message_bytes": 128, "max_messages": 1}
    visible = site_rows if site_rows is not None else ((0, 1, stock), (1, 3, 12.))
    sites = []
    for site_id, site_x, site_stock in visible:
        sites.append({"id": site_id, "x": site_x, "y": 1, "stock": site_stock,
                      "peer_count": int(site_x == x) + sum(peer["x"] == site_x and peer["y"] == 1
                                                           for peer in peers)})
    return {"version": "commons-v3-physical-sites-v1",
            "observation_version": "commons-v3-observation-v2", "tick": tick,
            "self": me, "sites": sites, "peers": [dict(peer) for peer in peers], "messages": [],
            "ecology": {"renewal_law": "logistic", "renewal_rate": .24, "recovery": .02,
                        "weather_multiplier": {"distribution": "uniform", "low": .9, "high": 1.1},
                        "capacity_prior": {"distribution": "log_uniform", "low": 8., "high": 100.},
                        "initial_stock_fraction": {"distribution": "uniform", "low": .3, "high": .9,
                                                   "independent_by_site": True}}}


def inject(observation, posteriors, phi, q):
    result = deepcopy(observation)
    for site in result["sites"]:
        site["capacity"] = (phi / .5) * posteriors[site["id"]].quantile(q)
    return result


@pytest.mark.parametrize("phi", [.375, .5])
@pytest.mark.parametrize("q", [.25, .5])
def test_static_packet_sequence_matches_manual_posterior_injection_and_frozen_memory(phi, q):
    wrapper = AsocialForager(phi=phi, q=q)
    baseline = ForagerPolicy(2, .5, "net_yield")
    manual = {0: SitePosterior(0), 1: SitePosterior(1)}
    first = packet()
    before = deepcopy(first)
    manual[0].observe_stock(20.)
    manual[1].observe_stock(12.)
    expected = baseline(inject(first, manual, phi, q))
    action = wrapper(first)
    assert action == expected
    assert action.move == (0, 0) and action.harvest == 0.
    assert wrapper.memory()["forager"] == baseline.memory()
    assert first == before
    # Prescribed solitary zero-harvest transition, with weather multiplier 1.
    # This is not a world step or a closed-loop episode.
    later = packet(tick=1, stock=22.42, inventory=8.8)
    manual[0].update(CleanTransition(0, 0, 20., 22.42, 20., 0.))
    manual[0].observe_stock(22.42)
    for site_id, record in baseline.records.items():
        record["capacity"] = (phi / .5) * manual[site_id].quantile(q)
    expected = baseline(inject(later, manual, phi, q))
    later_before = deepcopy(later)
    assert wrapper(later) == expected
    assert wrapper.memory()["forager"] == baseline.memory()
    assert [wrapper.posteriors[i].memory() for i in sorted(manual)] == [manual[i].memory() for i in sorted(manual)]
    assert later == later_before
    assert wrapper.evidence.seen == {(0, 0)}
    assert json.loads(json.dumps(wrapper.memory())) == wrapper.memory()


def test_initial_packet_bounds_all_visible_sites_without_inventing_unseen_sites():
    wrapper = AsocialForager()
    assert wrapper.phi == .375 and wrapper.q == .5 and wrapper.grid_size == 400
    wrapper(packet())
    assert set(wrapper.posteriors) == set(wrapper.records) == {0, 1}
    assert wrapper.posteriors[0].memory()["operations"] == [{"kind": "bound", "stock": 20.}]
    assert wrapper.posteriors[1].memory()["operations"] == [{"kind": "bound", "stock": 12.}]
    assert wrapper.evidence.seen == set()
    assert wrapper.aggressive is False
    assert wrapper.reserve_ticks == 2 and wrapper.stock_floor_fraction == .5


def test_transition_precedes_new_bound_and_keeps_off_grid_saturation_atom():
    wrapper = AsocialForager()
    first = packet(stock=9.99, site_rows=((0, 1, 9.99),))
    action = wrapper(first)
    assert action.harvest == 0. and action.move == (0, 0)
    wrapper(packet(tick=1, stock=10., inventory=8.8, site_rows=((0, 1, 10.),)))
    posterior = wrapper.posteriors[0]
    assert posterior.atoms[10.] > 0.
    assert [operation["kind"] for operation in posterior.memory()["operations"]] == ["bound", "transition"]
    expected = SitePosterior(0)
    expected.observe_stock(9.99)
    expected.update(CleanTransition(0, 0, 9.99, 10., 9.99, 0.))
    assert posterior.atoms == expected.atoms
    assert posterior.memory() == expected.memory()


def test_new_peer_confounds_transition_but_new_stock_still_updates_capacity_bound():
    wrapper = AsocialForager()
    wrapper(packet())
    wrapper(packet(tick=1, stock=22., inventory=8.8, peers=({"id": 1, "x": 1, "y": 1},)))
    assert wrapper.evidence.seen == set()
    assert wrapper.posteriors[0].memory()["operations"] == [
        {"kind": "bound", "stock": 20.}, {"kind": "bound", "stock": 22.}]
    assert wrapper.posteriors[0].atoms == {}


def test_remembered_nonvisible_site_capacity_is_refreshed_from_current_posterior():
    wrapper = AsocialForager()
    wrapper(packet())
    wrapper(packet(tick=1, stock=22.42, inventory=8.8))
    expected = (wrapper.phi / .5) * wrapper.posteriors[0].quantile(wrapper.q)
    old = deepcopy(wrapper.records[0])
    wrapper.records[0]["capacity"] = 999.
    # A skipped tick deliberately makes this a new local baseline, not an
    # unobserved multi-step extraction transition.
    wrapper(packet(tick=3, x=5, inventory=6.4, site_rows=((1, 3, 12.), (2, 6, 40.))))
    assert wrapper.records[0] == {**old, "capacity": expected}
    assert set(wrapper.posteriors) == {0, 1, 2}
    assert wrapper.evidence.seen == {(0, 0)}


def test_repeated_packet_reuses_action_without_duplicate_learning_or_navigation():
    wrapper = AsocialForager()
    wrapper(packet())
    later = packet(tick=1, stock=22.42, inventory=8.8)
    action = wrapper(later)
    before = deepcopy(wrapper.memory())
    assert wrapper(deepcopy(later)) is action
    assert wrapper.memory() == before
    assert wrapper.evidence.seen == {(0, 0)}


def test_hidden_world_fields_and_messages_cannot_change_actions_or_memories():
    class Unreadable:
        def __iter__(self):
            raise AssertionError("hidden or message data accessed")

        def __deepcopy__(self, memo):
            raise AssertionError("hidden or message data copied")

    ordinary = packet()
    poisoned = packet()
    for name in ("true_capacities", "ledger", "weather", "messages", "future_world"):
        poisoned[name] = Unreadable()
    poisoned["ecology"]["world_condition"] = Unreadable()
    left, right = AsocialForager(), AsocialForager()
    assert left(ordinary) == right(poisoned)
    assert left.memory() == right.memory()
    assert left.last_action.messages == ()


@pytest.mark.parametrize("change", [
    lambda ecology: ecology.update(renewal_law="additive"),
    lambda ecology: ecology.update(renewal_rate=.25),
    lambda ecology: ecology.update(recovery=.01),
    lambda ecology: ecology["weather_multiplier"].update(distribution="normal"),
    lambda ecology: ecology["weather_multiplier"].update(low=.8),
    lambda ecology: ecology["weather_multiplier"].update(high=1.2),
    lambda ecology: ecology["capacity_prior"].update(distribution="uniform"),
    lambda ecology: ecology["capacity_prior"].update(low=10.),
    lambda ecology: ecology["capacity_prior"].update(high=90.),
    lambda ecology: ecology["initial_stock_fraction"].update(high=1.),
    lambda ecology: ecology["initial_stock_fraction"].update(independent_by_site=False),
    lambda ecology: ecology.pop("renewal_law"),
])
def test_mismatched_declared_model_is_rejected_before_any_memory_change(change):
    observation = packet()
    change(observation["ecology"])
    wrapper = AsocialForager()
    before = wrapper.memory()
    with pytest.raises(ValueError, match="declared ecology"):
        wrapper(observation)
    assert wrapper.memory() == before


@pytest.mark.parametrize("observation", [None, [], {}, {"ecology": None}])
def test_missing_declared_ecology_is_rejected(observation):
    wrapper = AsocialForager()
    with pytest.raises(ValueError):
        wrapper(observation)


@pytest.mark.parametrize("kwargs", [
    {"phi": 0.}, {"phi": .25}, {"phi": True}, {"phi": float("nan")},
    {"q": 0.}, {"q": .375}, {"q": 1.}, {"q": True}, {"q": float("nan")},
    {"grid_size": 0}, {"grid_size": 15}, {"grid_size": 400.}, {"grid_size": True},
])
def test_invalid_wrapper_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        AsocialForager(**kwargs)
