# Purposeful local navigation and finite numerical baselines: protocol v1

This stage follows the completed need-targeted development comparison. It
keeps the physical engine and all earlier evidence frozen. The purpose is to
test stronger local foraging and a finite, reproducible numerical baseline
before ecological or incentive qualification. There are no institutions,
political memberships, model-generation calls or evolutionary campaigns.
No favorable result is required to finish the study.

## Legal information and local controllers

The controller sees exactly the physical engine's local observation packet:
its own resources and action costs, grid boundaries and sensing radius, visible
sites and co-located headcounts, nearby identities/positions and received
messages. It receives no global layout, remote stocks, seed, renewal rate,
future weather or peer inventories. It may remember previously observed site
coordinates, stock/headcount/time, its own visits and the sensing footprints
actually observed. Observing an empty cell is legal information; inferring an
unseen site from the initializer's regular spacing is not.

The new forager follows purposeful routes to remembered opportunities and
unobserved sensing frontiers, revisits stale information, and uses the legal
move-and-harvest action at a visible or previously observed destination site,
using its latest available observation. In this radius-one panel, a one-step
destination is visible; with narrower sensing, a stale request may yield less
or nothing.
Remembered stock is stale evidence, not a current stock observation or an
estimate supplied by the evaluator. The routing rule and all its constants
are fixed in the source freeze before the numerical sweep. Movement is paid
from initial inventory, and only affordable one-cell steps are issued.
Protected travel reserves are paid through foregone consumption; no free fuel
or ecological resources are introduced. Consumption buffers remain available
to meet current need.

Normal desired inventory is `min(capacity, (1 + reserve_ticks) * need + fuel)`.
The need-targeted gross request converts the desired net inventory deficit by
`1 - harvest_cost_per_unit`, respecting actual pre-consumption storage and
the physical extraction limit. A positive stock-floor parameter limits the
request to observed stock above that fraction of capacity, divided by the
inferred co-located headcount. With floor zero, the actual request is capped
by demand, stock, rate and storage without headcount division. Service estimates
used for routing account for headcount at every floor value. The positive
floor is a voluntary individual request rule; simultaneous unobserved arrivals
can breach the aggregate floor, so it is not an enforced ecological quota.
An aggressive variant uses the same route parameters but requests stock up to
physical rate and storage limits, without the target or stock floor. Its
realized navigation may differ because its inventory and ecological path
differ. Aggressive replacements are therefore whole-policy interventions.

The deterministic routing details are:

- Estimate one-tick net service from the last observed stock above the policy
  floor, divided by the last headcount excluding the observer if present and
  including its prospective arrival; cap gross service at extraction rate.
  Discount remembered service for route ranking by `1 / (1 + age / 8)`.
  This is an explicit staleness heuristic, not a fitted renewal forecast.
- Stay and request harvest if the current site's service is positive and
  covers one tick of need. Otherwise, a fully provisioned agent without an
  active route waits; an under-yielding location can trigger travel while
  food remains available.
- First consider remembered sites with service above the current
  site's service. `nearest` orders by distance then higher service;
  `net_yield` orders by `(service - movement_cost * distance) / (distance + 1)`
  then distance. This ranking is a heuristic, not a guaranteed net return.
  On a known site, a promising trip whose fuel fits physical capacity may be
  planned before it is funded: wait and harvest while protecting only the
  actual planned trip fuel until movement is affordable. The resulting
  foregone consumption is recorded; this avoids consuming every small harvest
  while permanently being unable to pay for a known productive route.
- Otherwise choose affordable sensing frontiers among observed cells and their
  immediate neighbors, maximizing newly observable cells per travel step;
  break ties by distance, visits and an agent-specific deterministic hash.
  If there are no such frontiers, revisit an affordable site unobserved for at
  least eight ticks, oldest first, or return to the nearest known site when
  off-site. Do not bounce between freshly inspected empty sites solely to
  execute a return action.
- Persist the destination and follow Manhattan distance-reducing safe steps,
  preferring sensing novelty and fewer visits. Reassess when reaching a goal,
  inspecting a stale goal, learning that it is no better than the current site,
  exhausting its sensing novelty, or losing the full route budget while
  off-site. A still-unfunded planned trip on a known site can retain its fuel
  saving action. Agent/cell
  hash tie-breaking is fixed across ticks so equal routes do not alternate
  solely because the tick changes.
- Protect the larger of the four-step fuel buffer, the nearest-known-site
  return distance plus one, and any committed route's remaining distance plus
  its known-site return distance plus one. Use the v2 numerical margin and
  capacity cap. Route entry and every physical step must be affordable; an
  immediately adjacent known site requires at least its actual movement cost.

The rule need not discover every site or outperform the legacy policy in every
case. It retains stale-stock uncertainty and simultaneous-arrival contention.
The fixed eight-tick constants are not adjusted from panel outcomes.

## Predeclared numerical search

Enumerate all 18 combinations, without adaptive proposals:

| Parameter | Fixed candidate values |
| --- | --- |
| Desired extra consumption-buffer ticks | 0, 2, 4 |
| Voluntary stock floor / site capacity | 0, 0.25, 0.5 |
| Routing mode | `nearest`, `net_yield` |

Every candidate runs as a homogeneous population on nine rate/need cells:
rates 0.12/0.24/0.36 crossed with needs 0.8/1.2/1.6. Use tuning seeds
**62001 and 62002**, at 256 ticks, with the unchanged primary physical
configuration (24 agents, 16 sites, capacity 80, initial site stock 40).
This is **18 tuning environments × 18 candidates = 324 episodes**, not 324
independent search runs. All candidates, outcomes and failures remain visible.

Select once by highest equally weighted mean consumption divided by declared
need across these 18 environments. Break exact ties by higher mean
final-quarter consumption divided by need, then lexicographically smaller
candidate ID. Preserve every candidate's score and complete case records.
There is no utility-weight tuning, no evaluation-driven selection and no
score tolerance that turns a lower objective into an improvement. This is a
**consumption-selected homogeneous-population baseline** within a supplied
finite controller family, not a private optimum, equilibrium, model-driven
evolution or globally optimal planner. The selection objective can sacrifice
particular conditions; report those losses rather than change the objective.

## Separate evaluation panel

Predeclare seeds **63001–63004**, disjoint from tuning and all three previous
development banks. They cross the same nine physical grid cells plus the
five existing reference sensitivities: 512 ticks, keyed priority, initial
site stock 22, additive renewal and carrying capacity 8. The reference is
rate 0.24, need 1.2, 256 ticks. Focal identities are 0, 6, 12 and 18 by seed.
This gives **56 configurations**. All settings except the named sensitivity
are unchanged; utility weights remain 0, 0.05 and 0.2.

Run six conditions on every configuration:

| Condition | Policy composition |
| --- | --- |
| `legacy_need2` | Frozen need-targeted-v1 policy with two ticks of buffer |
| `fixed_forager` | New forager: buffer 2, floor 0, `net_yield` |
| `fixed_floor` | New forager: buffer 2, floor 0.5, `net_yield` |
| `selected` | The single candidate selected on the completed tuning bank |
| `focal_aggressive_selected` | One aggressive forager replaces the selected focal agent; selected peers remain unchanged |
| `all_aggressive` | Everyone uses the aggressive variant of the selected parameter setting |

If the selected controller matches a fixed anchor, retain both named
conditions and run them as declared; do not count identical controls as
independent evidence. No earlier bank is restarted. The legacy need-2 policy
is evaluated on these new seeds to provide a genuinely paired comparison.
Previous numerical means from other seeds are contextual, not matched effects.

Evaluation contains **336 episodes / 92,160 physical ticks**. Including
tuning gives **660 episodes / 175,104 physical ticks / 4,202,496 individual
decisions**, excluding verification replays. Report numerical candidate
evaluations separately from independent evolutionary runs (zero). Environment
seeds are reused across conditions, cells and sensitivities. Four fresh seed
realizations and small-world engineering tests do not constitute the larger
ecological/incentive qualification gate. Once inspected, these evaluation
outcomes are available for later development and cannot be called untouched
in a subsequent study.

## Outcomes, diagnostics and limits

For every cell retain condition means for population and final-quarter
consumption, unmet need, terminal inventory, ecological stock, movement and
extraction costs, waste and depleted-site-time fraction. Pair selected against
each fixed anchor and the legacy baseline. Pair the focal aggressive condition
against all-selected for focal consumption, inventory, private utility at
every declared weight, peer consumption and whole-world consumption. Compare
all-aggressive with all-selected to measure the population consequence of
widespread substitution. Report all null and adverse outcomes and every fixed
sensitivity.

Record additional evaluator-only access diagnostics: off-site individuals,
individuals with positive tick shortfall ending off-site, stock fraction on
unoccupied sites, and mean number of sites known to each local policy. These
global diagnostics are never exposed to the policy. They help separate local
access failure from loss of total ecological stock; unoccupied stock is not
automatically reachable or sustainably harvestable.

Use four-seed descriptive means and observed min–max paired differences, not
population confidence claims. Do not count agents, ticks or parameter cells
as independent replications. Consumption and shortfall are complementary
outcomes. Weighted terminal inventory remains separate from consumption gains.
No result here establishes institutional usefulness, a full information model,
an optimal controller or a qualified robust dilemma.

## Freezing, staged execution and preservation

Copy and hash the complete executable source/protocol set and save the full
candidate registry, objective, tie rule and both seed lists before tuning.
Finish exact small-world tests for locality, target/cost/capacity arithmetic,
simultaneous movement/extraction, purposeful routes, stale-site revisits,
prospective fuel safety and deterministic replay before that freeze.

Seal the complete tuning bank, then write a selection record binding its
manifest, design, source freeze, selected parameters and evaluation
specification before any evaluation episode runs. Evaluation never changes
the selected candidate. Interrupted runs replay and compare complete records;
completed and failed banks are preserved. An unexpected engineering failure
halts completion and leaves a failure receipt. Do not average surviving cases
or replace an adverse panel with a tuned rerun. A necessary source repair after
outcome inspection requires a new version and preserves the original bank.

Every episode checks accounting, capacity-aware extraction waste and affordable
known-site returns. Conditions share keyed weather within each configuration.
Record reference physical frames and snapshot continuation under identical
future committed actions; policy-memory recovery remains separate. Full
verification reconstructs selection and all aggregates and compares semantic
replays with exact canonical JSON. Any independent accumulation-order
tolerance is diagnostic only and cannot change execution or selection.

Push the verified implementation/design freeze, completed tuning/selection,
and completed evaluation/report as successive checkpoints. New raw evidence
uses a separate versioned public archive with verified download/restoration.
Publish recorded-data Chromatic Field SVG/PDF/PNG figures, complete CSVs,
captions and source/output hashes; inspect the rendered figures. Preserve all
earlier simulators, protocols, evidence and published archive identities.
