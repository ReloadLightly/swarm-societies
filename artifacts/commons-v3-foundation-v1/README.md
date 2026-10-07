# Commons v3 foundation case archives

This separate [catalog](catalog.json) contains only the 56 raw `cases/*.json.gz`
files from each completed development bank. Designs, summaries, completion
manifests, source snapshots and figures remain in the repository. Both banks
remain exploratory development evidence; v2 repeats the same cases after the
documented numerical navigation repair.

| Bank | Files | Original bytes | Archive bytes | Per-file SHA-256 manifest |
| --- | ---: | ---: | ---: | --- |
| Foundation v1 | 56 | 4,588,051 | 4,598,907 | [v1 inventory](commons-v3-foundation-v1.json) |
| Foundation v2 | 56 | 4,698,984 | 4,709,686 | [v2 inventory](commons-v3-foundation-v2.json) |

Total: **112 files, 9,287,035 original bytes; 9,308,593 archive bytes**.
The archives are slightly larger because their input case files are already
compressed. Each catalog entry pins the bank's design, completion manifest and
source manifest. The published release targets implementation commit
`e7c7cbb9b861ae5202324d2cee76fae8ad702381`; the catalog's source hashes were
recorded before that commit existed.
The packager runtime is recorded in the catalog. Archive byte reproduction is
scoped to the same Python/zlib toolchain; individual file checksums are exact.

The manifests name assets in release
[`commons-v3-foundation-2026-10-07`](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-foundation-2026-10-07).
All five hosted archive/metadata assets match their local sizes and SHA-256
digests. Public, unauthenticated download into an empty cache restored all 112
files in an actual clean checkout, byte-identical to the originals. Offline
verification also passed. [Validation records](../../evidence/commons-v3-foundation-validation-v1/README.md)
preserve the receipts. Release
assets are hash-pinned, not guaranteed server-immutable. Published archive
identities must be preserved; corrections require a new version.

```bash
python3 scripts/restore_evidence_v1.py --catalog artifacts/commons-v3-foundation-v1/catalog.json --study all
python3 scripts/restore_evidence_v1.py --catalog artifacts/commons-v3-foundation-v1/catalog.json --study all --check
```

Use `--study commons-v3-foundation-v1` or `--study commons-v3-foundation-v2` to
restore one bank. Archive restoration is needed for full semantic verification
and figure reproduction. Default tests use synthetic fixtures and need no
download; existing figure exports can be viewed directly. The
[archive guide](../../docs/evidence-archives-v1.md) describes offline caching,
verification receipts and restoration behavior.
