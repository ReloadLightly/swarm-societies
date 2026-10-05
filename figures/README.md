# Recorded experiment figures

Figures are rendered from saved evidence. Rendering performs no search or evaluation.

Visual tokens follow the inspected [reference](../docs/visual-reference.md). Source and output hashes are in `manifest.json`.

## results-table

[SVG](results-table.svg) · [PDF](results-table.pdf) · [PNG](results-table.png) · [Markdown](results-table.md) · [CSV](results.csv)

Fresh evaluation means on common environment seeds and partner/opponent snapshots. Each row is a recorded program condition. Cases are not independent evolutionary runs. Welfare before and after the disturbance, individual utility, and other societies’ welfare remain distinct. Missing values are displayed as em dashes.

## evolution-performance

[SVG](evolution-performance.svg) · [PDF](evolution-performance.pdf) · [PNG](evolution-performance.png)

Recorded search scores minus one: (candidate objective − incumbent objective) / max(1, |incumbent objective|). Each point is an evaluated candidate; outlined diamonds denote retained updates. Member objectives are private utility; institution objectives are society welfare. Fitness can change with partner composition. No observations, trajectories, descendants, uncertainty bands, or global best curves are fabricated when absent.

## program-lineages

[SVG](program-lineages.svg) · [PDF](program-lineages.pdf) · [PNG](program-lineages.png)

Each box is a recorded program with its normalized matched search gain, scheduled update unit, retention status, and changed source components. Component changes compare the full proposal to its source donor; only the scheduled member or institution unit enters the ecology when retained. Solid arrows connect proposal donors; named dashed orange links reference ecological comparison incumbents when different from the donor. Nodes are arranged by source ancestry, not evenly spaced generation time. Only retained candidates replace incumbents. The overview shows initial roots and the latest 12 nodes by generation, without selecting on fitness; additional numbered pages preserve all nodes in chronological groups of 12. Off-page parent IDs remain inside each box. Disconnected roots are initial programs or fixed references. Ancestry does not identify a causal contribution of a code change. Full IDs and change descriptions remain in the source JSON.

## cooperation-conflict

[SVG](cooperation-conflict.svg) · [PDF](cooperation-conflict.pdf) · [PNG](cooperation-conflict.png)

Fresh-case means of cumulative material units across the complete episode (60 ticks in the first run), not per-tick rates. Within-society pooling equals voluntary contributions plus compulsory taxes and must not be interpreted as exclusively voluntary cooperation. Between-society aid measures material transfers to other societies. Between-society conflict measures material harm imposed on other societies. These outcomes remain distinct.

## welfare-decomposition

[SVG](welfare-decomposition.svg) · [PDF](welfare-decomposition.pdf) · [PNG](welfare-decomposition.png)

Post-disturbance means on the same fresh cases as the results table. Left: total consumption shortfall per focal society during the post-disturbance phase; lower means fewer unmet needs. Right: mean infrastructure stock during that phase. The welfare formula is (phase consumption − 0.5 × phase shortfall) / (members × phase ticks) + 0.03 × mean infrastructure. Infrastructure therefore adds an explicit bonus: increasing it can raise welfare even when consumption shortfall worsens. These primitive outcomes must be considered separately when interpreting adaptation. No independent evolutionary-run uncertainty is available from a single search run.

## ecology-replay

[SVG](ecology-replay.svg) · [PDF](ecology-replay.pdf) · [PNG](ecology-replay.png) · [Animation](ecology-replay.gif)

A recorded episode, using stable society colors. Circles represent members and their current action, squares treasuries, diamonds resource patches; directed arrows show material flows. Society layout is schematic, not simulated physical movement. The static panel is the last recorded frame. The GIF samples at most the requested frame count plus disturbance boundary frames; its exact frame indices are preserved in the manifest.

## disturbance-response

[SVG](disturbance-response.svg) · [PDF](disturbance-response.pdf) · [PNG](disturbance-response.png)

The exact recorded replay episode shows society welfare and private wealth through the disturbance, indicated by a dashed vertical line. This illustration is not a population mean, a fresh-case comparison, or an independent evolutionary replicate. Lines join recorded per-tick observations; colors retain society identities.
