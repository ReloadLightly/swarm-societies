# Active work record

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
