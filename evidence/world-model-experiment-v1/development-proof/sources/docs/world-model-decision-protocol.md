# A fixed-planner allocation control

Version: world-model-decision-v1. Freeze this protocol, executable design and
source snapshots before the evaluation bank. Development is a separate bank;
its results select a consequential task, not an evaluation success threshold.
Earlier simulators, learners, studies and their evidence remain frozen.

## Question and development gate

Does a learned posterior improve one institutional allocation under the same
legal observations and fixed planner, compared with the public prior? Parameter
learning, control and active information acquisition are separate questions.
This study does not choose actions to acquire evidence or discover equations.

Exploratory development used one environment seed and grids of decision timing,
renewal/return coefficients, initial wealth and fixed policies. Its scripts and
records are retained under `runs/decision-development-exploration/`. They are
not independent final-panel evidence. The resulting task retains default
physical constants and initial wealth, uses home-only harvesting, and stops
scheduled investment after a common 32-tick warmup. The existing private-utility
form, consumption plus 0.2 terminal wealth, makes delayed material returns
visible even when consumption is already at its ceiling. Consumption welfare
is reported separately and is never inferred from terminal wealth.

Before preparing evaluation, complete six development arenas crossing
`r={2.4,4.6,6.8}` with `b={0.7,2.7}`, holding `g=0.3`, with distinct development
seeds and role rotations. For each legal state, hold r/g and the observation
fixed while forecasting b=0.7 and b=2.7. The gate requires at least two states
where these forecasts choose opposite extreme actions and both extreme-action
utility gaps exceed `max(0.005, 3 × paired planning MCSE)` per member. Realized
branch values must include at least two states favoring each extreme action by
at least 0.005 over the opposite extreme. At least two known-law choices of full
investment must improve realized utility over redistribution by over 0.005.
The intermediate action remains in every comparison. Save failed gates and all
case rows. If the gate fails, do not prepare this evaluation; report and revise
development in a separately recorded design.

## World, information and timing

Use 24 fresh independent shared-law arenas, three societies and four members
per society. The stationary law ranges remain r in [2.4,6.8], b in [0.7,2.7],
and g in [0.05,0.7], sampled independently in a new versioned evaluation seed
namespace. Public priors remain [2,8], [0.5,3] and [0,0.8]. Other supplied
constants are rho=.96, eta=.125, harvest scale h=2.4 and effort cost c=.08.
Initial wealth is 4 per member, initial patch stock 10, capacity 30 and
consumption need .85 per member/tick. Disable drought. The horizon is 64 ticks:
32 common warmup ticks followed by a 32-tick decision window.

Every member harvests its home patch with full effort. During warmup the fixed
institutional public fraction follows the existing staggered eight-tick
0/.3/.8 schedule; role rotations are recorded. Tax is .6, with no defense,
reserve or raids and equal redistribution. From tick 32 onward, public
investment is zero except one focal allocation at tick 32. Rotate the focal
society through all three identities within each arena; these are dependent
interventions on the same warmup, not independent worlds.

Run the existing redundant-report communication condition during warmup:
members 0 and 1 report their common home event, institutions deduplicate and
forward according to the frozen sharing contract. It is chosen because the
planner needs its own lagged patch measurement; it is not selected by posterior
confidence. Keep all fifteen private learners at 1,024 particles/four sweeps.
One canonical Gaussian-noisy growth value (sigma .05) exists per patch/tick.
The licensed mean external infrastructure is retained. The learner receives
neither exact growth, realized coefficients, weather nor evaluation targets.

At tick 32 start, deliver already queued reports before requesting the allocation.
An institution can use its own admitted tick-31 growth event and current legacy
institution payload: treasury, infrastructure after decay and member wealth
rounded as in the frozen engine. Current tick-32 growth measurements remain
unavailable until tick completion. Begin-tick weather and resolution order
have been drawn by the engine but are privileged and never sent to the planner.
Shared and private policy state, pending messages and every RNG state must
survive snapshot/restore. The new stepwise compatibility wrapper must exactly
match the old engine's outputs, receipts, candidate payloads and random draws.

## Fixed approximate planner

The menu is public fractions {0, .5, 1}; other rules remain fixed. Predict
32 ticks including the allocation tick. Investment occurs after that tick's
renewal and harvest, leaving **31 future renewal opportunities** in the window.
Maximize `(window consumption + .2 × terminal member wealth) / 4`.
Ties choose the first maximum in ascending menu order.

All three conditions use exactly the same planner and legal observation:

| Belief input | Coefficient samples |
| --- | --- |
| Prior | The institution's original public-prior particles, without updates |
| Learned | That institution's posterior after legal warmup report arrivals |
| Known-law reference | Repeated true r/b/g under the same observation restrictions |

Draw 512 equally weighted coefficient samples using common sample uniforms;
use a separate, common planning weather/order stream across actions and belief
conditions. The known-law reference is not a full-state oracle or an optimal
controller. Record forecasts, MC uncertainty, predicted budgets and choices
before any evaluator action branch is executed.

The planner is a separate local predictive implementation. It assumes unit
member productivity, home-only harvests and no later investment. Estimate last
tick's terminal stock by clipping its stock-before plus noisy growth to capacity
and subtracting the four nominal harvest capacities. Forecast current renewal
with sampled coefficients and independent weather. Current institutional budget
is forecast treasury plus .6 times predicted harvest, not a realized receipt.
Predict external infrastructure by decaying the previous legal external mean
once for the current tick and on later ticks. This misses any last-tick external
investment and ignores feedback from the focal allocation into neighbours.
These approximations apply identically to learned, prior and known-law inputs.
The planner never receives a simulator snapshot, current exact patch stock,
productivity, hidden RNG state or future weather.

## Protected branches and endpoints

Clone the privileged stepwise world at the allocation boundary and execute all
three menu actions separately for each focal society. Each branch returns to
the fixed zero-investment continuation. The nine physical branches per arena
share environmental randomness and are reused to score the three belief
conditions. Branching must leave the live world, sharing state, model posteriors,
policy memory and random generators unchanged. No branch outcomes feed a live
learner or planner.

Primary: learned minus prior decision-window utility, averaged over the three
focal societies within each arena. Secondary: known-law contrasts, consumption,
shortfall, mean consumption welfare, terminal wealth, investment, outward harm,
other-society welfare, forecast error and allocation regret relative to the
best of the three evaluated actions over this finite window. Forecast budget
error must use predictions committed before current receipts became available.
Report action frequencies and gains separately by society. A consumption
ceiling, zero harm or a failed planner reference remains visible.

Bootstrap 2,000 paired samples of whole arenas, seed 9401, for 95% percentile
intervals. Members, focal rotations, actions, forecasts and planning samples
are nested/dependent units. The 24-arena panel is not a power guarantee and
secondary intervals have no multiplicity adjustment. There are zero new
evolutionary searches and zero model-generation calls. Runtime replays and
development branches are not independent evolutionary replications.

## Completion and verification

Freeze all case identities, sources, policies, law distributions, observation
contract, communication/learner settings, planner menu, seeds, objective and
horizon before evaluation. Record passing development provenance in the final
design. Failures abort completion without replacing arenas or dropping cases;
completed artifacts cannot be overwritten. Retain semantic checks on reused
case files when recovering an incomplete run.

Archive canonical warmup packets, legally available planner observations,
institution priors/posteriors, committed forecasts, all branch outcomes,
live-state hashes, scalar tables, summaries and source/artifact hashes. The
verifier checks hashes and deterministically replays each full case, including
learning and decisions, then reconstructs summaries and contrasts. Tests must
reject privileged/future fields, incorrect delay, cross-owner state, branch
mutation, source changes and changed outcomes even after checksum rewrites.

Publish recorded-data Chromatic Field v1 plots, with society colors retained,
condition markers/labels, captions, source/output hashes and inspected
SVG/PDF/PNG exports. Preserve earlier results. Keep the calibration audit's
borderline likelihood-CDF departure and distinction between conditional
ecological beliefs and a full joint model explicit; useful decisions would not
retroactively certify calibrated uncertainty or structural discovery.
