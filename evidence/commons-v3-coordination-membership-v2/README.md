# Coordination and responsive membership engineering fixtures

[fixture.json](fixture.json) is a compact constructed engineering record,
not a sampled development/evaluation bank. It includes exact initial political
and physical states, all controller memories and future scripted actions,
source hashes, full decision/receipt/material traces and continuation checks.
Its SHA-256 is
`d505b0577c23d18bd7d3c9ffacf84e5f9142fe81549b67c10efbef9549f0d8e9`.

The [contract and interpretation](../../docs/commons-v3-coordination-membership-v2.md)
explain the new information affordance, static forecasts, affordable tie-entry,
voluntary quota promises and limitations. The four constructed checks cover
paid delayed communication with a staged message-removal control, responsive
exit and delayed refund, optional formation, and refusal for insufficient
protected liquidity. The sender's real payment remains in both message branches;
its scripted completion and the recipient's fresh controller are explicit setup.

All 18 continuation ticks reproduce decisions, private receipts and material
flows. Maximum absolute residual is 1.10e-14. The
[validation receipt](validation.json) records 680 passing v3 tests and 110
passing final focused tests, source preservation and fixture hashes. Zero model
calls, evolution, policy selection or sampled-bank episodes occurred.

Reproduce into a new output path:

```bash
.venv/bin/python scripts/demo_commons_v3_coordination_v2.py --full-trace \
  --output /tmp/commons-v3-coordination-v2-fixture.json
```

The output refuses overwrites. These small fixtures remain in Git; there is no
new bulk archive. Earlier experimental banks, raw archives, figures and verdicts
are unchanged. A real institutional comparison requires a new prospective
protocol and independent evaluation beyond these fixtures.
