# Optional-charter development raw archive

This separate archive contains all 144 compressed raw episodes from the
[completed development comparison](../../docs/commons-v3-institutions-development-v1.md).
The full source/design closure was frozen at
`a4c84e67cc7d6d05ef4d05c13e75c7fafe90e6c2` before execution. All episodes and
policy-memory midpoint continuations replay exactly.

The raw files total 17,133,617 bytes; the archive is 15,473,215 bytes, SHA-256
`1553e76b7f79e0b7640e98611f3a5a599ae3e956ff5103fbc83dc71f5b9f8d21`.
The catalog pins the archive manifest, which pins each original path, size and
hash. Local verification passes. Public publication and empty-root public/offline
restoration are pending this verified-results commit.

The intended new release identity is
`commons-v3-institutions-development-2026-10-07`. Once published, restore from
the repository root:

```bash
python3 scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-institutions-development-v1/catalog.json \
  --study commons-v3-institutions-development-v1
```

Compact evidence, frozen source copies, receipts, report and recorded-data
figures stay in Git. Preserve all earlier releases and this bank's identity.
Hashes detect changed assets; GitHub hosting is not administratively immutable.
