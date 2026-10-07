# Commons v3 ecology qualification archive

This [catalog](catalog.json) restores the completed ecology qualification bank:
**144 raw case files / 288 episodes**. It retains
every case, including failed or unresolved scientific gates. Compact designs,
source freezes, summaries and completion manifests remain in Git.
There are zero evolutionary runs or experimental model calls.

| Files | Original bytes | Archive bytes | Per-file SHA-256 manifest |
| ---: | ---: | ---: | --- |
| 144 | 58,201,356 | 57,406,528 | [manifest](commons-v3-ecology-qualification-v1.json) |

The archive, manifest and unique phase catalog are published in
[`commons-v3-qualification-2026-10-07`](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-qualification-2026-10-07). This bank is bound to source checkpoint
`ead7cfcec95decbdd8be213093f30b8ccec15d60`; the release target remains
`ead7cfcec95decbdd8be213093f30b8ccec15d60`. The [inventory](inventory.json) pins every raw file.
The [publication receipts](../../evidence/commons-v3-qualification-validation-v1/publication/ecology/README.md)
record unauthenticated public downloads, empty-cache restoration and offline
restoration into a second empty directory, all byte-identical to the originals.

```bash
python3 scripts/restore_evidence_v1.py --catalog artifacts/commons-v3-ecology-qualification-v1/catalog.json --study commons-v3-ecology-qualification-v1
python3 scripts/restore_evidence_v1.py --catalog artifacts/commons-v3-ecology-qualification-v1/catalog.json --study commons-v3-ecology-qualification-v1 --check
```

Use `--offline` when the SHA-named archive is cached, or `--offline --verify-only`
to verify the cached archive. Ecology and incentive catalogs have separate
identities; adding later assets never replaces earlier files. Hosting is
hash-pinned, not administratively immutable. Reproducing archive bytes is scoped
to the recorded Python/zlib runtime; restored payload hashes are exact.
