# External temptation probe reproduction, 7 October 2026

The user supplied `scripts/v3_temptation_probe.py` after the initial file search.
Its source ran unchanged with a transparent capture hook that saved each
`record_episode` return value before returning it to the original caller.
This record contains 64 episodes: seeds 90001–90008, the frozen fixed-floor
controller, focal identity 0, 256 ticks, storage capacities 80 and 8, zero or
23 aggressive peers, and both focal branches. All 64 episodes replay exactly;
the saved raw records reproduce the original stdout and summary exactly.

At capacity 80 among restrained peers, restrained focal consumption is
99.852921% of need. Aggression gains 0.001471 of need in consumption
[−0.000126, 0.003067]. At weight 0.05, the gain is 0.013893
[0.012296, 0.015489], of which **89.4132% is terminal inventory**.
At capacity 8 the weight-0.05 gain falls to 0.002174 [0.000578, 0.003770].
At capacity 80 against 23 aggressive peers, the consumption-only gain is
0.070589 [0.049163, 0.092015].

The additional capacity-8 endpoint matters: against 23 aggressive peers,
the consumption-only mean gain is **−0.001681 [−0.075374, 0.072012]**.
Its sign is unresolved. The supplied review's broad mechanism reproduces,
but these descriptive comparisons do not establish a formal assurance game,
best responses, equilibria, or a qualified social dilemma. Intervals use the
original script's ordinary 95% Student-t critical value 2.365 (seven degrees
of freedom). The zero-peer consumption interval spans zero; it does not prove
exact equivalence. The intervention changes a whole policy bundle.

No frozen bank, simulator, controller, utility weight or qualification rule
was edited. No experimental model calls, evolution or numerical selection
occurred. Seed declarations in all 13 existing frozen `design.json` files
were checked for overlap; their hashes, declared values and source copies
are preserved in this record.

Files:

- `original-stdout.txt`: all twelve original weight/capacity/peer contrasts.
- `summary.json`: unrounded estimates, decomposition and all focal seed rows.
- `design.json`, `sources.json`, `sources/`: exact execution provenance.
- `manifest.json`: hashes and sizes for every raw episode and primary record.
- `capture-receipt.json`, `replay-receipt.json`: capture and exact replay results.
- `cases/`: full compressed primitive episode records, published separately.
- [Recorded-data figure](../../figures/commons-v3-temptation-review-v1/README.md):
  SVG, PDF and PNG exports with source/output hashes and an inspected render.

Replay after restoring the separately archived raw records:

```bash
.venv/bin/python scripts/capture_v3_temptation_probe_v1.py verify \
  --output evidence/commons-v3-temptation-review-v1
```

Run the supplied standalone probe again without changing this completed bank:

```bash
.venv/bin/python scripts/v3_temptation_probe.py
```
