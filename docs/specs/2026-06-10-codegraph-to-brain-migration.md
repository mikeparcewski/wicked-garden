# North-Star Spec — move the code-relationship graph from `wicked-garden` into `wicked-brain`

- **Date:** 2026-06-10
- **Status:** Design (approved shape; pending written-spec review → implementation plan)
- **Author:** brainstormed with Mike Parcewski
- **Topic:** Relocate the codegraph-backed relationship graph (engine integration, injected-edge extractors, and the blast-radius / lineage / architecture query surface) out of `wicked-garden` and into `wicked-brain`, so any project — not just ones running garden — gets enhanced code/graph knowledge.
- **Related:** docs/adr/0001-code-relationship-graph-engine.md (**this spec amends/inverts it**), docs/required-peers.md, `scripts/_codegraph.py`, `scripts/codegraph/`, the `wicked-brain-lsp` skill.

---

## 1. Context & motivation

There are currently **two half-built code-intelligence stacks** answering overlapping questions in different places:

- **garden's codegraph stack** — `scripts/_codegraph.py` (peer shim) + `scripts/codegraph/inject_*.py` (injected-edge extractors), feeding `search:blast-radius` / `search:lineage` and (eventually) wicked-patch's `--db`. Introduced by ADR 0001 (dated 2026-06-09).
- **brain's LSP stack** — the `wicked-brain-lsp` skill already advertises "blast radius" and "architecture map" via language servers.

Two blast-radius implementations, two homes, one concept. The smell is structural: **"what breaks if I change X" / "what flows where" / "what's connected to this" are knowledge questions about relationships** — and brain *is* the knowledge layer. Code-relationship comprehension is a thinking pattern, and thinking patterns belong in brain.

ADR 0001 noticed `search:blast-radius` was "wrongly" calling the brain and concluded *pull the graph into garden*. **That was the wrong direction.** The original instinct (blast-radius = brain) was right; the fix is to move the *graph* to brain, not move the *query* to garden. The decisive secondary requirement: the graph is **valuable to everyone**, and requiring all of wicked-garden just to give a repo enhanced code/graph knowledge is unacceptable. The graph must be a standalone brain capability with **zero garden dependency**.

**Thesis:** brain *knows* (the relationship graph + every query over it). Garden *does* (deterministic refactor, gates, archetypes) and is merely a *consumer* of the graph.

---

## 2. Decisions (locked)

Settled during brainstorming; the spine of this spec.

| # | Decision | Rationale |
|---|---|---|
| D1 | **Ownership: brain owns the graph + all relationship queries; garden consumes.** The *knowing*-vs-*doing* line: brain knows (blast-radius, lineage, impact, callers, architecture); garden does (wicked-patch refactor, gates, archetypes). | Blast-radius is knowledge; knowledge lives in brain. Unifies the two stacks under one owner. **Amends ADR 0001.** |
| D2 | **Dependency arrow points garden→brain only, never back.** Brain is fully valuable standalone for code/graph knowledge. | "Don't require all of garden just for brain to have graph knowledge." The graph is universally valuable. |
| D3 | **Proprietary edges via a pluggable extractor-drop registry (option i).** Brain defines an extractor interface + a discovery dir, *ships* the generic/ecosystem extractors itself, and discovers + runs plugin-dropped extractors if present (ignores if absent). | Most "injected" edges are ecosystem/platform conventions (bus wiring, plugin frontmatter, hooks), not garden internals — brain should know them natively. The genuinely garden-proprietary ones (archetypes) drop in without a reverse dependency. Generalizes to any wicked-* plugin. |
| D4 | **codegraph = graph of record; LSP = live precision (option A).** codegraph owns the persistent relationship graph, injected edges, and blast-radius / lineage / architecture. LSP keeps def/ref/hover/diagnostics and **stops being a second blast-radius**. No fusion layer. | LSP cannot represent injected edges (it only knows language semantics) and has no persistent whole-repo graph; codegraph is the only layer that can. Two clean lanes, each doing what it's best at. YAGNI on a merge/facade. |
| D5 | **Freshness: lazy staleness-stamp baseline + optional commit-hook accelerator (A + C). No watcher full-reindex.** | The 40%-CPU runaway diagnosed on 2026-06-10 *was* a reindex loop (watcher → polling → repeated re-index). Lazy + staleness-stamped is structurally incapable of that failure. Commit-hook is an opt-in accelerator (garden's compiler already installs git hooks — precedent). |
| D6 | **DB stays codegraph-native: `<repo>/.codegraph/codegraph.db` (per-repo, gitignored).** Brain records a pointer + staleness, does not relocate it. | It is codegraph's stable, self-describing contract; consumers (wicked-patch `--db`) expect it; it travels with the repo. |

---

## 3. Target architecture

```
codegraph CLI (peer, resolved via env→config→PATH→node_modules→npx)
        │ index
        ▼
 <repo>/.codegraph/codegraph.db   ── per-repo, gitignored, codegraph-native ──┐
        ▲                                                                      │
        │ inject                                                               │ read
  ┌─────┴──────────────────────────────────────────────┐                      │
  │ brain BUILT-IN extractors (ship with brain):        │                      │
  │   • bus producer→consumer  (emit + _bus_consumers)   │                      │
  │   • command→agent          (subagent_type:)          │                      │
  │   • hook event→script      (hooks.json)              │                      │
  │   • agent→tool             (capability registry)     │                      │
  │ brain DISCOVERED extractors (drop-in, optional):     │                      │
  │   • garden: archetype→playbook/gate (archetypes.json)│                      │
  └──────────────────────────────────────────────────────┘                     │
                                                                                │
 LSP servers ──live──▶ def/ref/hover/diagnostics      ◀── SEPARATE LANE         │
                                                          (not blast-radius)     │
                                                                                 │
 brain GRAPH QUERIES  ◀───────────────────────────────────────────────────────┘
   blast-radius · lineage · impact · callers · architecture
   every answer carries a staleness stamp (N commits behind HEAD, indexed-at)

 CONSUMERS:
   • brain skill  `wicked-brain-graph`  (new) — the query surface
   • garden wicked-patch (rename/add-field/remove) — consumes .codegraph.db as --db
   • any other plugin
```

### 3.1 Component responsibilities

| Component | Home | Does | Depends on |
|---|---|---|---|
| codegraph engine | external peer (`@colbymchenry/codegraph`, MIT) | static multi-language graph, column-precise, SQLite | Node ≥ 22.5 |
| engine integration (resolve + run + staleness) | **brain** | resolution ladder, `index`, `impact`/`callers`, staleness stamp | codegraph peer |
| extractor framework + interface + discovery | **brain** | define interface, discover + run extractors | — |
| built-in extractors (bus / command→agent / hooks / capability) | **brain** | materialize ecosystem-convention edges | brain graph |
| `wicked-brain-graph` skill | **brain** | blast-radius / lineage / impact / callers / architecture | brain graph |
| LSP intelligence (`wicked-brain-lsp`) | **brain** | live def/ref/hover/diagnostics (blast-radius role removed) | language servers |
| archetype extractor (drop-in) | **garden** | materialize archetype→gate edges into brain's graph | brain extractor interface |
| wicked-patch (rename/add-field/remove) | **garden** | deterministic refactor; consumes `.codegraph.db` as `--db` | brain graph DB shape |

---

## 4. What moves / what stays

| Today (garden) | Disposition | Note |
|---|---|---|
| `scripts/_codegraph.py` (engine shim, staleness) | **→ brain** | **Cross-language re-home, not a file copy** — brain's server is Node; this is Python. Re-implemented in brain's runtime. The resolution-ladder + staleness *semantics* port verbatim. |
| `scripts/codegraph/inject_edges.py` (bus) | **→ brain built-in extractor** | reads `_bus_consumers.json` + emit sites — a wicked-bus convention, not a garden internal |
| `scripts/codegraph/inject_dispatch_edges.py` (command→agent) | **→ brain built-in extractor** | `subagent_type:` is a Claude-Code plugin convention |
| `scripts/codegraph/inject_capability_edges.py` (agent→tool) | **→ brain built-in extractor** | capability registry — ecosystem-wide |
| `scripts/codegraph/_graph_nodes.py`, `inject_all.py` | **→ brain** | shared helpers + the orchestration entry |
| archetype→gate extractor (proprietary; future) | **garden ships as drop-in** | discovered by brain at runtime; brain works without it |
| `scripts/engineering/patch/{codegraph_db,patch}.py` | **stays garden** | repoint `--db` to `<repo>/.codegraph/codegraph.db`; a *doing* action |
| `commands/search/{blast-radius,lineage,hotspots,index}.md` | **thin aliases → brain skills, or removed** | the query surface is brain's now |
| `tests/codegraph/test_codegraph.py` | **engine/extractor tests → brain; garden keeps drop-in + patch-consumer tests** | |

---

## 5. Freshness & failure modes

### 5.1 Freshness (D5)
- **Baseline (lazy + staleness-stamped):** brain stamps how far `.codegraph.db` is behind HEAD (commits-behind + indexed-at — the `staleness()` logic already in `_codegraph.py`). Reindex runs **on explicit demand** or **when a query finds the graph stale past a threshold**. Zero idle CPU.
- **Accelerator (opt-in, commit-driven):** a git `post-commit` / `pre-push` hook triggers reindex so the graph is commit-fresh. Off by default.
- **Explicitly NOT** watcher-driven full reindex — that is the failure class diagnosed on 2026-06-10.

### 5.2 Failure modes (fail-closed, never vacuous)
| Condition | Behavior |
|---|---|
| codegraph unresolvable (no peer) | query returns `engine: "unavailable"` — **not** an empty/zero-edge graph that looks like a real answer |
| graph stale | answer is returned **with** a `stale: true, commits_behind: N` flag; caller decides |
| drop-in extractor absent | skipped silently — the standalone guarantee (D2) |
| shim subprocess error/timeout | surfaced as data (`{error: ...}`), never raises (R4) |

---

## 6. Testing & the standalone guarantee

- Engine resolver: resolution ladder (env → config → PATH → node_modules → npx) + the set-but-empty kill-switch.
- Staleness math: present/absent DB, commits-behind computation, fail-open on git errors.
- Each built-in extractor: deterministic edge materialization against a fixture repo (producer→consumer, command→agent, hooks, capability).
- Extractor-drop discovery: present (runs) vs absent (skipped, graph still valid).
- Query correctness: blast-radius / lineage over a known fixture graph with injected edges grep cannot see.
- **Standalone guarantee (the load-bearing test):** brain's graph module imports **nothing** from garden — enforced in CI (the inverse of the compiler's existing "emitted gate imports nothing from the garden" AST test). This is what keeps D2's one-way arrow from silently regressing.

---

## 7. Implementation decomposition

Two phases, sequenced — garden phase depends on brain having shipped the graph.

### Phase 1 — `wicked-brain`
1. Engine integration (resolve + `index` + `impact`/`callers` + staleness), Node-native.
2. Extractor framework: interface + discovery dir + registry.
3. Built-in extractors: bus, command→agent, hooks, capability.
4. Graph query surface + new `wicked-brain-graph` skill (blast-radius / lineage / impact / callers / architecture).
5. Remove blast-radius/architecture from `wicked-brain-lsp`'s advertised surface (keep live ops).
6. Freshness: staleness stamp + opt-in commit hook.
7. Standalone CI test (zero garden imports).

### Phase 2 — `wicked-garden`
1. Repoint wicked-patch (`codegraph_db.py` / `patch.py`) to brain's `.codegraph.db`.
2. Ship the archetype extractor as a brain drop-in.
3. Convert `search:{blast-radius,lineage,hotspots,index}` commands to thin aliases over brain skills, or remove.
4. Delete the migrated `scripts/_codegraph.py` + `scripts/codegraph/*` from garden.
5. **Amend ADR 0001** (record the inversion: graph → brain, not garden) — likely a new ADR 0004 superseding the relevant section.
6. Update CLAUDE.md (storage/search sections) to point at brain for graph queries.

---

## 8. Out of scope (YAGNI)

- A unified LSP+codegraph graph or a query facade over both (D4 rejected B and C).
- Watcher-driven incremental reindex (D5 rejected B).
- Relocating the graph DB under brain's project dir (D6 — keep codegraph-native).
- Any general data-flow lineage layer beyond what codegraph + injected edges provide (deferred; was ADR 0001 roadmap step 5).

---

## 9. Related operational findings (non-blocking)

Surfaced while diagnosing why brain appeared "down" on 2026-06-10 (separate from this migration, tracked separately):
- **wicked-brain bug:** file-watcher polling fallback (after EMFILE) re-indexes unchanged files in a hot loop → ~40% CPU runaway. This spec's D5 ensures the *codegraph* reindex path cannot reproduce that class of bug, but the watcher bug itself is a brain-repo fix.
- **wicked-garden bug:** the brain reachability probe (`_brain_api` / `_check_search_staleness`, 2s timeout) collapses slow/down/errored/non-JSON into one "not reachable — start wicked-brain" message, mis-reporting an up-but-slow server. Dogfooding issue to be filed.
