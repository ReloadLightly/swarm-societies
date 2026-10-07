# Commons v3 navigation tuning archive

This separate [catalog](catalog.json) contains only the raw tuning case files:
324 candidate/environment records, each containing one episode across the 18 fixed candidates and 18 tuning environments. Designs, source freezes, numerical selection, summaries and
completion manifests remain in Git. These are exploratory numerical-baseline
records, not independent evolutionary runs or ecological/incentive qualification.

| Files | Original bytes | Archive bytes | Per-file SHA-256 manifest |
| ---: | ---: | ---: | --- |
| 324 | 5,334,049 | 5,113,226 | [tuning manifest](commons-v3-navigation-tuning-v1.json) |

The archive, manifest and uniquely named phase catalog are published in
[`commons-v3-navigation-2026-10-07`](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-navigation-2026-10-07).
This phase's source checkpoint is `cc9c2fe95a397de567d093daf1e47e1e240fc3a2`; the release
was created at `cc9c2fe95a397de567d093daf1e47e1e240fc3a2`. The catalog pins the
phase completion manifest, design, source manifest and pre-evaluation selection.
The [input inventory](inventory.json) records every original file.

All three hosted assets match their local sizes and hashes. Unauthenticated
public download into an empty cache restored all 324 files into an
empty directory, byte-identical to the original bank. Offline verification and
restoration into a second empty directory also pass. The
[publication receipts](../../evidence/commons-v3-navigation-tuning-v1-publication/README.md)
record these checks. Publication performed no simulations or model calls.

```bash
.venv/bin/python scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-navigation-tuning-v1/catalog.json \
  --study commons-v3-navigation-tuning-v1
.venv/bin/python scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-navigation-tuning-v1/catalog.json \
  --study commons-v3-navigation-tuning-v1 --check
```

Use `--offline` when the SHA-named archive is already cached. To verify the
cached archive itself, combine `--offline --verify-only`. This catalog restores
only tuning raw records. Complete study verification requires both the
separate tuning and evaluation archives once evaluation is complete.

Tuning and evaluation have separate immutable identities by convention. Later
assets do not replace this archive, manifest or catalog. The hosting provider
reports `immutable: false`; hashes detect
changed assets but do not guarantee administrative immutability. Archive byte
reproduction is scoped to the catalog's Python/zlib versions, while restored
payload checksums are exact. Earlier evidence identities remain unchanged.
