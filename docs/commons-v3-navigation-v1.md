# Commons v3: purposeful local foraging and a finite numerical baseline

This stage implements an observed-map forager and a finite parameter sweep,
following the [need-targeted baseline study](commons-v3-need-v1.md). It retains
the original physical engine, resource costs, carrying capacity and utility
weights. Earlier banks, including adverse outcomes, remain unchanged. There
are no institutions or political memberships and no experimental model calls
or evolutionary campaigns.

The [protocol](commons-v3-navigation-protocol-v1.md), implementation and full
[design](../evidence/commons-v3-navigation-v1/design.json) were pushed as
[`b16a239`](https://github.com/ReloadLightly/swarm-societies/commit/b16a2396a8067fad33cb199d58e6defcef01d6cc)
and the remote commit verified before tuning started. This prospective freeze
includes both seed lists, every candidate, the objective, tie rules and all
evaluation conditions. Its purpose is stronger baseline comparison, not the
larger ecological or incentive qualification gate.

## Local controller and numerical selection

Each individual remembers only observed sites, last observed stocks and
headcounts, observed sensing footprints, its own visits and a current route.
It follows purposeful Manhattan routes, seeks sensing novelty and periodically
reinspects stale sites. Stale stock is discounted by a fixed heuristic rather
than forecast with a hidden or fitted renewal law. The controller does not
know remote current stocks, the initializer's layout, weather, renewal rates,
the environment seed or other agents' inventories. All global diagnostics
are computed by the evaluator and never enter its observation packet.

Movement and harvesting can occur in the same committed action. The actor
pays movement from existing inventory and extraction costs from gross yield;
storage is enforced before consumption. Fuel covers a committed route and
known-site return. If a known productive trip needs more than the base fuel
reserve, an agent can save actual local harvest to fund it before departing.
This can reduce current consumption and is recorded as unmet need. Food
buffers remain consumable. Small-world tests establish these affordances and
specific invariants, not globally effective navigation.

The 18 numerical candidates cross buffers of 0/2/4 ticks, voluntary stock
floors of 0/0.25/0.5 of capacity, and nearest-site versus travel-adjusted-yield
routing. Positive floors divide requests among the inferred local headcount;
zero-floor requests are demand/storage capped without this division. Service
estimates account for crowding at every setting. Simultaneous arrivals can
breach a voluntary aggregate stock floor; no quota is enforced by the engine.

Each candidate runs on nine ecological grid cells and **two tuning seeds**,
62001 and 62002, for 256 ticks: **324 candidate/environment episodes**. Select
once by mean population consumption divided by declared need, with exact ties
broken by normalized final-quarter consumption and then candidate ID. Every
candidate and case remains in the record. This is one deterministic numerical
selection within a supplied controller family, not an independent evolutionary
run, a private optimum, equilibrium or globally optimal planner.

## Fresh comparison design

Evaluation uses **four separate seeds**, 63001–63004, on the nine grid cells
and five fixed reference sensitivities: longer horizon, keyed priority, lower
initial stock, additive renewal and capacity 8. The primary grid retains
capacity 80. These are **56 configurations and 336 episodes**, comprising
six conditions per configuration:

| Condition | Population |
| --- | --- |
| Legacy need-2 | Frozen earlier need-targeted controller with two ticks of buffer |
| Fixed forager | New forager, buffer 2, no voluntary stock floor, travel-adjusted-yield routing |
| Fixed floor | Same fixed parameters with a half-capacity voluntary floor |
| Selected | The single candidate selected from the completed tuning bank |
| Focal aggressive | One preselected aggressive forager among unchanged selected peers |
| All aggressive | Everyone uses the aggressive variant of the selected route setting |

Aggressive requests fill inventory subject to stock, rate and storage limits,
removing both need-targeting and the voluntary floor. Route parameters are
shared, but changed service estimates, stocks and inventories can change actual
navigation. These are whole-policy substitutions, not extraction-only
interventions. The selected policy may match a fixed anchor; separately named
identical conditions are retained without treating them as independent evidence.

Across tuning and evaluation there are **660 episodes, 175,104 physical ticks
and 4,202,496 individual decisions**, excluding verification replays. Two tuning
and four evaluation seed realizations are distinct. Reusing each seed across
cells, sensitivities and conditions does not create further independent
replicates. The larger disjoint qualification panel remains a subsequent stage.

## Recorded results

The completed tuning bank selects **buffer 4, floor 0.5, nearest routing**.
Its objective is **0.8799445193** of need, only **0.0002044781** above the
otherwise matching travel-adjusted-yield candidate. That runner-up has higher
final-quarter consumption (0.871315 versus 0.866650); the secondary criterion
does not apply because the primary values are not exactly tied. Selection and
all tuning outcomes were pushed as
[`cc9c2fe`](https://github.com/ReloadLightly/swarm-societies/commit/cc9c2fe95a397de567d093daf1e47e1e240fc3a2)
before opening evaluation.

All 12 positive-floor candidates rank above the six zero-floor candidates on
the tuning objective, but larger buffers are not uniformly helpful. Increasing
reserves lowers consumption at floors 0 and 0.25 in both route modes, and
raises it at floor 0.5. Travel-adjusted-yield routing wins six of the nine
matched parameter pairs. The selected candidate still meets only **0.493789**
of need in its worst grid-cell mean (renewal 0.12, need 1.6). These results
describe a floor-dependent controller bundle and reserve interaction, not
isolated extraction effects or general superiority of nearest routing.

![All recorded candidate objectives and adverse tuning cells](../figures/commons-v3-navigation-v1/candidate-selection.png)

*Tuning scores from every candidate/environment episode. The worst cell and
worst environment are retained diagnostics, not extra selection criteria.*

Across the nine fresh evaluation grid cells, selected mean consumption/need
is **0.880082**, compared with **0.876091** for the fixed floor, **0.653006**
for legacy need-2, **0.632345** for the fixed no-floor forager, and **0.153706**
for all-aggressive. The finite selection adds only **0.003990** of need over
the already strong fixed-floor anchor. This supports the floor-bearing
controller family more strongly than the particular numerical winner.

The table retains every evaluation cell. Population consumption and paired
focal/peer differences are per individual per tick; private utility adds
`0.05 × terminal inventory / horizon`. Sensitivities use the reference
rate 0.24 and need 1.2, changing only their named setting. Entries are means
of four paired seed/focal configurations; the complete ranges, additional
conditions and all three wealth weights are in the gallery CSVs.

| Cell | Legacy C | Fixed-floor C | Selected C | All-aggressive C | Focal ΔC | Focal ΔU, w=0.05 | Peer ΔC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r=0.12, need=0.8 | 0.316851 | 0.730968 | 0.731767 | 0.131815 | 0.062088 | 0.075120 | -0.088902 |
| r=0.12, need=1.2 | 0.268979 | 0.772741 | 0.785544 | 0.132173 | 0.275101 | 0.286912 | -0.128569 |
| r=0.12, need=1.6 | 0.198844 | 0.782338 | 0.788423 | 0.132595 | 0.569223 | 0.578302 | -0.149246 |
| r=0.24, need=0.8 | 0.800000 | 0.800000 | 0.800000 | 0.164817 | 0.000000 | 0.014828 | -0.000075 |
| r=0.24, need=1.2 | 1.083741 | 1.197891 | 1.199410 | 0.163314 | 0.006815 | 0.021253 | -0.017507 |
| r=0.24, need=1.6 | 0.367117 | 1.343930 | 1.374612 | 0.162862 | 0.026298 | 0.041074 | -0.139177 |
| r=0.36, need=0.8 | 0.800000 | 0.800000 | 0.800000 | 0.214258 | 0.000000 | 0.014828 | 0.000000 |
| r=0.36, need=1.2 | 1.200000 | 1.200000 | 1.200000 | 0.214437 | 0.000000 | 0.014437 | -0.000232 |
| r=0.36, need=1.6 | 1.600000 | 1.600000 | 1.600000 | 0.216234 | 0.000000 | 0.014047 | -0.000931 |
| 512 ticks | 0.731003 | 1.195943 | 1.193929 | 0.086676 | 0.003727 | 0.010946 | -0.014585 |
| Keyed priority | 1.085366 | 1.197891 | 1.199410 | 0.162745 | 0.006815 | 0.021253 | -0.017507 |
| Initial stock 22 | 0.723430 | 1.195711 | 1.195932 | 0.096235 | 0.000778 | 0.015334 | -0.031563 |
| Additive renewal | 1.200000 | 1.200000 | 1.200000 | 1.199427 | 0.000000 | 0.014437 | 0.000000 |
| Capacity 8 | 1.083741 | 1.197891 | 1.199410 | 1.054347 | 0.006815 | 0.007190 | 0.000098 |

At the reference, selected-minus-legacy consumption is **+0.115669** with
observed paired range **[+0.075652, +0.195003]**; selected-minus-fixed-floor
is only **+0.001519 [+0.001248, +0.001835]**. Longer-horizon selected
consumption remains **1.193929**, and final-quarter consumption **1.182944**,
compared with legacy **0.731003/0.343095**. Lower starting stock gives
selected **1.195932**, versus legacy **0.723430**. These gains address the
previous controls' recorded long-horizon and lower-stock failures.

The numerical winner is not uniformly superior: the fixed floor performs
slightly better over 512 ticks (**1.195943** versus **1.193929**), despite
three of four selected-minus-fixed pairs being positive. In the lowest-rate,
highest-need cell, selected consumption still meets only **49.28%** of need.
The fresh grid improves in five cell means and ties in four against each
anchor; repeated cells are not independent replications. Isolated changes
to navigation, extraction and buffers have not been identified.

![Recorded evaluation consumption, ecological stock and local access](../figures/commons-v3-navigation-v1/evaluation-performance.png)

*All 14 cells, descriptive paired ranges and unsmoothed reference trajectories.
Condition labels and markers identify policies; no society identities are
present in this physical-only study.*

At the reference, focal aggression gains **0.006815** consumption
**[0, 0.026752]**, positive in two of four pairs. The **0.021253** private
gain at weight 0.05 includes **0.0144375** from terminal inventory—**67.93%**
of the gain. Peers lose **0.017507** consumption **[−0.052658, −0.002831]**,
with losses in all four pairs. Under widespread aggression, consumption is
**0.163314**, final-quarter consumption **0.009128**, terminal stock only
**0.173%** of capacity and **96.55%** of site-ticks below one tenth of capacity.
This new bundle shows widespread recorded depletion, unlike the earlier
foundation greedy policy with substantial unused ecological stock.

That incentive pattern remains conditional. At capacity 8 the focal private
gain shrinks to **0.007190**, while mean peer consumption increases by
**0.000098** (one positive, one negative and two zero pairs); all-aggressive
consumption is **1.054347**, with final-quarter consumption **0.633794**.
With additive renewal, focal consumption and peer effects are zero and the
all-aggressive consumption penalty is just **0.000573**. The 512-tick focal
private gain is **0.010946**, below the plan's proposed 1%-of-need threshold
of 0.012 at the reference. At rate 0.24, need 1.6, positive mean focal gains
coexist with a seed pair losing **0.567094** consumption and **0.552639**
private utility at weight 0.05. Neither a population-selected controller nor
one aggressive variant supplies a private best response or a qualified dilemma.

![Recorded focal, peer and widespread aggressive effects](../figures/commons-v3-navigation-v1/aggressive-effects.png)

*Utility-weight sensitivity keeps endpoint wealth distinct from consumption.
Whiskers show observed paired minima and maxima, not confidence intervals.*

Access diagnostics also prevent conflating unused stock with sustainable
availability. At the reference, selected terminal stock is **73.96%** of
capacity, including **6.63% of total capacity** at unoccupied sites. Legacy
need-2 retains **43.47%**, including **17.00%** at unoccupied sites; the new
no-floor forager retains only **10.54%**, including **0.28%** unoccupied.
The mean fraction ending a tick off-site with recorded positive shortfall is
**0.118%** for selected, **3.813%** for legacy and **33.04%** for all-aggressive.
This count uses strictly positive recorded shortfall and may include tiny
floating-point amounts; it does not measure the amount of missed consumption.
Selected mean reference shortfall is **0.000590** per agent-tick. Unoccupied
stock is neither a reachability guarantee nor a sustainable-yield estimate.
Known-site diagnostics count memory at the last action commitment, without
adding a hypothetical observation after the final transition.
The selected controller knows only about **1.99 of 16 sites** per individual
at the reference endpoint. Strong consumption there does not demonstrate
comprehensive exploration. It spends more time off-site than the legacy
controller while recording less shortfall off-site; less travel is not the
explanation established by these comparisons.

The complete candidate scores, all fixed sensitivities, focal/private/peer
contrasts and access diagnostics are retained in the
[recorded-data gallery](../figures/commons-v3-navigation-v1/README.md).
Four-seed ranges are descriptive minima and maxima, not confidence intervals.

## Verification and reproduction

All **660 episodes replay exactly**: 324 in the
[tuning replay](../evidence/commons-v3-navigation-validation-v1/tuning-replay.json)
and 336 in the
[evaluation replay](../evidence/commons-v3-navigation-validation-v1/evaluation-replay.json).
All 660 episodes have zero unaffordable known returns. Extraction waste is
exactly zero in 655 episodes; five capacity-8 aggressive episodes have tiny
rounding-level totals, at most **1.42e-14**, retained in the raw record.
Maximum accounting residual is **4.40e-13**. The full repository
suite passes **842 tests and 123 subtests**, including all 300 commons tests.
An independent standard-library reconstruction passes **163,114 exact checks
and 93,983 numerical checks**, with maximum absolute accumulation difference
**1.71e-12**. Its scaled diagnostic tolerance never affects physics, selection,
sign-count thresholds or exact replay. The
[validation record](../evidence/commons-v3-navigation-validation-v1/README.md)
documents what is reconstructed and what remains a saved diagnostic.

All three recorded-data PNGs were inspected. The **18 gallery files**, including
SVG/PDF/PNG exports, seven CSVs, captions and manifest, rerender byte-identically.
Both older foundation banks and the need-targeted bank still match all original
artifact hashes. No frozen physical or earlier policy source changed.

The staged runner accepts only audited built-in policies. Candidate source
loading and bounded execution of generated v3 programs remain separate work.
Source hashes, full artifact inventories, deterministic keyed weather, waste,
accounting and known-site return affordability are checked. The reference case
also checks physical snapshot continuation with identical future actions;
policy-memory restoration is not claimed.

The full tuning record is sealed before selection. Its
[selection record](../evidence/commons-v3-navigation-v1/selection.json) binds
the tuning manifest, source freeze, selected parameters and predeclared
evaluation specification. An evaluation outcome cannot change the selected
candidate. Interrupted stages replay and compare complete files; completed or
failed banks are preserved. A failure stops completion rather than dropping
unsuccessful candidate/case combinations.

The complete raw bank is public in the
[`commons-v3-navigation-2026-10-07` release](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-navigation-2026-10-07),
using separate [tuning](../artifacts/commons-v3-navigation-tuning-v1/README.md)
and [evaluation](../artifacts/commons-v3-navigation-evaluation-v1/README.md)
catalogs. All **380 files / 11,786,864 payload bytes** restore byte-identically
through unauthenticated public downloads into empty caches/directories, and
through offline restoration. Tuning publication is preserved when evaluation
assets are added. Compact evidence, source copies and figures remain in Git;
raw restored files stay ignored. Hosting is hash-pinned, not administratively
immutable. Restore both phases before replaying the saved bank:

```bash
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-navigation-tuning-v1/catalog.json \
  --study commons-v3-navigation-tuning-v1
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-navigation-evaluation-v1/catalog.json \
  --study commons-v3-navigation-evaluation-v1
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_navigation_v1.py verify \
  --output evidence/commons-v3-navigation-v1
```

Create a separate reproduction from the repository root:

```bash
.venv/bin/python scripts/run_commons_v3_navigation_v1.py prepare \
  --output runs/commons-v3-navigation-reproduction
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_navigation_v1.py tune \
  --output runs/commons-v3-navigation-reproduction
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_navigation_v1.py evaluate \
  --output runs/commons-v3-navigation-reproduction
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_navigation_v1.py verify \
  --output runs/commons-v3-navigation-reproduction
.venv/bin/python scripts/visualize_commons_v3_navigation_v1.py \
  --source runs/commons-v3-navigation-reproduction --output runs/commons-v3-navigation-figures
```

`verify --phase tuning` replays tuning only. `verify --phase evaluation`
checks tuning hashes, aggregates and selection but replays only evaluation.
Thus one replay of each phase covers all 660 episodes without needlessly
repeating the tuning simulations. No experimental model calls are required.

## Limits and next gate

The finite grid selects on homogeneous-population consumption and two tuning
seeds. This gives a reproducible numerical benchmark, not a guarantee of
robustness or individually optimal behavior. The local controller still has
stale information, uncertain competition, heuristic route scores and a fixed
reinspection schedule. Four fresh comparison seeds support development
comparisons, not the stronger qualification claims. Report consumption and
terminal inventory separately, and distinguish unoccupied ecological stock
from resources that an agent can feasibly and sustainably access.

Separate ecological and incentive qualification follows sufficient baseline
strength. Optional institutions, founding/exit/change/dissolution and paid
enforcement remain later work. Do not adjust utility weights or suppress
adverse settings to obtain the intended dilemma. Any new experimental
model-driven search requires a separately authorized budget.
