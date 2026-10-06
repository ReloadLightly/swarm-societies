# World-model calibration gate

Protocol design, 6 October 2026. This document specifies a new diagnostic; it
contains no calibration results. The final machine-readable design must freeze
cases, seeds, numerical budgets and source hashes before the evaluation panel
runs. Published `world-model-v1` source, parameters, results and figures remain
unchanged. This work uses local numerical inference, with no evolutionary search
or new model-generation allowance.

## Question and interpretation

The published pooled learner's nominal 90% interval for spillover covered the
true coefficient in 18 of 24 arenas. That motivates a calibration investigation;
it does not establish its cause. The published task sampled coefficients from
interior ranges, whereas the learner used broader uniform priors. Bayesian
credible intervals do not promise 90% repeated-sampling coverage for every
fixed coefficient or every alternative task distribution.

Test three explanations separately: finite-particle approximation, inadequate
feature excitation, and the distinction between the fitted conditional model
and the complete ecological data-generating process. Do not infer that doubling
an interval's width fixes its underlying posterior.

Simulation-based calibration (SBC) draws truth from the fitted prior, simulates
data from its likelihood and checks where truth falls within inferred posterior
distributions. This targets inference correctness under the declared model,
not the adequacy of that model for every application.
[Talts et al., 2018](https://arxiv.org/abs/1804.06788).

Parameter-only checks can miss an algorithm that ignores data and returns its
prior. Add a data-dependent test quantity: the joint log likelihood of the
observed dataset, evaluated at both true and posterior parameter values.
[Modrák et al., 2025; first online 2023](https://doi.org/10.1214/23-BA1404).

## Two separate, prospective panels

| Panel | Independent units and observations | What it tests |
| --- | --- | --- |
| Prior-predictive SBC | 128 datasets; 128 observations each | Numerical posterior calibration under exogenous features and the declared prior/likelihood |
| Ecological task coverage | 64 new shared-law arenas; 128 ticks and 384 pooled patch observations each | Accuracy and interval behavior on the existing ecological task distribution |

For SBC, draw independent `r`, `b`, and `g` uniformly from the full learner prior:
`[2,8]`, `[0.5,3]`, and `[0,0.8]`. Generate own and external-mean infrastructure
independently from `Uniform(0,2)`, independently of the sampled coefficients.
Cycle capacity headroom through `30,30,6,0`: half the observations are guaranteed
uncapped throughout prior support, while the others exercise partial or complete
saturation. Capacity is 30. All features are chosen before outcomes.

Generate physical growth with independent `Uniform(.85,1.15)` weather, apply
the capacity cap, then add independent `Normal(0,.05²)` measurement noise.
The independent data generator should not call the learner's likelihood code.
The same complete dataset, including saturated observations, goes to each method.

For ecology, retain the published fixed policies, role rotation, sensor channel,
initial conditions, consumption mechanics and interior task-law ranges:
`r∈[2.4,6.8]`, `b∈[0.7,2.7]`, `g∈[0.05,0.7]`. Use new law, environment and sensor
seed namespaces that cannot overlap the published or development panels. Focus
on the pooled reference, where the reported spillover issue occurred. This is
not a new experiment on institutional reporting or control.

The ecological features are endogenous: exact stocks and infrastructure depend
on earlier latent physical outcomes, while the learner sees noisy growth.
The product of one-step growth likelihoods conditional on those features is
the fitted inference target. It need not equal the full posterior for the joint
process generating features and observations. An adaptive observation design
is ignorable only under appropriate conditional-independence assumptions; this
assumption is not established merely because policies are fixed. Therefore the
ecological panel is task-distribution coverage, not prior-predictive SBC.

## Numerical methods and independent reference

Compare the frozen `RenewalSMC` implementation at two declared budgets:

- Published: 1,024 particles, four rejuvenation sweeps, ESS threshold 0.5.
- Higher budget: 4,096 particles, eight rejuvenation sweeps, ESS threshold 0.5.

Keep priors, observation order, likelihood, and interval construction unchanged.
Use one seeded fit per method/dataset; reuse a common initialization seed where
specified, but do not claim identical random numbers throughout algorithms with
different particle counts. Numerical seeds are not additional independent worlds.
Record CPU, accepted observations, failed updates, resampling, move acceptance,
weight ESS and distinct particle values. Weight ESS immediately after resampling
does not measure how much genealogical diversity remains.

Retain a frozen-prior negative control that never consumes outcomes. Its marginal
parameter checks may look calibrated under prior-predictive simulation; the
data-dependent log-likelihood check should expose its failure to learn.

Fit an independently implemented batch posterior reference to each dataset's
same conditional likelihood and prior. This reference diagnoses approximation
to that target; it does not validate the ecological model itself. Check its
likelihood against numerical integration and the frozen production likelihood
on independently chosen capped, uncapped and tail cases.

Use four reference chains and assess rank-normalized split/folded R-hat, bulk
ESS and tail ESS for every coefficient. Reference acceptance requires R-hat
below 1.01 and both ESS measures at least 400. These diagnostics support an
operational reliability gate, not proof of exact sampling.
[Vehtari et al., 2021](https://arxiv.org/abs/1903.08008),
[authors' diagnostic examples](https://avehtari.github.io/rhat_ess/rhat_ess.html).

Initial reference length is 1,000 warmup iterations followed by 4,000 retained
draws per chain. A predeclared failure of the diagnostic gate triggers one rerun
with 2,000 warmup iterations and 8,000 retained draws per chain, using a separately
fixed retry seed. The gate applies to coefficients and the nonconstant joint
log likelihood. Retained sampling freezes its proposal; initialization and
warmup adaptation use evidence only. Report posterior-mean Monte Carlo standard
errors, and normalize reference precision by its posterior SD when comparing
methods. These settings were checked on a separate development benchmark before
the evaluation freeze; development cases are excluded from both final panels.
Preserve both attempts and their diagnostics.

Every case stays in the scheduled denominator. A failed reference is marked
unqualified and excluded only from claims requiring a credible reference, with
the qualified numerator and scheduled denominator displayed together. Never
replace failed cases or select reference cases after inspecting SMC errors.
Unexpected execution exceptions abort the run without deleting or replacing
scheduled cases; they must be repaired and documented before claiming completion.

## Measurements and uncertainty

The numerical comparison reports each coefficient's SMC mean difference from
the reference divided by reference posterior SD; the 90% interval-width ratio;
and 5th/95th quantile differences divided by prior width. Include paired case
plots and case-cluster intervals for budget effects. Show reference Monte Carlo
uncertainty beside close comparisons rather than labeling tiny differences as
algorithmic error.

For the SBC panel, report nominal 90% coverage with Wilson 95% binomial intervals and
posterior-CDF values at truth for all three coefficients and the joint log
likelihood. Draw empirical-CDF diagnostics against Uniform(0,1) with declared
finite-case uncertainty bands. Weighted particles approximate a posterior;
their stored count is not a count of independent exact posterior draws.
Likewise, autocorrelated reference-chain draws must not be presented as IID
SBC rank samples. Use posterior-CDF diagnostics and disclose their finite
Monte Carlo uncertainty; a rank implementation must explicitly handle dependence
and its finite-rank reference distribution.

The ecological panel reports the same coefficient accuracy, coverage and
interval widths, but does not apply a universal 90% calibration claim. Record
feature correlations, rank/conditioning, fraction of saturated observations,
and posterior correlations, especially between infrastructure return and
spillover. Compare methods on the same observed stream before attributing a
coverage difference to ecological complexity.

At 90% coverage, the binomial standard error is about 2.65 percentage points
for 128 independent datasets and 3.75 points for 64. These panels can diagnose
large failures; they cannot certify one-percentage-point calibration accuracy.
Treat separate parameters, posterior test quantities and methods as related
diagnostics, not multiple independent opportunities to declare success.

## Decision and evidence contract

If published SMC disagrees with a qualified reference and the higher-budget fit
reduces that discrepancy, report numerical sensitivity as the supported finding.
If both SMC settings match the reference while ecological coverage remains low,
do not describe more particles as the remedy; investigate the task distribution,
conditional model and observation contract. If SBC fails for the reference as
well, first investigate generator/likelihood agreement and reference quality.
Passing marginal SBC alone cannot establish all aspects of posterior correctness.

Before institutions use uncertainty to select or suppress reports, the findings
must identify a defensible inference setting or explicitly retain the unresolved
limitation. New code or observation-model changes require a newly named version
and another untouched panel. No outcome-dependent extra cases, silent old-budget
extensions or deletion of negative results are allowed.

Save the frozen design, source snapshots, exact datasets, posterior summaries,
CDF values, fit diagnostics, failures, reference retry records and artifact
hashes. Chromatic Field figures should show coverage with case denominators,
CDF departures, paired SMC/reference discrepancies, and error versus compute.
Use labels/markers for methods; reserve society colors for society identities.
Render and inspect SVG/PDF/PNG outputs. The protocol is planning material until
the frozen run supplies recorded evidence.
