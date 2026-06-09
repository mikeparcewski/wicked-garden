# ADR 0001 — Code-relationship graph: adopt codegraph as the engine, add injected-edge extractors

- **Status:** Accepted (prototype validated)
- **Date:** 2026-06-09
- **Context owners:** wicked-garden

## Context

Three features need a real code-relationship graph, and none works today:

- **`search:blast-radius`** — "what breaks if I change X" — currently runs a brain
  search (hardcoded to the wrong port, 4242; the brain is on 4243) + `grep`. It is
  effectively grep-with-extra-steps.
- **`search:lineage`** — data flow — same shape.
- **wicked-patch** (`engineering:rename`/`add-field`/`remove`) — deterministic
  multi-file refactor — requires a symbol `--db` that **nothing in the ecosystem
  produces**, so the whole family is dead-on-arrival.

The decisive requirement is **injected relationships**: this plugin's load-bearing
edges are wired by a shared *string* through a registry, never by a literal symbol
reference, so neither `grep` nor a static call-graph can see them:

| Injected edge (grep-/static-invisible) | Wired by (deterministically extractable) |
|---|---|
| event producer → consumer | `emit_event("wicked.x")` + `_bus_consumers.json` `event_filter` |
| command/Task → agent | `subagent_type:` frontmatter |
| agent → tool | `tool-capabilities` + `_capability_registry` |
| hook event → script | `hooks.json` |
| archetype → playbook/gate | `archetypes.json` + `refs/` |

## Decision

**Adopt [codegraph](https://github.com/colbymchenry/codegraph) (`@colbymchenry/codegraph`, MIT,
TypeScript/web-tree-sitter) as the static code-graph engine, consumed as a
runtime-resolved peer** (the same model as wicked-loom/vault/testing/bus), and
**add wicked-garden-specific injected-edge extractors on top.** Do not build a
graph engine from scratch — re-implementing multi-language tree-sitter resolution
to codegraph's fidelity is months of work it already does.

### Why codegraph (vs roam-code, vs build)
Both codegraph and [roam-code](https://github.com/Cranot/roam-code) (Apache-2.0,
Python) are credible "adopt-as-engine" candidates. codegraph wins for us on two
decisive axes:

1. **Architecture fit** — it ships a CLI + MCP server + a plain SQLite contract and
   is npm/node, exactly how we already consume our peers (a `_codegraph.py` shim
   mirrors `_loom.py`). roam-code is a Python library — a different integration shape.
2. **Patch precision** — codegraph is **column-precise** (`file:line:col` on nodes
   *and* reference sites) with real import/alias/workspace/re-export/JVM-FQN
   resolution and confidence/provenance per edge. roam-code is line-granular +
   heuristic name resolution (false-positive risk) — riskier to refactor against.

**Borrow, don't adopt, from roam-code:** its Code-Graph Attestation (re-derive
Merkle/edge digests from the live DB, fail-closed) is a genuine twin of our vault
gate, operating on a layer the vault doesn't cover; and its `oracle_*` deterministic
fact tools are clean gate inputs. We keep it at arm's length because it is a
*competing change-governance framework* (constitution/permits/leases) that overlaps
wicked-garden's entire premise — we want a code-graph *component*, not to outsource
our governance.

## Validation (prototype, this ADR)

Run on this repo, Node 26:

- `codegraph index` → **4,179 nodes / 7,733 edges** across 196 Python files in ~1s;
  plain SQLite at `.codegraph/codegraph.db` (auto-gitignored). `codegraph impact <symbol>`
  (blast-radius) and `query`/`callers` work out of the box.
- `scripts/codegraph/inject_edges.py` (the first injected-edge extractor) reads
  `_bus_consumers.json` + emit sites and materializes producer→consumer edges:
  `file:scripts/_bus.py --[wicked.persona.contributed]--> file:scripts/jam/_bus_consumers.py`.
  codegraph's static graph had **0** such edges; `grep` finds **no** link between
  producer and consumer (they share only the event string). Blast-radius now
  traverses them.
- Bonus finding: a consumer in `_bus_consumers.json` (`crew:auto-advance`) points at
  `scripts/crew/_bus_consumers.py`, which **does not exist** — a stale registry entry
  the graph build surfaced.

## Architecture

```
codegraph (static: symbols + imports/calls/refs, column-precise, SQLite)
        +  injected-edge extractors (deterministic, per wiring mechanism)
             bus emit↔_bus_consumers.json   [prototype: scripts/codegraph/inject_edges.py]
             command→agent (subagent_type)  [next]
             agent→tool (capabilities)       [next]
        +  data-flow lineage layer           [build: neither engine provides general lineage]
        =  the relationship graph
        →  consumers: blast-radius, lineage, wicked-patch (--db)
```

- **Peer shim** `scripts/_codegraph.py` — resolves + runs the codegraph CLI/MCP
  exactly like `_loom.py` does for loom (env `WICKED_CODEGRAPH_BIN` → config → PATH →
  npx). Pin Node ≥ 22.5 (codegraph uses `node:sqlite`); we run 26.
- **Injected edges** carry their semantics in the edge `metadata` (codegraph's
  node/edge `kind` are closed unions; `references` + `provenance='injected:<mechanism>'`
  is the no-fork convention). Coverage caveat: if a wired file isn't a codegraph
  node, the extractor skips it (and that itself flags stale wiring, as above).

## Consequences

- blast-radius/lineage flip from **redundant** (grep+broken) → **genuinely
  differentiated** (they answer injected-relationship questions grep cannot).
- wicked-patch flips from **broken** (no `--db`) → **working** (consumes the
  codegraph SQLite as its symbol DB).
- **Risk:** codegraph bus-factor = 1. Mitigated by MIT license + the SQLite schema
  being a stable, self-describing contract we can read even if upstream stalls.
- **Lock-in:** low — we depend on a documented SQLite shape, not an opaque service.

## Roadmap

1. ✅ Prototype: peer shim + bus injected-edge extractor + blast-radius proof (this ADR).
2. command→agent and agent→tool extractors (same pattern as the bus extractor).
3. Rewire `search:blast-radius`/`lineage` to query the graph (and fix the 4242→4243 port).
4. Wire wicked-patch to consume the codegraph SQLite as its `--db` (revives the patch family).
5. Build the data-flow lineage layer on top.
6. Evaluate borrowing roam-code's Code-Graph Attestation as a complement to the vault gate.
