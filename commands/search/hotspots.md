---
description: Find the most-referenced symbols in the codebase — classes, functions, and modules with the highest connectivity
argument-hint: "[--limit <n>]"
phase_relevance: ["build", "test", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:hotspots

Rank symbols by incoming reference count to expose god-objects, coupling hotspots, and high-impact refactor targets.

## Instructions

1. **Primary path — codegraph** (when `.codegraph/codegraph.db` exists):
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
   Report the ranked list. Call out anything with an unusually high count as a likely god-object or coupling hotspot worth refactoring. Note that injected edges (provenance LIKE `'injected:%'`) are included — a heavily-dispatched agent or capability appears here too.

2. **Fallback — brain** (no `.codegraph` index):
   ```bash
   PORT="$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_brain_port.py" 2>/dev/null || echo 4242)"
   curl -s -X POST "http://localhost:${PORT}/api" \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"class function module export","limit":30}}'
   ```
   Tell the user codegraph gives a sharper, offline answer and suggest `/wicked-garden:search:index` to build it.

3. **If neither is available**: say so and suggest `/wicked-garden:search:index`.

## Example

```
/wicked-garden:search:hotspots
/wicked-garden:search:hotspots --limit 10
```
