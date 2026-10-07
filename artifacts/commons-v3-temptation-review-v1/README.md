# External temptation probe raw archive

The separate release
[commons-v3-temptation-review-2026-10-07](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-temptation-review-2026-10-07)
targets source commit `56760889c8bef94e4cb4d3356514d4d4fca33cc3`.
Its 64 raw episode files total 6,664,398 bytes; the archive is 6,622,949 bytes.
This is exploratory reproduction evidence, not a new qualification panel.

The catalog pins the archive manifest; the manifest pins every original path,
size and SHA-256. All three hosted assets were downloaded without authentication
and matched the local bytes. Public restoration began with empty destination
and cache directories. All 64 files matched byte for byte; offline archive
verification and restoration into a second empty destination also passed.
[Publication receipts](../../evidence/commons-v3-review-v1/probe-publication/README.md)
record the comparisons.

Restore from the repository root:

```bash
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-temptation-review-v1/catalog.json \
  --study commons-v3-temptation-review-v1
```

The compact evidence, supplied original script, capture source, exact stdout,
summary, replay receipts and figure stay in Git. Earlier archive identities and
the sealed probe record are unchanged. Hashes detect asset changes; GitHub
hosting is not administratively immutable.
