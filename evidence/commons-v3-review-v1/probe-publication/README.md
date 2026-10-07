# Public restoration of the supplied temptation probe

The new release
[commons-v3-temptation-review-2026-10-07](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-temptation-review-2026-10-07)
was created without replacing or extending an earlier release. Its target is
the pushed source commit `56760889c8bef94e4cb4d3356514d4d4fca33cc3`.
This publication did not run simulations or change the sealed probe evidence.

All **64 files / 6,664,398 bytes** restore byte-identically from unauthenticated
public downloads with an initially empty cache and destination. Offline archive
verification passes, and offline restoration into a second empty destination
reproduces every original file. The 6,622,949-byte archive has SHA-256
`c0c0bcdccfd18bf06c255b1ff2b847f6b3f2719c30262bda3c6d423a033d5b13`.

The minimal saved publication script uses the existing archive packager and
restoration helper. `local-archive-verification.json` records packaging;
`source-commit-binding.json` binds the original script and compact records to
the source commit; `upload.json` records the unique release creation.
`public-assets.json` checks all three hosted assets, and the restoration,
offline verification and per-file comparison receipts support
`publication.json`. The new catalog and manifest are in
[artifacts/commons-v3-temptation-review-v1](../../../artifacts/commons-v3-temptation-review-v1/README.md).

The release reports `immutable: false`. Committed hashes detect changed assets;
they do not prevent an administrator from replacing or deleting GitHub assets.
