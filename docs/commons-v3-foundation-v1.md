# Commons v3: mobile agents and a stock-dependent physical world

This checkpoint implements the physical foundation of the
[spatial commons plan](commons-v3-plan.md), in a separate engine. It leaves
every earlier simulator, policy runtime, protocol and published study unchanged.
There are mobile individuals and renewable sites, with **no institutions,
mandatory membership or supranational authority**. Political formation and
enforcement remain the next layer after ecological qualification.

The purpose is to make extraction change future opportunities and to measure
those consequences before paying for another program-evolution campaign.
This is a physical implementation and exploratory development study, not a
claim of swarm intelligence or successful governance.

## Implemented physical contract

| Component | Implemented behavior |
| --- | --- |
| Space and movement | Bounded integer grid; cardinal movement by at most one cell; payment from the actor's available inventory |
| Local information | Radius-limited sites and nearby identities/positions; own inventory and public action costs; no remote stocks, peer inventories, hidden weather or environment seed |
| Extraction | Same-cell access; physical extraction-rate limit; proportional sharing of scarce stock or keyed random priority |
| Inventory and consumption | Finite storage; gross extraction incurs a material cost; overflow is recorded before consumption; voluntary reserves can reduce consumption and increase recorded unmet need |
| Local transfers | Optional gifts to visible, reachable agents; incoming gifts cannot finance simultaneous outgoing gifts; no transfer fee |
| Communication | Bounded UTF-8 payloads, paid payload-byte costs, sender provenance and one-tick delivery; reach required at commitment and after movement |
| Ecology | Renewal depends on post-extraction stock, with capacity clipping, bounded weather and explicit recovery; additive renewal is an implemented negative control |
| Accounting and continuation | Per-agent, per-site and whole-world flow ledgers; immutable states; versioned, checksummed physical snapshots; deterministic keyed events |

All actions are committed before any are resolved. Movement precedes messages,
then transfers, extraction, storage overflow, consumption and renewal. Peers'
actions cannot be observed and answered within the same tick. Recovery and
growth are ecological inflows; consumption, movement, extraction and messaging
are sinks. Transfers and harvesting relocate resources. Unrealized growth above
capacity is distinct from material discarded from inventory.

For post-extraction stock `s`, capacity `K`, rate `r`, recovery coefficient `q`
and weather multiplier `W`, potential growth is `W * (r*s*(1-s/K) + q)`.
Actual growth cannot exceed `K-s`. The additive control replaces `s*(1-s/K)`
with `K/4`, matching potential production at half capacity. This explicitly
changes dependence on stock; it does not hold realized resource budgets equal.
Weather and priority draws are keyed by seed, tick and site/identity, so changing
the number of actions or messages cannot shift an unrelated random stream.

No demographic death or reproduction is modeled, and no survival improvement
is reported. The old world-model learner is preserved as a tool; its additive
observation model has not been silently reused for this different ecology.

## Development design and interpretation

The active [v2 development protocol](commons-v3-foundation-protocol-v2.md),
[machine-readable design](../evidence/commons-v3-foundation-v2/design.json) and
[source hashes](../evidence/commons-v3-foundation-v2/sources.json) were recorded
before the repaired development panel ran. V2 follows inspection of v1 and
reuses its cases; it is explicitly not untouched evaluation data. Each panel crosses three renewal
rates with three needs at four seeds, then repeats a fixed reference cell under
five sensitivities. Four population conditions yield **56 configurations and
224 episodes**. Both banks are retained: 448 recorded episodes across two
diagnostic policy versions. Reused seeds, parameter cells, agents and ticks are dependent;
there are **zero independent evolutionary runs and zero experimental model calls**.

The conditions are all-restraint, all-greedy, one greedy focal replacement among
unchanged restrained peers, and a half-greedy population. Both local heuristics
share navigation and fuel budgeting. Restraint requests stock above half
capacity divided by visible co-located headcount. Greedy requests available
stock within physical and storage limits. Memory holds previously observed site
coordinates and the agent's own visited cells. Neither policy sees the global
state or law parameters. Both scout when expected local yield falls below half
their consumption need; these are diagnostic heuristics, not optimal or fully
qualified strong baselines. A policy replacement changes navigation as well as
extraction choices.

Sensitivities cover twice the horizon, a different contention rule, lower initial
stock, additive renewal and smaller carrying capacity. Private utility is
consumption plus weighted terminal inventory, evaluated at weights 0, 0.05 and
0.2 from the same saved primitives. Results distinguish focal consumption,
other agents' consumption, aggregate yield, late consumption, inventory and
ecological stock. With no affiliations, these are agent and peer outcomes;
they are not national welfare or cross-border harm estimates.

## Why the first development bank remains visible

The [v1 bank](../evidence/commons-v3-foundation-v1/manifest.json) revealed a
numerical control artifact. An agent could leave a known site with a nominal
round-trip travel budget and, after repeated subtraction, hold
`0.039999999999999994` units where the return check required `0.04`. It then
refused every move. At the reference cell, all-greedy consumption was only
0.241041 per agent-tick, yet terminal resource stock recovered to 89.16% of
capacity. That contrast cannot be presented as evidence of persistent
ecological collapse.

The separately versioned v2 policy retains a tiny prospective fuel buffer and
requires a positive numerical margin before scouting. Physics still charges
every movement in full; the repair neither creates resources nor rescues an
already underfunded state. V1 source, cases and results remain unchanged.
V2 checks the known-site return budget after every transition and records any
failure, independently of which population condition it would favor.

An earlier verifier-only repair replaced Python equality with canonical JSON
comparison, because boolean and numeric fields can otherwise compare equal.
All 56 case archives, the complete summary and the design stayed byte-identical
across that repair. Its preserved preflight is an additional reproduction, not
new independent evidence. The policy repair is a separate change and does alter
trajectories. These changes do not authorize a scientific claim selected from
the more favorable run.

## Recorded v2 development results

At the preselected reference cell (`rate=0.24`, `need=1.2`, 256 ticks), means
across four paired seed/focal configurations are:

| Population | Consumption/agent/tick | Final-quarter consumption | Terminal stock/capacity |
| --- | ---: | ---: | ---: |
| All restraint | 1.200000 | 1.200000 | 0.722566 |
| One greedy focal agent | 1.103430 | 1.075890 | 0.748991 |
| Half greedy | 0.537828 | 0.539999 | 0.375386 |
| All greedy | 0.229769 | 0.100000 | 0.667041 |

The focal replacement has **zero consumption gain in all four configurations**.
Its private gain is +0.010685/agent/tick at terminal-wealth weight 0.05
(observed range 0 to 0.014717), entirely from terminal reserves. Mean other-agent
consumption falls by 0.100769. Doubling the horizon reduces that private gain
to 0.005596; carrying capacity 8 reduces it to 0.000252 and removes mean peer
consumption loss. A range across four configurations is not a confidence interval.

| Reference sensitivity | All-greedy consumption | Focal consumption change | Focal private change, wealth weight 0.05 |
| --- | ---: | ---: | ---: |
| Base | 0.229769 | 0.000000 | 0.010685 |
| Horizon 512 | 0.164884 | 0.000000 | 0.005596 |
| Keyed priority | 0.251115 | 0.000000 | 0.010685 |
| Initial stock 55% | 0.138111 | 0.006363 | 0.017836 |
| Additive renewal | 1.200000 | 0.000000 | 0.010547 |
| Carrying capacity 8 | 1.093197 | 0.000000 | 0.000252 |

Across the nine grid cells, focal consumption improves in four cells and is
unchanged in five. All-greedy consumption is lower than restraint in all nine,
but this is not a clean demonstration of global ecological collapse. At the
reference cell, 66.70% of total stock remains at the end despite low consumption.
The preselected spatial example contains full unused sites alongside depleted
occupied sites. The repaired heuristic still has access and navigation
limitations. Zero return-fuel failures establishes the repaired arithmetic
invariant, not an effective foraging strategy.

The smaller-inventory control improves all-greedy consumption from 0.229769 to
1.093197 at the same need of 1.2. A need-targeted harvester with a modest reserve
under the original carrying capacity is therefore a necessary next baseline.
The additive control shows that changing stock dependence changes outcomes;
it does not isolate depletion from interacting movement and inventory policies.
Neither the strong-baseline gate nor the separate qualification gate has passed.

![Recorded development grid, focal returns and trajectories](../figures/commons-v3-foundation-v2/development-outcomes.png)

*Recorded v2 development data. Conditions use labels, markers and line styles;
focal ranges span four seed/focal configurations and are not confidence intervals.
[Full captions, CSV tables, source/output hashes and SVG/PDF/PNG exports](../figures/commons-v3-foundation-v2/README.md).*

![Recorded positions and resource stocks](../figures/commons-v3-foundation-v2/recorded-spatial-states.png)

*Actual initial/final grid coordinates for preselected seed 61001. Site intensity
represents resource stock; symbols/counts identify individuals at their recorded
cells. There are no political borders, memberships or inferred trajectories.
The [failed v1 gallery](../figures/commons-v3-foundation-v1/README.md) remains available.*

All 224 v2 episodes completed, representing 61,440 physical transitions and
1,474,560 individual decisions. Every recorded return-fuel violation count is
zero. The maximum engine accounting residual is 5.43×10⁻¹³ resource units;
an independent reconstruction stays below 8.6×10⁻¹³. These engineering checks
are distinct from scientific qualification. Four reference episodes also verify
physical-state snapshot continuation under identical future committed actions.

## Reproduction and engineering scope

The two raw case banks are kept in [checksummed development archives](../artifacts/commons-v3-foundation-v1/README.md).
Designs, summaries, source snapshots and figures remain in Git. Restore before
semantic replay or figure regeneration; default tests use small synthetic worlds:

```bash
.venv/bin/python scripts/restore_evidence_v1.py \
  --catalog artifacts/commons-v3-foundation-v1/catalog.json --study all
```

Verify every artifact, reconstruct aggregates and replay all 224 episodes:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_development_v2.py verify \
  --output evidence/commons-v3-foundation-v2 \
  --receipt runs/commons-v3-replay/receipt.json
```

Create a separate reproduction bank, preserving the published one:

```bash
.venv/bin/python scripts/run_commons_v3_development_v2.py prepare \
  --output runs/commons-v3-reproduction
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/run_commons_v3_development_v2.py run \
  --output runs/commons-v3-reproduction
.venv/bin/python scripts/visualize_commons_v3_development.py \
  --source evidence/commons-v3-foundation-v2 --output runs/commons-v3-figures
```

Completed and failed banks are preserved. Interrupted runs replay and compare
any complete saved cases before accepting them; source or design changes fail.
Physical snapshot continuation is tested under the same future committed
actions. It does not restore private policy memory or certify autonomous
agent-process recovery. Snapshot hashes detect corruption, not authorship.

Only audited built-in policies are executed by this development runner. It has
no generated-source loader, search campaign or new inference allowance. The
existing bounded execution adapters continue to support their frozen historical
engines; integrating v3 candidate execution is a later explicit implementation.

The next implementation is stronger decentralized foraging, including
need-targeted harvesting with modest reserves under the same carrying capacity,
followed by numerical baselines. A separate, larger qualification panel must
then measure unilateral temptation, collective losses and sustainable
alternatives. Optional organizations then
need executable founding, refusal, exit, amendment, replacement and dissolution,
with enforcement paid for and physically reachable. Neither favorable
institution formation nor a positive coevolution effect is a completion criterion.
