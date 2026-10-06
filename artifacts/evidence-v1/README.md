# Frozen evidence archive catalog

Source checkpoint: `069536285a7d0d30f0828fa999b2337d408e9562`. Archives contain existing bulk
evidence; designs, source snapshots, compact tables and test fixtures stay in Git.
All checksums are exact; use the [restore guide](../../docs/evidence-archives-v1.md).

| Study | Files | Original bytes | Download bytes | Manifest |
| --- | ---: | ---: | ---: | --- |
| world-model-calibration-v1 | 382 | 79,697,408 | 66,955,248 | [SHA-256 inventory](world-model-calibration-v1.json) |
| world-model-decision-development-v1 | 6 | 6,170,052 | 6,135,650 | [SHA-256 inventory](world-model-decision-development-v1.json) |
| world-model-decision-v1 | 30 | 30,826,958 | 30,644,134 | [SHA-256 inventory](world-model-decision-v1.json) |
| world-model-experiment-development-v1 | 6 | 62,381,503 | 62,285,489 | [SHA-256 inventory](world-model-experiment-development-v1.json) |
| world-model-experiment-smoke-v1 | 1 | 10,284,724 | 10,271,735 | [SHA-256 inventory](world-model-experiment-smoke-v1.json) |
| world-model-experiment-v1 | 30 | 315,758,208 | 315,222,084 | [SHA-256 inventory](world-model-experiment-v1.json) |
| world-model-sharing-v1 | 266 | 220,712,704 | 189,182,944 | [SHA-256 inventory](world-model-sharing-v1.json) |
| world-model-v1 | 123 | 24,763,696 | 9,563,709 | [SHA-256 inventory](world-model-v1.json) |

Total: **844 files, 750,595,253 original bytes; 690,260,993 archive bytes**.
Manifests and catalog pin archive identities; hosted release assets remain
administratively mutable unless GitHub release immutability is enabled.
Never replace a published archive: publish a new version and a new manifest.

```bash
python3 scripts/restore_evidence_v1.py --study all
python3 scripts/restore_evidence_v1.py --study all --check
python3 scripts/restore_evidence_v1.py --study all --offline --verify-only
```
