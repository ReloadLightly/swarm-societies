# Active work record

Active objective: run the consumption-focused follow-up to the completed first
Swarm Societies experiment. User authorized starting it on 2026-10-05.

**Completed:** both 30-minute arms exhausted their original allowances and
fresh evaluation finished at 2026-10-05 05:51:42 UTC (07:51:42 Europe/Berlin).
All search and evaluation processes have stopped. No budget was extended.
Fixed institutions retained six member changes; coevolution retained three
member and two institutional changes. All 11 evaluated mutations were valid.

Fresh consumption welfare: initial .843162, fixed institutions .846405,
coevolution .847238. Coevolution had 23.2% less unmet consumption than fixed
institutions, but 65.2% more outward harm and 1.8% lower private utility per
tick. Both evolved populations improved consumption relative to initial.
Only one paired pilot was run; the small welfare difference is exploratory.
Compact results and audit: `evidence/consumption-v2/final-summary.json` and
`completion.json`. Full case rows and inherited sources remain in local
checkpoints pending the detailed follow-up publication.

Question: does institutional coevolution improve consumption welfare compared
with equal-budget member-only search under fixed institutions? V2 removes the
direct infrastructure bonus, varies horizon (48/60/72 ticks) and drought timing,
and evaluates exact matched no-drought counterfactuals. Both arms start from the
same original mixed population. Private utility remains separately selected
and measured. One paired pilot does not establish a replicated search claim.

Frozen protocol: `docs/protocol-consumption-v2.md`. Code, prompt, source and
scenario definitions are hashed before search. Candidate feedback contains
aggregate objectives/outcomes; exact schedules and fresh cases are excluded.
The route remains actual upstream ShinkaEvolve through ChatGPT-authenticated
Codex, `gpt-6-astra`, `xhigh`, `fast`. No paid API or auxiliary inference.

Validation: all 46 tests passed; frozen first-experiment evidence still verifies
and its replay regenerates exactly. V2 material dynamics match v1; no-drought
pairs preserve exogenous draws. The v2 search benchmark measured 3.63 episodes/s
and 21.9 MiB peak RSS. Compact launch evidence: `evidence/consumption-v2/`.

Automatic fresh evaluation completed all 648 rollouts: initial population and
both final populations, each with 108 drought cases and 108 matched no-drought
counterparts. Saved results: `runs/consumption-v2/fresh/summary.json`.
Next work: finish the detailed inherited-program analysis, render the follow-up
figures and publish the complete scientific evidence. Do not start additional
inference without a new run budget. Independent paired replications are needed
before claiming an advantage for the search procedure.

```bash
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --status
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --resume
```

The campaign is complete; resume will not start additional search. Per-arm
budgets cannot be extended on resume. Full native archives, ecological state,
source snapshots, model traces and accounting remain in ignored
`runs/consumption-v2/pair-01-*/`. See `docs/consumption-v2-run.md` for all commands.

The first work package was published as commit
`0073a0d26aeb1e8b40ab65535d47050c42feb72a`. Its evidence/figures remain unchanged.
Its 60-minute search retained three member and three institutional changes;
higher welfare came from the infrastructure bonus while consumption shortfall
worsened. Full original checkpoints remain in ignored `runs/first/`, exhausted.
