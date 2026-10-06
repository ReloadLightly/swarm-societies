# Frozen program transplant figures

These Chromatic Field v1 figures show the completed exploratory factorial
diagnostic: 864 rollouts, four member/institution combinations, twelve new
environment schedules, three opponent panels and three focal society
identities. Every drought rollout has a matched no-drought counterpart.
The figures below display drought outcomes. All programs come from one
coevolution lineage; this is not independent replication of search.

## Factorial outcomes

[PNG](factorial-outcomes.png) · [SVG](factorial-outcomes.svg) · [PDF](factorial-outcomes.pdf)

Four-cell means cross original/evolved members with original/evolved
institutions. Shading encodes magnitude separately within each panel; darker
does not always mean better. Welfare equals `0.85 − 1.5 × unmet consumption
per member per tick`, so welfare and shortfall are two views of one outcome.
Private utility includes terminal wealth. Harm is outward raid loss per
focal society per tick.

## Institutional effects on welfare

[PNG](institution-effects.png) · [SVG](institution-effects.svg) · [PDF](institution-effects.pdf)

Each society's institution is swapped while retaining its original or evolved
members. The difference between these effects is the additive factorial
interaction. Diamonds are means; circles are paired environment means over
opponent panels. The circles describe environmental variation conditional on
one lineage, not search-level uncertainty. Society 2 has an unchanged
institution and provides an exact negative control.

## Institutional effects on outward harm

[PNG](institution-harm-effects.png) · [SVG](institution-harm-effects.svg) · [PDF](institution-harm-effects.pdf)

The same institutional contrasts applied to raid losses imposed on neighbours.
Positive values mean more harm. Society 1's evolved institution adds harm only
with its evolved members in these cases. This is an effect of the complete
institutional program; individual rules have not been isolated. Raid harm and
other societies' total welfare are different measurements.

## Reproduce

```bash
.venv/bin/python scripts/visualize_mechanism_study.py
```

The renderer reads [recorded evidence](../../evidence/mechanism-v1/README.md)
only and validates case coverage, scenario equality and manifest identity.
[manifest.json](manifest.json) records input/output hashes, software versions
and captions. See the [study interpretation](../../docs/mechanism-study.md).
