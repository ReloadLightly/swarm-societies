# Private beliefs and bounded truthful institutional sharing

Prospective protocol for the next parameter-learning experiment. This document
is a design, not a report of results. Freeze it together with the executable
design and source snapshots before running the evaluation panel. Development
uses a separate arena and seed namespace; previous simulators, learners,
protocols and evidence remain unchanged.

## Question and scope

Can a fixed institution improve its members' knowledge by forwarding truthful
measurements that their private sensors did not supply? How much of that gain
survives a communication delay? The intervention changes report content and
delivery timing while preserving the material trajectory, numerical learner,
private observations, query bank and declared channel capacity.

This is a passive, stationary parameter-learning control. It does not evolve a
reporting rule, permit deception, discover a physical equation, or use beliefs
to choose ecological actions. The previous
[calibration audit](world-model-calibration-v1.md) supports retaining 1,024
particles and four rejuvenation sweeps. Its remaining calibration caveats also
apply here: ecological beliefs condition on the supplied features rather than
modeling their full joint generating process.

## Shared world and private evidence

There are 24 independent arenas, each with three interacting societies, four
members per society, and 128 ticks. All societies share one hidden law draw. The
frozen
stationary ecology, investment/harvest policies, policy-role rotations, public
prior and interior task-law ranges match the identification control. The new
evaluation seed namespace makes these fresh worlds; no earlier evaluation
arena is reused. All case IDs are committed in the executable design before
evaluation. Throughput checks use a separate development namespace.

Each member owns a separate `RenewalSMC` instance. Every institution also owns
an independent instance and receives only admitted reports. Learner objects,
posterior arrays, random generators and evidence sets must never be shared
between owners. All models reset to the same public prior at the start of an
arena; no weights or evidence carry across arenas.

A member's patch footprint is its home patch plus the existing rotating other
patch, `(society + 1 + (member + tick) % 2) % 3`. A licensed instrument supplies
one phase-aligned growth event for each visible patch. The event includes stock
before growth, public capacity, local infrastructure, mean external
infrastructure, and noisy realized growth. This retains the explicit
`full_observation_control` infrastructure license: it is not an implementation
of inference over missing external features.

There is one noisy measurement per physical patch/tick event. Every authorized
observer receives the identical measured value and original event identity;
multiple observers do not create independent measurements of the same weather
realization. Gaussian sensor noise has standard deviation 0.05 and is added
after capacity clipping. The canonical event ID includes arena identity and
the original engine event ID. Instruments supply complete, admitted packets;
the communication layer may forward them but may not invent observations.

Learner payloads exclude the hidden law, weather, exact growth, post-growth
stock, censoring flag, future observations, evaluator probe targets and material
audit fields. The only exception to legacy local sensing is the declared
instrumentation contract above. A study-level truth registry is used for data
generation and scoring, never as an inference input.

## Report contract and interventions

A truthful report contains one authenticated event and its original provenance:
arena/event identity, patch, observation tick and phase, sensor identity,
original observer identity, and payload digest. Routing metadata records the
reporting member, sender, recipient, send tick, delivery tick and channel hop.
Forwarding preserves the original event and payload exactly. A new envelope,
author or delivery does not make a new piece of physical evidence.

The experiment uses fixed-size serialized frames of 1,024 bytes. Count the
whole frame, including provenance, routing metadata and padding. Count a
broadcast separately for every recipient copy;
do not price a twelve-member delivery as one free global message. Record actual
payload bytes as well as charged wire bytes. An oversized report is rejected;
it is never truncated into a different observation.

The planned information conditions are:

| Condition | Private member inputs | Institution inputs and forwarding | Purpose |
| --- | --- | --- | --- |
| Isolated (`isolated`) | Home and rotating-other events | No reports or broadcasts | No-sharing baseline |
| Redundant (`redundant`) | Same private events plus delivered broadcasts | Two fixed senders report the already visible home event; two report envelopes are forwarded | Matched-bandwidth content ablation |
| Complementary (`complementary`) | Same private events plus delivered broadcasts | The same two senders report their different rotating-other events; two envelopes are forwarded | Bounded institution-mediated information |
| Delayed complementary (`delayed_complementary`) | Same private events plus delivered broadcasts | Identical report content and channel capacity, with a longer fixed delivery delay | Latency intervention |
| Legal-union reference (`union_ceiling`) | Union of all three events every tick | Complete union supplied directly | Unbounded information reference |

Members 0 and 1 are the fixed report senders. Their rotating other patches
differ every tick. They use neither posterior uncertainty nor measured outcome
values to select reports. The home-report and complementary-report conditions
have identical numbers of attempted frames, fixed frame size, sender schedule,
recipients and delivery delays. For members, home reports are known duplicates;
for the institutional learner, the two copies of one home event count once.
Each society sends two uplink frames per tick, and its institution broadcasts
each delivered frame to all four members. The two broadcasts are charged as
eight recipient copies. Thus the ordinary steady-state channel allowance is
ten 1,024-byte frames per society per tick, including the uplinks. The same
two original report envelopes are forwarded even when both describe one event.
Keeping these duplicate transmissions is intentional: they measure the cost
of truthful but redundant reporting rather than granting that arm extra
capacity after deduplication.

The union reference is the union of legal member sensors within a society.
With this three-patch footprint, it happens to include all three patches.
There is no cross-society communication channel and no extra evaluator feature
in the reference. Its unrestricted data rate and zero channel delay make it an
information reference, not a fair equal-cost institutional competitor or a
guaranteed forecast optimum.

Ordinary uplink and downlink delays are one tick each. The delayed condition
uses four ticks on each hop. This delay contrast matches channel capacity and
the originating report schedule. It does not guarantee equal total bytes sent
within a finite horizon: later uplink arrivals can leave broadcasts unsent.
The complementary-versus-redundant contrast does match actual sent bytes.
Frame size, delays, sender schedule and conditions are part of the frozen
machine-readable design. Any change after evaluation
begins requires a separately versioned experiment.

## Timing, ownership and duplicate handling

At the start of each tick, deliver previously scheduled messages whose due
time has arrived. An institutional uplink arrival updates that institution and
schedules its forwarded envelope for arrival after the downlink delay. At
tick end, members admit the current authorized measurements and enqueue the
fixed selected reports. An event observed at the end of tick `t` therefore
reaches its institution at the start of `t + uplink_delay` and reaches members
at the start of `t + uplink_delay + downlink_delay`. A delayed event retains
its original observation time; arrival time never replaces it.

Each recipient maintains its own accepted-event set. First arrival can update
the posterior once; later arrivals of the same event and contents are logged
as duplicates and spend communication bytes but add no likelihood factor.
Conflicting contents under one event identity are rejected and remain visible
in diagnostics. Reordering valid delayed evidence is legal for the static-law
model, although finite-particle trajectories can depend on processing order.
The runtime fixes its within-tick delivery order for reproducibility.

No future event, unauthorized member report, forged source, mismatched payload
digest, wrong phase or cross-arena replay can enter a learner through an actor
port. The trusted study harness registers the canonical, arena-qualified sensor
events; actor ports cannot add to that registry. This is an in-process API
boundary, not a network authentication system or a sandbox for arbitrary Python.
The runtime
authorizes reports against the sender's admitted local evidence rather than
trusting a self-declared source ID. An institutional broadcast can forward
only a report that actually arrived at that institution.

Primary learning checkpoints end at the physical horizon. In-flight frames
are not silently flushed into endpoint beliefs. Report sent, delivered and
in-flight counts separately; charge bytes when sent. This makes the cost of a
longer delay visible, including evidence that arrives after the experiment's
decision horizon. Communication is a measured informational resource here;
it does not subtract wealth or change ecological actions.

## Predictions and endpoints

Score 512 predictive samples on 64 common one-step probes per arena at completed
ticks 0, 4, 8, 16, 32, 64 and 128. Probe construction matches the existing
identification control: independent local/external infrastructure inputs in
`[0,2]`, independent weather and sensor noise, and the arena's own hidden laws.
Thirty-two probes have guaranteed nonbinding capacity over the public prior;
32 exercise capacity limits. The probe design and targets are shared across
conditions, societies and members within an arena. Probe observations never
train a live model, and evaluation uses an independent random stream.

The primary estimand is the paired arena difference in **member mean CRPS
integrated over world ticks and divided by the 128-tick horizon**, using the
32 guaranteed-uncapped probes. Average members within society, then societies
within arena. The primary content contrast is complementary minus redundant
truthful reporting. Secondary contrasts are complementary minus isolated,
delayed minus ordinary complementary reporting, and union reference minus
complementary reporting. Redundant minus
isolated is an exact member-posterior negative control, with a distinct
institutional learning contrast. Lower CRPS is better.

Secondary endpoints include terminal CRPS; institutional CRPS; 90% predictive
coverage and interval width; parameter absolute error, interval width and
coverage; unique accepted events; duplicate arrivals; frame and byte counts;
event age at admission; and fitting CPU time. Show member heterogeneity rather
than presenting only an institution's shared model as everyone's knowledge.
Coverage from dependent models is averaged within arena; members are not
independent calibration replications.

Evidence-normalized member learning curves use exact checkpoints after
0, 8, 16, 32, 64, 128 and 256 unique accepted physical events, not received
envelopes or the sum of observations over members. A checkpoint callback scores
the state immediately after the threshold update, before another event can
enter the learner. When updates succeed, every member reaches the common range
`[0,256]` by the 128-tick horizon because its private footprint supplies two
events per tick.
Use piecewise-linear interpolation between these fixed evidence checkpoints
and divide the integrated CRPS by 256. Different conditions can encounter
different examples in different orders, so this is a descriptive comparison
at equal evidence counts, not an isolated test of inference efficiency.
All ordinary conditions use the same learner. Couple initial learner seeds by
arena and owner, without the condition name, so changing a route does not also
change the prior particle draw. The redundant and isolated member posterior
states should consequently agree exactly: duplicate arrivals cannot advance
the inference RNG or add evidence.

An acceptance-test replay control feeds every owner in a multi-tick fixture
its event stream, in the same order with the same initial seed, directly into
a fresh learner. This covers member and institutional ownership; it is not a
second full fit of every model in the production experiment.
Match particles, weights, accepted evidence, accumulated likelihood and RNG
state; communication and duplicate counters are checked separately. A replay
that includes all duplicate update calls may additionally compare complete
serialized snapshots. This checks that routing changes information rather
than secretly changing inference.

No success threshold is selected after inspecting the evaluation panel. If no
development-supported threshold is frozen, report full learning curves and
their area instead of a selectively chosen time-to-success statistic.

## Replication, failures and reproducibility

Independent hidden-law/environment arenas are the replication units. Societies,
members, ticks, forecasts and message copies within one arena are dependent.
Intervals use 2,000 percentile bootstrap samples of whole arenas; contrasts
resample paired arenas together. The experiment uses zero new evolutionary
runs and zero model-generation calls. A confidence interval describes this
panel and supplied model family, not arbitrary swarm intelligence.
The fixed 24-arena panel is not a prospective power guarantee. Secondary
intervals are descriptive, without a familywise multiplicity adjustment;
retain the predeclared primary contrast when interpreting the results.

Failed updates, rejected reports, oversize messages and incomplete deliveries
remain in the evidence. If numerical failures leave a common-evidence checkpoint
unreached, the runner retains the case's tick scores and ledgers but refuses
the complete-panel summary and completion manifest. It does not drop that
owner or arena. A computation exception likewise prevents successful completion.
Freeze learner settings, seeds, programs,
observation/channel contract, query design, checkpoints, contrasts and source
hashes before evaluation. Archive legal event packets, admission/delivery
ledger, checkpoint scores, terminal snapshots, parameter summaries, per-arena
metrics and completion hashes.

Verification must reconstruct sensor ownership, message eligibility, per-hop
latency, byte charges, unique-event admission, same-arena material identity,
all paired summaries and terminal forecasts. Intermediate checkpoint summaries
are rebuilt from archived prediction primitives; independently reconstructing
every intermediate posterior requires rerunning the frozen sources. Targeted
tests must detect duplicate
and conflicting events, cross-owner posterior aliasing, future observations,
unauthorized reports, incorrect delays, private-state leakage and channel
budget violations. Replaying admitted evidence must recover the direct
learner's state. Probe scoring must leave every training state unchanged.

The empirical release will include Chromatic Field v1 learning curves, a
communication/unique-evidence view, member-versus-institution learning and
uncertainty/coverage diagnostics, with recorded-data tables and captions.
Preserve SVG/PDF/PNG exports, inspect the rendered PNGs, and record source and
output hashes. Keep society colors attached to society identity; distinguish
communication conditions by labels and markers.

The strongest permitted conclusion is a measured effect of a specified,
truthful information-routing intervention under a supplied law family and
instrumented sensing. Further claims about evolved institutions, beneficial
decisions, hidden-state inference or structural discovery need their own
interventions and separately versioned evidence.
