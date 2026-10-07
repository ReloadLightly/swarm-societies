# Research state and next steps

**Implementation update:** the initial political lifecycle and explicit custody
extension, audited controllers and full policy-memory continuation are now
implemented and tested under the
[Stage 2 capability contract](commons-v3-institutions-contract-v1.md). The
existing [incentive replay obligation](../evidence/commons-v3-qualification-validation-v1/incentive-replay-v1.json)
is closed: all 3,360 episodes and saved aggregates reproduce exactly. The
assessment below records the pre-implementation checkpoint; its scientific
limitations and evaluation priorities remain in force. Follow `PROGRESS.md`
for current validation status and the next declared development comparison.

Assessment of the repository after the 7 October 2026 review response, against
checkpoint `773a299`. The project now has a credible physical testbed, strong
simple controllers and substantially better evidence discipline. Its central
question about useful, optional and changing institutions remains open: the
current v3 world has no political institutions to evaluate.

The next development priority is a small, materially explicit institutional
system and a fair comparison against decentralized coordination. The proposed
storage/prevalence study can refine that comparison, but its full execution or
a strict game classification should not block political interface development.
The earlier qualification verdicts remain unchanged. This plan starts no
experiments, changes no frozen protocol and authorizes no model spending.

## Position in the research program

| Area | What is established | Boundary of the evidence |
| --- | --- | --- |
| Historical evolution | Executable member/institution programs, replacement, evaluation and component transplants work. | Few proposals and one lineage per arm do not establish a reliable coevolution advantage. Members were not revisited after institutional changes in the consumption pilot. |
| Strong baseline criticism | A reconstructed simple harvester improves the supplied focal aggregate outcomes over saved coevolution. Outsiders lose slightly. | It is an exploratory bundle comparison, not universal dominance or absence of externalities. |
| World models | Supplied-law parameter learning, reference calibration, report provenance, decision branching and costed experiment controls are implemented. | Sharing benefits are small; allocation gains are largely inventory; active selection has no clear update-value advantage. Structural discovery and transfer to v3 are unimplemented. |
| Physical v3 | Mobility, local sensing, stock-dependent renewal, action costs, accounting, keyed environmental events and physical snapshots exist. | These capabilities do not establish strategic choice, institutions or collective intelligence. |
| Navigation | Strong floor-bearing local foragers sustain near-reference need over longer horizons. | The finite numerical winner is only slightly better than a fixed anchor and is not a private optimum. |
| Ecological qualification | Both controls pass the finite-horizon criteria in five of nine cells. Two cells have insufficient-supply certificates; two remain unresolved. | Neither indefinite sustainability nor universal solvability is established. |
| Incentive qualification | The complete bank measures focal substitutions, collective losses and storage/peer sensitivities. | The primary joint verdict is unresolved; broader qualification and reference robustness at every declared weight fail. |
| Preservation | The completed banks and probe have separately identified public archives with exact public/offline restoration. The 64-episode probe replays exactly. | Complete semantic replay of the 3,360 incentive episodes remains pending. Byte restoration is not semantic validation. |
| Institutions and adaptation in v3 | A political-world objective and prospective design requirements exist. | Membership, charters, treasury custody, monitoring, sanctions and formation are not implemented. Generated-policy containment has not been ported to v3. |

The [study index](study-index.md), [scientific review](research-review-2026-10-07.md),
[qualification report](commons-v3-qualification-v1.md) and
[latest review response](commons-v3-review-2026-10-07.md) contain the underlying
records. Stage 0's portability, historical execution and evidence repairs are
complete. Stage 1's physical foundation is implemented and its qualification
experiments have returned substantive mixed and negative results. Stage 2 has
not yet been implemented. An overall percentage-complete estimate would obscure
these very different kinds of progress.

## What the repairs changed scientifically

The stronger baselines changed the research question. Earlier need-targeted
policies left substantial consumption gains available to an aggressive focal
replacement, but performed poorly over longer horizons. Competent navigation
with a voluntary stock floor largely removes that opportunity when peers also
exercise restraint. It also makes collective losses under widespread supplied
aggression much more apparent. This shows why navigation competence, ecological
viability and incentives had to be examined separately.

The completed reference results are especially informative. For the fixed-floor
control, focal aggression adds **0.001687 consumption units per tick**, compared
with **0.016593 utility units** at weight 0.05; **89.83%** of that utility gain
is terminal inventory. The selected control instead loses **0.013786 consumption
units** and gains only **0.000712 utility units**. The supplied independent
eight-seed probe reproduces near-full restrained consumption, an approximately
89% inventory contribution, a much smaller capacity-8 gain and a consumption
advantage against 23 aggressive peers at capacity 80. The corresponding
capacity-8 high-prevalence contrast is unresolved.
[Complete incentive results](commons-v3-incentive-qualification-results-v1.md).

The defensible operational frame is **storage-sensitive coordination and
appropriation risk among supplied policies**. A strict stag hunt is a hypothesis.
Large collective losses do not imply a profitable unilateral deviation from
successful restraint. A small or unresolved deviation gain does not prove a
strict preference for restraint. Relative advantage against aggressive peers
can coexist with very poor absolute consumption. Report both absolute outcomes
and paired gains; neither a preferred label nor a stock-collapse picture can
replace the measured payoffs.

The current agents execute supplied policies. Substituting one policy for
another measures an empirical menu of payoffs; it does not establish that an
individual discovers or chooses a best response. This distinction becomes
critical for institutions: a permanently aggressive controller does not learn
to comply when threatened, and a scripted join action does not demonstrate
that membership is attractive.

Inventory has legitimate physical uses, including financing movement and
buffering consumption. The unsupported inference is that a prescribed reward
for inventory at the terminal tick demonstrates consequential welfare. Preserve
the weight and report its contribution separately. Adding mortality, new shocks
or reproduction could create endogenous storage value, but would be a new
physical model and is unnecessary for the next institutional implementation.

## What is reusable and what is missing

The physical engine is a useful foundation because it already separates legal
local observations from evaluator state and accounts for real action costs.
Its [implementation](../swarm_societies/commons_v3/engine.py) supports movement,
harvesting, transfers, messages and reserves. Peer observations expose identity
and position, not private inventory or hidden harvest histories. Institutions
cannot obtain monitoring evidence by reading the evaluator's ledger.

The current snapshots require a careful boundary. The qualification recorder
restores physical state and reuses previously committed actions. It explicitly
does not restore policy memory. A political checkpoint must also contain member
and institutional memories, charter state, pending proposals/messages, evidence
and outstanding custody obligations, with their timing and identities intact.

Historical bounded execution, observation validation, accounting and provenance
patterns are reusable engineering. The historical bounded adapter does not
already execute v3 candidates. Likewise, the old learner's validated likelihood
does not automatically apply to logistic renewal, mobile sensing and hidden
extraction. Reuse designs and controls where their assumptions hold; introduce
new versions for different state and observation contracts.

The repository's principal process risk is allowing validation and reporting
to become the research objective. The archive and replay infrastructure is now
an asset that should be used routinely. Another bespoke audit system, broad
cleanup or parameter sweep should earn its place by resolving a concrete
scientific decision. Preserve frozen duplicates rather than refactor them for
neatness. A single current plan and newest-first progress record are sufficient
to orient future work; earlier plans remain historical references.

## Immediate sequence and completion criteria

| Order | Work package | Completion criterion |
| --- | --- | --- |
| 1 | Close the existing incentive replay obligation. | The existing verifier reproduces every saved episode and aggregate, with a new receipt outside the bank. Any discrepancy is preserved and investigated. |
| 2 | Specify the political and physical capability contract. | Custody, consent, observation, timing, authority and absence of institutions have executable meanings, with a bounded first implementation. |
| 3 | Implement the smallest complete political lifecycle. | Deterministic fixtures exercise all required transitions, full checkpoints and resource/information limits, including failure and zero-institution outcomes. |
| 4 | Build one strong decentralized coordinator and simple voluntary charters. | Comparable generic capabilities, resources and information; responsive member choices are explicit and stubborn opportunists remain a separate stress control. |
| 5 | Develop and freeze the first institutional comparison. | A small declared development menu, then independent evaluation, meaningful consumption/cost/outsider endpoints and identified mechanism interventions. |
| Conditional | Implement and execute tipping v1 if its full surface changes the empirical design. | Separate executable/source freeze, unchanged panel, complete results including unresolved regions. Political implementation can proceed in parallel. |
| Later | Add bounded adaptation and consequential learning. | Strong baseline headroom, an appropriate v3 execution/model contract, and a separate budget for any model-driven campaign. |

The replay is a bounded closure task, not a new scientific panel or a reason
to repeat ecological auditing. Use the existing verifier without an ecology
argument, since the incentive bank contains its bound ecological input:

```bash
.venv/bin/python scripts/run_commons_v3_qualification_v1.py verify \
  --output evidence/commons-v3-incentive-qualification-v1 \
  --workers 4 \
  --receipt evidence/commons-v3-qualification-validation-v1/incentive-replay-v1.json
```

Use a new receipt path if that one already exists. Keep the log outside the
sealed bank. This plan does not execute the command. No new ecology publication,
figure or audit layer is needed to begin Stage 2 development.

## The first political implementation

Keep physical location, optional membership and asserted jurisdiction distinct.
Start with no organizations. A claim over a site grants no automatic priority,
exclusion, information or confiscation power. Individuals must be able to refuse
entry, withhold dues, violate a quota and leave. A quota describes a rule; it
does not clamp the physical harvest action.
No supranational actor enforces claims or agreements between organizations.

The first contract must settle how an institution holds resources, where they
can be spent, who controls transfers, and what happens on departure, amendment
or dissolution. An abstract treasury with unlimited geographic reach would
introduce a major capability that the existing world does not have. If new
resource or monitoring transitions are necessary, add a separately versioned
physical extension. Do not edit frozen `engine.py` or mutate inventories around
its accounting. With the extension inactive, old physical trajectories should
remain exactly reproducible.

For the first sanction mechanism, favor a narrowly bounded commitment funded
from voluntarily placed collateral, with explicit custody and evidence rules.
Its settlement guarantee is a supplied physical/contractual affordance, not
proof that enforcement emerges without assumptions. It cannot seize outside
inventory or compel a nonmember. If that guarantee cannot be grounded within
the chosen physical contract, begin with paid coordination and voluntary
transfers and record the enforcement limitation. General coercive confiscation
would require its own costly reach, resistance and predation controls and
should not be smuggled into a charter wrapper.

The end-to-end development fixture should show a local proposal and endorsement,
refusal, joining and funded activity, nonpayment, detected and undetected
violations, an attempted but unaffordable or unreachable sanction, exit,
amendment, replacement and dissolution. Specify when changes take effect so a
charter cannot retrospectively change dues and an exit cannot ambiguously erase
already committed obligations. Failed enforcement and institutional absence
must conserve resources as reliably as successful cooperation.

Tests should protect these boundaries, legal local information and whole-process
checkpoint continuation. The resulting traces establish a working lifecycle.
They do not establish emergence, deterrence, beneficial governance or evolutionary
stability. A possible implementation split is `politics_v1.py`, a separately
versioned political episode runner and audited institutional policies; these
are proposed module names, not capabilities already present in the repository.

## The first institutional question and fair controls

The next scientific question is whether optional, materially funded local
agreements can preserve or recover consumption under harmful peer behavior
better than strong decentralized coordination, and whether any member gains
come at outsiders' expense. Start with mixed populations and the existing
physical law. New demographic dynamics, new weather regimes and general warfare
are unnecessary for that first comparison.

Universal competent restraint remains an essential ceiling and overhead
control. With consumption already near full need at the reference, an added
institution cannot deliver a five-percentage-point consumption gain over that
ceiling. Costs may make nonformation the efficient outcome. The earlier
prospective 5%-of-need idea cannot be transplanted mechanically into this
comparison. Set the new smallest useful effects and primary contrasts before
its evaluation; do not revise the old thresholds or weaken the foragers.

Use a small initial baseline matrix:

| Condition | What it establishes |
| --- | --- |
| Frozen strong local foragers with no institution | The existing physical baseline and cost of adding governance. |
| Strong decentralized coordination without formal membership | Whether paid local communication, shared schedules or bilateral commitments suffice. |
| A simple optional coordinating charter | The effect of persistent organization and explicit membership using comparable underlying opportunities. |
| The charter with paid monitoring and bounded sanctions | The additional effect and cost of the specified monitoring/enforcement mechanism. |
| Universal restraint and universal supplied aggression | Ceiling and adverse anchors; neither replaces the strong decentralized rival. |

Match initial material resources, observation opportunities, movement and
communication costs. Generic physical capabilities must also be available to
noninstitutional actors where applicable. The organization may pool and arrange
those capabilities; it should not receive free powers that make the comparison
tautological. Formal political organization is the treatment, not free
omniscience or a new resource endowment.

Separate two behavioral roles. Responsive members use a declared local decision
rule or finite policy menu for joining, refusing, complying, violating and
exiting. Stubborn opportunists retain supplied nonresponsive behavior as a stress
control. Success against the latter can establish robustness or bounded physical
constraint, but cannot establish deterrence. A preprogrammed formation schedule
is an implementation fixture, not behavioral evidence. Keep the canonical
private utility unchanged and decomposed; using consumption as the research
endpoint does not silently change individual selection incentives or prove
that the response rule optimizes private utility.

Use a finite, recorded development menu for member and charter parameters,
including a joint numerical alternative where feasible. Then freeze selection,
environment conditions, social composition, primary comparisons and independent
evaluation seeds. Retain both strong forager backgrounds and unfavorable
storage/overhead controls; do not select a favorable world from the same panel
later called confirmation. Tipping data used to choose these conditions becomes
development information for the institutional study, even if it was prospective
for its own separate question.

Measure population consumption and shortfall over time, late outcomes, the
distribution of shortfall, stocks, access displacement and every material cost.
Report member and outsider outcomes, refusals, violations, exits and institutional
absence. Costs already deducted through the resource ledger must not be
subtracted a second time from realized consumption. Formation counts, longevity
and obedience are behavior measures; none is an automatic welfare success.

Membership creates selection bias. Define original-population and, where
appropriate, pre-entry or randomly offered-membership cohorts before treatment.
Retain exiters and excluded individuals in their original accounting. A rise in
current-member welfare can reflect losing the worst-off members. For a later
multiple-organization comparison, also record contested access and effects on
nonmembers; one functioning charter does not establish international outcomes.

Use a small number of mechanism interventions that answer an identified claim:
for example, disable useful monitoring or sanctions while retaining their
declared resource charge, then distinguish that result from refunding the
charge. Freeze those interventions and their timing before evaluation. A full
institutional removal changes several mechanisms and must be labeled accordingly.
An optional-entry comparison can include fixed affiliations diagnostically, but
fixed membership cannot stand in for a formation experiment.

## Role of the tipping protocol

The [existing tipping protocol](commons-v3-tipping-protocol-v1.md) is a specified
but unexecuted study: **12,288 episodes, 3,145,728 physical ticks and 75,497,472
individual decisions**, before replay. That is about **3.05 times the physical
work** of both completed qualification banks combined. It retains both controls,
four capacities, every integer peer count and 32 new seeds, with a separate
416-interval family.

Its full surface is scientifically useful if choosing institutional conditions
requires that resolution. It does not establish best responses, strategic
adaptation or institutional formation, and the simultaneous intervals may still
leave wide unresolved bands. More panel entries do not guarantee a unique
crossing. The existing protocol correctly permits no crossing or multiple
reversals.

Keep v1 unchanged. Before executing it, use the already recorded variation and
runtime to assess precision and cost, and state which design choice the results
will change. This is planning from existing data, not another simulation bank.
Implementation and deterministic lifecycle work can proceed while that decision
is made. A reduced decision-focused panel would require an explicit separate
prospective version, retaining v1 as the earlier design; it cannot be a silent
subset or adaptive extension.

Proceeding with Stage 2 engineering does not declare the failed Stage 1 incentive
gate passed. It adopts a distinct coordination/resilience question whose own
evaluation needs prospective criteria. The old scientific results remain
fail/unresolved, and no model-driven search is authorized by this sequencing
decision.

## When to return to adaptation and learning

Model-driven evolution needs three things beyond a working political simulator:
a consequential gap beyond strong simple and numerical baselines, a fair
prospective admission/evaluation design, and v3-compatible bounded candidate
execution. The legacy adapter is insufficient. Keep implementation, search,
repeated admission validation and untouched final evaluation separate. Budget
enough reciprocal updates to revisit members after institutional changes, retain
failures and rejections, and infer reliability over independent search runs.
Thousands of weather episodes do not replace replicated evolutionary runs.
A new inference route or allowance requires its own explicit decision.

The world-model investment remains useful. Its learner, reporting, calibration
and matched-decision controls provide methods for a later v3 study. Resume that
track when a specified costly information problem changes a consequential
action compared with a strong reactive controller and an appropriately scoped
known-law reference. Re-derive the observation model and likelihood for v3;
introduce unknown parameters before supplied-family selection and structural
discovery. Do not port every historical component simply because it exists.
This later track can proceed alongside institutional experiments once its own
decision and baseline requirements are met.

## Outcomes that should change the plan

If decentralized coordination solves the declared problem, report that result
and do not fund code evolution merely to force an institutional advantage. If
organizations form but cost more than they prevent, study the failure rather
than increase the terminal reward. If members gain while outsiders lose, retain
the tradeoff as a central result. If institutions fail to recruit, determine
whether the declared response model or costs explain it without relabeling a
scripted adoption schedule as emergence. Certified insufficient-supply cells
remain physical limits, not challenges any government must be able to solve.

The next concrete milestone is a complete optional political lifecycle and one
credible decentralized comparator under the same material and information
constraints. That would move the repository directly toward its original
question while preserving what the repair program has learned.
