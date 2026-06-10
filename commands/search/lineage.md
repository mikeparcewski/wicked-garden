---
description: Trace data lineage / dependency flow (downstream dependencies or upstream dependents)
argument-hint: "<symbol> [--direction upstream|downstream|both] [--depth N]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:search:lineage

Trace flow through the code-relationship graph — **delegates to wicked-brain's
`wicked-brain:graph`** (ADR 0004). Downstream = what the symbol depends on; upstream
= what depends on it. Includes injected edges (bus/dispatch/capability/archetype)
that grep and a static call-graph can't see.

> **Scope**: `lineage` answers "where does this flow from / to?". For pure
> "what breaks if I change X?" use `/wicked-garden:search:blast-radius`.

## Arguments
- `symbol` (required): the symbol/file to trace from (`file:<relpath>` or a resolved node id).
- `--direction` (optional, default downstream): `downstream` (dependencies), `upstream` (dependents), or `both`.
- `--depth` (optional): traversal depth (brain default applies if omitted).

## Instructions

1. **Ensure the graph is fresh**: `npx -y wicked-brain-call graph-index` (builds codegraph + runs the injected-edge extractors; reports `staleness`).

2. **Resolve the symbol to a node id** (`file:<relpath>` directly, or via `npx -y wicked-brain-call symbols --query "<symbol>"`).

3. **Trace** via brain:
   - **downstream** (what it depends on): `npx -y wicked-brain-call graph-lineage --node "<id>"` → `dependencies`.
   - **upstream** (what depends on it): `npx -y wicked-brain-call graph-blast-radius --node "<id>"` → `dependents`.
   - **both**: run both and present each direction.
   Each result includes injected edges (e.g. a consumer reached via `injected:bus`, an archetype via `injected:archetype`) and a `staleness` stamp.

4. **Fallbacks**: `engine:"unavailable"` → install codegraph where brain runs. Brain unreachable → `wicked-brain:search` + Grep for literal flow only (flag that injected/string-keyed links will be MISSING).

5. Report each path (source → sink), file locations per step, provenance of injected hops, and gaps.

## Examples
```bash
/wicked-garden:search:lineage file:scripts/_bus.py --direction upstream
/wicked-garden:search:lineage User.email --direction both
```

## Notes
- The graph + queries live in **wicked-brain** now; this command is a thin wrapper over `wicked-brain:graph`.
- Use `/wicked-garden:search:blast-radius` for the dedicated "impact of changing X" view.
