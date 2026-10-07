# Need-targeted local harvesting: development protocol v1

This separately versioned development comparison follows inspection of both
completed physical-foundation banks. It tests the next missing baseline:
harvest toward current consumption need and a small usable buffer under the
original carrying capacity of 80. It reuses the four development seeds and
their configurations; it is not an untouched ecological or incentive
qualification panel. No experimental model calls or evolutionary runs occur.
No favorable result is required for completion.

## Frozen physical and information contracts

The [foundation protocol](commons-v3-foundation-protocol.md) and unchanged
`commons-v3-physical-v1` engine supply all physical laws, costs, initialization,
local observations and accounting. The [v2 fuel-margin repair](commons-v3-foundation-protocol-v2.md)
supplies prospective fuel protection. The new policy uses only its legal local
packet, previously observed site coordinates and its own cell-visit counts.
It receives no hidden renewal rate, weather, remote stock or peer inventory.
There are no institutions, memberships, enforced quotas or higher authority.

## Predeclared policies

Two need-targeted policies differ only in desired consumption-buffer size:
zero or two ticks of the individual's current need. These are fixed controls,
not parameters selected from this panel's performance.

At a candidate cell, desired inventory before consumption is
`min(carrying_capacity, (1 + reserve_ticks) * need + fuel_reserve)`.
The harvest request is the positive target deficit divided by
`1 - harvest_cost_per_unit`, capped by visible stock, physical extraction rate
and actual storage headroom. Overflow precedes consumption, so current need
does not enlarge available storage. Scarce stock is still allocated by the
engine; a request does not guarantee a harvest.

The fuel reserve is the unchanged v2 rule: movement cost times the greater of
four steps or nearest-known-site distance plus one, with its prospective
numerical margin and carrying-capacity cap. Only this fuel is protected by
`Action.reserve`. The desired consumption buffer is freely consumed when
harvesting is insufficient; there is no deliberate withholding of that buffer
at the expense of current need.

The policy retains v2's visible-neighbor yield ranking, affordable one-step
movement, least-visited scouting and numerical return-fuel check. Two guards
prevent a harvest cap from creating purposeless scouting. If current inventory
already meets the target, stay and consume. Otherwise accept a positive local
yield score when it meets the least of half of current need, the positive
current consumable-inventory deficit and the positive capacity-capped target
deficit. The last bound also permits useful top-ups when need exceeds storage.
If no candidate is accepted but current inventory above protected fuel covers
current need, stay, request any available current-site top-up and consume. Otherwise scout or
use v2's current-site fallback. Moving onto a site still postpones harvest
until a later action, as in v2.

These choices change navigation decisions through yield scores and waiting,
as well as extraction. Comparisons with v2 and focal greedy replacements are
whole-policy interventions, not mechanism-specific extraction ablations.
Purposeful navigation, simultaneous move-and-harvest controllers and numerical
policy optimization remain separate subsequent baselines.

## Cases and population conditions

The complete 56-case development design is the same as foundation v2: rates
0.12/0.24/0.36 crossed with needs 0.8/1.2/1.6, seeds 61001–61004, 256 ticks,
and focal identities 0/6/12/18 respectively. At the preselected reference cell
(`rate=0.24`, `need=1.2`), retain all five existing sensitivities: 512 ticks,
keyed priority contention, initial stock 22, additive renewal and carrying
capacity 8. The last is explicitly a sensitivity; the primary grid and other
sensitivities retain capacity 80. No physical or utility parameter is retuned.

Each configuration has four new population conditions:

| Condition | Population |
| --- | --- |
| `need_0` | Everyone targets current need plus fuel, without an extra consumption buffer |
| `need_2` | Everyone targets current need, two further ticks of need and fuel |
| `focal_greedy_need_0` | One frozen v2 greedy individual replaces the preselected focal agent among unchanged need-0 peers |
| `focal_greedy_need_2` | The same replacement among unchanged need-2 peers |

This produces 224 new episodes, 61,440 physical ticks and 1,474,560 individual
decisions. It does not add independent evolutionary replications. The existing
v2 all-restraint and all-greedy comparisons are read from saved, hash-verified
records with exactly matched case configurations; those banks are not rerun
or overwritten. Four seeds reused across conditions, rates and sensitivities
remain four seed realizations, not 56 independent environments.

## Outcomes and interpretation

Report all cells and conditions, including adverse and null outcomes. Primary
descriptive quantities are consumption per agent-tick, final-quarter consumption,
terminal ecological stock/capacity and terminal individual inventory. Preserve
movement/extraction costs, waste, depleted-site-time fractions and trajectories.
For each baseline independently, pair focal replacement with its corresponding
all-baseline population; report focal consumption and terminal inventory,
peer and whole-world consumption, and private utility changes at the unchanged
terminal-wealth weights 0, 0.05 and 0.2. Utility is
`(cumulative_consumption + weight * terminal_inventory) / horizon`.
Report need-2 minus need-0 population contrasts as well.

Means and min–max ranges across four paired seed/focal configurations are
descriptive, not confidence intervals. Do not combine wealth-only returns with
consumption gains, equate hungry agents with global ecological collapse, or
call peer effects cross-border institutional outcomes. The additive sensitivity
changes stock dependence, not just one fixed realized resource budget.
Performance gains cannot establish an optimal controller, qualified social
dilemma, robust navigation or institutional benefit.

## Engineering acceptance and preservation

Before the panel runs, copy and hash the complete source/protocol set and save
the machine-readable design. Test cost conversion, target/storage caps, buffer
availability for consumption, waiting and numerical fuel boundaries using
small exact worlds. No policy changes follow inspection of panel outcomes.
Every episode checks accounting, absence of extraction overflow and affordable
known-site returns. Paired conditions share keyed weather. The preselected
reference case records physical frames and checks snapshot continuation under
identical future committed actions; this does not restore policy memory.

Save every case and compare completed cases on replay before resuming an
interruption. Preserve failed banks and failure receipts; refuse to overwrite
a completed bank. Verify source identities, complete artifact inventory,
canonical JSON values, aggregate reconstruction and a full semantic replay.
Preserve both earlier development banks byte for byte. A necessary later repair
requires a new version and retains the failed evidence.

Recorded-data Chromatic Field figures accompany the result, with readable
captions, CSV inputs, source/output hashes and SVG/PDF/PNG exports. Inspect the
rendered PNGs. The final report states remaining baseline and separate
ecological/incentive qualification work, regardless of these outcomes.
