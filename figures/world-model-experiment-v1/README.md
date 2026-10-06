# Costed investment experiments

Bank: **evaluation**. Arenas: **24**. Three dependent focal societies per arena. Zero evolutionary runs or model-generation calls.

Recorded-data Chromatic Field figures. Rendering runs no learning, acquisition selection or physical evaluation.

## experiment-selection

[SVG](experiment-selection.svg) · [PDF](experiment-selection.pdf) · [PNG](experiment-selection.png)

Recorded experiment choices and acquisition diagnostics. Active selection maximizes a joint Gaussian moment information proxy; fixed selects Split; random makes a precommitted uniform choice. These scores are not exact expected information gain or decision value. Early, Late and Split invest the same reserved resources and use identical reporting opportunities. In development, filled markers identify the active choice and the right panel shows downstream updated-minus-frozen utility on each identical physical path. Development cases are designed states and have no population confidence intervals. In evaluation, bars describe dependent focal choices clustered within independent arenas.

## experiment-effects

[SVG](experiment-effects.svg) · [PDF](experiment-effects.pdf) · [PNG](experiment-effects.png)

The primary contrast is active minus random in the value of posterior updating. Within each physical path, the updated and frozen-coefficient planners receive the same latest legal state; their comparison withholds coefficient updates, not all new information. Total updated-policy utility differences decompose exactly into this update-value difference and the difference under frozen coefficients. Across schedules, information value can interact with different material states. Black diamonds average focal societies within arena; society colors preserve identities. Evaluation intervals use 2,000 paired whole-arena bootstrap draws with seed 9501. Development shows descriptive means only. Secondary intervals have no multiplicity adjustment. Consumption and terminal wealth are distinct; utility includes both.

## experiment-opportunity-cost

[SVG](experiment-opportunity-cost.svg) · [PDF](experiment-opportunity-cost.pdf) · [PNG](experiment-opportunity-cost.png)

Opportunity-cost comparison against redistributing the escrow at the first probe tick without investing it. All displayed planners use updated beliefs. This baseline spends zero on probe investment and is outside the equal-investment Active/Fixed/Random comparison. Contrasts include changes in both material paths and subsequent learning. Held-out CRPS uses the common uncapped queries and lower values indicate better predictions. Utility, consumption and terminal wealth retain distinct meanings. Evaluation intervals resample whole independent arenas after averaging focal societies; designed development cases show descriptive means without intervals. All secondary intervals are unadjusted.

[Paired estimates](paired-estimates.csv) · [Absolute endpoints](absolute-endpoints.csv) · [Source/output hashes](manifest.json)

Prediction and communication metrics describe the underlying probe path and repeat across downstream belief rows. Post-probe CRPS scores the updated institutional learner; it is not a new frozen- or known-coefficient prediction score. Repeated metrics are not additional observations.

The renderer checks artifact hashes, complete grids, selected-path identities, matched investment and traffic, utility primitives, the exact contrast decomposition and independently recomputed summary means/intervals. The redistribution opportunity baseline is outside the matched-investment comparison.
