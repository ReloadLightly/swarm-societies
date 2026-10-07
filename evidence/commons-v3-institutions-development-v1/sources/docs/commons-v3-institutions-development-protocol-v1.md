# Optional-charter development protocol v1

This prospective protocol specifies the first scientific use of the
[political capability contract](commons-v3-institutions-contract-v1.md), after
the completed incentive replay and Stage 2 engineering at `2bf5544`. It is a
small **development comparison of supplied policy bundles**, not qualification,
independent evaluation, optimized governance or evolutionary evidence. Freeze
and push this protocol, the executable design and its full source closure
before recording any listed episode. All earlier banks remain unchanged.

## Question and scope

Can the current optional-charter policies maintain consumption under the
declared mixture of competent restrained foragers and stubborn aggressors,
relative to the same navigation with decentralized paid reporting and local
storage? What costs, formation failures, unused monitoring and outsider effects
explain the resulting development contrasts?

The reference population already approaches full consumption under universal
restraint. Neither improved consumption nor formation is required. Institutions
cannot fine nonmembers, and stubborn agents never join or respond to threats.
Their presence tests resilience and externalities; it cannot demonstrate
deterrence of those agents. The nonstubborn response rule can alter a harvest
request in view of a declared collateral risk, but retains competent restrained
navigation rather than an artificially weakened aggressive baseline. As a
result, the quota may rarely bind. Preserve that outcome.

## Finite panel

| Factor | Prospective values |
| --- | --- |
| Navigation | Frozen fixed-floor anchor: buffer 2, floor 0.5, net-yield route; selected: buffer 4, floor 0.5, nearest route |
| Carried capacity | 8 and 80 |
| Stubborn agents | 0 or 6 of 24; separate all-24-stubborn anchors |
| Seeds | 93001, 93002, 93003, 93004; disjoint from preceding v3 panels and reserved tipping seeds |
| Horizon | 256 ticks; final 64 ticks reported separately |
| Physics | Unchanged v3 logistic law, need 1.2, initial patch stock 40; all remaining `Config` defaults |
| Political capabilities | Unchanged `PoliticalConfig` defaults, including 80 total custody units per site in every arm |
| Charter | Quota 2, bond 1, suggested dues 0.1, fine 0.5; no parameter search |

Four arms × two backgrounds × two capacities × two mixtures × four seeds
give **128 episodes**. The all-stubborn anchor runs once per background,
capacity and seed, adding **16 episodes**. Total: **144 episodes, 36,864
physical ticks, 884,736 individual decisions**, before exact replay. Seeds
are environmental replication units; repeated backgrounds/arms are paired
conditions, not extra independent replications. Cohort assignment is a fixed
SHA-256 ordering of `(protocol version, seed, individual ID)`, shared across
arms, capacities and navigation backgrounds. No agents are relocated or assigned
initial membership. Initial organizations, treasuries, bonds and caches are empty.

## Arms and shared opportunities

1. `frozen`: competent local forager, with no reports or political actions.
2. `decentralized`: the same forager plus paid local reporting and conservative
   personal cache management, without membership.
3. `charter_unmonitored`: the same reporting/cache controller with optional
   founding/entry/exit and the declared charter, but no monitoring or settlement
   actions. Anticipated enforcement is zero and agents withhold dues for unused
   operations. Entry bonds and proposal costs remain real.
4. `charter_enforced`: the same optional-charter policy purchases monitoring and
   settlement when affordable, voluntarily funds that activity and uses the
   fixed anticipated monitoring probability 0.5 in its supplied response rule.

All arms execute the same political/physical engine and begin with the same
material endowment and observation rules. Stubborn agents use the supplied
aggressive forager for that background, with no reports, caches, membership
or political actions, identically across arms. The all-stubborn anchor uses
those same policies. Nonstubborn agents keep `aggressive=False` in every arm.

The three active development arms share the reporting implementation and
period of four ticks. Personal caches hold at most two ticks of need per
individual/site. Deposit only when stationary and carried inventory exceeds
six ticks of need plus the physical reserve and planned message charge; bound
the deposit to that surplus and the personal cache limit. Retrieve locally when
carried inventory is below two ticks of need. Retrieval occurs after physical
consumption, so it cannot repair the current tick's shortfall. Political intents
can displace cache actions: this is an accounted opportunity cost, not extra
action capacity. Only legal local boards/observations inform these decisions.

Enforcement uses the lowest-ID currently co-located member as the supplied
monitor selector. The anticipated threat requires another locally eligible
monitor and sufficient observed opening treasury. The probability is a fixed
heuristic, not an estimated detection rate or private optimum. Actual evidence,
settlement, collateral exhaustion and costs remain observable outcomes.
The supplied harvest rule estimates attainable extraction as local stock divided
by visible co-located agents. It can choose the quota even without a fine when
that estimate gives zero extra gain. Under proportional contention this estimate
need not equal the eventual share; the response is not an optimized best reply.

**Fairness boundary:** formal charter metadata/boards and binding escrow have
no full nonmembership bilateral-contract analogue in this implementation.
The decentralized arm has the same generic material world, cache and paid
report opportunities, but is only one declared coordination policy. This panel
cannot identify the effect of formal organization alone, establish dominance
over all decentralized agreements, or separate coercive enforcement from its
supplied secure-custody assumptions. The enforcement-on/off contrast changes
both behavior and resource charges; it is not a cost-matched mechanism
intervention. Any stronger later comparison requires its own declared controls.

## Outcomes, custody and inference

Primary development outcomes are realized population consumption divided by
need, all ticks and final 64 ticks, and consumption for the original eligible
and stubborn cohorts. Cohorts are assigned before treatment and retain all
exiters and nonjoiners. Empty cohorts return null, never zero. Report current
member/nonmember outcomes separately as selection-prone diagnostics.

Retain per-agent consumption, shortfall, extraction, movement/message/harvest
costs, private political fees, actor-attributed treasury spending, collateral
forfeiture, custody transfers and opening/closing membership. Include stock
and depletion series, formation and active-institution counts, membership time,
entry/refusal/exit events, actual opening-charter violations, paid observations,
settlement attempts/success/failure, and costs. Treasury spending is a pooled
cost attributed to its operator for traceability; it is not that operator's
private payment. Do not subtract already paid costs again from consumption.
Depleted-patch fractions use stock strictly below 10% of patch capacity.

Terminal ownership is declared **book accounting**, with no forced liquidation
or additional consumption ticks. For each individual, retain carried inventory,
owned local caches, active collateral, released/mature refund claims and an
equal share of active treasury among current members. These allocations exactly
exhaust material custody once; abandoned/released claims retain their owners.
Sum the components for a book-wealth diagnostic. Report consumption plus
weights **0, 0.05 and 0.2** times terminal carried inventory separately from the
same weights times book wealth, normalized by horizon and need. The original
weights and old private-utility results are unchanged. Book ownership is not
accessible or guaranteed consumption: resources may be remote or still subject
to a pending collateral liability. Do not introduce an outcome-fitted discount
or treat the assigned value as an endogenous fitness benefit.

For each background/capacity/mixture, report every seed value and the mean and
min/max of the four paired contrasts: decentralized−frozen,
unmonitored−decentralized, enforced−decentralized and enforced−unmonitored.
Report corresponding absolute outcomes and anchors. Do not present confidence
intervals, qualification pass/fail claims, optimized selection or pooled
independent sample sizes. There is **no adaptive extension or winning-policy
selection** in this protocol. The complete results inform the next design;
any later change requires a new version and independent evaluation.

## Execution, recovery and preservation

Use the separately versioned development policy, measurement and runner modules.
Only audited built-in policy kinds execute. The bank records source copies and
hashes, the exact design, initial/midpoint/final complete checkpoints, committed
actions/intents and measured per-tick records. Midpoint continuation restores
policy memories and recomputes future decisions, including pending political
state. It does not substitute stored actions for restored policies.

Recovery verifies completed episode files and their source/design identity,
preserves them and continues only missing episodes. Never overwrite conflicting
or completed evidence. Exact semantic replay must regenerate every episode,
saved summary and checkpoint continuation; aggregation also reconstructs from
the raw measurement records. Unexpected engineering failure halts the run and
preserves partial work; scientific losses or absence of institutions do not.

Publish raw evidence in a new identified archive, verify public/offline
restoration, and retain compact results, source closure, replay receipts and
recorded-data Chromatic Field figures in Git. Inspect SVG/PDF/PNG exports and
record source/output hashes. This authorizes no model calls, evolutionary runs,
new qualification samples or execution of the separate tipping protocol.
