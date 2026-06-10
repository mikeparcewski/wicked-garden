---
description: Build/refresh the code-intelligence index (semantic brain + structural codegraph)
argument-hint: "<path>"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:index

Refresh the two code-intelligence layers the other `search:*` commands query. Both
live in **wicked-brain** now (ADR 0004):

- **semantic** (wicked-brain) — concept/symbol search, `wicked-brain:search`/`query`.
- **structural** (codegraph graph, owned by brain) — `wicked-brain:graph` (blast-radius/lineage) and the wicked-patch family.

## Arguments
- `path` (required): directory to index (the brain server's `--source` repo).

## Instructions

1. **Semantic layer** — invoke `/wicked-brain:ingest` with `<path>` (incremental; only changed files re-ingest).

2. **Structural layer** — one call rebuilds the codegraph static graph **and** re-applies every injected-edge extractor (built-in bus/dispatch/capability + any per-repo drop-ins under `.codegraph-extractors/`):
   ```bash
   npx -y wicked-brain-call graph-index
   ```
   This replaces the old `codegraph index` + `inject_all.py` two-step — brain runs the build and the extractors in a single pass, so the injected layer is never left empty after a re-index. The result reports per-extractor counts, `total_injected_edges`, and a `staleness` stamp.

3. **Verify**:
   ```bash
   npx -y wicked-brain-call stats         # brain chunk/tag counts (semantic layer)
   ```
   and confirm `graph-index` reported `total_injected_edges > 0` on a repo with wiring.

## Notes
- Both layers are incremental/idempotent — safe to re-run.
- Freshness is lazy by design (no file-watcher reindex). `graph-*` results carry `commits_behind`/`indexed_at`; re-run `graph-index` when stale.
- If codegraph isn't resolvable where brain runs, `graph-*` returns `engine:"unavailable"` — install `@colbymchenry/codegraph` or set `WICKED_CODEGRAPH_BIN`.
