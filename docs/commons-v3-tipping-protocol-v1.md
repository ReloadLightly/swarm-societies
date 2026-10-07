# Storage and aggressive-peer prevalence: prospective protocol v1

This separate design adopts option **(b)** of the external review supplied on
7 October 2026: measure the consumption incentives for restraint across storage
capacity and aggressive-peer share. It preserves the completed development
banks and the ecological/incentive qualification protocols frozen at `b44ee25`.
Those protocols retain every original verdict, including weights 0/0.05/0.2,
capacity 8 and their five declared peer counts. This design neither extends
their samples nor changes their interpretation thresholds.

**Status: numerical design specified; implementation and source-closure freeze
pending. No episodes are authorized by a prepared directory alone.** Before
execution, implement a separately versioned registry, recorder integration,
analysis and recovery path, verify them, and commit and push this protocol with
the complete source closure and design hash. Record remote commit verification.
Do not run this panel while completing or recovering the frozen incentive bank.
No prospective episodes have been run for this protocol.

## Question and scope

At the reference ecology, for which storage capacities and peer compositions
does switching a focal individual from a frozen restrained controller to its
supplied aggressive variant improve **consumption**? Does widespread aggression
lower consumption relative to universal restraint? Report the complete surface,
including no crossover, multiple reversals and unresolved regions. A unique,
monotone tipping point is not assumed.

The review's seeds 90001–90008 are exploratory evidence for choosing this
question. They cannot become confirmation seeds. The protocol also follows
earlier storage and terminal-inventory sensitivities, so it is a new prospective
test of an informed hypothesis, not an untouched original research question.
It does not introduce starvation, mortality, reproduction, capability loss or
new shocks. Those would require different physics and a separate protocol.

## Fixed physics, controls and interventions

Use `commons-v3-physical-v1` and the unchanged audited `ForagerPolicy` in
`policies_navigation_v1.py`. The reference configuration is
`Config(initial_patch_stock=40.0, need=1.2)`, with only `inventory_capacity`
varied as specified below. Preserve the 12×12 grid, 24 individuals, 16 sites,
radius-one sensing, site capacity 40, initial inventory 2, renewal rate 0.24,
recovery 0.02, keyed weather amplitude 0.1, logistic renewal, proportional
contention, maximum harvest 4, movement cost 0.02 and harvest cost 0.02.
All other configuration fields remain unchanged. Every episode lasts **256
ticks**; the final quarter is zero-based action indices **192–255**, inclusive,
corresponding to the recorder's post-step trajectory ticks **193–256**.

| Mandatory control | Reserve ticks | Voluntary stock floor | Routing |
| --- | ---: | ---: | --- |
| `fixed_floor` | 2 | 0.5 | `net_yield` |
| `selected` | 4 | 0.5 | `nearest` |

Bind the existing selected-policy record SHA-256
`4665d982a65e08ac65dc0244b341a0cf519da2f417964b65414d4e271369cadc`.
The physical engine SHA-256 is
`3086b3f10c6e8b2cfbfc107caeb72c6598d464f7e0537971bd1d9264833fa9ac`;
the forager source SHA-256 is
`e1260830e106acdb72423cbab069d291a97e7d0d1e1173792fd0a5664082d8b4`.
The executable freeze must verify these bindings and close their imports.
Neither control may be dropped or selected again using these results.

An aggressive individual uses the same controller parameters and route mode
with `aggressive=True`: its inventory target becomes capacity and its voluntary
stock floor becomes zero. Navigation, extraction and subsequent ecological
paths can all change. This is a **whole-policy substitution**, not an isolated
extraction intervention, optimization of a private response or equilibrium
calculation. All decisions use the existing legal local observation contract.
Peer composition and evaluator diagnostics do not enter policy observations.

Keep the engine's `terminal_wealth_weight=0.05` field unchanged. The primary
payoff is measured consumption, algebraically the existing weight-zero score.
No coefficient is fitted or retuned. Terminal inventory is reported in physical
units as a diagnostic; it cannot count toward any primary incentive endpoint.

## Complete factorial panel and seed identities

Cross storage capacities **8, 16, 32 and 80** with every integer aggressive-peer
count **k = 0, 1, …, 23**, both controls and seeds **91001–91032**. These
capacities retain the earlier reference/stress anchors and add two fixed
interior levels; they are not chosen from this panel's outcomes. No adaptive
refinement of capacities or peer counts is permitted.

The initial reservation scan found no 91001–91032 seed-field collision in 57
available registry/manifest/summary JSON files containing 180 distinct seed
values, including all six v3 development/qualification designs. Textual checks
of the available protocols and executable registries found no reservation in
this range. The review's reserved 90001–90008 range is disjoint. Repeat the
registry check and save its exact file inventory and hashes at executable
freeze; an intervening collision must be resolved in a new protocol version
before any episode, never by silently replacing an observed seed.

Use the zero-based index `j` in the ascending 32-seed list. The focal identity
is `(7 * j) % 24`. This visits all 24 identities before repeating eight; it
does not create an independent identity sample within each seed. Order the
remaining identities by ascending SHA-256 hexadecimal digest of the exact
UTF-8 string

```text
commons-v3-tipping-peer-v1|<decimal seed>|<decimal agent_id>
```

with the integer identity as the final tie break. The first k identities in
that order are aggressive peers. Keep this nested order and the focal identity
fixed across capacities, controls and branches. It depends on no realized
location, inventory, outcome or policy output.

For each seed, capacity, control and k, execute a focal-restrained branch R
and a focal-aggressive branch A. The branches begin from identical physical
states and fresh identical controller memories; only the focal policy differs.
Their peers have identical assignments and they share event-keyed weather.
The aggressive-peer fraction is **k/23**. The full-population fractions are
**k/24** in R and **(k+1)/24** in A. Retain both denominators in exported data.

There are **128 physical seed/capacity configurations**, **192 paired
control/capacity/peer conditions**, **384 branch conditions** and **12,288
episodes**: `32 × 4 × 2 × 24 × 2`. This is **3,145,728 physical ticks** and
**75,497,472 individual decisions**, excluding replay. The independent sampling
units are the **32 environmental seeds**, reused across the whole factorial
panel. There are zero experimental model calls, evolutionary runs and new
numerical policy-selection runs. The episode count is not a replicate count.

## Payoffs and simultaneous interval family

For seed s, capacity B, control c and peer count k, let `C_R` and `C_A` be
the focal cumulative consumption divided by `256 × 1.2` in the two matched
branches. Define the primary focal gain `D(B,c,k,s) = C_A - C_R`. Define
`D_late` identically using only the final quarter and denominator `64 × 1.2`.
Positive gain favors the aggressive variant; negative gain favors restraint.

For each seed/capacity/control, also compute:

| Endpoint | Definition |
| --- | --- |
| `V` | All-restrained population consumption / `(24 × 256 × 1.2)` |
| `V_late` | All-restrained final-quarter consumption / `(24 × 64 × 1.2)` |
| `L` | All-restrained minus all-aggressive population consumption, using the same full-horizon denominator |
| `L_late` | The same population loss with the final-quarter denominator |

The all-restrained episode is `(k=0, R)`; the all-aggressive episode is
`(k=23, A)`. Reuse those recorded arms without adding duplicate episodes.
Loss endpoints are paired within seed before any standard error is computed.

Freeze a **416-interval** family at family alpha **0.05**:

- 384 focal gain intervals: `4 capacities × 2 controls × 24 k × 2 windows`.
- 16 all-restrained consumption intervals: `4 × 2 × 2 windows`.
- 16 collective consumption-loss intervals: `4 × 2 × 2 windows`.

Use Student-t intervals over 32 seed values with **31 degrees of freedom**,
`mean ± critical × sample_standard_deviation / sqrt(32)`. The two-sided
Bonferroni critical value is **4.3960645817488**, computed before execution
using SciPy 1.18.1 as `t.ppf(1 - 0.05/(2*416), 31)`. Ordinary descriptive 95%
intervals use **2.039513446396408**, from `t.ppf(0.975, 31)`. Store these
literals in the future executable registry; runtime quantile calculation
cannot change a verdict. This family is separate from the earlier frozen
194-interval qualification family and cannot retroactively alter it.

Coverage is approximate and depends on the seed-level sampling distribution.
Agents, ticks, controls, capacities and peer counts are not independent
replicates. Zero sample variance yields a zero-width interval, not a universal
invariance claim. Preserve every seed value, sample spread and sign count.
Use exact numerical comparisons without a threshold-changing tolerance.

## Signs, material effects and crossover reporting

For each full-horizon and late focal interval `[lower, upper]`, report both
the sign status and the material-effect status:

| Status | Predeclared rule |
| --- | --- |
| Resolved aggression advantage | `lower > 0` |
| Resolved restraint advantage | `upper < 0` |
| Sign unresolved | Neither strict sign rule holds, including intervals touching zero |
| Material aggression advantage | `lower >= 0.01` |
| Material restraint advantage | `upper <= -0.01` |
| Resolved negligible effect at the 1%-of-need scale | `lower > -0.01` and `upper < 0.01` |
| Material magnitude unresolved | None of the three preceding material rules holds |

A negligible effect can have a resolved sign. Failure to resolve a sign does
not prove indifference. Also report the lower-bound gate at **+0.01** as
pass when `lower >= 0.01`, fail when `upper < 0.01`, otherwise unresolved.
All-restrained adequacy uses **0.95** for both V endpoints; collective material
harm uses **0.05** for both L endpoints, under the same pass/fail/unresolved
rule. Adequate consumption here is not a replacement ecological qualification:
the full earlier ecological gate also concerns stock and depletion.

For every capacity and control, publish all 24 focal intervals in both windows.
List the complete sets of resolved positive, negative, negligible and unresolved
counts, every neighboring reversal, and the smallest k with a resolved material
aggression advantage if one exists. Label that smallest count as a *first
resolved count*, not an estimated unique tipping point. If some smaller counts
are unresolved, say so explicitly. Do not interpolate between k values, fit a
monotone curve, smooth away reversals or collapse an unresolved band to a point.
Capacity is also not assumed to have a monotone effect.

A single sign boundary K, with **1 <= K <= 23**, may be reported only if
**every** sampled k below K
has `upper < 0` and **every** sampled k at or above K has `lower > 0` in the
specified window. Report K as the discrete interval `[(K-1)/23, K/23]`, and
state that the claim concerns the tested policy menu and integer compositions.
If this conjunction fails, retain the full set-valued result. A shared boundary
claim must hold for both controls and both windows; report their separate
results even if the conjunction passes. No boundary is a valid outcome.

## Interpretation and the next scientific stage

Classify the observed policy menu separately for each capacity/control/window,
then report whether both controls and both windows agree. These descriptors
can overlap when a resolved sign has negligible magnitude; retain both labels:

- An **assurance-compatible sign pattern** requires a resolved restraint
  advantage at k=0, a resolved aggression advantage at k=23 and a strictly
  positive simultaneous lower bound for all-restrained versus all-aggressive
  population consumption loss (`L.lower > 0`, or `L_late.lower > 0` in the
  late window). Report
  whether the stricter adequacy and material-harm gates also pass.
- **Near indifference at low aggression with a high-aggression advantage**
  requires a resolved negligible focal effect at k=0 and a resolved aggression
  advantage at k=23. This does not establish the strict assurance pattern.
- A **material unilateral-temptation and collective-harm pattern** requires
  `D(k=0)` to pass +0.01, L to pass +0.05 and V to pass 0.95 in the specified
  window. A sustained, both-control version requires these gates in both
  windows and both controls at the same capacity. Report all intermediate k
  values even when these endpoint gates pass.
- Other, conflicting and unresolved patterns remain named as such. A positive
  reference result for one controller cannot replace the other controller.

These are operational patterns among two supplied policies in a finite-horizon,
heterogeneous 24-agent setting. They do not prove a symmetric two-player payoff
matrix, Nash equilibria, private optimality, evolutionary stability or dominance
over untested policies. In broad usage an assurance problem can itself be a
social dilemma. The narrower unsupported claim to avoid is a robust,
consumption-based temptation to defect from otherwise successful restraint.
Near-zero low-aggression gains plus positive high-aggression gains alone do not
establish a strict stag hunt. Inventory-sensitive weight-0.05 gains cannot
substitute for the consumption criteria in this protocol.

The framing follows the evidence. Stage 2 remains the next scientific priority:
optional institutions among mobile individuals, with founding, refusal, entry,
exit, amendment, replacement and dissolution, materially paid local enforcement
and no supranational government. Institutions may coordinate expectations,
restrain appropriation, fail or remain absent; the eventual comparison must
match the observed incentive problem and record outsider costs. A failed
temptation gate is not a reason to manufacture a different utility weight or
delay the research indefinitely through new reporting layers. This protocol
introduces no institutions and authorizes no model-driven campaign.

## Recording and execution requirements

The future runner must save every branch's individual consumption, shortfall,
inventory, movement/extraction/message costs, positions, known-site counts,
ecological stock, renewal and depletion trajectories. Retain whole-population,
focal, unchanged-peer and policy-cohort summaries. Report unchanged-peer
consumption effects for every k, while keeping their descriptive intervals
outside the 416-interval family. Terminal inventories, stock depletion and
access diagnostics explain results; none can rescue a failed consumption gate.

Use only audited built-in policies. Preserve the existing material-residual
relative tolerance 1e-9, maximum per-tick extraction waste 1e-9 and known-return
affordability checks. Validate pairing, identities, factorial counts, interval
families and absent/duplicate-case rejection before execution. Exact replay and
aggregate reconstruction must preserve the source and input bindings.
Interrupted runs verify and preserve completed cases; scientific failure
cannot trigger retries. Engineering failures preserve the bank and require a
separately versioned repair. Do not add seeds after inspecting results.

The new bank will use separate evidence and archive identities. Its result
report must retain all endpoints and the full 0–23 surface, with recorded-data
figures in Chromatic Field v1 after the framing decision. Preserve SVG, PDF and
PNG exports, captions and source/output hashes, inspect rendered images, and
verify public restoration when publishing raw evidence. This prospective
contract does not request additional ecology-bank publication, figures or audit
layers while the review's framing decision is pending.
