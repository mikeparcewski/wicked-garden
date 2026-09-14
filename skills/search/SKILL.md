---
name: wicked-garden-search
user-invocable: true
description: |
  Code-intelligence search over wicked-estate's static + injected
  code-relationship graph (ADR 0005): index (build/refresh), blast-radius
  (dependents), lineage (data/dependency flow), hotspots (PageRank
  centrality), service-map (infra + code), narrate (orientation walkthrough).
  Every graph read is ONE call on every seat, in every session kind — the
  read-only estate shim (`wicked-garden run scripts/_estate_client.py
  --readonly call …`).

  Use when: "index the codebase"; "what breaks if I change X" / "blast
  radius" / "impact analysis"; "trace lineage" / "upstream or downstream of a
  symbol"; "most-referenced symbols" / "god objects" / "coupling hotspots";
  "map the services"; "architecture walkthrough" / "narrate this codebase".

  NOT for concept/memory search — use `wicked-garden-mem`; a bare symbol
  lookup is the estate `SearchEntity` tool through the same shim.
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# wicked-garden:search — code-intelligence over the estate graph

All actions delegate to **wicked-estate**, which owns the unified static + injected code-relationship
graph as of ADR 0005 (superseding the brain-homed graph of ADR 0004). Garden no longer maintains its own
graph; it consumes estate's. Garden contributes its proprietary **archetype** edges to estate's graph via
the drop-in TOML rules in `.wicked-estate-extractors/archetype.toml` (auto-discovered by `wicked-estate index`).

## Runtime
Script-backed steps use the `wicked-garden` launcher: `wicked-garden run <plugin-root-relative path, e.g. scripts/…> [args]`. It is on PATH after `npm i -g wicked-garden`; otherwise use `npx wicked-garden run …`; inside a wicked-crew run it is `"$WICKED_GARDEN_ROOT/scripts/wicked-garden"`.
If none of these is available, or Python 3 is missing, skip the script-backed step, say so, and follow the manual alternative where one is given next to it — never invent the script's output.
Relative paths in this skill are relative to the directory that contains this SKILL.md.

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

Doctrine / which-rules-apply: **Steering** (the governance rules, 7 steering types) is in the same stores — the estate `knowledge.recall` tool through the shim — `wicked-garden run scripts/_estate_client.py --readonly call '{"tool":"knowledge.recall","arguments":{"scope_prefix":"wiki:",…}}'` (`wiki:` is a historical prefix) — + the estate `rules.recall` tool the same way (§ Resolving symbols) (cited, read-only); management: wicked-core `crates/wicked-governance/STEERING.md`.

## Index / freshness (shared by every action)

The graph lives in **wicked-estate** (ADR 0005): a 75-language tree-sitter
static graph **plus** injected domain edges, built by the estate binary — no
external engine, no Node version floor.

1. **Build / refresh** (operator work at a terminal — never from a seat; see the rule below the list) — one
   command rebuilds the static graph **and** re-applies every injected-edge rule
   (per-repo TOML drop-ins under `.wicked-estate-extractors/`, e.g. garden's archetype rules):
   ```bash
   wicked-estate index <path>        # DB defaults to .wicked-estate/graph.db
   ```
   Incremental and idempotent — unchanged files are skipped; editing the extractor
   rules forces a full re-extract. The estate binary the shim spawns serves the same DB, so a refresh is
   immediately visible to the tools. Freshness is lazy (opt-in `wicked-estate watch`);
   estate prints a `STALENESS: N commit(s) since last index` marker — re-run when stale.
2. **Verify**: `wicked-estate stats` reports node/edge counts plus `unresolved=N`
   (references no resolver could bind — a health signal, not an error count); archetype
   wiring shows as injected edges (provenance `extractor:archetype-*`).

**From a seat — any seat, any session kind** (a governed run's unit, a chat turn, any session
where you are the agent): the graph is handed to you already indexed and the write CLI is **never**
yours: never `wicked-estate index`, never `wicked-estate scip|tfstate|import-telemetry|compact|watch`,
never `wicked-estate clusters --annotate`. A stale graph is *reported* through its
`STALENESS` marker, not rebuilt. Binary resolution: `WICKED_ESTATE_BIN` env → `PATH` → `~/.local/bin`.

## Resolving symbols + the one way to the graph (shared by every action)

**The one way to the graph — on every seat, in every session kind** (a governed run's unit, a chat
turn, a human session at a terminal): the estate shim in read-only mode, store pinned by the
environment. Every estate tool named in this skill is reachable through its `call` action:
```bash
wicked-garden run scripts/_estate_client.py --readonly call '{"tool":"BlastRadius","arguments":{"symbol":"<name>"}}'
```
`--readonly` is literal (the spawned estate binary reads only; `WICKED_ESTATE_READONLY=1` rides
every worker so it spawns read-only by default). The store rides `WICKED_ESTATE_DB` /
`WICKED_HOME` / `WICKED_MEMORY_DB` from the environment, or `--db <path>`; the shim refuses an
unpinned store (`{"ok": false, "reason": …}`) — report that, never guess a store. There is no
other transport: no estate tool is registered on any seat, so there is nothing to "connect",
nothing to fall back to, and no second rung — a grep is not the graph.

**Resolve the symbol.** Estate tools take symbol **names** directly (a file node's name is its
repo-relative path, e.g. `scripts/_bus.py`); when a name is ambiguous or you need the node id,
resolve it first:
```bash
wicked-garden run scripts/_estate_client.py --readonly call '{"tool":"SearchEntity","arguments":{"name":"<symbol>"}}'
```
`name` is the exact / substring symbol match; `query` is full-text over the knowledge stores and
answers `matches: []` for a code symbol — a 0-hit `query` does not mean the graph is empty.

**Name the path that answered** (`shim` or `ungrounded`) in every result. If the shim answers
`{"ok": false, …}` or the fence denies the call, write `estate: not available (<reason>)` in your
output and continue **UNGROUNDED** — report the gap; do not substitute grep for the graph. A
denied call is final: record it — no variants, no wrappers, no retry
(`wicked-garden-governed-worker` A2/A5). The `wicked-estate` CLI is not a rung: its write verbs
are never run from a seat (§ Index / freshness) and its read verbs are not how a seat grounds.

## Blast radius — "what breaks if I change X?"

Analyze what would be affected if you changed a symbol — traces **dependents**
(what uses this) over the code-relationship graph, including injected edges
(bus/dispatch/capability/archetype) that grep and a static call-graph cannot see.
For **data-flow tracing** (UI field → DB column or reverse) use the `lineage` action.

**Arguments**: `symbol` (required — a file path like `src/app.py`, or a symbol
name); `--depth` (optional traversal depth; estate default 8, max 24).
Starting from a **file path** returns its **importer files** as dependents
(File→File import edges), so `blast-radius scripts/_bus.py` answers "which
files import this file" — no longer an empty "no resolved dependents".

1. **Freshness** (§ Index / freshness) — read the `STALENESS` marker and report it; never
   rebuild from a seat.
2. **Resolve the symbol** (§ Resolving symbols).
3. **Query blast radius from estate** (static + injected dependents in one
   answer — the authoritative layer): the estate **`BlastRadius`**
   tool with `{"symbol": "<name-or-path>", "depth": <n>}` through the shim (§ Resolving symbols).
   The `dependents` array includes relationships grep can't see: a command that
   *dispatches* an agent, a consumer that *subscribes* to an event, an agent that
   *declares* a capability — and archetype→playbook relationships via garden's
   `.wicked-estate-extractors/archetype.toml` (provenance `extractor:archetype-playbook`).
   Results carry confidence + provenance per edge and an `unresolved_callers` count —
   reference sites **no resolver could bind** (repeat call sites of a bound relationship
   are NOT counted, so `0` is legitimate for a fully-resolved hot symbol).
4. **Path**: the shim (§ Resolving symbols + the one way to the graph) — or `ungrounded`, said so.
5. Report: **dependents** (static + injected, with provenance), total blast-radius
   count, files affected, the graph's staleness, and **which path answered** (`shim` / `ungrounded`).

Examples: `blast-radius scripts/_bus.py` · `blast-radius UserService --depth 3`.

## Lineage — "where does this flow from / to?"

Trace flow through the code-relationship graph. Downstream = what the symbol depends
on; upstream = what depends on it. Includes injected edges grep can't see.

For pure "what breaks if I change X?" use the `blast-radius` action.

**Arguments**: `symbol` (required — a file path or symbol name);
`--direction` (optional, default `downstream`): `downstream` (dependencies),
`upstream` (dependents), or `both`; `--depth` (optional traversal depth;
estate default 8, max 24).

1. **Freshness** (§ Index / freshness) — report the `STALENESS` marker; never rebuild from a seat.
2. **Resolve the symbol** (§ Resolving symbols).
3. **Trace** with the estate tools through the shim:
   - **downstream** (what it depends on): the **`Lineage`** tool with
     `{"symbol": "<name>"}` → `dependencies`.
   - **upstream** (what depends on it): the **`BlastRadius`** tool with
     `{"symbol": "<name>"}` → `dependents`.
   - **both**: run both and present each direction. (A bounded multi-hop walk
     with edge-kind filters is available via the **`TraverseGraph`** tool.)
   Each result includes injected edges (e.g. a consumer reached via a bus
   rule, an archetype via `extractor:archetype-playbook`) with confidence +
   provenance per edge.
4. **Path**: the shim (§ Resolving symbols + the one way to the graph) — or `ungrounded`, said so.
5. Report each path (source → sink), file locations per step, provenance of
   injected hops, gaps, and **which path answered** (`shim` / `ungrounded`).

Examples: `lineage scripts/_bus.py --direction upstream` · `lineage User.email --direction both`.

## Hotspots — most-central symbols

Rank symbols by PageRank centrality to expose god-objects, coupling
hotspots, and high-impact refactor targets — the estate `RankHotspots`
tool through the shim. → Full procedure: [refs/hotspots.md](refs/hotspots.md)

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

For "answer this from the knowledge base" / "what does the record say about X", load
[refs/answer.md](refs/answer.md) — synthesizes an answer strictly from wicked-estate `knowledge.recall` +
`memory.recall` results, citing each claim's `source`. Shared with the `wicked-garden-mem` skill's `answer` action.
