# Related work — world-model paper v1

Draft under [contract §3](paper-contract-world-models-v1.md), 8 October 2026.

Learning sustainable extraction and territorial behavior has precedents in
[Perolat et al.](https://arxiv.org/pdf/1707.06600v2) and
[Leibo et al.](https://arxiv.org/pdf/1702.03037v1). The sustainable-foraging line
adds temporal learning and reflective governance:
[Payne et al.](https://arxiv.org/html/2407.01501v2) improve single-agent behavior
without reliably solving the group problem. Explicit ecological models are
also established in adaptive management and
[Ju et al.'s fishery controller](https://doi.org/10.1111/exsy.13324).
Our question concerns how locally interacting learners acquire a capacity map
while their extraction changes the observations used to infer it.

Information is not automatically beneficial. [Kuusela and Laiho](https://doi.org/10.1016/j.jeem.2019.102287)
analyze costly public signals followed by strategic emissions: information
investment can exceed or fall short of cooperative levels. Their two-stage
model does not infer regenerative site capacities from local transitions.
[Dubois et al.](https://doi.org/10.1371/journal.pone.0240212) likewise show why
information disclosure and extraction must be evaluated together.

Recent collective-inference work supplies close algorithmic comparisons.
[Wu et al.](https://arxiv.org/html/2609.17384v1) distinguish naive fusion from
counting evidence increments once and compare exploration and information
controls. Their Assumption 1 excludes another robot's action from each robot's
transition and observation models. Their learned-yield foraging variant samples
fixed site distributions without consumption; other tasks do contain one-use
items. [Farr et al.](https://arxiv.org/html/2605.06988v1) demonstrate erroneous
consensus during static-target search, using entropy-weighted additive fusion
and communication congestion. We therefore do not claim that every aspect of
these systems is uncoupled. The present comparison targets the specific coupling
between others' harvesting and ecological transition evidence, and contrasts
receipts, provenance-preserving raw evidence and multiplicative belief fusion.

One targeted search also identified [Kilpatrick and El Hady](https://arxiv.org/html/2607.29476v1):
a single Bayesian forager learns patch richness while consumption depletes it,
including replenishment and consequences of heterogeneity. This directly
precedes learning a resource map through exploitation, but lacks co-harvester
confounding and social fusion. [Falcón-Cortés et al.](https://arxiv.org/pdf/1901.07465)
share memories of fixed-profitability sites; [van der Post et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC2728903/)
combine social diet learning with depletion and annual renewal, rather than
capacity posteriors and receipt-based identification. These precedents prevent
claiming that collective learning under depletion is itself new.

The intended contribution is the contracted comparison of evidence regimes
under regenerative extraction coupling, with separate capacity accuracy,
calibration and material outcomes. No identical comparison was identified in
the inspected sources; this is a bounded search result, not proof of priority.

Roland approved closing this bounded pass using abstracts and public information
for the two unavailable full texts (contract §17). The
[official ALIFE 2023 abstract](https://2023.alife.org/programme/) describes
reflective governance of renewable resources; the
[Mills–Lewis author abstract](https://www.trustworthyai.ca/publication/think-before-you-act-popperian-expectations-for-adaptive-agents/)
describes causal expectations from internal simulation. Their detailed
experiments remain unchecked. Wu, Farr and the accessible Kuusela–Laiho
manuscript sections support the distinctions above; inaccessible texts are not
counted as negative evidence for overlap. The bounded G0 search found no
identical design in the inspected material; the two full texts remain pending
for later checking when supplied.
