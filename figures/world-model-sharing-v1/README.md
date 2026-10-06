# Private beliefs and bounded truthful sharing

Recorded-data Chromatic Field v1 figures. The experiment changes report content and delivery timing while preserving the world, private measurements and numerical learner.

Bank: **evaluation**. Independent arenas: **24**. Societies per arena: **3**. Private members per society: **4**. Independent evolutionary runs and model-generation calls: **0**.

Colors identify societies consistently. Condition markers and line styles do not represent different societies. Whole arenas, not members, societies, forecasts, messages or particles, are resampled for uncertainty intervals.

## member-learning

[SVG](member-learning.svg) · [PDF](member-learning.pdf) · [PNG](member-learning.png)

Member predictive CRPS on the 32 common guaranteed-uncapped probes per arena, averaged over four private models within each society. Top: recorded completed-tick checkpoints. Bottom: exact states immediately after 0, 8, 16, 32, 64, 128, 256 unique-event admissions, before any following event is processed. Curves are means over independent arenas; shading gives pointwise 95% whole-arena bootstrap intervals. Isolated and redundant private states coincide, so their lines overlap. Equal evidence counts need not identify equal examples or orders and therefore do not isolate inference efficiency. The legal-union arm is an unrestricted information reference, not a matched-bandwidth institution. Colors identify societies; markers and dashes identify conditions.

## institutional-learning

[SVG](institutional-learning.svg) · [PDF](institutional-learning.pdf) · [PNG](institutional-learning.png)

Recorded institutional predictive CRPS, one separately owned institution model per society and condition. Institutions receive no direct private sensor stream in the ordinary conditions; they learn only from authenticated uplink arrivals. Redundant member reports still train the institutional model once per event, while duplicate envelopes add no likelihood. The isolated institution remains at its prior. Legal-union institutions are supplied all legal events directly as an information reference. Curves and pointwise 95% intervals resample complete independent arenas, not societies or forecasts. These models are distinct from members' personal beliefs; institutional performance alone does not establish member learning.

## paired-effects

[SVG](paired-effects.svg) · [PDF](paired-effects.pdf) · [PNG](paired-effects.png)

Paired arena differences for the prospectively declared report-content contrast (complementary minus redundant), sharing contrast (complementary minus isolated), and delay contrast (delayed minus ordinary complementary). Black diamonds average four members within each society and three societies within each arena. Colored points retain society-specific estimates, each still based on independent arenas. Lines are 95% percentile intervals from 2,000 paired arena bootstrap draws. The primary endpoint is tick-integrated CRPS divided by the 128-tick horizon. Evidence-normalized integration uses the exact common range of 0–256 unique events and remains descriptive because event contents and order differ. The terminal endpoint scores the final physical horizon, without flushing in-flight reports. The report-content contrast matches actual wire bytes; the delay contrast matches channel capacity and origin schedule but may send fewer downlinks before the horizon. Secondary intervals have no familywise multiplicity adjustment.

## communication-accounting

[SVG](communication-accounting.svg) · [PDF](communication-accounting.pdf) · [PNG](communication-accounting.png)

Finite-horizon communication and evidence accounting, averaged over independent arenas. Left: bytes sent per society, split into delivered versus still-in-flight frames; each frame is 1,024 charged bytes, including provenance and padding, and every broadcast recipient copy is charged separately. Middle: delivered downlink arrivals per member, distinguished as novel accepted physical events versus duplicates of known events. Right: total unique-event counts in member and institutional models, including legal local sensor inputs. Colored points retain society identity; circle/square/cross meanings are panel-specific and labeled. Redundant and complementary conditions match actual bytes, sender schedule and delay. The longer-delay condition matches origin schedule and channel capacity but can send fewer downlinks within 128 ticks; pending frames are not flushed. The union reference has no charged communication because its legal sensor union is supplied directly as an unrestricted information reference. Its zero channel charge is not evidence of free achievable information transmission.

## member-uncertainty

[SVG](member-uncertainty.svg) · [PDF](member-uncertainty.pdf) · [PNG](member-uncertainty.png)

Terminal member-model coefficient coverage and marginal 90% credible-interval width, shown separately for each society and supplied law coefficient. Each independent arena contributes an average over its four dependent members before bootstrap resampling; model copies are not treated as independent calibration cases. Dots and lines show means and 95% arena bootstrap intervals. The nominal 0.90 line is descriptive for this interior-law ecological task panel; it is not the full-prior, exogenous-feature calibration control. Particle approximation and conditioning on latent-outcome-dependent ecological features retain the earlier audit's limitations. The unrestricted union and truthful sharing conditions need not have identical numerical trajectories, and narrow uncertainty alone does not establish learning quality. Institution statistics are retained separately in the accompanying parameter table.

## Derived tables and provenance

[Endpoint statistics](endpoint-statistics.csv) · [Paired effects](paired-contrasts.csv) · [Parameter coverage and width](parameter-statistics.csv) · [Communication accounting](communication-statistics.csv) · [CPU cost](compute-statistics.csv) · [Source/output hashes](manifest.json)

Derived tables retain society-level means as well as whole-arena means. Communication-table 'mean_across_societies' rows describe mean per-society cost, not the sum over an arena. Novelty per KiB counts accepted recipient updates, not independent physical events, and is undefined in arms with no channel. Bootstrap intervals use 2,000 whole-arena draws and seed 9301; all reported contrasts are paired. The primary content contrast is complementary minus redundant on member time-average CRPS. Secondary intervals are descriptive and have no familywise multiplicity adjustment.

The renderer checks design and input hashes, ownership/checkpoint grids, recorded interval arithmetic, and learning/contrast/CPU statistics against the frozen study summary. It runs no inference or ecological evaluation. The study's semantic verifier separately reconstructs routing and saved predictions.

```bash
.venv/bin/python scripts/visualize_world_model_sharing.py
```
