---
name: wicked-garden-modernize
user-invocable: true
description: |
  Domain router for the modernize archetype's rule-extraction path: turn a
  legacy estate into a schema-conformant domain-model document (business rules
  with confidence + provenance, entities, requirements) that brain validates and
  stores and crew gates on coverage. Steers three fork workers.

  Use when: "extract the business rules from this legacy codebase", "build a
  domain model / requirements graph from the estate", "reverse-engineer what
  this system does before we port it", "modernize" / "port from <legacy stack>"
  and the ask is the rules-and-domains extraction half (not the code transform).

  NOT for in-place expand-contract shape change (that is migrate); NOT the target
  code transform itself (that is the code-modernization transform skills). This
  skill produces the DOMAIN MODEL, not the new code.
phase_relevance: ["discover", "extract", "blueprint"]
archetype_relevance: ["modernize"]
---

# wicked-garden-modernize

The **rule-extraction spine** of the `modernize` archetype. Where the archetype
playbook (`skills/archetype/refs/modernize.md`) covers the full
discover→…→cutover shape, this skill owns the piece that produces the shared
**domain-model document** — the artifact that crosses every repo boundary in the
Domain-Brain contract.

**The contract in one line:** the only thing that crosses repo lines is a
document that validates against `@wicked/domain-model-schema@1.0.0` (vendored at
`vendor/domain-model.schema.json`) plus an estate `SymbolId` string. Garden
STEERS (emits + validates the document), brain EQUIPS (owns the schema + engine
+ stores), estate GROUNDS (owns SymbolId identity + the graph), crew GOVERNS
(gates on coverage). This skill mocks the other three behind fixtures.

## The four-way seam

```
crew GOVERNS  →  garden STEERS  →  brain EQUIPS  →  estate GROUNDS
(coverage gate)  (this skill +      (domain-model    (SymbolId + graph
                  3 fork workers)    engine + store)   + Louvain clusters)
```

Garden never imports brain or estate code. It emits a document and references
SymbolId strings; brain validates + stores; estate is the sole writer of graph
structure.

## Routing — the three fork workers

| Ask | Worker | Produces |
|-----|--------|----------|
| Mine business rules from the estate → domain-model doc | [modernize-extractor](../modernize-extractor/SKILL.md) | `business_rules[]` with confidence + provenance; estate `requirement` annotations |
| Group clusters into domains → drive brain's domain engine | [modernize-translator](../modernize-translator/SKILL.md) | `domains{}` keyed to estate Louvain communities; `requirements_graph.json` via brain |
| Threat-model the extracted model before build | [modernize-antagonist](../modernize-antagonist/SKILL.md) | pre-build threat list / RISK-flag reasons |

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
  "${CLAUDE_PLUGIN_ROOT}/scripts/modernize/emit_domain_model.py" \
  --fixture > /tmp/domain-model.json

# Validate any doc against the vendored schema + hard invariants
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/modernize/validate_domain_model.py" \
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
- `scripts/modernize/_mocks.py` — the disjoint fixtures: a fake estate client
  (canned clusters + `resolve`/`annotate`) and a fake brain client. **These mock
  the other three products; no other-product code is imported.**

## Honest scope — implemented vs stubbed (PHASE-1)

**Implemented + tested:** the vendored + pinned schema; the deterministic
document assembler; the validator (schema + hard invariants); the fixture
mocks; a conformant fixture document; the pytest suite that validates emitter
output and the fixture against the schema.

**Stubbed / mocked (the cross-repo seams):** the LLM rule-statement extraction
step (rules are injected as input — the "skill-supplied extractor" seam); the
real estate CLI (`clusters --json --summary`, `resolve`, `annotate`,
`semantics`) — replaced by `_mocks.EstateClient`; the real brain engine
(`wicked-brain domain build`) — replaced by `_mocks.BrainClient`. Wiring these
to the live CLIs is the next phase; the interfaces are fixed by the contract so
each side builds disjoint.

## Ground in the repo's method first

Before extracting, check for **wicked-understanding** repo playbooks (the
"how to work in THIS repo" layer). A modernization lives or dies on
repo-specific wiring. If present, load the matching playbook.

## Depth

- [refs/domain-model-emit.md](refs/domain-model-emit.md) — the full field map,
  the seven hard invariants, and the SymbolId reference rule.
- [refs/extraction-flow.md](refs/extraction-flow.md) — how the extractor drives
  estate (resolve → annotate → semantics) and brain, with the mock seam.
- `vendor/README.md` — the vendored-schema pin + drift discipline.
