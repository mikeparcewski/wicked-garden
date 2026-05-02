---
description: Find the most-referenced symbols in the codebase — classes, functions, and modules with the highest connectivity
argument-hint: "[--limit <n>] [--layer <layer>] [--type <type>]"
phase_relevance: ["build", "test", "review"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:hotspots

Identify hotspot symbols ranked by total reference count (incoming + outgoing). Use this to find central coupling points, high-impact refactor targets, and architectural load-bearers.

## Instructions

1. **Search brain for high-connectivity symbols**:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"class function module export","limit":50}}'
   ```
   If brain is unavailable, fall back to Grep/Glob:
   - Use Grep to find class/function definitions across the codebase
   - Use Grep to count import/require references to each symbol
   - Rank by reference count
   Suggest `wicked-brain:ingest` to index the codebase for faster hotspot analysis.

2. **Count references** for discovered symbols using Grep:
   ```
   Grep: <symbol_name> across all source files — count matches
   ```

3. Arguments (all optional):

   | Argument | Default | Description |
   |----------|---------|-------------|
   | `--limit N` | 20 | Number of results to return |
   | `--layer LAYER` | — | Filter to one architectural layer (`backend`, `frontend`, `database`, `view`) |
   | `--type TYPE` | — | Filter to one symbol type (`CLASS`, `FUNCTION`, `METHOD`, `TABLE`, etc.) |

4. Present results as a ranked table:

   | Rank | Symbol | Type | Layer | In | Out | Total |
   |------|--------|------|-------|----|-----|-------|
   | 1 | `UserService` | CLASS | backend | 42 | 18 | 60 |
   | 2 | `db_session` | FUNCTION | database | 38 | 5 | 43 |
   | 3 | `AuthMiddleware` | CLASS | backend | 31 | 11 | 42 |

5. Highlight:
   - The top 3-5 symbols and why they are hotspots (high in-count = shared dependency; high out-count = coordinator/orchestrator)
   - Any layer with a disproportionate share of hotspots (potential coupling concentration)
   - Symbols where `in_count` is very high relative to `out_count` (widely imported utilities)
   - Symbols where `out_count` is very high relative to `in_count` (orchestrators or god objects worth reviewing)

## Example

```
/wicked-garden:search:hotspots
/wicked-garden:search:hotspots --limit 10
/wicked-garden:search:hotspots --layer backend
/wicked-garden:search:hotspots --type CLASS --limit 15
```
