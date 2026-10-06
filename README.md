# Swarm Societies: Coevolving Institutions and Learning Shared World Dynamics

**Living research report · 6 October 2026**

[Code and reproduction](#6-reproducibility) ·
[Current results](#4-experiments-and-results) ·
[Research roadmap](docs/research-roadmap.md) ·
[World-model proposal](docs/world-model-proposal.md) ·
[Active work record](PROGRESS.md)

## Abstract

Swarm Societies studies how interacting societies allocate resources, govern
information, and acquire knowledge of a shared environment. The platform
separates executable member policies, institutional programs, authoritative
material dynamics, and independent evaluation. We report an initial multilevel
evolution experiment, a consumption-focused matched search pilot, a factorial
intervention on saved programs, and a new numerical world-model implementation.
The evolutionary pilot produced a small consumption-welfare advantage for
institutional coevolution alongside greater harm to neighbouring societies.
The program transplant diagnostic identified a member-dependent institutional
effect on harm; beneficial welfare complementarity remained unresolved.
The world-model feature estimates hidden renewal coefficients online using
weather-aware Bayesian particles and explicit observation contracts. Across
24 independent arenas, private learners reduced final predictive CRPS from
**0.9422 to 0.2496**; pooling three times the evidence improved the learning
trajectory further. This instrumented control fixes policies and supplies the
equation family, establishing measurement before institutional knowledge
sharing, active experimentation, and rule discovery. We distinguish predictive
accuracy, identifiable physical knowledge, useful control, and evolutionary
improvement throughout.

## 1. Introduction

A society can prosper without understanding its environment, and it can learn
useful facts without distributing their benefits fairly. Our research question
is therefore broader than whether many agents achieve a high shared reward:
**which institutions help interacting societies acquire accurate, transferable
knowledge and use it effectively, at what cost to members and neighbours?**

The repository provides a small economic ecology in which those questions can
be tested separately. Members pursue private utility. Institutions govern
taxation, investment, redistribution, permissions, and reporting. Societies
compete for renewable resources and can assist or harm one another. Executable
member and institutional programs can evolve independently, while a trusted
simulator determines every material consequence.

The current world contains three societies and shared resource patches. It
does not implement spatial motion, physical proximity, demographic group
reproduction, or a decentralized peer network. Here, “swarm societies” names
the research program; central institutional hubs and fixed membership describe
the implemented substrate.

The immediate progression is **parameter learning and information governance →
active experimentation → structural discovery**. Parameter learning is now an
executable feature. The later stages remain research objectives, rather than
capabilities inferred from memory fields or cooperative-looking behavior.

## 2. Related work and positioning

SwarmWorld motivates the separation of local decisions from authoritative
consequences and reusable artifacts [1]. This repository uses an independently
authored compact simulator; it is not a SwarmWorld fork or a reproduction of
its material-physics results. The AI Economist provides prior art for joint
adaptation of individual behavior and institutional economic rules [2]. Our
evolution experiments use the actual upstream ShinkaEvolve engine [3], with
separate ecological acceptance criteria for members and institutions.

Probabilistic ensembles and recurrent world models show how learned dynamics
can support prediction and planning [4,5]. Their control results do not by
themselves establish recovery of interpretable laws. Multiagent world-model
research highlights the problems of hidden interactions, shared representations,
and communication budgets [6]. These motivate explicit knowledge ownership and
information controls here.

Sparse equation discovery, executable world models, and active law-discovery
systems supply complementary methods for the next stage [7–9]. A useful
prospective contribution is a benchmark of **how institutions produce, test,
communicate, and retain causal knowledge in a shared resource world**. The
present implementation establishes part of that benchmark; it does not claim
priority for world models, multiagent learning, or hierarchical governance.
The [30-source review](docs/world-model-literature.md) distinguishes verified
conference/journal work from recent preprints and records applicability limits.

## 3. Environment and methods

### 3.1 Resource ecology and incentives

Each society has members with personal wealth and productivity, a treasury,
infrastructure, defense, institutional memory, and delayed member reports.
Members can harvest, contribute, share, guard, rest, or raid. Institutions set
taxes, expenditure fractions, reserves, redistribution weights, raid permission,
and broadcasts. Private and institutional state reset between episodes;
inherited program source persists across evolutionary updates.

Patches renew before actions, all intentions are collected before resolution,
and a seeded initiative order determines access to scarce stock. Weather,
conflict randomness, and order are drawn independently of chosen actions to
support matched comparisons. A ledger enforces

$$
L_{\mathrm{final}}=L_{\mathrm{initial}}+R-C-A-D-V-F,
$$

where liquid resources include patches, wealth, and treasuries; the right-hand
terms are renewal, consumption, action costs, raid destruction, infrastructure
investment, and defense spending. Transfers do not create resources.

Private utility is cumulative consumption plus $0.2$ times terminal wealth.
The consumption-v2 society objective is

$$
W=\frac{\sum_t(C_t-0.5S_t)}{MT}
 =0.85-1.5\frac{\sum_t S_t}{MT},
$$

with $M$ members, $T$ ticks, and unmet consumption $S_t$. Thus welfare and
shortfall are algebraically linked. The first experiment additionally rewarded
infrastructure directly; its scores must not be compared numerically with v2
as if the objectives were identical. Taxes, voluntary transfers, private
utility, inequality, and outward harm remain separate measurements.
[Full environment specification](docs/model.md).

### 3.2 Program evolution and causal interventions

ShinkaEvolve proposes restricted Python programs. A scheduled member replacement
must improve that member's utility; an institution replacement must improve
its society's welfare. Each acceptance comparison holds environmental draws,
partners, and opponents fixed. Later accepted replacements change the context
for subsequent proposals. Source inheritance, ecological incumbency, and
evaluation provenance are recorded separately.

The verified inference route is ChatGPT-authenticated Codex, `gpt-6-astra`,
`xhigh`, `fast`, through the pinned upstream Shinka Headless adapter. Previous
allowances are exhausted. Local evaluation, numerical learning, and figure
generation do not extend those allowances; another model-driven evolution
campaign requires a new declared budget. [Route and evidence](docs/subscription-route.md).

Frozen-program transplants independently exchange member and institutional
components. They identify effects conditional on the saved lineage and chosen
environment panel. They are not independent replications of evolutionary
search, and a whole-program intervention does not isolate one permission,
memory field, or reporting rule.

### 3.3 Learnable renewal model

The separately versioned
[world-model ecology](swarm_societies/ecology_world_model_v1.py) exposes explicit
measurements while preserving the older simulators. The first learner estimates
three hidden coefficients: baseline renewal $r$, local infrastructure return
$b$, and spillover return $g$. The supplied mechanism is

$$
X_{s,t}=\min\!\left(K-P^{\mathrm{end}}_{s,t-1},\;
r\omega_{s,t}+bI_{s,t}+g\overline I_{-s,t}\right),
\qquad Y_{s,t}=X_{s,t}+\epsilon_{s,t},
$$

where $I$ is infrastructure after depreciation,
$\omega\sim\mathcal U(0.85,1.15)$ is hidden weather, and
$\epsilon\sim\mathcal N(0,0.05^2)$ is independent measurement noise added
after capacity clipping. Noisy readings can be slightly negative or above
headroom; the underlying material growth remains bounded.

[RenewalSMC](swarm_societies/world_model_v1/learner.py) uses a bounded uniform
prior, 1,024 parameter particles, and sequential likelihood updates. Resampling
below half the particle count is followed by four Metropolis rejuvenation
steps targeting the complete accepted evidence history. The likelihood
integrates hidden weather and the capacity point mass; saturated observations
are retained. Future forecasts use a separate RNG and do not mutate learning
state. Snapshots include posterior particles, accepted evidence, diagnostics,
and RNG state.

| Coefficient | Public uniform prior | Evaluation law distribution |
| --- | --- | --- |
| Baseline renewal $r$ | $[2,8]$ | $[2.4,6.8]$ |
| Local infrastructure return $b$ | $[0.5,3]$ | $[0.7,2.7]$ |
| External spillover $g$ | $[0,0.8]$ | $[0.05,0.7]$ |

Evaluation ranges are a fixed task distribution, not information supplied to
the learner. Every society in an arena faces the same sampled physical laws.

This is **parameter identification in a supplied equation**. It does not
discover the equation, the observation model, or conservation. The present
experiment grants full infrastructure features through free audit sensors.
Each private society learner receives its own patch's renewal measurements;
a pooled reference receives all three patches. This instrumentation is richer
than the legacy member API and is explicitly a control, not evidence that
unmodified actors could infer these laws from stock differences alone.

### 3.4 Evaluation and replication

The renewal study compares a frozen prior, private learners, and a pooled
reference on 24 independently sampled law/environment arenas, each lasting
128 ticks with three interacting societies and four members per society.
Fixed policies vary investment by role and time; learned beliefs do not change
actions. The pooled reference receives three times as many unique observations
per tick. Its advantage therefore measures access to evidence, not algorithmic
superiority or successful institutional governance.

At seven checkpoints, each model predicts 64 common queries generated under
its arena's own hidden law with independent weather and measurement noise.
The primary endpoint uses 32 queries guaranteed uncapped across the entire
public prior support. The other 32 are capacity controls. Primary learning
quality is CRPS integrated over ticks and divided by the horizon; terminal
CRPS, parameter error, 90% interval coverage and width are secondary. CRPS
scores equally weighted empirical forecasts with 512 samples [10]. Query
outcomes never update the learner.

Uncertainty intervals resample whole arenas. Societies, ticks, repeated probe
queries, and pooled references copied across society rows are dependent
observations. Evolutionary comparisons instead require independent evolutionary
run pairs. These are different replication units.

## 4. Experiments and results

| Study | Independent search runs | Evaluation scale | Main interpretation |
| --- | ---: | --- | --- |
| First multilevel experiment | 1 | 540 fresh rollouts | Infrastructure reward raised welfare without improving consumption resilience |
| Consumption-v2 | 1 matched pair: 1 run per arm | 648 drought/no-drought rollouts | Small consumption advantage with greater external harm |
| Program transplants | 0 new searches; saved coevolution lineage | 864 rollouts | Institutional harm depends on the member program background |
| World-model-v1 | 0 searches | 24 independent law/environment arenas | Stationary parameter-learning control; fixed policies and free audit sensors |

### 4.1 Initial evolution: distinguish score gains from consumption

The first 60-minute search retained three member and three institutional
replacements. Descendants' post-drought welfare rose from **0.8610 to 0.9229**.
The gain decomposed into **+0.06679** from the direct infrastructure reward
and **−0.00490** from the consumption/shortfall term. Cumulative post-drought
shortfall increased from **0.770 to 1.162**, and member utility fell **9.65%**.
These outcomes motivated removal of the infrastructure bonus.

The [archived first-study report](docs/first-study-report.md) preserves the
complete results, lineage descriptions, execution accounting, figures, source
attribution, and historical reproduction commands. Its historical status
statements are not the current project status.

### 4.2 Consumption-focused matched pilot

Each arm received 30 minutes of search from the same initial population.
Fresh cases varied environment, drought timing, episode length, opponent panel,
and focal society; each drought case had a matched no-drought counterpart.

| Population | Consumption welfare ↑ | Unmet need/member/tick ↓ | Outward harm/tick ↓ | Private utility/tick ↑ |
| --- | ---: | ---: | ---: | ---: |
| Initial | 0.843162 | 0.004559 | 0.619992 | 0.931941 |
| Evolved members, fixed institutions | 0.846405 | 0.002396 | 0.332363 | 0.978720 |
| Member–institution coevolution | 0.847238 | 0.001841 | 0.549101 | 0.961051 |

Coevolution improved welfare by **0.000833** over the fixed-institution arm,
with **23.2% less unmet consumption**, **65.2% more outward harm**, and **1.8%
lower private utility**. One paired pilot cannot establish a reliable advantage
for the search procedure. The schedule ended before members could evolve again
under their changed institutions.

![Consumption welfare and separate private/external tradeoffs](figures/consumption-v2/outcome-tradeoffs.png)

*Figure 1. Recorded fresh-case means from the consumption pilot. Welfare and
shortfall represent the same primitive consumption outcome; private utility
and harm expose distinct tradeoffs. [Captions, data and exports](figures/consumption-v2/README.md).*

### 4.3 Frozen-program transplants

Crossing original/evolved members and institutions on a new environmental
panel yielded welfare **0.844263** for the original combination,
**0.845106** for evolved members alone, **0.845648** for evolved institutions
alone, and **0.846926** for both. The additive welfare interaction was
**+0.000434**, with an environmental cluster interval of
**[−0.000550, +0.001612]**. Positive welfare complementarity remains unresolved.

Swapping evolved institutions onto evolved members increased outward harm by
**0.076462 units/tick**, interval **[0.041531, 0.113561]**. The same swap onto
original members added exactly zero harm. The extra harm was concentrated in
society 1. This identifies a conditional effect of complete institutional
programs, not its internal cause. [Study and portable evidence](docs/mechanism-study.md).

![Institutional harm effects depend on member programs](figures/mechanism-v1/institution-harm-effects.png)

*Figure 2. Institutional transplant effects by society and member background.
Points show conditional environmental variation within one lineage, not
independent search replications. [Figure provenance](figures/mechanism-v1/README.md).*

### 4.4 Learning unknown renewal coefficients

The completed study contains **24 independent arenas**, **9,216 unique
environmental observations**, and **18,432 learner updates** across private
and pooled conditions. No update failed. The experiment used no evolutionary
inference. The following means and 95% whole-arena bootstrap intervals come
from the [recorded summary](evidence/world-model-v1/summary.json).

| Condition | Observations/model at tick 128 | Time-averaged CRPS ↓ [95% interval] | Final CRPS ↓ | Final 90% predictive coverage |
| --- | ---: | ---: | ---: | ---: |
| Frozen prior | 0 | 0.9422 [0.7683, 1.1577] | 0.9422 | 94.4% |
| Private society learner | 128 | 0.3088 [0.2844, 0.3340] | 0.2496 | 89.0% |
| Pooled reference | 384 | 0.2703 [0.2454, 0.2967] | 0.2481 | 89.1% |

Private learning substantially improved prediction over the frozen prior.
Pooling lowered time-averaged CRPS by **0.038445**, paired interval
**[0.030612, 0.047006]** for the improvement, or **12.5%** relative to private
learning. Its terminal advantage was much smaller: **0.001595**, paired
interval **[0.000590, 0.002651]**. The principal difference is earlier useful
prediction with more evidence per tick; equal-evidence efficiency has not
been established.

![Recorded predictive learning curves for the three societies](figures/world-model-v1/learning-curves.png)

*Figure 3. Common-probe CRPS by completed tick and society. Lines distinguish
conditions; society colors remain fixed. Bands resample independent arenas.
Prior and pooled references repeat across panels for comparison, not as
additional replicates. The primary probe subset excludes capacity-dominated
queries. [Data, captions and vector exports](figures/world-model-v1/README.md).*

Mean normalized parameter error fell from **0.2319** under the prior to
**0.0405** privately and **0.0203** with pooling. This metric averages each
model's root-mean-square coefficient error after scaling each coefficient by
its public prior width; it is not an equation-discovery score. Separate
coefficient trajectories remain necessary because accurate aggregate forecasts
can conceal a weakly identified spillover coefficient.

![Recovery of baseline renewal, local return and external spillover](figures/world-model-v1/parameter-recovery.png)

*Figure 4. Mean absolute coefficient error by society and checkpoint, in each
coefficient's own units. Columns use different scales. Hidden simulator truth
is used by the evaluator only, never as learner input.*

| Parameter | Private mean absolute error | Pooled mean absolute error | Private 90% parameter-interval coverage | Pooled 90% parameter-interval coverage |
| --- | ---: | ---: | ---: | ---: |
| Baseline renewal $r$ | 0.04557 | 0.02359 | 87.5% | 91.7% |
| Local return $b$ | 0.03247 | 0.01561 | 93.1% | 95.8% |
| Spillover $g$ | 0.05367 | 0.02725 | 83.3% | **75.0%** |

Parameter uncertainty needs further work. The pooled spillover interval
contained the true coefficient in only **18 of 24 arenas**, despite lower
point-estimate error. Good predictive coverage does not establish calibrated
parameter beliefs. Private coverage averages 72 society models nested within
24 arenas; pooled coverage uses 24 models, not their repeated plotting rows.
Finite-particle accuracy and weak excitation of particular coefficients are
possible explanations to test, not established causes. The evaluation panel
has not been reused to tune away this result.

![Parameter interval coverage and width](figures/world-model-v1/parameter-uncertainty.png)

*Figure 5. Coverage and width of 90% parameter credible intervals, distinct
from predictive intervals for future outcomes. The spillover result motivates
further calibration tests. Intervals resample whole arenas.*

Final predictive interval widths were **6.398** resource units for the prior,
**1.319** privately, and **1.309** with pooling. Learned intervals retained
approximately nominal 90% coverage while becoming much narrower. This is
empirical calibration on the declared stationary task distribution, not a
guarantee under hidden features or changed mechanisms. The
[calibration and endpoint panels](figures/world-model-v1/README.md),
[full study report](docs/world-model-v1.md), and
[frozen design](evidence/world-model-v1/design.json) retain the complete
comparison and scope.

## 5. Discussion, limitations, and next experiments

The experiments support a disciplined separation of outcomes. A reward function
can favor infrastructure accumulation while consumption worsens. Institutional
changes can improve local consumption while increasing harm. A learned model
can predict accurately without identifying every coefficient, especially when
infrastructure features are correlated or growth is consistently capped.

The first numerical learner addresses the measurement problem under explicit
instrumentation. It does not yet establish collective intelligence, learned
planning, autonomous experimentation, equation discovery, evolved reporting
institutions, or decentralized knowledge formation. Pooled evidence is a
reference condition, with additional data and no communication price. Posterior
intervals are numerical approximations whose empirical calibration must be
reported, not assumed.

The next experiments will first test parameter calibration and compute
sensitivity on new arenas, then reduce sensor access, introduce bounded and delayed
reports, compare evidence-selection rules, and hold the learner fixed while
varying information governance. Equal-time and equal-evidence comparisons
answer different questions. Later experiments will independently change
physical laws, opponent policies, and report reliability to test whether a
society revises the correct explanation.

Stage 2 will first compare supplied mechanism families, then permit terms,
interactions, and branches to change within a declared expression grammar.
That transition separates model selection from structural discovery. Active
experimentation and fixed-planner interventions will test whether improved
knowledge changes actual welfare and harm. Any model-driven program search
will receive a separately specified budget.

The economic substrate itself remains limited: fixed membership, central
institutions, no spatial movement, no death or migration, and many regimes
near the consumption ceiling. Results about evolutionary search remain based
on individual pilot lineages. The [roadmap](docs/research-roadmap.md) prioritizes
scarcity maps, targeted mechanism interventions, cross-play, invasion, and
independent search replications alongside the new learning program.

## 6. Reproducibility

Use Python 3.13 to match the recorded environment. The current package includes
the numerical learner and its dependencies; the historical requirements lock
belongs to the first experiment and is retained unchanged. The new
[world-model environment](requirements-world-model-v1.txt) pins the versions
used for numerical inference, plotting and tests.

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements-world-model-v1.txt -e '.[test]'
.venv/bin/python -m pytest -q
```

Audit the completed world-model evidence and regenerate its figures:

```bash
.venv/bin/python scripts/run_world_model_study.py verify
.venv/bin/python scripts/visualize_world_model_study.py
```

Reproduce the same deterministic case bank in a new directory, without model
generation or evolutionary search:

```bash
.venv/bin/python scripts/run_world_model_study.py prepare --output runs/world-model-reproduction
.venv/bin/python scripts/run_world_model_study.py run --output runs/world-model-reproduction
.venv/bin/python scripts/run_world_model_study.py verify --output runs/world-model-reproduction
```

Numerical results are deterministic under the recorded software environment;
CPU measurements and timestamps depend on the machine. Existing completed
studies are not overwritten. The current suite passes **90 tests and 14
subtests**, including exact legacy trajectory preservation, likelihood checks,
planted and confounded parameter controls, deduplication, snapshot restoration,
and forecast isolation.

Existing evidence and figures can be checked locally without evolutionary
inference:

```bash
.venv/bin/python scripts/verify_evidence.py --require-final
.venv/bin/python scripts/verify_mechanism_evidence.py
.venv/bin/python -m swarm_societies.visualize_consumption
.venv/bin/python scripts/visualize_mechanism_study.py
```

Evidence includes frozen designs, exact program sources, data tables, accounting,
and source/output hashes. The world-model study additionally records noisy
measurements, forecasts, parameter estimates, learner snapshots, and computation.
Every empirical figure follows [Chromatic Field v1](docs/visual-reference.md):
warm paper, stable cobalt/magenta/orange society identities, explicit condition
markers, and inspected SVG/PDF/PNG exports. Visuals represent recorded data;
design illustrations are labeled separately.

The [first-study archive](docs/first-study-report.md),
[consumption protocol](docs/protocol-consumption-v2.md),
[mechanism diagnostic](docs/mechanism-study.md), and
[world-model implementation plan](docs/world-model-implementation-plan.md)
retain detailed methods. [PROGRESS.md](PROGRESS.md) records active work and
verification status. Upstream Shinka is required only for its evolutionary
route, not for fitting the numerical world model or rendering recorded results.

## 7. References

1. Pal, Wang & Buehler (2026). [SwarmWorld: Stigmergic technological evolution in societies of language-model agents](https://arxiv.org/abs/2608.26081). Preprint. [Repository integration decision](docs/upstream.md).
2. Zheng et al. (2022). [The AI Economist: Taxation policy design via two-level deep multiagent reinforcement learning](https://www.science.org/doi/10.1126/sciadv.abk2607). *Science Advances*.
3. Lange, Imajuku & Cetin (2025/2026). [ShinkaEvolve](https://arxiv.org/abs/2509.19349). ICLR 2026. Actual engine pinned to [revision 9912af1](https://github.com/SakanaAI/ShinkaEvolve/tree/9912af12d423504b8d580f4179fd15f5f88b8c50).
4. Chua et al. (2018). [Deep Reinforcement Learning in a Handful of Trials using Probabilistic Dynamics Models](https://proceedings.neurips.cc/paper_files/paper/2018/hash/3de568f8597b94bda53149c7d7f5958c-Abstract.html). NeurIPS.
5. Hafner et al. (2019). [Learning Latent Dynamics for Planning from Pixels](https://proceedings.mlr.press/v97/hafner19a.html). ICML.
6. Zeng & Zhang (2025). [Efficient Information Sharing for Training Decentralized Multi-Agent World Models](https://rlj.cs.umass.edu/2025/papers/Paper103.html). *Reinforcement Learning Journal*.
7. Brunton, Proctor & Kutz (2016). [Discovering governing equations from data by sparse identification of nonlinear dynamical systems](https://doi.org/10.1073/pnas.1517384113). *PNAS*.
8. Tang, Key & Ellis (2024). [WorldCoder: Building World Models by Writing Code and Interacting with the Environment](https://proceedings.neurips.cc/paper_files/paper/2024/hash/820c61a0cd419163ccbd2c33b268816e-Abstract-Conference.html). NeurIPS.
9. Cao et al. (2026). [ALDER: Discovering the Laws of a World by Acting in It](https://arxiv.org/abs/2609.33728). September preprint.
10. Gneiting & Raftery (2007). [Strictly Proper Scoring Rules, Prediction, and Estimation](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf). *JASA*.

The [full research review](docs/world-model-literature.md) annotates 30 primary
sources. Visual conventions derive from the read-only
[actir-backprop-neat reference](https://github.com/ReloadLightly/actir-backprop-neat/tree/9472743f1cb7ea12eafcf489126b1a43b8f5735f);
its numerical results are not reused.
