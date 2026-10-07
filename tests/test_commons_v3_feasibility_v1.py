"""Policy-independent relaxation tests; no qualification environments run."""

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import json
import math

import pytest

from swarm_societies.commons_v3.engine import Action, Config, initialize, step
from swarm_societies.commons_v3 import feasibility_v1 as feasibility


def q(certificate, key, section="bounds"):
    return feasibility.exact_quantity(certificate[section][key])


def one_site(**kwargs):
    return Config(width=1, height=1, n_agents=1, n_patches=1, **kwargs)


def test_phase_order_excludes_last_renewal_and_keeps_harvest_cost():
    cfg = one_site(initial_inventory=0, initial_patch_stock=1, patch_capacity=100,
                   need=100, max_harvest=100, harvest_cost_per_unit=.5,
                   renewal_rate=0, recovery=100, weather_amplitude=0)
    first = feasibility.consumption_certificate(cfg, 1)
    second = feasibility.consumption_certificate(cfg, 2)
    assert first["window"]["usable_renewals"] == 0
    assert Fraction(1, 2) <= q(first, "resource_total") < Fraction(500001, 1000000)
    assert Fraction(101, 2) <= q(second, "resource_total") < Fraction(50500001, 1000000)
    assert first["status"] == second["status"] == "proven_insufficient"
    result = step(initialize(cfg, 900_001), (Action(harvest=100),))
    assert result.ledger.agents[0].consumption == .5
    assert result.ledger.patches[0].growth > result.ledger.agents[0].consumption


def test_late_window_deliberately_starts_with_full_capacities():
    cfg = one_site(initial_inventory=0, initial_patch_stock=0, inventory_capacity=8,
                   patch_capacity=40, need=10, renewal_rate=0, recovery=0)
    certificate = feasibility.consumption_certificate(cfg, 20, window_start=19)
    assert certificate["window"] == {"start_tick": 19, "stop_tick": 20, "ticks": 1,
                                      "starting_resources": "full_capacities_relaxation", "usable_renewals": 0}
    assert q(certificate, "initial_inventory_total") == 8
    assert q(certificate, "initial_stock_total") == 40
    assert q(certificate, "consumption_total") == 8
    assert certificate["status"] == "proven_insufficient"


def test_analytic_logistic_maximum_and_zero_renewal():
    cfg = one_site(patch_capacity=40, renewal_rate=.25, recovery=.5,
                   weather_amplitude=.5, initial_patch_stock=0)
    certificate = feasibility.consumption_certificate(cfg, 10)
    assert q(certificate, "exact_real_growth_per_patch_tick") == Fraction(9, 2)
    assert Fraction(9, 2) <= q(certificate, "growth_per_patch_tick") < Fraction(4500001, 1000000)
    empty = feasibility.consumption_certificate(replace(cfg, renewal_rate=0, recovery=0), 10)
    assert q(empty, "growth_per_patch_tick") == 0


def test_sustainable_bound_is_not_initial_stock_or_finite_feasibility():
    cfg = one_site(initial_inventory=80, initial_patch_stock=40, need=1,
                   renewal_rate=0, recovery=0)
    certificate = feasibility.consumption_certificate(cfg, 1)
    assert certificate["status"] == "unresolved"
    assert q(certificate, "consumption_total") == 1
    assert q(certificate, "consumption_per_tick", "sustainable_ceiling") < Fraction(1, 10**8)
    assert certificate["scope"]["policy_optimality_claim"] is False
    assert certificate["scope"]["feasibility_claim_if_unresolved"] is False


def test_harvest_rate_and_inventory_caps_are_independent_ceilings():
    cfg = one_site(initial_inventory=0, initial_patch_stock=40, need=2,
                   max_harvest=.25, renewal_rate=4, recovery=1)
    certificate = feasibility.consumption_certificate(cfg, 20)
    assert certificate["limiting_bounds"] == ["harvest_rate_total"]
    assert certificate["status"] == "proven_insufficient"
    assert q(certificate, "consumption_total") < 5
    capacity = feasibility.consumption_certificate(replace(cfg, inventory_capacity=.1), 20)
    assert capacity["limiting_bounds"] == ["consumption_cap_total"]
    assert q(capacity, "consumption_total") == 20 * Fraction(.1)


def test_zero_need_has_no_ratio_and_no_insufficiency_claim():
    certificate = feasibility.consumption_certificate(one_site(need=0), 4)
    assert certificate["status"] == "unresolved"
    assert q(certificate, "consumption_total") == 0
    assert certificate["bounds"]["fraction_of_need"] is None
    assert certificate["sustainable_ceiling"]["fraction_of_need"] is None


@pytest.mark.parametrize("contention", ["proportional", "keyed_priority"])
@pytest.mark.parametrize("law", ["logistic", "additive"])
def test_every_legal_transfer_and_contention_flow_remains_below_certificate(contention, law):
    cfg = Config(width=1, height=1, n_agents=4, n_patches=1, initial_inventory=.7,
                 inventory_capacity=1.7, need=.3, initial_patch_stock=1.3,
                 patch_capacity=2.1, renewal_rate=.3, recovery=.012345,
                 max_harvest=1.1234, harvest_cost_per_unit=.271828,
                 message_byte_cost=.0000001, contention=contention, renewal_law=law)
    state = initialize(cfg, 900_002)
    rows = []
    for tick in range(24):
        actions = tuple(Action(harvest=cfg.max_harvest if (i + tick) % 3 else .1,
                               transfers=tuple((j, .123456789 if tick % 2 else 1.7)
                                               for j in range(4) if j != i),
                               messages=(((i + 1) % 4, "x"),), reserve=.07 if i % 2 else 0.)
                        for i in range(4))
        result = step(state, actions)
        rows.append(result.ledger)
        state = result.state
    for start in (0, 6, 23):
        certificate = feasibility.consumption_certificate(cfg, 24, window_start=start)
        actual = sum((Fraction(a.consumption) for row in rows[start:] for a in row.agents), Fraction())
        assert actual <= q(certificate, "consumption_total")
        nested_total = math.fsum(row.consumption for row in rows[start:])
        assert Fraction(nested_total) <= q(certificate, "reported_consumption_total")
    assert Fraction(result.metrics.consumption) <= q(feasibility.consumption_certificate(cfg, 24), "reported_consumption_total")


@pytest.mark.parametrize("law", ["logistic", "additive"])
@pytest.mark.parametrize("capacity", [1e-300, .03125, 40., 1e6])
def test_growth_rounding_envelope_at_extreme_capacities(law, capacity):
    for rate in (0., .24, 4.):
        for share in (0., .25, .5, .75, 1.):
            cfg = one_site(initial_inventory=0, need=0, patch_capacity=capacity,
                           initial_patch_stock=capacity * share, renewal_rate=rate,
                           recovery=capacity * .01, weather_amplitude=1., renewal_law=law)
            result = step(initialize(cfg, 900_003), (Action(),))
            certificate = feasibility.consumption_certificate(cfg, 2)
            assert Fraction(result.ledger.patches[0].growth) <= q(certificate, "growth_per_patch_tick")


def test_exact_threshold_comparison_never_uses_display_or_tolerance():
    cfg = one_site(need=1, inventory_capacity=.5, initial_inventory=.5,
                   max_harvest=0, initial_patch_stock=0, renewal_rate=0, recovery=0)
    equal = feasibility.consumption_certificate(cfg, 1, target_fraction=Fraction(1, 2))
    above = feasibility.consumption_certificate(cfg, 1, target_fraction=Fraction(1, 2) + Fraction(1, 2**200))
    assert equal["target_fraction_exact"]["upper_float"] == .5
    assert above["target_fraction_exact"]["upper_float"] == math.nextafter(.5, math.inf)
    assert equal["target_fraction"] == above["target_fraction"] == .5
    assert equal["status"] == "unresolved"
    assert above["status"] == "proven_insufficient"


def test_rational_certificate_json_is_finite_and_outward():
    certificate = feasibility.consumption_certificate(Config(), 512, window_start=384, target_fraction=.95)
    loaded = json.loads(json.dumps(certificate, allow_nan=False))
    assert loaded == certificate
    def check(value):
        if type(value) is dict:
            if set(value) == {"numerator", "denominator", "upper_float"}:
                exact = feasibility.exact_quantity(value)
                assert Fraction(value["upper_float"]) >= exact
            else:
                for item in value.values():
                    check(item)
    check(certificate)
    assert certificate == feasibility.consumption_certificate(Config(), 512, window_start=384, target_fraction=.95)


@pytest.mark.parametrize("kwargs", [{"horizon": True}, {"horizon": 0}, {"horizon": 2**31},
                                   {"horizon": 2, "window_start": True},
                                   {"horizon": 2, "window_start": -1},
                                   {"horizon": 2, "window_start": 2},
                                   {"horizon": 2, "target_fraction": False},
                                   {"horizon": 2, "target_fraction": math.nan},
                                   {"horizon": 2, "target_fraction": -.1},
                                   {"horizon": 2, "target_fraction": 1.1}])
def test_invalid_inputs_are_rejected_without_boolean_number_alias(kwargs):
    with pytest.raises(ValueError):
        feasibility.consumption_certificate(Config(), **kwargs)


def test_quantity_reader_rejects_boolean_numbers_and_changed_display():
    value = feasibility.consumption_certificate(Config(), 1)["bounds"]["consumption_total"]
    for name, replacement in (("numerator", True), ("denominator", False), ("upper_float", False),
                              ("upper_float", value["upper_float"] + 1)):
        modified = deepcopy(value)
        modified[name] = replacement
        with pytest.raises(ValueError):
            feasibility.exact_quantity(modified)


def test_certificate_rejects_incompatible_arithmetic(monkeypatch):
    class DifferentFloatInfo:
        radix, mant_dig, max_exp, rounds = 2, 24, 128, 1
    monkeypatch.setattr(feasibility.sys, "float_info", DifferentFloatInfo())
    with pytest.raises(RuntimeError, match="binary64"):
        feasibility.consumption_certificate(Config(), 1)
