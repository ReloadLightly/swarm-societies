# Swarm Societies working conventions

Read `PROGRESS.md` for the current experimental state,
`docs/world-model-calibration-v1.md` for the independent calibration audit and
implementation decision, and `docs/world-model-v1.md` for the implemented
stationary identification control.
The completed private-belief sharing stage is documented in
`docs/world-model-sharing-v1.md`. The completed stepwise allocation control is
documented in `docs/world-model-decision-v1.md`; its earlier design rationale
remains in `docs/world-model-decision-plan.md`.
The user's current priority remains parameter learning followed by rule
discovery; `docs/world-model-proposal.md` describes the staged design and
`docs/research-roadmap.md` preserves the broader research program.

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
controller. Next: design a costed active-experimentation control, separating
information value from direct material effects and matching fixed/random
intervention budgets. Keep hidden external features, confidence-based selection
and structural discovery as separately controlled stages.

Sharing evidence is complete; do not restart it. For future interrupted sharing
reproductions, use `scripts/resume_world_model_sharing.py`: the frozen original
`run` command rewrites every incomplete study's case files. Recovery verifies and
preserves complete arenas, archives partial work, and reports resumed-only time.
Decision development and evaluation evidence are also complete; do not restart
them. `scripts/run_world_model_decision.py verify` refits and replays all saved
cases and the copied development proof. Its `run` command recovers incomplete
reproductions by verifying saved cases and refuses to overwrite a completed bank.

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
