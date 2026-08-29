# Hotspots — find the most-central symbols

Rank symbols by PageRank centrality over the code-relationship graph to expose
god-objects, coupling hotspots, and high-impact refactor targets.

**Arguments**: `--limit <n>` (optional): number of results (default 20, max 200).

## Instructions

1. **Freshness** — ensure the graph is current with the search skill's `index`
   action (`wicked-estate index <path>` builds the static graph + injected
   edges; estate prints a `STALENESS` marker when commits have landed since
   the last index). The ranking below reads that graph.
2. **Primary path — the estate MCP `RankHotspots` tool**: call it with
   `{"limit": <n>}` (optionally `{"seeds": ["<symbol>", …]}` for a
   personalized, subsystem-local ranking). PageRank over Calls+Imports edges —
   strictly better than a raw incoming-edge count, because it weights a
   reference by the centrality of the referrer.

   Report the ranked list. Call out anything with an unusually high score as a
   likely god-object or coupling hotspot worth refactoring. Injected edges are
   part of the same graph — a heavily-dispatched agent or capability appears
   here too. File and Import nodes are **excluded** from the ranking
   (symbol-level hotspots only — files never appear, however many File→File
   import edges they carry); injected non-file nodes (agents, capabilities,
   archetypes) still rank.

3. **Fallback — the estate CLI** (MCP server not connected):
   ```bash
   wicked-estate rank        # same PageRank ranking, top-N to stdout
   ```
   (Resolve the binary via `WICKED_ESTATE_BIN` env → `PATH` → `~/.local/bin`.)

4. **If estate is unavailable entirely**: say so and suggest the search
   skill's `index` action after installing wicked-estate — and note that any
   grep-based approximation misses injected relationships and referral
   centrality.

## Example

```
hotspots
hotspots --limit 10
```
