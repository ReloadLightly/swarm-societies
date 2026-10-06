# Learnable world model: implementation proposal

Original implementation plan, 6 October 2026. A first stationary identification
control is now implemented and evaluated; see [world model v1](world-model-v1.md)
for completed scope and results. Broader milestones below remain a plan. Stage 1 estimates
unknown parameters in a declared family; Stage 2 will compare and discover
rule structures. Neither stage changes frozen v1/v2 evidence or authorizes
another model-driven evolution campaign.

## What the current interface permits

The existing engine draws weather and execution order, decays infrastructure,
regenerates patches, calls institutions, gathers simultaneous member intentions,
resolves actions, then allocates institutional funds and consumes resources.
The relevant implementation is
[`ecology_consumption_v2.py`](../swarm_societies/ecology_consumption_v2.py#L103).

Members observe their home patch and one rotating other patch before actions,
their own wealth, productivity and infrastructure, the tax rate, institutional
messages, and their previous intended action. Institutions observe local
wealth, treasury, infrastructure, and previous decision-time reports. Neither
receives realized action receipts. Institutions do not directly see patches or
defense. Reports can describe intentions or measurements; they are not audited
outcomes. See the
[observation construction](../swarm_societies/ecology_consumption_v2.py#L118).

Consequently, a wealth difference mixes harvesting, costs, tax, raids,
redistribution and consumption. A pre-action patch-stock difference mixes
regeneration, clipping and everybody's extraction. A model can predict these
differences without identifying their causes. Current replays contain more
information than actors receive and must never become a silent training input.

Memory starts empty each episode, while executable programs persist between
evolutionary updates. The restricted
[`CandidateProgram`](../swarm_societies/candidate.py#L48) permits bounded Python
and JSON state, not imports or arbitrary numerical libraries. Keep that frozen
interface intact; use new modules for numerical learners and experiment control.

## Stage 1 world and information contract

Create `ecology_world_model_v1.py`, initially preserving v2 material dynamics
at default parameters. Name its public law-family specification separately from
the private realized `WorldParameters`. All societies inhabit the same sampled
world. Shared physical parameters must not be sampled independently for each
society; patch-specific weather and declared local heterogeneity remain distinct.

The initial unknown parameter vector is regeneration baseline `r`, local
infrastructure yield `b`, spillover yield `g`, infrastructure survival `rho`,
construction efficiency `eta`, harvest productivity `h`, and effort cost `c`.
Capacity, allocation semantics and action definitions are initially public.
Do not attempt every coefficient, capacity and hidden regime simultaneously.

With `I_t` denoting infrastructure after decay, `P_end,t−1` previous terminal
patch stock, and `U_t` realized investment, the declared equations are:

```
growth_t = min(max(0, K − P_end,t−1),
               r × weather_t × regime_t + b × I_t + g × mean_other_I_t)
I_t+1 = rho × (I_t + eta × U_t / members)
harvest = min(stock_available_at_resolution, h × productivity × effort)
effort_cost = 0 if action == rest else min(wealth_available_at_resolution, c × effort)
```

These reproduce the current coefficients with `rho=.96`, `eta=1/8`, `h=2.4`
and `c=.08`, alongside current regeneration settings. The regime multiplier is
an exogenous state, not another society's behavior. Begin with stationary worlds;
introduce unknown change times only after stationary recovery works.

Add three explicitly separate data products:

1. **Private action receipt:** actor identity, tick, requested and resolved action,
   actual yield, paid cost and tax, transfers received/given, consumption and raid
   loss. A denial or supply limit must be distinguishable from intended effort.
   Receipts describe the actor's own transactions, never an opponent's private
   state, RNG draw or future outcome.
2. **Patch measurement:** patch, tick, phase, measured stock and infrastructure,
   sensor identity and measurement precision. Add a terminal patch-stock reading
   so the next pre-action reading can separate growth from extraction. End-of-tick
   stocks are observations, not action receipts. Preserve the home-plus-rotating-
   neighbour footprint, extending its measured fields explicitly.
3. **Institutional account receipt:** realized local tax/contribution totals,
   budget, investment and redistribution. This permits estimation of construction
   efficiency without pretending the institution knew its eventual budget when
   it announced allocation fractions.

Weather stays hidden and contributes process uncertainty. Other societies'
unobserved infrastructure remains latent; it cannot be filled from the evaluator.
In the three-society setting, different members' rotating neighbour readings can
jointly cover infrastructure that no single member observes that tick. A separate
full-observation audit mode establishes that the learner can recover identifiable
parameters before distributed sensing is tested.

Record phase explicitly: `after_decay`, `before_actions`, `after_actions`, and
`after_allocation`. Infrastructure used in regeneration differs from its value
after investment. A terminal reading paired with a later observation must retain
its actual age. Existing decision-time reporting adds another delay because an
action's receipt did not exist when its report was written. The new protocol
should provide a bounded post-outcome reporting phase: members may communicate
completed observations at tick end; institutions receive them next tick. This is
an intentional versioned timing change, not a reinterpretation of old reports.

Exact receipts make harvest and effort coefficients easy: one affordable,
uncensored action can identify them. Use these as plumbing controls. The research
task is regeneration, infrastructure, spillovers and later regime inference under
incomplete, delayed, correlated evidence.

## Learner and runtime interfaces

Suggested module boundaries:

| Module | Responsibility |
| --- | --- |
| `world_model_v1/schema.py` | Versioned observations, receipts, provenance, predictions and snapshots |
| `world_model_v1/learner.py` | Fixed numerical baseline learners and serialization |
| `world_model_v1/runtime.py` | Private/shared learner ownership, messages, update scheduling and quotas |
| `world_model_v1/evaluate.py` | Protected law truths, held-out queries, scoring and case generation |
| `world_model_v1/study.py` | Frozen designs, rotations, paired conditions and summaries |
| `visualize_world_model_v1.py` | Recorded-data Chromatic Field figures |

Use `reset(prior, observation_spec, learner_seed)`, `predict(query)`,
`update(observed_transition)`, `snapshot()` and `restore(snapshot)` for learners.
Prediction is read-only. Each transition includes an observation identity,
source, channel, timestamp, phase, availability mask and provenance. Each forecast
records target, horizon, conditioning information, distribution or predictive
samples, and the model snapshot hash used to generate it.

In the first sharing experiment, institutions choose which authenticated
observations to forward; the runtime checks ownership and preserves their
original event IDs. This isolates evidence selection from factual accuracy.
Free-form claims, corrupted measurements and strategic false reports are later,
explicit treatments; they must not acquire the status of sensor receipts merely
by declaring a source ID. Count serialization and provenance in the byte budget.

Runtime owns separate instances for every member and institution. Numerical
weights are learner state; candidate private/shared JSON remains policy state.
Actor code receives only a bounded belief summary and its authorized observations.
Initially keep model architecture fixed and test information institutions, rather
than confounding model architecture, governance and policy search at once.

A passive observer treatment must not feed beliefs to decisions. An active
treatment exposes the same summary schema and permits a declared exploration
policy. Missing models, invalid predictions, resource overruns and failures stay
in the results; they cannot silently fall back to an oracle.

The runtime must distinguish observation ownership from logs. Trusted audit
records may contain true parameters, global states, interventions and evaluator
seeds. Actor payloads contain none of those fields. “Ephemeral” means a held-out
probe branch is discarded without updating live worlds, learners, reports, RNG
streams or evolutionary selection state. It does not make privileged branch
data safe to give a learner.

## Baselines and identifiable targets

Start with a frozen prior predictor, an independent member learner, a society
learner using delivered reports, and a centralized learner receiving the union
of those same legal observations. Add a known-parameter model with the same
observation limits and a privileged full-state model as separate references.
Neither is a guaranteed control optimum or a fair governance comparator.
Use identical architectures and priors across ordinary pooling conditions.

The primary renewal learner is a bounded sequential Monte Carlo posterior over
the physical coefficients. Use the declared weather distribution, capacity
point masses and measurement precision in its likelihood; integrate missing
inputs only under an explicit state model. Log effective sample size,
resampling/rejuvenation and failed updates. Particle count, public priors and
compute limits are fixed before comparisons. Collapsed or invalid particles
must not masquerade as successful identification.

Use unconstrained normal–inverse-gamma Bayesian linear regression on
`[1, own_infrastructure, mean_other_infrastructure]` only as an approximate
sanity baseline on fully observed controls designed so caps cannot bind over
the entire public parameter/weather support. Its Gaussian noise differs from
bounded weather whose variance scales with baseline regeneration; check
calibration. Ordinary conjugacy does not survive hard parameter constraints.

Saturated stocks are censored observations. Include their correct likelihood;
do not regress clipped growth as unconstrained flow or simply remove observed
saturation, which selects outcomes and can bias inference. Parameter bounds
must come from the frozen public prior, not true sampled coefficients.

Missing neighbour features require a reduced-information predictive model or
explicit marginalization. A first implementation may defer full-law updates
when required inputs are unavailable, but must label resulting parameter claims
unidentifiable and include a strong local prediction baseline. Pooled recovery
in an intentionally complementary-sensor task demonstrates the value of combined
information; it does not by itself demonstrate a superior learning algorithm.

For infrastructure, regress `I_t+1` on `I_t` and realized investment per member:
the coefficients identify `rho` and `rho × eta`, provided excitation separates
the two. Constant investment or correlated infrastructure trajectories can make
the design poorly conditioned. Log rank, condition measures and parameter
posterior correlation. Hold unknown-defense raid laws for a later instrumented
task; current receipt data cannot identify their full mechanism.

Pool evidence increments, not independently trained posterior precisions with
their prior counted repeatedly. Deduplicate identical patch readings and evidence
recirculated in broadcasts. Members sharing one patch/weather shock are not
independent measurements merely because their reports have different authors.

## Lifecycle, learning speed and evaluation

The default learning unit is a complete world episode: reset beliefs to the
same prior; learn from its observations; discard state at reset. Repeated worlds
with persistent memory constitute a separately named transfer/cultural-memory
treatment. Evolution may later change executable learning or reporting rules,
but its search state and budget remain separate from online parameter learning.
Final evaluation cannot warm-start from development trajectories.

At each step, commit a prediction before revealing its target, score it when
the target becomes available, then update. Snapshot after a fixed number of
completed transitions, for example 0, 4, 8, 16, 32, 64, 128 and 256. This proposed
schedule requires longer new episodes than some v2 cases. It is not a completed
experiment or a power calculation.

Score both the observed trajectory and a frozen, held-out query bank. Share the
query design across arenas, instantiated under each arena's own hidden law
draw with independent starts and RNG. All societies in that arena face the same
bank under the declared observation restrictions and fixed context length.
Different-law queries are a separate transfer treatment. Include
one-step prediction, open-loop multi-step prediction, and interventions on
investment, harvesting and neighbour behavior. Probe-only outcomes never train
the model. Report oracle expected responses or repeated-simulation distributions
when randomness prevents a single deterministic answer.

Primary learning quality should be held-out predictive loss over experience,
with parameter error restricted to identifiable tasks. Also report calibration,
interval width, Brier score for binary outcomes, counterfactual error and decision
regret. Use CRPS for numerical forecasts with a fixed number of equally weighted
predictive samples per condition, and check Monte Carlo sensitivity on development
data. A separate evaluation RNG preserves live-state identity. Negative log
likelihood must respect the mixed observation measure, including capacity point
masses; arbitrary Gaussian or zero-variance densities produce misleading scores.

Measure speed in world ticks, unique environmental observations, communicated
bytes and CPU time. Report area under the predictive-loss curve and observations
to a preregistered accuracy threshold. Threshold failures are right-censored,
not dropped. A full-observation learner's lower error and an information-limited
learner's attainable conditional error answer different questions.

Compare algorithms first on identical recorded evidence, then compare active
data collection. Only the second measures whether a society chooses informative
interventions. Pair worlds and random draws across conditions, rotate society
IDs and sensor assignments, and separate changes in physical laws from changes
in opponent policy. Replication units are independent world runs or independent
evolutionary runs, depending on the claim; societies, ticks and probe branches
within a shared world are not independent replications.

## Implementation order and acceptance criteria

1. **Instrumented engine and data boundary.** Default material trajectories match
   v2 under legacy policies; accounting and common random numbers still hold.
   Tests reject future receipts, private parameter leakage, wrong phase pairing,
   malformed data and cross-society model-state sharing. New observations do not
   silently enter old evaluator feedback.
2. **Stationary identification.** Recover trivial receipt laws and known planted
   growth/infrastructure coefficients under informative interventions. Include
   saturation, zero effort, insufficient funds, no investment, collinear features
   and absent neighbour measurements. Identifiability failures must be visible.
3. **Distributed learning.** Compare isolated, legitimate pooled and union-data
   learners. Test duplicate reports, prior double-counting, delayed evidence,
   observation-budget parity and intervention on report content. Verify that
   removing informative content changes learning without changing simulator truth.
4. **Adaptation and useful decisions.** Add hidden regime shifts, separately
   changing opponents, active probing and model-guided choices. Measure knowledge,
   welfare, harm and exploration costs separately. Confirm snapshot probes do not
   mutate the live experiment and reset semantics prevent train/test carryover.
5. **Structure discovery.** Introduce held-out functional families only after
   parameter-learning controls pass. Version the admissible hypothesis language,
   complexity budget, and interventional tests; fitting known coefficients cannot
   count as discovering a previously unknown equation.

Every completed experiment writes portable input/output tables, source hashes,
learner snapshots and a manifest. Chromatic Field exports should include learning
curves, law-recovery/identifiability panels, calibration plots, and aligned
change-point responses; information pooling and communication costs deserve a
paired comparison. Keep cobalt, magenta and orange tied to society identity,
use markers or labels for conditions, preserve SVG/PDF/PNG, inspect rendered
PNGs, and show failures. No spatial swarm imagery should imply unimplemented
movement. These figures are required outputs of future experiments, not
illustrative claims that learning has already occurred.
