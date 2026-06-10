# ADR 0004 — Move the code-relationship graph to wicked-brain (inverts ADR 0001's homing)

- **Status:** Accepted
- **Date:** 2026-06-10
- **Supersedes:** the *homing* decision of [ADR 0001](0001-code-relationship-graph-engine.md) (graph lives in garden). **Keeps** ADR 0001's engine choice (codegraph) and the injected-edge concept.
- **Context owners:** wicked-garden + wicked-brain
- **Implements:** `docs/specs/2026-06-10-codegraph-to-brain-migration.md` (decisions D1–D6).

## Context

ADR 0001 adopted `@colbymchenry/codegraph` + wicked-garden-specific injected-edge extractors **inside garden**, and noted in passing that `search:blast-radius`/`lineage` were "wrongly" calling the brain (hardcoded to the wrong port) and concluded the fix was to *pull the graph into garden*.

That instinct was backwards. "What breaks if I change X" / "what flows where" / "who depends on this" are **knowledge** questions about relationships — and the brain is the knowledge layer. It already shipped LSP-based code intelligence (`wicked-brain:lsp` advertised blast-radius/architecture). So the ecosystem had **two half-built code-intelligence stacks** answering overlapping questions in different repos. The decisive constraint: the graph is valuable to *every* repo, and requiring all of wicked-garden just to give a repo enhanced code/graph knowledge is unacceptable.

## Decision

**Move the code-relationship graph to `wicked-brain`.** Brain owns the engine integration, the unified graph, and every relationship query (blast-radius / callers / lineage). Garden becomes a **consumer**. The line is *knowing* (brain) vs *doing* (garden — deterministic refactor, gates, archetypes).

Per the spec's locked decisions:
- **D1/D2** Brain owns the graph + queries; **zero garden dependency** — brain is valuable standalone; the dependency arrow only ever points garden→brain.
- **D3** Brain ships the generic/ecosystem extractors (bus, command→agent dispatch, capability); a **pluggable drop-in registry** (`<repo>/.codegraph-extractors/*.mjs`) lets any plugin contribute proprietary extractors (garden's archetype extractor) without brain importing the plugin.
- **D4** codegraph = graph-of-record; LSP = live single-symbol precision (blast-radius/architecture moved off the lsp skill onto `wicked-brain:graph`).
- **D5** Lazy staleness stamp + opt-in commit hook; **never** a watcher-driven full reindex (a known CPU-runaway hazard).
- **D6** The graph DB stays codegraph-native (`<repo>/.codegraph/codegraph.db`); brain reads it directly via better-sqlite3.

### What ADR 0001 keeps vs changes
| | 0001 | 0004 |
|---|---|---|
| Engine | codegraph (adopt, runtime peer) | **unchanged** |
| Injected-edge concept | yes | **unchanged** |
| Home of the graph + queries | wicked-garden | **wicked-brain** |
| blast-radius/lineage owner | garden commands | **brain `graph-*` actions + `wicked-brain:graph` skill** |
| bus edge direction | `source=producer, target=consumer` (latent bug — blast-radius(producer) saw nothing) | **`source=consumer, target=producer`** (consumer depends on the producer's event contract; blast-radius(producer) surfaces the consumer) |

## Consequences

- **Any repo** gets relationship-graph knowledge by running wicked-brain — no garden required. Verified on a real repo: brain `graph-index` on wicked-garden built the static graph + 20 injected edges, and `blast-radius(scripts/_bus.py)` surfaced the `jam` consumer wired only by the `wicked.persona.contributed` event string (grep-invisible).
- Garden's `scripts/_codegraph.py` + `scripts/codegraph/*` (the in-garden engine shim + extractors) are **superseded** by the brain implementation and are removed/aliased (this PR family).
- `search:blast-radius` / `search:lineage` rewire to brain's `graph-*` actions (no more grep-with-extra-steps).
- wicked-patch consumes the same codegraph-native `.codegraph/codegraph.db` brain builds (via `scripts/engineering/patch/codegraph_db.py`) — unchanged contract.
- garden ships its proprietary **archetype** extractor as a brain drop-in (`.codegraph-extractors/archetype.mjs`), discovered by brain's registry — the D3 mechanism in action.

## Implementation

- wicked-brain: Phase 1a (graph core) + Phase 1b (injected edges + extractor registry) — see wicked-brain PR.
- wicked-garden: Phase 2 — archetype drop-in, command rewire, this ADR, CLAUDE.md update.
- Plans: `docs/plans/2026-06-10-codegraph-to-brain-phase1a-graph-core.md`, `docs/plans/2026-06-10-codegraph-to-brain-phase1b-injected-edges.md`.
