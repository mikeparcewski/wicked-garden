---
description: |
  Use when you need to know what would break or be affected by changing a symbol — traces both
  dependencies (what this uses) and dependents (what uses this) via the graph index.
  NOT for full data lineage tracing (use search:lineage) or general code search (use wicked-brain:search).
argument-hint: "<symbol> [--depth N]"
phase_relevance: ["build", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:blast-radius

Analyze what would be affected if you changed a symbol. Shows both what this symbol depends on and what depends on it.

> **Scope**: `blast-radius` answers "what breaks if I change X?" — impact of changing a symbol (dependents graph).
> For **data flow tracing** (UI field → DB column or reverse), use `/wicked-garden:search:lineage` instead.

## Arguments

- `symbol` (required): The symbol to analyze
- `--depth` (optional): How deep to traverse dependencies (default: 2)

## Instructions

1. **Query the codegraph graph** for static + injected dependents (the authoritative layer — covers what grep can't see):
   ```bash
   # Static refs (imports/calls/instantiations) resolved by the engine:
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_codegraph.py" 2>/dev/null  # shim is library-only; run the CLI:
   codegraph impact <symbol> --json   # or: npx -y @colbymchenry/codegraph@latest impact <symbol> --json

   # INJECTED relationships grep + the static graph miss (bus producer→consumer,
   # command→agent dispatch, agent→capability) — read straight from the graph DB:
   python3 - "$SYMBOL" <<'PY'
   import sqlite3, sys, pathlib
   sym = sys.argv[1]
   db = pathlib.Path(".codegraph/codegraph.db")
   if not db.exists():
       print("no index — run `codegraph index` first"); raise SystemExit
   c = sqlite3.connect(str(db))
   # dependents reaching this symbol's file via any injected edge
   rows = c.execute(
     "SELECT source, target, provenance, metadata FROM edges "
     "WHERE provenance LIKE 'injected:%' AND (source LIKE ? OR target LIKE ?)",
     (f"%{sym}%", f"%{sym}%")).fetchall()
   for r in rows: print(r)
   c.close()
   PY
   ```
   `codegraph impact` gives static dependents; the `injected:%` query adds bus/dispatch/capability edges (materialized by `scripts/codegraph/inject_edges.py`, `inject_dispatch_edges.py`, `inject_capability_edges.py`). Union both — a complete blast radius needs the injected layer, since a command that *dispatches* an agent or a consumer that *subscribes* to an event has no literal reference for grep to find.

2. **Cross-reference via brain** (semantic neighbors the graph may not name):
   ```bash
   PORT="$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_brain_port.py" 2>/dev/null || echo 4242)"
   curl -s -X POST "http://localhost:${PORT}/api" \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<symbol>","limit":30}}'
   ```
   Use matching chunks to corroborate the dependent set.

3. **If neither graph nor brain is available**: Use Grep and Glob to trace literal references only — and flag that injected relationships (bus/dispatch/capability) will be MISSING from the result. Suggest `codegraph index` + the inject extractors, or `wicked-brain:ingest`, for a complete picture.

4. Report the impact assessment:
   - **Dependencies** (outgoing): What this symbol uses/imports
   - **Dependents** (incoming): What uses this symbol — static (from `codegraph impact`) AND injected (from the `injected:%` edges)
   - Total blast radius count
   - Files affected

## Example

```
/wicked-garden:search:blast-radius DatabaseConnection --depth 3
/wicked-garden:search:blast-radius UserService
```

## Use Cases

- **Pre-refactoring**: Know what will break before changing code
- **Safe changes**: Identify low-risk symbols to modify
- **Tech debt prioritization**: Focus on high-impact components

## Notes

- **Requires a codegraph index**: run `codegraph index` (writes `.codegraph/codegraph.db`), then materialize the injected edges (`scripts/codegraph/inject_edges.py`, `inject_dispatch_edges.py`, `inject_capability_edges.py`) so the `injected:%` query returns bus/dispatch/capability dependents. Without an index, the graph steps no-op and you fall back to grep (literal refs only).
- Deeper depth = more complete but slower analysis
- For data lineage tracing (UI → DB), use `/wicked-garden:search:lineage` instead
