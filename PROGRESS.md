# Work record

Objective: implement, execute, analyze, visualize and publish the first complete experimental increment of Swarm Societies. No additional environment or unrelated infrastructure is in scope.

Repository: `/home/roland/actir/swarm-societies`, origin `https://github.com/ReloadLightly/swarm-societies.git`. Initially empty unborn `main`, with no existing work or applicable repository instructions.

Implementation complete: protected material-accounted ecology; configurable societies and members; private state and shared institutional memory; separately inherited member and institutional programs; actual upstream ShinkaEvolve/native Headless integration; subscription-only execution; protected fresh-case evaluation; source/lineage archive; replay and scientific figures.

Search complete: exactly 3,600 cumulative active seconds, `gpt-6-astra`, `xhigh`, `fast`, ChatGPT authentication. Nine unique evaluator programs: eight valid including the initial program and one invalid mutation. Ten native database rows additionally include one documented infrastructure failure. Six replacements accepted: three members and three institutions. One valid mutation tied. Nine completed model calls reported 257,830 input / 131,185 output tokens; two interrupted calls have unknown usage. Peak sampled process-tree RSS 438.4 MiB. Terminal audit confirms all processes stopped and SQLite integrity passed.

Fresh results complete: five conditions × 108 common cases. Descendant post-drought welfare .92287 versus initial .86098; individual utility 50.82 versus 56.24; post shortfall 1.162 versus .770; outward harm 0 versus 37.78. The welfare difference decomposes into infrastructure bonus +.06679 and consumption/shortfall contribution −.00490. Higher encoded welfare does not show improved consumption resilience. Evolved institutions collect more tax and enforce raid restrictions; voluntary contributions decline and no intersociety aid emerged. One exploratory search run only.

Scientific checks: frozen simulator/runtime/protocol hashes, archived source dependencies, common cases, exact means, material conservation, selection objectives and archived-source replay verified. The 20-test repository suite passed; the upstream recovery suite passed 40 tests. Final plots and README report actual outcomes and limitations.

Work package: implementation, search, fresh evaluation, analysis and visual inspection are complete. Publication target is origin/main; the committed repository contains the scientific record and reproduction commands. The next proposed experiment removes the direct infrastructure bonus, randomizes disturbance timing/horizon, and compares multilevel versus fixed-institution search across independent runs. It has not been started.

Full resumable checkpoints remain locally in ignored `runs/first/`: `programs.sqlite`, `evolution_context.json`, `budget_checkpoint.json`, exact settings, program snapshots, prompts and call logs. Upstream checkouts are ignored `.cache/upstream/`. Compact reproducible evidence is in `evidence/experiment/`; publication figures are in `figures/`.

Resume command:

```bash
.venv/bin/python scripts/run_evolution.py --run-dir runs/first --budget-minutes 60 --resume
```

The allowance is exhausted, so this command is now a no-op. Replay needs no inference and no local checkpoints:

```bash
.venv/bin/python -m swarm_societies.experiment replay --run-dir evidence/experiment --seed 424242 --output /tmp/swarm-replay.json
.venv/bin/python scripts/verify_evidence.py --require-final
```
