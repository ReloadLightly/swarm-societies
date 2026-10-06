# Foundation repair verification

Verification receipts for the supplemental calibration checker and bounded
policy execution. These are engineering checks, not new evolutionary runs or
scientific treatment comparisons. No experimental model calls were made.

| File | Check |
| --- | --- |
| `calibration-py313.json` | All 192 saved calibration cases pass on Python 3.13.5, NumPy 2.5.3, SciPy 1.18.1 |
| `calibration-py312.json` | Same full-bank check passes on Python 3.12.13 with the same numerical versions |
| `calibration-py311-rejected.json` | Older numerical stack fails on an audit float outside the permitted tolerance fields |
| `portable-tests-py312.log` | 67 focused verifier tests pass on the second passing runtime |
| `default-replay-parity.json` | Complete default 80-tick consumption replay equals the frozen direct engine |
| `frozen-sources.json` | 301 declared hashes from 28 inventories pass, covering 158 distinct checked paths |
| `full-tests.log` | Full repository regression test output |
| `validation.json` | Test result, reproduction commands and source identities |
| `manifest.json` | Archive byte sizes/hashes and implementation source hashes |

The calibration checks reconstruct 4,283,648 retained sample likelihoods and
verify 401 artifacts each. All 4,620 compared diagnostic locations match
exactly in these two complete replays. Synthetic one-ULP regressions exercise
the new tolerance. This does not reproduce the external review's 72/576 count
or establish universal numerical portability.

The rejected Python 3.11.15/NumPy 2.4.6/SciPy 1.17.1 check differs at
`evaluation-prior_predictive-000/audit/feature_condition_number`:
5.316990220125069 recorded versus 5.316990220125071 reconstructed. The checker
does not relax this unrelated audit field. Original archived bytes and all
scientific qualification decisions remain unchanged.

These receipts are exact copies of the completed checks. Runtime paths and
timestamps describe this checkout; the temporary second environments need not
exist on another machine. The replay parity summary hashes the larger local
execution receipt, which is kept under ignored `runs/foundation-repairs-v1/`;
the summary records its result digest and frozen source identities. Recreate
that receipt using the seed-101 replay command in the
[repair report](../../docs/foundation-repairs-v1.md).

The [report](../../docs/foundation-repairs-v1.md) documents the tolerance scope,
execution defaults, supported entry points and remaining work. No frozen
runner, simulator, protocol or previous evidence was modified.
