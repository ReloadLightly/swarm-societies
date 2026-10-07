# Commons v3 incentive review figures

Recorded incentive evidence only, in Chromatic Field v1. No ecology figure layer, new simulation or changed qualification verdict.

![Reference peer curves](reference-peer-curves.png)

Reference rate 0.24, need 1.2, capacity 80, 256 ticks. Each point changes only the focal policy at a fixed assignment of 0, 6, 12, 18 or 23 aggressive peers. Means and ordinary descriptive 95% seed-level Student-t intervals use 16 matched seeds, 65001–65016. All gains are aggressive minus restrained, divided by need; weight 0 is consumption only. Straight segments guide the eye between observed counts, without interpolating a tipping point. Peer prevalence is k/23; total aggressive prevalence is k/24 or (k+1)/24. These intervals are not the simultaneous qualification intervals. Conditions use explicit panel labels; no societies or institutions are present.

[SVG](reference-peer-curves.svg) · [PDF](reference-peer-curves.pdf)

![Storage decomposition](storage-decomposition.png)

Reference zero-aggressive-peer substitution, 16 paired seeds. Bars separate mean consumption and terminal-inventory contributions to utility at the unchanged weight 0.05, divided by need. Black diamonds show their sum with ordinary descriptive 95% seed-level Student-t intervals. Capacity 8 is the frozen sensitivity. Positive inventory and negative consumption can cancel; these are not new qualification tests.

[SVG](storage-decomposition.svg) · [PDF](storage-decomposition.pdf)

Regenerate with `.venv/bin/python scripts/visualize_commons_v3_incentive_review_v1.py`. The [manifest](manifest.json) binds source, renderer and exports.
