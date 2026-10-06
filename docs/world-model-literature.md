# Learning the laws of the swarm world: literature and design implications

Reviewed **6 October 2026**. This targeted primary-source review supports the
[world-model proposal](world-model-proposal.md). It covers model-based
reinforcement learning, uncertainty, active system identification, equation
discovery, executable models, and causal identification. It is not a systematic
or exhaustive review. Sources were checked against publisher proceedings,
journal pages, or original arXiv records; recent preprints and conceptual papers
are labeled separately. Searches included foundational methods and 2025–2026
work available by the review date. Design recommendations below are our
synthesis, not results already demonstrated in this repository.

The user has selected **both stages**: first learn unknown parameters in a
declared mechanism family, then learn which mechanisms and equation structures
govern the environment. These are different scientific achievements and should
have separate protocols and endpoints.

## The decision for this repository

Build a small, structured probabilistic world model first. Give it explicit
predictions, uncertainty, and a restricted history of observations. Add neural
and executable-program alternatives as comparisons once the measurement and
information boundaries work. Our world already exposes numerical quantities;
rendering observations into images would introduce an unnecessary perception
problem. The existing architecture and observation limits are documented in
[model.md](model.md).

| Approach | What it contributes | Recommended place | Principal limitation |
| --- | --- | --- | --- |
| Bayesian regression or probabilistic ensembles over mechanism heads | Cheap online updates, interpretable coefficients, uncertainty | First parameter-learning implementation and persistent baseline | Correct coefficients require informative observations and an adequate assumed structure |
| Recurrent neural world model | Compresses histories and represents hidden state and nonlinear dynamics | Matched predictive baseline after the data contract is stable | Good predictions or rewards do not establish interpretable law recovery |
| Sparse or symbolic equation model | Selects terms, branches, and functional relations | Second stage: explicit structure discovery | Search grammar, observations, and excitation bound what can be discovered |
| Executable code world model | Expresses discrete events and compositional rules; can support planning | Later structural-discovery arm, with numerical fitting and verification | Model-generation cost, program errors, prior knowledge, and evaluation leakage require measurement |

PETS supplies a practical uncertainty-and-planning precedent [1]. PlaNet and
Dreamer explain why a history-dependent latent state can support decisions
under incomplete observations [2,3]. TD-MPC2 illustrates strong control with an
implicit model [4]. These methods motivate comparisons; their control results
do not decide which architecture best measures learning in this small economy.

Use separate components for physical transitions, beliefs about unobserved
state, and predictions of other societies' actions. This separation is a
modeling choice to test. It prevents us from defining every opponent strategy
change as a change in physical law. A model can still be wrong about any of
these components; log their predictions separately.

## Identification comes before architecture

The current observation contract does not identify every simulator coefficient.
Members see their own and a rotating other patch, but not all withdrawals,
weather draws, or neighbouring infrastructure. Institutions see local finances
and reports, not the complete environmental ledger. A patch-stock difference
therefore mixes regeneration, extraction, capacity clipping, and spillovers.
Personal wealth differences mix production, taxation, consumption, transfers,
and theft. The previous action is observable; its complete material receipt is
not currently an observation.

Consequently, fitting a stock predictor is a valid forecasting experiment but
is not automatically a regeneration-law experiment. If high regeneration and
high hidden extraction explain the same evidence as low regeneration and low
extraction, the learner should retain ambiguity. Instrumented local receipts,
additional costly measurements, or controlled experiments can resolve selected
ambiguities in a new simulator version. They are changes to the information
available, and must be charged and documented.

Identification theory reinforces this distinction. Controlled-world-model
results connect counterfactual reliability to conditional action variation,
under restrictive assumptions [14]. Causal representation results require
specified interventions and assumptions, rather than prediction alone [16].
Neither theorem applies wholesale to this ecology. Their practical implication
here is to test whether the data can distinguish the competing explanations
before scoring one explanation as learned.

Report three levels separately: **parameter identification** within a supplied
formula; **model selection** among supplied formulas; and **structural
discovery**, where the learner introduces missing terms or relationships from
an allowed grammar. SINDy is a strong inspectable baseline, but cannot recover
terms outside its library [5]. Even structural discovery has a hypothesis
language; disclose its variables, operators, priors, and complexity limits.

## Learn through experiments, then test transfer

Existing policies often repeat a narrow subset of actions. More such data may
improve familiar forecasts without identifying response to an untried action.
Active system identification gives a principled reason to vary informative
inputs, although its cleanest guarantees concern much simpler systems [7].
Plan2Explore provides an operational comparison: seek disagreement about future
outcomes rather than merely revisit observations that were surprising [6].
Unpredictable weather can sustain error without offering useful new knowledge.

For our experiments, compare random exploration, fixed coverage schedules, and
model-disagreement selection with equal opportunities and observation budgets.
In-world probes must consume the declared action or resource opportunity.
Evaluator-only cloned interventions can establish ground-truth effects, but
their answers must not enter learner memory. Keep development probes distinct
from final held-out interventions.

Recent equation-discovery work strengthens the second stage. LLM-SR separates
program structure proposals from numerical coefficient fitting [9]. LLM-ACES
connects competing symbolic hypotheses to adaptive data collection [12]. ALDER
adds independent validation and explicit revision after counterexamples [13].
For this project, that suggests an evidence record linking each proposed law
to its support, contradictions, revision history, and validation scope. A
model should be allowed to remain unresolved rather than always declare a law.

These papers do not remove our experimental obligations. In particular,
ALDER distinguishes fixed-candidate experiment selection from broader equation
revision, and identifies some unmatched comparisons in its ODE evaluation
[13]. We should make the same distinctions, use equal budgets, and avoid
transferring reported advantages to interacting societies without testing them.

## Knowledge quality and useful decisions

Score predictions before the learner receives the outcome used for an update.
Measure held-out predictive error and proper distributional scores, calibration,
multi-step deterioration, and errors in predicted intervention effects. Measure
learning speed against elapsed ticks, unique observations, communication, and
compute. Sharing can increase evidence per tick; it does not by itself prove a
more efficient learning algorithm.

Parameter recovery is meaningful only on identifiable tasks. Structural
recovery should allow mathematically equivalent expressions and be accompanied
by out-of-distribution intervention tests. Consumption or welfare alone can
miss incorrect models when an easy policy succeeds. Conversely, improved
knowledge may initially cost resources because experiments displace production.

First compare predictors on controlled streams with behavior fixed. Then give
the same planner different learned models and measure actual welfare, shortfall,
harm, and robustness. Frozen, shuffled, and oracle-model controls can separate
benefit from the model, additional memory, or the planner. An oracle model with
the same observation restrictions is different from an oracle with hidden state.

Prevent discovery from becoming recall. Published simulator constants and prior
generated programs already contain domain knowledge. New hidden parameters and
later hidden structural variants should be sampled independently of those
constants. LLM-SRBench makes memorization a concrete benchmarking concern [10].
If conservation or functional families are provided, describe them as prior
knowledge. A conservation-constrained predictor has not discovered conservation.

Mechanistic World Models offers a useful conceptual framing for organizing
reusable explanations [15]. The prospective contribution here would be evidence
about the institutions that produce, test, communicate, and preserve such
knowledge, rather than a claim that adding a predictor establishes intelligence.

## Multiagent learning and collective knowledge

Multiagent world models already have substantial empirical precedent. MAMBA,
MABL, and MAG investigate global information, decentralized execution, and
prediction errors propagating between local models [17–19]. CoDreamer separates
communication for world modeling from communication for decisions [20]. More
recent work tests selective sharing under bandwidth limits [21], while DMAWM
separates local agent representations from a shared environment module [22].
Thus, novelty should come from testing how institutions govern learning in an
interacting resource economy, rather than from adding several world models.

Training access must be explicit. CoDreamer's independent baseline shares
parameters and therefore trains on all agents' experience; its Melting Pot
experiments use cooperative rewards and exclude the social-generalization test
scenarios [20]. Those are legitimate design choices, but they would not test
whether isolated societies independently discover laws. Our private baseline
needs private training data and weights. A pooled reference, a bandwidth-matched
random-sharing baseline, and content-preserving versus content-destroying
communication interventions answer different questions.

Keep opponent behavior separate from physical transitions, following the
distinction made operational by opponent modeling [23]. Factorized latent
models and robustness theory motivate structured representations and
interventional transfer tests [24,25]; neither proves that our coefficients
are identifiable. Change ecological laws with opponents fixed, change opponents
with laws fixed, and then change both. A good learner should localize which
explanation failed rather than label every surprise a new physical law.

Sharing beliefs is not equivalent to sharing independent evidence. Distributed
learning theory makes observation and connectivity assumptions explicit [26],
and decentralized estimation has long studied erroneous reuse of information
[27]. Give observations semantic IDs and track their provenance. Repeated
reports of one patch at one tick are not independent renewal experiments.
Deduplication alone does not remove correlations caused by shared weather or
joint actions. Fuse fresh evidence under an appropriate likelihood instead of
multiplying posteriors containing the same prior and observations.

Evaluate probabilistic forecasts with proper scores [28], and evaluate change
detection using delay and false alarms [29]. Use independent arenas as the
replication unit: one society's experiment can alter what every other society
observes. Distinguish immediate material effects from effects mediated by
others' responses [30]. First compare learners on identical recorded streams;
then test active experimentation and model-assisted decisions. These are our
proposed controls, not established advantages of any society in this repository.

## Annotated primary sources

1. **Chua et al. — PETS, NeurIPS 2018.**
   [Deep Reinforcement Learning in a Handful of Trials using Probabilistic Dynamics Models](https://proceedings.neurips.cc/paper_files/paper/2018/hash/3de568f8597b94bda53149c7d7f5958c-Abstract.html).
   Probabilistic ensembles and trajectory sampling support uncertainty-aware
   control with learned dynamics. Relevant to a compact initial learner and
   planner. Results in control benchmarks do not establish calibrated uncertainty
   under strategic nonstationarity or this observation contract.

2. **Hafner et al. — PlaNet, ICML 2019.**
   [Learning Latent Dynamics for Planning from Pixels](https://proceedings.mlr.press/v97/hafner19a.html).
   Combines deterministic and stochastic latent dynamics with online planning;
   addresses partial observability and multi-step prediction. Supports a belief
   state built from history. Its visual reconstruction machinery is unnecessary
   for the repository's numerical observations.

3. **Hafner et al. — DreamerV3, Nature, 2 April 2025; initial preprint January 2023.**
   [Mastering diverse control tasks through world models](https://www.nature.com/articles/s41586-025-08744-2).
   Demonstrates policy learning through imagined trajectories across diverse
   tasks using one configuration. A substantive neural baseline, not evidence
   that physical equations are recovered. The published workloads and resource
   requirements should not be treated as the minimum viable implementation here.

4. **Hansen, Su & Wang — TD-MPC2, ICLR 2024.**
   [Scalable, Robust World Models for Continuous Control](https://proceedings.iclr.cc/paper_files/paper/2024/hash/cf73d57b6dcda32b293df7c2d5341f49-Abstract-Conference.html).
   Learns an implicit latent model for local trajectory optimization and
   demonstrates broad continuous-control performance. Useful planning reference.
   Its task-oriented representation supplies no direct equation-recovery test;
   adapting the method to our discrete choices and continuous effort is work.

5. **Brunton, Proctor & Kutz — SINDy, PNAS, 2016.**
   [Discovering governing equations from data by sparse identification of nonlinear dynamical systems](https://doi.org/10.1073/pnas.1517384113).
   Selects a sparse set of candidate terms to describe dynamics. Supports an
   interpretable, inexpensive structural baseline. Appropriate coordinates,
   sufficient excitation, and a suitable function library matter; unobserved
   extraction and capped stocks complicate direct application.

6. **Sekar et al. — Plan2Explore, ICML 2020.**
   [Planning to Explore via Self-Supervised World Models](https://proceedings.mlr.press/v119/sekar20a.html).
   Uses imagined ensemble disagreement to guide exploration, followed by
   adaptation to downstream tasks. Supports comparing purposeful exploration
   with passive observation. Disagreement approximates information gain; neither
   it nor prediction error guarantees useful experimentation in every domain.

7. **Wagenmaker & Jamieson — COLT 2020.**
   [Active Learning for Identification of Linear Dynamical Systems](https://proceedings.mlr.press/v125/wagenmaker20a.html).
   Designs inputs to accelerate parameter estimation and provides finite-time
   and asymptotic results. Establishes a rigorous active-identification
   precedent. Its linear-system and input-control assumptions do not describe
   an economy with autonomous competitors and hidden withdrawals.

8. **Tang, Key & Ellis — WorldCoder, NeurIPS 2024; preprint 19 February 2024.**
   [Building World Models by Writing Code and Interacting with the Environment](https://proceedings.neurips.cc/paper_files/paper/2024/hash/820c61a0cd419163ccbd2c33b268816e-Abstract-Conference.html).
   Builds Python world models from interactions and connects them to planning,
   with gridworld and task-planning experiments. Closely matches executable
   inheritance in this project. Its results do not establish that code induction
   resolves hidden-state ambiguity or scales cheaply to this economy.

9. **Shojaee et al. — LLM-SR, ICLR 2025.**
   [Scientific Equation Discovery via Programming with Large Language Models](https://proceedings.iclr.cc/paper_files/paper/2025/hash/28df8e730c054c5331855fd4d5403ba9-Abstract-Conference.html).
   Proposes equation programs and fits their numerical parameters. Supports
   separating structural search from coefficient optimization. The model's
   scientific priors are external knowledge, and the original evaluation uses
   four designed problems; broad discovery claims require additional evidence.

10. **Shojaee et al. — LLM-SRBench, ICML 2025; preprint 14 April, revised 7 June 2025.**
    [A New Benchmark for Scientific Equation Discovery with Large Language Models](https://arxiv.org/abs/2504.10415).
    Uses transformed and synthetic equation problems to reduce trivial
    memorization. Motivates hidden structural variants and explicit controls
    for prior familiarity. Benchmark accuracy remains specific to its equations,
    search spaces, and scoring rules.

11. **Lehrach et al. — preprint, 6 October 2025.**
    [Code World Models for General Game Playing](https://arxiv.org/abs/2510.04542).
    Converts natural-language rules and trajectories into executable models for
    planning, including imperfect-information games. Supports separating model
    construction from action search. Supplied rules mean this is not evidence
    of discovering unknown laws exclusively from interaction.

12. **Abhyankar et al. — LLM-ACES, preprint, 23 June 2026.**
    [Closed-Loop Discovery of Dynamical Systems with LLM-Guided Adaptive Search](https://arxiv.org/abs/2606.25039).
    Couples symbolic hypotheses to disagreement-guided acquisition of informative
    trajectories. Relevant to the active structural-discovery stage. Its ODE
    benchmarks differ from discrete event dynamics, competing policies, and
    strategically filtered reports.

13. **Cao et al. — ALDER, preprint, 27 September 2026.**
    [Discovering the Laws of a World by Acting in It](https://arxiv.org/abs/2609.33728).
    Combines equation proposals, numerical fitting, independent validation,
    and experiments that generate counterexamples. A close methodological
    precedent. The permitted variables and grammar still limit discovery; the
    paper distinguishes controlled selector comparisons from structural revision
    and explicitly notes unmatched ODE comparisons.

14. **Zhang et al. — preprint, 24 July, revised 27 July 2026.**
    [On the Identifiability of Controlled World Models](https://arxiv.org/abs/2607.22430).
    Connects representation and transition identification to predictable-signal
    separation and conditional action variation, with counterfactual error
    consequences. Supports measuring action coverage. Results depend on specified
    Gaussian latent/control assumptions and are not general guarantees for this
    multiagent ecology.

15. **Posner, Lei & Schölkopf — perspective preprint, 14 July, revised 15 July 2026.**
    [From Observation to Insight: Mechanistic World Models and the Quest for Autonomous Discovery](https://arxiv.org/abs/2607.12474).
    Proposes organizing world knowledge around reusable explanatory mechanisms.
    Useful vocabulary for the project's scientific objective. This is a
    conceptual blueprint, not an experimental demonstration that a particular
    architecture outperforms predictive alternatives.

16. **Varıcı et al. — AISTATS 2024; preprint 24 October 2023, revised 14 February 2024.**
    [General Identifiability and Achievability for Causal Representation Learning](https://arxiv.org/abs/2310.15450).
    Establishes identification results using specified hard interventions on
    latent variables. Clarifies why observational fit is insufficient. Ordinary
    member actions do not automatically satisfy the paper's intervention and
    modeling assumptions.

17. **Egorov & Shpilman — MAMBA, AAMAS, 9–13 May 2022.**
    [Scalable Multi-Agent Model-Based Reinforcement Learning](https://ifmas.csc.liv.ac.uk/Proceedings/aamas2022/pdfs/p381.pdf).
    Adapts latent imagination to cooperative multiagent learning and exploits
    shared information in the world model. An empirical foundation for later
    neural comparisons. Shared access and cooperative objectives differ from
    independent societies learning under competing interests.

18. **Venugopal et al. — MABL, AAMAS 2024; preprint 12 April 2023.**
    [Bi-Level Latent-Variable World Model for Sample-Efficient Multi-Agent Reinforcement Learning](https://www.ifaamas.org/Proceedings/aamas2024/pdfs/p1865.pdf).
    A global latent state informs a local latent state during training; agents
    execute using the local level. Evaluates SMAC, Flatland, and MAMuJoCo.
    Establishes a useful information-access comparison, while centralized
    training remains distinct from independent online knowledge acquisition.

19. **Wu et al. — MAG, AAAI 2023; proceedings published 26 June 2023.**
    [Models as Agents: Optimizing Multi-Step Predictions of Interactive Local Models in Model-Based Multi-Agent Reinforcement Learning](https://ojs.aaai.org/index.php/AAAI/article/view/26241).
    Optimizes local models while accounting for errors propagating through
    their interactions across prediction steps; evaluates StarCraft II.
    Motivates testing rollout deterioration in addition to one-step fit.
    Better long-horizon predictions do not independently establish mechanism
    or causal-structure recovery.

20. **Toledo & Prorok — CoDreamer, preprint, 19 June 2024.**
    [Communication-Based Decentralised World Models](https://arxiv.org/abs/2406.13600).
    Uses graph communication separately in world models and actor–critic
    networks, with VMAS and cooperative Melting Pot experiments. Provides
    relevant communication ablations. Parameter sharing and the exclusion of
    Melting Pot's unfamiliar-partner tests limit what these results say about
    independent societies and social generalization.

21. **Zeng & Zhang — RLJ 6:909–922; presented at RLC, 5–9 August 2025.**
    [Efficient Information Sharing for Training Decentralized Multi-Agent World Models](https://rlj.cs.umass.edu/2025/papers/Paper103.html).
    Tests local world models, component-specific experience sharing, and
    selective communication under explicit bandwidth limits. Some restricted
    sharing configurations outperform broader sharing in cooperative tasks.
    Particularly close prior art for bandwidth controls; it does not establish
    institutional discovery of physical laws or robustness to strategic reports.

22. **Xue et al. — DMAWM, ICML, 6–11 July 2026.**
    [Learning Disentangled Multi-Agent World Model for Decentralized Control](https://proceedings.mlr.press/v306/xue26e.html).
    Separates independent agent modules from a shared environment module to
    better align imagination with decentralized execution. Recent empirical
    support for separating representations. A common trained environment model
    is a different information regime from independently learning societies;
    architectural disentanglement alone is not causal identification.

23. **Yu et al. — MBOM, NeurIPS 2022; preprint 4 August 2021.**
    [Model-Based Opponent Modeling](https://proceedings.neurips.cc/paper_files/paper/2022/hash/b528459c99e929718a7d7e1697253d7f-Abstract-Conference.html).
    Uses an environment model to imagine improving opponent policies and mixes
    these hypotheses according to observed behavior. Tests fixed, learning,
    and reasoning opponents. Supports distinct environment and opponent
    components; recursive strategic planning is optional complexity after a
    simpler behavior-prediction baseline.

24. **Liu et al. — IFactor, NeurIPS 2023.**
    [Learning World Models with Identifiable Factorization](https://papers.neurips.cc/paper_files/paper/2023/hash/65496a4902252d301cdf219339bfbf9e-Abstract-Conference.html).
    Separates latent factors by relationships to actions and rewards, with
    block-identifiability results and empirical control studies. Useful
    precedent for explicit factorization. Its assumptions and notion of latent
    identification do not guarantee recovery of ecological coefficients from
    stock observations confounded by hidden extraction.

25. **Richens & Everitt — ICLR 2024; preprint 16 February 2024.**
    [Robust Agents Learn Causal World Models](https://openreview.net/pdf?id=pOoKI3ouv1).
    Connects low regret across a sufficiently rich family of distributional
    shifts to approximate causal knowledge. Motivates held-out intervention
    tests. Strong performance under ordinary seed variation does not meet
    the theorem's premises or certify causal understanding.

26. **Nedić, Olshevsky & Uribe — preprint, 21 August 2015.**
    [Fast Convergence Rates for Distributed Non-Bayesian Learning](https://arxiv.org/abs/1508.05161).
    Gives explicit finite-time concentration results for distributed hypothesis
    learning from conditionally independent observation processes. Supports
    measuring knowledge acquisition rates and topology effects. Independence,
    connectivity, hypothesis adequacy, and stationarity assumptions require
    separate checking in our coupled ecological trajectories.

27. **Bréhard & Krishnamurthy — ICASSP, 15–20 April 2007.**
    [Optimal Data Incest Removal in Bayesian Decentralized Estimation Over a Sensor Network](https://dihana.cps.unizar.es/proceedings/ICASSP/2007/pdfs/0300173.pdf).
    Characterizes how network topology and recycled information affect
    Bayesian fusion, including storage costs of exact correction. Direct
    motivation for provenance and duplicate-evidence tests. Our simpler
    receipt-deduplication protocol is a proposed engineering choice, not an
    implementation of their general graph-based correction algorithm.

28. **Gneiting & Raftery — JASA 102(477):359–378, 2007.**
    [Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).
    Develops distributional scores, including log and continuous ranked
    probability scores, and interval forecast evaluation. Supports measuring
    uncertainty quality rather than coverage alone. The repository's capped
    outcomes contain boundary masses, so the predictive distribution and
    scoring implementation must handle them explicitly.

29. **Adams & MacKay — preprint, 19 October 2007.**
    [Bayesian Online Changepoint Detection](https://arxiv.org/abs/0710.3742).
    Tracks a posterior over elapsed time since the latest change. An
    inspectable baseline for detecting drought or changed mechanisms.
    Its generative assumptions and hazard prior must be declared; detection
    delay without false-alarm rates is an incomplete assessment.

30. **Triantafyllou et al. — ICML, 21–27 July 2024.**
    [Agent-Specific Effects: A Causal Effect Propagation Analysis in Multi-Agent MDPs](https://proceedings.mlr.press/v235/triantafyllou24a.html).
    Formalizes effects of an action that propagate through other agents and
    states conditions for identifying a counterfactual counterpart. Relevant
    when one society's experiment changes others' behavior. Simulator branches
    can measure defined effects, but observational predictive accuracy does not
    itself identify those counterfactuals.
