# Incentive qualification with matched peer populations: protocol v1

Freeze this protocol together with the ecological protocol before either bank
runs. The engine, fixed-floor and previously selected controllers, action costs
and utility weights remain unchanged. There are no institutions, new policy
searches, experimental model calls or evolutionary runs. Ecological outcomes
cannot revise this design. An adverse qualification result is retained in full.

## Separate seeds, fixed populations and scope

Use seeds **65001–65016**, disjoint from ecology 64001–64016 and all earlier
development banks. Cross the same nine rate/need cells with both frozen
controls at 256 ticks. The reference is rate 0.24 and need 1.2. Each seed's
focal identity is `(7 * seed_index) % 24`, using zero-based index in the declared
seed list. Other identities are ordered by SHA-256 of
`commons-v3-qualification-peer-v1|seed|agent_id`, with identity as final tie
break. This evaluator-only order depends on neither observed locations,
inventories, payoffs nor policy outputs. Keep identities fixed across paired
conditions, controls and sensitivities.

For **0, 6, 12, 18 and 23 aggressive peers** among the other 23 individuals,
run two branches: focal restrained and focal aggressive. Aggressive peers are
the first k identities in the nested frozen order. All other peers retain
their assigned control. The two branches begin from the identical physical
state, with identical peer policies and keyed weather; only the focal policy
changes. This yields **10 arms per control**. Peer prevalence is k/23;
the full population has k/24 or (k+1)/24 aggressive individuals depending on
the focal branch. Do not confuse the two denominators.

The aggressive variant retains the control's route mode but removes the
need-target and voluntary floor. Actual inventories, navigation and subsequent
ecological paths can differ. These are **whole-policy substitutions**, not
extraction-only mechanisms, private best responses or equilibrium tests.

At the reference, retain five sensitivities: 512 ticks, carrying capacity 8,
initial site stock 22, keyed-priority contention, and additive renewal. Each
uses the same 16 incentive seeds and both backgrounds, but only the three
endpoint arms: all restrained, one focal aggressive, and all aggressive.
Intermediate-peer effects are qualified only in the primary grid; they are
not simulated or inferred in the sensitivity panels. Utility weights
**0, 0.05 and 0.2** rescore the same trajectories and require no new episodes.

The primary grid has **2,880 episodes**. The five sensitivity panels add
**480 episodes**, for **224 configurations, 3,360 episodes, 884,736 physical
ticks and 21,233,664 individual decisions**. Together with ecology, the total
is **3,648 episodes, 1,032,192 ticks and 24,772,608 decisions**, excluding
replays. Sixteen seeds are reused across conditions and cells; these counts
are not independent replicates or independent search runs.

## Primary material-effect gate

Within each seed, cell and background, compute:

1. Focal private-utility gain from the matched 0-peer restrained→aggressive
   change, divided by need. Utility is `(cumulative consumption + weight ×
   terminal inventory) / horizon`. The primary weight remains **0.05**.
2. All-restrained minus all-aggressive population mean consumption, divided
   by need.
3. The same population consumption loss in the final quarter, divided by need.

Require simultaneous lower confidence bounds of **0.01, 0.05 and 0.05**,
respectively. The late endpoint requires sustained yield harm instead of only
initial liquidation. Depleted stocks are a separate explanatory outcome and
cannot substitute for a failed consumption criterion. Each primary cell passes
only when all three criteria pass for **both backgrounds**. Fail/unresolved
rules and the shared **194-interval** Student-t/Bonferroni family are fixed in
the ecological protocol. The 54 primary intervals cover all nine cells, not
only cells that happen to appear viable.

A primary qualified region requires the **same adjacent pair containing the
reference** to pass ecological criteria and all primary incentive criteria
for both controls. Cells cannot be stitched across favorable backgrounds or
different endpoints. Pair adjacency is horizontal/vertical in the frozen
3×3 grid. An adjacent pair's failure or uncertainty remains visible.

## Robustness, decomposition and adverse outcomes

For the reference plus four logistic sensitivities (long horizon, capacity 8,
lower stock and keyed contention), repeat the three material criteria at every
declared utility weight. The 50 additional simultaneous intervals cover five
panels × two backgrounds × five distinct endpoints: focal utility at three
weights, population mean loss, and population late loss. Population loss is
shared across weight verdicts, not a new observation at each weight.

Report a separate reference-robustness verdict for each weight. The broader
canonical-weight qualification requires both a primary qualified adjacent pair
and all these logistic-reference criteria at **weight 0.05**. A failed or
unresolved sensitivity blocks that broader claim; neither changing the weight
nor dropping a stress test can rescue it. Weight-zero results explicitly test
consumption-only temptation, and need not match the canonical utility verdict.
The capacity-80/256-tick primary verdict remains separately reported.

Additive renewal is a prespecified descriptive negative control, not a route
to passing or failing the logistic robustness conjunction. Report whether
material consumption harm is absent, resolved or uncertain under ordinary
95% descriptive intervals; do not interpret a nonsignificant difference as
proof of no effect. These reference stress tests do not establish robustness
at every other grid cell, population size, geometry or possible deviation.

For every peer prevalence, retain matched focal consumption, utility at all
weights, terminal inventory, unchanged-peer consumption and whole-population
effects. Also report branch cohort means and overall spread trajectories.
Decompose utility changes into consumption and weighted endpoint inventory.
All raw seed values, negative gains, null effects and ecological/access costs
remain in the summaries. Intermediate contrasts and additional endpoints use
descriptive intervals only; they are not extra uncorrected qualification gates.
Intervals are approximate seed-level estimates, not distribution-free proofs.

## Execution and release contract

Both source/design freezes are pushed before either bank executes. The
completed ecology manifest and summary are bound to the incentive completion
record so the combined verdict cannot quietly use a different ecology panel.
The source closure includes the prior navigation selection, frozen policies,
new recorder/analysis, feasibility derivation and both protocols. Candidate
source loading remains unsupported: only the audited built-ins run.

Apply the ecological protocol's accounting, observation, recovery, exact replay,
failure preservation and source-hash requirements. Completed cases are immutable;
scientific failure is not an execution failure and does not trigger retries.
Unexpected engineering failures halt the bank and require a separately versioned
repair. Do not increase seeds after inspecting an interval or tune the physical
world to obtain the proposed dilemma.

Publish both banks and every verdict, with recorded-data figures for the
scarcity/feasibility map, primary paired margins, intermediate-peer response
curves and all reference sensitivities. Preserve SVG, PDF and PNG exports,
captions, source/output hashes and inspected renders. Public archive identities
are new and separate; all earlier data and unsuccessful baselines remain intact.
No result by itself establishes useful governance or authorizes model spending.
