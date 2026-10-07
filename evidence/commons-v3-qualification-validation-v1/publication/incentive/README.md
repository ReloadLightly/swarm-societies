# Incentive qualification publication verification

The [catalog](../../../../artifacts/commons-v3-incentive-qualification-v1/catalog.json) restores
**224 files / 453,051,247 bytes** from the
[qualification evidence release](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-qualification-2026-10-07). All three public assets match
their local bytes and hashes. Public verification used no authentication.

An empty cache and empty destination restored every original file. Offline
archive verification and restoration into a second empty destination also
passed. These operations did not run simulations or model calls.

- [Publication receipt](publication.json)
- [Completed bank verification](bank-integrity-before-publication.json)
- [Local archive verification](local-archive-verification.json)
- [Public asset identity and hashes](release-assets-public.json)
- [Empty-cache restoration](public-restoration.json)
- [Per-file byte comparisons](restored-byte-comparison.json)
- [Offline verification](offline-verification.json)
- [Offline restoration](offline-restoration.json)
- [Exact publication script](publish_phase_v1.py.txt)

The source checkpoint is `e895b72103c41408e262cbf199e7cc98740a7fb8`; the release target is
`ead7cfcec95decbdd8be213093f30b8ccec15d60`. GitHub reports
`immutable: false`. Hashes detect altered
assets without claiming that administrators cannot change the release.

[Ecology preservation checks](ecology-assets-preserved.json) confirm unchanged earlier asset IDs, sizes, downloaded bytes and all frozen local publication files.
