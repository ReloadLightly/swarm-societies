# Swarm Societies: A Research Testbed for Resources and Institutions

**Living research report · 7 October 2026**

The new physical commons implements mobile individuals, local sensing and
stock-dependent renewal, with no institutions or supranational government.
The earlier nonspatial studies remain frozen. Optional institutional formation
and change are still planned; ecological qualification and strong baselines
must precede further experimental model spending.

[Study index](docs/study-index.md) ·
[Detailed archived report](docs/living-research-report-2026-10-07.md) ·
[Scientific review](docs/research-review-2026-10-07.md) ·
[Physical commons](docs/commons-v3-foundation-v1.md) ·
[Need-targeted baselines](docs/commons-v3-need-v1.md) ·
[Local navigation and numerical baselines](docs/commons-v3-navigation-v1.md) ·
[Separate qualification protocols](docs/commons-v3-ecology-qualification-protocol-v1.md) ·
[Implementation plan](docs/commons-v3-plan.md) ·
[Current checkpoint](PROGRESS.md)

## Abstract

Under what conditions do locally formed institutions improve their members'
welfare without exporting costs to outsiders, and how does the relative rate
of member and institutional adaptation change that outcome? Swarm Societies
develops executable environments for this question. Its current experiments
establish accounting, program replacement, parameter learning and controlled
information sharing. **They do not establish an advantage for evolved
governance:** an exploratory simple-harvesting baseline improves all four
reported focal averages over the saved coevolved population, while slightly
reducing outsiders' welfare. Numerical controls show supplied-law learning,
a small allocation benefit dominated by wealth, and no clear active-selection
benefit in posterior-update value. The new spatial prototype supports local
depletion. Purposeful local foraging with a voluntary stock floor now sustains
near-reference demand over longer runs; an 18-candidate numerical selection
improves only slightly over the fixed-floor baseline. Private gains remain
sensitive to storage, terminal inventory and environment. A separately frozen,
16-seed ecological panel now witnesses finite-horizon viability in five of
nine cells, certifies insufficient supply in two and leaves two unresolved.
Incentive qualification is being evaluated on its own fresh seed set.

## 1. Research question and present scope

In the legacy studies, members pursue private utility; institutions are selected for their own society's
welfare. No higher-level objective governs relations between societies. This
separation permits local gains and external harm to coexist, but does not by
itself create a consequential social dilemma or demonstrate collective
intelligence.

The proposed world separates **physical location, political membership and
claimed jurisdiction**. Membership will be optional; claims will require
material means to enforce. Zero institutions and failed cooperation remain
valid outcomes. Movement is implemented in the separate physical prototype;
institutional formation and political transitions remain future capabilities.

## 2. Related work

The independent simulator and upstream ShinkaEvolve engine draw on resource
worlds, multilevel economic adaptation, program evolution and probabilistic
world models. The [literature review](docs/world-model-literature.md),
[scientific review](docs/research-review-2026-10-07.md) and
[archived references](docs/living-research-report-2026-10-07.md#7-references)
record attribution and scope. This is not a SwarmWorld reproduction.

## 3. Environment and methods

Legacy members harvest, transfer resources, guard, rest or raid. Institutions control
taxation, investment, redistribution, raid permission and reporting. A trusted
simulator resolves actions and accounts for renewal, consumption, transfers,
destruction and investment. Private utility is consumption plus 0.2 times
terminal wealth. Consumption-v2 welfare is
`0.85 − 1.5 × unmet need/member/tick` at the default consumption need of 0.85;
welfare and shortfall therefore measure the same primitive outcome.
[Environment specification](docs/model.md).

The [new physical engine](docs/commons-v3-foundation-protocol.md) has 24 mobile
individuals and 16 sites on a 12×12 grid. It implements local extraction,
consumption, transfers, costly messages and stock-dependent renewal with
recovery. Actions commit simultaneously; ledgers record every material flow.
Its development policies are audited local heuristics. There are no institutions,
affiliations, mortality or evolutionary searches in these banks.

The subsequent [ecological](docs/commons-v3-ecology-qualification-protocol-v1.md)
and [incentive](docs/commons-v3-incentive-qualification-protocol-v1.md)
protocols retain both the fixed floor and the earlier numerical winner. They
were frozen and pushed before either fresh seed set ran. Ecology uses 512 ticks
and 16 seeds per cell; incentives use 16 different seeds and matched focal
substitutions at 0, 6, 12, 18 and 23 aggressive peers. A prespecified family
of 194 scalar Student-t intervals with Bonferroni correction governs the gates.
Coverage is approximate and model-based; seeds are the replication units.
Storage, horizon, initial-stock, contention and utility sensitivities are
separately reported. [Conservative physical certificates](docs/commons-v3-feasibility-v1.md)
can prove insufficient supply; a permissive upper bound cannot prove feasible
local control.

Historical search accepts member replacements for private gains and institutions
for society gains on fixed cases. The pilot has one run per arm; transplants
estimate conditional component effects within its lineage. The later exploratory
baseline audit did not influence search.

The world-model controls estimate three coefficients of a supplied renewal
equation. They retain 1,024 particles and four rejuvenation sweeps, explicit
noisy observations and protected forecasts. Reporting preserves event provenance,
deduplicates evidence and charges matched serialized bytes. The allocation and
experiment controls hold planners and action menus fixed. Their intervals
resample independent arenas; members, branches, particles and repeated queries
are dependent observations. [Methods and protocols by study](docs/study-index.md).

## 4. Experiments and results

The legacy studies' strongest diagnostic is the missing-baseline problem. A reconstructed
policy harvests the fullest visible patch with no tax, investment or raids.
On the existing mechanism panel:

| Drought outcome | Initial | Coevolved | Simple harvest |
| --- | ---: | ---: | ---: |
| Focal consumption welfare ↑ | 0.844263 | 0.846926 | **0.848654** |
| Unmet need/member/tick ↓ | 0.003825 | 0.002050 | **0.000897** |
| Focal private utility/member/tick ↑ | 0.933662 | 0.965109 | **1.038674** |
| Outward raid loss/society/tick ↓ | 0.602067 | 0.534878 | **0** |
| Other societies' mean welfare ↑ | 0.847117 | 0.846872 | 0.845842 |

These means cover 12 environment/timing tuples, 108 focal scenarios and 216
paired drought/no-drought rollouts, with **zero new searches or model calls**.
Simple harvesting raises private utility by 7.62% versus coevolution, but reduces
outsiders' welfare by 0.001030. Focal welfare improves/ties/worsens in 23/84/1
scenarios. This bundled replacement does not isolate raid removal, establish
universal dominance or eliminate ecological externalities.

![Recorded focal and outsider outcomes for the baseline comparison](figures/baseline-review-v1/baseline-outcomes.png)

*Figure 1. Recorded drought means, with separate axis ranges and condition
markers. Means describe one saved evolutionary lineage; they are not independent
search replications. [Evidence](evidence/baseline-review-v1/README.md) and
[captions, exact means, SVG/PDF/PNG exports and hashes](figures/baseline-review-v1/README.md).*

The remaining studies establish controls and limitations that the redesign
must preserve:

| Study and replication | Supported result |
| --- | --- |
| [Initial evolution](docs/first-study-report.md): one search run | Direct infrastructure reward raised the score while post-drought shortfall increased and private utility fell 9.65%. |
| [Consumption pilot](docs/consumption-v2-run.md): one run per arm | Coevolution improved welfare by 0.000833 over member-only search, with 65.2% more raid harm and 1.8% lower private utility. |
| [Program transplants](docs/mechanism-study.md): one saved lineage, 864 rollouts | Institutional harm depended on the member background; positive welfare complementarity remained unresolved. |
| [Parameter learning](docs/world-model-v1.md): 24 arenas | Private final predictive CRPS fell from 0.9422 to 0.2496. Pooling supplied three times the evidence. |
| [Calibration](docs/world-model-calibration-v1.md): 128 prior-predictive datasets + 64 ecological arenas | All 192 references qualified. More compute modestly improved agreement at 4–5 times the fitting cost. |
| [Private sharing](docs/world-model-sharing-v1.md): 24 arenas | Complementary reports improved time-average CRPS by 0.68% at matched bytes; the terminal contrast remained unresolved and equal-evidence scores favored isolated/redundant members. |
| [Allocation decisions](docs/world-model-decision-v1.md): 24 arenas | Learned-minus-prior utility was +0.021110 [0.009014, 0.033678] per member; 85.7% came from weighted terminal wealth. |
| [Costed experiments](docs/world-model-experiment-v1.md): 24 arenas | Active-minus-random posterior-update value was −0.000969 [−0.005181, 0.002920]. A small total gain was already present with frozen coefficients. |

Bracketed ranges are paired 95% whole-arena bootstrap intervals. All numerical
world-model studies used zero evolutionary searches. Separate development gates,
negative controls, secondary endpoints and complete tables remain in the
[study index](docs/study-index.md) and linked reports.

The separate [spatial development study](docs/commons-v3-foundation-v1.md)
contains two preserved banks of 56 configurations and 224 episodes each, using
the same four seeds. The first exposed a floating-point return-fuel trap in the
navigation policy. The repaired second version recorded zero unaffordable-return
violations; it remains development data, not fresh qualification.

At the reference cell, restrained agents consume **1.200000** per agent-tick
versus **0.229769** for the greedy heuristic. A single greedy replacement gains
**zero consumption**; its **0.010685** utility gain at terminal-wealth weight
0.05 comes entirely from inventory, while peers lose **0.100769** consumption
per agent-tick. Reducing carrying capacity from 80 to 8 shrinks that private gain
to **0.000252** and removes peer consumption losses. Greedy terminal ecological
stock remains **66.70%** of capacity: local depletion and access failures coexist
with unused resources. These are descriptive means, not confidence claims.
[Recorded figures, tables and provenance](figures/commons-v3-foundation-v2/README.md).

The separate [need-targeted baseline study](docs/commons-v3-need-v1.md) adds
224 episodes on the same 56 development configurations. At capacity 80,
targeting current need with zero/two ticks of usable buffer raises reference
consumption to **1.123083/1.137248**. Greedy focal replacements now gain
**0.105842/0.095690** consumption per tick while peers lose
**0.336463/0.287450**. However, population consumption falls to
**0.798804/0.804615** at 512 ticks, and two-tick reserves reduce consumption
by **0.254884** relative to zero reserves with lower initial stock. These
reused-seed policy comparisons leave navigation and qualification unresolved.

![Need-targeted consumption and ecological stock](figures/commons-v3-need-v1/baseline-comparison.png)

*Recorded four-seed development means, with saved v2 controls and unsmoothed
reference trajectories. [Complete effects, sensitivities and provenance](figures/commons-v3-need-v1/README.md).*

The [navigation and numerical-baseline study](docs/commons-v3-navigation-v1.md)
adds purposeful observed-map routes, paid route-fuel saving and a finite sweep
of buffers, stock floors and routing rules. Its 18 candidates use two tuning
seeds; selection was frozen and pushed before evaluation on four disjoint
seeds. The **660 episodes** are numerical evaluations, with **zero independent
evolutionary runs or experimental model calls**. At reference need 1.2:

| Fresh-seed population consumption per agent-tick | Reference | 512 ticks | Initial stock 22 |
| --- | ---: | ---: | ---: |
| Legacy need-2 | 1.083741 | 0.731003 | 0.723430 |
| New forager, no floor | 1.097344 | 0.568493 | 0.460814 |
| Fixed half-capacity floor | 1.197891 | **1.195943** | 1.195711 |
| Selected: buffer 4, floor 0.5, nearest route | **1.199410** | 1.193929 | **1.195932** |
| All aggressive | 0.163314 | 0.086676 | 0.096235 |

The selected controller averages **88.01% of need** across the fresh grid,
versus **87.61%** for the fixed floor and **65.30%** for legacy need-2. Its
worst cell still meets only **49.28%** of need. At the reference, focal aggression
gains **0.006815** consumption and **0.021253** private utility at weight 0.05;
**67.93%** of that utility gain is terminal wealth. Peers lose **0.017507**
consumption. All-aggressive terminal stock is only **0.173%** of capacity,
unlike the earlier greedy policy's large unused stock. But capacity 8 removes
the mean peer consumption loss, and one high-need focal case loses
**0.567094** consumption per tick. Four-seed ranges remain descriptive;
selection within this controller family is not a private optimum or a
qualified social dilemma.

![Fresh-seed navigation comparisons and access diagnostics](figures/commons-v3-navigation-v1/evaluation-performance.png)

*All nine grid cells and five sensitivities, with paired observed ranges and
unsmoothed reference trajectories. [Candidate scores, aggressive effects,
complete CSVs and SVG/PDF/PNG provenance](figures/commons-v3-navigation-v1/README.md).*

The completed ecological qualification bank contains **288 episodes** on
16 fresh seeds per cell. Both controls pass all five ecological criteria in
the same five cells, including two adjacent pairs containing the reference:

| Renewal rate | Need 0.8 | Need 1.2 | Need 1.6 |
| --- | --- | --- | --- |
| 0.12 | Feasibility unresolved | Certified insufficient | Certified insufficient |
| 0.24 | Witnessed viable | Witnessed viable | Feasibility unresolved |
| 0.36 | Witnessed viable | Witnessed viable | Witnessed viable |

At reference need 1.2, fixed/selected mean consumption is
**1.192293/1.196167** per agent-tick; final-quarter consumption is
**1.184978/1.190646**. Late ecological stock averages about **74.1%** of
capacity, with no depleted-site time. For the two certified cells, the
conservative 512-tick supply ceiling meets at most **77.50%/58.13%** of need,
below the 95% target even under relaxed access assumptions. The other two
failed cells remain unresolved: policy failure is not an impossibility proof.
These are finite-horizon ecological findings. The separately frozen incentive
bank is in progress; ecological success alone does not qualify a social dilemma.

## 5. Limitations and next experiments

The legacy ecology uses additive renewal, often operates near the consumption
ceiling and has no mobility or endogenous institution formation. Raiding and
ecological appropriation impose different costs. Few accepted proposals and
one lineage per search condition cannot establish reliable evolutionary gains.

World-model results concern supplied laws and instrumented observations.
Numerical agreement does not establish universal calibration: the shared
borderline likelihood-CDF departure and the conditional ecological observation
model remain limitations. Prediction benefits alone do not establish useful
decisions. Additional allocation consumption occurred in only one arena;
experiment selection chose Early in 71/72 states and did not establish repayment
of its opportunity cost. These are integration and identification controls.

The [ordered plan](docs/commons-v3-plan.md) now has separately frozen ecological
and incentive qualification protocols. The ecological bank is complete; the
incentive bank is running on its own new seeds. Baseline limitations and adverse
cases remain visible, and ecological viability alone does not establish robust
private temptation or collective harm. Optional institutions and costed enforcement then face
hand-designed and numerical baselines. Replicated adaptation, cross-play,
invasion and unfamiliar scarcity follow a new protocol and explicitly authorized
inference budget. No gate requires institutions or coevolution to win.

## 6. Reproducibility

Compact records, source snapshots and figures stay in Git; full numerical
evidence is restored from [checksummed release archives](docs/evidence-archives-v1.md).
The [need-targeted public archive](artifacts/commons-v3-need-publication-v1/README.md)
restores all 56 cases byte-identically; its report gives download, offline
restoration and full regeneration commands.
The navigation bank uses separate [tuning](artifacts/commons-v3-navigation-tuning-v1/README.md)
and [evaluation](artifacts/commons-v3-navigation-evaluation-v1/README.md)
catalogs; restore both before its exact 660-episode replay or figure regeneration.
Git history is unchanged, so use `git clone --depth 1` for a smaller initial
checkout; an ordinary full clone still downloads historical evidence blobs.

Use Python 3.13 and the [pinned numerical environment](requirements-world-model-v1.txt):

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-world-model-v1.txt -e '.[test]'
.venv/bin/python -m pytest -q
```

Restore calibration evidence, verify it and regenerate the recorded baseline figure:

```bash
.venv/bin/python scripts/restore_evidence_v1.py --study world-model-calibration-v1
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_calibration_portable_v1.py \
  --receipt runs/calibration-portable-v1/receipt.json
.venv/bin/python scripts/visualize_baseline_review.py
```

Use `--study all` to restore the legacy catalog, or `--offline` to use verified
cached archives. The default test suite works without downloading the full banks.

The supplemental verifier preserves exact source hashes and qualification/retry
decisions; tolerance applies only to enumerated reference diagnostics. It passes
all 192 cases on Python 3.12/3.13 with the pinned numerical libraries. An older
stack's out-of-scope drift remains a documented compatibility limit. Use a new
receipt path each time. [Foundation repairs and validation](docs/foundation-repairs-v1.md).

Execute new or untrusted policies in the supported legacy engines through bounded workers:

```bash
.venv/bin/python -m swarm_societies.run_bounded_v1 episode \
  --engine consumption-v2 \
  --programs seeds/initial.py seeds/cooperative.py seeds/selfish.py \
  --seed 101 --replay --receipt runs/bounded-replay-v1/receipt.json
```

Workers enforce memory, CPU, wall and output limits; this is resource containment,
not an OS security sandbox. Frozen direct runners remain for audited trusted
policies. V3 currently runs audited built-in heuristics only; generated-policy
integration is still pending. Its [report](docs/commons-v3-foundation-v1.md#reproduction-and-engineering-scope)
gives separate restoration and replay commands. The [study index](docs/study-index.md) links full verification,
reproduction and interruption-recovery commands. Completed evidence, protocols
and simulators are preserved. The [inference route](docs/subscription-route.md)
and old budgets remain unchanged and exhausted. Local numerical checks and
recorded-data rendering require no experimental model calls.
