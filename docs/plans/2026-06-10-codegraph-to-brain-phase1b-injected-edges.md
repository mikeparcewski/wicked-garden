# Codegraph → Brain, Phase 1b: Injected Edges + Extractor Registry — Plan

> **For agentic workers:** executed via subagent-driven-development against the wicked-brain repo (branch `feat/codegraph-graph-core`, same as Phase 1a). Builds on Phase 1a's `codegraph-client`/`codegraph-index`.

**Goal:** Materialize wicked-ecosystem **injected edges** (grep-/static-invisible, string-wired relationships) into the codegraph graph so blast-radius/lineage traverse them — with a pluggable registry so brain ships generic extractors and any plugin can drop in proprietary ones (Decision D3). **Zero garden dependency.**

**Repo:** `/Users/michael.parcewski/Projects/wicked-brain` (worktree `.claude/worktrees/codegraph-phase1a`).

---

## Decisions

| # | Decision | Why |
|---|---|---|
| B1 | Brain **ships** built-in extractors that read only target-repo files/conventions: **bus** (`_bus_consumers.json` + emit sites), **dispatch** (`subagent_type:` in `commands/**/*.md` → `agents/<d>/<n>.md`), **capability** (agent `tool-capabilities:` frontmatter → `capability:<name>` nodes, **frontmatter-only — no registry import**). | These are wicked-bus / Claude-plugin conventions, not garden internals. No garden code is imported (the garden `capability` extractor's `_capability_registry` import is dropped — registry *filtering* becomes a drop-in concern). |
| B2 | **Drop-in registry**: brain scans `<sourcePath>/.codegraph-extractors/*.mjs`, dynamic-imports each, runs its `extract({db, sourcePath, nodes})`. Absent dir → no-op. | D3 mechanism. Garden's proprietary archetype extractor (Phase 2) drops in here. Dependency points target→brain only; brain never imports the drop-in's repo. |
| B3 | Extractors write to the codegraph SQLite **read-write** (better-sqlite3). Each is **idempotent**: `DELETE FROM edges WHERE provenance=?` (its own), re-insert. Self-node markdown/virtual nodes via `ensureFileNode`/`ensureVirtualNode` (codegraph indexes code, not .md — issue garden#916). | Matches the garden Python extractors' contract; injected edges co-locate in the same `nodes`/`edges` tables as the static graph (ADR 0001). |
| B4 | `graph-index` runs the codegraph build **then** all extractors (built-in + drop-in) in one pass, so a single action yields the complete graph. Re-index drops injected edges (codegraph rebuild) → extractors re-apply every run. | One front door; blast-radius never sees a stale/empty injected layer. |

Edge convention (from Phase-1a contract): edge `(source, target, kind, metadata, provenance)`; injected edges use `kind="references"`, `provenance="injected:<mechanism>"`, semantics in `metadata`. Direction matches static edges so `DEPENDENTS_BY="target"` blast-radius surfaces the dependent (e.g. consumer is a dependent of producer ⇒ edge `source=consumer? ...`). **NB:** the garden bus extractor inserts `edge(source=producer, target=consumer)`; verify against Phase-1a blast-radius direction during implementation and align so blast-radius(producer) surfaces the consumer (see Task B-real).

## File structure (brain `server/`)

| File | Responsibility |
|---|---|
| `lib/codegraph-nodes.mjs` | `ensureFileNode(db, relpath, lang?)`, `ensureVirtualNode(db, id, kind, name, filePath?)` — idempotent `INSERT OR IGNORE` populating all NOT NULL node cols. Port of `_graph_nodes.py`. |
| `lib/codegraph-extractors/bus.mjs` | `extract({db, sourcePath})` — read `scripts/_bus_consumers.json` + grep `wicked|wg.x` event strings in `scripts/**/*.py`; insert producer→consumer edges (`injected:bus`). |
| `lib/codegraph-extractors/dispatch.mjs` | command→agent edges from `subagent_type:` handles resolving to `agents/<d>/<n>.md` (`injected:dispatch`). |
| `lib/codegraph-extractors/capability.mjs` | agent→`capability:<name>` edges from `tool-capabilities:` frontmatter (`injected:capability`); creates virtual capability nodes. |
| `lib/codegraph-extract.mjs` | registry: `BUILTINS=[bus,dispatch,capability]`; `discoverDropins(sourcePath)` scans `<sourcePath>/.codegraph-extractors/*.mjs`; `runExtractors({db, sourcePath})` runs all, returns `{<label>:counts, total_injected_edges, dropins:[...]}`. Fail-open per extractor. |
| `bin/wicked-brain-server.mjs` | `graph-index` action: after `runIndex`, open db read-write, `runExtractors`, return build + injection stats + staleness. |
| `test/codegraph-nodes.test.mjs`, `test/codegraph-extract.test.mjs`, per-extractor tests | fixtures with the wiring; assert edges materialized + idempotency + drop-in discovery (present/absent). |

## Tasks (TDD, subagent-driven)

- **B1 nodes**: `codegraph-nodes.mjs` + test (ensure file/virtual node idempotent; all NOT NULL cols set).
- **B2 bus extractor**: `extractors/bus.mjs` + test (fixture repo with `scripts/_bus_consumers.json` + a producer .py emitting the event + the consumer module node; assert producer→consumer edge with `injected:bus`; idempotent re-run).
- **B3 dispatch + capability extractors** + tests (fixture command/agent .md with `subagent_type:` and `tool-capabilities:`).
- **B4 registry**: `codegraph-extract.mjs` + test (runs builtins; discovers a drop-in `.mjs` in `.codegraph-extractors/` and runs it; absent dir → builtins only; one failing extractor doesn't abort the rest).
- **B5 wire `graph-index`** to run extractors after build + test (action returns injection stats; read actions unaffected).
- **B-real**: real-repo test — point brain at **wicked-garden**, `graph-index`, then `graph-blast-radius` on a bus producer module; assert a consumer wired only via the event string appears in the blast radius (a link grep cannot find). This is the Phase-1b acceptance + part of the goal's "tested on a real repo".

## Out of scope
Registry-filtered capability validation (drop-in concern); hooks event→script extractor (additive later); import-node→file resolution (Phase 1a limitation).
