---
description: |
  Use when you need to know what would break or be affected by changing a symbol — traces
  dependents (what uses this) over the code-relationship graph, including injected edges
  (bus/dispatch/capability) that grep and a static call-graph cannot see.
  NOT for full data lineage tracing (use search:lineage) or general code search (use wicked-brain:search).
argument-hint: "<symbol> [--depth N]"
phase_relevance: ["build", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:blast-radius

Analyze what would be affected if you changed a symbol — **delegates to wicked-brain's
code-relationship graph** (`wicked-brain:graph`), which owns the unified static + injected
graph as of ADR 0004. Garden no longer maintains its own graph; it consumes brain's.

> **Scope**: `blast-radius` answers "what breaks if I change X?" (the dependents graph).
> For **data-flow tracing** (UI field → DB column or reverse), use `/wicked-garden:search:lineage`.

## Arguments
- `symbol` (required): the symbol to analyze (a file like `scripts/foo.py`, or a symbol name).
- `--depth` (optional): traversal depth (brain default applies if omitted).

## Instructions

1. **Ensure the graph is fresh** (brain builds the codegraph static graph + runs the injected-edge extractors in one pass):
   ```bash
   npx -y wicked-brain-call graph-index
   ```
   The result carries a `staleness` stamp; if `stale` is true after editing, re-run it.

2. **Resolve the symbol to a graph node id.** Node ids are `file:<relpath>` for files, or `function:<hash>` etc. for symbols. For a file, use `file:<path>` directly. For a named symbol, find its id via brain:
   ```bash
   npx -y wicked-brain-call symbols --query "<symbol>"     # or wicked-brain:lsp workspace-symbols
   ```

3. **Query blast radius from brain** (static + injected dependents in one answer — the authoritative layer):
   ```bash
   npx -y wicked-brain-call graph-blast-radius --node "file:<path-or-resolved-id>"
   ```
   The `dependents` array includes relationships grep can't see: a command that *dispatches* an agent (`injected:dispatch`), a consumer that *subscribes* to an event (`injected:bus`), an agent that *declares* a capability (`injected:capability`). Each result carries a `staleness` stamp.

4. **Fallbacks** (in order):
   - If `graph-blast-radius` returns `engine: "unavailable"`, codegraph isn't installed where brain runs — install it (`npx @colbymchenry/codegraph`) or set `WICKED_CODEGRAPH_BIN`, then `graph-index`.
   - If brain is unreachable, fall back to `wicked-brain:search` for semantic neighbors, then Grep/Glob for literal refs — and **flag that injected relationships will be MISSING** from the result.

5. Report: **dependents** (static + injected, with provenance), total blast-radius count, files affected, and the graph's staleness.

## Example
```
/wicked-garden:search:blast-radius scripts/_bus.py
/wicked-garden:search:blast-radius UserService --depth 3
```

## Notes
- The graph + queries live in **wicked-brain** now (ADR 0004); this command is a thin wrapper over `wicked-brain:graph`. For lineage (downstream dependencies) use `/wicked-garden:search:lineage`.
- Garden contributes its proprietary **archetype** edges to brain's graph via the drop-in extractor `.codegraph-extractors/archetype.mjs` (discovered by brain's registry) — so archetype→playbook relationships are in the blast radius too.
