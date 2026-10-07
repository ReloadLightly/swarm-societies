# Commons v3 development panel v2: numerical navigation repair

This panel follows inspection of the failed navigation control in development
v1. It is another exploratory development run on the **same cases**, not fresh
qualification data. The [v1 physical and development protocol](commons-v3-foundation-protocol.md)
applies, with the policy repair below. All physical laws, parameters, initial
placement, policy score thresholds, seeds, population conditions, horizons,
sensitivity cases, existing scientific outcomes and utility weights remain unchanged.

## Preserved failure and bounded repair

In v1, repeated subtraction of movement costs could leave a scouting agent two
cells from a known site with `0.039999999999999994` units, below the required
`2 * 0.02`. Its exact return-fuel check then refused every move. This could
produce permanent immobility despite nearby resource recovery. Treating the
resulting consumption loss as ecological collapse would be a control failure.
The v1 source freeze and complete results are preserved.

V2 changes only prospective numerical fuel margins in the diagnostic policy:

- For a desired reserve `b`, retain `b + 8 * epsilon`, capped by carrying
  capacity, where `epsilon = 1e-9 * max(1, b)` for nonzero movement cost.
- Admit a scouting step only when inventory covers its immediate movement plus
  the return path to a known site **and** `1e-9 * max(1, required_fuel)`.
- Zero-cost movement receives zero extra reserve or margin.

No movement is discounted and no resources are created. This avoids entering
unaffordable return states from the policy's normal trajectories. It does not
promise to rescue an externally constructed, already underfunded state.
The margins are far smaller than the proposed scientific effect thresholds;
they were chosen to protect the existing budget invariant, not to optimize
ecological performance. Navigation rankings and the half-need scouting threshold
are unchanged. The frozen physical engine is unchanged.

The new implementation is `policies_v2.py`, with separately frozen
`development_v2.py`, a new CLI and this protocol. The original policy and runner
remain available for reproducing the failure. Both source/protocol sets are
pinned before their respective runs; inspecting v1 informed this repair and
disqualifies the reused cases as an untouched evaluation panel.

## Checks and interpretation

Before the v2 panel, test capacity awareness, the prospective fuel invariant,
multi-step return at floating-point boundaries and exact replay. After running,
audit stranded agents and high-stock/low-consumption combinations rather than
assuming that lower consumption means depleted ecology. Run all 56 configurations
and four paired conditions again, retaining all 224 episodes. Compare with v1
to expose the control artifact, but do not count paired reruns or episodes as
new independent evolutionary replications.

An additional engineering diagnostic records, after every transition, the number
of off-site agents whose inventory is below the exact movement cost of returning
to their nearest previously observed site, using that policy's actual memory.
A nonzero count fails the development run and preserves its failure receipt.
This check is prospective for v2, motivated by v1's observed failure; it is not
a new scientific outcome chosen to favor one population condition. Default
initial placement and sensing ensure every policy knows a site. Agents already
on a site do not need fuel to reach it.

The v1 engineering preflight also exposed Python's boolean/numeric equality in
semantic verification. Exact canonical-JSON comparison repaired that metadata
check without changing physics, policies, cases or numerical results; both
preflight and strict-verifier outcomes are compared separately. This repair is
distinct from v2's changed navigation behavior.

The scientific exit gate remains open. In particular, a focal gain that exists
only through terminal reserves, vanishes with longer horizons or smaller storage,
or disappears against a better decentralized policy is not robust evidence of
the intended social dilemma. Four reused seeds and two local diagnostic policies
cannot establish the later qualification or strong-baseline gates. Institutions,
political transitions, enforcement and model-driven search are not part of this
panel.
