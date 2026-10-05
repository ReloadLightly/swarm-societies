# Upstream inspection and integration decision

Inspected on 2026-10-05. Only source and documentation needed for this increment were requested; no upstream experiment dataset, model weights, JavaScript dependencies, or paper figure archive was downloaded.

## SwarmWorld

Repository: <https://github.com/lamm-mit/SwarmWorld>\
Pinned revision: `6af7ae9fa36d98b07b0492cf139658e8af1f6eab`\
Local ignored source: `.cache/upstream/SwarmWorld`\
License: Apache-2.0. No SwarmWorld source code is copied or vendored into this increment.

The focused review covered these implementation surfaces:

| Surface inspected | Finding and decision |
| --- | --- |
| `src/biofoundry/simulation.py`, `world.py`, `env.py` | Authoritative resource/action physics, local observations, and a PettingZoo wrapper. Their material/artifact schema is broader than the first resource-institution experiment requires. |
| `policies/base.py`, `policies/scripted.py`, `policies/llm.py` | Policy protocol returns action mappings from a simulator. Our candidates instead receive copied observation dictionaries, enabling stricter evaluator isolation and independent member/institution inheritance. |
| `programs.py` | Bounded artifact-controller instructions and content identities. Our units are Python decision programs; the seeds do not restrict discoverable institutions to fixed instruction recipes. |
| `events.py`, `playback.py` | Versioned traces, source/configuration checks, deterministic replay, and a separate presentation view. We use the same architectural separation with an independently authored compact JSON schema. |
| `analysis.py`, `trace_analysis.py` | Independent-seed analysis and event-grounded diagnostics inform the separation of search records, fresh-case measurement, and replay. |

Direct embedding would couple the initial experiment to substantial artifact physics, dependencies, and an action contract that lacks independently selected societies and institutions. The practical integration is architectural reuse through a new small simulator, not a SwarmWorld fork or wrapper. This enables early executable evaluations and controlled material accounting. A future SwarmWorld adapter can implement the same candidate/selection interface after this increment is complete; it is not implemented here.

Pal, Wang, and Buehler's [SwarmWorld paper, arXiv:2608.26081v1](https://arxiv.org/abs/2608.26081) provides the conceptual foundation: local observations, persistent memory/artifacts, executable inheritance, and independent consequence evaluation. Section 4.1 explicitly states that model weights remain fixed. Its within-world cultural/technological accumulation is therefore not evidence of the member-policy and institution selection added here. Our private/shared state updates remain distinct from inherited source changes across rollouts. We do not use the paper's data or reproduce its reported performance.

```bibtex
@misc{pal2026swarmworld,
  title = {SwarmWorld: Stigmergic technological evolution in societies of language-model agents},
  author = {Pal, Subhadeep and Wang, Fiona Y. and Buehler, Markus J.},
  year = {2026},
  eprint = {2608.26081},
  archivePrefix = {arXiv},
  primaryClass = {cs.AI},
  url = {https://arxiv.org/abs/2608.26081}
}
```

## Other foundations

The actual ShinkaEvolve source revision, invocation, subscription configuration, and execution evidence are documented by the engine integration and run metadata. Shinka search islands are archive partitions, not the societies in the simulated environment. See [protocol.md](protocol.md).

The read-only visual reference is <https://github.com/ReloadLightly/actir-backprop-neat>. Its README and figure-generation style inform the experiment's figure design; its numerical evidence is not reused. Specific inspected files and figure conventions are recorded with the visualization work.
