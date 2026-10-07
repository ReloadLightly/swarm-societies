# Swarm Societies working conventions

Read `PROGRESS.md` for the current experimental state,
`docs/world-model-calibration-v1.md` for the independent calibration audit and
implementation decision, and `docs/world-model-v1.md` for the implemented
stationary identification control.
The completed private-belief sharing stage is documented in
`docs/world-model-sharing-v1.md`. The completed stepwise allocation control is
documented in `docs/world-model-decision-v1.md`; its earlier design rationale
remains in `docs/world-model-decision-plan.md`.
The completed costed experiment-selection control is documented in
`docs/world-model-experiment-v1.md`.
The current priority is the scientific redesign in `docs/commons-v3-plan.md`,
following `docs/research-review-2026-10-07.md`. The user specified mobile
individuals in an anarchic international system: institutions can emerge,
be absent, change and disappear, with no supranational government. Qualify the
ecology, incentives and strong baselines before further experimental model
spending. Preserve parameter learning and rule discovery as tools and later
research stages; their earlier design remains in `docs/world-model-proposal.md`.
The broader research program remains in `docs/research-roadmap.md`.

Foundation repairs are documented in `docs/foundation-repairs-v1.md`.
Use `scripts/verify_calibration_portable_v1.py` for supplemental calibration
verification; keep the frozen original verifier unchanged. Its float tolerance
is limited to enumerated reference diagnostics and never changes qualification
or retry decisions. Use `swarm_societies.execution_v1` or
`python -m swarm_societies.run_bounded_v1` for new/untrusted policy execution,
including fresh evaluation, replay and checkpoint continuation. Direct frozen
APIs remain for audited trusted policies. The bounded historical search adapter
is `scripts/evaluate_search_bounded_v1.py`; it preserves the old acceptance rule
for parity and does not authorize a new campaign.

Stage 0 data publication/restoration and README consolidation are complete.
See `docs/evidence-archives-v1.md` and `evidence/data-packaging-v1/` for the
verified public archives, clean-checkout restoration and offline checks.
Restore full banks with `python3 scripts/restore_evidence_v1.py --study all`
before semantic replay or figure regeneration. Default tests retain their
small fixtures and require no evidence download. Keep restored bulk files
ignored; new evidence versions need new archive identities. Hashes detect
changed assets, but GitHub hosting is not administratively immutable.
The complete earlier report remains in
`docs/living-research-report-2026-10-07.md`; `docs/study-index.md` indexes it.

Stage 1's physical foundation is implemented in `swarm_societies/commons_v3/`;
read `docs/commons-v3-foundation-v1.md` and both separately frozen development
protocols. The engine has mobile individuals, local information, stock-dependent
renewal, accounting and physical snapshots, with no institutions, memberships
or supranational authority. Optional political transitions remain unimplemented.
The old world-model learner has not been transferred to this different renewal
law. V3 runners currently execute only audited built-in policies; the existing
bounded candidate adapters support the historical engines, not v3 yet.

Both 56-configuration/224-episode development banks are complete. Preserve
`evidence/commons-v3-foundation-v1/`, whose policy revealed a numerical
return-fuel trap, and `evidence/commons-v3-foundation-v2/`, which applies a
prospective fuel margin with unchanged physics, cases and scientific thresholds.
V2 records zero unaffordable known-return violations. This fixes one diagnostic
policy failure; it does not establish strong navigation or scientific qualification.
The same four seeds were reused after inspecting v1, so neither bank is an
untouched qualification test. No experimental model calls or search runs occurred.

At the v2 reference cell, restraint consumes 1.200000 versus greedy 0.229769
per agent-tick. Focal greedy replacement gains zero consumption; utility gain
0.010685 at wealth weight 0.05 is entirely terminal inventory. Peer consumption
falls 0.100769. Carrying capacity 8 reduces that utility gain to 0.000252 and
eliminates peer consumption losses. Greedy terminal ecological stock is 66.70%
of capacity: distinguish local depletion, access failures and unused resources
from collapse of the entire commons. These are descriptive four-seed results,
not confidence intervals or cross-border institutional outcomes.

Next: stronger local baselines, beginning with need-targeted harvesting and
modest reserves under the same capacity 80, followed by separate ecological and
incentive qualification. Keep institutions, their lifecycle and paid enforcement
as later work. Do not start model spending or tune utility weights to manufacture
a dilemma; preserve all adverse development outcomes and version future changes.

The exploratory reconstructed greedy baseline reproduces the external review's
mechanism table: focal welfare 0.848654 and private utility 1.038674 exceed the
saved coevolved means 0.846926 and 0.965109. This does not establish universal
dominance or zero external cost: other societies' mean welfare is 0.001030 lower.
Evidence is separate in `evidence/baseline-review-v1/`; preserve the original
mechanism study. No new evolution or model calls were used. Distinguish
raid-victim losses from ecological externalities and bundle substitutions from
mechanism-specific interventions.

The calibration audit supports retaining 1,024 particles/four rejuvenation sweeps
as the working default. Higher compute is a sensitivity setting, not an adopted
default. All 192 batch references qualified; close numerical agreement does not
establish universal calibration. Preserve the shared borderline likelihood-CDF
departure and the distinction between conditional ecological beliefs and a full
joint model. Private member beliefs and bounded, provenance-preserving reports
are now implemented under fixed truthful rules, deduplication, delay and the
instrumented observation contract. The 24-arena sharing study found a small
0.68% time-average prediction benefit at matched bytes; the terminal contrast
remains unresolved, and equal-evidence scores favor isolated/redundant members.
Do not infer improved inference efficiency or decisions from sharing alone.
The separate 24-arena decision control found learned-minus-prior utility of
+0.021110 [0.009014, 0.033678] per member, with 85.7% of the gain attributable
to weighted terminal wealth and additional consumption in only one arena.
The known-law reference retains planner/state approximations. Do not claim
general consumption-welfare improvement, evolved governance or an optimal
controller. The separate 24-arena costed experiment control found no clear
active-minus-random advantage in posterior-update value: −0.000969
[−0.005181, 0.002920] per member. A small total-utility advantage is already
present with frozen coefficients. Active selected Early in 71/72 states;
the Fixed Split control does not establish an advantage over all fixed timing
schedules. Repayment relative to zero-investment redistribution remains
unresolved. A later supplied-mechanism-family comparison remains distinct from
structural discovery, after the new ecology is qualified. Keep hidden external features,
confidence-based selection and adaptive sequences of experiments as separately
controlled stages.

Sharing evidence is complete; do not restart it. For future interrupted sharing
reproductions, use `scripts/resume_world_model_sharing.py`: the frozen original
`run` command rewrites every incomplete study's case files. Recovery verifies and
preserves complete arenas, archives partial work, and reports resumed-only time.
Decision development and evaluation evidence are also complete; do not restart
them. `scripts/run_world_model_decision.py verify` refits and replays all saved
cases and the copied development proof. Its `run` command recovers incomplete
reproductions by verifying saved cases and refuses to overwrite a completed bank.
Costed experiment development and evaluation evidence are also complete; do not
restart them. `scripts/run_world_model_experiment.py verify --workers 2` refits
and replays all saved cases and the copied development proof. Its recovery
preserves verified cases and refuses to overwrite a completed bank. Aggregation
checks one full case at a time before retaining scalar projections to limit RAM.

Keep the README as an informative living research paper: abstract, methods,
actual experimental results, tables, figures, limitations and reproduction.
The user requested an arXiv-paper style, not a claim of arXiv publication.
Update evidence-based statistics and preserve earlier detailed study records
as new stages arrive.

The user wants experiment visualizations in **Chromatic Field v1** throughout
the project. Follow `docs/visual-reference.md` and reuse the tokens and export
helpers in `swarm_societies/visualize.py`. New experimental results should come
with recorded-data figures, captions, and source/output hashes; inspect the
rendered images. Preserve SVG, PDF, and PNG exports. Society colors identify
societies consistently; distinguish experimental conditions with labels or
markers. Do not draw spatial dynamics the simulator does not implement.

Preserve frozen simulators, protocols, and published evidence. Put new
diagnostics and protocol changes in separately versioned files/directories.
Keep exploratory analyses distinct from prospective tests. Report the number
of independent evolutionary runs separately from environment cases and
rollouts. Mechanistic claims require interventions; code complexity, memory
fields, and compulsory tax pooling are not evidence of collective intelligence.

Existing search allowances are exhausted. Local analysis and evaluation of
saved programs do not consume a new inference budget. A new model-driven
evolution campaign needs a separately specified budget; never silently extend
an old allowance. Preserve the established inference route unless the user
changes it.
