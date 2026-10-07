# Paper contract v1: how swarms learn a resource map they are depleting

**Status:** binding plan for the next paper, 8 October 2026. Prepared for Roland
from an independent review of `e699f6a`. It adopts the literature table and the
identifiability analysis in `docs/commons-v3-world-model-reframing-review-v1.md`
and replaces that document's open-ended "Next decision" section with fixed
decisions. **Changes to this contract need Roland's explicit approval** and are
recorded in §17. Implementers carry out the tickets; they do not reinterpret the
question.

## 1. Question and hypotheses

> How do swarms that learn differently (alone, by sharing extraction receipts,
> by relaying raw site evidence, or by exchanging beliefs) learn a site-by-site
> map of resource capacity that their own harvesting depletes and confounds?
> When does the resulting knowledge sustain consumption, and when does sharing
> make outcomes worse?

The independent variable is **how the swarm learns its world model**. The
dependent variables are world-model accuracy and calibration, and their
material consequences.

| Hypothesis | Prediction |
| --- | --- |
| H1, social evidence | Evidence relay (L2) learns site capacities faster than asocial learning (L0) and recovers more of the oracle's consumption. |
| H2, consequence scaling | The L2 − L0 consumption gain is larger when capacities are widely heterogeneous than when moderately heterogeneous. In the moderate world, a cautious fixed belief is nearly as good as knowledge. |
| H3, coupling | Co-located harvesting confounds regrowth evidence. Sharing extraction receipts alone (L1) therefore improves capacity estimates over L0. |
| H4, beliefs versus evidence | Belief exchange with naive fusion (L3) becomes overconfident. With a biased minority it spreads the bias and loses consumption relative to L2 at matched bytes; L2 is robust. |

Null or reversed results are reportable outcomes, not reasons to change the design.

## 2. Why this question: consequence evidence

These are scratch probes on the frozen v3 engine and frozen navigation forager:
4 seeds, 512 ticks, initial stock 0.6 of capacity. Only the capacity value seen
by the forager was altered. Heterogeneous capacity was patched in-process, not
in the repository. They are descriptive only; Ticket B must reproduce them on
the versioned engine (Gate G1). Values are the share of need met.

| Probe | Need 1.2 | Need 1.6 | Implication |
| --- | ---: | ---: | --- |
| One global capacity K=40: forager believes K=20 / 30 / 40 / 50 / 60 / 80 | 0.989 / 0.997 / 0.991 / 0.907 / 0.755 / 0.003 | 0.787 / 0.866 / 0.826 / 0.743 / 0.611 / 0.002 | Overestimating capacity is costly; underestimating is cheap. A cautious fixed belief is close to optimal, so learning one global K would be nearly inconsequential. |
| Additive regrowth, floor 0 vs 0.5 | 1.000 vs 0.999 | 0.907 vs 0.878 | Restraint is cheap insurance. With no floor, logistic regrowth collapses (0.313 / 0.062). Learning the law family is inconsequential, so it is out of scope. |
| Moderate heterogeneity (K_j in 20–60, mean 40): oracle vs best single belief | 0.986 vs 0.982 | 0.835 vs 0.799 | Little headroom. This is the internal negative control. |
| Wide heterogeneity (K_j in 10–90; the probe did not rescale to sum 640): oracle vs best single belief | 0.970 vs 0.824 | 0.866 vs 0.671 | 15–20 points of headroom even against the best fixed belief. Site-specific knowledge is first-order. |
| Sole harvesters, as a share of harvesting agent-ticks, in oracle-like arms | 0.25–0.26 | 0.33–0.37 | Most extraction transitions are confounded by other agents' harvest. |

The half-capacity floor is not the best known-law decision. At need 1.6, a floor
at 0.375 K beat 0.5 K (0.866 vs 0.826). The oracle reference therefore chooses its
floor fraction on development seeds (§6).

## 3. Positioning and claim

Nearest work, with the full table in the reframing review:
- **Model-free commons learning:** Perolat et al. 2017; Leibo et al. 2017.
- **Sustainable foraging:** Aishwaryaprajna & Lewis 2023; Payne et al. 2024.
- **Learn the ecology, then harvest:** Ju et al. 2023/2025; Walters & Hilborn's adaptive management.
- **Information in commons:** Dubois et al. 2020; Kuusela & Laiho 2020.
- **Collective inference in swarms:** Heins 2026; Legarda Herranz et al. 2026; Madin et al. 2026; Chin & Pinciroli 2025; Zakir et al. 2026.
- **Added to the review's table:**
  - Wu et al. 2026, *Exact Fusion and Coordinated Exploration in Multi-Robot Active Inference* (arXiv 2609.17384). Exact evidence-increment fusion. Its **Assumption 1: "No robot's action enters another robot's transition or observation model."** Consumable resources enter only the task term, and its foraging variant does not deplete sites.
  - Farr et al. 2026, *The Cost of Consensus: Malignant Epistemic Herding…* (arXiv 2605.06988). Repeated belief fusion drives confident wrong consensus in static target search.

**Claim, with no "first" in it.** Collective-inference methods for swarms assume
that each agent's evidence is unaffected by the others' actions. In a
regenerating commons this fails: co-located harvesting enters every observer's
regrowth evidence, and the swarm consumes the field it is mapping. We measure how
evidence regimes perform under this coupling and what their epistemic errors cost
materially. The regimes are no sharing, extraction receipts, relayed evidence with
provenance, and belief exchange. The material costs are lost consumption,
starvation next to food and local collapse. Heterogeneity of the world is the
consequence lever.

**Literature closure, time-boxed to one day:**
- Full text of Kuusela & Laiho 2020, Aishwaryaprajna & Lewis 2023, Mills & Lewis 2025, Wu et al. 2026 and Farr et al. 2026.
- One targeted search for decentralized learning of site-specific capacity or regrowth by foragers.
- Output: a related-work draft of at most one page.
- If a paper already runs the coupled design, stop and report to Roland before Ticket C.

## 4. World (Ticket A)

- **Engine.** New versioned physics module, e.g. `commons_v3/engine_sites_v1.py`, version `commons-v3-physical-sites-v1`. It is a copy of the frozen engine with **per-site capacity K_j and per-site initial stock**. Everything else is unchanged: logistic law, r = 0.24, recovery 0.02, weather multiplier ±10%, harvest and movement costs, local messages. Do not edit `engine.py`.
- **Parity test.** With all K_j = 40 and v1 initial stocks, the frozen forager reproduces engine-v1 trajectories and digests exactly on stored seeds.
- **Capacity worlds.** Both sum to 640, so total maximum sustainable yield is equal. Drawn per arena seed:
  - moderate: {20, 30, 40, 50, 60} × 3 plus {40}, shuffled over the 16 sites;
  - wide: {10, 20, 40, 60, 90} × 3 plus {40}, rescaled to sum 640, shuffled.
- **Initial stock.** S0_j = u_j · K_j with u_j ~ U(0.3, 0.9), independent per site. The distribution is declared to agents.
- **Demand.** Need 1.2 (about 74% of total maximum sustainable yield) and 1.6 (about 99%).
- **Population and horizon.** 24 agents, 16 sites, 12×12 grid, 512 ticks. The final quarter is also reported.

## 5. Observation and evidence contract

**Hidden from agents:**
- K_j;
- weather realizations;
- other agents' realized harvests, unless received in a message;
- all evaluator state.

**Declared to agents:**
- logistic law, r = 0.24, recovery c = 0.02, weather multiplier w ~ U(0.9, 1.1);
- the initial-stock rule;
- a common prior on each K_j: log-uniform on [8, 100]. Agents do not know which world condition they are in.

**Observation contract v2:** site observations drop `capacity` and anything derived
from it. Agents still see stock, coordinates, peer positions, their own
inventory and messages.

**Clean transition.** Observer i at site j sees S_t and S_{t+1}. Either:
- no other agent occupied site j's cell during extraction at t, which is checkable from the start-of-(t+1) headcount; or
- receipts cover every co-located agent.

Then z_t = S_t − H_t and G_t = S_{t+1} − z_t.

**Likelihood (exact, per site):**
- Potential growth P(z; K) = r·z·(1 − z/K) + c.
- Realized growth G = min(K − z, w·P).
- Unclipped: G is uniform on [0.9P, 1.1P].
- Clipped (stock reaches capacity): a point mass at S_{t+1} = K.
- Hard constraint: K ≥ the largest stock ever observed at j.

**Identifiability.** With r, c and the weather amplitude known, K_j is identified by:
- clean transitions at stocks where ∂P/∂K = r·z²/K² is not negligible, i.e. high stock;
- saturation.

Low-stock transitions are weakly informative, and contention removes clean
transitions. These bottlenecks are exactly what the arms manipulate.

**Learner.** An exact grid posterior per site over K: log-spaced on [8, 100],
about 400 points. Do not reuse `RenewalSMC` or the v1 calibration result.
Do reuse two principles from `world_model_v1`:
- provenance and deduplication: one physical event is one evidence item, keyed by (site, tick);
- prequential/CRPS scoring for optional predictive checks.

## 6. Decision layer

- **Base controller.** The frozen `ForagerPolicy` (navigation v1, reserve 2, floor fraction 0.5, `net_yield`). No edits to its code.
- **Belief-injection wrapper.** A subclass or wrapper in a new module. Each tick, before calling the forager, it sets the capacity seen for every visible site to K̃_j = (φ / 0.5) · Q_q(K_j | evidence). It also refreshes `records[j]["capacity"]` for remembered sites. The effective floor is then φ · Q_q.
- **Tuning.** φ ∈ {0.375, 0.5} and quantile q ∈ {0.25, 0.5} are chosen once on development seeds. The oracle uses the same φ with the true K_j.
- **Why knowledge is consequential.** Beliefs change restraint (the floor) and allocation (the forager's site-service scores) without any engineered reward.

## 7. Arms: the different swarms

| Arm | Learning and communication |
| --- | --- |
| R-oracle | True K_j through the same wrapper. Knowledge ceiling for this decision rule. |
| R-fixed | Best single belief for all sites, chosen on development seeds from {20, 30, 40}. This is the competitor that does nothing clever. |
| R-greedy | Floor 0. Collapse anchor. |
| L0 asocial | Own clean transitions, saturation and maximum-stock bounds only. |
| L1 receipts | Co-located agents message their realized harvest each tick, which makes shared-site transitions clean. No relaying. |
| L2 evidence relay | L1, plus agents relay site-indexed clean transition records (site, tick, z, S_{t+1}) to visible neighbours. Receivers deduplicate by (site, tick) and update exactly. Evidence spreads only through local encounters. |
| L3 belief exchange | L1, plus agents send site-indexed posterior summaries (median and interquartile range). Receivers multiply them into their own posterior without removing shared components: the common double-counting choice. |
| L2-biased, L3-biased | 4 of 24 agents start with a prior log-uniform on [50, 100]. They act on and share their beliefs truthfully. |

- **Message settings.** All communicating arms use `max_messages = 4` (declared). The engine's default byte cost of 0.001 per byte is unchanged.
- **Matched bytes.** L2 and L3 share one message schedule and byte budget, e.g. at most one message of at most 96 bytes every 4 ticks, plus receipts.

## 8. Conditions

The design is 2 heterogeneity levels (moderate, wide) × 2 demand levels (1.2, 1.6) = 4 cells. The moderate world is the internal negative control for H2.

Pre-declared fallback (G3 only): make r a single unknown global parameter with a 2-D posterior.

## 9. Measurements

- **Epistemic:**
  - per-site |log(median posterior / true K_j)| over time;
  - 90% interval coverage;
  - time until the median is within 10% of K_j;
  - fraction of evidence that is clean;
  - consensus versus accuracy: between-agent dispersion against error, where confident wrong consensus is the herding signature.
- **Material:**
  - share of need met, whole run and final quarter;
  - **starvation next to food:** shortfall while standing on a site whose stock exceeds the oracle floor;
  - local collapse: site-ticks below 10% of capacity;
  - communication bytes and cost.
- **Distribution:** per-agent consumption spread; biased agents versus the rest.

## 10. Primary contrasts and statistics

All contrasts are paired by seed: the same world and starting positions for every arm. There are 32 fresh evaluation seeds. Five primary contrasts, with Holm correction across them:

| Contrast | Measure | Condition |
| --- | --- | --- |
| P1 | L2 − L0, share of need | wide, need 1.6 |
| P2 | (L2 − L0)_wide − (L2 − L0)_moderate, share of need | need 1.6 |
| P3 | L1 − L0, capacity error at tick 128 | wide |
| P4 | L3-biased − L2-biased, share of need | wide, need 1.6 |
| P5 | L3 − L2, 90% interval coverage | wide |

Everything else is descriptive, with ordinary 95% intervals. No large simultaneous-interval families.

## 11. Gates and kill criteria

| Gate | Condition | If it fails |
| --- | --- | --- |
| G0 | Literature closure finds no identical prior design. | Report to Roland before Ticket C. |
| G1 | Ticket B, 4 development seeds, versioned engine: R-oracle − R-fixed ≥ 0.08 of need in the wide world at need 1.6. | Stop and report. |
| G2 | Simulation-based calibration of the site posterior passes on at least 500 synthetic transitions, including clipped ones. | Fix the learner before any arm runs. |
| G3 | Learning is not trivial: if L0 reaches R-oracle consumption within 0.02 by tick 64 in all four cells, sharing cannot matter. | Use the single pre-declared fallback (§8); if still trivial, stop. |
| G4 | The engine parity test passes. | Fix the engine before Ticket B. |

One documented revision is allowed after the development pass, using 4 more development seeds. Then the design freezes once.

## 12. Tickets

| Ticket | Work | Gate |
| --- | --- | --- |
| A | `engine_sites_v1`, observation contract v2, parity tests. | G4 |
| B | Consequence map: R-oracle, R-fixed and R-greedy × 4 cells × 4 development seeds. Choose φ for the oracle and the single belief for R-fixed. | G1 |
| C | Exact site posterior; clean-transition extraction from legal observations only; calibration; L0 wrapper. | G2 |
| D | Message records (receipts, evidence with (site, tick) deduplication, beliefs); L1–L3; biased minority; development pass; choose q. | G3 |
| E | Freeze design, seeds and contrasts. Run the 32-seed evaluation and replay. Produce three figures and the README as a paper draft. | — |

Use the existing archive and replay tooling as it is. Add no new audit or
publication layers.

## 13. Figures

1. **Learning.** Capacity error and coverage over time by swarm, wide versus moderate, with the clean-evidence fraction as an inset.
2. **Consequences.** Share of need met by swarm and condition, against the oracle, best-fixed and greedy references (headroom recovered).
3. **When sharing hurts.** Belief exchange versus evidence relay under the biased minority: consensus–accuracy scatter, consumption, and starvation next to food.

## 14. Timeline

| Dates | Work |
| --- | --- |
| Oct 8–9 | Literature closure and Ticket A |
| Oct 10–11 | Ticket B (G1) |
| Oct 12–16 | Ticket C (G2) |
| Oct 17–23 | Ticket D and development pass (G3) |
| Oct 24–30 | Optional revision, then freeze |
| Nov 1–10 | Evaluation and figures |
| Nov 11–30 | README as paper and an 8-page ALIFE draft |

The ALIFE 2027 deadline is not yet announced; ALIFE 2026's full-paper deadline was 12 April 2026.

## 15. Out of scope (parked, not deleted)

- exclusion, charters and institutions;
- the tipping bank;
- imitation and evolution;
- storage and capability shocks;
- learning the law family;
- model calls and ShinkaEvolve.

Possible follow-up after this paper: ShinkaEvolve over fusion and communication rules, with this paper's arms as baselines.

## 16. Process rules

- Tickets run in order. Each ends with passing tests and a short PROGRESS.md entry.
- Reviews happen only at G1, after the development pass (G3), before the freeze and after evaluation.
- Any deviation from this contract needs Roland's approval and an entry in §17.

## 17. Contract change log

(none)
