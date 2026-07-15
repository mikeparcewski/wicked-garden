# extraction-flow — how the extractor drives estate + core (with the mock seam)

The modernize workers never import estate or core code. They talk to a **fixed
interface** and — depending on whether the peer CLIs are installed — either the
**real CLI** (`scripts/modernize/_clients.py`) or, hermetically, a **mock**
(`scripts/modernize/_mocks.py`). This ref documents the interface (the real
CLI/engine contract) and the mock seam.

## Which implementation runs (the seam)

`scripts/modernize/_clients.py` picks the backing at call time, mirroring
`scripts/_loom.py`'s precedence:

- `estate_client(db)` → the CLI-backed `CliEstateClient` when **`wicked-estate`**
  resolves (`WICKED_ESTATE_BIN` env → config.json `tool_preferences.wicked-estate`
  → PATH → `node_modules/.bin`) **and** a store path is given; else the
  fixture-backed `_mocks.EstateClient`.
- `core_client()` → the CLI-backed `CliCoreClient` when **`wicked-core`** resolves
  (`WICKED_CORE_BIN` → config.json `tool_preferences.wicked-core` → PATH →
  `node_modules/.bin`); else `None`, and the caller falls back to the hermetic
  `_mocks.BrainClient` + `emit_domain_model` doc-assembly lane. Set-but-empty
  `WICKED_*_BIN` is the kill-switch (force mock).

## The estate surface (what the extractor + translator call)

estate is the sole authority for graph structure. In production the workers shell
its CLI (`CliEstateClient`); hermetically they call `_mocks.EstateClient`, which
returns canned fixtures and records writes. Same six method names either way:

| Method | Production CLI | Purpose |
|---|---|---|
| `read_clusters(params) -> [Community]` | `clusters --json --summary` | Full community membership (the `members:[symbol_id]` feed). The MCP `Communities` tool omits members, so the CLI (with `--summary`, for the object shape) is the contract. |
| `resolve(name, file?, kind?) -> [symbol_id]` | `resolve <name> --json [--file EXACT] [--kind]` | name → SymbolId. Returns an **object array**; the client extracts each `.symbol_id`. `--file` is **exact `location.file` equality**, not a basename. **A write keyed on a bare name is a silent no-op / silent fan-out** — always resolve first. |
| `annotate(symbol_id, type, key, value, confidence, provenance, replace)` | `annotate --symbol <id> --type … --key … --value … [--confidence] [--provenance] --replace` | Typed k/v annotation (multi-valued). The client **always** passes `--symbol` (a bare name fans out to every search hit) and **always** `--replace` (the CLI defaults to APPEND, which stacks duplicate rows across re-index runs). |
| `set_requirement(symbol_id, requirement, validated)` | `semantics <id> --requirement … --validated true\|false` | The single canonical requirement↔symbol link (node_semantics — a **separate** subcommand from `annotate`). |
| `read_annotations(symbol_id) -> [Annotation]` | `annotations --symbol <id> --json` | Read back. **Must** use `--symbol` — the positional `annotations <name>` form name-*searches* and returns an array, so a SymbolId there matches nothing and yields `[]` silently. `--symbol` returns the single-symbol object `{symbol, annotations[]}`. |
| `find_by_annotation(key, value?) -> [symbol_id]` | *(no CLI verb)* | Reverse lookup. **Not available on the CLI-backed path** — there is no reverse-annotation verb, and the real extractor resolves forward (name → SymbolId → annotate), so `CliEstateClient.find_by_annotation` raises. Mock-lane only. |

### The two coordinated writes per bound rule

Ported from anti-legacy's `annotate()`, both keyed by SymbolId, **neither copying
symbol structure**. On the real CLI each field is a **separate argument** — there
is no pipe-packed string:

1. **Native projection into estate** (so estate queries see it): a typed
   annotation `annotate(symbol_id, type=<t>, key=<rule_id>, value=<statement>,
   confidence=<c>, provenance=<p>, replace=True)`, where `type` is
   `"business_rule"` when the rule is RESOLVED (confidence at/above the threshold)
   or `"risk"` when it is below threshold.
2. **The canonical requirement link**: `set_requirement(symbol_id,
   requirement=<statement>, validated=<resolved>)` (`semantics`). This is what the
   later `wicked-core domain-graph` read counts toward front-half coverage.

The traceability thread the workers must not break:
`estate node (native file/line) → requirement/annotation → business_rules[].id →
legacy_components[] → crew task → UAT verdict`. A broken link is a gate failure,
not a warning.

## The core surface (owns doc assembly — the inversion)

**core owns the domain-model build.** The translator does **not** hand core an
assembled document; it annotates the estate store (via the estate surface above),
then invokes core, which **reads the store and builds `requirements_graph.json`
itself**. `CliCoreClient`:

| Method | Production | Purpose |
|---|---|---|
| `domain_graph(db, out, coverage?) -> doc` | `wicked-core domain-graph --db <db> --out requirements_graph.json [--coverage F]` | Reads the annotated store, **recomputes front-half coverage**, and builds the capability plan. **Fails closed** (writes nothing, non-zero exit) when coverage < 1.0 — so every behavior-bearing node must be annotated first. A supplied `--coverage` file is an optional cross-check that must agree. |
| `coverage(db, out) -> report` | `wicked-core coverage --db <db> --out coverage.json` | Emit the store's front-half coverage report (optional — `domain_graph` recomputes internally). |

There is **no `--overlay`** and **no doc-in/summary-out** shape: the store is the
input, the built doc is the output. Garden's `validate_domain_model.py` then runs
as a **consumer-side cross-check** on core's output against the vendored schema.

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
document contract serves a COBOL estate and a Rust monorepo. (These mirror
`wicked-core`'s `CoverageConfig.behavior_other_tags`; core is the coverage
authority on the real path.)

## The disjoint-build mock seam

`scripts/modernize/_mocks.py` remains the hermetic lane: garden builds + tests
its side against fixtures while estate and core build theirs. The real path
(`_clients.py`) shells the peer CLIs — argv lists, never a shell string — so the
"imports NO other-product code" doctrine holds either way. The mocks:

- `EstateClient` — canned `read_clusters()` (a two-community fixture with member
  SymbolIds), `resolve()` (name → deterministic fixture SymbolId), and
  `annotate()`/`set_requirement()` that **record** calls so a test can assert the
  write happened (the anti-legacy silent-no-op scar is caught by asserting the
  recorded id is a real SymbolId, never a bare name).
- `BrainClient` — the **hermetic doc-assembly lane** only (`build_domain_graph(doc)`
  returns a `{domains, requirements, dropped}` summary and `validate()` runs the
  stdlib draft-07 schema check). This does **not** model the real core flow (which
  reads the store); it exists so `emit_domain_model.py` can assemble + validate a
  document with no peers present. On the real path, `core_client()` returns a
  `CliCoreClient` and this stand-in is not used.

**No other-product code is imported.** When the peer CLIs are present the
`_clients.py` factories swap in the CLI-backed impls — the workers don't change.
