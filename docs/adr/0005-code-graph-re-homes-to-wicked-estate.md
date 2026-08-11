# ADR 0005 — Re-home the code-relationship graph to wicked-estate (supersedes ADR 0004)

- **Status:** Accepted
- **Date:** 2026-08-11
- **Supersedes:** [ADR 0004](0004-code-graph-moves-to-wicked-brain.md) **in full** — the graph's
  home moves from `wicked-brain` to `wicked-estate`. Also **retires the engine choice** carried
  forward from [ADR 0001](0001-code-relationship-graph-engine.md): `@colbymchenry/codegraph` is
  replaced by estate's own 75-language tree-sitter extractor. What ADR 0001/0004 got right — a real
  relationship graph with **injected edges** as the load-bearing idea — stands; only the home and
  the engine change.
- **Context owners:** wicked-garden + wicked-estate
- **Relates to (estate):** estate `docs/adr/ADR-005-code-intel-as-a-brain.md` (code-intel as a brain),
  estate `docs/adr/ADR-001-graph-schema.md` (graph schema),
  estate `docs/extractor-sdk.md`, estate `CLAUDE.md`. (Cross-repo references are given as
  paths, not links — they resolve in the `wicked-estate` repo, not this one.)
- **Retarget checklist:** [`0005-retarget-inventory.md`](0005-retarget-inventory.md) — the actionable
  call-site → estate mapping that Stage S5 executes.

## Context

ADR 0004 homed the code-relationship graph in `wicked-brain`: brain shelled `@colbymchenry/codegraph`
to build a per-repo `.codegraph/codegraph.db`, read it back over `graph-*` server actions + a
`wicked-brain:graph` skill, and let plugins contribute proprietary injected edges through a drop-in
registry (`<repo>/.codegraph-extractors/*.mjs`). Garden became a consumer: `skills/search/SKILL.md`,
`skills/search/refs/hotspots.md`, and `wicked-patch` (`scripts/engineering/patch/codegraph_db.py`)
all target that brain surface, and garden ships `.codegraph-extractors/archetype.mjs` as its drop-in.

Two facts have since changed the ground under ADR 0004:

1. **The brain graph is gone.** ADR 0004's implementation is stripped from the current wicked-brain
   working tree — there is no `wicked-brain-graph` skill, no `@colbymchenry/codegraph` dependency,
   and no `graph-*` server action. Every garden call-site above therefore points at a **surface that
   no longer exists** — an already-dangling contract, not a live coupling.

2. **wicked-estate already owns a more capable graph.** Per the ecosystem's center-of-gravity
   decision (root `CLAUDE.md`: *"wicked-estate is the center of gravity — code graph, memory, and
   knowledge live there; everything else is a consumer"*), estate independently built the exact
   capability ADR 0004 described, and more:
   - a **75-language tree-sitter extractor** (`wicked-estate-extract`, `LANG_TABLE` /
     `languages.toml`) — no external `codegraph` peer, no Node ≥ 22.5 requirement;
   - an **`ExtraEdgeExtractor`** (`crates/wicked-estate-extract/src/extra_edge.rs`,
     `docs/extractor-sdk.md` Part 2) that injects event-bus / command-dispatch / framework-hook edges
     from a **plain TOML rule file** — the same "grep-invisible injected edge" idea as ADR 0001's
     extractors and archetype.mjs, but as data instead of per-repo JS;
   - the **`wicked-estate-overlay` `XedgeStore`** (`crates/wicked-estate-overlay/src/xedge.rs`) for
     injected **cross-store / cross-repo** edges — a capability the brain graph never had;
   - **`BlastRadius`, `Lineage`, `TraverseGraph`, `RankHotspots`, `SearchEntity`, `RetrieveEntity`**
     as **live MCP tools** (`crates/wicked-estate-mcp/src/lib.rs`, backed by
     `crates/wicked-estate-retrieve/src/lib.rs`).

   Estate's own ADR-005 frames this as its through-line — *"make wicked_estate a **brain** — store the
   actual content, cache expensive results, and run cross-graph queries"* — with blast-radius,
   lineage, and cross-graph joins as first-class query surfaces. The graph question ADR 0004 was
   trying to answer ("what breaks / what flows where / who depends on X") is exactly what estate is
   for.

So the ecosystem no longer has "two half-built code-intelligence stacks" (ADR 0004's framing). It has
**one mature stack in estate** and a **set of dangling garden pointers at a retired brain surface**.

## Decision

**Re-home the code-relationship graph to `wicked-estate`.** Estate owns the engine (its tree-sitter
extractor), the injected-edge extraction (`ExtraEdgeExtractor` TOML rules), the cross-repo overlay
(`XedgeStore`), and every relationship query (`BlastRadius` / `Lineage` / `TraverseGraph` /
`RankHotspots`) exposed as MCP tools. Garden stays a **consumer** — the *knowing* (estate) vs *doing*
(garden: deterministic refactor, gates, archetypes) line from ADR 0004 is preserved; only the "knowing"
provider changes from brain to estate.

This is a **retarget, not a port.** Estate already implements every capability the brain surface
promised, at higher fidelity (75 languages vs a codegraph peer; TOML rules vs per-repo JS drop-ins;
cross-repo overlay the brain never had). There is no code to move — only garden call-sites to repoint.

### What ADR 0004 keeps vs changes

| | 0004 (brain) | 0005 (estate) |
|---|---|---|
| Home of the graph + queries | wicked-brain | **wicked-estate** |
| Static engine | `@colbymchenry/codegraph` peer (Node ≥ 22.5) | **estate `wicked-estate-extract`** — 75-language tree-sitter, in-binary |
| Injected edges | per-repo JS drop-ins `<repo>/.codegraph-extractors/*.mjs` | **`ExtraEdgeExtractor` TOML rules** (`.wicked-estate-extractors/<name>.toml`, `extra_edge.rs`) |
| Cross-repo / cross-store edges | none | **`wicked-estate-overlay` `XedgeStore`** (`xedge.db`) |
| blast-radius / lineage owner | brain `graph-*` actions + `wicked-brain:graph` skill | **estate MCP tools `BlastRadius` / `Lineage` / `TraverseGraph` / `RankHotspots`** |
| Graph DB | `<repo>/.codegraph/codegraph.db` (codegraph-native SQLite) | **estate index DB** (`wicked-estate index <path>`; queried via MCP, not read raw) |
| wicked-patch symbol source | reads `.codegraph/codegraph.db` directly | **estate graph** (via MCP / an estate export) |
| Injected-edge direction | `source = dependent, target = producer/playbook`; blast-radius = dependents | **unchanged in spirit** — estate invariant is `source = dependent, target = dependency`, blast-radius = dependents (`xedge.rs` header; estate `CLAUDE.md`). The archetype rule ports **without a direction flip.** |

### What stands from ADR 0001 / 0004

- **Injected relationships are the whole point.** Garden's load-bearing edges (event producer→consumer,
  command→agent, agent→tool, archetype→playbook) are wired by a shared *string* through a registry,
  never a literal symbol reference — invisible to grep and to a static call-graph. Estate's
  `ExtraEdgeExtractor` is the direct, more-capable successor to ADR 0001's `inject_edges.py` and
  archetype.mjs: same idea (deterministic edge injection per wiring mechanism), expressed as TOML data
  the estate binary applies, with a shared **`node_scheme` convergence key** so producers and consumers
  of the same topic land on one synthetic node (`docs/extractor-sdk.md` Part 2, event-bus example).
- **The knowing/doing split** (brain/estate knows; garden does) is preserved verbatim — only the
  knowing provider changes.

## Consequences

- **The dangling contracts get a real target.** Every garden call-site that today references a
  retired brain surface (`graph-index`, `graph-blast-radius`, `graph-lineage`, `wicked-brain:graph`,
  raw `.codegraph/codegraph.db` reads) maps to a live estate MCP tool or the estate graph. The exact
  mapping is [`0005-retarget-inventory.md`](0005-retarget-inventory.md).
- **Any repo** gets relationship-graph knowledge by running the wicked-estate MCP server — no garden
  required and, unlike ADR 0004, **no external codegraph peer / Node version floor** either.
- **Garden's archetype extractor is re-authored, not dropped.** `.codegraph-extractors/archetype.mjs`
  (JS, better-sqlite3, `INSERT INTO edges …`) becomes an estate `ExtraEdgeExtractor` TOML rule set —
  the archetype→playbook edge that no grep can see is preserved, now as data estate applies at index
  time. This is the single highest-effort inventory item because estate's regex-per-file rule model
  differs from archetype.mjs's JSON-catalog-plus-file-existence logic; the inventory records the
  recommended shared-`node_scheme` modeling.
- **Cross-repo blast-radius becomes possible** (estate `XedgeStore`) — a capability the brain graph
  never had. Out of scope for S5's mechanical retarget, but this ADR homes it in estate so it has a
  place to land.
- **No consumer code changes in this ADR.** This PR is the decision + the checklist only. The
  retarget edits (skill rewrites, `codegraph_db.py` repoint, the archetype TOML rule,
  `.claude/CLAUDE.md` and `.product/*` doc refresh) are executed in **Stage S5** against the inventory.

## Implementation

- **This PR (Stage S0):** ADR 0005 + [`0005-retarget-inventory.md`](0005-retarget-inventory.md); mark
  ADR 0004 superseded (its Status banner). No consumer code touched.
- **Stage S5 (later):** execute the retarget inventory — repoint `skills/search/*` to estate MCP
  tools, repoint `scripts/engineering/patch/codegraph_db.py` to the estate graph, author the archetype
  `ExtraEdgeExtractor` TOML rule against `crates/wicked-estate-extract/src/extra_edge.rs` /
  `docs/extractor-sdk.md`, and refresh the doc/spec references (`.claude/CLAUDE.md`, `.product/*`,
  `README.md`).
- **Estate side (already built):** MCP tools registered in `crates/wicked-estate-mcp/src/lib.rs`;
  extractor SDK in `crates/wicked-estate-extract/src/extra_edge.rs` + `docs/extractor-sdk.md`;
  cross-repo overlay in `crates/wicked-estate-overlay/src/xedge.rs`. Nothing to build in estate for
  the core retarget.
