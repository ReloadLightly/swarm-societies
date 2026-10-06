# Visual reference and scientific encodings

The user-requested read-only reference is
[ReloadLightly/actir-backprop-neat](https://github.com/ReloadLightly/actir-backprop-neat),
inspected at revision `9472743f1cb7ea12eafcf489126b1a43b8f5735f`.
Only its tree, README, `docs/VISUAL_STYLE.md`, `scripts/visual_theme.py`, and
`scripts/plot_study.py` were fetched in a shallow, blob-filtered temporary clone.
Its experimental datasets, archives, and dependencies were not downloaded.

The reference uses **Chromatic Field v1**: opaque warm white (`#FFFEFC`),
dark text (`#161625`), secondary text (`#6F6A78`), cobalt (`#3534CF`),
magenta (`#C93683`), orange (`#F26A37`), and fine rules (`#DCD7E0`).
We use the same visual tokens with DejaVu Sans, generous panel spacing,
readable labels, right-aligned numeric tables, and deterministic SVG, PDF,
and PNG exports. The implementation here is independently written; no
reference experimental results enter this study.

Society IDs retain their colors across every frame: 0 cobalt, 1 magenta,
2 orange, then teal, violet, and clay. Program conditions are identified
by explicit labels rather than being confused with society identities.
Replay member letters identify actions; resource flows have directed arrows,
and raids use dashed lines. Replay geometry is schematic and never implies
physical spatial dynamics absent from the simulator.

Figures load recorded evidence only. Fresh-case means remain separate from
search fitness. Missing search, invalid candidates, and absent descendants
must remain visible; no invented learning curve or inheritance is allowed.
Environmental cases are not independent evolutionary replications.
Solid lineage arrows denote source inheritance; named dashed links reference
the ecological comparison incumbent when it differs from the donor. Nodes
follow source ancestry rather than evenly spaced generation time. Only a
retained proposal replaces its comparison incumbent. These relationships do
not establish causal effects of individual changes.

Search points show the archived score minus one: the normalized improvement
over a matched incumbent. They remain unconnected because successive
proposals can have different objectives and partner populations. Society
colors, update-type markers, and retained-update outlines have separate keys.
The welfare decomposition displays primitive consumption shortfall and
infrastructure beside the scoring equation, keeping the infrastructure bonus
visible when interpreting adaptation.

Render with:

```bash
.venv/bin/python -m swarm_societies.visualize \
  --summary evidence/experiment/summary.json \
  --replay evidence/experiment/replay.json --output figures
```

The figure manifest records source hashes, export hashes, software versions,
captions, and exact animation frame selection. Static replay panels show the
last recorded frame; GIFs retain the disturbance boundary and sampled frames.

## Continuing experiment series

Every new experiment should include Chromatic Field figures derived from its
saved evidence, with SVG, PDF and PNG exports, a caption explaining the unit of
comparison, and a manifest connecting inputs to outputs. Inspect the rendered
images for overlap, clipping and misleading scales. Keep previous experiment
exports unchanged in their original directories.

Use factorial panels for component swaps, paired-effect plots for interventions,
payoff matrices for cross-play, and phase diagrams for ecological parameter
sweeps. Give quantitative plots priority over decorative swarm imagery. Label
schematic replays explicitly. A new finding should have an appropriate figure
as part of the same work package.

Show absolute differences alongside relative percentages when endpoints are
near a ceiling or floor. Distinguish environmental variation conditional on a
frozen population from uncertainty across independent evolutionary searches.
For consumption v2, welfare is exactly `0.85 − 1.5 × shortfall/member/tick`;
plotting both explains the units, but provides only one independent outcome.

Architecture diagrams may illustrate proposed systems when explicitly labeled
as designs without experimental data. The
[world-model architecture](../figures/world-model-design/README.md) follows the
same style and export conventions. It contains no hypothetical learning curves.
