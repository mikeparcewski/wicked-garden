# Estate memory scopes, kinds, and tiers

Reference for the `wicked-garden-mem` actions and the mem fork workers. The
authoritative engine-side definitions live in wicked-estate
(`wicked-estate-memory-core`: `Scope`, `MemKind`, `Tier`); this page is the
agent-facing summary so callers pass well-formed arguments.

## Scopes — hierarchical `kind:id` paths

A scope is a slash-separated path of `kind:id` segments, most-general first:

```
project:wicked-garden
org:acme/agent:claude
brain:wicked-garden/doc:4f2a91
project:wicked-estate/session:2026-08-11
```

Rules of thumb:

- **Store** under the narrowest scope that still makes the memory findable.
  The backend defaults to `project:<cwd-basename>` — right for repo-scoped
  work. Session-specific scratch can add a `/session:<id>` segment.
- **Recall** uses one of two filters (mutually exclusive on the wire):
  - `scope_prefix` — subtree match: every memory whose scope equals the
    prefix or descends from it. `scope_prefix: ""` = the root subtree =
    **everything**. This is the recall-everything convention the brain
    migration standardized on.
  - `scope` — estate's ancestor-visible inheritance: memories at this scope
    plus those inherited from ancestor scopes.
- **Erase** (`memory.erase`) takes `scope_prefix` and deletes the whole
  subtree. The backend's kind-guard requires at least one `kind:id` segment;
  the root erase needs `confirm_erase_all: true`.

### Brain-migrated memories

The wicked-brain retirement (Phase 5-S7) migrated brain memories into estate
under leaf scopes shaped `brain:<project>/doc:<id>`. They are ordinary
memories: the default `scope_prefix: ""` recall reaches them, and a
`scope_prefix: "brain:<project>"` targets just that legacy subtree (useful
for review or cleanup).

## Kinds (what a memory IS) and tiers (its lifecycle region)

| Kind | Default tier | Store when… |
|------|--------------|-------------|
| `fact` | `semantic` | a decision, gotcha, or stable distilled fact ("we chose X because Y") |
| `skill` | `procedural` | a pattern, convention, or how-to that gets reinforced by use |
| `episode` | `episodic` | a timestamped event ("the deploy broke when…") |
| `entity` | `semantic` | a profile of a person/system/component |
| `working` | `working` | session-local scratch; volatile, capacity-bounded |
| `archive` | `archival` | cold storage; normally reached via consolidation, not direct store |

Tiers (`working` / `episodic` / `semantic` / `procedural` / `archival`) are
regions of one graph with lifecycle policy — not separate stores. Recall
weights them (semantic/working strongest, archival weakest). Pass `tier`
only to override the kind's default; the table's mapping is right for
almost every store.

### Mapping the old brain vocabulary

Brain's memory types map onto estate kinds as follows (used by
`wicked-garden-mem-capture`):

| Brain type | Estate kind | Tier |
|------------|-------------|------|
| decision | `fact` | `semantic` |
| pattern / procedural | `skill` | `procedural` |
| preference | `fact` | `semantic` |
| gotcha | `fact` | `semantic` |
| discovery | `episode` | `episodic` |

Memory/knowledge content that quotes an estate SymbolId minted before the
2026-08 id-scheme migration may be dangling — when a cited SymbolId fails to
resolve in the graph, fall back to the estate MCP `SearchEntity` tool by name.

## Store resolution (which DB answers)

The estate MCP binary resolves its domain stores per-process:
`WICKED_MEMORY_DB` / `WICKED_KNOWLEDGE_DB` env overrides, else
`~/.wicked/memory.db` and `~/.wicked/knowledge.db`. Tests point these at
scratch paths; normal sessions inherit the user's real stores. The shim
(`scripts/_estate_client.py`) is fail-open — a missing binary or store
degrades to `ok: false`, never a crash.
