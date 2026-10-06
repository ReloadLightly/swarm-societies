# Scientific review and baseline audit

Reviewed 7 October 2026 against commit `ca929bc`. The external review correctly
identifies the main sequencing failure: substantial implementation and numerical
validation preceded a strong baseline and incentive audit. The existing studies
support a working research instrument and limited conditional findings. They do
not establish that evolutionary search discovers competitive governance, or that
the current environment is an adequate model of a spatial commons.

The [implementation plan](commons-v3-plan.md) makes environment qualification
and strong baselines prerequisites for further experimental model spending.
The user's target is mobile individuals in an anarchic international system:
institutions may form, be absent, change and disappear. No higher institution
governs relations between societies. Current frozen simulators and evidence
remain unchanged.

## The baseline criticism reproduces

The review did not include its policy source. A reconstructed policy always
harvests the fullest visible patch at full effort, contributes nothing, sets
zero tax, investment, defense and reserve, and never raids. It reproduces every
rounded entry in the supplied table using the frozen mechanism-study cases,
opponents and focal society rotations.

| Focal programs | Welfare ↑ | Unmet need ↓ | Raid harm per tick ↓ | Private utility per tick ↑ | Other societies' mean welfare ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial | 0.844263 | 0.003825 | 0.602067 | 0.933662 | 0.847117 |
| Coevolved | 0.846926 | 0.002050 | 0.534878 | 0.965109 | 0.846872 |
| Reconstructed greedy | **0.848654** | **0.000897** | **0** | **1.038674** | 0.845842 |

This is an exploratory reanalysis of **12 existing environment tuples**, crossed
with three opponent panels and three focal identities: **108 focal cases and
216 drought/no-drought rollouts** for the reconstructed policy. Initial and
coevolved comparators come from the saved evidence. There are no new independent
evolutionary runs or experimental model-generation calls. These are finite-panel
means, not estimates of the reliability of the search procedure.

The greedy policy raises focal private utility by **7.62%** relative to the
coevolved population and reaches the welfare ceiling in **101/108 drought
cases**. Against coevolution, focal welfare improves in 23 cases, ties in 84 and
worsens in one; private utility improves in 106 and worsens in two. Aggregate
dominance therefore does not mean dominance in every case. Welfare and unmet
need are algebraically linked rather than independent outcomes.

![Recorded baseline comparison](../figures/baseline-review-v1/baseline-outcomes.png)

*Exploratory baseline audit on the existing mechanism panel. Conditions are
labelled explicitly with neutral markers.
The figure reports descriptive averages without population confidence claims.
Raid harm measures victim losses from raids, not every external cost.*

The additional outsider column changes the interpretation. Greedy harvesting
lowers other societies' mean welfare by **0.001030** relative to the coevolved
focal transplant. Mean welfare across all three societies is consequently
**0.000110 lower**, despite higher focal welfare. This small descriptive
contrast is not a resolved population effect, but it demonstrates why zero
recorded raid harm cannot be equated with no externality. The intervention
changes an entire member/institution bundle; it does not isolate the causal
effect of removing raids or of any particular extraction rule.

[Recorded diagnostic and reproduction](../evidence/baseline-review-v1/README.md)
and [figure provenance](../figures/baseline-review-v1/README.md) preserve the
reconstruction, source hashes and saved results separately from the old study.

## What each criticism establishes

| Issue | Assessment | Required response |
| --- | --- | --- |
| Simple harvesting beats the evolved programs | Confirmed on the four supplied aggregate endpoints; outsider welfare qualifies broader dominance | Add strong baselines before search; evaluate member, resident, outsider and whole-world outcomes |
| Regeneration does not depend on stock | Confirmed for unsaturated inflow; capacity clipping still depends on stock, and current extraction can deprive others | New ecological version with stock-dependent renewal and direct incentive tests |
| There is no commons dilemma and greedy is always optimal | Too strong as a theorem: current scarcity, investment and appropriation already create interdependence; the intended depletion dilemma was not demonstrated | Measure profitable unilateral deviation and collective losses, rather than infer a dilemma from an equation |
| Lower regeneration makes investment valuable | The reported 3.5–4.5 sweep was not independently rerun in this review | Treat it as a development lead; publish a frozen scarcity map rather than import its numbers as established results |
| Raiding is entirely inherited and never pays | Initial raids are inherited, but evolved society 1 also enables new raid behavior; bundle replacement cannot identify raid profitability | Paired raid-permission and member-action interventions, with all other behavior preserved |
| Evolution barely happened | Correct as a limitation on scientific inference | Replicated campaigns with many reciprocal adaptation cycles and explicit compute accounting |
| Every proposal was accepted, so selection did not exist | Incorrect literally: a paired incumbent comparison and archive selection exist | Replace the negligible improvement margin; test admission, rejection and adaptation coverage; do not target a rejection percentage |
| World-model wins were predetermined | Many comparisons deliberately validate an expected mechanism; finite-sample prediction and decision gains are not mathematical guarantees | Describe them as identification and integration controls; require a consequential decision and nontrivial information tradeoff for a new scientific claim |
| The project already demonstrates a swarm | Unsupported by the current three societies of four agents without physical movement | Implement and test locality, mobility, distributed information and optional institutions before claiming these capabilities |
| README lacks a central claim | Fair | Lead with one research question and the strongest supported result; archive detailed study records without erasing adverse evidence |
| Bulk evidence should leave Git | Fair, and the review understates current size | Versioned external archives, small manifests, verified restoration; consider history rewriting separately |
| Accept only robust improvements on held-out cases | Directionally correct, with a terminology trap | Admission uses validation data; any repeatedly queried admission panel is not the untouched final test |
| Faster proposal models are needed | A reasonable efficiency hypothesis, not an established model choice | Benchmark throughput and valid improvements under a separately approved route/budget; preserve current route meanwhile |
| Candidate memory is unbounded | True of the language checker and some direct entry points; false of the existing search evaluator subprocesses | Centralize bounded execution across all untrusted paths and test failure containment |

The original transplant finding remains a valid conditional intervention:
swapping institutions on evolved members changes raid losses. It does not show
that search reliably discovers predation or that predation is adaptive.
Similarly, the new greedy result does not erase the transplant contrast; it
changes how much scientific weight it should carry.

## Search and engineering audit

The consumption pilot has **13 started model calls, 11 completed proposals and
two budget-interrupted calls**, with one independent run per arm. Fixed
institutions received six completed member proposals; coevolution received
three member and two institution proposals. Both arms had 1,800 seconds and
the same six search cases. All eleven proposals passed
`new > old + 1e-9`. No member was revisited after an institutional change.
[Admission code](../swarm_societies/consumption_evaluation.py) and the
[recorded consumption study](consumption-v2-run.md) provide the existing protocol.

These facts support describing the experiment as a pipeline pilot. They do
not establish a stable evolutionary equilibrium, reliable coadaptation or
general superiority of either arm. Equal elapsed allowances also yielded
unequal completed proposal counts. The next study must distinguish performance
per compute budget from the effects of adaptation order. Search and fresh
evaluation seeds are separated in the inspected code; no final-test leakage
was found in those paths. Repeated selection on six cases remains an
overfitting risk.

The calibration verifier does compare recomputed diagnostic floats exactly.
The reported last-bit ESS discrepancies are consistent with numerical
portability failure. The review's precise 72/576 mismatch count was not
reproduced here; one retained case recomputes exactly under the original
environment. The mentioned patch was not present. Add a separately versioned
portable verifier with narrow floating tolerances, exact file hashes and exact
case/gate logic. Do not weaken all comparisons or overwrite frozen sources.
[Verifier](../scripts/run_world_model_calibration.py).

Both existing search evaluator CLIs already set **1 GiB address-space and
120 CPU-second limits**. The policy checker alone cannot prevent a large
allocation or a costly builtin, and other library/fresh-evaluation paths lack
the same centralized protection. The remedy is consistent subprocess isolation,
parent-enforced wall limits, bounded output and explicit failure records.
[First evaluator](../scripts/evaluate_candidate.py),
[consumption evaluator](../scripts/evaluate_consumption_candidate.py),
[candidate runtime](../swarm_societies/candidate.py).

The supplied review predates the costed-experiment stage. The latest recorded
suite is **352 tests and 102 subtests**, not 282 tests. The later 24-arena study
found no clear active-selection advantage in posterior-update value, and its
small total gain was already present with frozen coefficients. This reinforces
the need for useful baselines and meaningful decision stakes; it is not a new
positive learning claim. [Experiment report](world-model-experiment-v1.md).

The earlier allocation control also has very little decision headroom: the
prior controller's mean realized regret within its three-action menu is
0.026949 on utility 31.282372. Learning recovers about 78% of that menu gap,
but the absolute utility gain is only 0.021110 and primarily terminal wealth.
This is evidence that the integration can affect decisions, not yet a
substantial governance result. [Decision report](world-model-decision-v1.md).

At review time the repository contains approximately **748 MiB of tracked
file contents**, **735 MiB of working evidence** and **604 MiB in `.git`**.
These are different measures, not three additive dataset sizes. Archive
externalization should preserve the exact published bytes and their provenance.
A history rewrite changes commit identities and requires its own migration
decision after successful independent restoration.

## Literature and the scope of a possible paper

The supplied references resolve to primary paper pages. One title correction:
Kumar and colleagues' paper is **Evolving Interpretable Constitutions for
Multi-Agent Coordination**, not “Simulation.” Existence of a preprint does not
validate its methods or establish this project's novelty. The relevant overlap
is already substantial.

| Primary source | Consequence for this project |
| --- | --- |
| [Group selection promotes prosocial prompts](https://arxiv.org/abs/2606.23343) | Group versus individual transmission and cooperation already have a direct LLM study. A new contribution needs physical externalities, institutional mechanisms or a distinct causal comparison. |
| [Evolving Interpretable Constitutions](https://arxiv.org/abs/2602.00755) | Evolving rules in a survival grid world is not sufficient novelty by itself. |
| [From Certain Doom to Survival](https://arxiv.org/abs/2609.22600) | Agents already author, validate and vote on executable governance in a commons setting. We need testable differences in formation, enforcement, mobility and external costs. |
| [Beyond Scalar Rewards](https://arxiv.org/abs/2603.19453) | Code-policy refinement with social feedback already exists. Its full-state policy interface differs from our proposed local-information contract; feedback content and access must be controlled. |
| [Tapes Together Strong](https://arxiv.org/abs/2609.10817) | Computation and material costs can be part of the dilemma. Its self-replicating machine-code substrate differs from externally proposed policy edits. |
| [SwarmWorld](https://arxiv.org/abs/2608.26081) | Spatial local action, executable artifacts and strong isolated-search comparisons are relevant standards; it does not imply universal superiority of collective search. |
| [When Do Institutions Beat Intelligence](https://arxiv.org/abs/2608.11357) | Information-routing and institutional advantages need matched alternatives and interventions that remove the proposed mechanism. |
| [When Agents Evolve, Institutions Follow](https://arxiv.org/abs/2604.27691) | It compares governance architectures on benchmarks; it should not be cited as direct evidence of endogenous ecological institution formation. |
| [Certifying cooperation](https://arxiv.org/abs/2609.06586) | Cooperation requirements should be demonstrated. Its bounded-horizon task certificates do not automatically certify an open commons environment. |
| [ALDER](https://arxiv.org/abs/2609.33728) | Parameter fitting, structural proposals, held-out verification and intervention selection should remain distinct. |
| [Identifiability of Controlled World Models](https://arxiv.org/abs/2607.22430) | Action excitation matters; its Gaussian latent-state assumptions do not supply a theorem for this ecological learner. |
| [Sequential Social Dilemmas](https://arxiv.org/abs/1702.03037) | Cooperation is a property of policies and their payoffs over time. Test the incentive structure directly. |
| [Melting Pot](https://proceedings.mlr.press/v139/leibo21a.html) | Generalization to new social partners needs its own evaluation, beyond new weather seeds. |

A defensible question is when institutions that arise among mobile, self-interested
individuals improve resident welfare, and whether that success exports costs to
outsiders under the absence of higher government. Relative member/institution
adaptation rates provide one intervention on this question. Selecting code with
two objectives is not automatically biological or cultural multilevel selection:
that stronger framing requires explicit transmission, replacement and group
lineage dynamics.

No current result warrants a promised arXiv claim or a fixed publication date.
The first success criterion is an environment with verified incentives, viable
alternatives and honest evaluation. A result in which a simple institution or
numerical optimizer remains best is scientifically legitimate.
