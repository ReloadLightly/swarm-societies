# Next step: can learned laws improve an allocation decision?

**Status:** implemented and evaluated on 6 October 2026. The
[completed study](world-model-decision-v1.md) records the frozen design, results
and limitations; this document preserves the preceding implementation rationale.

Prospective implementation plan, 6 October 2026. This is neither a frozen
experimental protocol nor a results report. It proposes the smallest next
control after private learning and truthful information sharing: a versioned
stepwise ecology and one consequential allocation decision using a fixed
planner. No new evolutionary search or model-generation allowance is required.

## 1. Separate learning, decisions and experimentation

Parameter learning asks whether beliefs predict renewal and recover supplied
coefficients. The next control asks whether those beliefs improve a material
decision. Active experimental design instead chooses actions to acquire useful
information; structural discovery changes the proposed equation. Combining all
four now would make an improvement difficult to explain.

Uncertainty-aware model rollouts have a useful precedent in
[PETS, Chua et al., NeurIPS 2018](https://proceedings.neurips.cc/paper_files/paper/2018/hash/3de568f8597b94bda53149c7d7f5958c-Abstract.html),
which combines probabilistic learned dynamics with sampled uncertainty
propagation. Our proposed control uses the existing mechanistic posterior,
not a neural ensemble, and makes no claim that PETS results transfer here.

## 2. Minimum transition interface

Create a new module, provisionally `ecology_stepwise_v1.py`; preserve the
[frozen engine](../swarm_societies/ecology_world_model_v1.py).
Expose reset, strict phase transitions, legal observations, completed receipts,
and privileged snapshot/restore. A possible interface is `begin_tick()`,
`set_institution_decisions(...)`, `member_observations()`, and
`finish_tick(member_actions)`, with a compatibility episode wrapper.

Preserve the existing causal order: depreciation, renewal, institution
decisions, simultaneous member intentions, action resolution, allocation and
consumption. Institution decisions occur before current tax receipts establish
the actual budget. Current growth measurements remain available at the
declared reporting phase; refactoring must not give a planner early access.
Restore must include policy memories, pending communication, phase, accumulated
metrics and all random-generator state, including already drawn randomness.

Acceptance requires exact legacy material trajectories, RNG behavior, actor
payloads, accounting and receipts under the wrapper, including nondefault
planted laws. Pausing/restoring at legal phase boundaries must reproduce an
uninterrupted run. Invalid phase transitions and future observations must fail.

## 3. A single-decision comparison

Begin each fresh arena with the same fixed-policy warmup and a fixed
communication condition. At one declared checkpoint, a focal institution
chooses a public-investment fraction from a small menu; tax, defense and
redistribution rules otherwise remain fixed. After this allocation, all
policies return to their prescribed schedule. Rotate the focal society within
the same arena without treating rotations as independent worlds.

Compare the identical planner supplied with: the learned posterior, the frozen
prior, or the true coefficients under the same legal observations. Fix its
objective, action menu, planning samples, horizon, tie-breaking and nuisance
forecasts. The known-law condition tests whether coefficient knowledge helps
this planner; it is not a full-state oracle or a guaranteed optimal controller.

The planner needs a separate predictive implementation initialized only from
authorized measurements and posterior samples. Other physical mechanisms can
remain supplied knowledge. State assumptions about opponents and future
external infrastructure explicitly. Forecast the eventual institutional budget;
do not substitute its realized post-action value. The known-law condition uses
the same observation restrictions and approximations.

## 4. Development gate: the decision must depend on knowledge

Investment occurs after current renewal and harvesting. From the implemented
coefficients, one invested unit adds `rho × b × eta / members` to next-tick
uncapped home-patch growth. With `rho=.96`, `eta=.125`, four members and the
current task range `b∈[.7,2.7]`, that is only **0.021–0.081 resource units**.
This is a physical marginal response, not an economic return guarantee.

A one-step welfare planner could therefore always redistribute. Test delayed
returns over a development horizon such as 32 ticks, while checking capacity,
harvest demand and consumption shortfall. Before freezing evaluation, require
multiple valid states/laws where the same legal-state planner changes action
ranking when supplied different coefficients, with gaps exceeding declared
planning Monte Carlo tolerance. Also check that known-law choices can change
realized action value in evaluator branches. If either gate fails, report an
uninformative decision task and revise development conditions; do not infer
that learning is useless or tune against the final panel.

## 5. Protected branches and empirical acceptance

Evaluator branches may clone complete simulator state to estimate each menu
action's consequences. Planners receive neither those snapshots nor branch
outcomes, hidden parameters outside the labeled reference, weather or RNG state.
Commit forecasts and choices before evaluation. Paired branch randomness
reduces comparison noise; it does not give actors foresight. Verify that all
branches leave live worlds, beliefs, queues and random streams unchanged.

Freeze fresh arena seeds, warmup, decision timing, planning budget and objective
after development. Report focal welfare, unmet consumption, terminal wealth,
investment, effects on other societies and predictive error separately.
Action-value regret must name its finite menu and evaluation horizon. Bootstrap
independent shared-law arenas; members, rotations and stochastic branches are
nested observations. Retain failed planning and invalid forecasts explicitly.
Publish recorded-data Chromatic Field figures, tables, captions, inspected
SVG/PDF/PNG exports, and source/output hashes.

## 6. Active design follows this control

[Plan2Explore, Sekar et al., ICML 2020](https://proceedings.mlr.press/v119/sekar20a.html)
plans for future novelty during exploration before downstream task adaptation.
[Wagenmaker and Jamieson, COLT 2020](https://proceedings.mlr.press/v125/wagenmaker20a.html)
analyze adaptive inputs for identifying linear dynamical systems under complete
input control. These distinguish knowledge-seeking from immediate utility;
neither supplies guarantees for autonomous interacting societies here.

A later protocol can compare fixed excitation, random interventions and
information-directed actions at matched resource and opportunity budgets.
Record executed investment and forgone consumption. Capacity censoring,
correlated local/external infrastructure and uncontrollable neighbours remain
identification hazards. Preserve the existing conditional-model calibration
caveat; do not turn posterior confidence into an unquestioned exploration rule.
