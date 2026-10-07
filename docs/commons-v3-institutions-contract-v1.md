# Optional local institutions: capability contract v1

This is Stage 2's first engineering contract, dated 7 October 2026. It implements
the [current research plan](research-state-and-next-steps-v1.md) in separately
versioned modules. It is not a prospective institutional experiment, an amendment
to qualification, or evidence of beneficial governance. The frozen physical
engine, policies, protocols and completed banks retain their original identities.

The implemented world begins with **no institutions**. Individuals can propose,
refuse, endorse, join, withhold contributions, violate rules, leave, change an
agreement, replace it and dissolve it. An institution has no territorial
extraction priority, exclusion power, remote inventory access or special sensor.
Two institutions can claim the same site without either acquiring ownership of
its ecological stock. Membership and physical location are separate.

## Supplied physical and contractual capabilities

The new [extension](../swarm_societies/commons_v3/politics_v1.py) composes the
unchanged physical engine with an explicit additional material ledger. It adds
local custody at existing resource sites: individual caches, pledged collateral
and pooled treasuries. All share the same **80-unit total capacity per site** by
default, across all organizations and individuals. Founding more organizations
does not multiply this capacity. Deposits come from private inventory; custody
creates no resources. Generic caches and paid local monitoring are available
to nonmembers as well as members. Refunds require local physical access and
space in the recipient's carrying inventory.

Custody is secure and mechanically honors the recorded commitment. A paid local
audit truthfully measures actual extraction; a valid collateral settlement can
destroy the voluntarily pledged material. These are **supplied affordances**,
not an explanation of how secure property, truthful auditors or enforcement
institutions emerge. They require no government actor in the simulation, but
they do assume credible escrow. Theft, resistance, coercive confiscation,
trustee malfeasance and enforcement against outsiders are unimplemented. This
scope must remain visible in any later paper.

Formal organization can pool voluntary funds to purchase these operations.
No rule changes the harvest action or the underlying contention law. No
quota violation automatically produces evidence or a fine. Nonmembers can
observe and settle valid pledged claims using the same paid local operations;
they cannot be fined merely for sharing the site. Before an institutional
comparison, the decentralized policy must be allowed the relevant generic
storage, communication and commitment opportunities. Implementing an eligible
capability does not establish that a particular comparison policy uses it well.

## State, consent and lifecycle

State includes the physical world, all institutions and custody claims,
proposals, private audit receipts, caches, monotone identities and cumulative
operation costs/forfeitures. Each individual can belong to at most one active
institution. Institutions remain as inactive custody/lineage records after
dissolution; erasing an organization never erases its unpaid claims.

Each charter declares a gross-extraction quota, entry bond, suggested voluntary
dues and a maximum collateral fine. Defaults are 2, 1, 0.1 and 0.5 resource
units respectively. These are engineering defaults, not fitted policy choices
or a frozen scientific treatment. Quotas concern actual extraction at the
custody site. There is no automatic taxation, dues debt or nonpayment penalty.
An individual may choose to pay any affordable amount, including zero.

| Intent | Consent, reach and effect |
| --- | --- |
| `propose` | An unaffiliated individual at a site pays the proposal cost and advertises a charter there. A proposal expires after eight ticks. |
| `endorse` a founding proposal | The proposer and at least one other unaffiliated individual must endorse together at that site, with affordable bonds and sufficient shared storage. Earlier endorsements are not standing consent. Membership and bonds become effective for the following tick. |
| `refuse` | A local individual records refusal. There is no penalty or automatic entry. |
| `join` | A local outsider voluntarily pledges the existing charter's bond. A retained earlier claim must first be withdrawn before rejoining the same institution. |
| `pay` | A local member moves the chosen amount from private inventory to the common treasury. |
| `exit` | A member can leave from any location, including while moving. Exit is effective after this tick's physical activity; that activity still falls under the previously accepted commitment. |
| `withdraw` | A former member locally retrieves a requested amount of mature custody, limited by carrying space. A claim released by an exit during tick t becomes withdrawable at commitment time t+2. |
| `amend` | A member proposes a new charter. All current members must endorse together locally. The new rule starts next tick; old witnessed obligations retain their old terms. Bond-size changes are outside v1 and require a future explicit funding contract. |
| `replace` | Unanimous local endorsement creates a new institutional identity, transfers the active members' collateral and treasury, and retains earlier released claims at the old identity. The old record names its successor. Replacement waits until no live receipt or current paid monitor can create an outstanding old-identity liability. |
| `dissolve` | Unanimous local endorsement ends membership and divides the treasury into equal refundable claims for current members, with a final-recipient rounding correction. The last member's exit also dissolves the institution. Previously departed members retain their own collateral claims. |
| `cache`, `retrieve` | Any individual can deposit in or retrieve from their own local cache. These use the same site capacity and post-physical withdrawal timing as institutional custody. |

Other than exit, a local operation requires the individual to start at the
relevant site and commit no movement that tick. This avoids ambiguous remote
settlement or moving-monitor reach. A political action that is well formed but
unavailable returns a failed event with the generic reason `unavailable`.
Malformed actions fail atomically before execution. Each individual commits
one physical action and at most one political intent per tick.

## Paid evidence and bounded settlement

`monitor` targets a site and costs 0.05 by default. The observer must remain
there. It reports actual gross harvest allocated to each individual present
after physical movement and contention, including zero harvest and outsiders.
It never interprets a harvest request as realized extraction. Reports are
private to the paying observer and arrive at the next decision. Monitoring
creates no continuing surveillance. Without it, even a large violation can go
undetected.

Each receipt binds the subject's membership and charter at commitment, the
observed tick/site and the still-pledged maximum collectible fine. The fine
cap excludes later treasury distributions. A nonmember receipt has no fine.
`sanction` can use a receipt only on the immediately following tick, at its
custody site, and costs 0.02 by default. The fine destroys at most the remaining
pledged amount; the destruction and settlement cost are separately accounted.
Private inventory is never seized. Multiple witnesses cannot multiply the
fine for the same institution, subject and tick. Settlement attempts resolve
in agent-ID order, and failed duplicate attempts pay no settlement fee.

The paid operation can use the actor's private inventory, or the opening
treasury if the actor is a member of the institution at that site. New
contributions cannot finance treasury operations in the same tick. An
unaffordable or unreachable attempt fails. An exited member's bond remains
locally held through the final receipt window. Changes or dissolution do not
cancel that liability; fresh sanctions cannot reach the member's later
private inventory. Forfeiture is a cost, not income for another institution.

This first commitment is deliberately narrow. A permanently aggressive policy
can ignore a quota and exhaust its collateral. There is no automatic top-up,
expulsion, future debt, pursuit or punishment after the bond is gone. Such
behavior is a stress control, not evidence about deterrence.

## Tick order and material accounting

1. Validate the entire state and all physical/political commitments.
2. Settle valid previous-tick receipts from already pledged collateral.
3. Charge affordable proposal/monitoring operations and move deposits/bonds
   into custody. Resolve simultaneous consent using only proposals visible at
   commitment. Treasury operations use opening funds only.
4. Execute the unchanged physical engine with the explicitly recorded remaining
   private inventory: movement, messages, transfers, extraction, consumption
   and ecological renewal retain their original order and costs.
5. Issue purchased receipts under the opening charter; make departures and
   custody releases effective. Finish local mature withdrawals/retrievals into
   available carrying space. Withdrawals cannot finance this tick's actions or
   consumption.

New membership and charter state is published with the resulting tick. Although
the implementation stages some immutable records before the physical call,
liability and eligibility use the opening membership and accepted charter.
Endorsement cannot grant a new member retroactive liability or access to
newly contributed operating funds.

The physical substep has its original ledger. The outer ledger independently
checks the combined identity:

```
opening private inventory + custody + ecological stock + realized growth
  = closing private inventory + custody + ecological stock
    + consumption + physical movement/message/harvest costs + physical waste
    + political operating costs + forfeited collateral
```

Transfers, deposits, refunds and treasury distributions move existing resources.
Unrealized growth above patch capacity is not deducted again. A physical
`StepResult` refers to its own substep; the final political `State.world` also
includes post-physical refunds. Report the outer ledger when custody is active.
With no political intents or prior political state, physical results and
trajectories are exactly identical to the original engine.

## Observation and continuation

The legal observation retains the original physical packet and adds a
`politics` field. Charter boards, proposals, roster, treasury and own custody
claim can be inspected only while at their site. The individual knows their
own current membership and accepted charter away from the site, but receives
no remote treasury balance, roster changes, other individuals' inventories or
unpaid extraction history. Paid receipts are visible only to their observer.
These are supplied communication/inspection rules, not free global information.

Political snapshots use JSON-native state, a version and a checksum, and
validate custody, identifiers, memberships and material capacities on restore.
Checksums detect changed contents; they do not authenticate the historical
truth of a deliberately reconstructed checkpoint. The separate episode runner
also checkpoints audited policy kinds, parameters and every mutable memory
field. Continuation regenerates observations and new decisions; it does not
replay a previously committed action list as a substitute for policy state.
An explicitly scripted fixture binds its entire future schedule in its memory.

## Engineering completion and scientific boundary

Deterministic tests cover institution absence, refusal, founding, entry,
nonpayment, paid activity, detected/undetected extraction, outsider immunity,
failed settlement, exit, amendment, replacement, dissolution, local refunds,
conservation and full checkpoint continuation. They should include concurrent
actions, JSON file round trips and changes to hidden remote state. Test traces
establish executable capabilities, not empirical formation or institutional
benefit.

The audited policy layer retains the frozen competent navigation controller,
adds a candidate paid local reporting coordinator, and supplies explicit
voluntary-charter response heuristics. A reporting candidate is not yet a
qualified strongest decentralized baseline. A scripted lifecycle is not
spontaneous political formation, and a responsive heuristic is not a computed
private optimum. No generated policy execution or model spending is introduced.

Next comes a small declared development comparison using the same physical
affordances, followed by a separately frozen independent evaluation. The
[current plan](research-state-and-next-steps-v1.md) specifies consumption,
maintenance/recovery, original cohorts including exiters, outsider effects,
all operation costs, and mechanism controls. The old qualification verdicts
and terminal utility weights remain unchanged. The tipping protocol remains
unexecuted and is not a prerequisite for this engineering implementation.
