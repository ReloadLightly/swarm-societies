# Need-targeted development validation

These compact receipts cover the separate
[need-targeted checkpoint](../../docs/commons-v3-need-v1.md). The study and its
protocol were frozen before its 56 configurations / 224 episodes ran. No
experimental model calls, evolutionary runs or public archive uploads occurred.

| Check | Recorded result |
| --- | --- |
| Exact semantic replay | [56 cases / 224 episodes verified](replay.json); canonical JSON comparisons, without floating tolerance |
| Independent numerical audit | [29,055 checks passed](independent-audit.json); maximum discrepancy 1.080025e-12 |
| Targeted commons tests | [235 passed](commons-tests.log), including 73 new policy and runner tests |
| Full default invocation | [769 passed and 123 subtests passed](full-tests.log); eight localhost-server tests failed at socket creation under the sandbox |
| Loopback retry | [All eight passed](loopback-tests.log), without code changes; 777 unique tests pass across the two invocations |
| Recorded figures | [All 12 gallery files rerender identically](figure-verification.json); both PNGs inspected by renderer author and primary reviewer |
| Local archive | [56 files / 3,647,037 payload bytes](local-packaging.json), packaged and [verified](local-archive-verification.json) |
| Empty-directory restoration | [56 restored, none pre-existing](offline-restoration.json); [all payloads byte-identical](restored-byte-comparison.json) |
| Cached archive | [Offline verification passed](offline-archive-verification.json) |
| Preservation | [707 protected tracked files and 112 earlier raw cases unchanged](preservation.json); only six existing living-document/ignore files edited |
| Scientific report | [Final independent claims review](report-review-final.json); [earlier review](report-review.json) retained |

The original test log retains all eight `PermissionError` failures. They occur
while constructing synthetic `127.0.0.1` HTTP servers, before download behavior
is exercised. The targeted retry enables loopback sockets and selects exactly
those eight tests; its other 35 archive tests are deselected. This is not a
claim that a single unrestricted full-suite invocation was run. The full
invocation took 626.90 seconds and the retry 5.47 seconds, with other validation
work overlapping the first invocation. Timing is not a performance comparison.

The [independent audit script](independent_audit.py) uses only the standard
library and imports neither physics nor the study's aggregation functions. It
reconstructs consumption, shortfall, final-quarter totals, inventory, costs,
ecological endpoints and paired focal/peer/world/utility contrasts from recorded
agent and trajectory primitives. Its tolerance is
`2e-12 * max(1, abs(actual), abs(expected))` for accumulation-order differences.
This diagnostic tolerance never changes physics, the policy, an acceptance
decision or the strict semantic replay. Per-agent and per-patch residual
maxima are saved diagnostics rather than independently reconstructed physical
ledgers. Source hashes and every cell's comparison are retained in the audit
receipt.

Reproduce that audit from the repository root, after restoring the new cases:

```bash
.venv/bin/python evidence/commons-v3-need-validation-v1/independent_audit.py \
  --source evidence/commons-v3-need-v1 --output runs/need-independent-audit.json
```

The output path must be new. [Study commands](../../docs/commons-v3-need-v1.md#verification-and-reproduction)
cover freeze, execution, semantic replay and figure regeneration. The
[separate archive catalog](../../artifacts/commons-v3-need-v1/README.md) supports
this workspace's offline cache and documents fresh-checkout regeneration.
Its `source_url` is null: no remote download or GitHub synchronization is claimed.

`preservation.json` compares all pre-existing tracked files with the initial
working-tree inventory. The six expected changes are `.gitignore`, `AGENTS.md`,
`PROGRESS.md`, `README.md`, `docs/commons-v3-plan.md` and `docs/study-index.md`.
Every other tracked file remains byte-identical, and both preceding banks'
112 raw files match their original completion manifests. The initial working
tree was clean. `validation.json` pins this validation bundle, final new
implementation/tests/reports, evidence and figure manifests, and archive catalog.
