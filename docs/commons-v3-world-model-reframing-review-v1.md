**Current plan:** [Paper contract v1](paper-contract-world-models-v1.md) replaces the reframing review’s “Next decision” section and is the current binding plan.

# World-model reframing: scoped literature review and decision, version 1

7 October 2026. This is a research-direction review, not an experimental
protocol, source freeze, or authorization to execute a panel.

The exclusion-first paper proposal is superseded. **Ticket 1, the adaptive
exclusion controller, is paused.** The implemented physical mechanism remains
available as an optional extension. The active objective returns to explicit,
consequential world-model learning and collective inference. Developing the
previous proposal before checking its closest literature was a sequencing error;
a well-controlled experiment does not by itself establish a useful contribution.

## Decision and limits

The review supports changing the question. It does not yet justify the broad
claim that learning a renewable environment, collective inference, or harmful
information sharing is new. All three have substantial antecedents. Nor does a
selection of recent papers establish that the whole swarm-intelligence field
has moved to one topic. Collective inference is a relevant active research line
that fits this repository's original objective.

The recommended **candidate** question is:

> When does costly local evidence sharing help a foraging swarm learn useful
> resource dynamics and sustain consumption, and when do correlated evidence
> or the resulting harvesting decisions make sharing harmful?

Its possible contribution is a causal account of the link between distributed
knowledge and material outcomes when harvesting changes both the resource and
future evidence. That intersection needs further checking against the closest
work below. It is not a claim of first use of Bayesian learning, sustainable
foraging, endogenous sampling, paid information or decentralized communication.
No result is promised: better inference may leave decisions unchanged, help
individuals overharvest, or fail to repay monitoring and communication costs.

The next deliverable is an observation-and-decision contract, after resolving
the remaining literature questions. There is no replacement arm matrix, parameter
grid, sample allocation or implementation campaign in this document.

## Scope and primary-source findings

This is a scoped review as of 7 October 2026, not an exhaustive systematic
review. It starts with the supplied papers, checks original manuscripts, and
follows adjacent work on adaptive resource management and information sharing.
Primary full texts were inspected for the arXiv papers in the table, Ju et al.
and Dubois et al.; access limits and abstract-only leads are identified below.
Versions matter: the stubborn-robot paper's v2 title differs from its 2025 v1.
Recent preprints are evidence of overlap, not field consensus. No alphaXiv
AI-generated overview is used as methodological evidence.

| Primary source and inspected version | What overlaps, and what remains distinct |
| --- | --- |
| [Perolat et al., *A multi-agent reinforcement learning model of common-pool resource appropriation* (2017, v2)](https://arxiv.org/pdf/1707.06600v2), §§3.3–3.4 | Independent deep-Q agents learn territorial exclusion; defended regions support healthier stocks, and easier exclusion increases inequality. This substantially overlaps the rejected headline. Their policy learning does not fit an explicit ecological transition model. That difference alone does not establish our novelty. |
| [Leibo et al., *Multi-agent Reinforcement Learning in Sequential Social Dilemmas* (2017, v1)](https://arxiv.org/pdf/1702.03037v1) | Scarcity can increase learned aggression. Gathering uses fixed-delay apple respawning, unlike stock-dependent renewable depletion. Aggression under scarcity is consequently an antecedent, not a new claim to pursue. |
| [Payne, Aishwaryaprajna and Lewis, *Online Learning of Temporal Dependencies for the Sustainable Foraging Problem* (2024, v2)](https://arxiv.org/html/2407.01501v2) | Recurrent learning improves single-agent sustainability but does not reliably solve the multi-agent setting. Inputs include aggregate resource and population/action information. The proposed future reflective meta-layer is broader than an explicit learned regrowth model; the paper does not establish that missing ecological knowledge caused the group failures. |
| [Heins, *Collective Sensing as Emergent Bayesian Inference* (3 October 2026, v1)](https://arxiv.org/html/2610.04415v1), §§2–4 | Gives a Bayesian interpretation of collective gradient sensing in a changing light field. The inferred posterior describes the school; individual agents do not execute the proposed Bayesian filter. Correlation, overlapping evidence and overconfidence are already explicit concerns. This rules out “collective perception only studies static features” as a blanket distinction. |
| [Legarda Herranz, Francesca and Birattari, *Gaussian Processes for Modelling Spatial Fields with Robot Swarms* (15 September 2026, v1)](https://arxiv.org/html/2609.17463v1), §§II–III | Learns spatial fields while establishing a common reference frame through local communication, with peer-model fusion and forgetting. Distributed probabilistic field learning is already established here; learning regenerative dynamics while consuming the field is a different proposed task. Our coordinate-aware simulator is not a reproduction of their localization problem. |
| [Madin et al., *Collective Ranking of Environmental Signals through Gaussian Belief Propagation in a Patrolling Robot Swarm* (18 August 2026, v1)](https://arxiv.org/html/2608.17690v1), §§2–3 | Combines patrol movement, local measurements and message passing to infer and rank environmental signals; evaluates against averaging and on physical robots. Useful distributed beliefs and action-dependent observation locations are not new by themselves. It does not test extraction of a regenerating resource. |
| [Chin and Pinciroli, *BayesCPF* (7 April 2025, v1)](https://arxiv.org/html/2504.04774v1), §§III–IV | Couples fill-ratio inference to sensor-accuracy estimation under degradation. Calibration and unreliable sensing are direct antecedents. Its binary field and sensor model do not transfer unchanged to hidden harvesting and renewal. |
| [Zakir et al., *Bio-inspired decision making in robot swarms under biases* (14 June 2026, v2)](https://arxiv.org/html/2509.07561v2) | Compares direct-switch and cross-inhibition under stubborn opinions, independent discovery and corrupted messages. Bias robustness is already studied. Our existing stubborn harvesters are fixed action policies, not an implemented population of stubborn ecological beliefs. |
| [Tupayachi, Li and Das, *Learning to Harvest Without Collapse in a Regenerative Commons: A Lagrangian Framework* (2026, v1)](https://arxiv.org/html/2609.36478v1), §§2, 4.3 and appendices | Learns harvest policies for two agents on a deterministic stock, with exact normalized biomass and a designer-controlled ecological price. It does not fit a growth-law posterior or test paid local evidence sharing. Its terminal-depletion constraint averages across reset episodes; that is distinct from safety throughout one continuing commons. |
| [Ju et al., *Model-based offline reinforcement learning for sustainable fishery management* (online 2023; journal 2025)](https://onlinelibrary.wiley.com/doi/full/10.1111/exsy.13324), §§3–5 | Learns fishery dynamics from incomplete catch/effort data and plans with the resulting partially observable model. It tests misspecification and nonidentifiability under insufficient effort variation. “Learn the ecology, then harvest sustainably” is already directly addressed; the proposed distinction must concern distributed online evidence and its collective consequences. |
| [Dubois et al., *Contrasting effects of information sharing on common-pool resource extraction behavior* (2020)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0240212) | Human experiments compare disclosure rules and strategic reports. Sharing can change extraction adversely as well as beneficially. Their repeated token game and revealed aggregate extraction differ from learning hidden regenerative dynamics. Information sharing helping or harming commons users is nevertheless an established question. |

Adjacent primary sources further narrow the candidate. The original
[Walters and Hilborn working paper on adaptive control of fishing systems](https://pure.iiasa.ac.at/id/eprint/314/)
already combines parameter estimation and informative control. Publisher abstracts
for [Springborn and Sanchirico (2013)](https://doi.org/10.1016/j.jeem.2013.07.003)
and [Kling, Sanchirico and Fackler (2017)](https://doi.org/10.1016/j.jeem.2017.01.001)
cover endogenous learning through harvesting and jointly costly monitoring/control,
respectively. The [Kuusela and Laiho (2020) abstract](https://www.sciencedirect.com/science/article/pii/S0095069619300579)
also places Bayesian information acquisition and spillovers inside a strategic
common-pool problem. These are overlap warnings, not grounds for claiming we
have completed a full comparison of their assumptions and proofs.

Two especially close sources still require full-text comparison. The identity of
[Aishwaryaprajna and Lewis's ALIFE 2023 sustainable-foraging paper](https://doi.org/10.1162/isal_a_00646)
is verified, but primary full text was inaccessible; its detailed governance
mechanism is not treated as checked. The authors' abstract for
[Mills and Lewis's *Think Before You Act* (2025)](https://www.trustworthyai.ca/publication/think-before-you-act-popperian-expectations-for-adaptive-agents/)
describes causal expectations from internal simulation; full-text comparison
is still needed. Generic reflection is therefore also too broad a novelty claim.

Before claiming a distinct paper contribution, complete these closest full-text
comparisons and a focused citation search on decentralized adaptive harvesting
with private, shared and strategically selected evidence. A failure to find an
identical design in this pass is not proof that none exists.

## What the repository actually supplies

The original [world-model proposal](world-model-proposal.md) asks how societies
acquire accurate, transferable knowledge and at whose cost. The completed
[parameter](world-model-v1.md), [sharing](world-model-sharing-v1.md),
[decision](world-model-decision-v1.md) and [costed-experiment](world-model-experiment-v1.md)
studies already distinguish learning, reporting and material value. Their mixed
results remain part of the motivation: prediction gains did not establish
broad consumption benefits. The return to this objective preserves that work
instead of treating the political primitives as the project's destination.

Current [local observations](../swarm_societies/commons_v3/engine.py) expose
visible patch stock and capacity, coordinates and peer locations. They do not
supply the renewal coefficient, law flag, weather realization, recovery term
or other agents' realized harvest. Stock sensing is currently exact; noisy
local stock sensors would be a new condition, not a capability already present.

The [navigation forager](../swarm_societies/commons_v3/policies_navigation_v1.py)
uses capacity to compute a configured residual-stock floor. The fixed control's
fraction is 0.5. For positive logistic growth, half-capacity maximizes potential
one-step production before weather/clipping. This is a powerful supplied prior.
It is not a proof of an optimal individual policy under movement, contention,
reserves and finite horizons, and the forager never evaluates a transition law.
Thus the review's substantive criticism stands, but “every agent knows the
full world model” and “today's forager is a known-law oracle” are too strong.

A future hidden-capacity condition must version the observation contract and
check indirect disclosure through initial stock, normalization, policy constants,
reports and restored memory. Removing one field is insufficient if every arena
still starts at its secretly varied capacity. World truth remains available to
evaluation, never silently to a learner.

### Identifiability comes before choosing the learner

For a stationary observer of one patch, write

```text
z_t = S_t − H_t
S_(t+1) = z_t + G_t
logistic potential growth = r × z_t × (1 − z_t/K) + recovery
additive potential growth = r × K/4 + recovery
```

The engine applies multiplicative weather and clips growth to remaining
capacity. `H_t` is total realized extraction, not the observer's own harvest.
Consecutive stock observations and own receipts cannot generally identify
regrowth when others also harvest. A likelihood that substitutes own harvest
for total harvest would confuse neighbors' behavior with ecology.

There is a useful existing affordance: [paid local monitoring](../swarm_societies/commons_v3/politics_v1.py)
is available to stationary nonmembers too. Its private next-tick evidence lists
realized extraction by final on-site actors. Combined with consecutive local
stock observations, a complete monitor record can recover post-harvest stock
and realized growth. This is a candidate legal measurement path with an actual
cost, not a new free global sensor or evidence that buying it will pay. Timing,
completeness, clipping and weather must enter the new likelihood explicitly.
Unmonitored transitions require a specified latent-extraction model or exclusion
from direct law-identification updates; they cannot be labeled clean evidence.

There are further restrictions even with observed extraction. Away from clipping,
additive renewal identifies the production combination `r*K/4 + recovery`,
not all its factors separately. Logistic and additive potential production agree
at `K/2` with matching coefficients: observations concentrated there may poorly
distinguish them. Hidden capacity is learnable only under stated conditions;
variable conditions and informative stock ranges must be justified. Parameter
learning inside a supplied family, choosing between supplied families, and
structural equation discovery are three different claims.

The [historical learner](../swarm_societies/world_model_v1/learner.py) uses a
different additive law, infrastructure effects, weather placement and noisy
growth sensor. Reuse inference architecture, provenance/deduplication,
prequential scoring, snapshots and reference methodology. Re-derive the
likelihood and its calibration for v3. The old 192-reference result is not a
calibration certificate for this new observation process. Historical truthful
report registration also cannot be silently equated with v3's unverified peer
assertions.

## What survives, and what must change

| Retain | Necessary change for the learning question |
| --- | --- |
| Ingredient-isolating controls | Preserve the logic, not the old exclusion arms. Individual versus shared learning needs matched sensing/planning; a frozen-belief control separates learning from controller complexity. Neutral copying has no automatic role if imitation is absent. |
| Strong reactive and greedy references | Keep the existing foragers, but declare their capacity information. A true-coefficient reference should use the same local state, action menu and planner as learners; it is still not a globally optimal controller. |
| Identical-state branches | Snapshot beliefs, evidence provenance, queues, memories, capability and keyed randomness as well as physical state. Cutting future sharing measures its continuation value; it does not erase previously shared knowledge. Tick 768 is retained only if justified in the eventual protocol. |
| Physical value of food under shocks | Consumption and maintained capability are material outcomes. Do not reward terminal inventory in imitation, learning targets or selection. Storage can help through actual future consumption/function. Shock and capability dynamics remain unimplemented. |
| Bounded development and independent evaluation | Retain four development seeds, one complete freeze and 32 fresh evaluation seeds as the user's planning envelope. No seed range or power guarantee carries over from the rejected plan; no new panel is launched now. |
| Null outcomes and distributional accounting | Separate predictive quality, uncertainty calibration, behavioral change, consumption/capability and resource persistence. Report who gains and pays. Accurate shared beliefs need not improve collective welfare; agreement is not accuracy. |
| Provenance and cost controls | Reuse deduplicated evidence and matched-byte principles. Equal-evidence analysis distinguishes information quantity from inference efficiency; equal-cost controls distinguish information value from paying different fees. Repeated posterior multiplication is not independent evidence. |
| Optional institutions without higher authority | Later ask which local rules support useful measurement and reporting, once that information problem is shown to matter. Preserve exclusion as an extension; do not force a territorial-emergence claim into the first learning paper. |

The small, no-mutation imitation design would establish selection among seeded
traits, not learning an ecological law. Founder effects and fixation would need
explicit handling if it returns. This is a question-to-method mismatch; using
an older numerical method is not itself a scientific defect. Conversely,
adding neural networks, mutation or more agents would not repair missing novelty.
A 24-agent study also cannot establish swarm-size scaling without testing it.

“Misinformed” needs a distinct definition. Wrong initial beliefs, ignored
updates, biased sensors, false reports and permanently aggressive actions are
different interventions. Do not combine them into one supposedly diagnostic
stubborn arm. Likewise, sharing can hurt through repeated evidence, accurate
but synchronized harvesting, or material fees. Those explanations require
different controls. Information carried in paid local messages is not inherently
non-excludable or beneficial to outsiders; its public-good properties are an
empirical issue, not an assumption.

## Next decision, before a new plan

1. **Close the nearest-literature comparison.** Resolve the identified full-text
   gaps where possible and compare distributed adaptive harvesting and strategic
   information work on information, incentives, learning targets and outcomes.
   State a contribution that remains worthwhile without a “first” claim.
2. **Write one explicit observation-and-decision contract.** Choose what is
   unknown; specify legal measurements and hidden extraction; show which harvest,
   route or monitoring decision a changed belief can change. Estimating a
   parameter while always applying the same floor would not make knowledge
   consequential. Do not automatically replace the floor with posterior `K/2`.
3. **Decide whether the proposed contribution is identifiable.** Require a fair
   true-coefficient comparison and a route to separating inference failures,
   decision failures and incentive conflict. If local data cannot identify a law,
   narrow the claim to predictive control or revise the measurement assumptions
   openly; do not present posterior concentration as successful discovery.
4. **Only then specify the minimal experiment.** Choose contrasts, the physical
   storage mechanism, measurement costs and uncertainty conditions to answer
   that question. Develop on the bounded seeds, freeze once, and evaluate fresh.
   Larger mechanism menus, publication layers and exclusion are later decisions.

This sequence restores the world-model objective without discarding the repaired
physics, negative institutional evidence, paid monitoring, communication or
checkpoint machinery. Completed banks, frozen sources and published identities
remain unchanged. No new simulation, adaptive controller, model call, figure,
raw archive or receipt is produced by this review.
