# Prospective protocol: consumption welfare under uncertain episode timing

This protocol is written before any v2 fresh-case evaluation. Its hash, the
fresh-bank hash, source revisions, exact search banks, and campaign settings
must be recorded in the frozen campaign manifest and referenced run contexts
before search begins. The manifest supplies
the authorized number of independent run pairs and the equal active search
wall-clock budget per run; this document does not select a compute budget.
Changing a scientific rule after inspecting fresh outcomes requires a new
protocol version and a new fresh panel. The original protocol, simulator,
candidate prompt, and first-run evidence remain unchanged.

## Question and comparison

Does allowing institutions to coevolve with member policies improve
consumption-based collective welfare and response to a resource disturbance,
compared with spending the same search budget on member policies under fixed
institutions, when episode length and disturbance timing vary?

Both arms begin with the **same mixed population**: society 0 uses the initial
seed, society 1 the cooperative seed, and society 2 the selfish seed. Each
society has four members carrying its seed member policy and one copy of its
seed institution. Exact source hashes are frozen. Neither arm starts from the
previous experiment's descendants. The fixed-institution arm retains each
society's own initial institution; it does not assign the cooperative
institution to every society.

| Arm | Inherited units eligible for replacement | Search schedule |
| --- | --- | --- |
| Coevolution | Individual member policies and societal institutions | Alternate one member attempt and one institution attempt. |
| Fixed institutions | Individual member policies only | Every replacement attempt targets a member; initial institutions remain fixed. |

The resource physics and initial conditions are otherwise identical. The
versioned `ecology_consumption_v2` simulator removes the direct infrastructure
bonus from welfare and supports a matched disturbance-off intervention.
Infrastructure retains its actual effects on resource regeneration and its
material construction cost. The original simulator is preserved for exact
reproduction of the first experiment.

## Objectives and units

For a member in an episode of length `T`, the selection objective is:

`member objective = (cumulative actual consumption + 0.2 × terminal personal wealth) / T`.

The raw utility and both primitive terms are also retained. Normalizing by
episode length prevents longer cases from receiving an automatic utility
advantage in the search average. Private interests can still diverge from
society welfare through terminal wealth and effects on other members.

For a society with `M` members and a phase of `L` ticks:

`consumption welfare = (phase consumption − 0.5 × phase consumption shortfall) / (M × L)`.

There is **no direct infrastructure term**. Institution selection uses this
quantity over the whole episode. Before- and after-disturbance measurements
use their actual phase lengths. Consumption and shortfall per member-tick are
reported alongside raw material totals, private utility, terminal wealth,
infrastructure, taxes, voluntary contributions, aid, conflict, and effects on
other societies. Pooling remains contributions plus compulsory taxes and is
not treated as exclusively voluntary cooperation.

## Variation, inheritance, and selection

Actual upstream ShinkaEvolve supplies proposal generation and source-parent
sampling. Both arms use the same recorded engine revision, archive settings,
candidate language, initial source, and authorized subscription route. The
campaign manifest records the exact model and inference settings. There is no
paid API, embedding, judging, or auxiliary-inference fallback. Search islands
are archive partitions, not simulated societies.

Both functions must remain valid in every candidate source. Substantive
changes to permitted helpers, branches, loops, memory algorithms, and
allocation rules are allowed. Only the scheduled unit enters the population
after acceptance. In the fixed arm, changes to the candidate's institution
function never replace or modify an executed initial institution. Source
ancestry and the ecological comparison incumbent are recorded separately.

Let `j >= 1` index trusted replacement attempts after the initial evaluation;
recorded invalid attempts count in this index. In the coevolution arm, odd
`j` targets a member and even `j` its society's institution. Set
`slot = floor((j − 1) / 2)`, `society = slot mod 3`, and, for a member update,
`member = floor(slot / 3) mod 4`. In the fixed arm every attempt targets a
member, with `slot = j − 1` and the same society/member mapping. This preserves
the original coevolution schedule while giving the fixed arm more member
opportunities per attempted proposal. Actual opportunity counts are reported;
equal wall-clock budgets do not imply equal numbers of evaluations or tokens.

For each attempt, challenger and incumbent face the same six search scenarios
and exactly the same frozen member and institutional population. A member is
selected on its own normalized utility; an institution is selected on its
society's consumption welfare. Average the six case objectives equally after
normalization. Accept only a mean improvement greater than `1e-9`. Invalid
candidate programs are recorded separately from infrastructure failures, and
neither is a successful replacement. Shinka generation numbers and trusted
replacement-attempt indices remain separate records.

The archive score remains
`1 + (candidate mean − incumbent mean) / max(1, abs(incumbent mean))`.
It is a proposal heuristic under changing partners and opponents, not a
stationary ranking. Accepted replacements change later ecological contexts.
Episode memory resets between rollouts and is never inherited; programs and
their exact lineage hashes persist across generations.

## Search scenarios and observation boundary

Each independent run pair shares a six-case search bank. The horizon and
disturbance-fraction pairs are fixed before search:

`(48, 0.35), (48, 0.65), (60, 0.35), (60, 0.65), (72, 0.35), (72, 0.65)`.

The [scenario adapter](../swarm_societies/consumption_study.py)'s
`make_search_cases(replication_seed)` deterministically permutes their
order for the replication and assigns six independent environment seeds.
The disturbance tick is `floor(horizon × fraction)`: 16/31 for 48 ticks,
21/39 for 60 ticks, and 25/46 for 72 ticks. Horizon values each
occur twice; search fractions 0.35 and 0.65 each occur three times. The middle
fraction 0.50 is reserved for part of the fresh timing distribution.

Environment and schedule random streams use domain-separated SHA-256 seed
derivation in the trusted adapter. Search and fresh environment integers occupy
disjoint numeric namespaces. The exact generated banks, seed-derivation
implementation, replication seeds, and arm-specific search RNG seeds are
frozen in the campaign manifest and scenario files before outcomes are read.
An independent replication receives its own search bank and search RNG
streams; the campaign shares one fixed fresh panel across all arms and
replications. Arms within a run pair share the search bank and starting
population but use distinct search RNG seeds. The preparation script sets
`replication_seed = 2026100500 + replicate_index` for one-based indices and
`search_seed = 1000000 + 2 × replicate_index + arm_index`, where coevolution is arm 0
and fixed institutions arm 1. It deterministically shuffles the arm execution
order separately for each pair. These exact values are recorded in
`campaign.json` and the run contexts.

Candidates retain the original observation keys: elapsed `tick`, local
material observations, and private or shared memory. They receive no selected
episode horizon, future disturbance tick, scenario seed, or fitness value.
Elapsed time and observed changes can inform behavior, but the remaining
episode length is unknown. Proposal feedback includes the arm, target unit, paired
mean objectives, and aggregate normalized outcomes. Exact search scenario seeds,
horizons, and disturbance ticks remain in trusted audit records and are omitted
from proposal feedback; fresh cases are never sent to the mutation model. The evaluator, simulator truth, scenario banks,
measurement code, and fresh cases are outside candidate control. General
knowledge of a variable timing distribution is not proof that a policy has
learned to recognize a disturbance.

## Fresh cases and the matched disturbance intervention

Before search outcomes are inspected, `make_fresh_cases()` constructs twelve
fresh environment/schedule tuples shared by the whole campaign. The horizon list contains
four copies each of 48, 60, and 72 ticks. The disturbance-fraction list contains
four copies each of 0.35, 0.50, and 0.65. These lists are independently shuffled
and then paired. Each boundary uses the same floor rule as search. The actual
tuples, rather than a claim of a complete factorial crossing, define the
protected timing panel.

Cross each tuple with three frozen opponent panels (initial, cooperative,
selfish) and three focal society identities: **108 common disturbed cases per
tested population**. The focal society retains the tested population's member
composition and institution. Nonfocal societies use the designated frozen
panel. The same cases and opponent snapshots are used for the initial
population and all final arms and run pairs. The initial opponent panel uses
the initial mixed population; the cooperative and selfish panels assign their
respective seed programs to every nonfocal society. Fresh measurements never
enter search feedback or candidate selection.

For every case, run an exact matched counterfactual with
`enable_disturbance=False` through the trusted adapter's `disturbance=False`
option. This adds another 108 rollouts, for **216 rollouts per tested
population**. Initial conditions, programs, horizon, environment seed, and
all exogenous random draws remain the same. The scheduled disturbance tick
still defines the comparison's pre/post split, but the exogenous regeneration
reduction is disabled. Endogenous actions and resource states may then diverge
in response to the intervention. This is an implemented model counterfactual,
not an inferred undisturbed trajectory.

Select the final ecological population by the acceptance rule at the search
budget boundary. Do not choose a candidate or earlier checkpoint using fresh
performance. Evaluate this population even if no improvement occurred; absence
of accepted updates is itself recorded. Counterfactuals and environment cases
are not extra evolutionary replications.

## Endpoints, uncertainty, and interpretation

The primary endpoint is mean overall consumption welfare on the 108 disturbed
fresh cases. The primary comparison is the within-replication difference
`coevolution − fixed institutions`, followed by the mean of these paired
run-level differences across the independent run pairs authorized in the
manifest. Report every pair, not only the best search trajectory.

Secondary endpoints include post-disturbance welfare, normalized consumption
shortfall, normalized member utility, private wealth, material cooperation and
conflict, and other societies' welfare. The matched drought effect is
`outcome with drought − outcome without drought` on identical cases. For
welfare, a less negative effect indicates less damage from this modeled
disturbance. Comparing these effects between arms describes a difference in
shock response; a favorable post-minus-pre slope alone is not evidence of
adaptation. Mechanistic claims about recognizing scarcity, online learning,
or cooperative coevolution require supporting program and behavioral evidence.

An **independent evolutionary run** is the replication unit for claims about
the search procedure. Environmental uncertainty is conditional on the evolved
population: resampling, if reported, groups all opponent panels, focal
identities, and disturbance-on/off measurements by their twelve
environment/schedule tuples. These descriptive intervals do not replace
run-level replication. If the authorized campaign contains only one run pair,
label it an exploratory pilot and make no replicated claim about the search
procedure. With multiple pairs, report their paired differences and variation;
small replication counts still limit generalization. Preserve flat and
negative results.

## Budget, failures, and evidence

Each arm receives the same per-run cumulative active search wall-clock budget
from the frozen manifest. Resume accounting and checkpoints preserve consumed
time; a restart does not grant a new budget. Record initialization, inference,
evaluation, failures, and incomplete in-flight work according to the same
supervisor rules in both arms. No silent model switch, substitute search, or
outcome-dependent extension is allowed. Fresh evaluation is separately timed
and does not increase a search budget.

Preserve evaluated and unevaluated proposals, candidate validity, infrastructure
failures, completed generations, scheduled member/institution opportunities,
accepted replacements, source and component hashes, source-parent and
comparison-incumbent links, exact scenario banks, population snapshots,
runtime, token usage where exposed, and resource measurements. Keep search and
fresh evidence distinct. Deterministic replay concerns saved programs and
simulator inputs; identical future subscription-model proposals are not
promised from an RNG seed alone. This document reports no v2 result.
