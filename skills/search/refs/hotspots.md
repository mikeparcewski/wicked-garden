# Hotspots — find the most-central symbols

Rank symbols by PageRank centrality over the code-relationship graph to expose
god-objects, coupling hotspots, and high-impact refactor targets.

**Arguments**: `--limit <n>` (optional): number of results (default 20, max 200).

## Instructions

1. **Freshness** — read the `STALENESS` marker the result carries and report it. The graph is
   rebuilt by an operator at a terminal (`wicked-estate index <path>` — the search skill's
   `index` action), never from a seat.
2. **The estate `RankHotspots` tool through the read-only shim** — the one way, on every seat
   and in every session kind (store pinned by the environment; see the search skill's
   "Resolving symbols + the one way to the graph"):
   ```bash
   wicked-garden run scripts/_estate_client.py --readonly call '{"tool":"RankHotspots","arguments":{"limit":20}}'
   ```
   Optionally `{"seeds": ["<symbol>", …]}` for a personalized, subsystem-local ranking.
   PageRank over Calls+Imports edges — strictly better than a raw incoming-edge count,
   because it weights a reference by the centrality of the referrer.

   Report the ranked list. Call out anything with an unusually high score as a
   likely god-object or coupling hotspot worth refactoring. Injected edges are
   part of the same graph — a heavily-dispatched agent or capability appears
   here too. File and Import nodes are **excluded** from the ranking
   (symbol-level hotspots only — files never appear, however many File→File
   import edges they carry); injected non-file nodes (agents, capabilities,
   archetypes) still rank.

3. **If the shim answers `{"ok": false, …}`** (no store pinned, estate not installed): write
   `estate: not available (<reason>)`, say what would fix it (install wicked-estate, index the
   repo at a terminal), and continue **ungrounded** — a grep-based approximation misses injected
   relationships and referral centrality, so it is not the ranking; name the path that answered
   (`shim` / `ungrounded`).

## Example

```
hotspots
hotspots --limit 10
```
