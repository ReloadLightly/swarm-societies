# Active work record

Active objective: run the consumption-focused follow-up to the completed first
Swarm Societies experiment. User authorized starting it on 2026-10-05.

**Running:** `runs/consumption-v2/campaign.json`, launched at
2026-10-05 04:44:57 UTC (06:44:57 Europe/Berlin). This is a matched pilot with
one run per condition, 30 active search minutes each, 60 minutes total.
The fixed-institution arm runs first; coevolution is queued next. The initial
native Shinka evaluation is valid and subscription inference is starting.
Exact live state is in `campaign_checkpoint.json`, not this static record.

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

Next automatic step: after both search budgets finish, the supervisor runs the
protected fresh panel for the initial population and both final populations
(108 drought cases plus 108 no-drought counterparts each). Results appear in
`runs/consumption-v2/fresh/summary.json`. Next interactive step: inspect completed
search/fresh outcomes, analyze inherited changes, render the follow-up figures
and publish its scientific results. Do not alter the frozen study mid-run.

```bash
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --status
.venv/bin/python scripts/run_consumption_study.py --plan runs/consumption-v2/campaign.json --resume
```

Resume only after interruption; a running campaign holds its lock. Per-arm
budgets cannot be extended on resume. Full native archives, ecological state,
source snapshots, model traces and accounting remain in ignored
`runs/consumption-v2/pair-01-*/`. See `docs/consumption-v2-run.md` for all commands.

The first work package was published as commit
`0073a0d26aeb1e8b40ab65535d47050c42feb72a`. Its evidence/figures remain unchanged.
Its 60-minute search retained three member and three institutional changes;
higher welfare came from the infrastructure bonus while consumption shortfall
worsened. Full original checkpoints remain in ignored `runs/first/`, exhausted.
