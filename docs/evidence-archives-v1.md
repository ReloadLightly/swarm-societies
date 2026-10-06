# Evidence archives v1

Bulk evidence is distributed as eight versioned archives. Git retains study
designs, completion manifests, compact tables, summaries, source snapshots,
figures and the published case fixtures needed by the default tests. Restoring
an archive puts the original bytes at their original paths; no scientific
runner or verifier needs a different observation format or filesystem layout.

The source checkpoint is `069536285a7d0d30f0828fa999b2337d408e9562`.
The [catalog](../artifacts/evidence-v1/catalog.json) pins each archive manifest;
each manifest lists every payload file's path, byte size and SHA-256 as well
as the complete archive's size and SHA-256. The destination is the existing
public repository's [evidence release](https://github.com/ReloadLightly/swarm-societies/releases/tag/evidence-v1-2026-10-07).
These assets contain evidence already published in the repository.

## Restore and check

The restoration tooling uses the Python standard library on Linux/macOS
(Python 3.11 or newer); Windows users can use WSL. From the repository root,
restore one study or every archived study:

```bash
python3 scripts/restore_evidence_v1.py --study world-model-calibration-v1
python3 scripts/restore_evidence_v1.py --study all \
  --receipt runs/evidence-restore-v1/receipt.json
```

Use `--study` followed by one or more catalog study IDs. Downloads are cached
under `.cache/evidence-v1/` by archive hash. Already complete, matching evidence
is checked locally and does not require another download. Partial downloads can
resume when the server's range response is consistent; final size and digest
must match before an archive enters the verified cache.

```bash
# Check restored files without contacting the network or changing evidence.
python3 scripts/restore_evidence_v1.py --study all --check

# Restore missing evidence from already cached archives, with no network.
python3 scripts/restore_evidence_v1.py --study all --offline

# Check cached archive bytes and every payload, without restoring files.
python3 scripts/restore_evidence_v1.py --study all --offline --verify-only
```

`--root` chooses a checkout to restore and `--cache` chooses another cache.
An optional receipt path must be new. A normal restoration never replaces a
different existing file: inspect a conflict before deciding which copy to keep.
Every archive is fully checked and staged before files are published. Archives
containing undeclared entries, duplicate paths, traversal, links or mismatched
sizes/hashes fail. New files are published individually without replacing
existing paths. An interruption can leave a verified subset; rerunning resumes
by accepting identical existing files. No all-files filesystem transaction is
claimed.

After restoration, the frozen verification and rendering commands in the
[study index](study-index.md) work at their original paths. In particular,
calibration uses the [supplemental portable verifier](foundation-repairs-v1.md)
and the pinned numerical libraries. Archive integrity checks establish byte
identity, not statistical calibration or scientific validity.

## What moves and what stays

The migration covers **844 files and 750,595,253 uncompressed bytes** from eight
world-model studies: stationary identification, calibration, sharing, allocation
development/evaluation, and experiment smoke/development/evaluation. It includes
case records, retained arrays, learner snapshots, raw event/prediction tables
and the two large sharing checkpoint tables. Copied development proofs retain
their original nested paths and bytes.

The preceding checkpoint tracked 1,133 evidence files totaling 768,984,812 bytes.
The **289 retained files total 18,389,559 bytes**, before adding this migration's
small verification records. This removes 97.6% of the existing evidence payload
from the current Git tree. These are file-content byte counts, not Git object
sizes, compressed download sizes or experimental sample counts.

All original source snapshots and manifests stay tracked. The calibration
case-067 JSON/NPZ pair remains a 634,386-byte fixture because it exercises the
reference retry distinction. The complete mechanism study and the earlier
evolution and reconstructed-baseline records also remain in Git. Thus the
default regression suite needs no evidence download. Reconstructing full
world-model tables, figures or semantic verification requires the relevant
archives first; already rendered SVG/PDF/PNG figures stay in Git.

Restored bulk files are ignored at their original paths so they do not return
to ordinary source commits. This does not remove them from the local working
directory of an existing checkout.

## History and archive identity

The Git history is preserved. Removing tracked payloads in the migration commit
reduces the current checkout and future shallow clones; an ordinary full clone
still retrieves historical objects. For a small current checkout:

```bash
git clone --depth 1 https://github.com/ReloadLightly/swarm-societies.git
cd swarm-societies
python3 scripts/restore_evidence_v1.py --study world-model-calibration-v1
```

There is no history rewrite, force-push, Git LFS conversion or new hosting
account. Future evidence revisions must receive new archives and manifests;
do not replace an asset under an existing published identity. The committed
hashes detect a changed or corrupted remote asset. GitHub release immutability
is a separate repository setting; a hash-pinned URL alone does not prevent an
administrator from deleting or replacing a hosted asset. GitHub documents that
distinction in [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).

## Rebuild and validate an archive

The low-level `scripts/evidence_archive_v1.py` supports `package`, `verify`,
`fetch` and `restore`. Packaging takes an `evidence-inventory-v1` JSON object
whose `files` entries contain repository-relative `path`, `sha256` and `size`.
It checks the source bytes and emits deterministic gzip/tar metadata. Rebuilding
the same inventory from the same bytes under the same Python/zlib toolchain
must produce the same archive digest. Downloaded archives are checked against
their published digest regardless of the downloader's compression library.

```bash
python3 scripts/evidence_archive_v1.py package \
  --root . --inventory runs/study-inventory.json \
  --output runs/study.tar.gz --manifest runs/study-manifest.json
python3 scripts/evidence_archive_v1.py verify \
  --manifest runs/study-manifest.json --archive runs/study.tar.gz
```

Package outputs are new files; frozen evidence is read-only input. The release
contains the per-study manifests as assets in addition to the archives, while
the catalog pins the checked-in copies. The migration's verification record
reports archive hashes, clean-checkout restoration, offline verification and
the regression suite. Publication and restoration must pass before tracked
bulk files are removed.
