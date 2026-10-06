# Fixed-planner allocation decisions

Recorded-data figures in Chromatic Field v1. No renderer operation trains a model, selects an action or evaluates a branch.

Bank: **evaluation**. Independent arenas: **24**. Focal societies per arena: **3**. Decision horizon: **32 ticks**. Failed plans: **0**. Independent evolutionary runs and model-generation calls: **0**.

Societies retain cobalt, magenta and orange. Conditions use labels and neutral marker shapes. Whole independent arenas are resampled after averaging the three dependent focal decisions.

## paired-decision-effects

[SVG](paired-decision-effects.svg) · [PDF](paired-decision-effects.pdf) · [PNG](paired-decision-effects.png)

Paired realized outcome differences under the same fixed allocation planner supplied with a frozen prior, a learned institutional posterior, or known coefficients. Black diamonds average the three focal societies within each arena; colors retain society identity. Lines are 95% percentile intervals from 2,000 whole-arena bootstrap draws with seed 9401. The primary contrast is learned minus prior private utility per member, defined as decision-window consumption plus 0.2 terminal wealth. Consumption and terminal wealth are reported separately. Mean welfare is consumption minus half unmet need per member per tick; its contrast is a rescaling of consumption here, not an independent endpoint. Secondary intervals are descriptive and have no familywise multiplicity adjustment. Known coefficients do not reveal hidden state or future weather.

## choices-and-regret

[SVG](choices-and-regret.svg) · [PDF](choices-and-regret.pdf) · [PNG](choices-and-regret.png)

Recorded choices from the fixed public-investment menu of 0, 0.5 and 1. Stacked bars use neutral fills and hatching for allocation fractions; society titles retain the established colors. Regret is the highest realized utility among three paired evaluator branches minus utility of the chosen branch, within the declared 32-tick window and fixed subsequent policy. This realized finite-menu benchmark uses the sampled future trajectory and is not an expected-value optimum, full-state oracle or globally optimal policy. Regret marks and intervals retain arena-level replication; focal rotations and menu branches are nested observations. All attempted plans remain in choice denominators.

## forecast-diagnostics

[SVG](forecast-diagnostics.svg) · [PDF](forecast-diagnostics.pdf) · [PNG](forecast-diagnostics.png)

Top: committed forecast of eventual institutional allocation budget versus its realized post-harvest value. Bottom: committed forecast utility difference between investing all and redistributing all versus the realized paired branch difference. Points show each recorded arena/focal/condition combination, not independent replications. Conditions use marker shapes and societies use fixed colors. The diagonal denotes exact agreement. Every planner receives the same legal current institution observation and one-tick-lagged home measurement, assumes unit member productivity, reconstructs previous terminal stock from noisy growth, and forecasts external infrastructure by decay only. The known-law condition retains these approximations. Future weather, RNG state, realized current taxes and branch outcomes enter no forecast.

## Tables and provenance

[Absolute endpoints](endpoint-statistics.csv) · [Paired differences](paired-contrasts.csv) · [Choice counts](choice-counts.csv) · [Forecast errors](forecast-statistics.csv) · [Source/output hashes](manifest.json)

All interval tables use 2,000 percentile bootstrap draws with seed 9401. The primary endpoint is learned-minus-prior private utility. Welfare, consumption, terminal wealth, spillovers and forecast errors remain separate. A gain in terminal wealth does not by itself establish improved consumption, welfare, inference efficiency or governance.

The renderer checks completion-manifest input hashes, complete decision/branch grids, chosen-branch accounting, forecast links, finite-menu regret, and independently recomputed whole-arena statistics against the saved summary. Development exploration and the action-ranking gate are not pooled into these evaluation figures.

```bash
.venv/bin/python scripts/visualize_world_model_decision.py
```
