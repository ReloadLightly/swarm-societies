# Commons v3 physical consumption ceilings, version 1

This diagnostic derives policy-independent upper bounds from the frozen
`commons-v3-physical-v1` engine. It runs no environments and selects no policy.
A target above a certified upper bound is physically impossible under the
stated arithmetic model. A target below that bound remains **unresolved**:
the relaxation does not construct a feasible policy or establish an optimum.
It cannot attribute the remainder of a policy's shortfall to navigation alone.

The implementation is
[`feasibility_v1.py`](../swarm_societies/commons_v3/feasibility_v1.py).
It changes neither engine physics nor completed evidence. Its assumptions and
threshold inputs must be frozen with any prospective qualification protocol.
No empirical qualification or model spending is part of this diagnostic.

## API and interpretation

```python
from fractions import Fraction
from swarm_societies.commons_v3.engine import Config
from swarm_societies.commons_v3.feasibility_v1 import consumption_certificate, exact_quantity

certificate = consumption_certificate(
    Config(), horizon=512, window_start=384, target_fraction=Fraction(95, 100)
)
upper = exact_quantity(certificate["bounds"]["consumption_total"])
```

The window is `[window_start, horizon)`. A window starting at tick zero uses
the configured initial inventories and stocks. A later window is allowed to
start with every inventory and resource site full, irrespective of what an
actual preceding trajectory could achieve. `horizon` is at most the engine's
tick limit, `2**31 - 1`; the guarantee covers successful, validated steps.

Each quantity contains an exact integer `numerator` and positive integer
`denominator`, plus an `upper_float` rounded toward positive infinity.
All bound calculations and status decisions use `Fraction`, never the display
float or a tolerance. Top-level `horizon`, `window_start` and `target_fraction`
identify a certificate's requested scope. The last is a convenient nearest
float; `target_fraction_exact` preserves the exact input used for decisions.
A supplied float means its exact binary value; use a
`Fraction` to specify an exact decimal threshold. JSON serialization preserves
the rational certificate. `status` is `proven_insufficient` only when the
certified consumption ceiling is strictly less than the target fraction of
aggregate need. Equality and every other case return `unresolved`. With zero
need the consumption ceiling is zero, ratios are null and status is unresolved.

`bounds.consumption_total` bounds the **exact sum of the binary64 consumption
values in individual agent ledgers**. The separately enlarged
`reported_consumption_total` also accommodates ordinary engine cumulative
metrics, endpoint differences and nested `math.fsum` ledger totals. The
`reported_consumption_per_agent_tick` field includes one final division's
rounding. Reporting allowances do not change the resource decision. These
are bounds on unweighted consumption; terminal wealth and utility weights do
not enter them. Reading a saved rounded scalar cannot recover the exact
underlying ledger sum, so audit canonical sums from ledger entries when needed.

## Exact-real relaxation

Write `N` for population, `P` for sites, `K` for site capacity, `B` for inventory
capacity, `d` for per-person need, `h` for maximum gross harvest, `r` for renewal
rate, `a` for recovery, `w` for weather amplitude and `c` for gross harvest cost.
All are the engine's configured values. Let `L` be the window length and
`I0,S0` its relaxed initial total inventory and site stock. Movement, messages,
access, interference among agents, reserve decisions and discarded inventory
can only reduce attainable consumption in exact arithmetic; the relaxation
does not charge them. Obligatory harvest cost is retained: one gross unit of
extraction contributes at most `1-c` inventory units. Transfers conserve mass
in exact arithmetic and have a separate numerical allowance below.

For any post-extraction stock `x` between zero and `K`,

```
x * (1 - x/K) = K/4 - (x - K/2)**2 / K <= K/4.
```

The additive law directly uses `r*K/4`. Weather is at most `1+w`, and renewal
is capped by the remaining space. Therefore each site's gross growth per tick
is at most

```
g = min(K, (r*K/4 + a) * (1+w)).
```

This is an optimistic bound for every weather realization; it does not assume
that average weather equals its maximum, or that the growth-maximizing stock
can be maintained while meeting the proposed consumption target.

The engine extracts and consumes **before** renewal. Consequently only the
first `L-1` renewals in a window can support that window's consumption. Summing
the stock and inventory balances gives

```
gross extraction <= S0 + (L-1)*P*g
consumption <= I0 + (1-c) * (S0 + (L-1)*P*g).
```

Two additional ceilings hold independently:

```
consumption <= N*L*min(d, B)
consumption <= I0 + (1-c)*L*N*h.
```

The first reflects consumption's need cap and the engine's inventory cap
**before consumption**. The second retains the maximum harvesting rate. The
certificate takes the minimum of the three ceilings, after the explicit
arithmetic allowances below. It does not assert that this minimum is attainable.
For tick-zero windows, `I0=N*initial_inventory` and `S0=P*initial_patch_stock`.
For later windows, `I0=N*B` and `S0=P*K`; even the first stock in that window may
be consumed, whereas renewal following its final consumption may not.

Dropping initial-resource terms per unit time gives the exact-real sustained
consumption ceiling per tick

```
min(N*min(d,B), (1-c)*P*g, (1-c)*N*h).
```

The reported sustainable ceiling adds per-tick numerical allowances. This is
a replenishment ceiling with vanishing initial-resource terms, not proof of
attainability or a claim that the finite, bounded-counter engine runs forever.

## Conservative binary64 certificate

The supported arithmetic model is CPython with IEEE 754 binary64, rounding to
nearest and gradual underflow. Let `u=2**-53` and `eta=2**-1074`. A basic
operation has absolute error at most `u*abs(exact result)+eta`. For `math.fsum`
we allow `4*u*sum(abs(inputs))+eta`, covering ordinary accurate summation and
the possible last-bit double rounding on supported platforms. The module
checks interpreter and binary64 characteristics; it does not independently
verify the hardware or prove a particular C library implementation. Changing
rounding mode, flushing subnormals, replacing `math.fsum`, or using a different
arithmetic implementation is outside the certificate's assumptions.

Config values are converted to their exact rationals. Intermediate upper
certificates can be rounded **upwards** to a `2**-128` rational lattice to keep
records compact. This adds conservative slack, including for exceptionally
small configurations, and never rounds a bound down.

First bound renewal arithmetic itself. In the logistic expression let
`q=fl(x/K)`, `b=fl(1-q)`, `A=fl(r*x)`. Monotonicity gives `q,b` in `[0,1]`;
the errors in `q` and `b` are each at most `u+eta`. The first product's error is
at most `u*r*K+eta`. Thus the exact product before its final rounding satisfies

```
A*b <= r*K/4 + 2*r*K*(u+eta) + (u*r*K+eta).
```

Round this ceiling upward through the final multiplication, addition of
recovery and multiplication by the weather envelope. For additive renewal,
round `r*K`, division by four, addition of recovery and weather multiplication
upward in their actual order. The hash fraction rounds into `[0,1]` and the
weather expression is monotonically bounded by `fl(1+w)`, for which the
certificate uses an outward envelope. At `w=0`, weather is exactly one; zero
rate and recovery give exactly zero growth. The capacity remainder
`fl(K-x)` is at most `K`, so the resulting upper bound `g_plus` is capped at
`K`. These steps retain rounding effects in the actual renewal law.

For material conservation, define

```
M = 16*(N+P+1)*(B+K+h+d+a+1)
E = upward_lattice(8*u*M).
```

`M` bounds the magnitudes of all basic operations relevant to noncumulative
material balances and the exact sums of their nonnegative `fsum` inputs.
In particular a recipient receives at most `(N-1)*B` requested units, a
harvest request sum is at most `N*h`, production intermediates are at most
`4*K`, and weather potential is bounded by slightly more than `2*(4*K+a)`.
All are far below binary64 overflow for the validated config range. Message
prices that exceed inventory can be arbitrarily larger than useful material
flows within the config limits; they are rejected and need no mass-error
term. Accepted movement/message payments are nonnegative subtractions and
cannot increase retained inventory by monotonicity. Cumulative counters and
display aggregation are handled separately. Hence `E` covers each relevant
operation and `fsum` error, including underflow.

For either contention rule, total allocation from availability `A0` is at most
`A0+(N+2)*E`, and each recipient's allocation is at most their request. For
proportional allocation, write the rounded request total as `t`. If `t<=A0`,
the request sum is at most `A0+E`. Otherwise the rounded scale is at most one;
its exact weighted error obeys `t*fl(A0/t)<=A0+E`. The request-total error adds
at most `E`, and at most `N` rounded products add `N*E`. The engine's final
excess correction only decreases allocations. In priority allocation,
telescoping at most `N` rounded remaining-budget subtractions adds at most
`N*E` instead. The same bound therefore covers both paths.

A transfer sender's retained inventory plus their exact sum of allocations
is at most their pre-transfer inventory plus `(N+2)*E`: if the retained
amount is positive, its subtraction and outgoing `fsum` need only `2*E`;
otherwise the allocator bound applies. Each recipient's repeated incoming
additions contribute at most `(N-1)*E`. Across all agents the transfer phase
therefore adds at most `N*(2*N+1)*E` to the relaxed material account.
For each agent, one harvest-cost multiplication, three pre-cap arithmetic
operations and the final inventory subtraction add at most `5*E` to
`inventory_after + consumed`. Capping inventory only decreases this sum.
The exact per-tick agent inequality is consequently

```
I_after + C <= I_before + (1-c)*gross_harvest + eI
eI = N*(2*N+6)*E.
```

For each site, allocation, rounded extraction totals, clipped subtraction and
stock addition give

```
gross_harvest + stock_after <= stock_before + growth + (N+3)*E.
eS = P*(N+3)*E.
```

The final step can omit growth and retain the same conservative allowance.
Telescoping both inequalities gives the implemented resource ceiling

```
I0 + (1-c)*(S0 + (L-1)*P*g_plus + L*eS) + L*eI.
```

The harvest-rate ceiling becomes `I0+(1-c)*L*N*h+L*eI`; no allocation can
increase an individual's declared harvest request. The exact demand/inventory
ceiling needs no rounding allowance, since `min` and nonnegative subtraction
never make consumption exceed either stored cap. The sustainable replenishment
ceiling becomes `(1-c)*(P*g_plus+eS)+eI`, also intersected with the demand/capacity
and harvesting ceilings. These allowances cover every legal joint action,
including transfers and messages; they do not assume the current baselines
use only a subset of engine features.

Finally, for horizon `H`, write `m=min(d,B)` and
`gamma=H*u/(1-H*u)`. The error of an agent's cumulative consumption counter is
at most `gamma*H*m + H*eta/(1-H*u)`. Add the `fsum` allowance for the population,
then double the result to cover both endpoints. If that single-endpoint error
is `e`, also allow `u*(H*N*m+2*e)+eta` for the final floating subtraction.
This avoids relying on exact cancellation of nearby endpoints. The resulting
allowance also dominates the usual two levels of positive ledger `fsum` aggregation. This
larger reporting allowance is recorded separately from the physical ceiling.
No observed residual, chosen tolerance or empirical error estimate enters any
proof or status decision.

## Verification and limits

Run `python3 -m pytest -q tests/test_commons_v3_feasibility_v1.py`. Focused tests
cover consume-before-renew timing, gross conversion, inventory/harvest caps,
late-window relaxation, exact threshold boundaries, outward JSON fractions,
strict boolean/number distinctions, the arithmetic precondition, transfer and
contention paths, and renewal at extreme capacities. Small synthetic worlds
check bounds against actual engine ledger values; they use no qualification
seeds and are not qualification observations.

This relaxation intentionally discards geography, individual allocation,
travel costs, useful-stock location, feedback, information and policy limits.
It can establish resource insufficiency; it cannot certify ecological
sustainability, incentive alignment, equilibrium, a private optimum or a
strongest policy. A policy falling below a ceiling can still be resource
limited in ways this relaxed bound does not capture. Separate prospective
ecological and incentive criteria remain necessary.
