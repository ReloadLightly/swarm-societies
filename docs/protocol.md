# Frozen protocol: first experimental increment

Written before inspecting fresh evaluation results. Changes to this protocol require a new version and a new held-out panel.

## Question and experimental unit

Can source-code variation in member policies and executable resource-allocation institutions change collective performance and response to a resource disturbance? This increment is a single exploratory evolutionary run. An independent evolutionary run, not a rollout or a society, is the replication unit for claims about the search procedure.

Default ecology: three societies, four members each. Membership is explicit and fixed during an episode. Fresh private member state and shared institutional memory are initialized on every rollout. Episode learning is state modification; evolution is persistent program replacement between rollouts. The public simulator and candidate API are documented in `model.md`.

## Variation, inheritance, and selection

Actual upstream ShinkaEvolve proposes unrestricted source edits within the permitted Python language. The two executable functions are the member-policy and institutional units. Safety restrictions on imports, reflection, execution time, and output size protect the evaluator; seed institutions are not an enumerated strategy catalogue.

Candidate evaluations alternate member and institutional updates. Member proposals occupy one member slot and compete against that slot's incumbent on mean individual utility. Institutional proposals replace one society's institution and compete on that society's mean welfare. Other member and institutional programs are frozen for both sides of each paired comparison. Society and member slots rotate deterministically. A candidate is retained in the ecological population only if its paired mean improvement is strictly positive (tolerance 1e-9). No fresh-case result affects selection. Candidates that fail to execute are invalid, not zero-fitness discoveries.

Inheritance preserves exact source files, full-program hashes, component AST hashes, ecological predecessor IDs, and (from the Shinka database) the proposal's source-parent ID. A displaced ecological incumbent is not necessarily the proposal's code parent. Shared/private episode state is never inherited. Shinka search islands are archive partitions; simulated societies are interacting ecological actors. This run uses one search island.

Other populations change after accepted updates; therefore later fitness depends on changing collaborators and rivals. The design implements within-society policy coevolution, institution–member coevolution, and competitive/cooperative intersociety coevolution when reciprocal updates actually occur. Cooperative actions alone are not evidence of cooperative coevolution. If there are no accepted updates, none of these evolutionary dynamics has been demonstrated.

Shinka's archive score is normalized gain against the contemporaneous incumbent, `1 + (candidate - incumbent) / max(1, abs(incumbent))`. Scores from different ecological contexts are proposal heuristics, not a stationary performance ranking. Ecological replacement always uses the paired raw objective. Stored outcomes include both raw scores and the population snapshot. The final ecological population is selected by this rule; no retrospective best-on-test selection is permitted.

## Budget, initial population, and references

The cumulative active search wall-clock budget is 3,600 seconds, resumable from saved accounting and upstream databases. Subscription inference is the only permitted route. No paid model, embedding, judging, or auxiliary inference fallback is allowed. One inference and one evaluator job run at a time initially; local timing and peak memory measurements are recorded before launch. A route failure is a blocker, not permission to substitute another search algorithm.

The initial ecology uses `initial.py`, `cooperative.py`, and `selfish.py`, one program per society with four copies of its member policy. The fixed reference uses the cooperative institution in every society while keeping the initial member-policy population. It is an executable memory-sharing and redistribution reference, not an inactive no-op. The final descendant is the final ecological population, if any accepted changes exist. A crossed intervention attaches final member policies to initial institutions and initial member policies to final institutions when descendants are available; these are diagnostic interventions, not independent search replications.

## Search and fresh cases

Search uses environmental seeds 101, 202, and 303, with all incumbents and challengers evaluated against identical partner/opponent snapshots. The held-out panel is generated and stored by the evaluation harness outside candidate observations. It uses 12 distinct fresh environment seeds, each crossed with three frozen external opponent panels (initial, cooperative, and selfish). Focal society identity rotates across all three society slots; the focal society's members and institution come from the tested population. Nonfocal societies use the designated opponent panel. Exactly the same cases and snapshots are used for every treatment. These are generalization cases, not 108 independent evolutionary runs.

Report paired mean differences and descriptive uncertainty across environment-seed clusters when applicable. Within-case member outcomes, per-society welfare, pre/post-disturbance welfare, within-society cooperation/conflict, between-society cooperation/conflict, and external harm remain separate. Disturbance timing and effects are simulator-owned and never provided as future observations. No descendants means the table explicitly reports their absence rather than a fabricated comparison.

## Recorded evidence and interpretation

Record unique evaluated programs, valid/invalid evaluator jobs, accepted member/institution replacements, completed Shinka generations, exact changed components, elapsed time, token usage if exposed, and resource measurements. Preserve search-vs-fresh labels on all data and plots. Plot the observed sequence; do not interpolate missing generations or imply progress when execution is blocked. Export lineage graphs with distinct proposal ancestry and ecological replacement where available. Replay material flows from recorded simulator events. Flat or negative outcomes are results.

The evaluator, simulator, protocol, and protected cases are not editable by candidates. This is a constrained research language boundary, not a claim that Python AST filtering is a general hostile-code sandbox. Reproduction should run untrusted external candidates in an OS sandbox as well.
