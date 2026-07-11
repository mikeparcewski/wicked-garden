---
name: wicked-garden-search
user-invocable: true
description: |
  Code-intelligence search over wicked-brain's unified static + injected
  code-relationship graph (ADR 0004). One skill, six routed actions:
  index (build/refresh the semantic + structural layers), blast-radius
  (impact analysis over dependents), lineage (data/dependency flow),
  hotspots (most-referenced symbols), service-map (service architecture
  from infra + code), and narrate (codebase orientation walkthrough).

  Use when: "index the codebase" / "build or refresh the code-intelligence
  index"; "what would break if I change X" / "blast radius of" / "impact
  analysis"; "trace lineage" / "where does this flow from/to" / "upstream
  or downstream of a symbol"; "most-referenced symbols" / "find god
  objects" / "coupling hotspots"; "map the services" / "service dependency
  map" / "visualize the service architecture"; "architecture walkthrough" /
  "narrate this codebase". Replaces the former /wicked-garden:search:*
  commands (index, blast-radius, lineage, hotspots, service-map).

  NOT for general code/concept search — use wicked-brain:search or
  wicked-brain:query directly.
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# wicked-garden:search — code-intelligence over the brain graph

All actions delegate to **wicked-brain**, which owns the unified static +
injected code-relationship graph as of ADR 0004. Garden no longer maintains
its own graph; it consumes brain's. Garden contributes its proprietary
**archetype** edges to brain's graph via the drop-in extractor
`.codegraph-extractors/archetype.mjs` (discovered by brain's registry).

## Routing

| Action | Answers | Where |
|--------|---------|-------|
| `index` | build/refresh the code-intelligence index | § Index / freshness |
| `blast-radius` | "what breaks if I change X?" (dependents) | § Blast radius |
| `lineage` | "where does this flow from / to?" (data flow) | § Lineage |
| `hotspots` | most-referenced symbols, god-objects | [refs/hotspots.md](refs/hotspots.md) |
| `service-map` | service architecture from infra + code | [refs/service-map.md](refs/service-map.md) |
| `narrate` | codebase orientation / architecture walkthrough | [codebase-narrator/SKILL.md](codebase-narrator/SKILL.md) |

## Index / freshness (shared by every action)

Two code-intelligence layers, both living in **wicked-brain** (ADR 0004):

- **semantic** (wicked-brain) — concept/symbol search, `wicked-brain:search`/`query`.
- **structural** (codegraph graph, owned by brain) — `wicked-brain:graph`
  (blast-radius/lineage) and the wicked-patch family.

1. **Semantic layer** — invoke `/wicked-brain:ingest` with `<path>` (the brain
   server's `--source` repo; incremental — only changed files re-ingest).

2. **Structural layer** — one call rebuilds the codegraph static graph **and**
   re-applies every injected-edge extractor (built-in bus/dispatch/capability +
   any per-repo drop-ins under `.codegraph-extractors/`):
   ```bash
   npx -y wicked-brain-call graph-index
   ```
   This replaces the old `codegraph index` + `inject_all.py` two-step — brain
   runs the build and the extractors in a single pass, so the injected layer is
   never left empty after a re-index. The result reports per-extractor counts,
   `total_injected_edges`, and a `staleness` stamp.

3. **Verify**:
   ```bash
   npx -y wicked-brain-call stats         # brain chunk/tag counts (semantic layer)
   ```
   and confirm `graph-index` reported `total_injected_edges > 0` on a repo with wiring.

**Notes**
- Both layers are incremental/idempotent — safe to re-run.
- Freshness is lazy by design (no file-watcher reindex). `graph-*` results
  carry `commits_behind`/`indexed_at`; re-run `graph-index` when stale.
- If codegraph isn't resolvable where brain runs, `graph-*` returns
  `engine:"unavailable"` — install `@colbymchenry/codegraph` or set
  `WICKED_CODEGRAPH_BIN`.

## Resolving symbols + fallback ladder (shared by blast-radius and lineage)

**Resolve the symbol to a graph node id.** Node ids are `file:<relpath>` for
files, or `function:<hash>` etc. for symbols. For a file, use `file:<path>`
directly. For a named symbol, find its id via brain:
```bash
npx -y wicked-brain-call symbols --query "<symbol>"     # or wicked-brain:lsp workspace-symbols
```

**Fallbacks** (in order):
1. If a `graph-*` call returns `engine: "unavailable"`, codegraph isn't
   installed where brain runs — install it (`npx @colbymchenry/codegraph`) or
   set `WICKED_CODEGRAPH_BIN`, then re-run `graph-index`.
2. If brain is unreachable, fall back to `wicked-brain:search` for semantic
   neighbors, then Grep/Glob for literal refs — and **flag that injected
   relationships will be MISSING** from the result (injected/string-keyed
   links are invisible to grep).

## Blast radius — "what breaks if I change X?"

Analyze what would be affected if you changed a symbol — traces **dependents**
(what uses this) over the code-relationship graph, including injected edges
(bus/dispatch/capability/archetype) that grep and a static call-graph cannot see.

> **Scope**: `blast-radius` answers "what breaks if I change X?" (the
> dependents graph). For **data-flow tracing** (UI field → DB column or
> reverse), use the `lineage` action.

**Arguments**: `symbol` (required — a file node like `src/app.py`, or a symbol
name); `--depth` (optional traversal depth; brain default applies if omitted).

1. **Ensure the graph is fresh** (§ Index / freshness): `npx -y wicked-brain-call graph-index`.
   The result carries a `staleness` stamp; if `stale` is true after editing, re-run it.
2. **Resolve the symbol to a node id** (§ Resolving symbols).
3. **Query blast radius from brain** (static + injected dependents in one
   answer — the authoritative layer):
   ```bash
   npx -y wicked-brain-call graph-blast-radius --node "file:<path-or-resolved-id>"
   ```
   The `dependents` array includes relationships grep can't see: a command that
   *dispatches* an agent (`injected:dispatch`), a consumer that *subscribes* to
   an event (`injected:bus`), an agent that *declares* a capability
   (`injected:capability`) — and archetype→playbook relationships via garden's
   `.codegraph-extractors/archetype.mjs` (`injected:archetype`). Each result
   carries a `staleness` stamp.
4. **Fallbacks**: § Resolving symbols + fallback ladder.
5. Report: **dependents** (static + injected, with provenance), total
   blast-radius count, files affected, and the graph's staleness.

**Examples**
```
blast-radius scripts/_bus.py
blast-radius UserService --depth 3
```

## Lineage — "where does this flow from / to?"

Trace flow through the code-relationship graph. Downstream = what the symbol
depends on; upstream = what depends on it. Includes injected edges
(bus/dispatch/capability/archetype) that grep and a static call-graph can't see.

> **Scope**: `lineage` answers "where does this flow from / to?". For pure
> "what breaks if I change X?" use the `blast-radius` action.

**Arguments**: `symbol` (required — `file:<relpath>` or a resolved node id);
`--direction` (optional, default `downstream`): `downstream` (dependencies),
`upstream` (dependents), or `both`; `--depth` (optional traversal depth;
brain default applies if omitted).

1. **Ensure the graph is fresh** (§ Index / freshness): `npx -y wicked-brain-call graph-index`.
2. **Resolve the symbol to a node id** (§ Resolving symbols).
3. **Trace** via brain:
   - **downstream** (what it depends on): `npx -y wicked-brain-call graph-lineage --node "<id>"` → `dependencies`.
   - **upstream** (what depends on it): `npx -y wicked-brain-call graph-blast-radius --node "<id>"` → `dependents`.
   - **both**: run both and present each direction.
   Each result includes injected edges (e.g. a consumer reached via
   `injected:bus`, an archetype via `injected:archetype`) and a `staleness` stamp.
4. **Fallbacks**: § Resolving symbols + fallback ladder.
5. Report each path (source → sink), file locations per step, provenance of
   injected hops, and gaps.

**Examples**
```
lineage file:scripts/_bus.py --direction upstream
lineage User.email --direction both
```

## Hotspots — most-referenced symbols

Rank symbols by incoming reference count to expose god-objects, coupling
hotspots, and high-impact refactor targets. Reads the graph DB brain builds
(`.codegraph/codegraph.db`), with a brain-search fallback.
→ Full procedure: [refs/hotspots.md](refs/hotspots.md)

## Service map — detect the service architecture

Detect services and their connections from infrastructure config
(docker-compose/k8s/helm) plus brain/code patterns; report as table, json, or
mermaid. → Full procedure: [refs/service-map.md](refs/service-map.md)

## Narrate — codebase orientation

For "give me an architecture walkthrough" / "narrate this codebase" / "where
should I start reading", use the nested skill:
[codebase-narrator/SKILL.md](codebase-narrator/SKILL.md) — produces a guided
reading order, annotated directory map, data-flow diagram, and gotchas list.
