"""Conservative, policy-independent consumption certificates for frozen v3.

This is an upper-bound relaxation, not a controller or a feasibility solver.
It executes no worlds.  Exact rational certificates include a conservative
binary64 allowance; their float fields are outward-rounded presentation only.
See docs/commons-v3-feasibility-v1.md for the proof and arithmetic assumptions.
"""

from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction
import math
import sys
from typing import Any

from .engine import Config, VERSION as ENGINE_VERSION


VERSION = "commons-v3-feasibility-v1"
UNIT_ROUNDOFF = Fraction(1, 2**53)
MIN_SUBNORMAL = Fraction(1, 2**1074)
CERTIFICATE_FRACTION_BITS = 128


def _exact(value: int | float | Fraction) -> Fraction:
    if type(value) not in (int, float, Fraction):
        raise ValueError("expected an integer, finite float, or Fraction; bool is not numeric")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("expected a finite number")
    return Fraction(value)


def _ceil_lattice(value: Fraction) -> Fraction:
    """Round only upwards onto a rational lattice to keep certificates compact."""
    scale = 2**CERTIFICATE_FRACTION_BITS
    numerator = value.numerator * scale
    return Fraction(-(-numerator // value.denominator), scale)


def _rounded_upper(value: Fraction) -> Fraction:
    # Round-to-nearest binary64 has error <= u*abs(exact result) + min_subnormal.
    # Exact zero stays zero; the lattice adds only outward certificate slack.
    return _ceil_lattice(value * (1 + UNIT_ROUNDOFF) + MIN_SUBNORMAL) if value else Fraction(0)


def _upper_float(value: Fraction) -> float:
    result = float(value)
    if Fraction(result) < value:
        result = math.nextafter(result, math.inf)
    return result


def _quantity(value: Fraction) -> dict[str, int | float]:
    return {"numerator": value.numerator, "denominator": value.denominator,
            "upper_float": _upper_float(value)}


def exact_quantity(record: dict[str, Any]) -> Fraction:
    """Read a certificate's exact value; never compare its display float."""
    if type(record) is not dict or set(record) != {"numerator", "denominator", "upper_float"}:
        raise ValueError("invalid exact quantity")
    numerator, denominator = record["numerator"], record["denominator"]
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError("invalid rational numerator or denominator")
    value = Fraction(numerator, denominator)
    if type(record["upper_float"]) is not float or record["upper_float"] != _upper_float(value):
        raise ValueError("invalid outward float display")
    return value


def _arithmetic_precondition() -> None:
    if (sys.implementation.name != "cpython" or sys.float_info.radix != 2
            or sys.float_info.mant_dig != 53 or sys.float_info.max_exp != 1024
            or sys.float_info.rounds != 1 or math.ulp(0.0) != float(MIN_SUBNORMAL)):
        raise RuntimeError("certificate requires CPython round-to-nearest IEEE binary64 with subnormals")


def _growth_upper(config: Config) -> tuple[Fraction, Fraction, Fraction]:
    """Exact-real maximum, weather envelope, and outward binary64 growth bound."""
    rate, capacity = _exact(config.renewal_rate), _exact(config.patch_capacity)
    recovery, amplitude = _exact(config.recovery), _exact(config.weather_amplitude)
    ideal = min(capacity, (rate * capacity / 4 + recovery) * (1 + amplitude))
    # The hash fraction rounds to [0,1]. Monotonic arithmetic makes the inner
    # weather expression <= 1, its scaled expression <= amplitude.
    weather = _rounded_upper(1 + amplitude) if amplitude else Fraction(1)
    if config.renewal_law == "logistic":
        # q=fl(x/K), b=fl(1-q), a=fl(r*x), p=fl(a*b), with b in [0,1].
        # r*x*(1-x/K)<=r*K/4. Errors in q and b are <=u+eta each.
        error_ratio = UNIT_ROUNDOFF + MIN_SUBNORMAL
        error_first_product = UNIT_ROUNDOFF * rate * capacity + MIN_SUBNORMAL
        before_last_product = (rate * capacity / 4
                               + 2 * rate * capacity * error_ratio
                               + error_first_product)
        production = _rounded_upper(before_last_product) if rate else Fraction(0)
    else:
        production = _rounded_upper(_rounded_upper(rate * capacity) / 4)
    potential = _rounded_upper(_rounded_upper(production + recovery) * weather)
    # fl(K-x) <= K by monotonicity, so the physical capacity cap is exact here.
    return ideal, weather, min(capacity, potential)


def consumption_certificate(config: Config, horizon: int, *, window_start: int = 0,
                            target_fraction: int | float | Fraction = 1.0) -> dict[str, Any]:
    """Bound total consumption in ticks [window_start, horizon), without runs.

    A zero-start window uses configured initial resources.  A later window
    starts with full inventories and full sites, a deliberately loose relaxation.
    ``proven_insufficient`` means the certified upper bound is strictly below
    the requested fraction of aggregate need; every other result is unresolved.
    Inputs and comparisons use exact rational values of the supplied numbers.
    """
    _arithmetic_precondition()
    if type(config) is not Config:
        raise ValueError("config must be Config")
    config.__post_init__()
    if type(horizon) is not int or not 1 <= horizon <= 2**31 - 1:
        raise ValueError("horizon must be an integer in [1, 2**31-1]")
    if type(window_start) is not int or not 0 <= window_start < horizon:
        raise ValueError("window_start must be an integer in [0, horizon)")
    target = _exact(target_fraction)
    if not 0 <= target <= 1:
        raise ValueError("target_fraction must be in [0,1]")

    n, p, length = config.n_agents, config.n_patches, horizon - window_start
    capacity, site_capacity = _exact(config.inventory_capacity), _exact(config.patch_capacity)
    need, harvest = _exact(config.need), _exact(config.max_harvest)
    net = 1 - _exact(config.harvest_cost_per_unit)
    initial_inventory = n * (capacity if window_start else _exact(config.initial_inventory))
    initial_stock = p * (site_capacity if window_start else _exact(config.initial_patch_stock))
    ideal_growth, weather, growth = _growth_upper(config)

    # M dominates exact magnitudes of material-affecting, noncumulative
    # arithmetic and positive fsum inputs. Unaffordable message-cost arithmetic
    # and cumulative/reporting counters are not needed in this material proof.
    magnitude = 16 * (n + p + 1) * (capacity + site_capacity + harvest + need
                                   + _exact(config.recovery) + 1)
    error = _ceil_lattice(8 * UNIT_ROUNDOFF * magnitude)
    agent_slack = n * (2 * n + 6) * error
    patch_slack = p * (n + 3) * error

    demand = n * length * need
    consumption_cap = n * length * min(need, capacity)
    # No growth after the last consumption can finance this window's meals.
    gross_resource = initial_stock + (length - 1) * p * growth + length * patch_slack
    resource_bound = initial_inventory + net * gross_resource + length * agent_slack
    harvest_bound = initial_inventory + net * length * n * harvest + length * agent_slack
    components = {"consumption_cap_total": consumption_cap,
                  "resource_total": resource_bound, "harvest_rate_total": harvest_bound}
    bound = min(components.values())
    limiting = [name for name, value in components.items() if value == bound]
    sustainable_components = {"consumption_cap_per_tick": n * min(need, capacity),
                             "replenishment_per_tick": net * (p * growth + patch_slack) + agent_slack,
                             "harvest_rate_per_tick": net * n * harvest + agent_slack}
    sustainable = min(sustainable_components.values())

    # This larger reporting allowance also covers differences of endpoint
    # cumulative metrics, as well as the usual nested fsum ledger aggregation.
    # It is not used to weaken or change the exact resource decision.
    hu = horizon * UNIT_ROUNDOFF
    gamma = hu / (1 - hu)
    counter_error = gamma * horizon * min(need, capacity) + horizon * MIN_SUBNORMAL / (1 - hu)
    endpoint_error = n * counter_error + 4 * UNIT_ROUNDOFF * n * (horizon * min(need, capacity) + counter_error) + MIN_SUBNORMAL
    endpoint_subtraction_error = (UNIT_ROUNDOFF * (horizon * n * min(need, capacity)
                                                   + 2 * endpoint_error) + MIN_SUBNORMAL)
    reporting_allowance = _ceil_lattice(2 * endpoint_error + endpoint_subtraction_error)
    reported_bound = bound + reporting_allowance

    return {
        "version": VERSION, "engine_version": ENGINE_VERSION,
        "config": asdict(config), "horizon": horizon, "window_start": window_start,
        "window": {"start_tick": window_start, "stop_tick": horizon, "ticks": length,
                   "starting_resources": "full_capacities_relaxation" if window_start else "configured_initial_resources",
                   "usable_renewals": length - 1},
        "target_fraction": float(target), "target_fraction_exact": _quantity(target),
        "target_consumption_total": _quantity(target * demand),
        "status": "proven_insufficient" if bound < target * demand else "unresolved",
        "limiting_bounds": limiting,
        "bounds": {**{key: _quantity(value) for key, value in components.items()},
                   "initial_inventory_total": _quantity(initial_inventory),
                   "initial_stock_total": _quantity(initial_stock),
                   "demand_total": _quantity(demand),
                   "consumption_total": _quantity(bound),
                   "consumption_per_agent_tick": _quantity(bound / (n * length)),
                   "fraction_of_need": _quantity(bound / demand) if demand else None,
                   "reported_consumption_total": _quantity(reported_bound),
                   "reported_consumption_per_agent_tick": _quantity(_rounded_upper(reported_bound / (n * length))),
                   "exact_real_growth_per_patch_tick": _quantity(ideal_growth),
                   "growth_per_patch_tick": _quantity(growth),
                   "weather_multiplier": _quantity(weather)},
        "sustainable_ceiling": {
            "interpretation": "per_tick_ceiling_with_vanishing_initial_resource_terms_not_attainability",
            **{key: _quantity(value) for key, value in sustainable_components.items()},
            "consumption_per_tick": _quantity(sustainable),
            "consumption_per_agent_tick": _quantity(sustainable / n),
            "fraction_of_need": _quantity(sustainable / (n * need)) if need else None},
        "roundoff": {
            "arithmetic_model": "CPython_binary64_round_to_nearest_subnormals_fsum_error_at_most_4u_sum_plus_eta",
            "canonical_quantity": "exact_sum_of_per_agent_per_tick_ledger_consumption_floats",
            "certificate_fraction_bits": CERTIFICATE_FRACTION_BITS,
            "unit_roundoff": _quantity(UNIT_ROUNDOFF),
            "minimum_subnormal": _quantity(MIN_SUBNORMAL),
            "operation_magnitude_bound": _quantity(magnitude),
            "single_operation_allowance": _quantity(error),
            "agent_material_allowance_per_tick": _quantity(agent_slack),
            "patch_material_allowance_per_tick": _quantity(patch_slack),
            "reporting_allowance_total": _quantity(reporting_allowance)},
        "scope": {
            "all_legal_joint_actions": True, "successful_validated_engine_steps_only": True,
            "movement_message_costs_access_contention_relaxed": True,
            "obligatory_harvest_cost_retained": True, "weather": "worst_case_upper_envelope",
            "policy_optimality_claim": False, "feasibility_claim_if_unresolved": False,
            "executed_episodes": 0},
    }
