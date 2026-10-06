# Costed, institution-selected investment experiments

Version: world-model-experiment-v1. Freeze the protocol, executable design and
source snapshots before running the recorded development or evaluation banks. Preserve all earlier
simulators, learners, studies and evidence. This is numerical parameter learning
in a supplied equation, with zero new evolutionary searches or model-generation
calls.

## Question and operational contrasts

Can a society choose a more useful investment experiment than a fixed schedule
or a random schedule at the same resource and communication budget? Separate
the value of posterior updating from the consequences of the investment itself.
This first control chooses a complete schedule once from the current belief;
it does not adapt that schedule to observations collected during the experiment.

Each physical experiment is followed by the same allocation planner with either
the updated institutional posterior or its frozen pre-experiment posterior.
Both receive the identical current legal state and latest delivered home
measurement. This is a **parameter-update ablation**, not withholding all new
information: the latest state remains visible to both planners.

The primary contrast is the active-minus-random difference in update value:

```
(utility(active, updated) - utility(active, frozen))
  - (utility(random, updated) - utility(random, frozen))
```

The total updated-policy utility difference decomposes exactly into this term
plus the active-minus-random difference under frozen coefficients. The latter
is an operational material-path comparison under a specified controller, not
an identification of every physical mechanism. Update value can interact with
the state created by an experiment; its cross-schedule contrast does not hold
physical states equal. Consumption, terminal wealth, investment and harm remain
separate endpoints.

## World, escrow and timing

Retain three societies, four members per society, initial wealth 4, patch stock
10, capacity 30, consumption need .85, no drought and home-only full-effort
harvesting. Keep supplied rho=.96, eta=.125, h=2.4 and c=.08. Hidden shared-law
r/b/g ranges remain [2.4,6.8], [.7,2.7] and [.05,.7]; public prior bounds remain
[2,8], [.5,3] and [0,.8]. Use new versioned seeds.

Warmup lasts eight ticks, 0–7. The preceding staggered investment schedule
applies through tick 6. On tick 7 every institution sets public investment zero,
tax .6 and reserve fraction 1. Its subsequent legally observed treasury is the
experiment escrow B. This is existing money withheld from redistribution, not
a new resource endowment.

The probe window spans ticks 8–15. All institutions set tax zero throughout this
window; there are no contributions, aid, raids or defense expenditure. Thus the
focal institution's available budget contains only its known escrow. Other
institutions redistribute their escrow on tick 8 and make no investment during
the window. The focal institution chooses one of three cost-matched schedules:

| Schedule | Investment at tick 8 | Investment at tick 12 | Retained escrow |
| --- | --- | --- | --- |
| Early | B | 0 | Zero after tick 8 |
| Late | 0 | B | All until tick 12 |
| Split | B/2 | B/2 | Half until tick 12 |

At unspent intermediate ticks reserve all remaining escrow. Fractions of the
remaining treasury implement each tranche through the existing engine. Verify
actual receipts: all three schedules must invest the same B, end with zero
escrow and use the same reporting opportunities. Equal invested resources do
not imply identical consumption or opportunity costs.

A fourth physical path redistributes B at tick 8 and makes no probe investment.
It is an **opportunity-cost baseline outside the matched-investment comparison**.
It receives the same observation and communication schedule.

Investment follows current growth and harvest. Early investment can affect
seven observed renewals in the eight-tick window; investment at tick 12 can
affect three. At tick 16 start, deliver the tick-15 report before requesting
the subsequent allocation. Current tick-16 growth remains unavailable. The
continuation lasts 32 ticks, including tick 16, with the prior three-action
allocation menu {0,.5,1}. Later investment is zero. Tax returns to .6, and
remaining funds are redistributed equally.

## Beliefs, communication and acquisition score

Use the existing redundant-report runtime, with one canonical noisy measurement
per patch/tick, sigma .05, truthful fixed routing, bounded serialized frames,
one-tick per-hop delays and owner-specific deduplication. All fifteen private
learners retain 1,024 particles and four rejuvenation sweeps. The licensed
external infrastructure sensor remains available. Communication bytes and
learning updates are recorded; communication and compute are not given a new
material price in this control.

Before any probe path runs, commit the legal pre-probe observation, coefficient
samples, scores for all three schedules, active selection, fixed selection and
random selection. Fixed selects Split. Random selects one schedule uniformly
using an independent precommitted RNG stream. A descriptive uniform-mixture
reference may average all three evaluator outcomes, but must not replace the
declared random choice in the primary contrast.

The active selector uses a separate local forecast, never an engine snapshot,
current growth, hidden coefficients, productivity, future weather or branch
outcomes. It assumes unit productivity, nominal home harvesting, a lagged stock
reconstruction and decay-only external infrastructure. Exact escrow tranches
are applied after forecast renewal and harvest.

Score schedules using a joint Gaussian moment approximation to information
about the coefficients across the eight future home-growth observations.
For each coefficient draw, compute the conditional moments of weather-driven,
capacity-clipped renewal. The covariance across these conditional means is
epistemic disagreement; conditional weather variance plus sensor variance is
the diagonal noise covariance. The score is one half the log determinant of
identity plus noise-standardized disagreement covariance. Propagate a common
nominal stock path for each schedule from its posterior predictive mean.

This score is a deterministic **information proxy**, not exact expected
information gain, calibrated uncertainty or decision value. Its joint covariance
accounts for redundant directions better than summing one-step disagreements,
but its Gaussian and state approximations remain explicit. Use 512 coefficient
draws. Ties follow the declared schedule order. All schedules receive the same
particle sample and legal observation.

## Protected physical paths and downstream choices

Rotate the focal society through all three identities within each arena. Clone
the common pre-probe world and private-learning/transport state for each of four
physical paths. Learn only from that path's legally delivered events. Preserve
the live world, all learner and transport state, policy memories and random
streams. No path's observations may update another path or the live checkpoint.

At each post-probe allocation state, commit all action forecasts before running
the three physical menu branches. Reuse each branch outcome to score updated,
frozen and known-coefficient inputs to the same 512-sample allocation planner.
The known-law reference retains observation and planner approximations and is
not an optimal controller. Branch evaluation performs no further learning.

Utility is probe-window consumption plus continuation consumption plus .2
terminal wealth, divided by four members. Common warmup consumption is excluded.
Also retain continuation-only utility. Do not subtract invested B again:
investment already affects the physical wealth and consumption ledger. Report
actual investment, redistribution, harvest, consumption, shortfall, terminal
wealth, outward harm and other-society outcomes. Opportunity costs are measured
against the redistribution path, not assumed equal from matching B.

Score pre- and post-probe predictions on common independent held-out renewal
queries. Targets never update beliefs or choose experiments. Report learning
scores separately from realized allocation value; improved information-proxy
scores need not improve prediction or utility.

## Development gate and prospective evaluation

Implementation checks include synthetic selector fixtures and a full-budget
numerical smoke execution of the first development case before source freeze.
That smoke's selection, performance and gate outcomes were not inspected; only
successful execution and runtime were checked. Its source copies, design and
case remain under `runs/world-model-experiment-smoke/`, outside gate evidence.
The gate criteria below were specified before that execution and were not
changed. The complete recorded development bank is executed after source freeze.

Development comprises six deliberately designed arenas crossing r={2.4,4.6,6.8}
with b={.7,2.7}, with g=.3 and distinct development seeds. It supplies 18 dependent
focal states and 54 cost-matched physical probe paths, plus 18 redistribution
paths. The gate requires:

- Positive escrow in every focal state, all resource/byte/timing/isolation
  invariants satisfied, and no failed forecast or learner update.
- At least two distinct active schedules across the 18 focal states.
- At least two states selecting a schedule other than fixed Split with a
  predicted score advantage over Split greater than 1e-4 proxy units. This
  tolerance is not a confidence interval.
- At least two cost-matched physical paths where posterior updating changes
  the downstream allocation choice relative to frozen pre-probe coefficients.

No gate requires a positive active-minus-random performance effect. A failed
gate prevents evaluation preparation and is retained as a result. Revisions
require a separately recorded design; final evaluation cases cannot guide them.

If the gate passes, prepare 24 fresh independent law/environment arenas, with
three dependent focal rotations and four probe paths per focal state. This is
288 physical probe paths and 864 physical allocation continuations, sharing
24 warmups. Strategies, beliefs, societies, members and branch outcomes are
dependent observations, not independent evolutionary replications. The six
development arenas are not pooled into evaluation estimates.

Average focal contrasts within each arena, then bootstrap 2,000 paired whole
arenas for 95% percentile intervals using seed 9501. The primary contrast is
defined above. Active-minus-fixed, total utility, redistribution-baseline,
prediction and known-law comparisons are secondary and have no multiplicity
adjustment. Retain null and adverse results.

## Completion, recovery and evidence

Freeze case identities, source hashes, observation permissions, learner and
selector settings, policies, seeds, gate, endpoints and bootstrap before running.
Evaluation preparation independently verifies and copies the passing development
archive. Failed updates, forecasts or invariant checks prevent completion; no
cases are replaced or dropped. Completed studies cannot be overwritten.
Recovery must semantically replay existing complete cases before reusing them.

Archive exact sources, full case checkpoints, observations, coefficient draws,
selection and forecast commitments, action receipts, path/branch outcomes,
learner and transport snapshots, tables, summaries and source/output hashes.
Verification refits and replays complete cases, reconstructs statistics and
recursively checks development provenance. Tests must reject privileged input,
wrong phase or delay, unequal spending, crossed path state, mutation, source
changes and semantic tampering even after checksum rewrites.

Render recorded evidence in Chromatic Field v1, preserving society colors,
condition labels, inspected SVG/PDF/PNG exports, captions and hashes. Keep the
conditional ecological interpretation and the calibration audit's shared
borderline likelihood-CDF departure visible. Useful experimentation would not
by itself establish rule discovery, universal calibration or evolved governance.
