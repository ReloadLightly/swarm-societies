# Experimental design for adaptive local exclusion, version 1

**Status: proposed design, 7 October 2026. No experiment is launched or frozen
by this document.** This translates the [evening steering and implemented
physical extension](commons-v3-exclusion-conventions-v1.md) into a bounded paper
study. Numerical adaptation and the storage/capability extension still require
implementation. All earlier banks, protocols and verdicts remain unchanged.

## 1. The paper's question and contribution

**When do local exclusion conventions emerge, what do they gain members, and
what do they cost outsiders, as storage and scarcity change?**

The proposed contribution is a controlled account of adaptive, locally maintained
exclusion and its distributional consequences. It is not a demonstration that
institutions must improve welfare. The first charter bank motivates this change:
already-restrained members, unreachable harmful outsiders and fixed policy types
could not answer this question. Refining that comparator remains paused.

Separate three claims throughout the experiment and manuscript:

| Question | Evidence required | What does not establish it |
| --- | --- | --- |
| Do exclusion practices arise and persist? | Start without organizations; record voluntary formation, actual costly guarding, turnover and spread under local imitation. | Preassigned membership, a surviving charter or a scripted guard. |
| Does exclusion improve population outcomes? | Paired runs with and without the physical capability, from matched initial conditions. | High current-member consumption. |
| What does an established arrangement gain members and cost others? | Paired continuations from a common state, with cohorts fixed before intervention. | Comparing eventual members with eventual non-members across different runs. |

Use “adaptive local exclusion coalitions” as the precise working model description.
“Convention” denotes a persistent shared behavioral practice under supplied
affiliation recognition, not invented law or a learned moral norm. Do not claim
collective intelligence merely from formation, parameter copying or guard counts.

Position the eventual contribution against existing exclusion and property-rights
models, not as the first explanation of cooperation or ownership. Social-exclusion
models already study costly exclusion and its evolutionary persistence
([Sasaki and Uchida, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3574310/));
coevolutionary models already connect resource economies with property conventions
([Bowles and Choi, 2013](https://doi.org/10.1073/pnas.1212149110)). The proposed
distinction to investigate is mobile physical access with resistance, endogenous
storage consequences and explicitly identified effects on outsiders. A focused
related-work comparison must establish that contribution before claiming novelty.

## 2. Minimum model needed before development

Keep 24 mobile individuals, local sensing, the existing resource accounting,
competent navigation and the optional local institutional lifecycle. Every
individual may change policy parameters; there is no permanently stubborn
outsider cohort. Membership never forces a restrained harvesting policy.

Use the selected nearest-route/buffer-4 navigation routine across all arms,
without a new navigation search. Its spatial memory remains private. The
adaptive resource floor and aggression parameters can change harvesting for
members and outsiders alike. Keep paid communication opportunities equal across
arms. Disable optional route-report traffic in this first study so the new
performance-report channel has a clear bandwidth budget.

For this experiment, propose a minimal affiliation charter: zero bond, dues and
fine, with quota equal to the physical maximum and no automatic voluntary quota
cap in the controller. Retain the existing material founding cost and consent,
refusal, joining and exit procedures. No treasury pooling, monitoring or collateral
sanction is needed to ask the exclusion question. These are new experiment
settings, not modifications to the old charter bank. Protection identity and
its recognition are supplied infrastructure, explicitly acknowledged in the paper.

Retain the implemented exclusion law: positive private guard/resistance costs,
stationary guarding that forgoes harvest, physical reach, resistance and finite
effort divided among outsider harvesters. Start with unit effort and costs of
0.1 per unit. An organization does not own the physical action: individuals can
also occupy alone. Mere claims have no force. Tiny-request feints remain a
known limitation of count-based pressure sharing; this study does not establish
robustness against an unrestricted adversary.

### 2.1 Local numerical adaptation — implement next

Use a five-parameter policy vector with common rules for everyone:

| Parameter | Proposed initial support | Behavioral role |
| --- | --- | --- |
| Resource floor | 0, 0.25, 0.5, 0.75 | Stock retained by restrained extraction decisions. |
| Aggressive-harvest probability | 0, 0.25, 0.5, 0.75, 1 | Chance of switching to the aggressive request rule, including when a member. |
| Guard probability | 0, 0.25, 0.5, 0.75, 1 | Chance of affordable local guarding when a competing harvester is locally possible. |
| Entry threshold | −0.1, 0, 0.1, 0.2 of need per tick | Required local forecast advantage for proposing, endorsing or joining. |
| Exit threshold | −0.1, 0, 0.1, 0.2 of need per tick | Persistent outside-option advantage required to leave. |

Construct 24 initial vectors by seeded, balanced marginal sampling, with random
pairings across parameters and positions. Reuse those exact vectors across arms
and cells for each seed. No initial institution or privileged founding individual.
The supports are prospective defaults, not a fitted optimum or an exhaustive
strategy space. Resistance uses a common affordable unit-effort response to a
recent own exclusion outcome; no policy may inspect opponents' simultaneous
actions. Freeze its exact local trigger along with guard and entry/exit rules.

Copy the whole vector from one local role model; retain the recipient's own
navigation, receipt and membership histories. Begin with **mutation disabled**
in all main arms. This tests selection and spread of standing variation, not
invention of new parameter values. It deliberately narrows the earlier broader
mutation proposal. Mutation/reproduction can follow in another study; neither
is required to replace fixed types with adaptation here.

The selection signal is the individual's recent realized consumption divided
by need. Do not add terminal inventory, a membership bonus or evaluator welfare.
Consumption already reflects material costs; do not subtract them again.
Function/health is measured separately. This bounded imitation rule is not a
claim of private optimality, causal evaluation of a neighbour's strategy, or
selection directly maximizing long-run survival.

Use complete **32-tick parameter-constant epochs**, with delayed reporting.
At each epoch boundary, first choose updates from eligible previously delivered
reports, then act with the new vector for the next 32 ticks. Also send one paid,
bounded report of the just-completed epoch to a keyed, uniformly chosen visible
neighbour. That report is usable at the next epoch boundary, not immediately.
For example, a report of ticks 0–31 is emitted at tick 32, delivered through
the existing message mechanism, and can influence copying at tick 64. Its
transmission cost affects the actual outcomes of epoch 32–63 and is included
when that entire epoch is subsequently scored. Every tick belongs to a score
epoch; no repeated communication phase is systematically omitted.

Reports bind the archived vector that generated the score, which may differ
from the sender's current vector. The receiver compares its own score over
the same dates and copies that reported vector. Require the sender also to be
currently visible at the update, with no current-neighbour payoff lookup.
Only reports for the one scheduled comparison epoch are eligible. Reject
mixed-vector or incomplete epochs; no valid local report means no copying.
Choose uniformly among eligible received reports. This introduces an explicit
information lag; it is not instant imitation of current fitness. Use actual
bytes and affordability. Nominally identical opportunities do not guarantee
identical realized communication costs after trajectories diverge.
The first possible copying opportunity is tick 64; retain delivered reports
across intervening ticks instead of reading only the current physical inbox.

Reports are a new, explicitly supplied **truthful local information channel**.
The transition may project the sender's own receipts, never global ranks or
other agents' hidden inventories. All arms use the same channel, including the
fixed-parameter arm. This studies adaptation under that affordance, not evolved
honesty. Persist receipt dates, parameter epochs and report provenance so full
controller continuation remains reproducible.

For eligible role model j and learner i, propose
`p(copy) = 1 / (1 + exp(-4 × (score_j - score_i)))`.
Payoff-blind copying uses probability 1/2 with the same candidate protocol.
This is the pairwise Fermi comparison family; the intensity and local information
restriction are our supplied design choices.
[Traulsen, Nowak and Pacheco (2006)](https://arxiv.org/abs/q-bio/0609020).
Use keyed randomness for proposals, recipients and acceptance, with synchronous
updates from pre-update reports. No model calls or generated programs.

### 2.2 Endogenous storage value — implement after adaptation

Choose **shortfall-induced capability loss under supply shocks**, keeping fixed
identities and population size. Reproduction and deaths would introduce ancestry,
replacement and changing welfare denominators; defer them for this paper.

Proposed dimensionless capability state starts at `h = 1` and updates after
consumption, with `c = consumption / need`:

```text
h_next = clip(h + 0.02 × c − 0.10 × (1 − c), 0, 1)
physical effectiveness = 0.5 + 0.5 × h
```

Apply opening effectiveness `e_i` to maximum harvesting and both innate and
purchased resistance: `B_i = e_i × (1 + r_i)`. Each guard contributes
`e_g × guard_effort / number_of_opponents` to pressure, and admission remains
`requested_harvest × B_i / (B_i + pressure)`. Charge committed nominal effort,
without a capability discount on its price. Keep movement geometry/cost unchanged to preserve the navigation contract.
The positive capability floor permits recovery when resources become available;
it does not guarantee recovery everywhere. Need and consumption remain physical,
and capability is not a hidden resource account or an extra utility reward.
This requires a separately versioned transition; do not rewrite frozen physics.

Measure both continuous capability and functional person-ticks (`h >= 0.5`).
Call these capability outcomes, not biological survival or mortality. The rates
and cutoff above are developmental assumptions and must be checked before the
single evaluation freeze, without fitting them to institutional success.

A prerequisite fixture starts capacities 8 and 80 with identical initial
resources and a common surplus opportunity, then interrupts supply. Resources
must accumulate through legal harvesting. Show that the resulting stores
actually delay shortfall and preserve subsequent physical capability; include
all waste and costs. No free initial stockpile for the high-capacity agent.
An otherwise identical constant-capability fixture isolates the physical
feedback. These checks establish a mechanism, not its population effect.
Reduced harvesting capability can also mechanically restrain depletion and
improve later ecology. That is an allowed feedback, not evidence that damage
always lowers welfare; the paper must not attribute every storage effect solely
to private buffering.

## 3. Four environmental conditions

Vary storage and renewal productivity, while keeping geometry, resource sites,
population, need and shock process fixed. Reducing patch count would also alter
encounters and navigation, so it is not the primary scarcity manipulation.

| Setting | Proposed value |
| --- | --- |
| Grid / agents / sites | 12 × 12 / 24 / 16 |
| Need / starting private inventory | 1.2 / 2 for every individual, at both capacities |
| Site capacity / initial site stock | 40 / 40 |
| Carrying capacity | 8 or 80 |
| Renewal productivity | 0.24 or 0.20 |
| Recovery / harvest material cost | 0.02 / 0.02 per gross unit |
| Ordinary weather | Existing keyed ±0.1 multiplicative variation |
| Common shock law | One 16-tick zero-renewal interval in each 128-tick block; keyed onset from offsets 0–112, identical across paired treatments. Suppress recovery during the interval too. |
| Horizon / late window | 1,024 ticks / final 256 ticks |

Agents do not receive future shocks or hidden renewal coefficients. Existing
site stock is not deleted when renewal stops. Shock timing and current physical
effects must be distinguished in observations and accounting.

Before shocks, the nominal maximum net renewal/need ratios are about 1.318
and 1.100. Multiplying by the 112/128 productive-time fraction gives about
1.153 and 0.962. These derive from
`sites × (renewal_rate × site_capacity / 4 + recovery) × (1 − harvest_cost)
 / (agents × need)`.
They omit movement, guarding, spatial access and actual stocks. They are nominal
mean ceilings, not achieved feasibility, finite-horizon impossibility certificates
or proof that the first condition is easy. The lower-productivity cell deliberately
approaches a resource limit; universal full need may be unattainable there.

Hold the shock law fixed across these four cells. “Scarce” must never mean the
conditions where a preferred institution happens to win. Four cells support
contrasts across these regimes, not a continuous phase boundary or a universal
storage threshold. A dense phase diagram is outside this paper's initial scope.

## 4. Four comparison arms

| Arm | Exclusion capability | Parameter update | Main purpose |
| --- | --- | --- | --- |
| A — adaptive exclusion | Available | Payoff-biased local copying | Main model. |
| B — adaptive open access | Unavailable | Same payoff-biased copying | Total effect of exclusion availability: A−B. |
| C — neutral copying | Available | Payoff-blind copying, same local reports and opportunities | Selection from payoff differences beyond turnover/drift: A−C. |
| D — fixed parameters | Available | Initial vectors retained | Adaptive parameter change beyond supplied starting diversity: A−D. |

All arms retain local memory, stochastic actions and responsive entry/exit. D
freezes parameters, not movement or the membership history. In B the controller
knows force is unavailable and retains its ordinary harvest option; no ghost
guard fee or artificial lost harvest. B may still form non-enforcing affiliations.
It is a capability ablation, not a cost-matched enforcement intervention. This
does not restart the paused monitoring/collateral mechanism-splitting package.

Use paired initial geometry, traits and keyed environmental events. Share event
keys, not a mutable random stream whose consumption changes with the arm.
Report no-formation and low-contact cases. Do not give A free information or
different initial resources, and do not weaken navigation in its rivals.

## 5. Two experiments with different estimands

### Experiment I: emergence and whole-population consequences

Run all four arms from no organizations in every cell. Separate:

- **Formation:** any voluntarily established multi-member claim.
- **Persistence:** claim durations, occupancy, member turnover and exits.
- **Operational exclusion:** an active claim with at least two members over
  a 32-tick window and paid member guarding on at least eight distinct ticks.
  Record the number of distinct guards and concentration of guarding costs
  separately; a specialized single guard does not invalidate an arrangement.
- **Sustained practice:** at least two consecutive qualifying, nonoverlapping
  32-tick windows in the final 256 ticks. Report prevalence and raw trajectories
  as well as this proposed binary endpoint; the cutoff is not the definition of
  useful governance.
- **Spread:** actual copying events, guard-related trait frequencies, lineage
  transmission and effective update/contact counts. Formation alone does not
  establish payoff-biased spread.

The physical source of any benefit is actual access/resource allocation, not
the presence of a label. Record contest frequency and pressure alongside
extraction. Guarding in the absence of outsiders remains a real cost.

Primary welfare quantities are population consumption/need and functional
person-tick share over all 1,024 ticks. Also report the fixed late window, mean
capability, shortfall distribution, lowest-quartile consumption, stock, waste,
guard/resistance costs, communication/founding costs and affiliation time.
All 24 original identities remain in denominators. Current-member means are
descriptive and cannot identify a benefit of joining.

### Experiment II: member gains and costs exported to outsiders

At **tick 768** of each A run, take a complete state/controller boundary.
Select one active claim with at least two members by a keyed, payoff-blind draw.
Do not require that it is successful or already satisfies the guarding endpoint.
Define `M*` as its current members and `O*` as every other original individual,
**including members of rival claims**. These cohorts never change in the comparison.

Continue for 256 ticks under two versions of the same state:

1. Normal continuation, already contained in A's final 256 ticks.
2. The focal claim's guarding capability is unavailable at its site. Disable
   guarding for its current members, following any recorded legal successor
   of that claim. Other coalitions and their capabilities remain intact.

Affected policies receive the appropriate legal capability restriction and may
adapt, exit or reorganize. Resistance and ordinary harvesting remain available;
disabled guarding incurs no guard cost or harvest sacrifice. This estimates the
**net continuation value of the focal exclusion capability**, including behavioral
responses and saved costs. It does not hold future actions/costs artificially
fixed or identify the isolated pressure formula. New unrelated claims remain
possible; report such substitution rather than hiding it.

For each fixed cohort, compare normal-minus-disabled consumption/need per
agent-tick, capability and shortfall. Report total resource-unit changes too:
the size of the member gain and total outsider loss can differ greatly from
their per-person means. Retain exiters and later joiners in their pre-branch
cohorts. A secondary exposed-outsider cohort may use visits to the focal site
during ticks 704–767; never select it using post-intervention visits or losses.

If no claim is eligible, record that outcome. The branch estimand is unavailable,
not zero, and the run stays in Experiment I. Always report eligibility counts.
If everyone belongs to the selected claim, outsider effects are unavailable.
Do not exclude subsequent dissolution or unfavorable branch results.

This estimates consequences **conditional on an established claim at a fixed
time**. It is neither the effect of deciding to join nor the overall value of
all institutions. A−B provides the separate unconditional population comparison.
Branch membership and eligibility can differ across environmental cells. Their
cross-cell differences describe different established-claim populations, not
the causal effect of storage on a single fixed member cohort. Reserve that
unconditional environmental comparison for Experiment I.

## 6. Development and a single independent evaluation

Reserve development seeds **94001–94004**, with **94005–94008** available for
one recorded revision if needed. Reserve evaluation seeds **95001–95032**.
These ranges are unused in the repository's current source/protocol declarations;
the final executable design must also check every earlier frozen seed list.
Unit fixtures use separate synthetic states and never inspect evaluation episodes.

Use four development seeds first. Make at most one coherent design revision
before using the remaining four; preserve both attempts as development. No
automatic extension until a favorable result, no retuning terminal weight and
no third development seed block under this plan. Revisions need reasons tied to
implementation, information flow or the scientific question, not a demand that
guarding win. Null formation, costly free-riding and worsening outsider outcomes
may be the answer.

| Stage | Independent seeds | Full episodes | Additional 256-tick branches, maximum | Physical ticks, maximum | Individual decisions, maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial development | 4 | 64 | 16 | 69,632 | 1,671,168 |
| Development ceiling, two four-seed passes | 8 | 128 | 32 | 139,264 | 3,342,336 |
| Proposed independent evaluation | 32 | 512 | 128 | 557,056 | 13,369,344 |

Counts exclude engineering tests and replay, and assume an eligible branch in
every A cell. Branches reuse the normal continuation, so it is not executed or
counted twice. Pure provisional calculations inside the force resolver add CPU
work, not physical ticks. Measure throughput in development before scheduling
evaluation; no wall-clock claim or model budget is implied by this table.

Thirty-two evaluation seeds are proposed to give the paper a stronger basis
than the four-seed development panels. This is not a power guarantee, particularly
when claims seldom form. Before the single freeze, assess attainable precision
using development variances and branch eligibility. If the budget or expected
precision does not support the proposed claims, narrow the claims or revise the
prospective plan before evaluation. Never add evaluation seeds after seeing it.

The one complete freeze must bind source versions, the parameter/update rules,
information timing, capability/shock law, conditions, all seeds, branch selection,
outcome definitions and analysis. Push it before any independent episode. An
evaluation implementation failure stops interpretation; repair in a new version,
preserving the failed attempt. No replacements for scientifically adverse seeds.

The development decision is whether the implementation supports an interpretable
adaptive experiment and yields a coherent outcome worth independently estimating,
including a failure regime. A nonzero guard count or one favorable seed is not
decisive. Do not build new archives, receipt systems or audit layers while trying
to find that result. Use existing run records and ordinary tests. Once a decisive
result exists, reuse the existing publication machinery with a separate archive
identity and verified restoration; do not create another infrastructure project.

## 7. Analysis and claim discipline

The independent unit is the **complete simulation seed**, covering environment,
initial traits and behavioral randomness. Cells, agents, time windows, imitation
events and branches are correlated observations within that replicate, not extra
independent runs. Pair arms and branches within seed; resample whole seed blocks
for cross-cell contrasts. Do not infer equilibrium from a 1,024-tick horizon.

Propose a primary family of 20 cell-specific comparisons: four A−B consumption
contrasts, four A−B functional-share contrasts, four A−C sustained-practice
contrasts, and four each of the branch M*/O* consumption contrasts. Use a fixed
Holm correction across that declared family. Unavailable contrasts retain their
slot and cannot make the remaining family easier. Use paired continuous-outcome
inference and exact paired binary inference as appropriate; freeze the final
interval/test implementation after development and before evaluation. Show
all seed-level effects, 95% precision intervals and adjusted primary decisions;
label ordinary intervals as non-simultaneous. All-zero formation requires an
event-rate upper bound, not a zero-width bootstrap claim of impossibility.

Treat A−D, other welfare distributions, parameter trajectories, environmental
interactions and threshold sensitivities as prespecified secondary descriptions.
The four-cell surface is still central to the figures; the design does not
justify an unmeasured critical boundary. Branch effects with fewer than eight
eligible seeds are descriptive only; report the selection/precision limitation.

Use **0.02 of need per agent-tick** as a proposed practical consumption scale
and **five percentage points** as a proposed functional-share scale. These are
explicit decision conventions to assess before the freeze, not fitted utility
weights. Distinguish a directional effect from evidence that it exceeds those
scales. A confidence interval crossing zero is unresolved; failure to reject a
difference is not equivalence. Tolerance statements are descriptive under the
proposed 20-test zero-difference family. A confirmatory “no material outsider
harm” claim would require a separately declared non-inferiority hypothesis or
adjusted bound against −0.02 in the single freeze; an ordinary 95% interval or
nonsignificant loss does not authorize that claim. Do not add that test after
seeing favorable evaluation data.

Interpret results without requiring an institutional win:

| Observed pattern | Defensible interpretation |
| --- | --- |
| Formation, payoff-biased persistence, member gain and outsider loss | Adaptive exclusion can sustain a locally beneficial, externally costly arrangement under these conditions. |
| Member gain with outsider harm bounded below the declared tolerance | Descriptive compatibility with limited average harm; a confirmatory non-inferiority claim requires its prospectively declared adjusted test. Inspect distributional losses too. |
| Formation with losses to members and outsiders | Persistent costly conflict or maladaptive conventions under the supplied update rule. |
| Declining guarding under imitation, despite executable opportunities | Private selection/free-riding may undermine exclusion; retain the failure mechanism. |
| Rare formation or insufficient local reports | Limited emergence or adaptation under the specified encounter/information regime. |
| Mixed seeds, sparse eligible branches or wide intervals | Unresolved effects; narrow the paper's claims rather than selecting favorable runs. |

Terminal inventories and unchanged legacy utility weights may be reported as
diagnostics. They do not determine selection, paper verdicts or a social-dilemma
label. The old incentive bank remains failed/unresolved on its original terms.

## 8. Paper structure, figures and scope boundaries

Working title: **Adaptive Local Exclusion: Member Benefits and Outsider Costs
under Resource Scarcity**. Use “conventions” in the title only if the evidence
supports persistent shared practice and its adaptive spread.

Plan three main figures from recorded data, in Chromatic Field v1:

1. **Model and adaptive dynamics:** the local information/action sequence plus
   formation, guarding and trait trajectories. Show all replicates or choose
   illustrative traces by a declared rule; never the best seed alone.
2. **Storage × scarcity outcomes:** four-cell emergence and population
   consumption/function estimates, with the four arms and uncertainty.
3. **Who gains and who loses:** paired branch member/outsider effects, fixed
   cohorts, eligibility counts and guard/resistance expenditure.

Use approximately one page for motivation/related work, two for the model, one
for design, two for results and two for discussion/references within the working
eight-page budget. Adjust once the venue specifies what counts toward the limit.
Write methods and an honest results scaffold before evaluation; fill claims
and captions from complete data afterward. Figures do not precede decisive data.

ALIFE 2027's official pages list Prague, 19–23 July 2027. As checked on
7 October 2026, the ISAL listing leaves the submission deadline blank and the
conference site describes planning as early-stage; these pages do not establish
a 2027 paper-length rule. Eight pages is the user's planning target, not a
verified 2027 requirement. [Official conference](https://2027.alife.org/),
[ISAL listing](https://alife.org/conference/alife-2027/),
[current program status](https://alife.vscht.cz/program).

Keep stigmergic marks as an optional later extension. The present registry is
not stigmergy. That framing would require local mark creation/decay, a mutable
respect convention, and a mark-information intervention. Do not add it merely
for the title. Likewise defer reproduction, generated policies, world-model
learning, the large tipping bank and further charter-monitoring controls.

## 9. Next implementation tickets

1. **Adaptive controller and legal performance channel.** Implement the five
   parameters, membership without compulsory restraint, paid dated local reports,
   biased/neutral/frozen updates and complete state/memory continuation. Demonstrate
   actual copying from legal evidence in a constructed fixture.
2. **Storage and capability extension.** Implement the resource-shock/capability
   timing and outer accounting, then the matched storage-buffer fixture. Inactive
   extensions must reproduce their prior physical behavior.
3. **One development runner.** Implement the four cells/arms, common initial
   conditions, fixed-time focal-claim branch and original-identity measurements.
   Start with the first four development seeds only, keeping failed outcomes.
4. **Scientific decision and one complete freeze.** Resolve developmental
   implementation/analysis details, decide whether a second four-seed development
   pass is justified, assess precision, and freeze the independent design.
5. **Independent evaluation and paper.** Complete all frozen comparisons, then
   render the three figures, write the supported result and use existing
   publication/restoration machinery when the evidence warrants it.
