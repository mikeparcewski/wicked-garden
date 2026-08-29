# ADR 0005 — Retarget inventory (brain graph surface → wicked-estate)

<!-- historical-doc -->

Companion to [ADR 0005](0005-code-graph-re-homes-to-wicked-estate.md). This is the **actionable
checklist Stage S5 executes.** Every garden call-site that references wicked-brain's (now-retired)
code-graph surface is listed with: source `file:line`, what it calls today, the estate replacement
(exact tool / file), and an effort note. **No code is changed in this ADR PR** — S5 does the edits.

All line numbers are against garden `HEAD` at the time of writing; re-confirm before editing.

## Estate replacement surface (the targets)

| Estate capability | Where it lives (estate repo) | Replaces (brain) |
|---|---|---|
| `BlastRadius` MCP tool — "what breaks if I change X?" (transitive dependents) | tool registered `crates/wicked-estate-mcp/src/lib.rs:34,69`; impl `crates/wicked-estate-retrieve/src/lib.rs:769` (name `:772`, desc `:776`) | `graph-blast-radius` action |
| `Lineage` MCP tool — "what does X depend on?" (transitive dependencies; complement of BlastRadius) | registered `.../mcp/src/lib.rs:35,75`; impl `.../retrieve/src/lib.rs:1020` (name `:1023`, desc `:1027`) | `graph-lineage` action |
| `TraverseGraph` MCP tool — bounded multi-hop walk, forward/reverse/both, `edge_kinds` filter | registered `.../mcp/src/lib.rs:34,68`; impl `.../retrieve/src/lib.rs:609` (name `:633`, desc `:637`) | generic graph walk / `graph-*` BFS |
| `RankHotspots` MCP tool — most-central symbols by PageRank over Calls+Imports | registered `.../mcp/src/lib.rs`; impl `.../retrieve/src/lib.rs:1223` (name `:1226`, desc `:1230`) | `hotspots` raw-SQLite read |
| `SearchEntity` / `RetrieveEntity` MCP tools — symbol lookup / node fetch | registered `.../mcp/src/lib.rs:34,66-67`; impl `.../retrieve/src/lib.rs:337`,`:489` | `symbols` / `wicked-brain-call` lookups |
| `ExtraEdgeExtractor` — injected edges from TOML rules (`.wicked-estate-extractors/<name>.toml`) | `crates/wicked-estate-extract/src/extra_edge.rs`; docs `docs/extractor-sdk.md` Part 2 | `.codegraph-extractors/*.mjs` JS drop-ins |
| `XedgeStore` / `XedgeReader` — injected cross-store / cross-repo edges (`xedge.db`) | `crates/wicked-estate-overlay/src/xedge.rs` | (no brain equivalent) |
| Index build (75-lang tree-sitter, in-binary) | `wicked-estate index <path>` (`crates/wicked-estate/src/main.rs:3`); `LANG_TABLE` in `crates/wicked-estate-extract/src/treesitter.rs` | `graph-index` (codegraph shell-out) |

**Edge-direction invariant (unchanged in spirit):** estate uses `source = dependent, target =
dependency`; `BlastRadius` = dependents (`crates/wicked-estate-overlay/src/xedge.rs:10-14`, estate
`CLAUDE.md`). This matches archetype.mjs's own convention (`source = archetype`/dependent, `target =
playbook`/dependency — archetype.mjs:17-19), so the archetype rule ports **without a direction flip.**

---

## A. Active consumer call-sites (S5 must repoint these — they execute)

### A1 — `skills/search/SKILL.md` (the `wicked-garden-search` skill, six actions)

| Line(s) | Calls today | Estate replacement | Effort |
|---|---|---|---|
| 7-10, 27-33, 48-52 | Prose: "delegate to wicked-brain… owns the unified static + injected graph (ADR 0004)… `wicked-brain:graph`" | Rewrite framing: delegates to **wicked-estate MCP**; cite ADR 0005 | S — prose |
| 61, 113, 151 | `npx -y wicked-brain-call graph-index` (build/refresh) | `wicked-estate index <path>` (CLI) — or note the estate MCP server indexes on connect | M — command swap + freshness note |
| 88 | `npx -y wicked-brain-call symbols --query "<symbol>"` | `SearchEntity` MCP tool (resolve name→node id) | M |
| 119, 155 | `npx -y wicked-brain-call graph-blast-radius --node "…"` → `dependents` | `BlastRadius` MCP tool (`symbol` arg) | M |
| 154 | `npx -y wicked-brain-call graph-lineage --node "…"` → `dependencies` | `Lineage` MCP tool (`symbol` arg) | M |
| 78-80, 92-94 | codegraph-unavailable / `WICKED_CODEGRAPH_BIN` / `@colbymchenry/codegraph` install fallback | Delete — estate needs no external engine; replace with "estate MCP unreachable" fallback | S — remove dead ladder |
| 84-89 | Node-id scheme (`file:<relpath>`, `function:<hash>`) | Re-document against estate `SymbolId` scheme | S |

Also update the frontmatter `description` (lines 4-24) which advertises "wicked-brain's unified …
graph (ADR 0004)" and "use wicked-brain:search / wicked-brain:query" — repoint to estate.

### A2 — `skills/search/refs/hotspots.md` (hotspots action)

| Line(s) | Calls today | Estate replacement | Effort |
|---|---|---|---|
| 11 | "brain's `graph-index` builds the codegraph graph + injected edges" | `wicked-estate index` | S |
| 14-35 | **Primary path: raw `sqlite3` read of `.codegraph/codegraph.db`** — `SELECT target, COUNT(*) … FROM edges … GROUP BY target` | `RankHotspots` MCP tool (PageRank ranking — strictly better than incoming-edge count) | M — replace the whole inline Python block with an MCP call |
| 41-48 | Fallback: `curl` to brain HTTP `localhost:4242` `search` action | Replace with estate MCP fallback (or drop) | S |

### A3 — `scripts/engineering/patch/codegraph_db.py` (wicked-patch symbol DB — the `.codegraph/codegraph.db` reader)

| Line(s) | Does today | Estate replacement | Effort |
|---|---|---|---|
| 1-46 | Module: "adapt codegraph's SQLite into the symbol-graph DB wicked-patch expects" (ADR 0001 payoff) | Re-source from the **estate graph**; header/rationale rewrite to ADR 0005 | — |
| 42-47 | `build_patch_db(codegraph_db, out_db)` opens `.codegraph/codegraph.db` read-only via `sqlite3.connect(file:…?mode=ro)` | Read estate's graph instead — either (a) an **estate graph export** to the patch schema, or (b) query estate MCP (`TraverseGraph`/`RetrieveEntity`) and materialize the patch `--db`. Decide the seam in S5. | **L** — the codegraph↔patch column mapping (lines 34-98) must be re-derived against estate's node/edge shape (`SymbolId`, `EdgeKind`) |
| 109 | `--codegraph-db` default `.codegraph/codegraph.db` | New default pointing at the estate graph/export path | S |
| tests: `scripts/engineering/patch/tests/test_codegraph_db.py:22,25,50-52` | Build a codegraph-shaped temp DB and assert the translation | Rewrite fixtures to estate's shape (or the export contract) | M — test rewrite |

> Note: `patch.py` / `propagation_engine.py` / `generators/*` consume the *translated* patch `--db`,
> not codegraph directly — so once `codegraph_db.py` is repointed, the rest of the patch family is
> unaffected (only the adapter and its tests change).

### A4 — `.codegraph-extractors/archetype.mjs` (garden's proprietary injected-edge extractor)

| Line(s) | Does today | Estate replacement | Effort |
|---|---|---|---|
| 1-67 | JS drop-in run by brain's registry: reads `.claude-plugin/archetypes.json`, and for each archetype key whose `skills/archetype/refs/<name>.md` playbook exists on disk, `INSERT INTO edges` a synthetic `archetype:<name>` → playbook-file edge (`provenance = injected:archetype`), idempotently | Re-author as an estate **`ExtraEdgeExtractor` TOML rule set** (`.wicked-estate-extractors/archetype.toml`) per `crates/wicked-estate-extract/src/extra_edge.rs` + `docs/extractor-sdk.md` Part 2 | **L (highest-effort item)** |

**Why L / modeling note.** archetype.mjs's logic is *JSON-catalog iteration + file-existence guard +
edge to an existing file node*. Estate's `ExtraEdgeExtractor` is *regex-over-one-file-text, glob-filtered,
emitting a synthetic node + edge to a synthetic target node*. The port is not 1:1:
- **Recommended shape (idiomatic to estate, mirrors the event-bus emit/consume example):** two rules
  sharing one `node_scheme` (the convergence key) so both land on the same synthetic node —
  1. rule `file_glob = ".claude-plugin/archetypes.json"`, `pattern` capturing each archetype key,
     `emit_node`/`emit_edge` to `node_scheme = "archetype-playbook"`, `id_template = "playbook:{name}"`;
  2. rule `file_glob = "skills/archetype/refs/*.md"`, `pattern`/glob capturing `{name}`, `emit_edge`
     onto the same `node_scheme = "archetype-playbook"`, `id_template = "playbook:{name}"`.
  Blast-radius on `playbook:{name}` then reaches both the catalog entry and the playbook file.
- **Two semantic deltas to accept or design around:** (a) archetype.mjs's *"skip if the playbook file
  is missing — flag, don't fabricate"* guard has no direct regex-rule equivalent (a glob rule only
  fires on files that exist, which achieves a similar effect but drops the explicit `skipped` count);
  (b) archetype.mjs targets the playbook's **file node** directly, whereas ExtraEdge targets a
  **synthetic** node — the shared-`node_scheme` model above co-locates them on a synthetic node
  rather than pointing at the file node. If S5 needs the edge to land on the literal file node, that
  is the one case that may warrant a small `extra_edge.rs` affordance (target = file node by path) —
  raise it with estate before assuming the TOML model suffices.
- Delete the `.codegraph-extractors/` dir + its packaging/permission refs once ported
  (`.npmignore:54`, `.claude/settings.local.json:87`).

### A5 — `skills/core/SKILL.md` (top-level skill roster)

| Line(s) | Says today | Estate replacement | Effort |
|---|---|---|---|
| 95 | "> `wicked-brain:search` / `wicked-brain:graph` for code search and relationship graphs" | Repoint the relationship-graph half to estate MCP (`BlastRadius`/`Lineage`/`TraverseGraph`) | S |
| 90, 104 | `wicked-garden-search` blast-radius/lineage examples (thin wrappers over brain) | Unchanged names; they now wrap estate (fixed transitively via A1) | S |

### A6 — `skills/search/codebase-narrator/SKILL.md` + other search sub-refs

`codebase-narrator/SKILL.md:3,131` and `skills/search/refs/service-map.md` describe the search
skill's `blast-radius`/`lineage` actions. They delegate to `../SKILL.md`, so they're **fixed
transitively by A1** — audit for any direct `graph-*`/`.codegraph` mention (none found in the sweep)
and update the ADR-0004 references. Effort: **S**.

---

## B. Documentation / spec references (update for consistency — no executable coupling)

These don't call the brain surface at runtime, but assert the ADR-0004 homing and must be refreshed
so the narrative matches ADR 0005. Group-edit in S5.

| File:line | Asserts | Fix | Effort |
|---|---|---|---|
| `.claude/CLAUDE.md:208` | "Code-relationship graph lives in wicked-brain (ADR 0004)… `graph-*` actions + `wicked-brain:graph`… `.codegraph/codegraph.db`" | Rewrite to estate + ADR 0005 | S |
| `README.md:77` | Optional peer `npx @colbymchenry/codegraph` "powers blast-radius/lineage/hotspots/wicked-patch" | Estate MCP; drop the codegraph peer | S |
| `.product/REQ-001-application-overview.md:89` | Patch "reads the codegraph from wicked-brain (`.codegraph/codegraph.db`)" | Estate graph | S |
| `.product/REQ-002-technology-constraints.md:60` | "wicked-brain builds/maintains `.codegraph/codegraph.db`" | Estate | S |
| `.product/RAID.md:33,60` | ASS-003 + codegraph dependency row | Estate; drop codegraph external-dep risk | S |
| `.product/DES-001-technical-design.md:186,206,259,307` | `.codegraph/codegraph.db` "built/maintained by wicked-brain", shared with patch | Estate graph + estate index | M — several diagram/table edits |
| `docs/required-peers.md` (codegraph peer entry) | codegraph as optional runtime peer | Drop / repoint | S |
| `.npmignore:54` | ignores `.codegraph-extractors/` | Remove once archetype.mjs is ported (A4) | S |
| `.claude/settings.local.json:87` | allow `node --check .codegraph-extractors/archetype.mjs` | Remove with A4 | S |

## C. Leave as-is (historical record — do NOT rewrite)

- `docs/adr/0001-code-relationship-graph-engine.md`, `docs/adr/0004-code-graph-moves-to-wicked-brain.md`
  — historical ADRs. 0004's **Status banner is updated to "Superseded by ADR 0005"** in this PR (the
  supersede convention); its body stays intact as the record of the prior decision.
- `CHANGELOG.md:144-145` — changelog entries are an append-only record; don't rewrite history.
- `docs/plans/2026-06-10-codegraph-to-brain-phase1a-*.md`, `…-phase1b-*.md`,
  `docs/specs/2026-06-10-codegraph-to-brain-migration.md` — completed migration artifacts for the
  *brain* move (now superseded). Leave as historical; optionally add a one-line "superseded by ADR
  0005" pointer at the top in S5 (optional, S).

---

## Effort roll-up

| Bucket | Items | Effort |
|---|---|---|
| A1 search skill rewrite | 1 skill, ~10 edits | M |
| A2 hotspots → `RankHotspots` | 1 ref | M |
| A3 `codegraph_db.py` → estate graph | 1 adapter + tests | **L** (seam decision: export vs MCP-materialize) |
| A4 archetype.mjs → ExtraEdge TOML | 1 extractor | **L** (modeling decision; possible estate SDK ask) |
| A5/A6 skill roster + narrator | 2-3 refs | S |
| B docs/specs consistency | ~10 files | S–M (bulk) |
| C historical | leave / optional pointer | — |

**Keystones for S5:** A3 and A4 carry real design decisions (the patch-DB seam; the archetype edge
model). Everything else is mechanical repointing once those two seams are settled.
