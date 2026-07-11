# Hotspots — find the most-referenced symbols

Rank symbols by incoming reference count to expose god-objects, coupling
hotspots, and high-impact refactor targets.

**Arguments**: `--limit <n>` (optional): number of results (default 25).

## Instructions

1. **Freshness** — ensure the graph is current with the search skill's `index`
   action (brain's `graph-index` builds the codegraph graph + injected edges
   and reports a `staleness` stamp). The ranking below reads the graph DB it
   produces; if it's stale, re-run the index.
2. **Primary path — read the graph DB** brain built (`.codegraph/codegraph.db`, when present):
   ```bash
   python3 - <<'PY'
   import sqlite3, pathlib
   db = pathlib.Path(".codegraph/codegraph.db")
   if not db.exists():
       print("no index — run `search:index` first"); raise SystemExit
   c = sqlite3.connect(str(db))
   # incoming edges per target = how heavily referenced a symbol is.
   # Exclude 'contains' (structural nesting, not a real reference) and self-loops.
   rows = c.execute(
     "SELECT target, COUNT(*) AS refs FROM edges "
     "WHERE kind != 'contains' AND source != target "
     "GROUP BY target ORDER BY refs DESC LIMIT 25").fetchall()
   for tgt, n in rows:
       node = c.execute("SELECT name, kind, file_path FROM nodes WHERE id=?", (tgt,)).fetchone()
       label = (node[0] if node else tgt)
       kind  = (node[1] if node else "?")
       print(f"{n:4d}  {kind:10s} {label}")
   c.close()
   PY
   ```
   Report the ranked list. Call out anything with an unusually high count as a
   likely god-object or coupling hotspot worth refactoring. Note that injected
   edges (provenance LIKE `'injected:%'`) are included — a heavily-dispatched
   agent or capability appears here too.

3. **Fallback — brain** (no `.codegraph` index):
   ```bash
   PORT="$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_brain_port.py" 2>/dev/null || echo 4242)"
   curl -s -X POST "http://localhost:${PORT}/api" \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"class function module export","limit":30}}'
   ```
   Tell the user codegraph gives a sharper, offline answer and suggest the
   search skill's `index` action to build it.

4. **If neither is available**: say so and suggest the search skill's `index`
   action.

## Example

```
hotspots
hotspots --limit 10
```
