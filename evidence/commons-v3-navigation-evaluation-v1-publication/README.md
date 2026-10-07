# Navigation evaluation publication verification

The [public archive catalog](../../artifacts/commons-v3-navigation-evaluation-v1/catalog.json)
restores **56 files / 6,452,815 bytes** from
[the navigation evidence release](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-navigation-2026-10-07). The
[publication receipt](publication.json) binds this phase to source checkpoint
`9cf537d796dad367f95e933f4cc53e840a63903f` and records all checks.

The archive, per-file manifest and phase catalog were downloaded without
authentication and compared byte for byte with their local copies. Using the
downloaded catalog and an empty cache restored every original file into an
empty directory. An independent byte comparison, offline archive verification
and restoration into a second empty directory all passed. No simulations,
policy selection or model calls occurred during publication.

- [Local archive verification](local-archive-verification.json)
- [Source-bank integrity before publication](bank-integrity-before-publication.json)
- [Hosted asset URLs, sizes and SHA-256](release-assets-public.json)
- [Public restoration](public-restoration.json)
- [Per-file byte comparison](restored-byte-comparison.json)
- [Offline archive verification](offline-verification.json)
- [Offline restoration](offline-restoration.json)
- [Exact packaging script](package_phase.py.txt)
- [Exact publication verification script](verify_public_phase.py.txt)

The release was created at `cc9c2fe95a397de567d093daf1e47e1e240fc3a2`. Its
`immutable` setting is `false`; committed
hashes detect changed assets without claiming administrative immutability.
This phase uses new asset names and preserves all earlier archive identities.

[Additional preservation checks](tuning-assets-preserved.json) confirm that all
three tuning asset IDs, sizes and downloaded bytes, plus 15 frozen local tuning
publication artifacts, are unchanged after evaluation assets were added.
