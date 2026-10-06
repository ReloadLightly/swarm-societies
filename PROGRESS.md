# Active work record

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
