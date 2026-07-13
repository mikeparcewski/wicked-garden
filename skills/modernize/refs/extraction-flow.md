# extraction-flow — how the extractor drives estate + brain (with the mock seam)

The modernize workers never import brain or estate code. They talk to a **fixed
interface** and, in PHASE-1, a **mock implementation** of it. This ref documents
the interface (the real CLI/engine contract) and the mock seam.

## The estate surface (what the extractor + translator call)

estate is the sole authority for graph structure. In production the workers
shell its CLI; in PHASE-1 they call `scripts/modernize/_mocks.EstateClient`,
which returns canned fixtures and records writes. The interface is the six-method
`EstateClient` the Domain-Brain contract freezes:

| Method | Production CLI | Purpose |
|---|---|---|
| `read_clusters(params) -> [Community]` | `clusters --json --summary` | Full community membership (the `members:[symbol_id]` feed). The MCP `Communities` tool omits members, so the CLI is the contract. |
| `resolve(name, file?, kind?) -> [symbol_id]` | `nodes --json` / `resolve` | name → SymbolId. **A write keyed on a bare name is a silent no-op** — always resolve first. |
| `annotate(symbol_id, type, key, value, confidence, provenance, replace)` | `annotate --symbol <id> … --replace` | Typed k/v annotation (multi-valued). `--replace` = idempotent upsert; the workers always pass it so a re-index replaces rather than stacks. |
| `set_requirement(symbol_id, requirement, validated)` | `semantics <id> --requirement … --validated …` | The single canonical requirement↔symbol link. |
| `read_annotations(symbol_id) -> [Annotation]` | `annotations --symbol <id> --json` | Read back. |
| `find_by_annotation(key, value?) -> [symbol_id]` | `nodes --annotated-with K[=V] --json` | Reverse lookup. |

### The two coordinated writes per bound rule

Ported from anti-legacy's `annotate()`, both keyed by SymbolId, **neither copying
symbol structure**:

1. **Native projection into estate** (so estate queries see it): the compact
   tagged requirement string — convention `"<rule_id>|<confidence>|<provenance>|<statement>"`
   — plus `requirement_validated = 1` (RESOLVED at/above threshold) or `0`
   (RISK). Reverse lookup via `by-requirement <REQ>`.
2. **The domain-model document** row: `legacy_components[]` holds the SymbolId;
   `provenance.ref` holds the SymbolId or file#anchor. **Nothing else about the
   symbol is copied** — no name uniqueness, no file, no source text.

The traceability thread the workers must not break:
`estate node (native file/line) → requirement annotation → business_rules[].id →
legacy_components[] → crew task → UAT verdict`. A broken link is a gate failure,
not a warning.

## The brain surface (what the translator calls)

brain owns the domain-model engine + store. The translator hands brain the
assembled document and consumes its summary; it does **not** reimplement the
engine. In PHASE-1 this is `scripts/modernize/_mocks.BrainClient`:

| Method | Production | Purpose |
|---|---|---|
| `build_domain_graph(doc) -> summary` | `wicked-brain domain build --db <estate_db> --overlay annotations.jsonl` | Build `requirements_graph.json` (capability plan) with round-trip no-silent-drop. |
| `validate(doc) -> ok` | brain-side schema validation | brain rejects a `schema_version` it has no validator for — no silent best-effort. |

## Config-driven miner kind-sets (invariant 6)

The extractor must read the behavior/type/structural kind-sets from
`config.coverage.*`, **never hardcode** them. The generic modern defaults:

| Config key | Feeds | Modern default |
|---|---|---|
| `coverage.behavior_kinds` | domain actions/verbs | `["module","function","method"]` |
| `coverage.type_kinds` | domain entities/nouns | `["class","interface","struct","trait","enum","record"]` |
| `coverage.structural_kinds` | field-level nouns | `["field","variable"]` |
| `coverage.estate_behavior_kinds` | mainframe/IaC only | `[]` for a pure modern repo; `["db2_table","cics_program","step"]` on a mainframe estate |

`emit_domain_model.py` accepts a `config` dict and defaults to these — the same
document contract serves a COBOL estate and a Rust monorepo.

## The disjoint-build mock seam

`scripts/modernize/_mocks.py` is the whole point of the disjoint build: garden
builds + tests its side against fixtures while brain, estate, and crew build
theirs in parallel. The mocks:

- `EstateClient` — canned `read_clusters()` (a two-community fixture with member
  SymbolIds), `resolve()` (name → deterministic fixture SymbolId), and
  `annotate()`/`set_requirement()` that **record** calls so a test can assert the
  write happened (the anti-legacy silent-no-op scar is caught by asserting the
  recorded id is a real SymbolId, never a bare name).
- `BrainClient` — `build_domain_graph()` returns a summary
  `{domains, requirements, dropped}` and `validate()` runs the same stdlib
  draft-07 schema check brain would (against the vendored schema).

**No other-product code is imported.** When the real CLIs land, swap the mock for
a CLI-backed impl with the identical interface — the workers don't change.
