---
description: Build/refresh the code-intelligence index (semantic brain + structural codegraph)
argument-hint: "<path>"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:index

Refresh the two code-intelligence layers the other `search:*` commands query:

- **semantic** (wicked-brain) — concept/symbol search, `wicked-brain:search`/`query`.
- **structural** (codegraph) — `search:blast-radius`, `search:lineage`, and the wicked-patch family.

## Arguments

- `path` (required): Directory to index.

## Instructions

1. **Semantic layer** — invoke `/wicked-brain:ingest` with `<path>` (incremental; only changed files re-ingest).

2. **Structural layer** — rebuild the codegraph graph, then re-apply the injected edges:
   ```bash
   # first time on a repo: codegraph must be initialized before it can index
   npx -y @colbymchenry/codegraph init 2>/dev/null || true
   codegraph index "<path>"   # or: npx -y @colbymchenry/codegraph index "<path>"
   # codegraph indexes CODE only; re-apply the injected layer (bus producer→consumer,
   # command→agent dispatch, agent→capability) it doesn't know about and a re-index drops:
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
      "${CLAUDE_PLUGIN_ROOT}/scripts/codegraph/inject_all.py" "<path>/.codegraph/codegraph.db"
   ```
   The `inject_all` step is **required** for `blast-radius`/`lineage` to surface the string-keyed
   relationships grep and the static graph can't see (#916). Skipping it leaves the injected
   layer empty after every re-index.

3. **Verify**:
   ```bash
   PORT="$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_brain_port.py" 2>/dev/null || echo 4242)"
   curl -s -X POST "http://localhost:${PORT}/api" -H "Content-Type: application/json" \
     -d '{"action":"stats","params":{}}'                       # brain chunk/tag counts
   ```
   `inject_all` prints per-extractor edge counts + a `total_injected_edges` — report both.

## Notes

- Both layers are incremental/idempotent — safe to re-run.
- If `codegraph` isn't resolvable, the structural commands degrade to grep + brain (and say so);
  run `codegraph index` once to enable blast-radius/lineage/patch.
