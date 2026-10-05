# Executable model and candidate contract

This increment is an original, compact resource ecology inspired by SwarmWorld's separation of candidate decisions from deterministic consequences. It does not run the SwarmWorld simulator or claim to reproduce its material-science environment. The upstream inspection and integration decision are recorded in [upstream.md](upstream.md).

## Architecture and units

`ecology.run_episode` owns the environment, membership, accounting, disturbance, observations, and measurement. `candidate.CandidateProgram` owns a restricted executable member policy and institution. The evaluation harness owns immutable source snapshots, evolutionary acceptance, partner/opponent assignment, and protected cases. Rendering reads recorded data. Neither candidates nor renderers compute their own fitness.

A society has explicit member IDs, one treasury, infrastructure, defense, institutional state, member reports, and an institutional broadcast. Each member has personal wealth, heterogeneous productivity, and private state. Membership remains fixed during an episode. Institution and member implementations can be inherited independently; heterogeneous member programs are supported through a society × member matrix. There is no restriction to a catalogue of seed strategies: generated functions may introduce helper functions, branches, loops, memory updates, and calculations in the supported Python language.

Episode state starts empty at reset and is never inherited. Programs, source hashes, and recorded parentage persist between generations. Memory updates can change behavior within an episode; those changes are not evolutionary updates. This increment has memory-bearing decision rules, not learned neural weights, belief calibration, general world models, autonomous institution creation, or demographic reproduction. The separate program, state, world, evaluator, and renderer layers leave those extensions possible.

## Resources and sequence

Each society has a home patch. Any member can harvest the home patch and one other currently observed patch. These are shared stocks: harvesting by one member removes resources available to all members and societies. Patch availability is partially observed, not privately owned.

On each zero-indexed tick:

1. All infrastructure depreciates by 4%. Each patch renews by weather-adjusted base regeneration plus `2.2 × own infrastructure` and a spillover of `0.08 × other societies' mean infrastructure`, capped at patch capacity.
2. Each institution reads its own treasury, infrastructure, members' wealth, and previous member reports. It emits allocation rules, a broadcast, and updated shared state.
3. All members receive observations before any member's action is resolved. Each emits an action, message, and updated private state. Weather, initiative order, raid random numbers, and victim indices are drawn independently of actions to preserve common random numbers between treatments.
4. Actions resolve in a seeded shuffled order. Scarce stock allocation therefore depends on realized initiative. A non-rest action costs up to `0.08 × effort` personal wealth. Members without wealth can still act; this is an abstract production game without death or labor eligibility.
5. Treasuries allocate investment, defense, reserves, and redistribution. Members consume up to 0.85 resource units by default. Unmet need is measured. Reports become available to the next institution call.

Default public API parameters are `EcologyConfig(n_societies=3, members_per_society=6, ticks=80, disturbance_tick=40, initial_wealth=4, initial_patch=35, patch_capacity=60, regeneration=8.5, consumption_need=0.85, drought_factor=0.36)`. The recorded first-run protocol overrides population and horizon. At `disturbance_tick` the base regeneration is multiplied by `drought_factor × a seed-specific uniform factor in [0.85,1.15]` per patch. Infrastructure additions are drought-independent. Weather varies in [0.85,1.15]. Productivity varies in [0.85,1.15] between members and is fixed within an episode. Future disturbance timing, magnitude, and random seeds are absent from observations. Agents can react to observed scarcity or exploit a learned search-horizon schedule; held-out environmental seeds alone do not rule out timing overfitting.

| Member action | Material consequence |
| --- | --- |
| `harvest` | Withdraw up to `2.4 × productivity × effort` from a visible patch; institutional tax goes to own treasury. |
| `contribute` | Transfer up to `2 × effort` from personal wealth to own treasury. |
| `share` | Transfer up to `2 × effort` to the chosen society's treasury. Sharing with self is recorded as contribution. |
| `raid` | Target a random member in the chosen society. Same-society raids cannot target self. If successful, take up to `2.3 × effort / (1+0.4 × defense)`; 72% reaches the attacker and 28% is destroyed. |
| `guard` | Forego harvesting and add 0.4 protection to own society during this tick. This protection is independent of effort; effort controls only the action cost. |
| `rest` | No production, transfer, protection, or action cost. Consumption still occurs. |

Raid success probability is `0.75 / (1 + defense)` where defense includes current guards and previously accumulated institutional defense. Institutions can prohibit outward raids; attempts still incur action cost and are counted. They cannot prohibit same-society theft through this control. Separate attempt counts, successful losses, gain, and destruction make the distinction observable.

## Candidate API

A source file must define both functions:

```python
def member_policy(observation, private_state):
    return {'action': 'harvest', 'target': observation['society_id'],
            'effort': 1, 'message': {}, 'state': private_state}

def institution(observation, shared_state):
    return {'tax_rate': 0.2, 'public_fraction': 0.4,
            'defense_fraction': 0.1, 'reserve_fraction': 0.1,
            'raid_permission': False,
            'redistribution': [1 for m in observation['members']],
            'messages': {}, 'state': shared_state}
```

Member observation keys are `tick`, `society_id`, `member_id`, `n_societies`, `n_members`, `wealth`, `productivity`, `infrastructure`, `tax_rate`, `patches`, `messages`, and `last_action`. A patch is `{id, stock}`. The member sees its home and a rotating other patch; with two societies it necessarily sees both stocks, but never sees opponents' private memory, policies, treasury, members' wealth, or future state. Target society IDs are bounded modulo the configured society count. Harvesting an invisible patch resolves to the home patch. Other actions can address society IDs without inspecting the target's wealth.

Institution observation keys are `tick`, `society_id`, `n_societies`, `treasury`, `infrastructure`, `mean_wealth`, `members`, and `reports`. A member entry is `{id, wealth}`; a report is `{member, message}`. The institution has access to local wealth for redistribution, not members' private state. Members can misreport observations. The institution can aggregate, withhold, transform, or relay information through `messages`; only its broadcast reaches members. The cooperative seed reacts to private stock trends and the institution's shortage signal, so the memory/information channels can affect actual decisions.

Tax is clipped to [0,0.8]. Public, defense, and reserve fractions are nonnegative, individually clipped to [0,1], and normalized if their sum exceeds one. The unallocated fraction is redistributed using a member-length nonnegative weight list, bounded at 100 per member; zero total weight means equal distribution. Each `8 × member count` resource units invested adds one infrastructure unit. Defense investment adds `spending / member count` to 65% of previous defense. Both forms of spending remove liquid resources. Reserves remain in the treasury. Members receive transfers before consumption.

Both states and broadcasts must be JSON dictionaries of at most 8,192 serialized characters; member messages are limited to 1,024 characters. Complete function results are limited to 32,768 characters. Unknown actions, malformed weights, execution errors, nonfinite output, and budget overruns invalidate a candidate evaluation. Invalid scalar fractions are bounded to their lower limit. Resource effects are applied only by the simulator.

## Protection and reproducibility

The candidate language rejects imports, classes, private names, reflection attributes, dynamic code evaluation, exception machinery, context managers, asynchronous functions, generators, exponentiation, and bit shifts. Available builtins are simple arithmetic, collection, sorting, and iteration functions. Public dictionary/list methods are allowed. Module scope permits functions, docstrings, and literal constants only. A call has a 10,000 executed-line budget. Observation/state inputs are JSON copies; output primitives are copied and checked again. Fresh program namespaces are created for each member and institution in every episode. This is not a general hostile-Python sandbox: a single allowed operation can allocate substantial memory, and an outer resource-limited evaluator is necessary. The first-run harness adds subprocess isolation, memory limits, and timeout handling.

Simulator truth and private evaluation inputs live outside the candidate namespace. Candidate programs cannot import the evaluator or inspect files. The first-run candidate-generation process is separately configured and must receive only the program API and search evidence. Hashes identify source snapshots; a deterministic result digest identifies a replay including its configuration, seed, metrics, and events. Reproduction requires the same source and simulator revision.

## Outcomes and accounting

Individual utility is `cumulative consumption + 0.2 × terminal personal wealth`. Individual interests therefore include a personal buffer even when taking resources from others. Per-tick society welfare is `(total consumption − 0.5 × total shortfall) / member count + 0.03 × infrastructure`. Pre, post, and overall welfare are means over their respective ticks. Welfare is an explicitly chosen value function, not an emergent moral judgment. Infrastructure's direct bonus can reward construction even without improved consumption; primitive consumption, shortfall, wealth, and infrastructure are retained to expose this tradeoff.

`cooperation_within` equals tax plus voluntary contribution: it measures material pooling, not voluntary prosocial intent. `cooperation_between` equals outward aid. Taxes, contributions, aid, within-society theft, outward harm, inward harm, raid gain, and redistribution are also separate raw columns. Infrastructure spillovers affect others but are not counted as aid. There is competition for shared patches even when no raid occurs. `adaptation` is post-minus-pre welfare; a positive value is descriptive and does not by itself identify evolved adaptation.

The liquid-resource ledger enforces, within numerical tolerance:

`final liquid = initial liquid + regeneration − consumption − action costs − raid destruction − investment − defense spending`.

Liquid stock includes all patches, personal wealth, and treasuries. Taxes, contributions, aid, redistribution, and non-destroyed loot are transfers, not creation. Investments transform liquid stock into a depreciating productive capacity; their later output appears explicitly as regeneration.

The result has `society_metrics`, flat `member_metrics`, `aggregate`, a tick-by-society `timeseries`, and a `ledger`. Optional `replay` frames contain `tick`, `disturbed`, `patches`, societies and visible member actions, plus material events. `program_hashes` and `member_program_hashes` identify the exact actors. Search and fresh-case fitness are kept in distinct harness records. See [protocol.md](protocol.md) for variation, inheritance, selection, and inference limits.
