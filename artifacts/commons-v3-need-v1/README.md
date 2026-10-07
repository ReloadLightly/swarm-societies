# Commons v3 need-targeted case archive

This separate [catalog](catalog.json) describes the 56 raw `cases/*.json.gz`
files from the completed need-targeted development bank. The bank contains
224 episodes on reused development cases, with no evolutionary runs or
experimental model calls. Designs, summaries, the completion manifest, source
snapshots and figures remain in the repository. The earlier foundation archive
identities are unchanged.

The archive is **local only, pending publication**. Its manifest explicitly has
`source_url: null`, and the catalog has no release URL. Online retrieval is
unavailable until publication; a fresh checkout does not contain the local
archive or its cache.

| Files | Original bytes | Archive bytes | Per-file SHA-256 manifest |
| ---: | ---: | ---: | --- |
| 56 | 3,647,037 | 3,657,256 | [Need-targeted inventory](commons-v3-need-v1.json) |

The archive is slightly larger than its payload because the case files are
already compressed. The [input inventory](inventory.json) and catalog pin every
file, the bank's design, completion manifest and source manifest. The catalog
also records the packager source hash and Python/zlib versions. Exact archive
byte reproduction depends on that toolchain; payload checksums are exact.

The verified local archive is
`runs/commons-v3-need-v1-validation/commons-v3-need-v1.tar.gz`. An identical copy
is available at
`.cache/evidence-v1/f9358d7a108c253fe87900bf73babe1ad7b7c1c65833583996ea8ef9b5e7a7e2.tar.gz`.
The archive was verified and restored into an empty local directory; all 56
restored files were independently compared byte for byte with the bank.
This is an offline restoration check, not a public-download test.

Restore from the existing local cache, or check the restored files:

```bash
.venv/bin/python scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-need-v1/catalog.json \
  --study commons-v3-need-v1 --offline
.venv/bin/python scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-need-v1/catalog.json \
  --study commons-v3-need-v1 --check
```

To verify the cached archive even when the raw files are already present, add
`--verify-only` to the offline command. To restore in another checkout before
publication, copy the archive into that checkout's `.cache/evidence-v1/` under
the SHA-256 filename shown above, then run the same offline command.

A checkout without the archive can regenerate the complete new bank in a
fresh output directory using the recorded source and protocol:

```bash
.venv/bin/python scripts/run_commons_v3_need_v1.py prepare \
  --output runs/commons-v3-need-reproduction
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_need_v1.py run \
  --output runs/commons-v3-need-reproduction
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_need_v1.py verify \
  --output runs/commons-v3-need-reproduction
```

This creates a separate reproduction and preserves the completed evidence bank.
No evidence download or model calls are required for this regeneration or the
default tests. Numerical reproduction retains the recorded environment scope.
Corrections or subsequent evidence versions require new archive identities.
