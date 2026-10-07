# Research roadmap: interacting, evolving societies

The [current repository assessment and execution plan](research-state-and-next-steps-v1.md)
now supplies the active sequence after the completed qualification and review
response. The research themes below remain a historical catalogue. Stage 2
optional-institution development is next; the complete tipping experiment is
a separate empirical work package, not a prerequisite for every political
implementation task. No existing qualification verdict or model budget changes.

The first [political capability extension](commons-v3-institutions-contract-v1.md)
is now implemented and engineering-tested. Stage 2 next requires a declared
development comparison and independent institutional evaluation. Implemented
consent and escrow do not establish emergence or useful governance.

**Current priority, updated 7 October 2026:** the
[scientific review](research-review-2026-10-07.md) and
[spatial commons implementation plan](commons-v3-plan.md) now govern the next
stage: mobile individuals, optional changeable institutions, and no higher
authority between societies. Ecological incentive and baseline gates precede
new model spending. World models remain tools and a later research track.

The earlier priority selected learnable world models, first
parameter inference and then rule discovery. The
[world-model proposal](world-model-proposal.md),
[dedicated literature review](world-model-literature.md), and
[implementation plan](world-model-implementation-plan.md) develop that feature.
The first [stationary parameter-learning control](world-model-v1.md) is now
implemented and evaluated on 24 independent arenas.
The broader experiments below remain relevant; their earlier ranking does
not supersede the new spatial-commons plan.

Research reviewed **6 October 2026**. This is a technical synthesis and a
proposed research program, not a new preregistration or authorization for
additional inference. Existing experiment protocols and frozen evidence remain
authoritative. Recent preprints below are research leads, not established
consensus. Proposed extensions are identified separately from reported results.

## What is established

The repository implements a small, executable resource ecology: members make
partially observed decisions, institutions allocate resources and relay
information, and societies interact through shared harvesting, aid, raids, and
infrastructure spillovers. Individual and institutional programs can inherit
separately. A trusted simulator resolves consequences, enforces a conservation
ledger, and records exact program identities and replay data. Private memory,
shared memory, and reports exist within episodes; programs persist between
evolutionary updates. [Model](model.md), [original protocol](protocol.md).

The first exploratory run demonstrated working program evolution and
institutional enforcement. Its welfare improvement came from the explicit
infrastructure bonus while consumption shortfall worsened. That motivated v2,
which selects institutions on consumption and shortfall, varies episode and
disturbance timing, and includes matched no-drought controls.

The completed v2 pilot contains one budget-matched run pair and 648 evaluation
rollouts. Mean consumption welfare was 0.843162 initially, 0.846405 with fixed
institutions, and 0.847238 with coevolution. Coevolution reduced unmet
consumption relative to the fixed arm but increased outward harm and reduced
private utility. These tradeoffs motivate the next questions; one search pair
does not establish a reliable advantage for coevolution. [Work record](../PROGRESS.md),
[frozen v2 protocol](protocol-consumption-v2.md),
[compact results](../evidence/consumption-v2/final-summary.json).

The resumption audit narrows this further: coevolution attempted only
`M0, I0, M1, I1, M2`. No member was reevolved after its institution changed,
so reciprocal member–institution adaptation was not exercised. All 36 cases
against cooperative opponents reached the 0.85 welfare ceiling in every arm,
and between-society aid was zero. Some member/institution message keys differ;
channel compatibility and execution coverage need checking before attributing
benefits to information processing. Greater outward harm did not coincide with
lower average other-society welfare in the coevolution-versus-fixed comparison.

This is currently **interacting institutional societies**, with a central
institution inside each society. Reports flow through an institutional hub;
there is no evolving peer communication graph. Membership is fixed, and there
are no demographic births, deaths, migration, or group reproduction. There is
no learned neural world model. The Shinka archive is a search mechanism, not a
population of simulated societies. Spatial-looking replay layouts are
schematic: agents do not move through a physical landscape.

## A defensible research direction

The strongest prospective contribution is a **causal testbed for coevolving
executable governance under ecological and social change**. The question is:

> Which combinations of individual behavior, institutional rules, and
> information channels produce collective resilience, and when do those gains
> survive unfamiliar partners, opportunistic entrants, and damaged channels?

The constituent ideas already exist: two-level institutional learning in the
AI Economist [13], social generalization in Melting Pot [14], executable
collective artifacts in SwarmWorld [1], and mechanism-breaking institutional
controls in Han [3]. A potentially distinctive contribution would combine
these with separate member/institution inheritance, material accounting,
replicated search, and causal intervention records. This combination is a
research hypothesis, not a verified first-of-its-kind claim.

Our advantage should come from discriminating explanations. A high welfare
score, many messages, more infrastructure, or an elaborate program does not
alone establish collective intelligence. Each proposed mechanism needs an
intervention that should remove its benefit, plus a benchmark it should beat.

## Ranked experiments

All new diagnostic cases must use a separately named development bank. Once
their outcomes guide design, they cannot be described as untouched final
evaluation. Scientific changes require a new versioned simulator or protocol.

| Priority and experiment | Hypothesis and controlled comparison | Measurements and Chromatic Field figure |
| --- | --- | --- |
| **1. Member–institution transplant** — completed diagnostic | Descendant members and institutions complement one another. Cross initial/descendant members with initial/descendant institutions, keeping other inputs and environmental draws paired. Evaluate drought on/off. [Results and limits](mechanism-study.md). | Welfare, consumption, shortfall, private utility, outward harm; four-cell outcome plots and paired institutional-effect plots. |
| **2. Scarcity and dilemma map** — local simulation | Cooperation is useful only in identifiable incentive regimes. Sweep regeneration and demand, then mix candidate cooperative/selfish policies while fixing institutions. Compare the focal policy against the same co-player composition. | Consumption deficits, depletion, private payoff, outside harm; scarcity heatmaps and Schelling payoff curves showing profitable unilateral deviation. |
| **3. Memory and report interventions** — small evaluator extension | Stored information changes useful decisions. Compare intact programs with private-memory reset, institutional-memory reset, suppressed reports, stale reports, and independently shuffled reports. Separate content destruction from message-volume changes. | Paired outcome changes, action disagreement, response delay, channel-use frequency; intervention forest plot and aligned timelines. |
| **4. Cross-play and invasion** — frozen population matrix | Gains transfer beyond familiar collaborators and survive opportunism. Cross independently evolved member sets and institutions; introduce one selfish member, then increasing invader fractions. Keep opponent panels and seeds paired. | Invader advantage, resident welfare, externalities, recovery; cross-play matrix and invasion-payoff curves. |
| **5. Independent matched search replications** — new inference budget | Coevolution improves outcomes reliably for a declared compute budget. Repeat paired arms from identical starting populations, with independent search banks and search randomness per pair; allow enough scheduled opportunities to revisit members after institutional changes. | Per-run paired welfare differences, failures, opportunity counts, tokens, runtime, harm; paired dot plot with run-level intervals and explicit tradeoffs. |
| **6. Communication and authority topology** — new simulator version | Decentralization helps under local failure but can impair coordination. Compare institution hub, peer ring, local neighborhoods, and no messages with matched bandwidth and observation access. Separately vary fiscal authority. | Welfare versus communication cost, failure sensitivity, coordination delay; topology-by-disruption response surfaces and recorded flow networks. |
| **7. Quality-diversity archive** — new search arm | A repertoire of viable institutional strategies adapts better than one incumbent. Compare current search with a behavior-indexed archive at matched budgets and identical probe scenarios. | Archive coverage, qualified quality, held-out robustness, worst-case welfare, selection cost; repertoire maps and Pareto plots. |
| **8. Coevolving environments and cultural inheritance** — later program | Changing challenges and reusable institutions create sustained transferable innovation. Compare fixed curriculum, random curriculum, and bounded environment coevolution; independently test inherited code versus inherited episode state. | New solved regimes, transfer matrix, persistence, lineage reuse, plateau duration; environment–policy maps and lineage timelines. |

### Start with explanations, then spend on search

For the transplant, let `W_mi` denote an outcome with member source `m` and
institution source `i`, where 0 is initial and 1 descendant. Report all four
cells and `W_11 − W_10 − W_01 + W_00`. This interaction measures
complementarity on the chosen outcome scale. It is conditional on the frozen
trajectory and evaluation setting; it does not show that coevolution reliably
discovers that complementarity. Full-population transplants and focal-society
transplants answer different questions and should be labeled separately.

The completed diagnostic ran 864 local rollouts without model inference.
With evolved members held fixed, replacing original institutions with evolved
ones increased mean welfare by 0.001819 and outward harm by 0.076462 resource
units per tick. With original members, the institution swap changed outward
harm by exactly zero. The additional harm arose in society 1. The welfare
interaction was +0.000434, with a descriptive environment-cluster interval
spanning zero; this is not established beneficial synergy. The next targeted
intervention should independently toggle raid permission while preserving
the rest of the evolved institution, then test message and memory channels.
The full institutional swap alone cannot assign the effect to its permission
rule. [Diagnostic evidence](../evidence/mechanism-v1/summary.json).

For disturbance response, compare drought versus no drought with identical
exogenous draws, then contrast that paired effect between treatments. A rising
post-disturbance trajectory can otherwise reflect ordinary accumulation.
Report effects on other societies separately from raid losses: local welfare,
external harm, and outsiders' total welfare can move in different directions.

Scarcity maps should come before a larger search campaign. Consumption is
capped by need, so near-full consumption gives little welfare headroom. A
declared grid spanning abundance, binding scarcity, and severe shortage can
reveal informative regimes. Keep population size fixed initially; changing
population also changes aggregate consumption and competition. Evaluate
cooperative/selfish labels as hypotheses using actual payoffs. SocialJax uses
Schelling diagrams for this purpose [7]. Increasing contributions is not
sufficient if compulsory tax explains the change.

Add an information-bottleneck task family where no single member observes
enough to choose well, but pooled local reports can resolve the decision.
Measure improvement over both isolated local rules and a matched full-information
reference. The current task may allow successful harvesting without reports.

Memory ablations require care. Resetting a state dictionary can break an
interface or force perpetual initialization; distinguish invalid executions
from behavioral effects. Establish that a channel is read and behaviorally
active, then perform interventions that preserve its schema. For delayed or
shuffled reports, preserve the reporting rate and use a separately seeded
intervention stream. A null result may mean redundancy or unused information,
not that memory never matters. Mechanism-breaking controls follow the logic
of Han's institutional study [3]; these particular treatments are our proposal.

### Make interaction a measurable object

For cross-play, evaluate a member set with its own institution, another run's
institution, and the original institution. Also vary opponent populations.
This separates internal compatibility from robustness to outsiders. An
invader's private gain and residents' collective loss are distinct endpoints.
The present fixed-membership model can test these interventions but cannot
demonstrate evolutionary fixation; actual replacement dynamics would be a
separate extension.

Preserve the empirical payoff matrix rather than only a scalar leaderboard.
Strategies may be nontransitive. Alpha-Rank supplies a principled analysis of
finite strategy interactions [15], but its answer is conditional on the
sampled strategies and population model. Start with transparent payoff and
best-response plots; add rankings only after payoff estimates are stable.

Topology experiments must disentangle information from power. Removing the
institution currently removes more than a communication hub: taxation,
redistribution, and enforcement may disappear too. First vary communication
while holding allocation rules fixed, then vary authority in a separate
factor. Charge communication by the same byte or transmission budget, and
measure hub failure versus random local failures. Physical local sensing,
travel, and stigmergic fields would require new environment dynamics; a
network drawing alone does not implement them. SwarmBench's decentralized
setting is a useful external comparison [2].

### Add diversity before claiming open-endedness

Shinka already supplies program variation and archive sampling [8]. Its
contextual improvement score is not an absolute measure across changing
opponents. For quality-diversity, reevaluate candidates on a fixed development
probe panel before archive insertion. Start with two interpretable descriptors,
such as voluntary transfer rate and reserve share; distinguish tax from
contribution. Keep harm and inequality visible as separate outcomes. Store
high-quality alternatives within descriptor cells, following MAP-Elites [10].

Measure functional diversity: do archived alternatives solve different
disturbances or partner conditions? Source-code novelty is not enough.
Compare a selected repertoire with a single-policy baseline while accounting
for the cost and information available to the selector. Multiagent QD offers
precedent for contingency adaptation [9], but its cooperative control results
do not establish benefits in this mixed-incentive ecology.

A later POET-inspired extension could evolve challenge parameters alongside
policies, with admissibility rules excluding impossible or trivial worlds and
transfer attempts between niches [11]. Keep an external task panel fixed to
measure progress. Expanding an archive inside fixed action and environment
schemas is bounded exploration. Claims of open-ended progress need explicit
novelty, learnability, and continued transfer criteria [12], not merely a long
run or increasing program length.

## Replication, compute, and evidence

The completed v2 search budget is exhausted. Publishing and deterministic
diagnostics can reuse frozen programs without inference. A new campaign
requires a concrete new budget; this roadmap does not extend the original one.

A practical planning candidate is 8–12 independent matched run pairs, subject
to throughput and budget review. This is a starting design, not a power
guarantee. Define a smallest scientifically useful effect and assess precision
using a separate planning pilot or sensitivity analysis. One observed pair
cannot estimate between-search variance adequately. Fix the final number of
pairs and stopping rule before inspecting confirmatory outcomes.

Budget for repeated selection cycles, not just several accepted edits. Under
the current coevolution schedule a member is revisited only after 24 proposals.
Use measured proposal throughput to plan multiple rotations and record actual
coverage. A run with too few opportunities tests an initialization regime;
it cannot substantiate reciprocal coadaptation.

Use equal active wall-clock allowance as the primary compute comparison, as
v2 does. Record proposals, completed evaluations, accepted replacements,
member/institution opportunities, tokens, and infrastructure failures. A
secondary fixed-evaluation-budget experiment would answer a different
efficiency question. Equal time does not imply equal search opportunities or
equal inference usage. Do not silently change the model, inference route,
archive behavior, or scientific rules midway through a campaign.

For claims about search, the independent run pair is the inference unit.
Environment seeds, members, societies, and ticks are nested observations.
Average the declared common evaluation panel within each run before computing
paired run-level effects. Retain negative runs and every arm. Conditional
environmental intervals can supplement, but cannot replace, this variation.
Reliable RL evaluation emphasizes uncertainty rather than point estimates
alone [16]. Avoid treating bootstrap output from a tiny number of runs as
strong evidence.

Keep one primary endpoint and predeclare secondary tradeoffs. Consumption
welfare, tail shortfall, individual utility, within-society inequality, and
outward harm should remain distinct. Use stress episodes beyond the search
horizon to test persistence and recovery. Controlled misinformation or stale
memory could later test failure propagation; Emergence World motivates this
question [6], while its LLM-driven long-duration results do not transfer
automatically to our executable policies.

## Visualization contract

Every experiment should produce a data table, concise caption, provenance
manifest, and deterministic SVG/PDF/PNG figure, with animation when temporal
behavior matters. Follow [Chromatic Field v1](visual-reference.md): warm white
`#FFFEFC`, dark text, fine rules, and stable cobalt/magenta/orange society
identities. Use explicit condition labels rather than silently repurposing
society colors. Plot individual run estimates whenever feasible.

Phase diagrams should label observed grid cells and any interpolation;
lineage diagrams should separate inheritance from causal evidence. Replays
should show recorded actions, resource transfers, and disturbance boundaries.
Decorative fields must never masquerade as measured density or physical
space. Uncertainty, missing evaluations, failed candidates, and negative
results belong in the same visual language as successful outcomes.

## Annotated primary sources

Dates distinguish first preprints from verified venue or revision information.
The annotations describe sources; experiment designs above are our synthesis.

1. **Pal, Wang & Buehler — [SwarmWorld](https://arxiv.org/abs/2608.26081), 26 Aug 2026, preprint.** Deterministic material consequences, executable artifacts, cultural ablations, and matched isolated-search controls. Shared worlds improve portfolio outcomes, not every best-artifact endpoint. Four world seeds per comparison limit inference; fixed model weights and artifact reuse do not demonstrate this repository's multilevel program selection.

2. **Ruan et al. — [Benchmarking LLMs' Swarm intelligence](https://arxiv.org/abs/2505.04364), first submitted 7 May 2025.** SwarmBench tests decentralized coordination under local perception and communication. Useful for a second, spatial substrate. Do not confuse it with Gao et al.'s separate [SwarmBench orchestration benchmark](https://arxiv.org/abs/2608.30661), 31 Aug 2026, which evaluates orchestrators.

3. **Han — [When Do Institutions Beat Intelligence?](https://arxiv.org/abs/2608.11357), 11 Aug 2026; v2, 7 Sep 2026, preprint.** Controlled institutional and capability comparisons identify information-routing, validation, state, and action bottlenecks. Matched controls remove or invalidate the proposed institutional signal. Synthetic ecologies and simulated strategic reporters bound generality.

4. **Fei, Guo & Xiao — [When Agents Evolve, Institutions Follow](https://arxiv.org/abs/2604.27691), 30 Apr 2026, preprint.** Compares seven historical governance specifications across models and tasks; rankings change and review gates can fail. Institutions are static specifications, so the title is not evidence of endogenous institutional evolution.

5. **Molinghen, Charels & Lenaerts — [Certifying cooperation](https://arxiv.org/abs/2609.06586), 6 Sep 2026; v2, 10 Sep, preprint.** Temporal cooperation graphs and bounded-horizon certificates distinguish required cooperation from rewarded partial completion. Useful measurement discipline; certificates are specific to the task, horizon, and complete-success definition.

6. **Akkil et al. — [Emergence World: Adversarial Stress-Testing of Long-Horizon Multi-Agent Systems](https://arxiv.org/abs/2609.17320), 15 Sep 2026, preprint.** Persistent agent worlds expose delayed propagation of misinformation and memory contamination. Motivates controlled persistence tests, not an assertion that the same failures occur here.

7. **Guo et al. — [SocialJax](https://arxiv.org/abs/2503.14576), 18 Mar 2025; v3, 17 Mar 2026; accepted ICLR 2026.** Efficient sequential social-dilemma environments, behavioral metrics, and Schelling diagrams. Promising future comparison substrate; reported acceleration is tied to its JAX pipeline and hardware, not a predicted speedup for arbitrary Python policies.

8. **Lange, Imajuku & Cetin — [ShinkaEvolve](https://arxiv.org/abs/2509.19349), 17 Sep 2025; [ICLR 2026 paper](https://openreview.net/pdf?id=lKEdGCoDNC).** Program evolution with archive sampling, novelty filtering, and model allocation. The repository uses a pinned, restricted configuration; paper-wide results do not validate our ecology or imply all upstream features are enabled.

9. **Iyer et al. — [Multiagent Quality-Diversity for Effective Adaptation](https://journals.sagepub.com/doi/10.3233/FAIA251201), ECAI 2025 proceedings; publisher online date 25 Aug 2026.** MASQD develops diverse team repertoires and tests contingency adaptation in cooperative control. Supports functional archive evaluation; distinct from evolving mixed-incentive institutional programs.

10. **Mouret & Clune — [Illuminating search spaces by mapping elites](https://arxiv.org/abs/1504.04909), 20 Apr 2015, foundational paper.** MAP-Elites retains quality across user-defined behavioral niches. Descriptor choice defines what diversity is visible and must be justified.

11. **Wang et al. — [Enhanced POET](https://proceedings.mlr.press/v119/wang20l.html), ICML 2020.** Coevolves challenges and solutions and transfers solutions across environments. Basis for a bounded curriculum extension, not evidence that unlimited innovation follows automatically.

12. **Hughes et al. — [Open-Endedness is Essential for Artificial Superhuman Intelligence](https://arxiv.org/abs/2406.04268), 6 Jun 2024, position paper.** Defines open-endedness through observer-relative novelty and learnability. Useful operational vocabulary; its broader thesis is an argument rather than a demonstrated guarantee.

13. **Zheng et al. — [The AI Economist: Taxation policy design via two-level deep multiagent reinforcement learning](https://www.science.org/doi/10.1126/sciadv.abk2607), Science Advances, May 2022.** Prior art for jointly adapting individual agents and institutional economic rules. Our prospective distinction must be tested in program inheritance, changing societies, and causal diagnosis, not claimed from two-level learning alone.

14. **Agapiou et al. — [Melting Pot 2.0](https://arxiv.org/abs/2211.13746), first submitted Nov 2022, technical report.** Standardizes evaluation against unfamiliar social partners across varied scenarios. Supports cross-play and held-out populations rather than evaluation against environmental randomness alone.

15. **Omidshafiei et al. — [Alpha-Rank: Multi-Agent Evaluation by Evolution](https://arxiv.org/abs/1903.01373), 2019.** Analyzes asymmetric and nontransitive empirical games through evolutionary dynamics. Useful after a payoff matrix exists; rankings cannot establish robustness against strategies never evaluated.

16. **Agarwal et al. — [Deep Reinforcement Learning at the Edge of the Statistical Precipice](https://arxiv.org/abs/2108.13264), NeurIPS 2021.** Demonstrates the fragility of benchmark conclusions based on few runs and point estimates; motivates interval estimates and explicit run-level variability here.
