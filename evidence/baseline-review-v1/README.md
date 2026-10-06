# Exploratory simple-baseline review

This separate diagnostic reconstructs the external review's described policy:
always harvest the fullest visible patch at effort one, with zero tax,
investment, defense, reserve and raiding. The review supplied no policy source.
The reconstructed source reproduces every reported digit of its mechanism-panel
table; this does not establish that the unseen original source was identical.

The focal institution and all four focal members are replaced together. The
existing mechanism-v1 cases, opponents, identities and drought settings remain
fixed. There are **12 environment/timing tuples, 108 focal scenarios and 216
paired drought/no-drought rollouts**, with **zero new evolutionary searches and
zero model-generation calls**. This is an exploratory comparison made after the
published results, conditional on one existing evolutionary lineage. Neither
108 scenarios nor 216 rollouts are independent search replications.

| Drought outcome | Initial | Coevolved | Reconstructed greedy |
|---|---:|---:|---:|
| Focal consumption welfare | 0.844263 | 0.846926 | 0.848654 |
| Unmet need/member/tick | 0.003825 | 0.002050 | 0.000897 |
| Focal private utility/member/tick | 0.933662 | 0.965109 | 1.038674 |
| Outward raid loss/focal society/tick | 0.602067 | 0.534878 | 0.000000 |
| Other societies' mean welfare | 0.847117 | 0.846872 | 0.845842 |

The simple policy improves mean focal utility by **0.073565**, or **7.6225%**,
relative to the saved coevolved population. This is a bundled policy
replacement, not an isolated estimate of the effect of removing raids. Its
focal welfare is higher in 23 scenarios, tied in 84, and lower in one; its
private utility is higher in 106 and lower in two. Its mean welfare across all
three societies is lower by 0.0001104. Zero recorded outward harm means zero
raid-victim losses; harvesting competing patches can still affect outsiders.

Welfare is exactly `0.85 − 1.5 × unmet need/member/tick`, so those two rows are
one primitive outcome. Means do not demonstrate universal dominance or quantify
uncertainty across independent evolutionary searches. No new confidence claim
is made. The reconstruction reaches the welfare ceiling in 101/108 drought
scenarios and 107/108 no-drought scenarios.

`policy.py`, `audit.py`, `provenance.json`, `baseline.json`, and `comparison.json`
are byte-identical copies of the original diagnostic files under
`runs/review-v3/greedy-mechanism-check/`. `manifest.json` hashes these files and
this README, and identifies the existing frozen source and comparator inputs.
The archive uses the unchanged files in `evidence/mechanism-v1/` for its
comparators; retain that evidence directory alongside this one.

The [recorded-data figure](../../figures/baseline-review-v1/README.md) includes
focal and outsider outcomes. Rendering never runs the simulator.

## Reproduction

From the repository root, use a fresh directory at the same three-level
layout; do not execute the archived runner inside the evidence directory. The
runner refuses to overwrite its outputs.

```bash
mkdir -p runs/review-v3/reproduction
cp evidence/baseline-review-v1/audit.py evidence/baseline-review-v1/policy.py \
  runs/review-v3/reproduction/
.venv/bin/python runs/review-v3/reproduction/audit.py
.venv/bin/python scripts/visualize_baseline_review.py
```

The numerical baseline rows, episode digests and aggregate comparisons should
match. Fresh provenance records have a new timestamp and source-path keys;
comparison-file provenance hashes consequently differ. These metadata
differences are not numerical differences. The original frozen simulator,
programs, study inputs and published outputs were not changed.
