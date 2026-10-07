# Costly local exclusion and adaptive conventions, version 1

7 October 2026, evening steering. This is the active research direction and
supersedes the comparator/mechanism-splitting work package in the earlier plan.
The completed 144-episode institutional bank, incentive bank and v2 controller
fixtures remain unchanged. This document versions an extension and a research
sequence; it does not freeze or launch an independent evaluation.

## Why the direction changes

The first institutional design cannot answer the proposed question about
institutional value under adaptive resource conflict. Members already use
restrained policies, without a qualified member-level consumption temptation.
The supplied stubborn outsiders cause harm but cannot be excluded or sanctioned
by the charter, and no policy adapts. E−D consumption is negative in every seed
in six of eight contexts. The positive fixed-floor/high-storage/mixed-cohort
mean combines an eligible-cohort change of −0.024235 with a stubborn-cohort
change of +0.159173 of need. Improving the decentralized comparator or splitting
collateral and monitoring cannot repair those structural limits.

Those results remain evidence about the supplied design, not proof that every
institution is useless. Coordination/membership v2 remains reusable engineering.
Its constructed fixtures establish neither adaptive conventions nor institutional
welfare. Comparator refinement and the proposed response/collateral/timing/
monitoring panel are **paused**.

The requested paper question is: **When do local exclusion conventions emerge,
what do they gain members, and what do they cost outsiders, as a function of
storage and scarcity?** The target is an ALIFE 2027 full paper, planned around
eight pages. This is a research target, not an achieved result or submission.

## Step (a): physical exclusion implemented first

The new [exclusion module](../swarm_societies/commons_v3/exclusion_v1.py) wraps
the frozen political and physical transitions. It supplies a contest technology,
not a government, legal entitlement, learned convention or optimal strategy.
It adds no endowment and changes no terminal utility coefficient.

Each individual commits its usual physical action, an optional political
intent, and a `Force(guard=..., resist=...)`. Guarding and resistance are mutually
exclusive. Effort is continuous from zero to four; each positive unit costs
0.1 private resource units by default. Both unit costs must be strictly positive.
These are declared engineering defaults, not selected scientific parameters.

A paid guard must be stationary at a resource site at the opening of the tick.
Guarding consumes its resource cost and the entire harvest opportunity that
tick. An attempted unaffordable or nonlocal action has no cost or effect.
Resistance is available to any stationary harvester at the site and pays its
own resource cost. Paid effort remains spent even when no opponent appears.
Incoming harvesters can be contested on arrival; this first version requires
stopping before paying for resistance on a later tick.

Any individual can occupy/guard, including non-members. At an active
institution's site, its opening members share a protection identity. Elsewhere
an individual guards for itself. A claim alone gives no access restriction.
Affiliation only determines whose harvest a guard protects; it does not license
otherwise unavailable physical force. This supplies shared affiliation
recognition and still does not establish parity with every informal coalition.

For each guard, divide its paid effort equally among the positive-request
harvesters at that site outside its protection group. Cancelled guard requests
do not count as harvest attempts. An individual's total hostile pressure `P`
is the sum of these shares from all rival guards. With resistance effort `r`,
its admitted request is

```text
requested harvest × (1 + r) / (1 + r + P).
```

No pressure preserves the original request exactly. The positive baseline
resistance prevents infinitesimal guarding from causing complete exclusion.
Finite guarding is diluted across outsiders. The count uses any positive
harvest request, so small-request feints can dilute pressure; robustness to
strategic feints is untested. Multiple rival groups can guard
the same site; no registry grants one claim priority. This smooth deterministic
contest law is a supplied modeling assumption. It permits partial exclusion,
not guaranteed monopoly, injury, eviction or confiscation. Resource denied to
one request remains available for the ordinary stock allocation and renewal.

Opening membership governs protection: a same-tick entrant does not receive
retrospective immunity, and a same-tick exiter retains opening protection for
that tick. Next-tick affiliation follows the original political lifecycle.
Force costs precede political spending and physics; incoming transfers, refunds
and harvested resources cannot finance them.

The transition resolves actual post-movement locations through a pure provisional
call to the existing political transition, then re-evaluates from the same input
with contested harvest requests. Only the final transition is applied. Keyed
environmental events are unchanged; there is no mutable RNG advance or duplicate
material charge. Policies never see the provisional result. This can require two
transition calculations on a contested tick and checks that movement agrees.
It uses the frozen spending/movement order and actual movement affordability,
without pretending that an intended destination was reached. With no paid force, the complete
political result retains exact parity with the frozen transition.

Observations retain the existing local political packet and public force costs.
They do not reveal opponents' private inventory, hidden payoffs, simultaneous
effort, or evaluator aggregates. State snapshots include the political state,
force configuration and accumulated force costs. Tests cover physical state
continuation; adaptive policy-memory continuation is a later requirement.

## Measurement and engineering checks

The outer material ledger includes private inventory, all political custody,
site stock, production, consumption, physical/political costs, forfeiture,
guarding and resistance. It retains individual actual outcomes, admitted and
blocked requests, and guard harvest opportunities forgone. **A blocked request
is not lost consumption or a causal outsider cost.** Stock contention, inventory
headroom and need can make these quantities very different.

The [measurement module](../swarm_societies/commons_v3/exclusion_measurement_v1.py)
separates fixed reference cohorts from opening membership and outsiders, with
population totals and empty-group counts. Fixed cohorts must be defined before
paired treatments and retain exiters. When starting with no organizations, use
predeclared identity/initial-trait cohorts in the eventual study, and treat
current-member statistics as selected descriptions. Never condition a causal
member-benefit estimate only on who joins after treatment. Individual panel
outcomes, initial cohorts and outsiders' outcomes all need to remain visible.

The [small executable demo](../scripts/demo_commons_v3_exclusion_v1.py) arranges
a scarce site where members gain consumption and outsiders lose, an abundant
site where guarding harms members, resistance that restores some access at a
cost, and rival guards whose costs reduce total consumption. These are paired
single-step action fixtures, including the guard's lost harvesting, not sampled
welfare estimates or an emergence experiment. Four additional transitions
continue exactly after a JSON state round trip. No new experimental bank,
archive, receipt or audit layer is introduced.

```bash
.venv/bin/python -m pytest -q tests/test_commons_v3_exclusion*.py
.venv/bin/python scripts/demo_commons_v3_exclusion_v1.py
```

Validation: 738 v3 regression tests passed, followed by all 60 final new focused
tests (including two added final checks). The demo's maximum material residual
is 3.03e-15. Frozen source files and existing evidence/archive paths are unchanged.

## Step (b): local numerical adaptation next

Replace permanently assigned restrained/stubborn types with bounded numerical
policies. Start with local payoff-biased imitation over a small declared vector:
resource floor, aggressive harvesting propensity, guarding propensity and
join/exit thresholds. Preserve competent navigation. Copy parameters, not a
neighbour's private spatial memory. Updates must be synchronous with bounded
mutation and reproducible keyed randomness. No model calls or generated code.

Choose and implement the local payoff information channel explicitly. The
current simulator does not expose neighbours' consumption or inventory. A
bounded dated local performance display/report would be a new supplied
affordance, with fixed observation windows and documented visibility/costs;
global evaluator welfare cannot silently select who gets imitated. Own material
outcomes are available. Keep imitation disabled and mutation disabled controls
to distinguish adoption, innovation and fixed supplied behavior. Numerical
learning is distinct from a new model-driven evolution campaign.

An optional swarm-intelligence hypothesis is that locally visible site marks
persist without a central manager and that respect/contest conventions spread
through imitation. A mark must have a declared creation, maintenance and decay
rule; respect must be a mutable policy choice. A mark cannot enforce itself.
Use absent, unreadable or shuffled marks as identified controls if this option
is implemented. The present formal affiliation label is **not** already such a
stigmergic mechanism, and the first force fixtures do not demonstrate emergence.

## Step (c): give storage an endogenous function

After numerical adaptation, add a separate starvation/capability extension with
resource shocks. Specify finite energy/health, actual shortfall damage,
capability loss, recovery and timing before sampling; stored resources must
physically buffer those consequences. Begin with fixed identities/population
to keep lifetime and outsider accounting intelligible. Reproduction funded
from surplus with mutation is an alternative if explicitly chosen in a new
version; it is not required in addition to the shock route.

Keep consumption, shortfall, survival/function and resource costs primary.
Demonstrate a paired shock-buffering benefit before claiming endogenous storage
value. Report any selection based on consumption separately from later selection
based on survival/function. Do not tune terminal wealth weights to make restraint
or institutions win. The old qualification verdicts remain failed/unresolved;
they do not qualify the new physical or adaptive game automatically.

## Development, freeze and paper decision

Use **four development seeds initially, at most eight in total**. Declare their
identities, conditions and numerical update rules in the executable development
design when steps (a)–(c) are ready. Development is allowed to expose failures;
record changes and all attempted conditions, with no claim of untouched testing.
Do not extend either completed bank. No sampled panel starts in this increment.

Keep the first development question small: storage 8 versus 80 crossed with
two declared scarcity settings, paired force availability and adaptive/fixed
controls. Define scarcity through physical supply or shocks independently of
the realized winner; do not choose it to favor guards. Begin without imposed
organizations for emergence claims. Arranged affiliations remain only an
engineering/causal-action diagnostic. Measure claim formation, nonformation,
lifetimes, exits and convention frequencies as behavior, alongside individual
consumption, shortfall, stock, guard/resistance expenditure and outsider harm.
Both no-emergence and extractive conventions are admissible results.

Before independent evaluation, make **one complete source/design/analysis
freeze**, including the selected numerical rules, storage/scarcity cells,
fresh seed list, contrasts, practically meaningful effect criteria and all
failure categories. No outcome-based retries, additions or parameter changes
inside that evaluation. Development trajectories are not independent evaluation
replicates; ticks and imitation events do not increase the number of seeds.

A decisive development result is a coherent, reproducible answer that changes
the scientific decision: costly conventions emerge and yield specified member/
outsider effects, or they consistently fail under the declared conditions.
A favorable seed or a constructed fixture is insufficient. Define quantitative
decision thresholds in the complete design before independent evaluation.
Defer new archives, receipt systems and audit layers until such a result exists;
preserve existing evidence and continue ordinary tests and Git synchronization.

For an eight-page paper, allocate roughly one page to question/background, two
to the physical and adaptive model, one to design, two to results and two to
interpretation/limitations and references, adjusted to the eventual venue
format. The central figure should eventually show emergence and separate
member/outsider outcomes across storage × scarcity from recorded data. Prior
negative results explain the redesign; infrastructure completion is not the
headline. Use Chromatic Field v1 when experimental results justify figures.
