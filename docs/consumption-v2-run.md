# Consumption-focused follow-up

The follow-up tests whether institutional coevolution improves consumption when
infrastructure earns no direct welfare bonus. It compares coevolution with
member-only search under the same initial fixed institutions. Both start from
the original mixed population. Episodes last 48, 60, or 72 ticks; drought
begins at a variable, unobserved fraction of the episode. Matched no-drought
rollouts isolate the modeled disturbance's effect.

The initial campaign is a **matched pilot: one independent run per condition,
30 active search minutes each, 60 minutes total**. It cannot establish a
replicated claim about the search procedure. The implementation supports
independent paired replications through a separate campaign manifest.

The [prospective protocol](protocol-consumption-v2.md) fixes selection and
analysis before fresh outcomes. The original simulator, protocol, sources,
figures and evidence remain reproducible. V2 uses its own simulator module,
scenario adapter, selection evaluator and output directory.

## Start, status and resume

From the repository with the existing pinned environment:

```bash
.venv/bin/python scripts/prepare_consumption_study.py --campaign-dir runs/consumption-v2 --replicates 1 --minutes-per-run 30
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json
```

The prepared directory and its budgets are immutable. Do not run preparation
again for an existing campaign. Observe its current state with:

```bash
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --status
```

After an interruption:

```bash
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --resume
```

The supervisor continues unfinished arms using only their remaining budgets.
It never extends a completed allowance. Only one inference/evaluator pipeline
runs at a time. The model remains `gpt-6-astra`, `xhigh`, `fast`, authenticated
through ChatGPT; paid APIs and auxiliary inference remain disabled. Search
parent/proposal RNG seeds are recorded; subscription inference itself is
stochastic and resume does not promise the same future proposal sequence.

After both searches terminate normally, the supervisor automatically evaluates
the initial population and both final populations on the protected common
panel. Each population receives 108 drought cases and 108 exact no-drought
counterfactuals. Fresh evaluation is separately timed, uses two local workers,
and makes no inference calls. Its results are written to
`runs/consumption-v2/fresh/summary.json`; the search comparison uses run-level
paired differences. Manually retry only that stage if needed:

```bash
.venv/bin/python scripts/evaluate_consumption_study.py --plan runs/consumption-v2/campaign.json --workers 2
```

## Checkpoints and provenance

| Path within `runs/consumption-v2/` | Contents |
|---|---|
| `campaign.json` | Frozen ordered run specifications, equal budgets, protocol/panel hashes and postprocessing command |
| `campaign_checkpoint.json` | Active arm, aggregate used budget and postprocessing state |
| `protected_fresh_cases.json` | Fresh scenario bank, excluded from proposal feedback |
| `pair-01-*/run_plan.json` | Frozen evaluator, prompt, starting program and immutable context hashes |
| `pair-01-*/programs.sqlite` | Native Shinka archive and proposal ancestry |
| `pair-01-*/evolution_context.json` | Current ecological population, exact comparisons and replacements |
| `pair-01-*/budget_checkpoint.json` | Per-arm remaining allowance and resource measurements |
| `pair-01-*/subscription_calls/` | Actual subscription traces and reported token usage |
| `fresh/` | Common-case outcomes and paired no-drought comparisons after search |

Full checkpoints and logs stay outside Git. The code, frozen scientific
protocol, tests and compact launch evidence are published. New figures and a
scientific interpretation require completed fresh results; none are asserted
at launch.
