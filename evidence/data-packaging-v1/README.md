# Evidence publication and README consolidation validation

Engineering migration, 7 October 2026. No scientific observations, frozen
simulators, protocols, study source snapshots or original evidence bytes changed.
No experimental model calls or evolutionary runs were made.

The [public release](https://github.com/ReloadLightly/swarm-societies/releases/tag/evidence-v1-2026-10-07)
contains eight archives and nine metadata assets. The
[catalog](../../artifacts/evidence-v1/catalog.json) pins each manifest and every
payload file. See the [restoration guide](../../docs/evidence-archives-v1.md).

| Validation | Result | Record |
| --- | --- | --- |
| Original tracked evidence | 1,133 files; 768,984,812 bytes | [Inventory audit](inventory-audit.json) |
| Externalized payload | 844 files; 750,595,253 bytes in eight archives | Catalog and archive manifests |
| Retained original evidence | 289 files; 18,389,559 bytes | [Retained inventory](keep_in_git-inventory.json) |
| Local archive round trip | All 844 files restored and rehashed | [Local receipt](local-roundtrip.json) |
| Hosted asset sizes and digests | All 17 match local inputs | [Release metadata](release-assets-public.json) |
| Public restoration | All 844 files downloaded and restored; zero preexisting payload files | [Public receipt](public-restoration.json) |
| Full original-byte comparison | All 1,133 evidence files and 82 prior implementation/test/seed files identical in both checkouts | [Identity receipt](restored-identity.json) |
| Offline cached archive verification | All eight archives and 844 payload files pass | [Offline receipt](offline-verification.json) |
| Default regression suite without bulk evidence | 542 tests and 123 subtests pass in 509.47 s | [Test log](clean-full-tests.log) |
| Independent local preservation/code review | No material findings; all 301 frozen declarations match | [Review](independent-review.json) |
| README preservation and links | 7,635 to 1,446 words; complete old narrative retained | [Consolidation check](readme-consolidation.json) |

The test checkout was an actual local shared clone of implementation commit
`72c96736a4de1d6e64747656a57715f0f37726ea`. Sparse checkout excluded exactly the
844 payload paths while retaining the original fixtures; imports resolved to
that checkout. The full suite completed before any payload restoration. The
documented command then downloaded all archives through public URLs into an
empty cache and restored their original paths. It used no GitHub credentials.
Offline verification ran with the network-restricted execution environment.
Only after public restoration, identity checking and offline verification passed
were the original payloads untracked in the main workspace.

The independent review preceded publication and explicitly records public
restoration as pending at that time; the later public and identity receipts
close that gate. [Validation metadata](validation.json) pins the final tooling
and documentation, and [the record manifest](manifest.json) hashes these records.
The original studies' own manifests and source snapshots remain unchanged.

The current Git tree loses 97.6% of its previous evidence payload, while all
original local files remain present and ignored. Historical Git objects remain;
full clones are still large, and shallow clones obtain the smaller current tree.
Archive hashes detect modification but do not prevent an administrator from
removing or replacing hosted assets. The release's immutability setting is off;
this migration did not alter repository settings. Archive integrity and passing
software tests do not establish statistical calibration or scientific validity.
