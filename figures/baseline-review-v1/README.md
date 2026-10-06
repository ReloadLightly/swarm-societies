# Simple baseline review · Chromatic Field v1

![Recorded focal and outsider outcomes](baseline-outcomes.png)

[SVG](baseline-outcomes.svg) · [PDF](baseline-outcomes.pdf) · [PNG](baseline-outcomes.png) · [Exact means](means.csv)

Recorded drought means from 108 matched focal scenarios: 12 environment/timing
tuples, three opponent panels and three focal identities. The initial and
coevolved conditions are saved programs from one existing search lineage. The
greedy condition is an exploratory reconstruction of an externally described
policy; its original source was not supplied. All four members and the focal
institution are replaced together. No new search or model call was made.

Each panel has a separate, explicitly displayed axis range. Markers identify
conditions; they do not encode society identity. Means have no uncertainty bars
and do not demonstrate universal dominance. Welfare and unmet need are the same
primitive outcome: welfare = 0.85 − 1.5 × unmet need/member/tick. Focal private
utility is (consumption + 0.2 × terminal wealth) per member per tick. Outward
raid loss counts victim losses, not all ecological effects. Other societies'
welfare decreases under the reconstructed baseline despite zero outward raids.

The evidence includes 216 new paired drought/no-drought rollouts; this figure
uses the drought half. The [archive](../../evidence/baseline-review-v1/README.md)
contains reconstruction choices, raw rows, comparisons, provenance and hashes.
The renderer reads recorded data only and checks hashes, complete paired grids,
summary arithmetic and the welfare identity before export.

Re-render from the repository root:

```bash
.venv/bin/python scripts/visualize_baseline_review.py
```
