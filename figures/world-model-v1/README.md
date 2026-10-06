# World-model parameter-learning control

Recorded evidence in Chromatic Field v1. This is an instrumented passive control with fixed policies and a supplied linear renewal family; no structural discovery or evolutionary learning is implied.

Independent arenas: **24**. Interacting societies per arena: **3**. Independent evolutionary runs: **0**.

Society colors are stable; line styles distinguish frozen prior, private observations, and pooled evidence reference. Pooled and prior copies across society panels are not extra replicates.

## learning-curves

[SVG](learning-curves.svg) · [PDF](learning-curves.pdf) · [PNG](learning-curves.png)

Recorded CRPS on 32 common guaranteed-uncapped same-law probes per arena. Top: completed world ticks. Bottom: the same evaluated checkpoints against unique observations assimilated; dots identify observed points, and gray marks the overlap of observed private/pooled count ranges. No curve is extrapolated beyond its evidence range. The frozen prior assimilates zero observations and is shown only as a horizontal reference in the bottom row. Lower is better. Lines join checkpoints; shading around curves gives pointwise 95% percentile bootstrap intervals resampling independent whole arenas. Prior and pooled references are repeated across society panels for comparison, not counted as independent replicates. Pooled gains per tick can reflect more evidence; neither faster learning nor sample efficiency establishes learned communication. Another 32 limited-headroom probes are recorded but excluded from this prespecified primary endpoint.

## parameter-recovery

[SVG](parameter-recovery.svg) · [PDF](parameter-recovery.pdf) · [PNG](parameter-recovery.png)

Mean absolute error of each coefficient's posterior mean against hidden simulator truth, by society and checkpoint. Base renewal r is in resource units per tick; returns b and g are in resource units per infrastructure unit per tick. Each column has its own scale; columns must not be ranked by vertical height. The same conditions and arena bootstrap as the predictive curves are used. These are numerical parameters of a supplied renewal mechanism, not recovered equation structures. Predictive accuracy does not imply all coefficients are identified.

## calibration-width

[SVG](calibration-width.svg) · [PDF](calibration-width.pdf) · [PNG](calibration-width.png)

Final-checkpoint 90% predictive-interval coverage and mean width on 32 common guaranteed-uncapped same-law probes per arena. Dots are means across independent arenas; horizontal lines are 95% percentile arena bootstrap intervals. The nominal coverage reference is 0.90. Width is in renewal resource units and must be considered alongside coverage. Repeated prior and pooled references are not additional independent samples.

## endpoint-comparison

[SVG](endpoint-comparison.svg) · [PDF](endpoint-comparison.pdf) · [PNG](endpoint-comparison.png)

Each independent arena contributes one mean across its three interacting societies. Time-average CRPS and paired differences from private evidence with 95% arena bootstrap intervals are the primary comparison; final probe CRPS and unique receipts per model provide context. Time-average CRPS is the trapezoidal area divided by the checkpoint time span. Scores use the 32 guaranteed-uncapped common probes per arena. Differences compare fixed estimators with different evidence access, not evolved learning algorithms. All negative and null results are retained.

## parameter-uncertainty

[SVG](parameter-uncertainty.svg) · [PDF](parameter-uncertainty.pdf) · [PNG](parameter-uncertainty.png)

Terminal coverage and mean width of 90% credible intervals for the hidden renewal coefficients, not predictive intervals for future outcomes. Society colors identify separate private estimates; prior and pooled copies are repeated only for comparison. Lines give 95% percentile bootstrap intervals over independent arenas. The parameter-statistics CSV averages societies within each arena before computing means and intervals, retaining 24 independent arena units. Observed pooled spillover coverage is 75.0% in this panel. Its interval reflects the limited arena sample; this finding calls for additional parameter-calibration validation and does not identify particle approximation as its cause. Approximately nominal forecast coverage does not establish calibrated coefficient beliefs.

[Endpoint contrasts as CSV](endpoint-contrasts.csv) · [Parameter statistics as CSV](parameter-statistics.csv) · [Source/output provenance](manifest.json)

Source evidence: [design](../../evidence/world-model-v1/design.json), [summary](../../evidence/world-model-v1/summary.json), [checkpoints](../../evidence/world-model-v1/checkpoints.csv), and [parameter estimates](../../evidence/world-model-v1/parameters.csv).

```bash
.venv/bin/python scripts/visualize_world_model_study.py
```
