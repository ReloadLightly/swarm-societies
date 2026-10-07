# Plan for a spatial commons with optional institutions

## Research objective

Build a world of mobile individuals with local information, consequential
resource competition and institutions that can form, be absent, change and
disappear. Relations between societies have no higher governing authority.
Physical laws are enforced by the simulator; political rules must operate
through the resources, information and enforcement capabilities of their actors.

The first paper question is:

> Under what conditions do locally formed institutions improve their members'
> welfare without exporting costs to outsiders, and how does the relative rate
> of member and institutional adaptation change that outcome?

This is a proposed research program, not a claimed finding or authorization
for another model-driven campaign. The [review and reproduced baseline](research-review-2026-10-07.md)
explain why the previous sequence must change. Existing world-model work remains
an instrument for later experiments. The immediate priority is a qualified
ecology and social dilemma, followed by strong baselines and political mechanisms.

The project should be able to produce a useful negative result. Institutions
may fail to form, a fixed rule may outperform coevolution, and successful local
governance may increase outsiders' losses. None of these outcomes should trigger
unreported retuning of the environment or replacement of evaluation cases.

**Current checkpoint:** the [physical foundation](commons-v3-foundation-v1.md)
implements movement, local access, renewable stocks, accounting and physical
snapshots. Two development banks preserve a failed navigation control and its
separate numerical repair. Stage 1's scientific qualification remains open;
the separately frozen [need-targeted comparison](commons-v3-need-v1.md) now
adds zero/two-tick usable buffers under the same carrying capacity. It improves
reference consumption but retains long-horizon failures; purposeful local
foraging and numerical baselines are next. Optional institutions
and political transitions have not yet been implemented.

## What the target world must implement

| Component | Required behavior | Evidence needed before claiming it works |
| --- | --- | --- |
| Mobile individuals | Positions, movement costs, local extraction and physical encounter | Movement changes reachable resources and contacts; no teleportation or global harvesting |
| Local information | Bounded sensing and delayed, costly communication | No hidden global-state access; held-state information interventions can change decisions |
| Renewable commons | Current extraction changes future production and others' opportunities | Paired incentive curves and ecological trajectories, including recovery |
| Optional institutions | Founding, refusal, joining, exit, amendment, replacement and dissolution | All transitions executable from legal local actions; zero institutions remains a valid outcome |
| Limited authority | Observation, collection and enforcement require material means and reach | Agents can evade or resist; quotas are not automatically obeyed; collection is not free |
| International anarchy | No global government, universal welfare reward or automatic treaty enforcer | Internal gains and outsider losses measured separately; cross-border promises require implemented incentives |
| Collective adaptation | Member and institutional programs change on documented schedules | Repeated reciprocal adaptation, lineage records and interventions on schedule and mechanism |
| Swarm behavior | Local actions produce population-level organization robust to perturbations | Compare local interaction with communication/interaction ablations and scale tests; animation or population size alone is insufficient |

Separate **physical location**, **political membership** and **asserted
jurisdiction**. Crossing a claimed border does not automatically change
membership; leaving an institution does not move the agent. Initially permit
one primary membership per agent, while permitting nonmembers and overlapping
claims over resource sites. Claims alone confer no enforcement power.

The first physical implementation uses 24 agents, 16 resource sites, a
256-tick horizon, a 12×12 grid and radius-one sensing. These settings are frozen
for the recorded development banks, not adopted as qualified scientific
parameters. Smaller exact cases check the implementation; later examine 12, 24 and 48
agents with density, resource supply and communication opportunities controlled.
Do not extrapolate from 24 agents to large swarms without those checks.

## Sequence and spending gates

| Stage | Deliverable | Exit gate | Experimental model calls |
| --- | --- | --- | --- |
| 0. Repair the research foundation | Baseline audit, portability checks, bounded execution and concise research status | Correct claims; portable evidence checks; contained candidate failures | Zero |
| 1. Build and calibrate the physical commons | New engine, accounting, snapshots and a scarcity map | Legal local behavior, viable sustainable regime, profitable unilateral deviation and collective losses | Zero |
| 2. Implement political formation and strong baselines | Optional organizations, costed enforcement, hand policies and parameter search | Political mechanisms work; baseline comparisons are fair; task has consequential headroom | Zero |
| 3. Freeze a small search pilot | New protocol, budget ledger, admission tests and throughput pilot | Explicit budget authorization; adequate revisits and measured throughput | Separately capped |
| 4. Run replicated comparisons | Member-only, institution-only and coevolution arms; schedule controls | Complete declared run blocks and untouched evaluation, including failures | Separately authorized campaign |
| 5. Test mechanisms and generalization | Cross-play, invasion, stress tests and targeted interventions | Claims survive the comparisons they require | Mainly saved-program evaluation |
| 6. Add consequential learning and rule discovery | Local uncertain models, nontrivial sharing and later structural revision | Information changes useful decisions at its measured cost | Numerical work first; new generative searches require another budget |

Stages 0–2 use numerical simulation and existing programs, without new
experimental model calls. A newly generated one-shot LLM baseline costs a call:
it belongs after these local gates and inside Stage 3's explicit allowance.
An old compatible program may be reused earlier, labelled as such.

Gate completion means numerical integrity and a valid scientific comparison.
It never requires a positive coevolution effect, frequent institution formation,
or a chosen rejection percentage. The qualitative incentive gate does require
the task to contain the dilemma being studied; that is an environment property,
not a desired result for the proposed method.

## Stage 0 Repair the foundation

Implementation checkpoint, 7 October: the
[foundation repair report](foundation-repairs-v1.md) records the supplemental
calibration verifier and bounded execution entry points (0B/0C). Both complete
192-case checks pass on Python 3.12/3.13 with the pinned numerical stack;
an older stack's out-of-scope audit drift is retained as a failed check.
The [evidence archive guide](evidence-archives-v1.md) and
[migration validation](../evidence/data-packaging-v1/README.md) complete 0D/0E:
all eight published archives restore byte-identically into a clean checkout,
offline verification passes, and the default suite passes without the bulk
files. The shorter README preserves the full previous report in `docs/`.
Git history remains unchanged. These are versioned, hash-pinned archives;
GitHub administrators retain the ability to remove or replace hosted assets.
Stage 1's physical implementation and development panels are now complete;
its ecological and incentive qualification is still open.

**0A. Correct the scientific record.** Retain the old results as engineering,
identification and exploratory controls. Add the reproduced greedy baseline and
outsider outcomes prominently. Replace any suggestion of established search
superiority with the actual conditional result. Treat raids, ecological
appropriation and lost opportunities as distinct external costs. Preserve all
old protocols, source snapshots and data.

**0B. Make numerical verification portable.** Add a versioned supplemental
calibration verifier rather than change the frozen runner. File hashes, source
identity, case inventory, dimensions, integer counts and qualification decisions
remain exact. Recomputed diagnostic floats may use explicitly documented
`rtol=atol=1e-12`, with the permitted fields enumerated. Reject nonfinite results
and material numerical changes. A tolerance must never hide a changed R-hat/ESS
qualification or retry decision; report a boundary discrepancy separately.
Record Python, numerical library and platform versions and maximum deviations.
Test one-ULP perturbations, material changes, missing/duplicate cases, tampered
samples and altered gate outcomes across the pinned environment and another
supported runtime.

**0C. Make all untrusted execution bounded.** The existing search CLIs already
have resource limits. Consolidate that protection for search, fresh evaluation,
replay and interactive execution of untrusted policies. Use subprocess memory
and CPU limits, a parent wall timeout, bounded IPC/output and explicit failure
receipts. Direct in-process execution is for audited trusted policies only.
Test memory exhaustion, an infinite loop, a long builtin, recursion, malformed
output and worker death. The parent, incumbent and completed checkpoints must
survive, and ordinary programs must retain deterministic trajectories. Choose
limits against measured workloads; do not impose a cap that breaks numerical
libraries before a policy runs.

**0D. Separate publication data from ordinary source checkout.** Keep compact
summaries, manifests, source snapshots, environment specifications and small
test fixtures in Git. Package bulky evidence in versioned, hash-pinned release archives
with checksums, byte sizes, schema versions and stable retrieval identifiers.
Add download/resume/cache and offline verification. Test complete restoration
on a clean checkout before removing tracked copies in a new commit. Zenodo or
a versioned dataset repository are candidate destinations, subject to actual
access and restoration tests. Preserve published archive identities; distinguish
byte-integrity verification from provider-enforced retention or immutability.
Merely deleting files in a new commit does not
shrink history. Any history rewrite needs a verified backup, preserved release
mapping, clone migration instructions and explicit authorization.

**0E. Shorten the README without losing evidence.** Keep the project name as a
name, and make the current capabilities explicit. Lead with the research
question, present implementation status, strongest supported result, limitations
and quick reproduction. Move the detailed study narrative into `docs/` with a
study index, rather than delete inconvenient findings. The eventual paper's
title and central claim must follow its evidence. A new environment is not
itself evidence that institutions or swarms are useful.

## Stage 1 Establish the physical dilemma

The separate `swarm_societies/commons_v3/` physical implementation is complete.
The [v1 protocol](commons-v3-foundation-protocol.md) and
[v2 repair protocol](commons-v3-foundation-protocol-v2.md) each retain a complete
56-configuration, 224-episode bank. V1 exposed a floating-point return-fuel
trap; v2 changes prospective fuel margins while preserving physical laws,
parameters and the case bank. Its zero recorded fuel violations establish that
specific invariant, not a qualified social dilemma or a strong baseline.

At the reference cell, v2 restraint consumes 1.200000 versus greedy 0.229769
per agent-tick. Focal consumption gain is zero. The private gain of 0.010685
at terminal-wealth weight 0.05 falls to 0.005596 with twice the horizon and
0.000252 with carrying capacity 8. Peer consumption losses disappear in the
capacity-8 condition. Greedy terminal ecological stock remains 66.70% of capacity,
so local depletion and access failures must be distinguished from global
resource collapse. These development outcomes come from four reused seeds;
neither bank substitutes for the disjoint qualification gate below.

**Need-targeted checkpoint:** the separately frozen
[development study](commons-v3-need-v1.md) completes the fixed zero/two-tick
buffer comparison under capacity 80, preserving the preceding banks. Reference
consumption improves to 1.123083/1.137248, with positive mean focal greedy
consumption gains and peer losses. However, 512-tick mean consumption falls to
0.798804/0.804615, and larger reserves are worse at lower starting stock.
The reused four-seed development panel does not qualify the environment.

**Immediate next step:** purposeful local foraging and numerical baselines,
then separate ecological and incentive qualification. Retain the complete
need-targeted bank, its adverse outcomes and both earlier banks; freeze every
new comparison before execution. Do not adjust wealth weights or weaken
baselines to obtain a preferred incentive pattern.

The remaining Stage 1 contract follows. Reuse accounting,
observation validation, event provenance and checkpoint patterns; do not alter
the frozen ecology files. Keep the engine independent of the proposal model.

Start with movement, harvesting, consumption, inventory, local transfers,
renewal and communication. Specify their phase order, simultaneous action
commitment and resource-contention rule. Use event-keyed exogenous randomness
so branches and different policy populations can share weather without an
extra message or action changing unrelated random draws. Ledgers must explain
every stock change and resource conversion, including waste, costs and sanctions.

A candidate renewable law is

```text
available = stock after declared growth and weather
terminal_stock = available − realized aggregate extraction
next_growth = r × terminal_stock × (1 − terminal_stock / K) + recovery
```

Capacity, recovery, weather bounds, phase order and resource conversion must be
explicit. A small recovery term distinguishes slow recovery from an artificial
permanent absorbing state. Compare this mechanism with an additive-renewal
negative control. Logistic growth is not automatically a social dilemma:
harvest above half capacity can increase renewal, and completely infeasible
scarcity can make all policies fail.

Specify private utility, consumption need and the selection horizon before
testing incentives. Report consumption, shortfall, reserves, ecological stock
and survival separately. Wealth weights and survival penalties need sensitivity
checks; neither action names nor a cooperation label should receive a reward.
Initial reserves must not pay for the entire episode. Longer horizons must
expose delayed losses rather than reward liquidation just before scoring ends.

**Required incentive interventions.** From identical states, compare a focal
restrained policy and an aggressive deviation against exactly the same peers.
Then vary the proportion of aggressive peers. Plot focal private returns,
outsider consumption and collective consumption over time. Establish both a
temptation to deviate and the harm when deviation spreads. Repeat with longer
horizons, different contention order and different initial stocks. A label
such as “selfish” or “Ostrom-style” is not a payoff measurement.

**Proposed qualification targets.** Finalize these thresholds before the
qualifying bank, using a separate exploratory grid:

- Exact accounting identities in small cases, and ledger residual below
  `1e-9 × max(1, cumulative material flow)` in larger cases; replay and snapshot
  restoration pass; no observation reaches beyond its legal contract.
- A 3×3 ecological grid with at least 16 environment seeds per cell contains
  abundant, binding-but-solvable and genuinely infeasible regimes. Retain all
  regimes and all failed runs in the map.
- In at least two adjacent solvable regimes, unilateral deviation improves
  private return by at least 1% of per-tick consumption need in declared utility
  units, while widespread deviation lowers per-agent consumption by at least
  5% of need relative to feasible restraint. Paired intervals must resolve the
  signs. Report utility-weight sensitivity and do not reinterpret the private
  threshold as consumption welfare.
- A locally implementable restrained policy sustains resources and satisfies
  most demand without hidden subsidies. Greedy play produces persistent
  depletion or materially lower sustainable yield. Specify the depletion
  threshold and duration before the qualifying bank and check a doubled horizon.
- The viable regime is not a single tuned parameter point. A disjoint
  qualification panel retains the incentive pattern. Revising the ecology after
  failure creates a new design version and preserves the failed map.

These are proposed design gates, not claims about current v3 results. Use a
tiny discretized world to obtain an exact solution or certified relaxation if
feasible. A merely stronger planner is a reference policy, not an upper bound.
For the larger partially observed world, report its information advantage and
optimization limitations explicitly.

## Stage 2 Make institutions optional and baselines strong

**Political lifecycle.** Start the formation experiment without mandatory
institutions. Agents can make a local founding proposal, endorse it, commit
resources, join or refuse, withdraw, propose an amendment and replace or dissolve
an organization. Initially use a bounded charter grammar for dues, extraction
quotas, monitoring, sanctions and redistribution. Document the provided
founding, adoption and change procedures. The experiment can establish emergence
of particular organizations and rules within these affordances, not invention
of the political action language from nothing.

Quotas are rules agents may violate, not engine clamps. Dues require payment or
an implemented collection mechanism. Monitoring purchases local evidence;
sanctions need evidence, material resources and reachable targets. A membership
bond may fund a declared contractual sanction, but it cannot authorize unlimited
confiscation or instant action across the world. Keep enforcement capability
distinct from communication topology. Handwritten and evolved institutions use
the same information and action interface.

No supranational actor assigns cooperation, guarantees peace or enforces a
treaty. Begin intergroup interaction with contested resource access, transfers,
ecological spillovers and costly enforcement. Direct violence, demographic
reproduction and elaborate treaty systems should be separately versioned
extensions when a specific hypothesis requires them. Anarchy describes the
absence of higher authority; it does not require predation to be optimal.

**Lifecycle gate.** Scripted integration cases must demonstrate founding,
refusal, nonpayment, detected and undetected violations, enforcement failure,
exit, amendment, replacement and dissolution. Resource and information checks
must pass even when there is no institution. Formation frequency and persistence
are outcomes, not acceptance criteria. Fixed affiliations are useful for the
physical calibration fixture, but they do not satisfy the target formation study.

**Baseline matrix.** Publish all of the following before interpreting search:

| Policy or institution | Purpose | Fairness requirement |
| --- | --- | --- |
| Random legal and idle controls | Catch accounting errors and impossible regimes | Same costs and initial resources |
| Greedy fullest-visible and nearest-profitable harvesting | Strong simple private behavior | Local information and actual movement costs |
| Threshold restraint and rotation | Separate ecological knowledge from governance | Same sensors; no privileged future weather |
| No institution | Test whether organization is needed | Keep peer actions and communication available |
| Simple dues plus investment, where investment is implemented | Avoid rewarding complex rules for a scalar allocation | Real treasury and declared delayed returns |
| Quotas, monitoring and graduated sanctions | Feasible institutional reference inspired by commons governance | Same sensing, founding and enforcement costs; compliance is not compulsory |
| Strong decentralized coordination | Avoid comparing institutions only against isolated incompetence | Same total communication and material opportunities |
| Random search and CMA-ES over a declared policy/charter family | Test whether ordinary numerical optimization suffices | Same training access and charged simulator work; disclose representation restrictions |
| Known-law local planner | Separate inference from control quality | Legal state access, charged computation |
| Global-information reference or certified tiny-world bound | Diagnose solvability and remaining room | Clearly evaluator-only; no claim of a bound without proof |
| One-shot LLM and matched best-of-N without iterative feedback | Separate pretrained design ability from evolutionary feedback | New calls only inside an authorized budget; same policy API and evaluation |

Numerical optimization over institutional parameters needs both a fixed strong
member background and, where feasible, a joint member/institution parameter
baseline. Otherwise the comparison confounds optimizer and search space.
Evaluate homogeneous populations and focal replacements against fixed opponents
separately. A policy that benefits from being the only aggressive harvester
may fail when everyone copies it.
Count simulator transitions or comparable evaluation work as well as episodes;
a longer episode or more expensive controller is not free. Also report model
calls, tokens, wall time and actual monetary cost where applicable.

**Baseline gate.** On a disjoint qualification panel, show a feasible policy
that materially improves on aggressive depletion, then demonstrate room beyond
the strongest simple baselines for the question being proposed. A provisional
minimum useful consumption effect is 5% of need per agent-tick; finalize it
before qualification, with the smallest useful outsider-loss change specified
separately. If a simple fixed policy or parameter optimizer already solves the
problem, do not buy a large code-evolution campaign on the same question.
Either study that result or justify a new task version. Do not weaken a strong
baseline to create headroom.

## Stage 3 Specify selection and its budget

Keep the established inference route unchanged until a new route and allowance
are explicitly selected. Benchmark any faster tier through a small, separately
budgeted pilot using valid proposals and useful improvements per unit cost,
not just response latency. No current provider/model choice is assumed here.

Use four distinct evidence partitions: implementation/development, search,
admission validation and untouched final evaluation. Any panel used repeatedly
to accept programs or choose parameters is selection data. Final weather seeds,
scarcity levels, social partners and invasion scenarios must never appear in
proposal feedback. Record every adaptive query and freeze the final protocol
before the definitive campaign.

Candidate admission first checks legality and bounded execution, then compares
against the same incumbent with paired evaluation draws. Require a predeclared
material improvement margin and validation evidence, not `1e-9` noise. Calibrate
the sequential comparison rule on development, cap retries and account for
repeated testing. Invalid, failed, interrupted and rejected proposals remain in
the ledger. Do not use the final panel as an acceptance filter, or force a
particular rejection rate.

Budget adaptation sweeps over the actual mutable program inventory. Every
relevant member lineage should be revisited after institutional change and
institutional rules after member change; require at least three reciprocal
sweeps in the pilot before calling the procedure coadaptation. If separate
programs for many individuals are too expensive, test shared policy templates
with individual state first and describe that representation honestly.

The pilot freezes throughput, failure rate, variance and a smallest useful
effect. Five independent runs per arm is a floor for considering replication,
not a power guarantee. Select the final run count with a prospective precision
or power analysis over **search runs**, and sensitivity to plausible variance.
Additional environments per lineage cannot substitute for more lineages.

An illustrative campaign of 300 completed proposals × five runs × three arms
already means **4,500 completed proposal calls**, before retries or schedule
variants. Two additional coevolution schedule variants at the same scale add
3,000. These are arithmetic planning examples, not an approved allowance or
recommended minimum. Estimate tokens, elapsed time and evaluation CPU from the
pilot before choosing the actual experiment. Learning curves may justify a
different depth; record the stopping rule before seeing final outcomes.

## Stages 4 and 5 Identify causes and test generalization

Run **members only**, **institutions only** and **coevolution** with matched
total search allowances, initial populations, interfaces, feedback and training
distributions. Include no-evolution and numerical baselines. This estimates
performance per budget; it does not hold member and institution proposal
opportunities simultaneously equal across all arms.

Use a separate scheduling experiment to isolate reciprocal adaptation. Compare
alternating with blocked updates while keeping the same counts of member and
institution proposals. To study relative update frequency, vary the allocation
of a fixed total budget, for example 1:4, 1:1 and 4:1, and report the allocation
change as part of the treatment. This avoids attributing extra compute to a
biological selection-rate mechanism.

The current procedure selects member programs on private payoff and institution
programs on constituent welfare. That is dual-objective program optimization.
A claim about cultural or biological multilevel selection additionally requires
specified within-group and between-group transmission, replacement, migration
and lineage accounting. Derive predictions for the implemented process rather
than import a threshold theorem from a different population model.

Freeze these evaluation families before search:

- **New environments:** unseen resource renewal, initial stocks, scarcity,
  weather and sufficiently long horizons. Report binding, abundant and
  infeasible regimes separately.
- **Cross-play:** new partners, rivals and institutions from independent runs;
  paired role and location rotations. Self-play success is insufficient.
- **Invasion:** replace 1 agent, then predeclared 10% and 25% fractions with
  opportunistic policies while holding population size fixed. Measure invader
  advantage and recovery. This is policy invasion, not demographic fixation.
- **Institutional interventions:** remove monitoring, enforcement or a rule's
  content one at a time while preserving the remaining interface. Separate the
  effect of disabling a mechanism at matched expenditure from refunding its
  costs. Use the same distinction for communication.
- **Information interventions:** content shuffle, delay and outages with
  matched packet counts/bytes where that is the estimand; track displaced
  computation and learning effort. Legal full-information controls are labelled.
- **Component transplants:** fixed/evolved members crossed with fixed/evolved
  institutions, paired on the same states and opponents. Mechanistic effects
  conditional on selected programs are distinct from search reliability.
- **Mobility and scale:** disable movement or constrain contact networks in
  controlled comparisons; vary population with resource density and local
  opportunity controlled. Do not confound mobility with free travel or extra land.

Measure resident consumption shortfall as the principal material endpoint, with
private returns, sustainability, inequality and outsiders' outcomes reported
separately. Keep the original cohort in world-level denominators; dead, expelled
or departed people must not vanish from welfare accounting. For institutional
selection, commit the evaluated constituency for the comparison window and
retain its members' subsequent outcomes, so changing the roster cannot improve
fitness by deleting disadvantaged people. Track current residents as an
additional descriptive population.

Report raid/appropriation losses, resource displacement, enforcement burdens
and outsider welfare separately. Taxes, obedience, messages and institution
count are behavior measures, not automatic indicators of cooperation. The
baseline audit already shows why a zero-raid score can conceal external costs.

For confirmatory claims, average environmental cases within each independent
search run and use paired run-level comparisons; cross-play needs clustering
by the independently sampled lineages on both sides. Declare primary contrasts
and multiplicity handling in the protocol. Report absolute effects, intervals,
failure rates and worst-case outcomes, not just relative percentages. Keep
null and harmful outcomes in the denominator.

## Stage 6 Make knowledge consequential

Preserve the 1,024-particle/four-sweep learner as the frozen stationary control.
Its existing renewal likelihood and calibration evidence do not transfer
automatically to stock-dependent growth, hidden extraction and mobile sensors.
The unresolved conditional-model and likelihood-CDF limitations remain recorded.

Introduce new world-model contracts only after strong reactive and known-law
baselines expose decisions that benefit from information. First isolate locally
unknown ecological parameters. Then add patch heterogeneity, regime changes and
report unreliability separately. Each extension needs its own matched baselines
and model checks; do not add all sources of uncertainty at once.

A meaningful sharing problem must sometimes make communication wasteful or
misleading, and sometimes useful at a real cost. Compare no sharing, simple
fixed sharing, redundant traffic, novelty-based reports and learned selection
under the same budgets. Delay, duplicated evidence and strategic misreporting
need separate interventions. An information advantage must survive comparison
with a strong local heuristic and improve a consequential decision.

Proceed from parameter learning to selection among supplied mechanism families,
then structural revision in a declared grammar. Evaluate predictive equivalence,
intervention predictions, decision regret and exploration cost. Neither supplying
the correct equation nor introducing an unnecessary unknown earns a discovery
claim. Any model-driven structural search requires its own authorized budget.

## Work packages and acceptance artifacts

| Order | Proposed implementation | Required artifact |
| --- | --- | --- |
| 0 | `scripts/verify_calibration_portable_v1.py` and bounded execution wrapper | Cross-platform receipt, failure-containment tests, frozen-source integrity check |
| 1 | `swarm_societies/commons_v3/engine.py`, accounting and observation contracts | Small exact cases, local-action tests, snapshots, recorded trajectories |
| 2 | `baselines/commons_v3/` and `scripts/run_commons_calibration_v3.py` | Scarcity map, payoff curves, viable/collapsing trajectories and a gate JSON |
| 3 | Political lifecycle and enforcement modules | Founding/refusal/exit/change/dissolution traces, legal-information checks and cost ledger |
| 4 | Parameter-search baselines and local planner references | Complete baseline table, evaluation budget ledger and headroom analysis |
| 5 | Versioned admission and search runner | Frozen protocol, model budget, reciprocal-update schedule and pilot report |
| 6 | Cross-play, invasion and mechanism evaluation | Run-level estimates, matched ablations and held-out robustness tables |
| Parallel | Evidence retrieval and research documentation | Clean-checkout reproduction, manifest validation and concise README/study index |

Every empirical work package publishes recorded-data Chromatic Field figures,
captions, source/output hashes and inspected SVG/PDF/PNG exports. The first
required figures are a scarcity map, matched payoff curves and stock/consumption
trajectories. Spatial replay is useful once the simulator actually implements
movement; it cannot substitute for those quantitative tests.

The first implementation ticket is **Stage 0 portability/execution hardening
alongside the smallest Stage 1 physical engine and hand-policy calibration
harness**. Political formation follows verified incentives. A broad production
UI, a larger population, demographic evolution or a new LLM campaign would
not resolve the current scientific bottleneck.

## Planning horizon and decisions

A provisional planning range is 3–6 engineering weeks for a small audited
spatial-and-formation system, and roughly 6–10 weeks including replicated search
and publication-quality evaluation. This is an estimate for sequencing, not a
deadline promise. The actual critical path is passing the dilemma and baseline
gates, followed by measured proposal throughput and statistical precision.

The user's political-world choice is settled: mobile individuals, optional and
changeable institutions, no supranational government. Remaining decisions should
be made when concrete evidence is available: the qualified ecology parameters,
minimal useful effects, approved proposal route/budget, final run count, and
external data destination. History rewriting is a separate optional decision.
No further clarification is needed to begin the no-model-spending work packages.
