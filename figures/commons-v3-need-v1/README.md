# Need-targeted physical development · Chromatic Field v1

Recorded exploratory development on the same four seeds and 56 configurations
as the saved v2 foundation bank. This is **not untouched qualification**.
The new bank has 224 episodes and adds need-targeted harvest
policies with zero or two needs of soft inventory reserve, plus one focal
greedy replacement for each baseline. Inventory capacity is 80 in the grid;
the separately declared small-inventory sensitivity remains 8. No institutions,
evolutionary runs or experimental model calls enter these comparisons.

![Population comparison](baseline-comparison.png)

[SVG](baseline-comparison.svg) · [PDF](baseline-comparison.pdf) · [PNG](baseline-comparison.png)

**Population caption.** Panels A and B compare means over four paired seeds for
the two new all-need-targeted populations and the saved v2 all-restraint and
all-greedy populations, across the complete nine-cell ecological grid.
Condition markers have small vertical offsets to expose coincident values;
horizontal positions retain the data values. Consumption is divided by
declared need; terminal ecological stock is divided by total site capacity.
Consumption failure and loss of the entire ecological stock are distinct.
Panels C and D show unsmoothed per-tick means over the four seeds of the
predeclared reference cell, r=0.24,
need=1.2; its row is shaded and starred above.
Line styles and markers identify conditions. No society colors are assigned.
The v2 curves are loaded from the hash-checked frozen figure table; old cases
are neither restored nor rerun by this renderer.

![Paired focal effects](focal-effects.png)

[SVG](focal-effects.svg) · [PDF](focal-effects.pdf) · [PNG](focal-effects.png)

**Focal-effects caption.** One predeclared focal individual switches to the
frozen v2 greedy policy while the other 23 agents retain need-targeting with
the indicated reserve. Each point is the mean paired difference across four
seeds; whiskers are observed minimum–maximum differences, **not confidence
intervals**. The two columns share scales within each row. Panels A and B
show `(consumption + wealth_weight × terminal_inventory) / horizon`, divided
by declared need. Weight 0 therefore represents consumption alone. Panels C
and D show per-peer mean consumption differences divided by need. Focal IDs
vary with seed; agents and ticks are not independent replicates. The focal
replacement changes a policy bundle, including navigation and harvesting,
so its effects do not identify an isolated mechanism. Four seeds are reused
across parameter cells, sensitivities and the preceding development banks.

Tables retain all saved cells, including the five declared sensitivities:

- [All condition means, including saved v2 conditions](condition-means.csv)
- [Paired focal effects, terminal inventory and utility weights](focal-effects.csv)
- [Paired reserve-2 minus reserve-0 effects](reserve-effects.csv)
- [Reference trajectories for every new and saved v2 condition](reference-trajectories.csv)

Effect-table values retain their original units. Focal consumption and utility
are per individual per tick; peer consumption is per peer per tick; terminal
inventory is an unnormalized endpoint. Population summary fields retain the
units declared in their names. Blank fields represent absent old diagnostics,
not zero measurements. Consumption and shortfall are complementary accounting
outcomes and must not be counted as independent welfare results.

The renderer calls `development_need_v1.verify(source, replay=False)` before
reading new data. This checks the source freeze, hashes, inventory and saved
aggregate without running policies or physics. Full semantic replay belongs
to the separate study verifier. Frozen v2 manifest hashes are pinned in this
renderer; the v2 design and summary must match their artifact hashes and all
new case configurations exactly. The old trajectory CSV must match its frozen
gallery manifest and evidence-manifest binding. This verifies a saved compact
projection; it does not repeat the v2 aggregate or semantic verification.

The manifest records all new evidence source hashes, the compact v2 comparison
inputs, renderer/helper hashes, software versions and exported file hashes.
Same-runtime rerenders are deterministic; cross-version byte identity is not
asserted. Every SVG, PDF and PNG export is retained.

```bash
.venv/bin/python scripts/visualize_commons_v3_need_v1.py \
  --source evidence/commons-v3-need-v1 \
  --comparison evidence/commons-v3-foundation-v2 \
  --comparison-figures figures/commons-v3-foundation-v2 \
  --output figures/commons-v3-need-v1
```
