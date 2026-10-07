# Active work record

## Ticket D resumed: four complete records replay exactly, 8 October 2026

Recovery implementation `9609ebe9b1e1b3a7d83ca3356cfc4c056c7881a9` was pushed
and remotely verified before resumption. All four previously saved episodes
now reproduce their complete scientific records exactly under the accelerated
implementation. Their gzip bytes are unchanged. These four verified cases
are synchronized as an intermediate checkpoint; the declared bank remains
incomplete, with q selection and G3 still pending. No sharing or independent
evaluation has started. The same runner continues the remaining L0 cases.

## Ticket D recovery checkpoint, 8 October 2026

Four complete L0 cases (moderate, need 1.2, q=0.25, seeds 90001–90004)
are saved in `evidence/commons-v3-learning-development-v1/cases/`.
The interrupted runner is no longer active. Preserve these files and verify
their entire records through the existing recovery path before continuing.
Quantile selection and G3 remain pending; no sharing cases have run.

The first speedup was pushed and remotely verified at
`468f40afa4f15614074f8939ea6b16a72941582e`. A further numerical speedup
specializes the finite eight-value normalization used by posterior quantiles,
with SciPy 1.18.1's exact operation order. Other versions or unsupported inputs
use the original library routine. It passes bit-identical density, CDF,
quantile, mixed-atom and continuation checks, including 10,003 synthetic
reduction vectors. Worker heartbeats and immediate error reporting go only to
stderr. Scientific records, parameters, gates and schedules are unchanged.
**433 checks pass** across the implemented tickets, including 112 focused
posterior/controller checks and 31 runner checks after these changes.
Resume the same incomplete bank with six workers, preserving all saved bytes.
Ticket E and independent evaluation remain unstarted.

## Ticket D execution: identical numerical speedup, 8 October 2026

The implementation checkpoint
`d3bf1bfda443b2eb8c9970686c8dc7e2a8ac5136` was pushed and remotely verified
before the declared development run. The first two L0 cases exposed slow
Python loops over long likelihood histories. No complete case had been saved
when that incomplete process tree was stopped; no scientific outcome was used
to revise an arm, prior, parameter, gate or measurement.

Only the new social posterior now broadcasts likelihood terms and subtracts
them in the original order, with exact CDF memoization within each posterior
revision. Frozen Ticket C is unchanged. Long-history tests compare density,
bin mass, normalization, mixed atoms, CDFs and quantiles bit for bit against
the original arithmetic, including biased/fused densities. Synthetic
five-quantile calculations speed up roughly 6–12 times. Caches do not enter
serialized scientific memory. This is a computational repair, not a design
revision. **420 checks pass**, including 100 posterior/controller checks and
30 runner checks after this repair. Resume the same incomplete bank through
the existing recovery path, with four workers; completed records, if present,
must replay exactly before being preserved. Ticket E remains unstarted.

## Ticket D: approved communication design before development, 8 October 2026

Roland authorized Ticket D after completed G2, then explicitly approved the
99%/1% full-support biased prior and the finite lognormal reconstruction of
median/IQR messages. Both amendments are in contract §7 and §17; their values
will not be selected from development outcomes. Ticket C checkpoint
`3c2b02fc60be4a503bb1a9516e9257807ab11829` was pushed and remotely verified.

The new observation adapter exposes only each agent's own exact previous-tick
harvest, equally in every arm. It changes no physics or frozen observations.
This implements the private information needed to send truthful receipts;
others' realized harvest remains hidden until delivered by the paid engine.
Harvest at t is observed at t+1 and can first reach another agent at t+2.
Receipt qualification retains the locally observed extraction-cohort identities
and requires every member's contribution, including zeros. Incomplete exchange
remains confounded. Canonical evidence is (site,tick,z,S_next), independent of
who observed or relayed it; actual own/cohort harvest stays separately labeled.

Receipt frames are 30 ASCII bytes carrying lossless binary64 harvest values.
Social frames are exactly 96 bytes, once every four ticks: raw evidence for L2,
median/IQR for L3, or padding when no content is available. Combined frames are
126 bytes, within the unchanged 128-byte engine limit. L1–L3 use at most four
unique recipients, with identical deterministic recipient scheduling and
receipt priority; co-located groups can exceed that delivery budget. Social
traffic reserves one recipient slot and combines with its receipt if applicable.
L2 sends the oldest event not yet attempted for that recipient; L3 cycles known
site summaries for that recipient. Neither message acknowledgments nor free
peer receipts are invented. Equal schedules and payload budgets do not force
equal realized paid bytes when positions or affordability differ; all attempted,
paid and delivered bytes/costs are measured explicitly.

Before outcomes, declare 32 L0 development episodes: q in {0.25,0.5} × four
conditions × the existing four seeds 90001–90004. Choose one q using equal-weight
whole-run consumption over 16 cases, then final-quarter consumption, then the
smaller q. This intentionally strengthens the asocial comparator; it is not
balanced tuning across arms. Transfer that q unchanged to 80 sharing episodes
(L1, L2, L3, L2-biased, L3-biased × 16 cases). The four biased identities are
fixed at 0,6,12,18. φ remains 0.375. Reuse the 48 selected frozen Ticket B
reference episodes without extending or rewriting that bank.

Evaluate G3 after L0 selection and before the sharing panel. If mean cumulative
first-64-tick oracle-minus-L0 share of need is at most 0.02 in **all four cells**,
use the contracted fallback before any sharing episodes. Retain both q
candidates' diagnostics. Otherwise complete the 80 sharing episodes, for
112 learner episodes in total. There are still only four development arena
seeds; no new seeds, independent evaluation or design freeze is authorized here.

Epistemic measurements include all 24×16 agent/site pairs, assigning untouched
priors to unseen sites in the evaluator only. Belief tick128 means evidence has
been processed from observation128; terminal512 receives an observation-only
update. Seen-only summaries and own/receipt/relay evidence counts are separate.
Starvation next to food uses post-extraction stock before regrowth; local
collapse uses post-regrowth stock, consistently with Ticket B. Development
analogues of P3 and P5 average the two wide-world demand levels within each
seed. P5 retains both time-average and terminal coverage, descriptively: its
primary time endpoint is unspecified in the contract and remains a pre-freeze
review item. No evaluation significance tests are run on these reused seeds.

The approved amendments and initial pre-development choices were pushed at
`9fa42f298134275d88405875fbc4485fee6cd3ce`, with remote verification.
Implementation is complete and **411 checks pass**: 360 engine/learner/receipt/
posterior checks, 21 controller checks and 30 development-runner checks.
Small engineering fixtures cover all six regimes and exact continuation;
paired initialization and weather must match before sharing can start.
No declared development episodes have started at this checkpoint.
Ticket E remains unstarted.

## Ticket C complete: site learning and Gate G2, 8 October 2026

Implementation and G2 criteria were pushed before the panel at
`746e8a69d30d4aeebda09e8926afbc8bd9e762d2`, with remote verification.
The fixed [calibration bank](evidence/commons-v3-world-model-calibration-v1/)
contains 1,024 independent synthetic sequences and 65,536 transitions:
29,214 clipped and 36,322 unclipped. Generator truth, weather and clipping flags
are retained for evaluation, never supplied to the learner.

**G2 passes.** All eight ECDF checks satisfy the predeclared simultaneous DKW
bound of **0.0600202**. These are independent-sequence checks, not a claim that
65,536 observations are independent replications.

| Tick | Posterior-rank distance | Predictive-PIT distance | Inclusive 90% coverage | Randomized 90% coverage |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.027884 | 0.026852 | 90.53% | 90.53% |
| 16 | 0.025616 | 0.024983 | 89.75% | 89.75% |
| 32 | 0.051525 | 0.033239 | 91.99% | 88.77% |
| 64 | 0.027700 | 0.041314 | 100.00% | 90.53% |

Independent one-transition quadrature CDFs agree within **2.57e-14**; the
predeclared tolerance was 0.002. The strongest CDF change relative to bound-only
inference is 0.993812, and distinct repeated saturation identifies the exact
off-grid capacity. Duplicate physical evidence leaves the posterior unchanged.
The unupdated prior itself has a rank distance of 0.023543, illustrating why
rank calibration alone would not establish evidence use.

At tick 16, mean absolute log-median capacity error is 0.020648 versus 0.547356
for bound-only inference. By tick 64 every no-harvest synthetic sequence has
identified its capacity atom, so inclusive intervals cover 100%. This is a
property of these fully observed renewal sequences, not evidence that learning
is trivial for harvesting, co-located agents. G3 is not evaluated here.

The posterior, local extractor and L0 wrapper are implemented. Continuous
integration uses 400 log bins plus exact observation-generated atoms, with no
inference from evaluator clipping labels. φ stays at 0.375; q remains untuned.
Calibration is limited to the synthetic clean-transition model. It does not
establish nominal coverage in the heterogeneous coupled arenas, where coverage
will be measured in the contracted arm comparison.

**All 1,024 sequences and 65,536 transitions replay exactly**, including
posterior records and every reported statistic. Canonical summary SHA-256:
`dcc015e686fa4357959ddd790de2f4bc96014182286a6f914ffeaed20eb5cad6`.

All **126 implementation checks pass**. After G2 passed, a 32-tick engineering
fixture with four agents and three sites verified real movement/harvesting,
legal clean/shared evidence handling and conservation. A tick-16 physical JSON
snapshot plus copied controller state reproduces every subsequent action,
ledger, metric, physical digest and controller memory exactly. This adds no
scientific L0 performance comparison or parameter choice.

Ticket C is complete. No scientific L0 arena bank, message arm, quantile
selection or fresh evaluation has run. Ticket D remains unstarted; it is the
next contracted work item. Frozen engines, foragers and completed banks remain
unchanged, with no experimental model calls.

```bash
.venv/bin/python scripts/run_commons_v3_calibration_sites_v1.py verify --workers 2
```

## Ticket C resumed after G1: learner and prospective G2 checks, 8 October 2026

Roland authorized the next ticket after the G1 report. Its result checkpoint
`b89fddfee055b44f5ff12afaf3c0186a8d775a42` was pushed and remotely verified.
Ticket C implements the site posterior, legal local evidence and L0 wrapper;
Ticket D's messages, development arms and quantile selection remain later work.

The exact clipped-uniform likelihood is represented by a continuous posterior
on 400 logarithmic bins with eight-point quadrature inside each surviving bin,
plus explicit off-grid atoms at observed stocks. Support boundaries are solved
analytically before integration. This is numerical integration of the contracted
likelihood, not an analytically exact integration claim or a discrete-capacity
prior. No observation is snapped, no sensor noise is invented, and no clipping
flag comes from the evaluator. Repeated saturation can identify a capacity;
replaying the same (site, tick) evidence cannot.

The L0 extractor conservatively requires the observer to occupy the site during
extraction, observe both consecutive stocks and have next-tick headcount one.
Its own realized solitary harvest follows from the known request and old stock.
It accepts stock bounds from all visible sites but does not use merely adjacent
empty sites as transition evidence. Shared or skipped transitions are excluded.
The wrapper keeps the selected φ = 0.375; q = 0.5 is an untuned implementation
default, with both contracted q values available for Ticket D's later selection.

Before any G2 panel outcomes, fix 1,024 independent synthetic sequences, seeds
91001–92024, 64 transitions each: K drawn from log-uniform [8,100], exogenous
initial stock 1, no harvest, and independent declared uniform weather. This
avoids conditioning a synthetic initial stock on hidden K without modeling
that selection. It is a synthetic likelihood check, not an arena run with the
contract's U(0.3,0.9) initial fractions. Checkpoints are ticks 1, 16, 32 and 64.

G2 requires finite, nonempty updates, at least 500 transitions including clipped
and unclipped cases, and all eight randomized posterior-CDF/predictive-PIT ECDF
distances within sqrt(log(1600)/(2×1024)) (family error bound 0.01). Inclusive
and randomized 90% coverage are descriptive; exact atoms can make inclusive
intervals conservative. Three independent quadrature references must agree in
CDF within 0.002, with at least one CDF shift exceeding 0.05 relative to the
bound-only prior; repeated saturation must yield the exact atom. These checks
prevent accepting an unchanged prior merely because its ranks are calibrated.
The fixed calibration harness reuses existing canonical storage and replay.

All 125 implementation tests pass: 36 legal-evidence, 38 independently checked
posterior, 12 calibration-harness and 39 static L0-wrapper checks. Analytic and
independent quadrature references cover off-grid mixed atoms, narrow surviving
support, predictive probabilities and serialized continuation; two input
validation defects found by those checks were fixed before calibration.
The calibration panel and all scientific L0 arena runs remain unstarted.
No new protocol, audit or publication layer is
introduced. G2 must pass before any arm run; the old calibration is not reused.

## Ticket B completed: G1 passes; stop before Ticket C, 8 October 2026

The implementation/selection checkpoint
`15f2191ba8b1a69964fdc8616ce00683bc600fbe` was pushed and remotely verified before
the panel. All 96 development episodes completed; all candidates are retained in
[`evidence/commons-v3-world-model-consequence-v1/`](evidence/commons-v3-world-model-consequence-v1/).
The [summary](evidence/commons-v3-world-model-consequence-v1/summary.json) includes
selection scores, all four cells, paired seed differences, final-quarter results
and material diagnostics. The cases include initial/final physical snapshots,
per-tick measurements, per-agent consumption and trajectory/weather digests.

One global **φ = 0.375** is selected (mean share of need 0.908820, versus 0.889410
for φ = 0.5). At that φ, one global **fixed K = 40** is selected (0.791363,
versus K = 30: 0.788010 and K = 20: 0.785445). These choices use all 16 cases,
not separate tuning for each condition. The resulting 48 selected episodes give:

| World | Need | Oracle share of need | Fixed share | Greedy share | Oracle − fixed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Moderate | 1.2 | 0.994007 | 0.981941 | 0.236125 | +0.012066 |
| Moderate | 1.6 | 0.842439 | 0.791464 | 0.083111 | +0.050975 |
| Wide | 1.2 | 0.976038 | 0.772931 | 0.259440 | +0.203107 |
| Wide | 1.6 | 0.822794 | 0.619117 | 0.104490 | +0.203677 |

**G1 passes:** the wide/high-demand mean paired gap is **0.203677 ≥ 0.08**.
The four differences, in seed order 90001–90004, are 0.173278, 0.165745,
0.232807 and 0.242878. The ordinary 95% t-interval is [0.140372, 0.266981];
it is descriptive, after selection on these same four reused development seeds.
Final-quarter shares in that cell are oracle 0.834694, fixed 0.606824 and greedy
0.014326. This establishes consequential knowledge for the supplied controller
on this development panel; it does not establish learnability or sharing value.
As a descriptive check using the retained candidates, the best fixed belief
within that cell is K = 20 (0.621546); its oracle gap is still 0.201248, positive
on every seed. This does not change the global selection or the G1 calculation.

The same cell's shortfall beside food above the oracle floor accounts for
0.349505 of need under the fixed belief, versus 0.003287 for the oracle.
Local collapse occupies 0.000427, 0.024323 and 0.932434 of site-ticks for fixed,
oracle and greedy respectively. Thus low consumption need not mean widespread
ecological collapse. All communication costs/bytes are zero in these references;
the maximum absolute accounting residual across all candidates is 2.154e-13.
Neither terminal inventory nor utility weight enters selection or G1.

**All 96 cases replay exactly**, including physical snapshots, policy/action
trajectory digests and every saved measurement; reaggregation also matches.
The canonical summary SHA-256 is
`518da11c1c98fcf23f801b89e8fb845f15afdc9abe47a6896137bfa065ffdc23`.
Ticket A's 204 checks and Ticket B's 91 checks pass. No fresh evaluation,
learner, sharing arm, experimental model call
or extension of a completed historical bank has run. **Stopped at G1 as
instructed; Ticket C remains unstarted.** The two unavailable full articles
remain pending for later checking under Roland's approved §17 access limitation.

Reproduction (completed banks refuse `run`; `verify` replays without writes):

```bash
.venv/bin/python scripts/run_commons_v3_consequence_sites_v1.py verify --workers 2
```

## Ticket B implementation before the development panel, 8 October 2026

G4 checkpoint `65354fcfebd94dcdcea30ab4c2b252aa83ac7947` was pushed and verified
on `origin/main`. Ticket B uses the same four scratch development seeds
90001–90004, with the contracted equal-total-capacity worlds and independent
U(0.3,0.9) initial fractions; these are not fresh evaluation seeds.

Choose one oracle floor fraction from {0.375, 0.5} using equal-weight mean
consumption over all 16 development cases. At that fraction, choose one fixed
capacity from {20, 30, 40} across the same 16 cases. Final-quarter consumption,
then the smaller parameter, break ties, following the existing navigation
selection ordering. Retain all 32 oracle, 48 fixed and 16 greedy episodes;
the selected reference map contains 48 of these 96 episodes. This is a finite
development choice, not the later design freeze or independent evaluation.

The wrapper injects capacity beliefs and refreshes remembered capacities without
editing the frozen forager. Greedy retains its native zero-floor branch,
reserve 2 and `net_yield`, with no aggressive inventory target. The consequence
runner reuses existing compressed case storage, immutable writes and exact
replay comparisons. It records whole-run/final-quarter consumption, per-agent
spread, communication costs, post-regrowth local collapse and starvation beside
food remaining after extraction and before regrowth. The last diagnostic does
not assert feasible unilateral access under simultaneous competition.

G1 uses the four paired wide-world/need-1.6 differences and the contracted
mean threshold of 0.08, independently of its descriptive 95% t-interval. All
intervals are descriptive after development selection. Stop at G1 regardless
of its result. All 91 controller/runner tests pass, including exact threshold
boundaries, global selection, paired worlds/weather, finite inputs and short
replays of all three references. The scientific panel has not started.
No learner, communication arm, new
protocol or archive layer is added.

## Ticket A: site-capacity physics and observation v2, 8 October 2026

The separate `engine_sites_v1.py` copies the frozen transition with immutable
per-site capacities/initial stocks. It retains the frozen event namespace,
weather IDs, physical costs, contention and `Action` type. The new snapshot
schema retains both capacity and initial-stock vectors for exact continuation.
Legal observation v2 omits capacities and declares only the common law, weather
range, initial-fraction distribution and capacity prior.

`worlds_sites_v1.py` constructs the contracted moderate/wide multisets (640 total
capacity each), seed-shuffled independently of keyed per-site U(0.3,0.9) initial
fractions. Agent positions and weather remain paired across arms and conditions.
No learning, exclusion, shocks or messages beyond frozen physical support are
added. The approved literature checkpoint `18fe0ec57ff99d4d6537adfac27008091df02f85`
was pushed and independently verified on `origin/main`.

**G4 passes.** The four stored seeds 90001–90004 match the frozen engine for
512 ticks: actions, policy memories, physical state, ledgers, metrics and pinned
trajectory digests are exact. New snapshot envelopes carry the new version and
site vectors; their common v1 physical payload hashes match after removing only
those added configuration fields. Snapshot continuation and hidden-capacity
noninterference also pass. Validation: 54 new engine tests, 14 world tests and
136 existing engine/navigation tests pass (204 total). Frozen sources and banks
are unchanged. Ticket B has not started.

## World-model contract resumed with approved literature scope, 8 October 2026

Roland authorized using abstracts and publicly available information for the
two unavailable full texts and will supply the articles later. This is recorded
in [contract §17](docs/paper-contract-world-models-v1.md#17-contract-change-log).
The [bounded related-work draft](docs/paper-related-work-world-models-v1.md)
closes §3 under that approval: no identical coupled design was found in the
inspected material; full methods of those two papers remain unchecked. No
additional search or protocol is introduced. Proceed A/G4, then B/G1, and stop
at G1. No learner or communication-arm implementation is authorized in this run.

The previous wait checkpoint `3b819a8fd12344ea6e99eb57b6e78488df481634`
was pushed and independently confirmed on `origin/main`.

## Binding world-model contract adopted; literature access limit, 8 October 2026

Roland's supplied shell block was run unchanged. Each scratch probe ran once;
all §2 figures reproduce to printed precision (96 + 80 episode rows). The
unchanged contract/probes, retained JSON/text outputs and three requested top
pointers were committed as `e4bf3c75c12f2acef39ebeee702618fe36aee214`
(`Adopt world-model paper contract v1`), pushed, and independently verified by
`git ls-remote origin refs/heads/main`.

The requested [one-page related-work draft](docs/paper-related-work-world-models-v1.md)
records the bounded §3 pass. Wu and Farr full texts do not run the contracted
regenerative-capacity comparison. Kuusela–Laiho manuscript methods and one
targeted decentralized-foraging search supply additional distinctions. The
primary full texts of Aishwaryaprajna–Lewis 2023 and Mills–Lewis 2025 remain
inaccessible despite publisher, author and repository searches; their primary
abstracts are identified explicitly. G0 is not declared cleared on that basis.

Roland explicitly selected **“Wait until both full texts are available.”**
Ticket A and Ticket B remain unstarted; G4 and G1 have not been evaluated.
Resume §3 only when the two full texts can be read, then continue A/G4 and B/G1
in order and stop at G1. No deviation was approved, so contract §17 remains
unchanged. The contract, probes, frozen engines and completed banks are unchanged.

The literature-draft checkpoint `b60abcccae85b98eb9c553f1526babf8d9919ecc`
was pushed and independently verified with `git ls-remote origin refs/heads/main`.


## Exclusion plan paused; world-model question restored, 7 October 2026

The user's subsequent review rejects the exclusion-first paper framing.
Ticket 1, the adaptive exclusion controller, is paused. The four-arm exclusion
plan remains a superseded proposal; none of its development or evaluation
runs has started. Physical exclusion remains implemented engineering, not a
scientific result. All completed banks and frozen source closures stay closed.

The scoped primary-source review and v3 information/learner assessment are
recorded in
[the reframing review](docs/commons-v3-world-model-reframing-review-v1.md).
The original objective of consequential world-model learning and collective
inference is restored. A candidate question is not a qualified novelty claim
or permission to freeze another design. No numerical adaptation, new experiment,
model spending, archive, receipt or additional audit layer is started.

The review checks the supplied papers and adjacent adaptive-harvesting and
strategic-information work. Territorial exclusion, collective inference and
learning fishery dynamics all have close antecedents. Two especially close
sources still need full-text comparison; adjacent abstract-only leads and the
remaining decentralized-harvesting comparison are explicit;
the narrower candidate contribution is provisional. The code assessment identifies
observed capacity and a logistic-relevant floor, rather than a full known-law
planner; hidden peer extraction confounds ordinary stock differences, while
existing paid monitoring may supply usable local transitions. The historical
likelihood and calibration cannot be transferred unchanged.

The next deliverable is an identifiable observation-and-decision contract after
resolving the remaining literature questions. README, roadmap and working
instructions now reflect this order. This is a documentation-only increment;
no simulator, policy, protocol source closure or evidence file changes.
All 259 local document-link targets resolve, and `git diff --check` passes.
Scientific tests were not rerun for this prose-only change.

Review checkpoint `ba19d530a35cd360aaa93cd671c4bdc24b167f5b` was pushed to
`origin/main` and independently confirmed with
`git ls-remote origin refs/heads/main`. This records synchronization in the
existing progress log without adding a receipt layer.

## Superseded exclusion paper design proposed, 7 October 2026

The [new design plan](docs/commons-v3-exclusion-experimental-plan-v1.md) translates
the evening review into a bounded ALIFE study. Four environmental cells
(storage 8/80 × two renewal levels) share four arms: adaptive exclusion,
adaptive open access, neutral copying and fixed parameters. The plan narrows
the initial adaptive stage to spread of standing variation without mutation,
uses paid local reports of complete scored epochs, and proposes actual
capability loss/recovery under supply shocks to give storage a physical role.

The central identification change is a fixed-time focal-claim branch. Members
and all outsiders, including rival-group members, are defined before the
intervention and retained through later entry/exit. The branch estimates the
conditional continuation value/cost of established exclusion; it does not
estimate the benefit of joining. Whole-population effects use paired full runs.
Missing claims remain outcomes, and outsider non-inferiority is not inferred
from a nonsignificant loss. The proposed primary family has 20 comparisons.

Initial development proposes four seeds, 64 full runs and up to 16 short
branches; at most eight development seeds across two recorded passes. The
independent proposal uses 32 fresh seeds, 512 full runs plus at most 128 short
branches: **557,056 physical ticks / 13,369,344 individual decisions** before
replay. One complete source/design/analysis freeze must precede evaluation.
No episode was executed, no scientific code changed, and no archive, receipt
or audit layer was added for this planning increment. Completed banks stay closed.

The official ALIFE 2027 pages confirm the July event; the pages checked do not
yet establish submission dates or a 2027 page limit. Eight pages remains the
user's working target. The plan links the official pages and selected primary
literature, defines three intended figures and records the next implementation
tickets. At this checkpoint numerical adaptation was proposed next; the subsequent
literature/world-model review pauses it.

Design commit `b4e82495022edb450b9678a5a4f65f73544d278b` was pushed and
independently verified with `git ls-remote origin refs/heads/main`. Local
document links, episode/decision arithmetic and the 20-comparison count checked;
scientific source and evidence paths have no changes in this increment.

## Evening steering adopted; costly physical exclusion implemented, 7 October 2026

The [new active extension and sequence](docs/commons-v3-exclusion-conventions-v1.md)
pause comparator refinement and charter response/collateral/timing/monitoring
splitting. The completed first design has restrained members without qualified
member temptation, harmful outsiders beyond charter sanctions, and no adaptation.
The 144-episode bank remains closed. Its adverse/cohort-specific results and
all earlier incentive verdicts remain unchanged.

Step (a) is implemented separately in `exclusion_v1.py`: any individual can
pay for stationary guarding and forgo harvesting; outsiders can pay to resist.
Opening affiliation determines shared protection at a claimed site. Claims
alone do nothing, finite guard effort is divided across outside harvesters,
and rival claims can contest each other. Actual movement is resolved before
contests. There is no seizure of outsider inventory or automatic member quota
enforcement. The outer ledger accounts for every material cost; no-force
transitions exactly preserve the old political result.

The evaluator separates fixed reference cohorts from opening membership and
outsiders. Constructed, paired action fixtures retain member gains with outsider
losses, member losses under abundance, costly resistance and rival-guard losses.
These are engineering checks, not sampled welfare estimates or emergence.
Four physical continuation ticks match after a JSON state round trip; maximum
demo material residual is **3.03e-15**. The v3 regression run passed **738 tests**;
the final focused run passed **60 new tests**, including two additional checks
of final-harvest monitoring and the limits of coercion. No frozen sources,
completed evidence banks or archive identities changed.

**Next:** (b) local payoff-biased numerical imitation over a few policy parameters,
with an explicit legal local performance signal; then (c) physical storage value
through shocks and starvation/capability loss. No model calls. Use 4–8 development
seeds and one complete freeze before independent evaluation. The ALIFE 2027
eight-page target asks when local exclusion conventions emerge, what they gain
members and what they cost outsiders across storage and scarcity. No sampled
panel, new archive, receipt or audit layer was created; defer those layers until
a decisive result. Ordinary tests and Git synchronization continue.

Implementation commit `32f172423ac224f0189e86a46637d7689508e537` was pushed to
`origin/main` and independently confirmed by `git ls-remote origin refs/heads/main`.
Synchronization is recorded here without creating a separate receipt layer.

## Consequential coordination and responsive membership v2 implemented, 7 October 2026

The [new engineering contract and checked fixtures](docs/commons-v3-coordination-membership-v2.md)
implement the next planned controller increment in separate modules. Paid,
dated remembered-site reports and revocable route intentions can change physical
decisions. Shared navigation uses only directly observed sites as return anchors;
disabled coordination retains exact frozen-forager behavior. False assertions
remain bounded beliefs, not secretly verified world facts.

The v2 runtime supplies the same explicit private previous-tick receipt to every
registered controller. Optional membership uses local service/liquidity entry
rules, voluntary quota promises, persistent own shortfall/private cost/outside
advantage for exit, and an eight-decision cooldown. Exit creates no spendable
refund; mature claims remain local and delayed. Binding bilateral commitment
parity and identified enforcement effects are still unresolved.

The [source-bound compact fixture](evidence/commons-v3-coordination-membership-v2/fixture.json)
records real paid message delivery changing a recipient's route/extraction,
exit at tick 4 under unchanged terms, local withdrawal at tick 6, optional
formation and liquidity-based refusal. **18 continuation ticks** regenerate
exact decisions/receipts/flows; maximum material residual **1.10e-14**.
The full v3 suite passes **680 tests**, and all **110 new focused checks** pass
against the final source files. No sampled bank, policy selection, model calls
or evolution occurred. This validates engineering, not general welfare benefit.

The first 144-episode bank and qualification sources remain unchanged. **Next:**
declare separate response, collateral, timing and paid-monitoring interventions
with explicit decentralized commitment/information parity, then freeze revised
development and fresh independent evaluation. Do not retune terminal weights,
extend completed banks or restart ecology work. The small engineering fixture
is kept in Git and needs no raw-bank download.

Implementation commit `5ba4d498389c6052fa88842d411cbbc7261f4ca3` is pushed and
independently verified by `git ls-remote origin refs/heads/main`; the
[synchronization receipt](evidence/commons-v3-coordination-membership-v2/synchronization.json)
binds its compact fixture and validation record.

## First institutional development comparison complete, 7 October 2026

The [full report](docs/commons-v3-institutions-development-v1.md) retains all
**144 episodes / four environment seeds / 36,864 ticks / 884,736 decisions**.
The protocol, executable design and source closure were pushed and remotely
verified at `a4c84e67cc7d6d05ef4d05c13e75c7fafe90e6c2` before the first episode.
Execution took 192.95 seconds; full semantic replay and all midpoint
policy-memory continuations passed in 244.83 seconds. Relevant checks passed
230 tests. Zero model calls, evolution or policy selection occurred.

**No robust enforced-charter advantage:** E−D consumption is negative in every
seed of six of eight contexts. At capacity 80 with six stubborn agents the
fixed/selected means are +0.021617/+0.041273 of need, with adverse seeds. The
fixed-floor population gain combines eligible-cohort loss −0.024235 with
stubborn-cohort gain +0.159173; its unmonitored arm performs better than its
enforced arm in every seed. Absolute enforced consumption reaches only
59.19%/60.06% of need in these two contexts.

Decentralized coordination sends just five paid reports in three of 32
episodes; no caches or exits occur in any episode. Enforced policies purchase
20,453 monitors but observe 54 violations (34 self-only, 20 externally observed)
and make 13 sanctions. Fixed-floor/capacity-80/six-stubborn enforcement has no
observed violation or sanction. Formation under static supplied rules and
positive bundle means do not establish useful governance or deterrence.
All consumption/cohort/late contrasts, nulls, losses and weights 0/0.05/0.2
remain in the summary and recorded-data figures. A separate read-only diagnostic
checks every raw hash; it does not execute policies or alter the bank.

The [new archive](artifacts/commons-v3-institutions-development-v1/README.md)
packages all 144 raw files (17,133,617 bytes) into a 15,473,215-byte archive.
Public and offline restoration each reproduce all 144 files into empty
destinations; hosted metadata also matches exactly. The new release targets
results commit `2c59d9e90e616a4e62c7c31b77e841986053c491`; remote main and tag
were verified at that commit. Earlier archive identities and frozen sources
remain unchanged. Publication and replay receipts are linked in the archive page.

**Next scientific work:** consequential decentralized coordination/commitment
controls, locally payoff-responsive refusal/exit, and prospective separation
of charter response, collateral, timing and paid monitoring. Use a new version
before revised development and independent evaluation; do not extend or tune
this completed bank. No new ecology layer, tipping panel or model spending.

## First institutional development panel prepared, 7 October 2026

The [prospective development protocol](docs/commons-v3-institutions-development-protocol-v1.md)
declares 144 episodes: both frozen navigation backgrounds, capacities 8/80,
0/6 stubborn agents, four policy arms and four fresh seeds 93001–93004, plus
all-stubborn anchors. Each episode has 256 ticks; total 36,864 physical ticks /
884,736 individual decisions. There is no policy selection, confirmatory gate,
model call or evolutionary run. The complete code/design/source closure is
prepared in `evidence/commons-v3-institutions-development-v1/` before execution.

All nonstubborn arms retain competent restrained navigation. The active arms
share paid reports and conservative local cache management. Optional charters
use the existing quota/bond/dues/fine defaults; the unmonitored arm anticipates
no enforcement and withholds funds for unused operations. These are declared
policy-bundle comparisons, not an isolated or cost-matched governance effect.
Formal boards and escrow still lack a full nonmembership contract analogue.

Measurement retains original cohorts, consumption, shortfall, costs, actual and
observed violations, membership, stock and custody. Terminal book ownership
allocates treasury equally among current members without redeeming it; carried
and book utility remain separate at weights 0/0.05/0.2. All source/controller,
measurement, recovery and relevant physical/political checks pass: **230 tests**.
The earlier incentive source closure is unchanged. Unit tests used synthetic
seed 42 cases; no declared development episode had run at preparation.
The seed-disjointness and preparation receipts are in
`evidence/commons-v3-institutions-development-validation-v1/`.

Execution must follow remote verification of this prepared source/design
increment. Retain nonformation, nulls and losses; do not tune or extend the panel.

## Incentive replay obligation closed; political implementation synchronized, 7 October 2026

The unchanged verifier exactly reproduces all **224 configurations / 3,360
episodes / 884,736 physical ticks / 21,233,664 individual decisions** and
reconstructs every saved aggregate and verdict. The new
[semantic replay receipt](evidence/commons-v3-qualification-validation-v1/incentive-replay-v1.json)
and [log](evidence/commons-v3-qualification-validation-v1/incentive-replay-v1.log)
are outside the frozen bank. Four workers took 2,081.48 seconds; zero model calls
or evolutionary runs. This replay did not restart or extend the completed bank.

All 17 frozen source files and 245 sealed artifacts retain their manifest
hashes. The manifest remains
`a2d858cb15bf34860566d49bbb7c2d3115fecbd9dfa2fb88e23eb42203830c05`.
The receipt's `ecology_original_verified: false` records the intentional absence
of a new original-ecology replay: its copied, bound ecological input was checked.
Earlier ecology verification remains valid. No new ecology audit, figure or
publication layer was added. Primary joint qualification remains unresolved;
broader qualification and reference robustness at all declared weights fail.

Political runtime/controllers and full policy-memory continuation are now
implemented and verified as described below. Commit
`a120744e01581bfd836ec242e421f6c83fe6191e` is pushed and independently confirmed
by `git ls-remote origin refs/heads/main`. The implementation adds no new
scientific bank or claim of beneficial institutions. The next work package is
the small declared institutional development comparison, with matched generic
capabilities, explicit terminal custody accounting, and original-population /
outsider outcomes. Freeze independent evaluation only after that development.

## Audited political controllers and full continuation verified, 7 October 2026

`commons_v3/policies_institutions_v1.py` retains the competent frozen forager,
adds bounded paid local reports with preserved observation times/provenance,
and supplies optional-charter decision rules. Cooperative, explicitly responsive
and stubborn behaviors remain distinct. Local affordable entry, refusal,
voluntary funding, monitoring, collateral settlement, exit and mature claim
retrieval use legal observations. These are candidate comparison policies, not
qualified private optima or evidence of institutional advantage.

`commons_v3/political_episode_v1.py` binds the audited source closure and restores
every physical/political state field and policy memory. It accepts only its
fixed built-in registry; generated v3 policy execution remains unimplemented.
The [lifecycle demo](scripts/demo_commons_v3_institutions_v1.py) exercises the
complete declared transition/failure sequence over 17 ticks and regenerates
61 continuation ticks from six JSON checkpoints. It ends with no active
institutions or custody, 0.52 operating cost, 0.5 forfeiture and maximum material
residual 1.42e-14. A separate nonscripted, nonzero-need fixture forms a charter
through supplied local rules and reproduces eight subsequent decision rounds
after restoring membership and audit evidence. These are engineering fixtures.

Validation: **76 new political/core/controller/runner tests**, within a full
**1,055-test / 123-subtest** check. The sandbox run passed 1,047 tests and all
123 subtests; eight existing archive tests failed because the sandbox forbids
their 127.0.0.1 server. Those exact eight passed with loopback networking allowed.
No implementation failure remains. Added logical-state checks reject duplicate
identities, inconsistent memberships/custody, boolean identity links and replayed
or expired consent. Frozen engine and qualification source files are unchanged.

The first implementation increment `a2a2482fdb62358b29f2f32afb0d71ac38c12247`
was pushed and independently confirmed by `git ls-remote origin refs/heads/main`.
Next scientific work is a small declared development comparison with matched
generic capabilities and a specified treatment of terminal custody, followed by
a separately frozen independent evaluation. No new research bank, tipping
episodes, model calls or evolutionary campaign were launched.

## Stage 2 political capabilities implemented, 7 October 2026

The first [political capability contract](docs/commons-v3-institutions-contract-v1.md)
and `commons_v3/politics_v1.py` implement optional local founding, refusal,
joining, exit, amendment, replacement and dissolution. Explicit custody covers
finite shared site storage, generic personal caches, voluntary bonds and dues,
delayed local refunds, paid extraction monitoring and bounded collateral
forfeiture. Quotas do not clamp harvest; outsiders' private inventories cannot
be seized. Secure custody and truthful paid audits are supplied assumptions,
not an explanation of enforcement emerging without infrastructure.

The core's 25 independent tests plus 97 frozen physical tests pass (122 total).
They include exact absence-of-politics parity, material conservation, observation
limits, concurrent exit/charter/replacement races, one fine per witnessed event,
and JSON snapshots. Frozen physics and qualification sources remain unchanged.
Full policy-memory continuation and the audited coordination/charter policies
are the next verified increment. No institutional experiment, tipping panel,
generated policy or model-driven campaign has been launched. Institutional
benefit remains untested; original qualification verdicts are unchanged.

The existing incentive semantic replay is progressing independently through the
saved bank, without restarting or extending it. Its final receipt remains pending.

## Overall assessment and Stage 2 execution plan, 7 October 2026

The [current assessment](docs/research-state-and-next-steps-v1.md) distinguishes
the implemented research instrument from the still-untested institutional
question. Stage 0 and the v3 physical foundation are complete; ecological
qualification is finite and partial, primary joint incentive qualification is
unresolved, and broader incentive qualification fails. V3 has no implemented
institutions or generated-policy execution adapter, and the old learner has
not transferred to the new renewal/observation law.

Next: close the existing incentive semantic replay, specify a versioned
political/physical capability contract, implement the full optional lifecycle,
and build a strong decentralized coordination comparator. Evaluate costly
maintenance/recovery under harmful peer behavior and outsider effects, with
universal restraint as a ceiling/overhead control. Scripted lifecycle traces
are engineering evidence; supplied responsive behavior and institutional
benefit require separate empirical stages. Member averages must retain the
selection/exit caveat and report original-population cohorts.

The 12,288-episode tipping protocol remains unchanged and unexecuted. Its full
surface can inform the empirical study, but it need not block political
interface development. This explicitly supersedes stale prospective ordering
in earlier plans without passing the old failed gate. Full incentive replay
remains pending; no new simulations, test-suite reruns or experimental model
calls were made for this planning assessment. Further ecology reporting remains
deferred, and model-driven adaptation still requires a new budget and baseline
headroom. README and earlier roadmaps link the active plan.

## Latest external review: probe reproduced and incentive framing revised, 7 October 2026

The supplied `scripts/v3_temptation_probe.py` reproduces on seeds 90001–90008:
fixed-floor restraint meets **99.8529% of need**; reference aggression gains
**0.001471** of need in consumption and **0.013893** at weight 0.05, with
**89.41%** of the latter from terminal inventory. Capacity 8 reduces canonical
gain to **0.002174**. Against 23 aggressive peers, reference consumption gain
is **0.070589 [0.049163, 0.092015]** of need, while the capacity-8 contrast is
**−0.001681 [−0.075374, 0.072012]**. These ordinary eight-seed descriptive
intervals do not amend frozen qualification gates. All **64 probe episodes**
replay exactly; original stdout and per-seed records are retained separately in
`evidence/commons-v3-temptation-review-v1/`. No model calls or evolution.
Its separate public catalog in `artifacts/commons-v3-temptation-review-v1/`
restores all **64 raw files / 6,664,398 bytes** byte-identically through an
unauthenticated empty-cache download and offline restoration. The release
targets the remotely verified review/probe commit `5676088`; the earlier
incentive-completion checkpoint `e895b72` is also pushed and remote-verified.
The separate incentive catalog in
`artifacts/commons-v3-incentive-qualification-v1/` now restores all
**224 raw files / 453,051,247 bytes** through public empty-cache and offline
restoration. It retains the existing qualification release target and all
earlier ecology asset identities/bytes. Full incentive semantic replay remains
pending; the source, raw artifact and aggregate checks pass.

The [complete incentive report](docs/commons-v3-incentive-qualification-results-v1.md)
retains all original verdicts, weights, sensitivities and the five recorded
peer counts 0/6/12/18/23. The bank was already complete and was not altered,
restarted or extended. Primary joint qualification is unresolved; broader
qualification and reference robustness at all three weights fail.

The [review response](docs/commons-v3-review-2026-10-07.md) selects option (b):
the new [storage × peer-share protocol](docs/commons-v3-tipping-protocol-v1.md).
Its numerical design is specified, but implementation/source freeze and future
execution remain separate; **zero** tipping-panel episodes have run. Terminal
weights are unchanged. The README distinguishes a plausible assurance/tipping
problem from a demonstrated strict stag hunt. Further ecology publication,
figure and audit layers are deferred. Stage 2 optional institutions, their
lifecycle and paid local enforcement without supranational authority remains
the next scientific priority after framing. No new inference budget is implied.

## Complete qualification bank: primary unresolved, robustness fails, 7 October 2026

Both prospectively frozen banks are recorded: **3,648 episodes / 1,032,192
physical ticks / 24,772,608 individual decisions**, with 16 disjoint fresh
seeds per stage and zero model calls or evolutionary runs. Ecological replay,
independent audit and public restoration were already complete at resumption.
The incentive source/artifact checks and exact saved-case aggregate reconstruction
now pass; full incentive semantic replay remains pending. Neither bank was
restarted or extended. The new external review prioritizes incentive framing;
further ecology publication, figures and audit layers are deferred.

The primary common-adjacent-pair verdict is **unresolved**. Both ecological
candidate pairs are blocked by the selected control's uncertain reference
focal gain. The broader qualification **fails**, including reference robustness
at every declared weight. Capacity 8 fails the private-gain threshold for both
controls at weights 0, 0.05 and 0.2; its population mean harm is unresolved even
though final-quarter harm passes. These are scientific outcomes, not retry
conditions. Preserve the complete bank and every adverse seed.

At the reference, fixed-floor focal consumption/utility gains are
**+0.001687/+0.016593** per tick at weight 0.05; **89.83%** of the utility gain
is terminal inventory. Selected focal consumption instead falls **0.013786**;
inventory contributes **+0.014497**, leaving only **+0.000712** mean utility.
Mean peer consumption falls **0.015443/0.020560** under fixed/selected controls.
This does not qualify a robust private temptation or authorize model spending.

## Ecological replay and independent audit complete, 7 October 2026

All **288 ecological episodes replay exactly**, including source/artifact
checks and aggregate reconstruction. A separate standard-library auditor
reconstructs raw flows, agent endpoints, quarters, cohorts and all 90 ecological
criteria, and verifies the 54 distinct conservative resource certificates.
It passes 42,769,556 exact checks, 1,506,078 numerical diagnostics and
17,994,052 inequalities, with a maximum numerical diagnostic difference of
8.88e-16. No diagnostic tolerance changes a qualification decision. A second
read-only review of the auditor and completed ecological data passes.

Raw data publication and both restoration checks are already complete. The
separate incentive bank continues under the original freeze; its complete
results, exact replay, independent audit and figures remain pending.

## Ecological archive publicly verified, 7 October 2026

The new `artifacts/commons-v3-ecology-qualification-v1/catalog.json` restores
all **144 raw files / 58,201,356 bytes** from public release
`commons-v3-qualification-2026-10-07`, targeted at ecological completion
`ead7cfc`. All three hosted assets match local hashes. Unauthenticated
empty-cache download and a second offline restoration both reproduce every
payload byte. Publication receipts are separate in
`evidence/commons-v3-qualification-validation-v1/publication/ecology/`.
Later incentive assets will retain separate identities and preserve these files.
The incentive bank, exact ecological replay and independent audit continue.

## Ecological qualification bank complete, 7 October 2026

All **144 configurations / 288 episodes** are sealed under the prospective
`b44ee25` freeze. Source/artifact hashes and full aggregate reconstruction pass;
exact semantic replay and independent raw-data auditing follow separately.
Both frozen controllers pass all ecological criteria in **five of nine cells**,
including the reference. Two adjacent reference-containing pairs pass the
ecological conjunction. This is finite-horizon ecological evidence; incentive
qualification still depends on the separately frozen bank.

The conservative 512-tick physical bounds certify insufficient supply for the
95%-of-need target in the low-renewal cells with need 1.2 and 1.6. The low-renewal,
need-0.8 cell and the rate-0.24, need-1.6 cell remain feasibility-unresolved:
both controllers fail, but their failure is not a physical impossibility proof.
Maximum ledger residual is **2.22e-13**. All earlier banks and 882 protected
pre-existing tracked files remain byte-identical. No model calls or evolution.

## Separate qualification protocols frozen, 7 October 2026

The ecological and incentive protocols are implemented and prepared, with no
qualification episodes run at this checkpoint. See
`docs/commons-v3-ecology-qualification-protocol-v1.md`,
`docs/commons-v3-incentive-qualification-protocol-v1.md` and the conservative
physical-bound derivation in `docs/commons-v3-feasibility-v1.md`.

Both the fixed-floor and previously selected controller remain mandatory.
Ecology uses 16 fresh seeds per cell at 512 ticks; incentives use 16 different
fresh seeds, matched focal substitutions at 0/6/12/18/23 aggressive peers,
and separately declared storage, horizon, initial-stock, contention and
utility sensitivities. The two banks total **3,648 episodes / 1,032,192 ticks /
24,772,608 individual decisions**, excluding replays. A fixed family of 194
simultaneous scalar intervals governs the primary and robustness verdicts.
Both protocols and complete source closures will be pushed before execution.
Prepared banks are `evidence/commons-v3-{ecology,incentive}-qualification-v1/`.

The rational physical certificates can establish insufficient supply for a
specified target; a permissive upper bound remains unresolved unless a legal
controller witnesses viability. No policy improvement, ecological result or
incentive result is assumed in advance. Engineering failure preserves a failed
bank; scientific failure does not trigger retries or threshold changes.

All **437 commons tests** pass, including exact serial/parallel equivalence,
recovery, conservative bounds, recorder and interval/gate checks. The full
repository suite passes **979 tests and 123 subtests**. Validation receipts are in
`evidence/commons-v3-qualification-validation-v1/`. No experimental model calls
or evolutionary runs are authorized or used. Earlier frozen banks are intact.

## Navigation and numerical-baseline checkpoint completed, 7 October 2026

The stronger local controller, predeclared finite sweep and disjoint-seed
comparison are complete. See `docs/commons-v3-navigation-v1.md` and the
recorded-data gallery `figures/commons-v3-navigation-v1/`. Preserve this bank
and all three preceding development banks; do not restart them.

**660 episodes / 175,104 physical ticks / 4,202,496 individual decisions**
cover 18 candidates on two tuning seeds and six comparison conditions on four
fresh evaluation seeds. The selected buffer-4/floor-0.5/nearest controller
consumes **1.199410** per agent-tick at the reference, versus fresh-seed
legacy need-2 **1.083741**; over 512 ticks it sustains **1.193929**. The
fixed-floor anchor is nearly as strong and slightly better at 512 ticks.
The hardest cell still meets only **49.28%** of need. Reference focal utility
gain remains **67.93% terminal wealth**, capacity 8 removes the mean peer
consumption loss, and one high-need focal case loses **0.567094** consumption.
This is stronger baseline evidence, not ecological/incentive qualification,
a private optimum or evidence for institutions. No experimental model calls
or evolutionary runs occurred.

All **660 episodes replay exactly** in separate 324/336-episode invocations.
The full suite passes **842 tests and 123 subtests**. Independent reconstruction
passes **163,114 exact and 93,983 numerical checks**. All episodes record zero
unaffordable known returns; 655 have exactly zero extraction waste and five
capacity-8 aggressive cases retain rounding-level totals no greater than
**1.42e-14**. Maximum accounting residual is **4.40e-13**. All three PNGs were
inspected, and all **18 gallery files** rerender byte-identically.

Both public catalogs restore **380 raw files / 11,786,864 bytes** from release
`commons-v3-navigation-2026-10-07`, byte-identically through unauthenticated
empty-cache downloads and offline restoration. The tuning and evaluation
catalogs are separate under `artifacts/commons-v3-navigation-{tuning,evaluation}-v1/`.
Evaluation publication preserves the earlier tuning assets and catalogs.
Implementation/design (`b16a239`), selection (`cc9c2fe`), tuning publication
(`587a26b`), evaluation/audit (`9cf537d`), figures (`14e155c`) and evaluation
publication/exact replay (`d28fa57`) were pushed and remote-verified as each
stage finished. Continue prompt GitHub synchronization for future work.

**Next:** separately specify ecological and incentive qualification, retaining
the fixed and selected baselines, the full scarcity map, storage/wealth/horizon
sensitivities and adverse focal outcomes. The current four-seed panel cannot
be reused as untouched qualification. Institutions, their lifecycle and paid
enforcement remain later stages. Do not alter weights or weaken baselines to
manufacture a dilemma, and do not start model spending without a new budget.

## Navigation evaluation complete; exact replay underway, 7 October 2026

The frozen 18-candidate tuning and four-fresh-seed evaluation are complete:
**660 episodes / 175,104 physical ticks / 4,202,496 individual decisions**,
with zero experimental model calls or evolutionary runs. All 324 tuning
episodes replay exactly. The independent standard-library audit passes
163,114 exact and 93,983 numerical checks across the complete bank. The
336-episode evaluation replay and recorded-data figures are underway.

On fresh reference seeds, selected consumption is **1.199410** versus legacy
need-2 **1.083741**, fixed no-floor forager **1.097344**, and fixed-floor
forager **1.197891**. At 512 ticks selected consumption stays **1.193929**
(final quarter **1.182944**), compared with legacy **0.731003**. This is
substantial development progress, but the selected controller is slightly
worse than the fixed floor at 512 ticks (**1.195943**).

Reference focal aggression gains **0.006815** consumption and **0.021253**
private utility at wealth weight 0.05; the remaining gain is terminal inventory.
Peers lose **0.017507** consumption per tick. All-aggressive consumption falls
to **0.163314** with terminal ecological stock **0.173%** of capacity.
Capacity 8 reduces the private gain to **0.007190** and changes mean peer loss
to a tiny gain (**0.000098**), while all-aggressive consumption is **1.054347**.
Preserve these sensitivities: four-seed comparisons are descriptive and do
not pass ecological or incentive qualification. The engine, weights, source
freeze and pre-evaluation selection are unchanged.

## Navigation tuning archive publicly verified, 7 October 2026

The pre-evaluation selection checkpoint is pushed as `cc9c2fe`; its release
`commons-v3-navigation-2026-10-07` now publishes the complete tuning bank.
The separate `artifacts/commons-v3-navigation-tuning-v1/catalog.json` restores
**324 raw files / 5,334,049 bytes**. All three public assets match local hashes;
unauthenticated empty-cache restoration and a second offline restoration are
byte-identical. Publication receipts are in
`evidence/commons-v3-navigation-tuning-v1-publication/`. Tuning and evaluation
have separate archive identities; later evaluation assets will not replace
this catalog. Hashes do not make GitHub hosting administratively immutable.

The four-fresh-seed evaluation and exact tuning replay are in progress.
The selected parameters and source freeze remain unchanged.

## Navigation tuning sealed before evaluation, 7 October 2026

All **324 tuning episodes** completed with no failed cases. The predeclared
consumption objective selects **`r4-f50-nearest`**: four ticks of desired food
buffer, a half-capacity voluntary stock floor, and nearest-site routing.
Its mean normalized consumption is **0.8799445193**, versus **0.8797400412**
for the otherwise matching travel-adjusted-yield candidate. The small margin
is a two-seed development result, not evidence of route-rule superiority.
All 18 candidates and their adverse cells are retained. The selected candidate's
worst-cell mean is **0.493789** of need. No evaluation outcome has been seen.

Tuning source/artifact hashes, aggregate reconstruction and the exact selection
binding pass. Full semantic replay is next. This checkpoint pushes selection
before evaluation begins; evaluation uses only the four predeclared disjoint
seeds. The full repository suite passes **842 tests and 123 subtests**.
The physical source and prospective protocol remain frozen at `b16a239`.
No experimental model calls or evolutionary runs occurred.

## Navigation and numerical-baseline design frozen, 7 October 2026

The new observed-map forager and staged numerical runner are implemented in
`policies_navigation_v1.py` and `development_navigation_v1.py`. The forager
uses legal local memory, purposeful routes, sensing frontiers, stale-site
reinspection, simultaneous move/harvest and paid route-fuel provisioning.
An exact small-world regression checks saving enough fuel to reach a known
productive site instead of consuming every small harvest. Food buffers remain
available for consumption. The physical engine and earlier policies are frozen.

All **300 commons tests** pass, including 39 new policy and 26 new runner tests.
The [prospective protocol](docs/commons-v3-navigation-protocol-v1.md), full
design and copied source hashes are recorded in `evidence/commons-v3-navigation-v1/`
before any tuning/evaluation execution. The finite grid has 18 combinations
of buffer, voluntary stock floor and route rule. Its 324 tuning episodes use
two seeds; 336 evaluation episodes use four disjoint seeds and six conditions.
Selection maximizes normalized homogeneous-population consumption, with fixed
late-consumption and candidate-ID tie rules. It is not a private optimum or
ecological/incentive qualification. The source/design freeze is pushed before
the panel starts, and the selected tuning checkpoint will be pushed before
evaluation. No experimental model calls or evolutionary campaign occur.

## GitHub synchronization and need-bank publication, 7 October 2026

The user explicitly requested prompt GitHub updates throughout subsequent
work. The completed need-targeted implementation, results, figures and
validation are pushed as `536ed64cb733f2091afd9c9c7905531826519ff7`;
remote `main` was independently verified at that commit. Continue pushing
completed, verified increments instead of waiting until a research stage ends.

The raw need-targeted bank is now public in release
`commons-v3-need-2026-10-07`, targeting that implementation commit. A separate
public catalog in `artifacts/commons-v3-need-publication-v1/catalog.json`
preserves the earlier local-only metadata without alteration. All three
hosted assets match their hashes. Public unauthenticated download into an empty
cache restored all **56 files / 3,647,037 bytes** byte-identically into an empty
directory; offline verification and another empty-directory restoration pass.
Receipts are in `evidence/commons-v3-need-publication-v1/`. Earlier comments
about unpublished data describe the preceding local checkpoint.

Stronger local navigation and a finite numerical baseline sweep are the
active implementation task. Keep the engine, utility weights and all prior
sources/evidence frozen. The new policy, candidate grid and separated tuning
and evaluation seeds must be fixed and pushed before running the new panel.
No experimental model calls or evolutionary campaign are authorized.

## Need-targeted local baseline checkpoint completed, 7 October 2026

Resumed from the completed physical-foundation checkpoint. The separate
`commons-v3-need-development-v1` study implements fixed zero/two-tick desired
consumption buffers under the same primary carrying capacity 80. Only travel
fuel is withheld from consumption; usable reserves, target caps and waiting
guards are explicit. The engine and both earlier banks remain unchanged.
Report: `docs/commons-v3-need-v1.md`; frozen protocol:
`docs/commons-v3-need-protocol-v1.md`.

The completed new bank has **56 reused development configurations / 224
episodes**, **61,440 physical ticks / 1,474,560 individual decisions**, and
**zero evolutionary runs or experimental model calls**. All need-0 and need-2
populations each have a paired greedy focal replacement. The four seeds,
physical cases, five sensitivities and utility weights match foundation v2;
the saved v2 comparisons were read without restarting the old banks. Source
and protocol copies were frozen before panel execution; no panel outcomes
were used to tune the controls.

At the reference cell, consumption is **1.123083/1.137248** for zero/two-tick
buffers, versus saved v2 greedy **0.229769** and restraint **1.200000**.
Focal greedy consumption gains are **+0.105842/+0.095690**; private utility
gains at wealth weight 0.05 are **+0.121224/+0.110419**. Peers lose
**0.336463/0.287450** consumption per peer-tick. These focal gains include
consumption, unlike the earlier restraint comparison's wealth-only reference
gain. They are conditional policy-bundle effects, not pure extraction effects
or cross-border institutional outcomes. The reference mean benefit of the
two-tick buffer is **0.014165**, with two positive and two negative seed pairs.

Adverse results remain visible. At 512 ticks, need-0/need-2 consumption falls
to **0.798804/0.804615** and final-quarter consumption to
**0.383088/0.385710**, with **56.95%/52.13%** of ecological stock remaining.
Lower initial stock makes the two-tick buffer worse by **0.254884** per
agent-tick across all four pairs. Capacity 8 retains focal consumption gains
and reduces, without eliminating, mean peer losses. All means/ranges describe
four reused seed/focal configurations; neither qualification nor robust
navigation has been established.

All **224 episodes replay exactly**, with zero recorded extraction waste or
unaffordable known returns. Maximum recorded accounting residual is
**2.15e-13**. A separate standard-library audit passes **29,055 numeric checks**
with maximum accumulation-order discrepancy **1.08e-12**. Its diagnostic
tolerance does not affect the engine or exact semantic replay. Both Chromatic
Field figures were inspected; all **12 gallery files** rerender identically.
SVG/PDF/PNG, four CSV tables, captions and hashes are in
`figures/commons-v3-need-v1/`.

The full test invocation returned **769 passed / 123 subtests passed**, with
eight existing archive tests blocked while creating their localhost HTTP
server under the network sandbox. A targeted rerun with loopback access passed
all eight: **777 unique tests and 123 subtests pass across the two invocations**.
Both logs are retained; no implementation or test changes were needed. The
targeted commons suite also passed 235 tests. Compact receipts and the audit
script are in `evidence/commons-v3-need-validation-v1/`.

The new local-only archive has **56 files / 3,647,037 payload bytes** and a
3,657,256-byte archive. Empty-directory offline restoration and independent
byte comparison pass. Its separate catalog is
`artifacts/commons-v3-need-v1/catalog.json`; a verified copy is in the local
cache. It has **not been publicly published or synchronized to GitHub**.
Raw cases remain ignored; a fresh checkout can regenerate the bank with the
report's commands. Earlier public archive identities and all frozen sources,
protocols and evidence are preserved.

**Next:** purposeful local foraging and numerical baselines, followed by
separate ecological and incentive qualification. Preserve all three completed
development banks. Institutions, their lifecycle and paid enforcement remain
later work; no new inference budget or evolutionary campaign is authorized.

## Spatial v3 physical foundation implemented, 7 October 2026

The separate `commons-v3-physical-v1` engine now implements mobile individuals,
local observations and actions, stock-dependent renewable sites, finite
inventories, costed movement/extraction/messages, optional gifts, simultaneous
commitment and resource-flow accounting. There are no institutions,
memberships or supranational authority. Snapshot continuation covers physical
state under the same future actions; private policy-memory recovery and bounded
execution of generated v3 programs remain separate work.

Report: `docs/commons-v3-foundation-v1.md`. Two separately frozen development
banks and protocols each contain **56 configurations / 224 episodes**, with
61,440 physical ticks and 1,474,560 individual decisions per bank. V2 reuses the
same four seeds and cases after inspecting v1: neither bank is an untouched
qualification panel. There were **zero evolutionary runs and zero experimental
model calls**.

V1 revealed a floating-point return-fuel trap. Its failed control and results
remain preserved. V2 adds a prospective numerical fuel margin without changing
physics; all 224 episodes record zero underfunded known-site returns. Full v2
semantic replay passes. A verifier-only canonical-JSON equality repair also
preserves all 56 v1 case files, its design and summary byte for byte; its earlier
source and metadata are retained in the validation directory. An externally
interrupted v2 run resumed through the official replay-and-compare path,
preserving all 33 already complete case hashes.

The scientific gate remains **open**. At the reference cell, all-restraint
consumption is 1.200000 per agent-tick versus greedy 0.229769, but 66.70% of
global stock remains. The illustrated run contains nine full unused sites
alongside hungry agents. This is local depletion plus access/navigation failure,
not demonstrated global ecological collapse. A focal greedy replacement gains
zero consumption; its +0.010685 private utility at wealth weight 0.05 comes
entirely from terminal inventory. Smaller carrying capacity nearly eliminates
that gain and removes peer consumption loss. The next implementation is
need-targeted harvesting with modest reserves under the same capacity, plus
purposeful local foraging and numerical baselines, before qualification or
institution experiments.

Both recorded-data galleries include SVG/PDF/PNG, CSV inputs and source/output
hashes. All four PNGs were inspected; all 24 gallery files rerender identically.
Independent numerical audits confirm accounting residuals below 8.6e-13. Raw
cases are published separately through `artifacts/commons-v3-foundation-v1/`
in release `commons-v3-foundation-2026-10-07`, targeting implementation commit
`e7c7cbb9b861ae5202324d2cee76fae8ad702381`. All five hosted assets match their
sizes and hashes. Public download into an empty cache restored all **112 files /
9,287,035 bytes** in a clean checkout, byte-identical to the originals; offline
verification also passes. Raw cases remain ignored, and history is unchanged.

The full default suite passed **704 tests and 123 subtests in 462.38 seconds**
in that clean checkout before restoration, with all 112 v3 and 844 legacy bulk
files absent. Implementation and test bytes remain unchanged after testing.
The independent preservation audit confirms all earlier protected code,
protocols and evidence unchanged. Compact receipts, preflight metadata and test
logs are in `evidence/commons-v3-foundation-validation-v1/`. The implementation
commit and this final validation checkpoint are synchronized to GitHub.


## Evidence publication and report consolidation completed, 7 October 2026

Stage 0D/0E is complete. The existing public GitHub repository now hosts eight
versioned evidence archives in release `evidence-v1-2026-10-07`, sourced from
checkpoint `069536285a7d0d30f0828fa999b2337d408e9562`. The catalog and per-file
size/SHA-256 manifests remain in `artifacts/evidence-v1/`. Restoration commands
and limitations are in `docs/evidence-archives-v1.md`; compact validation records
are in `evidence/data-packaging-v1/`.

The archives contain **844 files / 750,595,253 original bytes**, compressed to
690,260,993 bytes. All 17 hosted archive/metadata assets match their local
sizes and SHA-256 digests. Public, unauthenticated download into an empty cache
restored all 844 files in an actual clean sparse checkout. Offline verification
then checked every cached archive and payload. Comparing the complete restored
checkout and the original workspace against the pre-migration inventories found
all **1,133 original evidence files / 768,984,812 bytes** identical. All 82
previous implementation, script, test and seed files also remain identical;
an independent review rechecked 301 frozen source declarations without mismatch.

Only after these checks were the 844 payloads removed from Git tracking.
The original local files remain present and ignored. The **289 retained evidence
files / 18,389,559 bytes**, plus new migration receipts, include source snapshots,
designs, summaries, compact tables and the calibration case-067 test fixture.
This removes **97.6% of the previous evidence payload from the current tree**.
An ordinary full clone still downloads historical blobs; use a shallow clone
for the smaller current checkout. No history rewrite or force-push was used.
Hosted assets are hash-pinned but remain administratively mutable; no repository
immutability setting was changed.

The full default suite passed **542 tests and 123 subtests** in 509.47 seconds
in the clean checkout with all 844 bulk files absent, before public restoration.
The 72 archive/restoration tests cover corrupt and unsafe archives, size limits,
conflicting files, partial-download validation, caching and offline operation.
Final edits after that run only move verified data and update documentation and
receipts; implementation and test bytes remain unchanged.

The README now has **1,446 words**, down from 7,635. Its question, methods,
actual results, limitations and reproduction remain prominent. The complete
previous narrative, tables, captions and references are preserved in
`docs/living-research-report-2026-10-07.md`, with relative links adjusted;
`docs/study-index.md` indexes all studies, including null results and controls.

No experimental model calls or evolutionary runs were made. Stage 1's separate
spatial engine is next: mobile agents, legal local actions, stock-dependent
renewal, exact accounting and incentive calibration. Optional institutions and
costed enforcement follow the physical gate; no v3 capability or positive
institutional result is claimed by this checkpoint.

## Foundation repairs implemented, 7 October 2026

The user authorized the repair sequence following the scientific review.
The numerical verifier and candidate-execution repairs are additive; no frozen
simulator, source dependency, original verifier, protocol or earlier evidence
was changed. No experimental model calls or evolutionary search were made.

- Report and commands: `docs/foundation-repairs-v1.md`.
- Supplemental verifier: `scripts/verify_calibration_portable_v1.py`.
- Bounded execution: `swarm_societies/execution_v1.py`,
  `swarm_societies/execution_worker_v1.py` and the
  `python -m swarm_societies.run_bounded_v1` CLI.
- Bounded historical search adapter: `swarm_societies/search_execution_v1.py`
  and `scripts/evaluate_search_bounded_v1.py`.
- Compact verification records: `evidence/foundation-repairs-v1/`.

All **192 cases, 401 artifacts and 4,283,648 retained sample likelihoods** pass
on Python 3.13.5 and Python 3.12.13 with NumPy 2.5.3/SciPy 1.18.1. Each replay
compares 4,620 diagnostic scalar locations with zero drift; one-ULP behavior is
covered separately by focused regressions. The reviewer's 72/576 last-bit count
was not reproduced. Tolerance is restricted to reference R-hat/ESS diagnostics,
including retained attempts and likelihood diagnostics. Qualification, retries,
thresholds, exact observations and source hashes remain strict. Full-bank
testing caught and fixed the distinction between the fitter's joint `passed`
flag and its coefficient-only gate (case 067's first attempt).

A Python 3.11.15/NumPy 2.4.6/SciPy 1.17.1 check fails at the first case's
feature-condition-number audit, which differs by 1.776e-15 and is outside the
tolerance whitelist. Preserve this failed receipt and the pinned numerical
requirements; do not claim universal cross-stack portability.

Fresh bounded workers apply memory/CPU limits before policy compilation; the
parent enforces wall/output limits and process-group cleanup. All four episode
engines, normalized consumption cases and stepwise continuation are supported.
JSON insertion order and hash-seed-zero execution preserve observable ordering.
This is resource containment, not an OS security sandbox. Frozen direct APIs
remain trusted-only. Failed search jobs retain receipts and leave incumbents
unchanged; the new adapter preserves the old 1e-9 acceptance rule for parity,
not as the future scientific admission rule. Old search budgets stay exhausted.

The default 80-tick replay matches the entire frozen result; the worker used
1.23 seconds and peaked at 23,808 KiB RSS here. All **301 declared source/input
hashes from 28 inventories** match, covering 158 distinct checked paths.
The full suite passes **470 tests and 123 subtests** in 230.39 seconds,
including 118 new repair tests and 21 additional subtests. Independent
execution, integration and source-freeze reviews passed. The checkpoint's
validation record pins all new implementation and test sources.
External data publication/restoration and README consolidation remain open
Stage 0 tasks. The next scientific implementation is the separate spatial
physics and calibration gate, then optional institutions and strong baselines;
none of those v3 capabilities is claimed by this repair checkpoint.

## Scientific review and spatial commons plan, 7 October 2026

The user supplied a critical external review and requested a thorough assessment
and an ordered implementation plan. The user clarified the target: **mobile
individuals in an anarchic international system; institutions can emerge, be
absent, change and disappear**. This supersedes the immediate plan to advance
straight to supplied-mechanism model selection. Existing world-model components
remain tools; the first priority is a qualified ecology and strong baselines.

- Review: `docs/research-review-2026-10-07.md`.
- Proposed implementation and spending gates: `docs/commons-v3-plan.md`.
- Reconstructed baseline evidence: `evidence/baseline-review-v1/`.
- Recorded-data figure, SVG/PDF/PNG, table and hashes:
  `figures/baseline-review-v1/`; renderer `scripts/visualize_baseline_review.py`.

The reviewer did not supply policy source. A reconstruction of fullest-visible
harvesting, full effort, zero contributions/tax/investment and no raids exactly
reproduces the reported mechanism-panel means. Drought welfare/shortfall/raid
harm/private utility are **0.848654 / 0.000897 / 0 / 1.038674**, compared with
coevolved **0.846926 / 0.002050 / 0.534878 / 0.965109**. The private utility gain
is 7.6225%. This confirms a serious missing-baseline problem.

There are **12 existing environment tuples, 108 focal scenarios and 216 paired
rollouts**, not independent search replications. Greedy welfare improves/ties/
worsens in 23/84/1 cases against coevolution. Other societies' mean welfare is
**0.001030 lower**, and whole-world mean welfare is descriptively 0.000110 lower.
Zero raid losses do not imply no externalities. The policy bundle comparison
does not isolate raid removal; evolved society 1 also enabled new raid behavior.

The engineering review confirmed exact diagnostic-float comparisons in the
calibration verifier; it did not reproduce the external 72/576 last-bit count.
The mentioned tolerance patch was absent. Plan a separate portable verifier,
preserving exact bytes and qualification decisions. Search evaluators already
enforce 1 GiB memory and 120 CPU-second limits; consistent protection is needed
for the other untrusted paths. The v2 pilot used 13 started calls, 11 completed
proposals and two budget interruptions. Selection exists, but the negligible
margin, single runs and absence of reciprocal revisits limit inference.

The proposed sequence is: portability and execution hardening; new local
spatial physics; verified unilateral temptation and collective losses; optional
institutional formation and costed enforcement; strong fixed/numerical baselines;
then a separately budgeted pilot and replicated search. Do not make favorable
institutional emergence or a positive coevolution effect a completion gate.
Keep position, membership and jurisdiction distinct and track outsiders' costs.
No new experimental model spending is authorized by this planning request.

Independent scientific and engineering reviews passed after correcting two
document links. All six archived diagnostic artifact hashes, eight frozen
external-input hashes, 17 figure source hashes and five figure output hashes
pass. The five original diagnostic copies remain byte-identical. The PNG was
inspected; all six gallery files rerender byte-identically. No frozen simulator,
protocol or earlier evidence was changed. No new model calls or searches were
made; no v3 implementation is claimed. Verification receipt:
`runs/review-v3/archive-render-verification.json`.

## Costed experiment evaluation completed, 7 October 2026

The user authorized the next implementation and requested GitHub synchronization.
All completed private-sharing and allocation-decision code, reports, frozen
evidence and figures were committed and pushed as `7eea67c`; remote `main` was
independently checked at that hash. Earlier historical notes about uncommitted
work describe the preceding checkpoints. The costed experiment code, tests,
evidence, figures and documentation are included in the commit containing this
checkpoint, following `7eea67c` on `main`.

One-shot selection now chooses Early, Late or Split investment of an exact
escrow from existing resources, under the unchanged stepwise physical engine.
Fixed Split and a precommitted uniform Random schedule are controls. A separate
zero-investment redistribution path measures opportunity cost. Updated and
frozen-coefficient downstream planners share the same latest legal state;
their contrast measures posterior-update value on each physical path.

- Selector: `swarm_societies/world_model_v1/experimentation.py`.
- Frozen runner/protocol: `scripts/run_world_model_experiment.py` and
  `docs/world-model-experiment-protocol.md`, with 14 archived source files.
- Completed development and evaluation: `evidence/world-model-experiment-development-v1/`
  and `evidence/world-model-experiment-v1/`. **Do not restart either bank.**
- Report: `docs/world-model-experiment-v1.md`; README retains every prior study
  and adds methods, results, limits and reproduction for this control.
- Six inspected Chromatic Field figures in SVG/PDF/PNG, four CSV tables,
  captions and source/output hashes under `figures/world-model-experiment-development-v1/`
  and `figures/world-model-experiment-v1/`. All 26 gallery files repeat
  byte-identically. Renderer: `scripts/visualize_world_model_experiment.py`.

The six-arena development gate passed: 18 focal states, 72 probe paths and
216 continuations. Active selected Early 17 times and Late once, with 18 proxy
advantages over Split; updating changed 13 of 54 cost-matched allocations.
No operation failed. Its descriptive active-minus-random update-value effect
was −0.006280: readiness did not require favorable performance. The full gate
was independently replayed before the evaluation freeze. A pre-freeze numerical
smoke case, whose performance outcomes were not inspected for tuning, is
preserved separately under `evidence/world-model-experiment-smoke-v1/`.

The separate evaluation completed **24 independent arenas**, **72 nested focal
states**, **288 physical probe paths** and **864 allocation continuations**.
Its **primary active-minus-random posterior-update-value contrast is −0.000969
[−0.005181, 0.002920] per member**. There is no clear added update value.
Total updated-policy utility improves by **+0.005722 [0.000791, 0.010645]**,
but **+0.006691 [0.003687, 0.010896]** is already present with frozen
coefficients; the two terms decompose the total contrast exactly.

Active selected Early in **71/72 states**. The post hoc always-Early comparison
has exactly zero difference in update value and a descriptive −0.000100 total
utility difference. The Fixed Split control does not establish an advantage
over fixed timing generally. Active-minus-random post-probe CRPS is unresolved:
+0.000751 [−0.010876, 0.011920]. Against zero-investment redistribution, Active
has unresolved total utility **−0.014685 [−0.043589, 0.013016]**, with lower
consumption **−0.018790 [−0.037911, −0.002780]**. All secondary intervals are
unadjusted. Repayment of the experiment's opportunity cost is not established.

Every cost-matched path spends its exact escrow, averaging 3.396947 resource
units per focal institution. Every path adds eight institutional home events
and sends/delivers 80 KiB per focal society. Wealth-capped effort charges differ
among schedules in five focal states: equal investment and bytes do not match
all realized costs. All updates and forecasts succeeded. Outward harm is zero
by prescribed policy, not learned restraint. Measurements and updates on
counterfactual paths are dependent, not new independent replications.

The full suite passes **352 tests and 102 subtests**, including 31 selector and
39 runner tests. Aggregation checks one full case at a time and retains a small
scalar projection to limit RAM; semantic verification still refits full learners
and replays complete physical branches. Both 14-source freezes match the
workspace; all 32 development and 49 evaluation artifact hashes pass; all 33
copied development-proof files match the canonical bank byte-for-byte.
The final full replay passed for all 24 evaluation and six copied development
cases, including reconstructed tables, summaries and gate results. Independent
CSV calculations reproduce all reported means and whole-arena intervals.
Logs, independent audit outputs and a hash-linked verification receipt are
retained under `runs/world-model-experiment-verification/`.

Execution logs are retained in `runs/world-model-experiment-development-v1.log`,
`runs/world-model-experiment-prepare.log`, `runs/world-model-experiment-evaluation-v1.log`
and `runs/world-model-experiment-tests.log`. No new evolutionary search or
experimental model-generation calls were used. No source or gate criteria were
changed after freeze. Preserve the 1,024-particle/four-sweep default, conditional
ecological interpretation and unresolved shared likelihood-CDF departure.

Next: separately specify a supplied-mechanism-family comparison before
structural discovery. Adaptive experiment sequences, hidden external features,
confidence-based reports and any new model-driven search remain separate stages.

## Allocation decision control completed, 6 October 2026

The user authorized proceeding to the next clear step: determine whether learned
laws improve a consequential allocation. New, separately versioned stepwise
engine and fixed approximate planner are implemented; earlier frozen simulators
remain unchanged. Development and the fresh evaluation are complete. **Do not
restart either completed experiment.** The runner refuses to overwrite them.

Development selected home-only harvesting, 32 warmup ticks using the previous
staggered investment schedule, then one focal allocation from {0,.5,1} and 32
ticks of zero-investment continuation. Use existing consumption + .2 terminal
wealth utility; report consumption welfare separately. Preserve initial wealth
4 and all physical constants. The six-arena development gate passed before the
fresh 24-arena evaluation was prepared. Exploratory grids are preserved under
`runs/decision-development-exploration/`, not final-panel evidence.

- Engine/planner: `swarm_societies/ecology_stepwise_v1.py` and
  `swarm_societies/world_model_v1/decision.py`, with exact legacy episode,
  actor-observation, accounting and RNG parity and strict snapshot restoration.
- Frozen protocol/runner: `docs/world-model-decision-protocol.md` and
  `scripts/run_world_model_decision.py`. Source snapshots accompany both banks.
- Report: `docs/world-model-decision-v1.md`; README incorporates the new study
  while preserving all earlier detailed results.
- Three evaluation figures and one separate development figure in Chromatic
  Field v1, each in SVG/PDF/PNG, with five CSV tables, captions and source/output
  hashes: `figures/world-model-decision-v1/` and
  `figures/world-model-decision-development-v1/`.

All belief conditions use the same legal institution payload and delivered
prior-tick home observation. Current growth, actual current tax receipts,
productivity and simulator/RNG snapshots remain outside the planner. Forecasts
are committed before protected branches. The known-law reference retains the
same nominal-productivity, lagged-stock and external-infrastructure approximations.

The six-arena gate completed and passed: 17/18 robust same-state ranking switches,
11 realized redistribution-favoring states, six full-investment-favoring states,
and seven known-law investment choices with positive realized benefit. Zero
failed forecasts. Evidence: `evidence/world-model-decision-development-v1/`.
Evaluation preparation independently verified these cases and copied their full
provenance. The evaluation archive is `evidence/world-model-decision-v1/`.

The primary learned-minus-prior utility effect is **+0.021110 per member**, with
95% whole-arena interval **[0.009014, 0.033678]**, or **0.0675%** of the prior
mean. Prior / learned / known-law utility is **31.282372 / 31.303481 / 31.307353**.
Terminal wealth contributes **85.7%** of the gain. The consumption contrast is
only **+0.003028 [0, 0.009084]** over 32 ticks, and all additional consumption is
in **one independent arena**. Do not claim a general consumption-welfare gain.
External harm is zero by the fixed no-raid policy, not a learned reduction.

Learning changes 35/72 focal choices (33 improved utility, two worsened it).
Prior / learned / known-law realized menu regret is **0.026949 / 0.005840 /
0.001968**; its contrast algebraically repeats the utility contrast. Learned
and known-law choices agree in 62/72 states. This is one supplied-law allocation
task, not autonomous experimentation, structural discovery or evolved governance.

Independent units: **24 law/environment arenas**, with **72 nested focal
states**, **216 physical continuations** and **216 valid belief-condition
forecasts**. Six development arenas are separate. There are **2,304 distinct
warmup measurements**, **20,736 accepted owner-specific updates**, **20,160
duplicate attempts**, 360 learner models and zero failed updates. All protected
world, learner, transport and RNG states remain unchanged by evaluation branches.

Full verification independently refitted/replayed all 24 evaluation cases and
the copied six-case development proof, reconstructed summaries and checked
41 main artifact hashes. Both 11-source freezes still match the workspace;
the copied development archive is byte-identical to its original. Full suite:
**282 tests and 102 subtests passed**. All four PNGs were inspected, and all
21 gallery files repeat byte-identically. No new evolutionary search or
experimental model-generation calls were used. No Git commit or external
publication was performed.
Replay output, full test log and a hash-linked verification receipt are retained
under `runs/world-model-decision-verification/`.

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_world_model_decision.py verify
.venv/bin/python scripts/visualize_world_model_decision.py
.venv/bin/python scripts/visualize_world_model_decision_gate.py
.venv/bin/python -m pytest -q
```

Next controlled stage: design costed active experimentation against fixed and
random interventions with matched resource/communication budgets, separating
information value from direct material effects. Keep structural discovery and
any new model-driven search separately specified. Preserve the 1,024-particle,
four-sweep default, conditional ecological interpretation and calibration
audit's shared borderline likelihood-CDF departure.

## Private-belief sharing study recovered and completed, 6 October 2026

Resumed after connection loss and completed the frozen 24-arena study. All
earlier simulator, learner, protocol and evidence files remain unchanged.
The separately versioned `scripts/resume_world_model_sharing.py` semantically
verified and reused arenas 000–011 byte-for-byte, archived 14 interrupted files,
and recomputed unfinished arenas 012–023 using the same frozen sources/seeds.
Recovery took **920.13 seconds** with four workers; this is recovery time only,
not the original interrupted study's full wall time. The completion manifest
is present. **Do not restart this completed experiment.**

- Runtime: `swarm_societies/world_model_v1/sharing.py`; twelve member and three
  institutional models per arena/condition, canonical event provenance,
  truthful fixed reporting, per-owner deduplication, charged bytes and delay.
- Frozen study: `scripts/run_world_model_sharing.py`,
  `docs/world-model-sharing-protocol.md`, `evidence/world-model-sharing-v1/`.
- Report: `docs/world-model-sharing-v1.md`; paper-style README updated without
  removing prior study results. Next-stage plan: `docs/world-model-decision-plan.md`.
- Five Chromatic Field figures in SVG/PDF/PNG, five tables and source/output
  hashes: `figures/world-model-sharing-v1/`; renderer
  `scripts/visualize_world_model_sharing.py`.

Member time-average CRPS: isolated/redundant **0.260293**, complementary
**0.258516**, delayed **0.259564**, legal union **0.257289**. The primary
complementary-minus-redundant paired effect is **−0.001778**, with 95% whole-arena
interval **[−0.002939, −0.000604]**, or **0.68%** lower error. Terminal effect
**−0.000114 [−0.000238, +0.000010]** remains unresolved. At equal evidence counts
the contrast reverses: **+0.003363 [0.001506, 0.005242]**. Do not claim improved
inference per event. Equal counts can contain different examples/order.

Redundant and complementary reports each cost **1,272 KiB per society**.
Complementary sharing adds 126 unique events per member; redundant copies add
none. Delayed sharing adds 120, with 1,248 KiB actually sent before the horizon:
it matches capacity and origin schedule, not finite-horizon delivered bytes.
Delay increases time-average CRPS by **0.001048 [0.000382, 0.001842]**.

There are **9,216 distinct physical measurements**, **549,288 successful
owner-specific updates**, **152,568 duplicate attempts**, zero failed updates,
and **1,800 terminal models**. Independent units are the 24 shared-law arenas,
not members or reports. No new evolutionary search or model-generation calls.
Complementary member r/b/g coverage is **91.67% / 83.33% / 89.24%**, averaged
within arenas. Preserve the conditional ecological model and the calibration
audit's unresolved shared likelihood-CDF departure.

All 24 arenas passed semantic reconstruction during recovery and a separate
final verification pass. The latter checks **281 artifact hashes**, **22,680
checkpoints**, **68,040 parameter rows**, **1,451,520 prediction rows** and
**115,200 regenerated terminal forecasts**. Original per-arena checks ran in
four workers before canonical aggregation checks; full evidence hashes remained
unchanged. Intermediate posterior trajectories were not refitted. All five PNGs
were inspected, and all 22 figure-directory files repeat byte-identically.
The complete suite passes **194 tests and 35 subtests**. Original experiment,
mechanism, world-model and 192-case calibration evidence verifiers pass.
Recovery records, the final verification receipt and its execution harness
remain under `runs/world-model-sharing-recovery/`; for future
interrupted reproductions use the recovery command, since the frozen original
`run` command recomputes every case in an incomplete study.

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_world_model_sharing.py verify
.venv/bin/python scripts/visualize_world_model_sharing.py
.venv/bin/python -m pytest -q
```

Historical next-step note (completed in the decision study above): versioned
stepwise ecology with exact trajectory/RNG parity, then a development
action-ranking gate and fixed-planner comparison
using learned beliefs, the prior and known coefficients. No decision experiment
had been implemented or run at that checkpoint. Active experimentation and
structural discovery remain later stages. The sharing report records a nonproduction oversized
forwarded-frame edge case for future runtime hardening; do not modify frozen v1
to handle a new identifier contract. No Git commit or external publication was
performed during this recovery.

## Independent world-model calibration audit completed, 6 October 2026

The next clear implementation step was to test parameter uncertainty before
using it for institutional information governance. Implemented and ran a new,
prospective audit without modifying the published learner or earlier evidence.

- Independent batch posterior: `swarm_societies/world_model_v1/reference.py`;
  four Metropolis chains, separately implemented likelihood, explicit convergence
  gates, mean Monte Carlo errors, and a prescribed retry with both attempts saved.
- Frozen design and semantic verifier: `scripts/run_world_model_calibration.py`;
  `docs/world-model-calibration-protocol.md`; `evidence/world-model-calibration-v1/`.
- Report and implementation decision: `docs/world-model-calibration-v1.md`;
  paper-style README updated with the new methods, results and limitations.
- Four Chromatic Field figures in SVG/PDF/PNG and five statistical tables:
  `figures/world-model-calibration-v1/`; source/output manifest and deterministic
  renderer `scripts/visualize_world_model_calibration.py`.

128 independent prior-predictive datasets plus 64 new ecological arenas.
All **192 final references qualified**, with one prescribed retry. There were
**40,960 distinct observations**, **81,920 successful SMC updates**, and zero
failed updates. No new evolutionary search or model-generation calls.

Published SMC/reference mean gaps average **0.0451 posterior SD** in the controlled
panel and **0.0424 SD** in ecology. Higher compute lowers them to **0.0255/0.0284**,
near reference Monte Carlo uncertainty, at **4.26×/4.91×** fitting CPU cost.
Published/reference interval-width ratios average **0.990–1.002** by coefficient
and panel. Retain the published **1,024 particles/four sweeps** as the default.

Fresh ecological spillover coverage is **57/64 (89.06%)** published and
**58/64 (90.63%)** higher/reference. The earlier 18/24 result did not recur.
Do not claim calibration fully solved: reference ecological renewal coverage is
**53/64 (82.81%)**, and the controlled likelihood-CDF statistic has a shared small
departure. Maximum ECDF deviation is **0.11800/0.12100/0.12275** for published,
higher and reference, against a single-ECDF 95% DKW bound of **0.12004**.
All coefficient CDF curves fall within the band, including the frozen-prior
negative control; its likelihood-CDF deviation is **0.99707**.

Verification rebuilt all 192 datasets, 2,304 coefficient rows, 3,072 CDF rows,
1,728 agreement rows and **4,283,648 stored sample likelihoods**, checking 401
artifact hashes. The complete suite passes **126 tests and 35 subtests**.
Original experiment, mechanism and first world-model evidence verifiers pass.
All new figure PNGs were inspected; repeat rendering is byte-identical.

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_world_model_calibration.py verify
.venv/bin/python scripts/visualize_world_model_calibration.py
.venv/bin/python -m pytest -q
```

Next implementation: private member belief state and bounded institutional
reports, with evidence provenance, deduplication, delay and matched bandwidth.
Begin with fixed truthful report rules and existing instrumented sensing;
compare no sharing, bounded sharing and the pooled information ceiling.
Keep uncertainty conditional on the fitted model. Defer confidence-based report
selection and hidden-feature inference until their observation model and
calibration diagnostics have separate frozen controls.

## First learnable world model implemented and evaluated, 6 October 2026

Implemented the next approved stage and completed its frozen local experiment.
The user also requested GitHub publication, an informative About description,
and a README maintained as a living research paper with Chromatic Field results.

- New engine: `swarm_societies/ecology_world_model_v1.py`, parameterized laws,
  phase-stamped local measurements, private action receipts and institutional
  accounts. Default material trajectories/digests exactly match frozen v2.
- Learner: `swarm_societies/world_model_v1/learner.py`, bounded renewal-law SMC,
  1,024 particles, four posterior-preserving rejuvenation sweeps, exact hidden
  weather/capacity/noise likelihood, deduplication and restorable state.
- Study: `scripts/run_world_model_study.py`, with frozen design/source snapshots,
  shadow updates, independent held-out probes and semantic evidence verification.
- Report: `docs/world-model-v1.md`; paper-style root `README.md`; previous README
  preserved with relocated links in `docs/first-study-report.md`.
- Portable evidence: `evidence/world-model-v1/`; recorded-data SVG/PDF/PNG figures
  and tables: `figures/world-model-v1/`.

Twenty-four independent shared-law arenas, three societies each, 128 ticks.
Unknowns are baseline renewal, local infrastructure return and external
spillover. Fixed policies and full infrastructure audit sensing isolate a first
stationary identification control. Private models see their own patch events;
the pooled reference sees all three patch histories. No structural discovery,
learned action selection, communication governance or new evolutionary search.

Primary time-averaged held-out CRPS (lower is better): prior **0.942235**,
private **0.308766**, pooled **0.270321**. Pooled minus private:
**−0.038445**, 95% paired arena interval **[−0.047006, −0.030612]**.
Terminal CRPS: private **0.249648**, pooled **0.248053**. Pooling has three times
as much evidence per tick; the result does not establish inference efficiency.

Predictive 90% interval coverage is **88.98%** private and **89.06%** pooled.
Parameter calibration is weaker: the pooled spillover interval covers truth in
only **18/24 arenas (75%)**. Preserve this limitation; investigate calibration
and compute sensitivity on new independent data before relying on these beliefs.

All **18,432 learning updates** succeeded on **9,216 distinct environmental
events**. Evidence verification checks 1,512 checkpoints, 96,768 recorded probe
scores, and regenerates 7,680 terminal forecasts from saved snapshots. Full suite:
**90 tests and 14 subtests passed**. Original experiment and mechanism evidence
verifiers also pass. No original simulator or frozen protocol was edited.

```bash
.venv/bin/python scripts/run_world_model_study.py verify
.venv/bin/python scripts/visualize_world_model_study.py
.venv/bin/python -m pytest -q
```

Next: resolve parameter interval undercoverage; add private member learners and
institution-mediated reports under local sensing and matched bandwidth. Then
add costed exploration, changes in physical laws versus opponent behavior,
model-guided decisions and structural discovery. Existing inference allowances
remain exhausted; this local numerical study made zero model-generation calls.

## World-model research and proposal, 6 October 2026

The user prioritized learning the laws of the shared world and selected
**both parameter learning and structural discovery, in stages**. The research
and proposed design are complete; no world-model runtime, learner or new
world-model experiment has been implemented or run.

- `docs/world-model-proposal.md`: proposed mechanism-specific probabilistic
  learners, private and institutional knowledge, active experimentation,
  parameter learning followed by equation discovery, and evaluation design.
- `docs/world-model-literature.md`: 30 annotated primary sources, covering
  model-based control, identification, symbolic discovery, multiagent world
  models, communication, causal effects and proper scoring. Recent preprints
  are distinguished from published work; recommendations are a synthesis.
- `docs/world-model-implementation-plan.md`: observation/receipt contract,
  module interfaces, lifecycle, isolation requirements and acceptance checks.
- `figures/world-model-design/`: Chromatic Field design diagram in
  SVG/PDF/PNG, with renderer and provenance; not experimental evidence.

The critical finding is that current stock and wealth observations confound
several mechanisms. Add versioned, phase-stamped receipts and patch sensors
before claiming coefficient identification. The primary renewal learner is
a bounded, weather-aware particle posterior; regression is an approximate
control on designed uncapped data. Never discard observed saturation as if
it were missing at random. Deduplicate shared evidence without assuming
different patches or ticks are statistically independent.

Measure learning on frozen probe designs instantiated under each arena's own
hidden laws. Keep physical-law learning, hidden-state inference and opponent
modeling separate. Use arena-level replication, uncertainty/calibration and
intervention tests; welfare alone is not a learning score.

Next implementation stages, in priority order:

1. Versioned instrumented ecology and protected evaluation boundary; preserve
   legacy trajectories at reference parameters.
2. Stationary parameter learners, identification controls, and passive
   information-sharing comparisons with recorded learning figures.
3. Costed active experiments, physical-versus-social change detection, and
   fixed-planner comparisons.
4. Explicit rule selection, then structural revision with declared grammars,
   separate numerical fitting and untouched final intervention tests.

This supersedes the order of next work in the earlier resumption record below.
Prior protocols, results and exhausted search budgets remain unchanged.
The diagram was inspected and reproduced byte-identically. All nine recorded
source/artifact hashes, local links in eight related documents, and the
30-entry reference sequence verified; `git diff --check` passed. These are
documentation/renderer checks, not validation of an implemented learner.

## Resumption completed on 6 October 2026

Completed the requested repository audit, primary-literature research, and
Chromatic Field visualizations. Also evaluated a local factorial diagnostic on
saved programs: no new evolutionary search, model inference, or budget
extension. The user's ongoing visualization preference is recorded in
`AGENTS.md` and `docs/visual-reference.md`.

- Research roadmap: `docs/research-roadmap.md`, with 16 annotated primary
  sources and eight prioritized experimental directions.
- Consumption pilot figures: `figures/consumption-v2/`, with three
  SVG/PDF/PNG figures, portable scalar case data, CSV tables and provenance.
  Renderer: `swarm_societies/visualize_consumption.py`.
- New diagnostic: `docs/mechanism-study.md` and `evidence/mechanism-v1/`.
  Four component combinations, source programs, 432 paired case rows,
  864 rollout outcomes, contrasts and frozen design are portable.
- Diagnostic figures: `figures/mechanism-v1/`, with factorial outcomes,
  institutional welfare effects and institutional harm effects by society.
  Renderer: `scripts/visualize_mechanism_study.py`.

The diagnostic crosses original/evolved members with original/evolved
institutions on twelve new environment/timing tuples, three opponent panels
and three focal society identities, each with a matched no-drought control.
The design was frozen before evaluation. This is a post-hoc investigation of
one selected lineage, not independent search replication.

Welfare on the new bank: initial **0.844263**, evolved members only
**0.845106**, evolved institutions only **0.845648**, both **0.846926**.
The welfare interaction is **+0.000434**, with a descriptive environment
cluster interval **[−0.000550, +0.001612]**. Positive welfare complementarity
remains unresolved. With evolved members, swapping institutions adds
**0.076462 outward harm units/tick**; with original members it adds exactly
zero harm. Extra harm is concentrated in society 1. Society 2's unchanged
institution provides an exact negative control.

The audit verifies sources, scenario definitions, case/member coverage,
summary arithmetic, conservation, paired effects and negative controls.
Eight production rollouts regenerated exactly from relocated source snapshots.
All six new PNGs were inspected, and both figure series reproduce identical
exports. Tests reject altered summaries, case banks and manifest links.
Final test suite: **50 tests and 6 subtests passed**.

```bash
.venv/bin/python scripts/verify_mechanism_evidence.py
.venv/bin/python scripts/visualize_mechanism_study.py
.venv/bin/python -m swarm_societies.visualize_consumption
.venv/bin/python -m pytest -q
```

Next work, in order:

1. Isolate raid permission, report content and private/shared memory. The
   full-program intervention does not identify which rule caused extra harm.
2. Map scarcity and drought regimes: all cooperative-opponent v2 cases reached
   the welfare ceiling. Welfare and shortfall are redundant endpoints.
3. Test unfamiliar partners, selfish entrants and a distributed-information
   task. Current institutions are central hubs; spatial swarms are future work.
4. Plan replicated searches with several update cycles. V2 stopped after
   `M0, I0, M1, I1, M2`; no member was reevolved after its institution changed.
   The schedule revisits a member after 24 proposals. A new campaign needs a
   separately declared inference budget; do not extend old allowances.

No external publishing or Git commit was performed during this resumption.

## Completed consumption pilot from 5 October 2026

Original objective: run the consumption-focused follow-up to the completed
first experiment, authorized on 2026-10-05.

**Completed:** both 30-minute arms exhausted their original allowances and
fresh evaluation finished at 2026-10-05 05:51:42 UTC (07:51:42 Europe/Berlin).
All search and evaluation processes have stopped. No budget was extended.
Fixed institutions retained six member changes; coevolution retained three
member and two institutional changes. All 11 evaluated mutations were valid.

Fresh consumption welfare: initial .843162, fixed institutions .846405,
coevolution .847238. Coevolution had 23.2% less unmet consumption than fixed
institutions, but 65.2% more outward harm and 1.8% lower private utility per
tick. Both evolved populations improved consumption relative to initial.
Only one paired pilot was run; the small welfare difference is exploratory.
Compact results and audit: `evidence/consumption-v2/final-summary.json` and
`completion.json`. Full member rows and search archives remain in local
checkpoints. Scalar case data needed for plotting are now portable in
`figures/consumption-v2/`; the new diagnostic also contains executed sources.

Question: does institutional coevolution improve consumption welfare compared
with equal-budget member-only search under fixed institutions? V2 removes the
direct infrastructure bonus, varies horizon (48/60/72 ticks) and drought timing,
and evaluates exact matched no-drought counterfactuals. Both arms start from the
same original mixed population. Private utility remains separately selected
and measured. One paired pilot does not establish a replicated search claim.

Frozen protocol: `docs/protocol-consumption-v2.md`. Code, prompt, source and
scenario definitions are hashed before search. Candidate feedback contains
aggregate objectives/outcomes; exact schedules and fresh cases are excluded.
The route remains actual upstream ShinkaEvolve through ChatGPT-authenticated
Codex, `gpt-6-astra`, `xhigh`, `fast`. No paid API or auxiliary inference.

At v2 completion, all 46 tests passed; frozen first-experiment evidence still verifies
and its replay regenerates exactly. V2 material dynamics match v1; no-drought
pairs preserve exogenous draws. The v2 search benchmark measured 3.63 episodes/s
and 21.9 MiB peak RSS. Compact launch evidence: `evidence/consumption-v2/`.

Automatic fresh evaluation completed all 648 rollouts: initial population and
both final populations, each with 108 drought cases and 108 matched no-drought
counterparts. Saved results: `runs/consumption-v2/fresh/summary.json`.
The follow-up figures and a component-level diagnostic are now complete;
the next research steps appear above. Do not start additional inference
without a new run budget. Independent paired replications are needed before
claiming an advantage for the search procedure.

```bash
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --status
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --resume
```

The campaign is complete; resume will not start additional search. Per-arm
budgets cannot be extended on resume. Full native archives, ecological state,
source snapshots, model traces and accounting remain in ignored
`runs/consumption-v2/pair-01-*/`. See `docs/consumption-v2-run.md` for all commands.

The first work package was published as commit
`0073a0d26aeb1e8b40ab65535d47050c42feb72a`. Its evidence/figures remain unchanged.
Its 60-minute search retained three member and three institutional changes;
higher welfare came from the infrastructure bonus while consumption shortfall
worsened. Full original checkpoints remain in ignored `runs/first/`, exhausted.
