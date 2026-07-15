---
name: wicked-garden-domain
user-invocable: true
description: |
  The FOUNDATIONAL domain-model capability: extract a codebase's domain — testable
  business rules (with confidence + provenance), entities, requirements — as a
  schema-conformant model on the estate graph. The workers annotate the store;
  wicked-core reads it and builds the requirements graph, coverage-gating
  fail-closed. Steers three fork workers.

  A shared substrate, not a modernization tool. The `modernize` archetype DERIVES
  from it; build / migrate / review / specify / explore consume the SAME domain
  model — none OWN it. Understanding a codebase's domain is upstream of almost
  everything else garden does.

  Use when: "extract the business rules / domain model from this codebase", "build
  a requirements graph from the code", "what does this system actually require",
  "reverse-engineer the domain before we build/port/migrate". Works on ANY codebase
  (modern or legacy) — the value is the domain model, not the porting.

  NOT the code transform itself (that is the archetype consuming this model). This
  skill produces the DOMAIN MODEL, not new code.
phase_relevance: ["discover", "extract", "blueprint", "plan", "specify"]
archetype_relevance: ["modernize", "build", "migrate", "review", "specify", "explore"]
---

# wicked-garden-domain

The **domain-model capability** — a foundational substrate, not a step inside one
archetype. It produces the shared **domain model** (business rules + entities +
requirements on the estate graph); the `modernize` archetype derives from it, and
build / migrate / review / specify / explore consume the same model. Understanding
a codebase's domain is upstream of building, porting, reviewing, or governing it.

**The contract in one line:** the only thing that crosses repo lines is a
document that validates against `@wicked/domain-model-schema@1.0.0` (vendored at
`vendor/domain-model.schema.json`) plus an estate `SymbolId` string. Garden
STEERS (annotates the estate store + cross-checks the built document), core
BUILDS (`wicked-core domain-graph` reads the store, builds the requirements graph,
and coverage-gates fail-closed), estate GROUNDS (owns SymbolId identity + the
graph), crew GOVERNS (drives the run). The peer CLIs are shelled via
`scripts/domain/_clients.py`, or mocked behind fixtures when absent.

## The four-way seam

```
crew GOVERNS  →  garden STEERS  →  core BUILDS  →  estate GROUNDS
(drives the run) (this skill +     (domain-graph +  (SymbolId + graph
                  3 fork workers)   coverage gate)   + Louvain clusters)
```

Garden never imports core or estate code — it shells their CLIs (argv lists, no
shell string) or mocks them. It annotates the estate store and references SymbolId
strings; core reads the store and builds + coverage-gates the requirements graph;
estate is the sole writer of graph structure.

## Routing — the three fork workers

| Ask | Worker | Produces |
|-----|--------|----------|
| Mine business rules from the estate → domain-model doc | [domain-extractor](../domain-extractor/SKILL.md) | `business_rules[]` with confidence + provenance; estate `requirement` annotations |
| Group clusters into domains → invoke core's domain-graph build | [domain-modeler](../domain-modeler/SKILL.md) | `domains{}` keyed to estate Louvain communities; `requirements_graph.json` built by `wicked-core domain-graph` |
| Threat-model the extracted model before build | [domain-coverage](../domain-coverage/SKILL.md) | pre-build threat list / RISK-flag reasons |

Dispatch a worker with `Task(subagent_type=...)` (colon back-compat) or by
loading its skill in a fork context. Run order for a full extraction:
**extractor → translator → antagonist**. Each is independently invocable.

## The document this skill emits

A `domain-model@1.0.0` document (see `vendor/domain-model.schema.json`).
Top-level `{ metadata, domains }`; every domain has `requirements` + `entities`;
every requirement carries the full field set and **≥1 business rule**; every
business rule carries a **numeric `confidence ∈ [0,1]`** and a
**`provenance{source, ref, source_kinds}`**. Full field map + the hard
invariants: [refs/domain-model-emit.md](refs/domain-model-emit.md).

Reference-not-copy: `legacy_components[]` and `provenance.ref` hold estate
**SymbolId references**, never a copy of the symbol's code, file, or line.
estate resolves them live.

## The working core slice (what ships in PHASE-1)

Garden is skills-only, but the deterministic assembly + invariant enforcement is
real code you can run and test today:

```bash
# Emit a conformant domain-model doc from mocked estate + rule inputs
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/domain/emit_domain_model.py" \
  --fixture > /tmp/domain-model.json

# Validate any doc against the vendored schema + hard invariants
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/domain/validate_domain_model.py" \
  /tmp/domain-model.json
```

- `emit_domain_model.py` — the extractor's **deterministic core**: takes a mocked
  estate cluster + a list of extracted rules and assembles a schema-conformant
  document, enforcing the hard invariants at build time (drop needs a reason,
  ≥1 rule per requirement, numeric confidence).
- `validate_domain_model.py` — a stdlib-only draft-07 subset validation against
  the vendored schema (no third-party dependency — the repo is stdlib+pytest
  only), plus the extra invariants the schema can't express (numeric confidence
  type, SymbolId-shaped references).
- `scripts/domain/_clients.py` — the selection seam: `estate_client(db)` /
  `core_client()` return CLI-backed clients when `wicked-estate` / `wicked-core`
  resolve, else the mocks. Shells the peers (argv lists, no shell string).
- `scripts/domain/_mocks.py` — the disjoint fixtures: a fake estate client
  (canned clusters + `resolve`/`annotate`) and a fake brain client (the hermetic
  doc-assembly lane). **These mock the peers; no other-product code is imported.**

## Honest scope — implemented vs stubbed

**Implemented + tested:** the vendored + pinned schema; the deterministic
document assembler; the validator (schema + hard invariants); the CLI-backed
clients (`_clients.py`) that shell the real `wicked-estate` + `wicked-core`, with
argv-construction tests + an opt-in real-CLI lane; the fixture mocks; a conformant
fixture document; the pytest suite that validates emitter output and the fixture
against the schema.

**Wired to live CLIs (`_clients.py`):** the estate surface (`resolve`,
`annotate --replace`, `semantics`, `clusters --json --summary`,
`annotations`) → `CliEstateClient`; the domain-graph build
(`wicked-core domain-graph` — reads the store, builds the requirements graph,
coverage-gates fail-closed) → `CliCoreClient`. When the peers are absent, the
selection seam falls back to `_mocks` for hermetic testing.

**Still stubbed:** the LLM rule-statement extraction step (rules are injected as
input — the "skill-supplied extractor" seam). And the real end-to-end run needs a
fully-annotated, INDEXED store (coverage == 1.0) to clear core's fail-closed gate
— that store-seeding step is the end-to-end milestone (core#28), not this slice.

## Ground in the repo's method first

Before extracting, check for **wicked-understanding** repo playbooks (the
"how to work in THIS repo" layer). A modernization lives or dies on
repo-specific wiring. If present, load the matching playbook.

## Depth

- [refs/domain-model-emit.md](refs/domain-model-emit.md) — the full field map,
  the seven hard invariants, and the SymbolId reference rule.
- [refs/extraction-flow.md](refs/extraction-flow.md) — how the extractor drives
  estate (resolve → annotate → semantics) and core (`domain-graph`), the
  `_clients.py` selection seam, and the mock lane.
- `vendor/README.md` — the vendored-schema pin + drift discipline.
