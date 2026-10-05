# ShinkaEvolve engine and subscription transport

This experiment runs the **actual upstream ShinkaEvolve engine**, revision
`9912af12d423504b8d580f4179fd15f5f88b8c50` (package version `0.0.7`), from
[SakanaAI/ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve/tree/9912af12d423504b8d580f4179fd15f5f88b8c50).
Upstream supplies asynchronous proposal orchestration, full/diff mutation parsing,
weighted parent sampling, its program archive, database, and crash recovery.
The project supplies the interacting ecology, protected evaluator, ecological
selection and inheritance, and a small subscription transport adapter. The
Shinka search island is **not** a simulated society: the first run uses one
search island and three interacting societies.

## Verified route and actual settings

The local Codex configuration selected `gpt-6-astra`, reasoning effort `xhigh`,
and service tier `fast`. These settings were preserved. Codex CLI `0.160.0`
reported `Logged in using ChatGPT`; the authentication file reported
`auth_mode=chatgpt` with no API key. No credentials are copied or recorded.

Upstream's native Headless provider accepts
`headless/codex@gpt-6-astra?effort=xhigh`. Its documented
`SHINKA_HEADLESS_COMMAND` extension calls this repository's
`swarm_societies/shinka_bridge.py`, which translates the Headless CLI protocol to
`codex exec --json --ephemeral`. This avoids an additional npm wrapper while
retaining upstream's provider and evolutionary engine. A direct Codex smoke
returned `SUBSCRIPTION_ROUTE_OK`; a second smoke through the actual Shinka
Headless provider returned `SHINKA_SUBSCRIPTION_OK`.
The latter reported 9,173 input tokens, 34 output tokens, and 21 reasoning
output tokens. Exact compact probe evidence is in `evidence/route-probe/`.

The adapter requires ChatGPT login for every invocation, removes provider API
keys and alternative OpenAI endpoints from the environment, and explicitly sets
`forced_login_method="chatgpt"`. The engine has `embedding_model=None`,
`meta_rec_interval=None`, no novelty-model calls, no prompt evolution, and no
W&B logging. No paid API, embedding, or judging calls are permitted. Token
counts are usage measurements, **not** a monetary estimate: a subscription call
has no inferred per-call API price. The upstream database's numeric cost zero
must not be interpreted as zero economic cost or unlimited subscription use.

The Shinka configuration requests a temperature of zero, but the Headless
transport and Codex CLI do not forward or expose that setting. The effective
inference temperature is therefore unspecified; this is not deterministic
inference. Upstream parent sampling and patch-type selection use unseeded
Python/NumPy randomness in this first run. Environment seeds are recorded and
evaluation is deterministic for a fixed program and population, but replaying
the search or resuming a checkpoint does not promise an identical future
proposal trajectory. Resume preserves the ecological state, database and
remaining time allowance.

The inference process starts in an empty temporary directory with user config
and rules ignored. Shell tools, unified exec, apps, plugins, multi-agent tools,
browser tools, image generation and image viewing are disabled; web search is
disabled and host skill discovery skipped. The candidate receives its supplied
prompt, donor program, and search feedback. Holdout scenarios are not supplied
to the mutation model. The evaluator separately validates and executes candidate
policy code in its restricted API; inference restrictions are not a substitute
for that boundary.

Official background: [Codex authentication](https://learn.chatgpt.com/docs/auth)
and [non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode).
The successful live probes establish compatibility for this account and model;
they do not establish future availability or remaining subscription allowance.

## Search budget, progress and resume

```bash
.venv/bin/python scripts/run_evolution.py --run-dir runs/first \
  --context runs/first/evolution_context.json \
  --initial-program seeds/initial.py --budget-minutes 60

.venv/bin/python scripts/run_evolution.py --run-dir runs/first \
  --context runs/first/evolution_context.json \
  --initial-program seeds/initial.py --budget-minutes 60 --resume
```

The supervisor's budget is 3,600 cumulative active search seconds, including
engine initialization and the initial candidate evaluation. It updates
`budget_checkpoint.json` each second and prints progress every 30 seconds.
An interruption retains the remaining budget. An ungraceful supervisor crash
conservatively charges another ten seconds on resume. A still-running supervisor
is detected before a second process can start. Resuming an exhausted budget
does not start further search.

At the budget boundary the process group is killed, including any in-flight
proposal or evaluation; only completed evaluations count. SQLite transactional
recovery and the evaluator's atomic ecological snapshots support continuation.
An interrupted inference may have consumed subscription resources without a
completed usage event; such usage is unknown and must not be counted as zero.

The local scheduler timeout is twenty minutes because this upstream revision
measures it from **proposal start**, including up to fifteen minutes of model
inference. The evaluator independently caps CPU time at 120 seconds. In the
first run, an initial three-minute scheduler setting killed generation 1 before
evaluation after a 326-second inference. The original failed database entry is
retained, and classified as an infrastructure failure. The corrected run resumed
with 3,203.836 seconds remaining; the in-flight generation 2 call was interrupted
and has unknown usage. Exact evidence is in `evidence/engine-recovery.json`.
No diagnostic evaluation of generation 1 was admitted to ecological selection.

An offline host-side smoke exercised the actual engine's seed evaluation and
resume; the upstream checkpoint/recovery suite passed all forty tests. When only
generation 0 exists, upstream may insert the seed again on resume; the evaluator
deduplicates its job path, so this does not repeat ecological replacement. Search
program-row counts and unique evaluated candidates are therefore reported
separately. Ordinary resume after a proposal restores the native engine state.

Key checkpoints and evidence (large run files stay out of ordinary Git):

| File under `runs/first/` | Purpose |
|---|---|
| `programs.sqlite` | Native Shinka candidates, donor ancestry and search fitness |
| `evolution_context.json` | Ecological population and lineage checkpoint |
| `budget_checkpoint.json` | Cumulative allowance and measured resources |
| `actual_settings.json` | Exact model, route, concurrency and search settings |
| `engine_console.log`, `supervisor.log` | Progress and failure evidence |
| `gen_*/` | Candidate source, evaluator output and mutation attempts |
| `headless_prompts/`, `subscription_calls/` | Full prompts, response JSONL and usage |

Inference, evaluation and database concurrency are each one. Archive size is
eight; migrations and dynamic island spawning are disabled. Measured simulator
throughput informed this choice; strict sequential evaluation also gives each
candidate an unambiguous, frozen ecological context. Search archive scores are
proposal heuristics from their recorded contexts. Ecological replacement is
decided by a fresh matched comparison against the incumbent in the current
population, not by stale archive rankings.

To install the pinned engine in an existing environment:

```bash
uv pip install --python .venv/bin/python -r requirements-shinka.txt
```

Upstream source is Apache-2.0 licensed. ShinkaEvolve and Codex are attributed as
the mutation/search machinery; changes in the policy/institution programs are
an experimental result, not changes in the underlying language model weights.

## Completed first run

The run exhausted its 3,600-second cumulative allowance on 2026-10-05. The
[terminal audit](../evidence/engine-terminal.json) confirmed that every search
and inference process had stopped and SQLite integrity was `ok`. Nine unique
programs reached ecological evaluation (eight valid including the initial
program, one invalid); the native database also retains one pre-evaluator
infrastructure failure. Six replacements were accepted, three per selection
level. One valid mutation tied its incumbent and was not retained.

Nine completed search calls reported 257,830 input tokens (22,656 cached) and
131,185 output tokens (99,926 reasoning). Cached and reasoning counts are
subsets. Interrupted generations 2 and 11 have unknown usage. Probe usage is
excluded and remains separately archived. Peak sampled process-tree RSS was
459,743,232 bytes (438.4 MiB). The sampled live-process CPU total is incomplete
because exited children are excluded. See the [final summary](../evidence/experiment/summary.json)
for the complete accounting and [README](../README.md#results) for outcomes.

`runs/first/` remains the full local checkpoint. The documented 60-minute resume
command now exits without additional inference because no allowance remains.
