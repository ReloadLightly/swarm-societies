# Frozen-program transplant diagnostic

This is a post-hoc mechanism experiment on the single completed consumption-v2
coevolution lineage. Its design and program snapshots were frozen in
`manifest.json` before evaluating its new environment bank. It uses no model
inference and does not supply independent evolutionary replication.

The four conditions cross initial/evolved members with initial/evolved
institutions: `initial`, `members_only`, `institutions_only`, and `coevolution`.
The new bank contains twelve balanced-marginal horizon/timing tuples crossed
with three frozen opponent panels and three focal society identities. Each
case has an exact matched no-drought counterpart: 216 rollouts per condition,
864 total. Opponents always use the designated frozen seed panel; this tests
focal society transplants, not a simultaneous all-descendants ecology.

Environment seeds use a new, disjoint integer namespace. These cases are
unseen by the original search, but the mechanism question was chosen after
viewing previous results. Treat results as exploratory. All member programs
and institutions live in the portable `programs/` directory.

`contrasts.json` records paired member effects at each institution background,
institution effects at each member background, and the factorial interaction
`coevolution - members_only - institutions_only + initial` for every case.
`summary.json` reports environment-seed cluster bootstrap intervals. They
describe environmental variation conditional on this selected lineage, not
uncertainty across evolutionary searches. A positive interaction in welfare
means that the combined transplant exceeds the sum of its isolated effects
on this additive scale; it does not establish evolved reciprocity.

Consumption welfare has ceiling 0.85 and equals
`0.85 - 1.5 × shortfall per member-tick`. Welfare and shortfall therefore
encode the same primitive outcome. Raiding harm, private utility, and effects
on other societies remain separate. Society 2's unchanged institution provides
an exact negative control for institutional transplant effects.

Reproduce from this evidence directory without original run checkpoints:

```bash
.venv/bin/python scripts/verify_mechanism_evidence.py --evidence evidence/mechanism-v1
```

To regenerate rollouts, copy `manifest.json` and `programs/` into a new
directory, preserving relative paths, and run:

```bash
.venv/bin/python scripts/run_mechanism_study.py evaluate --output /tmp/mechanism-reproduction --workers 2
```

The runner checks frozen simulator/analysis source hashes, resumes completed
condition files, and verifies factorial pairing, material conservation, exact
pre-drought matching, aggregates, and the unchanged-institution control.
The additive publication audit also verifies every raw scenario against the
manifest, top-level summary values and counts, and the original data checksums.
Recorded program digests allow deterministic rollout comparisons after moving
the evidence directory. No frozen v1/v2 simulator or evidence was changed.
`portable-replay-check.json` records eight additional verification rollouts
regenerated from a temporary copy of the portable sources; all rows and episode
digests match the experimental results exactly.
