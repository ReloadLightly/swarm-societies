# Foundation repairs v1

This implements the numerical portability and execution-containment work in
[Stage 0 of the commons plan](commons-v3-plan.md). It changes how evidence is
checked and how supplied policies are evaluated. The frozen physical engines,
scientific protocols, original verifiers and published evidence remain intact.
It does not implement the spatial world or start another evolution campaign.

## Portable calibration verification

`scripts/verify_calibration_portable_v1.py` copies the original semantic
verification flow, with attribution and an immutable hash inventory for its ten
scientific dependencies. It reconstructs the observations, retained-sample
likelihoods, reference diagnostics, posterior summaries, tables and summaries.
It neither reruns posterior fitting nor changes stored data.

Only reference `rhat`, `bulk_ess` and `tail_ess` scalars receive the new rule
`abs(recorded - recomputed) <= 1e-12 + 1e-12 * abs(recomputed)`. This applies
to the main reference diagnostic, each retained attempt and the corresponding
log-likelihood diagnostics. Shapes, scalar types, thresholds, qualification,
retry decisions, source identity and file hashes remain exact. Even a tolerated
float difference fails if it crosses an individual qualification threshold.
Nonfinite values fail. The original likelihood reconstruction already used
`rtol=1e-9, atol=1e-10`; that separate rule is preserved and disclosed.

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_calibration_portable_v1.py \
  --source evidence/world-model-calibration-v1 \
  --receipt runs/calibration-portable-v1/receipt.json
```

Receipts record runtime versions, input and source hashes, tolerances, every
unequal diagnostic location, maximum deviations and the verification outcome.
Use a new receipt path outside the frozen evidence directory. Both successes
and semantic failures receive receipts; existing receipts cannot be replaced.
The original strict command remains available for historical reproduction.
This narrower portability repair does not establish universal calibration or
relax the known likelihood-CDF and conditional-model limitations.

## Bounded policy execution

`swarm_societies/execution_v1.py` runs allowlisted, plain-JSON jobs in a fresh
Linux subprocess. Resource limits apply before candidate compilation. Defaults
are 768 MiB address space, 15 CPU seconds, 30 wall seconds, 8 MiB request,
16 MiB result, and 64 KiB each for stdout and stderr. The parent enforces the
wall deadline and output bounds and terminates the worker process group on
failure. NumPy/SciPy imports have been checked under these limits; substantial
numerical studies may require explicitly chosen higher limits.

Workers use a cleared environment, disabled user-site/unsafe-path loading and
`PYTHONHASHSEED=0`. JSON transfer preserves dictionary insertion order. Frozen
seed-policy trajectories match the direct engines exactly; policies whose
behavior depends on set iteration also need the same hash seed for a direct
comparison. Receipts pin execution and engine sources and record the runtime
and actual applied resource limits.

Sources cross the boundary as bounded inline text. Arbitrary callables, pickle
and user-selected import targets are unsupported. Candidate syntax validation
still uses the frozen runtime. This is resource containment, **not an OS
security sandbox**. The direct Python APIs and frozen command-line runners
remain for audited, trusted policies. Use the new entry points below for new
or untrusted policies; installing these wrappers does not automatically reroute
old callers.

For a fresh episode or replay:

```bash
.venv/bin/python -m swarm_societies.run_bounded_v1 episode \
  --engine consumption-v2 \
  --programs seeds/initial.py seeds/cooperative.py seeds/selfish.py \
  --seed 101 --replay --receipt runs/bounded-replay-v1/receipt.json
```

The other engine names are `legacy`, `world-model-v1` and `stepwise-v1`.
Optional `--config` accepts an ecology configuration JSON file. `--members`
accepts a society-by-member matrix of policy paths relative to that JSON file.
World-model engines also accept `--world-parameters` and `--observation-mode`.
Existing receipts are never replaced.

For scripted evaluations, `execute_job(job, limits=ExecutionLimits(...))`
returns an explicit success or failure receipt. The CLI provides the same
interface through `job --input job.json --receipt receipt.json`. Supported jobs
include a single `candidate_policy` call, `candidate_validate`, complete episodes,
a normalized `consumption_case`, and `stepwise_advance`. Episode jobs use
`programs: [{"source": "...", "name": "..."}, ...]` and an optional
`member_programs` matrix of the same descriptors. `consumption_case` takes the
frozen scenario object in `case` and an optional boolean `disturbance`.

`batch --input jobs.json --output runs/new-batch` takes a bounded JSON list of
independent jobs. It records each failure, continues later jobs, and writes a
summary with per-receipt hashes. The output directory must be new. This is an
execution utility; it does not supply a new scientific case bank or silently
replace the frozen fresh-panel study design. A batch has per-job limits; an
outer search/campaign supervisor still owns its aggregate time budget.

`stepwise_advance` initializes from episode inputs plus `steps`, or continues
from `snapshot` plus `steps`. It returns a new snapshot and, upon completion,
the episode result. The CLI can continue a raw saved snapshot with:

```bash
.venv/bin/python -m swarm_societies.run_bounded_v1 advance \
  --snapshot runs/checkpoint.json --steps 1 \
  --receipt runs/checkpoint-next/receipt.json
```

Snapshots contain evaluator-only hidden laws and RNG state. They must never be
given to a candidate as an observation. A single `candidate_policy` call starts
a fresh program; use full episodes or stepwise snapshots to preserve mutable
module state across ticks. Failures do not rewrite the supplied checkpoint.
Override limits using the global `--limits limits.json` option before the
subcommand. Unsupported platforms fail explicitly.

## Search commit boundary

`scripts/evaluate_search_bounded_v1.py` accepts the historical `--program_path`,
`--results_dir` and `--context` arguments, plus `--engine legacy` or
`--engine consumption-v2`. The parent holds the context lock. Validation and
paired simulations run only in bounded workers; a failed or incomplete job
cannot provide a selection score or change the incumbent. The parent records
the rejection and retains child receipts. Repeated completed or failed job IDs
are idempotent. Outputs are recoverable from the committed context.

This adapter deliberately retains the historical objectives, alternating
schedule and `new > old + 1e-9` rule for parity. Stronger margins, held-out
admission and new search arms belong to the separately versioned future
protocol. Existing search budgets remain exhausted. Pointing an old campaign
at this evaluator does not grant another allowance.

## Validation and remaining work

The full repository suite passes **470 tests and 123 subtests** in 230.39
seconds. The added repair coverage accounts for 118 tests and 21 subtests.

Both Python 3.13.5 and Python 3.12.13 with NumPy 2.5.3/SciPy 1.18.1 verify all
**192 cases, 401 artifacts and 4,283,648 retained sample likelihoods**. Each
compares 4,620 reference diagnostic scalar locations, including repeated
attempt records, with zero drift on this machine. One-ULP acceptance and
threshold-crossing rejection are exercised separately by regression tests;
the reviewer's reported 72/576 drift count has not been reproduced here.

A third check with Python 3.11.15, NumPy 2.4.6 and SciPy 1.17.1 rejects the first
case: its feature-condition-number audit differs by 1.776e-15. That field is
outside the tolerance whitelist. This is a documented compatibility limit,
not evidence corruption or a changed reference qualification. Use the pinned
numerical versions for the documented reproductions; these checks do not
establish portability across every numerical stack. The failed receipt is
retained alongside the two passing receipts.

Focused tests cover diagnostic roundoff and threshold crossings, evidence
tampering, malformed jobs, child memory/CPU/wall/output failures, deterministic
episode parity, checkpoint continuation and incumbent preservation. A normal
80-tick, three-society/six-member replay matches the complete frozen result;
its bounded worker took 1.23 seconds and peaked at 23,808 KiB RSS on this host.
All 301 declared source/input hashes across 28 inventories match. Compact
receipts and the repository test record are archived in
[`evidence/foundation-repairs-v1/`](../evidence/foundation-repairs-v1/).

External data publication/restoration and the shorter README remain separate
Stage 0 tasks. The next scientific implementation is the versioned spatial
physics and commons calibration gate, followed by optional political formation
and strong baselines. Institutional emergence or a positive coevolution effect
will not be required outcomes.
