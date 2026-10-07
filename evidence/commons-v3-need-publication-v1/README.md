# Need-targeted archive publication verification

The completed need-targeted development archive was published as three assets
in release
[`commons-v3-need-2026-10-07`](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-need-2026-10-07),
targeting `536ed64cb733f2091afd9c9c7905531826519ff7`.
The [publication receipt](publication.json) records the release identity,
source commit, exact hashes and successful checks.

Unauthenticated public downloads of the archive, public manifest and catalog
matched their local bytes. Using the downloaded catalog and an initially empty
cache, restoration into an empty directory recovered **56 files / 3,647,037
bytes**, each independently compared byte for byte with the original bank.
Offline archive verification and restoration into a second empty directory
also passed. These are archive-integrity checks, not new experiments or
scientific qualification. No policy runs or experimental model calls occurred.

Receipts:

- [Local archive verification and manifest parity](local-archive-verification.json)
- [Public asset URLs, sizes and SHA-256 hashes](release-assets-public.json)
- [Public restoration](public-restoration.json)
- [All 56 restored-file byte comparisons](restored-byte-comparison.json)
- [Offline archive verification](offline-verification.json)
- [Offline restoration into another empty directory](offline-restoration.json)
- [Preservation of the original local-only metadata](local-metadata-preservation.json)
- [Exact verification script](publication-audit.py.txt)

The [new public catalog](../../artifacts/commons-v3-need-publication-v1/catalog.json)
adds public retrieval while preserving the historical local-only catalog,
manifest, inventory and README byte-for-byte. The archive itself is unchanged.
The release reports `immutable: false`; committed hashes detect changed assets
without claiming administrative immutability. The manifest in this directory
pins the verification records, public metadata and tooling.
