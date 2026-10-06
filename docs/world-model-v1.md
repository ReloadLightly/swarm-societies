# World model v1: stationary renewal-law identification

This first implementation turns the [world-model proposal](world-model-proposal.md)
into an executable parameter-learning control. It adds a separately versioned
ecology, instrumented observations, a probabilistic learner, protected forecasts,
and a reproducible experiment. It estimates three coefficients of a supplied
equation. Structural discovery and model-guided actions are later stages.

## Environment and observation contract

Three societies, each with four members, interact for 128 ticks. Each independent
arena samples one shared set of physical laws; societies do not receive separate
worlds. Fixed member policies harvest their own and periodically a visible other
patch. Institutional investment follows staggered eight-tick schedules, with
policy roles rotated across arena identities. This creates variation in local
and external infrastructure without a learner choosing actions. There is no
drought or policy evolution in this control.

The supplied renewal mechanism is

```text
X = min(capacity − previous terminal stock,
        r × W + b × own infrastructure + g × mean other infrastructure)
W ~ Uniform(0.85, 1.15)
Y = X + Normal(0, 0.05²)
```

Infrastructure is measured after depreciation, before renewal. The unknowns are
baseline regeneration `r`, local infrastructure return `b`, and external
spillover `g`. Public independent uniform priors are `[2,8]`, `[0.5,3]`, and
`[0,0.8]`. Evaluation laws are sampled from the fixed interior ranges `[2.4,6.8]`,
`[0.7,2.7]`, and `[0.05,0.7]`; these are task distributions, not learned priors.
Other physical coefficients and the mechanism family are supplied knowledge.

The engine records exact, phase-stamped measurements and itemized personal and
institutional receipts. The study constructs a narrower, explicit noisy growth
channel from those records. A learner receives only stock before growth, public
capacity, relevant infrastructure, noisy growth, and event identity. It receives
neither exact growth nor the resulting stock, true coefficients, weather, future
outcomes, or evaluator probes. Gaussian noise is added **after** physical capacity
clipping, so a noisy measurement may lie slightly outside the physical bounds.

`full_observation_control` explicitly permits the external infrastructure mean.
This is a free audit sensor condition for establishing identification; it is not
the legacy local information regime or a test of communication governance.
In `local` mode the engine omits that unobserved feature. The current numerical
learner rejects a missing feature instead of filling it from privileged truth.

Default engine parameters preserve v2 material trajectories, RNG draws, legacy
actor payloads and accounting exactly. New observations are separate outputs for
shadow learning. Candidates do not automatically receive them or learned beliefs.

## Inference and comparison

`RenewalSMC` approximates the joint posterior with 1,024 bounded particles.
Its likelihood integrates the hidden uniform weather and includes the capacity
point mass convolved with declared Gaussian sensor noise. It never discards
saturated observations as if they were a random subset of the data.

When effective sample size falls below half the particle count, systematic
resampling is followed by four random-walk Metropolis sweeps. Acceptance uses
the likelihood of all accepted evidence and the bounded prior. Rejuvenation
therefore targets static coefficients rather than introducing artificial drift.
The finite-particle approximation still needs calibration checks. A development
comparison motivated increasing the initial 512-particle/two-sweep setting;
development trajectories are excluded from the reported panel.

| Condition | Information supplied | Learned models per arena |
| --- | --- | ---: |
| Frozen prior | No outcome updates | One reference |
| Private | Own patch's noisy renewal event each tick, with licensed infrastructure features | Three separate society models |
| Pooled reference | Union of the three distinct patch events each tick | One reference |

The pooled learner receives three times as much evidence per tick and has no
bandwidth constraint. It is an information reference, not evidence for an evolved
institution or a more efficient inference algorithm. Prior and pooled rows are
repeated under society IDs for plotting; those copies are never independent
replicates. Identical forwarded event IDs are accepted only once; conflicting
contents under one ID raise an error.

All same-tick prequential forecasts are committed before any outcomes from that
tick update a learner. Prediction uses an independent RNG and must leave the
serialized live learner unchanged. Learners start from the same prior in every
arena. Saved final snapshots contain particles, weights, accepted evidence and
RNG state and can be restored without warm-starting another arena.

## Evaluation and statistics

The panel contains 24 independent hidden-law/environment arenas. Checkpoints
are 0, 4, 8, 16, 32, 64 and 128 completed ticks. Each arena has 64 common, held-out
one-step queries instantiated under its own hidden law draw, with independent
weather and sensor randomness. Query designs independently vary local and
external infrastructure over `[0,2]`. Thirty-two have enough headroom that
capacity cannot bind anywhere in the public prior support. The remaining 32
exercise zero headroom, strong clipping and mixed clipping. Probe targets never
train the models, and different-law transfer is not tested here.

The primary outcome is **time-averaged CRPS on the 32 guaranteed-uncapped probes**:
trapezoidal area under checkpoint loss, divided by 128 ticks. Lower is better.
This avoids letting trivial saturated predictions dominate the learning score.
Secondary outcomes include terminal CRPS, squared forecast error, 90% predictive
coverage and interval width, parameter error and all-probe CRPS. Every predictive
distribution uses 512 equally weighted samples, with the same probe-specific
random stream across checkpoints and conditions. The frozen prior curve is
therefore exactly constant.

Society outcomes are averaged within each arena before uncertainty estimation.
Reported 95% percentile intervals use 2,000 whole-arena bootstrap draws; paired
contrasts resample the same arenas together. Ticks, societies, repeated probe
targets and copied reference rows are not additional replications. Policy-role
assignments rotate across arenas; they do not constitute independent evolutionary
searches. The experiment uses no model-generation calls or old search allowance.

## Results from the frozen 24-arena panel

| Condition | Time-averaged CRPS, primary | Final CRPS | Final predictive coverage, nominal 90% | Observations per learned model |
| --- | ---: | ---: | ---: | ---: |
| Frozen prior | 0.942235 | 0.942235 | 94.40% | 0 |
| Private | 0.308766 | 0.249648 | 88.98% | 128 |
| Pooled reference | 0.270321 | 0.248053 | 89.06% | 384 |

Private learning reduced primary loss by **0.633469**, paired 95% arena interval
**[0.451801, 0.851678]**, relative to the frozen prior. Pooled minus private was
**−0.038445 [−0.047006, −0.030612]**, or a 12.45% lower mean primary loss. Its
terminal advantage was much smaller: **−0.001595 [−0.002651, −0.000590]**.
The pooled condition learned faster in world time while receiving more evidence;
this does not establish an inference-efficiency or governance advantage.

Predictive calibration does not imply parameter-belief calibration. The
following descriptive terminal statistics pool private models within arena;
there are 72 private model estimates nested inside 24 independent arenas, and
24 distinct pooled models.

| Coefficient | Private mean absolute error | Pooled mean absolute error | Private 90% parameter coverage | Pooled 90% parameter coverage |
| --- | ---: | ---: | ---: | ---: |
| Baseline regeneration `r` | 0.045567 | 0.023592 | 87.50% | 91.67% |
| Local infrastructure return `b` | 0.032465 | 0.015608 | 93.06% | 95.83% |
| External spillover `g` | 0.053673 | 0.027249 | 83.33% | 75.00% |

The pooled spillover interval covered truth in only 18 of 24 arenas. This is a
material limitation despite lower point-estimate errors. Additional independent
calibration and compute-sensitivity controls should precede decisions that rely
on these parameter intervals. This experiment does not distinguish finite-particle
error from other sources of interval undercoverage.

All 18,432 attempted learning updates succeeded. The evidence contains 9,216
distinct environmental measurements, 1,512 checkpoint rows and 96,768 probe-score
rows. Reference rows repeat some identical forecasts, so those counts describe
the archive, not independent experiments. Verification reconstructs 7,680 terminal
forecasts from saved learner snapshots and checks every scalar table against its
recorded primitives. The full test suite passed 90 tests and 14 subtests.

![Learning in world time and per observation](../figures/world-model-v1/learning-curves.png)

## Reproduction and evidence

The frozen machine-readable [design](../evidence/world-model-v1/design.json)
specifies every case, prior, seed namespace, checkpoint, program and source hash.
Its checksum is checked before execution. Portable source and policy snapshots
are included alongside scalar CSV tables, compressed prediction/observation
tables, learner snapshots, a summary, and an artifact-hash manifest.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-world-model-v1.txt -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run_world_model_study.py verify
.venv/bin/python scripts/visualize_world_model_study.py
```

To reproduce the deterministic case bank in a new output directory:

```bash
.venv/bin/python scripts/run_world_model_study.py prepare --output runs/world-model-reproduction
.venv/bin/python scripts/run_world_model_study.py run --output runs/world-model-reproduction
.venv/bin/python scripts/run_world_model_study.py verify --output runs/world-model-reproduction
```

Training CPU time and timestamps depend on the machine; recorded numerical
results are deterministic under the recorded software environment. Existing
completed designs are not overwritten. The
[Chromatic Field figure gallery](../figures/world-model-v1/README.md) renders saved
results, preserving society colors and distinguishing conditions by line style.

## Limits and next implementation

This experiment supplies the right equation family and a matched noise model,
grants full infrastructure measurements, fixes policies, and estimates only
three stationary coefficients. It measures one-step predictions and numerical
parameter recovery. It does not establish learning under legacy partial
observation, calibrated uncertainty under model misspecification, useful control,
efficient knowledge sharing, regime discovery, or structural law discovery.

Next compare private member models and institution-mediated reporting under
matched bandwidth and authorized local sensing. Then add costed experiments,
separate physical and social changes, and test a fixed planner using learned
models. Structural revision follows the separate second stage of the proposal.
