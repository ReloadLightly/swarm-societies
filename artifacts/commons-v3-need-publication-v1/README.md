# Commons v3 need-targeted archive publication

This [public catalog](catalog.json) restores the completed 56-case,
224-episode need-targeted development bank from the new
[`commons-v3-need-2026-10-07` release](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-need-2026-10-07).
The release targets source commit
`536ed64cb733f2091afd9c9c7905531826519ff7`. The same four development seeds
were reused; publication does not change the study's exploratory status.

The archive contains 56 files totaling 3,647,037 bytes; the download is
3,657,256 bytes. Its SHA-256 remains
`f9358d7a108c253fe87900bf73babe1ad7b7c1c65833583996ea8ef9b5e7a7e2`.
The [public manifest](commons-v3-need-v1.json) differs from the original
local-only manifest only in `source_url`. The original local catalog,
manifest, inventory and receipts remain unchanged at their original paths.

```bash
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-need-publication-v1/catalog.json \
  --study commons-v3-need-v1
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-need-publication-v1/catalog.json \
  --study commons-v3-need-v1 --check
```

All three hosted assets matched their local bytes through unauthenticated
public downloads. Restoration into an empty directory using an empty cache
recovered all 56 files byte-identically; cached verification and restoration
into a second empty directory also passed offline. The
[publication receipts](../../evidence/commons-v3-need-publication-v1/README.md)
record these checks. No policy execution or experimental model calls occurred.

Release assets are hash-pinned, not administratively immutable. Preserve this
published identity; later corrections need a new version. Compact evidence,
source snapshots and figures remain in Git, and restored case files stay ignored.
