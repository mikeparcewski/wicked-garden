---
name: wicked-garden-search
user-invocable: true
description: |
  Code-intelligence search over wicked-estate's unified static + injected
  code-relationship graph (ADR 0005). One skill, six routed actions:
  index (build/refresh the graph), blast-radius (impact analysis over
  dependents), lineage (data/dependency flow), hotspots (most-central
  symbols by PageRank), service-map (service architecture from infra +
  code), and narrate (codebase orientation walkthrough).

  Use when: "index the codebase" / "build or refresh the code-intelligence
  index"; "what would break if I change X" / "blast radius of" / "impact
  analysis"; "trace lineage" / "where does this flow from/to" / "upstream
  or downstream of a symbol"; "most-referenced symbols" / "find god
  objects" / "coupling hotspots"; "map the services" / "service dependency
  map" / "visualize the service architecture"; "architecture walkthrough" /
  "narrate this codebase". Replaces the former /wicked-garden:search:*
  commands (index, blast-radius, lineage, hotspots, service-map).

  NOT for general concept/memory search — use the `wicked-garden-mem` skill
  (recall/answer over estate's knowledge + memory stores) or the wicked-estate
  MCP's SearchEntity (symbol lookup) directly.
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# wicked-garden:search — code-intelligence over the estate graph

All actions delegate to **wicked-estate**, which owns the unified static +
injected code-relationship graph as of ADR 0005 (superseding the brain-homed
graph of ADR 0004). Garden no longer maintains its own graph; it consumes
estate's. Garden contributes its proprietary **archetype** edges to estate's
graph via the drop-in TOML rules in
`.wicked-estate-extractors/archetype.toml` (auto-discovered by
`wicked-estate index`).

## Routing

| Action | Answers | Where |
|--------|---------|-------|
| `index` | build/refresh the code-intelligence index | § Index / freshness |
| `blast-radius` | "what breaks if I change X?" (dependents) | § Blast radius |
| `lineage` | "where does this flow from / to?" (data flow) | § Lineage |
| `hotspots` | most-central symbols, god-objects | [refs/hotspots.md](refs/hotspots.md) |
| `service-map` | service architecture from infra + code | [refs/service-map.md](refs/service-map.md) |
| `narrate` | codebase orientation / architecture walkthrough | [codebase-narrator/SKILL.md](codebase-narrator/SKILL.md) |
| `answer` | cited answer from the estate knowledge/memory stores | [refs/answer.md](refs/answer.md) |

Doctrine / which-rules-apply: the **architecture wiki** is in the same stores — `knowledge.recall {"scope_prefix": "wiki:"}` + estate MCP `rules.recall` (cited); lifecycle: wicked-core `crates/wicked-governance/WIKI.md`.

## Index / freshness (shared by every action)

The graph lives in **wicked-estate** (ADR 0005): a 75-language tree-sitter
static graph **plus** injected domain edges, built by the estate binary — no
external engine, no Node version floor.

1. **Build / refresh** — one command rebuilds the static graph **and**
   re-applies every injected-edge rule (any per-repo TOML drop-ins under
   `.wicked-estate-extractors/`, e.g. garden's archetype rules):
   ```bash
   wicked-estate index <path>        # DB defaults to .wicked-estate/graph.db
   ```
   Incremental — unchanged files are skipped; editing the extractor rules
   forces a full re-extract automatically. (The estate MCP server serves the
   same DB, so an index refresh is immediately visible to the MCP tools.)

2. **Verify**: `wicked-estate stats` reports node/edge counts plus an
   `unresolved=N` token (call/import references no resolver could bind — a
   resolver-health signal, not an error count); a repo with
   archetype wiring shows the injected edges (provenance
   `extractor:archetype-declare` / `extractor:archetype-playbook`).

**Notes**
- Indexing is incremental/idempotent — safe to re-run.
- Freshness is lazy by design (no file-watcher reindex; `wicked-estate watch`
  exists for opt-in). Estate reports **staleness** on queries and prints a
  `STALENESS: N commit(s) since last index` marker — re-run `index` when stale.
- Binary resolution: `WICKED_ESTATE_BIN` env → `PATH` → `~/.local/bin`
  (`scripts/_estate_client.py` is the Python reach-shim for hooks).

## Resolving symbols + fallback ladder (shared by blast-radius and lineage)

**Resolve the symbol.** Estate tools take symbol **names** directly (a file
node's name is its repo-relative path, e.g. `scripts/_bus.py`). When a name is
ambiguous or you need the node id, resolve it first with the estate MCP
`SearchEntity` tool (`{"name": "<symbol>"}` → matches with ids and kinds).

**Fallbacks** (in order):
1. If the estate MCP server isn't connected, shell the CLI directly:
   `wicked-estate blast-radius <name>` / `wicked-estate query <name>`
   (resolve the binary via `WICKED_ESTATE_BIN` → PATH → `~/.local/bin`).
2. If estate is unreachable entirely, fall back to Grep/Glob for literal
   refs — and **flag that injected relationships will be MISSING** from the
   result (injected/string-keyed links are invisible to grep).

## Blast radius — "what breaks if I change X?"

Analyze what would be affected if you changed a symbol — traces **dependents**
(what uses this) over the code-relationship graph, including injected edges
(bus/dispatch/capability/archetype) that grep and a static call-graph cannot see.

> **Scope**: `blast-radius` answers "what breaks if I change X?" (the
> dependents graph). For **data-flow tracing** (UI field → DB column or
> reverse), use the `lineage` action.

**Arguments**: `symbol` (required — a file path like `src/app.py`, or a symbol
name); `--depth` (optional traversal depth; estate default 8, max 24).
Starting from a **file path** returns its **importer files** as dependents
(File→File import edges), so `blast-radius scripts/_bus.py` answers "which
files import this file" — no longer an empty "no resolved dependents".

1. **Ensure the graph is fresh** (§ Index / freshness): `wicked-estate index <path>`.
   Estate prints a `STALENESS` marker when commits have landed since the last
   index; re-run after editing.
2. **Resolve the symbol** (§ Resolving symbols).
3. **Query blast radius from estate** (static + injected dependents in one
   answer — the authoritative layer): call the estate MCP **`BlastRadius`**
   tool with `{"symbol": "<name-or-path>", "depth": <n>}`.
   The `dependents` array includes relationships grep can't see: a command that
   *dispatches* an agent, a consumer that *subscribes* to an event, an agent
   that *declares* a capability — and archetype→playbook relationships via
   garden's `.wicked-estate-extractors/archetype.toml` (provenance
   `extractor:archetype-playbook`). Results carry confidence + provenance per
   edge and an `unresolved_callers` count — reference sites **no resolver could
   bind** (repeat call sites of an already-bound relationship are NOT counted,
   so `0` is a legitimate value for a fully-resolved hot symbol; counts are
   much lower than under the pre-2026-08 over-counting definition).
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

**Arguments**: `symbol` (required — a file path or symbol name);
`--direction` (optional, default `downstream`): `downstream` (dependencies),
`upstream` (dependents), or `both`; `--depth` (optional traversal depth;
estate default 8, max 24).

1. **Ensure the graph is fresh** (§ Index / freshness): `wicked-estate index <path>`.
2. **Resolve the symbol** (§ Resolving symbols).
3. **Trace** via the estate MCP:
   - **downstream** (what it depends on): the **`Lineage`** tool with
     `{"symbol": "<name>"}` → `dependencies`.
   - **upstream** (what depends on it): the **`BlastRadius`** tool with
     `{"symbol": "<name>"}` → `dependents`.
   - **both**: run both and present each direction. (A bounded multi-hop walk
     with edge-kind filters is available via the **`TraverseGraph`** tool.)
   Each result includes injected edges (e.g. a consumer reached via a bus
   rule, an archetype via `extractor:archetype-playbook`) with confidence +
   provenance per edge.
4. **Fallbacks**: § Resolving symbols + fallback ladder.
5. Report each path (source → sink), file locations per step, provenance of
   injected hops, and gaps.

**Examples**
```
lineage scripts/_bus.py --direction upstream
lineage User.email --direction both
```

## Hotspots — most-central symbols

Rank symbols by PageRank centrality to expose god-objects, coupling
hotspots, and high-impact refactor targets — the estate MCP `RankHotspots`
tool. → Full procedure: [refs/hotspots.md](refs/hotspots.md)

## Service map — detect the service architecture

Detect services and their connections from infrastructure config
(docker-compose/k8s/helm) plus code patterns; report as table, json, or
mermaid. → Full procedure: [refs/service-map.md](refs/service-map.md)

## Narrate — codebase orientation

For "give me an architecture walkthrough" / "narrate this codebase" / "where
should I start reading", use the nested skill:
[codebase-narrator/SKILL.md](codebase-narrator/SKILL.md) — produces a guided
reading order, annotated directory map, data-flow diagram, and gotchas list.

## Answer — cited synthesis ("ask the record")

For "answer this from the knowledge base" / "what does the record say about
X", load [refs/answer.md](refs/answer.md) — synthesizes an answer strictly
from wicked-estate `knowledge.recall` + `memory.recall` results, citing each
claim's `source`. Shared with the `wicked-garden-mem` skill's `answer` action.
