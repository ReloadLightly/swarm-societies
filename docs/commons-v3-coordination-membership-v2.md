# Consequential coordination and responsive membership v2

This engineering increment follows the completed
[first institutional development bank](commons-v3-institutions-development-v1.md).
It preserves that bank and every source in its closure. New versioned controllers
address its almost inactive communication comparator and static membership
decisions. Synthetic fixtures exercise the new decisions; this is not a new
sampled development bank, policy selection or independent evaluation.

## Information and physical contract

The frozen engine and political primitives remain unchanged. The v2 episode
adapter adds an explicit **private previous-tick receipt**, equally available to
every registered controller. It contains only the actor's own consumption,
shortfall, extraction, physical charges, private political fees, voluntary dues
and collateral forfeiture. Fresh episodes begin without a receipt. Complete
checkpoints bind the receipt and its timing. No global measurement frame,
other person's inventory, remote treasury or unpurchased audit enters a policy.
This is a new observation contract, not a retroactive interpretation of v1.

Own consumption cannot be recovered reliably from inventory changes alone:
harvesting, transfers and custody confound that difference. Already incurred
charges are not subtracted again from realized consumption. The receipt supports
a declared dissatisfaction rule, not causal attribution of shortfall to an
institution.

Paid reports carry dated, attributed site observations and declared route
intentions. Intentions are unverified soft commitments; agents can depart from
them and malformed or expired messages must be ignored. They do not create
binding bilateral escrow or reveal other agents' private state. Route forecasts
use local information, remembered observations and explicit travel costs.
Messages are optional and protect consumption and movement reserves. A new
route must satisfy a declared surplus and fuel condition; sending messages
or using caches is not an end in itself.

Assertions may be false. Their site IDs and headcounts are bounded as message
data rather than secretly checked against the evaluator's world; otherwise a
plausible false report could abort the episode through checkpoint validation.
Fresh direct sensing supersedes conflicting reports. Reported destinations
do not establish safe return locations: directed travel uses directly observed
sites as return anchors. A known location still does not guarantee future food.
No adversarial robustness or useful value for every sent message is established.
Before the first directly observed resource site, the inherited exploration
rule still has no established return destination. In shared mode, the new
return-anchor rule is part of the controller bundle; disabling coordination
retains exact frozen-forager behavior.

## Membership decision rule

The same coordination controller underlies decentralized and charter modes.
The latter compares a short local service forecast under the proposed quota
with feasible remembered outside opportunities. It treats bond locking as a
liquidity constraint; released collateral is not immediate consumption.
Founding/entry fees and bonds must be affordable before physical actions, while
retaining need and navigation reserves. A forecast tie may permit voluntary
entry; no intrinsic membership reward or terminal-value change is added.

The outside menu includes staying at the same site without a quota. Consequently,
entry generally occurs on a forecast tie: accepting an affordable tie is a
supplied convention, not evidence of a discovered advantage. The static service
forecast repeats a dated stock-derived rate without solving renewal or depletion;
it is not a conservative bound on future consumption.

Members voluntarily limit their own extraction requests to accepted quotas
at the institution's site. The engine never clamps extraction. Repeated own
shortfall, excessive private political charges or a forecast outside advantage
can trigger exit after a minimum observation period. A cooldown prevents
immediate re-entry. These are supplied local heuristics, not optimal entry,
learned preferences, proof of beneficial membership or a best response.

Exit remains legal remotely. Refunds retain the existing delay and require
local access and carrying capacity. The initial new membership controller
does not purchase monitoring or fund an unused enforcement service. Existing
paid monitoring/settlement capabilities and frozen enforced controllers remain
available; prospective separation of their effects is the following work item.

## Engineering checks and scientific boundary

Fixtures must exercise an actionable paid message, route response, no-benefit
inactivity, stale/malformed report handling, affordable entry, refusal, repeated
dissatisfaction, actual exit and delayed local refund. Hidden-state changes
that leave legal observations unchanged must not change decisions. JSON
continuation must restore all policy memory, pending messages and private
receipts, regenerate decisions and retain material accounting.

The runtime admits only audited built-in classes. No generated-policy route,
model calls, evolutionary campaign or new qualification samples are introduced.
The v1 development losses and weak comparator remain the current empirical
result. These fixtures cannot show that v2 improves welfare across environments.

Before another sampled comparison, specify mechanism controls, matched
information/commitment opportunities, original-cohort and outsider endpoints,
and fresh seeds in a separately frozen protocol. Nonbinding intentions still
do not provide a full nonmembership counterpart to formal binding escrow.

## Implementation and checked fixtures

The new modules are [coordination](../swarm_societies/commons_v3/policies_coordination_v2.py),
[membership](../swarm_societies/commons_v3/policies_membership_v2.py),
[private feedback](../swarm_societies/commons_v3/own_feedback_v2.py) and the
[audited v2 episode runtime](../swarm_societies/commons_v3/political_episode_v2.py).
The constructor defaults are declared engineering choices, not estimated
preferences or selected optima:

| Rule | Default |
| --- | --- |
| Foraging background | Buffer 4, floor 0.5, nearest route; the fixed-floor background is also supported |
| Communication | At most one engine-bounded report per four ticks; direct observation age at most eight ticks; intentions expire after four |
| Route change | Positive estimated surplus above 0.05 × need, with travel/fuel checks |
| Membership forecast | Four-tick static service window; quota 2, bond 1, nominal unused dues 0.1, fine 0.5 |
| Entry liquidity | Preserve current need, two additional ticks of need, planned messages and navigation reserve after the entry debit |
| Exit | Minimum four ticks of observed membership; three consecutive adverse decisions |
| Adverse decision | Own shortfall above 0.1 × need, private political charges above 0.1 × need, or outside forecast advantage above 0.05 × need |
| Re-entry | Eight following decisions excluded after an exit; local mature claims may still be withdrawn |

Membership promises are voluntary cooperative behavior. They apply on the final
exit tick and on arrival at the remembered institution site. Remote membership
does not reveal a remote service forecast. A receipt from before observed entry
does not count as an outcome of that membership. Zero-value mature bond records
are cleared through a legal zero withdrawal so they cannot permanently prevent
later re-entry. No cash is created by exit or withdrawal.

The [recorded compact fixture](../evidence/commons-v3-coordination-membership-v2/fixture.json)
binds every source and initial state, including staged controls and complete
traces. It records four constructed checks:

- A real 21-byte delayed intention costs 0.021 resource units. Removing only
  the delivered information while retaining that payment changes the recipient's
  route and its subsequent extraction (2 versus 0). The sender completes its
  announced route through an explicitly scripted continuation; the recipient
  begins a fresh controller at the branch boundary. This is a constructed
  mechanism check, not a population benefit estimate.
- Own shortfall under unchanged charter terms triggers exit at tick 4. The
  collateral becomes available and is withdrawn at tick 6. Withdrawal does not
  increase consumption on that tick; it occurs after physical consumption.
- Supplied local rules form a charter in an arranged favorable state, without
  scheduling founding actions.
- Insufficient protected liquidity produces refusal and no membership.

All **18 continuation ticks** regenerate decisions, private receipts and flows
exactly. Maximum absolute material residual is **1.10 × 10⁻¹⁴**. The full v3
suite passes **680 tests**; the final new-policy/runtime suite passes **110**.
Tests also retain failed delivery, expired/malformed messages, false assertions,
no useful-information inactivity, hidden-state invariance, strict memory and
owner clocks, and exact disabled-coordination parity for both old backgrounds.
Zero experimental model calls, evolutionary runs or sampled-bank episodes occur.

Reproduce the compact engineering record from the repository root:

```bash
.venv/bin/python scripts/demo_commons_v3_coordination_v2.py --full-trace \
  --output /tmp/commons-v3-coordination-v2-fixture.json
.venv/bin/python -m pytest -q tests/test_commons_v3_policies_coordination_v2.py \
  tests/test_commons_v3_policies_membership_v2.py \
  tests/test_commons_v3_political_episode_v2.py
```

Use a new output path; the demo refuses overwrites. These small constructed
fixtures remain in Git and require no bank download. The next scientific item
is prospective mechanism separation and commitment/information parity, followed
by revised development and fresh independent evaluation. V2 engineering does
not replace the complete first bank's mixed and adverse results.
