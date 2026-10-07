# Commons v3 physical foundation: development protocol

This is an exploratory engineering and ecological development panel, not the
disjoint qualification bank in [Stage 1](commons-v3-plan.md). Its design is
recorded before panel execution. It makes no claim of institutional emergence,
swarm intelligence, evolutionary superiority or a qualified social dilemma.
All agents initially have no political membership; no institutions exist yet.
No experimental model calls or evolutionary searches are authorized here.

## Physical contract

The separate `swarm_societies/commons_v3/` engine uses a bounded 12×12 grid,
24 individuals and 16 renewable sites. Individuals sense within Manhattan
distance one; extraction requires occupying a site's cell. Physical location
is not political membership or jurisdiction. Public action affordances include
material costs and legal moves; observations exclude the environment seed,
remote state, other agents' inventories, renewal coefficients and future weather.

Every tick commits all actions against the same initial state. Resolution is
movement, local messages (recipient-ID order), transfers, harvesting, storage
overflow, consumption, then renewal. Movement, messages and outgoing transfers
spend only the sender's remaining initial inventory; neither incoming transfers
nor same-tick harvest can fund them. Transfers themselves have no extra fee.
Transfers and
messages require visibility at commitment and radius-one reach after movement.
Messages have bounded UTF-8 payloads, material costs, sender provenance and
one-tick delay. Costs charge payload bytes; envelope metadata is not charged.
Harvest requests face physical rate and resource limits. The primary contention
rule shares insufficient stock proportionally to requests; a keyed random
priority variant is a sensitivity. No political quota is enforced by physics.
An individual may reserve inventory, reducing current consumption and recording
the resulting unmet need, to preserve resources for later actions.

Logistic renewal uses post-extraction stock `s`:

```text
potential_growth = weather * (renewal_rate * s * (1 - s / capacity) + recovery)
realized_growth = min(capacity - s, potential_growth)
```

Weather lies within ±10% of one and is independently keyed by environment seed,
tick and site, so another action or message cannot shift its random stream.
The additive control substitutes `renewal_rate * capacity / 4` for the logistic
term. It matches potential renewal at half capacity, not realized resource
budgets along different trajectories. The recovery coefficient is 0.02
units/site/tick before weather scaling and remains part of the explicit
ecological inflow in the ledger. Carrying and ecological
capacity overflow, extraction costs, movement and messaging costs are recorded.

Default development capacity is 40/site, starting stock is 40/site, starting
individual inventory is 2, carrying capacity is 80, maximum extraction is
4/individual/tick, movement costs 0.02 and gross extraction costs 0.02 per unit.
These are development choices, not accepted calibration settings. Need and
renewal vary below. Initial reserves alone pay for fewer than three ticks;
initial ecological stock is separately reported and can subsidize early yield.
No mortality, reproduction or survival claim is implemented in this version.

Sites occupy the centers of evenly spaced grid subdivisions. In the default
geometry their coordinates are the Cartesian product of `{1,4,7,10}`. Every
site has one on-site starting slot; eight additional slots lie one cell east
of the checkerboard subset of sites. A seed-keyed permutation assigns individual
IDs to these slots. The slots are fixed across paired conditions. This is a
controlled initial placement, not a claim of naturally occurring settlement.

## Fixed local policies and paired interventions

Both policies use the same local navigation, tie and exploration rules and
retain an explicit travel reserve: the larger of four movement costs and the
cost of returning to a known site plus one step, capped by carrying capacity.
Memory stores only visited cells and coordinates of previously observed sites.
Scouting favors less-visited neighboring cells, with deterministic ID/tick ties,
and refuses moves that knowingly spend the fuel required to return to a known
site. A site is exploited when its estimated net return is at least half the
per-tick need; otherwise the policy scouts, even if some harvest is available.
This makes the greedy condition a harvesting/navigation heuristic, not an
optimal controller or the completed strong-baseline gate. Greedy harvests attainable visible
resources, respecting its carrying capacity and physical costs. Restraint uses
only stock above half a visible site's capacity, divided by the observed
co-located headcount, including self. Neither receives hidden laws or a global
map. Movement and harvesting may be combined by the engine, but these policies
move without harvesting on the same tick; arrivals therefore do not exploit an
outdated headcount. Source snapshots freeze all tie and exploration rules.

Four population conditions share each initial state and weather keys:

1. All use restraint.
2. All use greedy harvesting.
3. One focal agent switches from restraint to greedy; every peer is unchanged.
4. Even-numbered IDs use greedy; odd-numbered IDs use restraint.

Focal identities are 0, 6, 12 and 18 in the four respective seed rows. They are
varied with seeds, not independently crossed replicates. The mixed condition
reports both policy subpopulations. Individual IDs are not society labels.
A policy replacement changes its navigation and extraction choices together;
it does not isolate one mechanism in that policy.

## Complete development panel

The base grid crosses renewal rates `{0.12, 0.24, 0.36}` and consumption needs
`{0.8, 1.2, 1.6}`, using seeds `{61001, 61002, 61003, 61004}` and 256 ticks.
All nine cells and every outcome are retained. The global maximum logistic
production before costs/weather/recovery is a supply diagnostic, not a bound
on attainable consumption under local access.

At the preselected reference cell `rate=0.24, need=1.2`, five separately reported
sensitivities repeat all four conditions and seeds:

- 512 ticks;
- keyed random priority contention;
- initial ecological stock at 55% of capacity;
- additive renewal matched at half capacity;
- carrying capacity 8 instead of 80.

This is 36 base configurations plus 20 sensitivity configurations, each with
four paired population conditions: **224 episodes**, not 224 independent
evolutionary replications. Seeds reused across parameters and sensitivities
produce dependent comparisons. There are **zero evolutionary runs**.

## Outcomes and acceptance

Report consumption and unmet need per individual-tick, late-quarter consumption,
terminal reserves, ecological stocks, depletion duration, cumulative resource
costs, waste, movement and maximum ledger residual.
Depletion means end-tick stock below 10% of capacity; its reported fraction is
over all site-ticks. This measures low stock; under additive renewal low stock
alone does not imply reduced productive capacity. The late window is the final
quarter of the episode.
Compute private utility
from saved primitives at terminal-wealth weights 0, 0.05 and 0.2. Focal and
other-agent contrasts are paired within configurations; aggregate consumption
under widespread greedy play is compared with homogeneous restraint. Four seeds
support descriptive development diagnostics, not a resolved qualification claim.

Engineering acceptance requires exact tiny-world accounting checks, local
observation and action invariants, deterministic replay, physical-state checkpoint continuation,
and trajectory residuals below `1e-9 * max(1, cumulative material flow)`.
Every episode is checked; a failure is recorded and stops completion rather
than disappearing from denominators. A failed bank cannot later be marked
complete; preserve it and use a new output directory after any repair.
The checkpoint check restores physical state and applies the same subsequent
committed actions; it does not restore private policy memory or establish an
autonomous agent-process restart. Full development trajectories are recorded
as compact scalar rows; a preselected reference seed retains spatial frames.
Output and source hashes connect numerical records to figures.

There is no favorable-outcome acceptance rule. In particular, restraint meeting
everyone's need can leave no room for a consumption-only unilateral gain;
terminal inventory gains may shrink with horizon. Sustainable restraint plus
greedy depletion, without profitable individual deviation, establishes ecological
sensitivity only. Do not tune the wealth coefficient to manufacture temptation.
Any later qualification panel requires a frozen design, separate seeds, stronger
baselines and the remaining Stage 1 interventions. Institutions, their lifecycle
and costed enforcement remain Stage 2 work.
