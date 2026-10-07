# Local navigation and numerical-baseline validation

These receipts cover the separately frozen
[navigation study](../../docs/commons-v3-navigation-v1.md). Its 324 tuning
episodes and 336 fresh comparison episodes are complete. No experimental
model calls or evolutionary runs occurred. All earlier banks remain preserved.

| Check | Recorded result |
| --- | --- |
| Prospective source/design freeze | [Remote commit `b16a239` verified before tuning](prospective-freeze.json) |
| Selection before evaluation | [Remote commit `cc9c2fe` verified before evaluation](evaluation-freeze.json); exact selection binds sources, tuning and evaluation design |
| Exact tuning replay | [All 324 episodes pass](tuning-replay.json), without numerical tolerance |
| Exact evaluation replay | [All 336 episodes pass](evaluation-replay.json), without numerical tolerance |
| Independent primitive/aggregate audit | [163,114 exact and 93,983 numerical checks pass](independent-audit.json); maximum absolute difference 1.705303e-12 |
| Recorded engineering invariants | [All 660 episodes](recorded-invariants.json) have zero unaffordable known returns; 655 have exactly zero extraction waste, five have rounding-level totals ≤1.421086e-14; maximum accounting residual 4.399814e-13 |
| Commons tests | [300 passed](commons-tests.log), including 39 new policy and 26 new runner tests |
| Full suite | [842 tests and 123 subtests passed](full-tests.log) in one invocation, with loopback permission for synthetic archive servers |
| Recorded figures | [All 18 gallery files rerender byte-identically](figure-verification.json); all three PNGs inspected by renderer author and primary reviewer |
| Public tuning archive | [324 files restored publicly and offline, byte-identically](../commons-v3-navigation-tuning-v1-publication/README.md) |
| Public evaluation archive | [56 files restored publicly and offline, byte-identically](../commons-v3-navigation-evaluation-v1-publication/README.md); earlier tuning assets preserved |
| Preservation | [781 protected tracked files and 168 earlier raw cases unchanged](preservation.json) |
| Report review | [Independent claims review](report-review.json) compares final research claims with recorded evidence |

The phase replay receipts cover each episode once: evaluation replay checks
tuning hashes, aggregation and selection but does not resimulate tuning. The
`episodes: 660` field in that receipt counts the whole study; only its 336
evaluation episodes are physically replayed in that invocation. The separate
tuning receipt establishes the other 324 exact comparisons. Six reference
episodes also check physical snapshot continuation under identical future
committed actions; policy-memory checkpoint recovery is not established.

The [independent audit](independent_audit.py) uses only the standard library.
It imports no engine, policy, runner, aggregator or renderer. It reconstructs
agent consumption, inventory, utility, trajectory outcomes, all candidate
scores, exact selection and all 14 evaluation-cell contrasts. Source and
artifact hashes, seed sets and the candidate/condition inventory are exact.
Eighteen frame checks independently reconstruct available spatial diagnostics.
Known-site counts and joint hungry/off-site counts remain saved aggregates
where full per-tick policy memories or per-agent records were not archived.
Per-agent/per-patch accounting maxima are saved diagnostics, not an independent
physics derivation.

Accumulation checks use `2e-12 * max(1, abs(actual), abs(expected))`; the maximum
scaled discrepancy is 6.972751e-15. This tolerance never changes physics,
controller execution, exact candidate ranking, selection, sign-count thresholds
or semantic replay. Summary sign counts retain their frozen ±1e-12 rule.
Unoccupied stock divides by total site capacity; it does not establish
reachability. Positive-shortfall counts can include numerical-scale amounts.

After restoring both raw archives, reproduce the independent audit with a new
output path:

```bash
.venv/bin/python evidence/commons-v3-navigation-validation-v1/independent_audit.py \
  --source evidence/commons-v3-navigation-v1 --output runs/navigation-audit.json
```

The [study report](../../docs/commons-v3-navigation-v1.md#verification-and-reproduction)
gives archive restoration, phase replay and fresh reproduction commands.
Completed and failed banks are preserved; the runner refuses a completed rerun.
Interrupted banks verify and preserve complete cases. Public assets use
separate versioned identities and committed hashes; GitHub hosting is not
administratively immutable.

`preservation.json` compares the pre-navigation inventory at `d2b5274` with
the final files. Only six earlier living-document/ignore paths may change:
`.gitignore`, `AGENTS.md`, `PROGRESS.md`, `README.md`, `docs/commons-v3-plan.md`
and `docs/study-index.md`. Every other pre-existing tracked file remains
byte-identical, and all three earlier raw banks match their original manifests.
The final validation manifest pins the receipts, new source/tests/report,
completion and figure manifests, and both public catalogs.
