# World-model calibration audit

Recorded-data Chromatic Field v1 figures. This separately versioned numerical audit preserves the published learner and its original evidence.

Bank: **evaluation**. Independent prior-predictive cases: **128**. Independent ecological cases: **64**. Evolutionary runs and model-generation calls: **0**.

Reference qualification: Prior-predictive control 128/128 references pass; 0 fail; Ecological task panel 64/64 references pass; 0 fail.

Method settings are shown as particle count / rejuvenation sweeps. Methods use neutral marker and line encodings; no method is assigned a society color. Reference checks are necessary diagnostics, not proof of an exact posterior. Reference failures remain in all-case coverage, CDF and cost summaries, and are excluded only from qualified agreement.

## parameter-coverage

[SVG](parameter-coverage.svg) · [PDF](parameter-coverage.pdf) · [PNG](parameter-coverage.png)

Coverage of terminal 90% marginal credible intervals against simulator coefficients, with mean interval widths printed alongside. Dots and horizontal lines give all-case coverage and 95% Wilson binomial intervals over independent cases, including nonzero uncertainty when all cases cover. Every case is retained, including failed reference outcomes. Prior-predictive controls draw true laws from the learner's full prior and have exogenous features. Ecological cases draw laws from the narrower task distribution and use pooled histories from interacting fixed-policy societies; this is coverage under the fitted conditional likelihood, not a prior-predictive calibration test. The nominal 0.90 line has different inferential meanings in those panels. Method identity uses labels and neutral markers, not society colors.

## posterior-agreement

[SVG](posterior-agreement.svg) · [PDF](posterior-agreement.pdf) · [PNG](posterior-agreement.png)

Agreement with an independently implemented batch MCMC posterior on cases passing its prespecified rank-normalized R-hat and bulk/tail effective-sample-size checks. Small linked marks pair individual cases across SMC settings; larger marks and horizontal lines show case means and 95% bootstrap intervals. Both SMC settings use the same qualified cases, and the paired-agreement-contrasts CSV reports paired budget effects. Mean discrepancies are divided by reference posterior SD; interval widths are ratios to the reference; endpoint discrepancies are divided by the public prior width. Lower discrepancies and width ratios near one indicate closer numerical agreement. Small vertical ticks in mean panels show mean reference mean-MCSE divided by posterior SD, providing numerical-noise context rather than a hard significance threshold. Passing convergence diagnostics does not prove exact computation, and differences near reference Monte Carlo uncertainty must not be overinterpreted. The failed-reference denominator remains visible; those cases are excluded only from this qualified agreement, not raw coverage or CDF diagnostics. Frozen-prior agreement is retained in the derived CSV but omitted from this scale-focused SMC comparison.

## compute-accuracy

[SVG](compute-accuracy.svg) · [PDF](compute-accuracy.pdf) · [PNG](compute-accuracy.png)

Top panels report recorded fitting CPU cost for all cases, including unsuccessful references and retry computation. Bottom panels use only the shared qualified-reference cases, plotting fitting CPU seconds against each case's average standardized marginal posterior-mean discrepancy over r, b and g. Small symbols are cases and large symbols show means with 95% case bootstrap intervals on each axis. Chains, particles and coefficients are not independent replications. Fitting CPU includes inference, reference convergence diagnostics and retries; it excludes separately timed full-data CDF scoring and is machine-dependent. SMC processes the observations sequentially, whereas the batch reference fits the complete history once at its terminal point, plus any prescribed retry. These costs describe work to reach a terminal posterior, not matched online latency or a planning benchmark. The batch reference has its own Monte Carlo error; its cost is shown without treating it as an exact zero-error ground truth. Higher computation is a sensitivity comparison, not a changed production default.

## cdf-diagnostics

[SVG](cdf-diagnostics.svg) · [PDF](cdf-diagnostics.pdf) · [PNG](cdf-diagnostics.png)

Empirical CDF minus uniform CDF for each method's posterior CDF evaluated at simulator truth, separately for coefficients and the data-dependent log-likelihood statistic. One value per independent case is used; failed references remain in the raw curves. Each panel has its own vertical range to retain the unupdated prior's likelihood discrepancy without compressing coefficient diagnostics. In the prior-predictive cohort only, the gray band is the 95% Dvoretzky–Kiefer–Wolfowitz simultaneous bound for one ECDF under an independent uniform null. It is not a multiplicity-adjusted bound over all methods or quantities. Finite weighted particles and correlated reference draws make these approximate CDF diagnostics, not exact exchangeable discrete SBC ranks. Ecological curves are descriptive: narrower law draws and latent-outcome-dependent feature generation prevent interpreting them as the same uniform-null test. Marginal prior-predictive checks alone can accept an unupdated prior, so the data-dependent likelihood check is also shown. A successful CDF check does not establish useful learning or accurate decisions.

## Derived tables and provenance

[Coverage](coverage-statistics.csv) · [Posterior agreement](agreement-statistics.csv) · [Paired budget effects](paired-agreement-contrasts.csv) · [Compute](compute-statistics.csv) · [CDF diagnostics](cdf-statistics.csv) · [Source/output hashes](manifest.json)

Cases are the independent units. Coverage uses 95% Wilson binomial intervals. Other intervals use 2,000 bootstrap draws and seed 8307; paired methods share case identities. Tables are derived from recorded primitives and checked against the frozen summary. The renderer runs no training or ecological evaluation.

```bash
.venv/bin/python scripts/visualize_world_model_calibration.py
```
