# Commons v3: separate ecological and incentive qualification

**Both frozen banks are complete. The primary joint verdict is unresolved;
broader incentive qualification fails.**
Both protocols, designs and source closures were pushed before any qualification
episode ran. Both frozen controls pass the ecological criteria in five of nine
cells, including the reference. Two other cells are certified insufficient for
the stated consumption target, and two remain physically unresolved. Two
reference-containing adjacent pairs pass ecology. All 288 ecological episodes
replay exactly, the independent audit passes, and all 144 ecological case files
restore byte-identically from the public archive and offline cache. These
results alone do not establish incentive qualification. The complete
[incentive report](commons-v3-incentive-qualification-results-v1.md) retains
all preregistered verdicts, weights, storage sensitivities and peer curves.
Further ecology publication, figure and audit layers are deferred under the
[latest review response](commons-v3-review-2026-10-07.md).

This study tests the two strongest retained local controls from the
[navigation stage](commons-v3-navigation-v1.md) on new seed banks. It asks
whether they witness finite-horizon ecological viability and whether a supplied
aggressive substitution creates both a material private incentive and sustained
population consumption harm. The physical engine, controller parameters and
utility weights remain unchanged. A failed or unresolved gate is a valid
scientific result. The study contains no institutions, political membership,
experimental model calls, new policy selection or evolutionary runs.

## Prospective freeze and independent sampling units

The [ecological protocol](commons-v3-ecology-qualification-protocol-v1.md),
[incentive protocol](commons-v3-incentive-qualification-protocol-v1.md),
[physical-bound derivation](commons-v3-feasibility-v1.md) and copied source
closures were pushed as
[b44ee25](https://github.com/ReloadLightly/swarm-societies/commit/b44ee25bb36e7b3eeb9f27031e8580cdf0b27fd1).
The [push receipt](../evidence/commons-v3-qualification-validation-v1/freeze-push.json)
records independent remote-head verification and zero qualification episodes
before that push. Both protocols were frozen together: ecological outcomes
cannot revise the later incentive panel.

The [ecological design](../evidence/commons-v3-ecology-qualification-v1/design.json)
uses seeds **64001–64016**. The separate
[incentive design](../evidence/commons-v3-incentive-qualification-v1/design.json)
uses **65001–65016**. Both lists are disjoint from earlier development banks.
The independent sampling unit is a seed realization, giving **16 per stage**.
The same seed recurs across a stage's controls, cells and conditions; these
repetitions, individual agents and ticks are not additional independent samples.

| Stage | Configurations | Episodes | Physical ticks | Individual decisions |
| --- | ---: | ---: | ---: | ---: |
| Ecology | 144 | 288 | 147,456 | 3,538,944 |
| Incentive primary grid | 144 | 2,880 | 737,280 | 17,694,720 |
| Incentive reference sensitivities | 80 | 480 | 147,456 | 3,538,944 |
| Incentive total | 224 | 3,360 | 884,736 | 21,233,664 |
| Both stages | 368 | 3,648 | 1,032,192 | 24,772,608 |

Both banks have completed their full design counts. All counts exclude
replays. Independent evolutionary runs and experimental model calls are both
zero. Neither bank was restarted or extended during the review response.

## Physical world and frozen local controls

The base world has 24 mobile individuals, 16 resource sites on a 12×12 grid,
radius-one sensing, carrying capacity 80, initial inventory 2, and site
capacity/initial stock 40. Movement and extraction costs are both 0.02.
Stock-dependent renewal rates 0.12/0.24/0.36 cross consumption needs
0.8/1.2/1.6. The fixed reference is renewal 0.24 and need 1.2.

| Control | Desired food buffer | Voluntary stock floor | Route rule |
| --- | ---: | ---: | --- |
| Fixed floor | 2 ticks of need | 0.5 of site capacity | Travel-adjusted yield |
| Selected | 4 ticks of need | 0.5 of site capacity | Nearest site |

The selected controller is bound to the prior navigation
[selection record](../evidence/commons-v3-navigation-v1/selection.json),
SHA-256 4665d982a65e08ac65dc0244b341a0cf519da2f417964b65414d4e271369cadc.
No qualification result can select another parameter setting. Both controllers
use only legal local observations and their own memory; horizon, seed,
renewal parameters, feasibility bounds and global diagnostics never enter
the actor's observation packet. A voluntary floor is an individual request
rule, not an enforced aggregate quota.

The aggressive variant retains its background's route mode while removing
need targeting and the voluntary floor. Realized movement, inventory and
ecological paths can change. The contrasts therefore concern whole-policy
substitutions, not isolated extraction mechanisms, private optima or equilibria.

## Ecological gates and physical certificates

Ecological episodes last **512 ticks**. For each cell and control, the gate
uses these five seed-level endpoints:

| Endpoint | Required simultaneous bound |
| --- | --- |
| Mean consumption / need | Lower ≥ 0.95 |
| Final-quarter consumption / need | Lower ≥ 0.95 |
| (Fourth-quarter minus third-quarter consumption) / need | Lower ≥ −0.02 |
| Mean final-quarter total stock / total capacity | Lower ≥ 0.20 |
| Final-quarter depleted-site-time fraction | Upper ≤ 0.10 |

The third quarter is ticks 257–384 and the final quarter is 385–512.
A site is depleted when its stock after renewal is strictly below 10% of
capacity. All five criteria must pass for a control to pass a cell. The
ecological component of qualification requires both controls to pass in both
cells of an adjacent pair containing the reference; adjacency is one horizontal
or vertical step in the declared grid. The descriptive 256-tick prefix comes
from the same rollout and supplies neither another episode nor another replicate.

Separately derived conservative consumption certificates cover horizons 256
and 512 and the final 128-tick window, at full need and the 0.95 target. They
retain extraction costs, initial resources, a stock-dependent growth ceiling,
bounded weather and explicit floating arithmetic allowances. Final-tick renewal
cannot fund final-tick consumption. Access, movement and contention restrictions
are relaxed only in directions that increase the possible consumption bound;
late-window bounds permit full inventories and site stocks at the boundary.
Canonical bounds and comparisons use exact rational arithmetic.

The report distinguishes three statements:

- **Certified insufficient:** the conservative upper bound lies strictly below
  the stated consumption target for the stated horizon/window.
- **Witnessed viable:** at least one named frozen legal controller passes every
  operational ecological criterion. The qualification pair still requires both.
- **Feasibility unresolved:** no controller witnesses viability and the bound
  does not exclude the target. This does not establish physical impossibility
  or quantify what a better controller could recover.

A permissive upper bound is not a feasible allocation or an optimal policy.
The ecological gate establishes finite-horizon evidence, not indefinite
sustainability. The longest latter-half run with at least half the sites
depleted is also recorded; a run of at least H/8 ticks is a descriptive
persistent-depletion diagnostic, not an alternative admission criterion.

## Matched peer populations and material-effect gates

The incentive primary grid lasts **256 ticks**. Each seed fixes one focal
identity and a nested order of its 23 peers before execution. At
**0, 6, 12, 18 and 23 aggressive peers**, two branches retain identical peer
assignments while changing the focal from restrained to aggressive. This gives
10 arms per control. Peer prevalence is k/23; whole-population prevalence is
k/24 or (k+1)/24 depending on the focal branch.

For each cell and both controls, the primary gate requires simultaneous lower
bounds on three paired differences, normalized by need:

| Contrast | Required lower bound |
| --- | ---: |
| Focal utility gain at zero aggressive peers, wealth weight 0.05 | 0.01 |
| All-restrained minus all-aggressive mean population consumption | 0.05 |
| The same population consumption loss in the final quarter | 0.05 |

Private utility is cumulative consumption plus weight times terminal inventory,
divided by horizon. Focal consumption and weighted terminal inventory remain
separately reported. Depleted stock cannot substitute for a failed
consumption-harm criterion. A **primary qualified region** requires the same
adjacent pair containing the reference to pass the ecology and all primary
incentive criteria for both controls.

The five reference sensitivities are 512 ticks, carrying capacity 8, initial
site stock 22, keyed-priority contention and additive renewal. These retain
the same incentive seeds and two controls but only three endpoint arms:
all restrained, one focal aggressive and all aggressive. Intermediate-peer
stress curves are neither executed nor inferred. Wealth weights 0/0.05/0.2
rescore the same trajectories without extra episodes.

Reference robustness is reported separately at each weight over the primary
reference and four logistic sensitivities. The **broader canonical-weight
qualification** requires both a primary qualified pair and every reference
robustness criterion at weight 0.05. Failed or unresolved stress evidence blocks
that broader claim. Changing the weight or omitting a stress test cannot rescue
it. Additive renewal is a descriptive negative control, excluded from all
robustness gates; an uncertain effect is not evidence of no effect.

## Statistical contract and retained observations

The prespecified family contains **194 named scalar intervals**: 90 ecological,
54 primary incentive and 50 reference-robustness intervals. The frozen
two-sided Student-t critical value is **4.750567324005865**, with 15 degrees
of freedom and Bonferroni family alpha 0.05. Ordinary descriptive 95% intervals
use **2.131449545559776**. Every interval is the seed mean plus/minus the
critical value times the sample standard deviation divided by the square root
of 16. Six primary-reference intervals recur in the robustness requirements,
giving 188 distinct designated estimand intervals. The frozen denominator
remains 194; this duplication makes the correction conservative and does not
authorize a retrospective reduction.

For a lower-bound criterion, lower ≥ threshold passes, upper < threshold
fails, and the remainder is unresolved; upper-bound criteria reverse those
directions. Gates use exact saved numerical comparisons, with no tolerance.
A conjunction fails if any component fails, remains unresolved if none fails
and at least one is unresolved, and passes only when every component passes.
The primary region is a disjunction over the four eligible adjacent pairs.

Coverage is approximate and model-based. Bonferroni accounts for the declared
family but does not remove seed-distribution assumptions. Zero empirical
variance does not establish universal invariance. Agents and ticks are not
treated as independent samples. Complete seed values remain available for
every endpoint and contrast; negative gains and adverse sensitivities remain
in the record. Descriptive intervals never add another route to qualification.

## Recorded ecological results

The [completed ecological summary](../evidence/commons-v3-ecology-qualification-v1/summary.json)
retains all **288 episodes**. Both controls pass every criterion in the same
five cells; both fail in the other four. The table reports mean consumption
and final-quarter consumption per individual per tick, averaged over 16
independent seeds. Status uses the simultaneous criteria, not rounded table
values.

| Renewal | Need | Fixed C | Selected C | Fixed Q4 C | Selected Q4 C | Both-control ecological status | Physical interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0.12 | 0.8 | 0.712746 | 0.719942 | 0.705128 | 0.713724 | Fail | Feasibility unresolved |
| 0.12 | 1.2 | 0.754075 | 0.761196 | 0.739664 | 0.742331 | Fail | Certified insufficient |
| 0.12 | 1.6 | 0.763324 | 0.765940 | 0.745242 | 0.744311 | Fail | Certified insufficient |
| 0.24 | 0.8 | 0.800000 | 0.800000 | 0.800000 | 0.800000 | Pass | Witnessed viable, both controls |
| 0.24 | 1.2 | 1.192293 | 1.196167 | 1.184978 | 1.190646 | Pass | Witnessed viable, both controls |
| 0.24 | 1.6 | 1.334050 | 1.359199 | 1.324073 | 1.352031 | Fail | Feasibility unresolved |
| 0.36 | 0.8 | 0.800000 | 0.800000 | 0.800000 | 0.800000 | Pass | Witnessed viable, both controls |
| 0.36 | 1.2 | 1.200000 | 1.200000 | 1.200000 | 1.200000 | Pass | Witnessed viable, both controls |
| 0.36 | 1.6 | 1.600000 | 1.600000 | 1.600000 | 1.600000 | Pass | Witnessed viable, both controls |

At renewal 0.12 and need 1.2, the conservative complete-horizon consumption
upper bound is **0.775007 of need**; at need 1.6 it is **0.581256**. Both
exclude the 0.95 target over 512 ticks under the certificate's stated numerical
model, even after relaxing access and movement restrictions. The bound is
1.0 in the remaining cells. Thus the failures at renewal 0.12/need 0.8 and
renewal 0.24/need 1.6 do **not** prove insufficient physical supply.

Those unresolved cells also retain substantial mean final-quarter stocks:
fixed/selected fractions **0.641245/0.622440** at renewal 0.12/need 0.8,
and **0.696336/0.683121** at renewal 0.24/need 1.6. High stock does not
establish accessible or sustainable supply, but it prevents interpreting the
consumption failures as demonstrated depletion of the whole commons.

At the reference, the simultaneous intervals are:

| Ecological criterion | Fixed floor | Selected | Required bound |
| --- | ---: | ---: | --- |
| Mean consumption / need | [0.988658, 0.998496] | [0.993961, 0.999651] | Lower ≥ 0.95 |
| Final-quarter consumption / need | [0.975923, 0.999040] | [0.983156, 1.001254] | Lower ≥ 0.95 |
| (Q4 − Q3) consumption / need | [−0.010611, 0.003891] | [−0.014833, 0.008383] | Lower ≥ −0.02 |
| Final-quarter stock fraction | [0.733756, 0.748495] | [0.736984, 0.746373] | Lower ≥ 0.20 |
| Final-quarter depleted-site-time fraction | [0, 0] | [0, 0] | Upper ≤ 0.10 |

The selected final-quarter interval extends above the physical consumption
ceiling because the prespecified Student-t interval is untruncated. It is
reported as computed; the mean remains below need. Zero observed depletion
gives a zero-width empirical interval and does not prove universal absence.
Neither reference control records a persistent-depletion episode.

Both the reference plus **(renewal 0.24, need 0.8)** and the reference plus
**(renewal 0.36, need 1.2)** pass the ecological adjacency requirement.
The two other eligible pairs, with renewal 0.12/need 1.2 and renewal
0.24/need 1.6, fail. Which, if any, common pair also satisfies the incentive
criteria remains a separate result.

The dependent first-256-tick reference consumption means are **1.197591**
for the fixed floor and **1.199754** for selected, compared with full-horizon
means **1.192293/1.196167**. This prefix describes the recorded trajectory;
it is not an additional independent horizon experiment.

## Incentive results and recorded-data figures

The separate [complete incentive report](commons-v3-incentive-qualification-results-v1.md)
reports all nine primary cells, all four eligible adjacent pairs, every frozen
peer count and all six reference panels. The primary adjacent-region verdict
is unresolved; reference robustness fails at weights 0, 0.05 and 0.2, and the
broader canonical-weight verdict fails. These are the original frozen gates,
not revised classifications chosen in response to the review.

The existing combined renderer is retained, but further ecology figure work
is deferred. Review figures use a separate incentive-only gallery; they do
not revise any frozen scientific source or threshold.

## Validation, preservation and reproduction

The pre-execution full repository suite passed **979 tests and 123 subtests**.
The [validation directory](../evidence/commons-v3-qualification-validation-v1/)
contains the source-freeze checks and completed ecological validation.
The [ecological semantic replay](../evidence/commons-v3-qualification-validation-v1/ecology-replay.json)
reproduces all **144 cases / 288 episodes** exactly, including recomputed
aggregates, in **1,408.910 seconds with two workers**. That timing belongs to
the replay invocation, not the original experiment.

The separate standard-library
[independent numerical audit](../evidence/commons-v3-qualification-validation-v1/ecology-independent-audit.json)
reconstructs every ecological case and all **90 ecological gate entries**
from recorded primitives, without importing the project or executing policies.
It checks source/input/artifact bindings, initialization, keyed weather,
material flows, movement and local discovery, cohort and agent endpoints,
quarter/prefix summaries, intervals and exact rational certificate decisions.
The audit's accumulation tolerances apply only to numerical diagnostics;
qualification decisions use independently reconstructed strict comparisons.
Its maximum observed numerical difference is **8.88 × 10⁻¹⁶**.

The [independent audit review](../evidence/commons-v3-qualification-validation-v1/ecology-audit-review.json)
confirms complete cell/gate inventories and the declared family accounting,
with no unresolved material findings. Recorded flows do not independently
recover unrecorded policy requests, reserves or every allocation choice.
Exact policy execution and full physical-state continuation remain the
separate semantic replay's responsibility. The certificate is conditional
on its explicit arithmetic assumptions; neither audit is a formal hardware
proof. [Complete incentive semantic replay](../evidence/commons-v3-qualification-validation-v1/incentive-replay-v1.json)
now verifies all 3,360 episodes and exact aggregate/verdict reconstruction.
No additional independent incentive raw audit was performed. The separate
incentive review gallery has been inspected and repeats
byte-identically; further ecology figure and audit layers remain deferred.

Only audited built-in policies execute. Material residuals use the fixed
relative tolerance 1e-9, per-tick extraction waste above 1e-9 halts the run,
and unaffordable known-site returns are rejected. Recorded reference episodes
verify exact physical snapshot continuation under identical future committed
actions; policy-memory checkpoint restoration is not claimed. Source hashes,
condition inventories and paired initial-state/weather bindings are retained.

The recovery runner preserves and verifies completed cases. It refuses to
overwrite a completed bank or silently resume one marked with an unexpected
engineering failure. Scientific failure does not trigger retries, omitted
cases, extra seeds or threshold changes. Earlier banks remain unchanged.

The ecological archive is public in the
[qualification release](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-qualification-2026-10-07),
targeting source checkpoint
[ead7cfc](https://github.com/ReloadLightly/swarm-societies/commit/ead7cfcec95decbdd8be213093f30b8ccec15d60).
The separate
[ecological catalog](../artifacts/commons-v3-ecology-qualification-v1/catalog.json)
restores **144 files / 58,201,356 bytes**. Its archive occupies **57,406,528
bytes**. All three public assets match local hashes.
[Publication receipts](../evidence/commons-v3-qualification-validation-v1/publication/ecology/README.md)
verify unauthenticated downloads, an empty-cache/empty-destination restoration,
per-file byte identity, and offline restoration into a second empty destination.
These operations run no simulations.

Restore the ecological raw cases in a clean checkout:

~~~bash
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-ecology-qualification-v1/catalog.json \
  --study commons-v3-ecology-qualification-v1
~~~

Add --offline to use an already verified archive cache without network access.
The incentive archive has a [separate verified public catalog](../artifacts/commons-v3-incentive-qualification-v1/README.md);
the ecological catalog does not restore it. Once each bank is complete and
its raw cases are present, verify saved artifacts and recomputed aggregates
without executing episodes:

~~~bash
.venv/bin/python scripts/run_commons_v3_qualification_v1.py verify \
  --output evidence/commons-v3-ecology-qualification-v1 --hashes-only
.venv/bin/python scripts/run_commons_v3_qualification_v1.py verify \
  --output evidence/commons-v3-incentive-qualification-v1 \
  --ecology evidence/commons-v3-ecology-qualification-v1 --hashes-only
~~~

Remove the hashes-only flag and add --workers 4 for exact semantic replay of
every recorded episode. The incentive verification additionally binds its copied
ecological dependency to the original bank. Render only completed evidence:

~~~bash
.venv/bin/python scripts/visualize_commons_v3_qualification_v1.py \
  --ecology evidence/commons-v3-ecology-qualification-v1 \
  --incentive evidence/commons-v3-incentive-qualification-v1 \
  --output figures/commons-v3-qualification-v1
~~~

Incentive publication and public/offline restoration are complete: all 224 raw
files reproduce byte-identically, with source checkpoint `e895b72`. Earlier
ecology archive identities and bytes remain unchanged. The combined renderer
above remains available for reproduction; the current review defers further
ecology figure work and uses the separate incentive-only gallery instead.
Hashes detect changed assets, but GitHub hosting is not administratively
immutable. This study neither establishes useful governance nor authorizes
model spending.
