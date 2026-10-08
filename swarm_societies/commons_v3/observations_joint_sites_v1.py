"""A2 observations: known logistic form and one unknown shared growth rate.

Physical observations and private own-harvest feedback retain their existing
timing. The true rate is removed and replaced by the approved prior declaration;
neither the realized rate nor a derived growth value enters this packet.
"""
from copy import deepcopy

from . import observations_messages_sites_v1 as private


VERSION = "commons-v3-unknown-rate-observation-v1"
RATE_PRIOR = {"distribution": "log_uniform", "low": .12, "high": .48,
              "shared_across_sites": True}
ECOLOGY = {
    "renewal_law": "logistic",
    "renewal_rate_prior": RATE_PRIOR,
    "recovery": .02,
    "weather_multiplier": {"distribution": "uniform", "low": .9, "high": 1.1},
    "capacity_prior": {"distribution": "log_uniform", "low": 8., "high": 100.},
    "initial_stock_fraction": {"distribution": "uniform", "low": .3, "high": .9,
                               "independent_by_site": True},
}


def validate_ecology(observation):
    """Accept only the declared unknown-rate model, without consulting truth."""
    if (type(observation) is not dict
            or observation.get("unknown_rate_adapter_version") != VERSION):
        raise ValueError("expected the unknown-rate observation adapter")
    if observation.get("ecology") != ECOLOGY:
        raise ValueError("unsupported unknown-rate ecological declaration")
    for site in observation.get("sites", ()):
        if (type(site) is not dict
                or set(site) != {"id", "x", "y", "stock", "peer_count"}):
            raise ValueError("site observations must not expose capacity or derived growth")


def hide_rate(packet):
    """Project one existing private-feedback packet without altering its source."""
    if (type(packet) is not dict or packet.get("adapter_version") != private.VERSION
            or type(packet.get("ecology")) is not dict
            or "renewal_rate" not in packet["ecology"]):
        raise ValueError("expected a known-rate private-feedback observation")
    result = deepcopy(packet)
    result["ecology"].pop("renewal_rate")
    result["ecology"]["renewal_rate_prior"] = deepcopy(RATE_PRIOR)
    result["unknown_rate_adapter_version"] = VERSION
    validate_ecology(result)
    return result


def observations(state, previous_result_or_feedback=None):
    """Produce detached legal packets; all physical fields retain D's timing."""
    return tuple(hide_rate(packet) for packet in
                 private.observations(state, previous_result_or_feedback))
