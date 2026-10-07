# Ecological qualification of the frozen physical commons: protocol v1

This prospective study follows the completed local-navigation development
bank. It preserves the physical engine, both frozen forager controls, all older
protocols and evidence. There are no institutions, memberships, model calls,
evolutionary runs or new parameter selection. A failed or unresolved gate is
a valid result. This protocol, its executable registry and copied source
closure must be committed and pushed before any qualification episode runs.
The separate incentive protocol is frozen at the same checkpoint, before
ecological outcomes can influence its cases, thresholds or controls.

## Fixed design and legal information

Use the unchanged 24-agent, 16-site, 12×12 physical engine with radius-one
sensing, carrying capacity 80, initial inventory 2, initial site stock/capacity
40, movement cost 0.02, harvest cost 0.02 and stock-dependent renewal. Cross
renewal rates 0.12/0.24/0.36 with needs 0.8/1.2/1.6. Every case lasts **512
ticks**. Seeds **64001–64016** are disjoint from all earlier development and
from the separate incentive seeds. Reuse each seed across the nine cells and
both policies for paired descriptions; those repetitions are not independent
replicates. The independent sampling units for intervals are 16 seed realizations.

Both controllers use only the original legal local observations and their
own memory, with all navigation constants unchanged:

| Control | Frozen parameters |
| --- | --- |
| Fixed floor | Buffer 2, voluntary floor 0.5, travel-adjusted-yield routing |
| Selected | Buffer 4, voluntary floor 0.5, nearest-site routing |

The selected policy is the winner of the completed, separate navigation
tuning bank. Bind its selection record SHA-256
`4665d982a65e08ac65dc0244b341a0cf519da2f417964b65414d4e271369cadc`.
No qualification result can select another candidate. The floor is an
individual request rule, not an enforced aggregate quota. Global observations,
analytic bounds and evaluator diagnostics never enter the policy packet.

There are **144 configurations, 288 episodes, 147,456 physical ticks and
3,538,944 individual decisions**, excluding exact replays. The first 256 ticks
of a 512-tick episode may be summarized descriptively; they are a dependent
prefix, not a second episode or another replicate. Policy observations do not
contain the episode horizon. The primary gate uses the complete 512-tick record.

## Ecological gates

For each of the nine cells and each frozen control, compute five scalar
observations per seed:

| Endpoint | Passing direction and margin |
| --- | --- |
| Mean consumption / need | Lower confidence bound ≥ 0.95 |
| Final-quarter consumption / need | Lower confidence bound ≥ 0.95 |
| (Fourth-quarter minus third-quarter consumption) / need | Lower confidence bound ≥ −0.02 |
| Mean final-quarter total ecological stock / capacity | Lower confidence bound ≥ 0.20 |
| Final-quarter depleted-site-time fraction | Upper confidence bound ≤ 0.10 |

A depleted site has stock strictly below 0.10 of its capacity after renewal.
These are operational **finite-horizon** viability and nondecline criteria;
they do not prove indefinite sustainability, optimality or comprehensive
exploration. A control passes a cell only if every criterion passes. It fails
if any criterion fails, otherwise it is unresolved. For a lower-bound
criterion, a confidence interval wholly below the margin fails; an interval
straddling the margin is unresolved. Reverse the directions for upper-bound
criteria. Exact numerical comparisons determine every gate; no tolerance
changes a verdict.

The ecology report identifies all grid-adjacent pairs containing the reference
(rate 0.24, need 1.2) in which **both controls** pass in **both cells**.
Adjacency means one horizontal or vertical step in the declared 3×3 grid.
Retain all nine cells; do not replace failed cases, lower thresholds or choose
a background independently for each favorable cell. This is the ecological
component of the later combined gate, not incentive qualification by itself.

## Statistical contract shared with the incentive protocol

Use seed-level Student-t intervals with 15 degrees of freedom. The fixed
Bonferroni union contains **194 scalar intervals**: 90 ecological criteria
(9 cells × 2 controls × 5 endpoints), 54 primary incentive criteria, and 50
reference robustness criteria. At family alpha 0.05, use the frozen two-sided
critical value **4.750567324005865**; ordinary descriptive 95% intervals use
**2.131449545559776**. Both values were computed with SciPy 1.18.1 before
execution and are literals in the registry; runtime quantile drift cannot
change a gate. For observations x, the interval is mean(x) ± critical ×
sample-standard-deviation(x)/sqrt(16). Zero empirical variance gives a zero
width interval and does not establish universal invariance.

Coverage is **approximate and model-based**, relying on the seed-level
sampling distribution; Bonferroni does not remove that assumption. Reusing
seeds across endpoints or cells does not invalidate its union accounting.
No interval treats agents, ticks or mixtures as independent replicates.
Descriptive intervals outside the fixed family do not authorize new gates.
Preserve complete seed-level values so skew, outliers and zero variance remain
visible. No optional stopping, adaptive seed expansion or retrospective
family restriction is permitted.

## Physical feasibility and controller limitations

Record the separately derived conservative consumption certificates for each
configuration at horizons 256 and 512, plus the final 128-tick window, at full
need and the 0.95 viability target. The relaxation ignores access, contention,
movement and storage restrictions where that can only increase attainable
consumption. It includes extraction losses, available initial resources,
renewal's stock-dependent production ceiling, bounded weather and the fact
that final-tick renewal cannot fund final-tick consumption. Late-window
certificates permit full inventories and site stocks at the window boundary.
Exact rational quantities and an explicit numerical envelope govern their
comparison; see the separately frozen feasibility derivation.

Classify evidence without treating a permissive upper bound as a solution:

- **Certified insufficient:** the conservative upper bound is below the
  stated consumption target. Report the exact target and horizon.
- **Witnessed viable:** at least one legal frozen controller passes the
  operational ecological criteria; name it. The stricter qualification pair
  still requires both controls.
- **Feasibility unresolved:** the bound permits the target but neither
  controller demonstrates it. This does not prove genuine infeasibility or
  establish how much a better local policy could recover.

The map need not fill every proposed ecological category. In particular,
neither high total stock nor a permissive bound proves abundant accessible
supply, and local-controller failure does not establish an impossible regime.
No global-information planner or mathematically optimal policy is claimed.

## Recording, recovery and preservation

Save agent endpoints, quarter summaries, per-tick agent consumption, shortfall,
inventory, positions and known-site counts, ecological trajectories, material
costs and cohort totals. Record longest latter-half runs with at least half
the sites depleted; a run lasting at least H/8 ticks is a descriptive persistent
depletion diagnostic, not an alternative criterion that can rescue a failed
consumption gate. Reference frames and identical-action physical snapshot
continuation are recorded. Policy-memory checkpoint recovery is not claimed.

Only audited built-in policies execute. Check material residuals at the frozen
relative tolerance 1e-9, record actual extraction waste, reject material
per-tick waste above 1e-9 and reject unaffordable known-site returns. Tiny
floating residuals are retained. Conditions share keyed weather. Freeze sources,
designs and all inputs; exact semantic replay must reproduce case records and
aggregates. Unexpected engineering failures halt completion and preserve the
bank, rather than dropping cases. Interrupted execution verifies and preserves
complete records. A completed or failed bank cannot be overwritten.

Push verified checkpoints promptly. Publish raw cases in a new versioned
archive with verified public/offline restoration, compact summaries and hashes
in Git, and inspected Chromatic Field SVG/PDF/PNG figures with complete tables.
Older banks, including failed development controls, remain untouched.
