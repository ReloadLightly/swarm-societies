# Commons v3 physical-foundation validation

Engineering and exploratory-development records, 7 October 2026. The
[report](../../docs/commons-v3-foundation-v1.md) distinguishes working physics
from the still-open ecological and strong-baseline qualification gates.

The two banks each contain 56 configurations and 224 episodes, reusing four
seeds across parameter cells. There are zero independent evolutionary runs and
zero experimental model calls. V1 is a preserved failed navigation control;
v2 repairs a numerical fuel invariant and is still exploratory development.

| Check | Record |
| --- | --- |
| Independent v1 numerical and scientific audit | [V1 audit](v1-numerical-audit.json) |
| Independent v2 numerical and scientific audit | [V2 audit](v2-numerical-audit.json) |
| Strict v2 replay of all 224 episodes | [Replay](v2-replay.json) |
| Verifier metadata repair; all v1 numerical payloads unchanged | [Change](metadata-repair.json), [independent parity](metadata-parity.json) |
| Interrupted v2 run and unchanged 33 complete cases after recovery | [Interruption](v2-interruption.json), [resumption](v2-resumption.json) |
| Both galleries: source pins, visual inspection and identical rerenders | [Figure validation](figure-verification.json) |
| Local packaging and empty-target restoration of 112 case files | [Local archives](local-archives.json) |
| Earlier protected code, evidence, protocols and archive metadata unchanged | [Preservation audit](preservation-review.json) |
| 704 tests and 123 subtests pass without any bulk evidence | [Test receipt](tests.json), [full log](clean-full-tests.log), [checkout context](clean-test-context.json) |
| Five hosted assets match sizes and SHA-256 digests | [Publication receipt](publication.json), [release metadata](release-assets-public.json) |
| Public restoration of all 112 files from an empty cache; identical original bytes | [Restoration](public-restoration.json) |
| Offline cached archive verification | [Offline receipt](offline-verification.json) |
| Numerical report and documentation review | [Report](report-review.json), [overview links](documentation-review.json), [final local targets](documentation-targets.json) |

`preflight-metadata/` preserves the first v1 verifier source freeze, manifest,
design and summary. Its 56 compressed cases are byte-identical to the published
strict-verifier v1 bank; restore that bank and combine its `cases/` with this
metadata to reconstruct the earlier preflight. This is a metadata repair, not
another independent experiment. The separate v2 policy repair changes behavior.

[The archived packaging script](archive-builder.py.txt) is an exact source record
from `runs/commons-v3-foundation-v2/archive-build/build.py`; its relative-root
logic assumes that original location. It is not an additional supported CLI.

The earlier [650-test run](pre-v2-full-tests.log) passed before adding the v2
regressions. The first final-suite attempt was externally terminated with exit
143 and reported no assertion failures; its [partial log](interrupted-full-tests.log)
is retained, not counted as a completed test run. The successful final suite
passed **704 tests and 123 subtests in 462.38 seconds** in an actual clean local
clone of `e7c7cbb9b861ae5202324d2cee76fae8ad702381`. All 112 new and 844 legacy
bulk files were absent, imports resolved to that checkout, and the tracked tree
remained clean. No implementation or test bytes changed afterward.

The [public release](https://github.com/ReloadLightly/swarm-societies/releases/tag/commons-v3-foundation-2026-10-07)
targets that implementation commit. Its two archives contain 112 files and
9,287,035 original bytes; all five hosted assets match their local hashes.
After testing, the same checkout downloaded both archives without GitHub
credentials into a previously empty cache and restored every case. All restored
bytes match the original workspace; offline checks pass. Hosting remains
administratively mutable. No history rewrite, previous release replacement or
new raw-case Git tracking was used.

[Validation metadata](validation.json) pins the final new implementation,
test and documentation sources; [the record manifest](manifest.json) hashes
these validation records. Earlier interim receipts describe their own scope
and are superseded only where a later check is explicitly recorded.

Passing software tests, deterministic replay, accounting and hash checks do not
establish a social dilemma, effective navigation, institutional benefits or
general statistical calibration.
