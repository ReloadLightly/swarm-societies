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
is retained, not counted as a completed test run. Final clean-checkout testing
and public archive restoration will be recorded separately.

Passing software tests, deterministic replay, accounting and hash checks do not
establish a social dilemma, effective navigation, institutional benefits or
general statistical calibration.
