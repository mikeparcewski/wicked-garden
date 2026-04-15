---
description: Store a new memory
argument-hint: "<content>" [--type decision|pattern|preference|gotcha|discovery] [--tier working|episodic|semantic] [--importance low|medium|high] [--tags tag1,tag2]
---

# /wicked-garden:mem:store

Store a memory for persistence across sessions. Thin wrapper over `wicked-brain-memory` — brain owns the taxonomy, tier derivation, and TTL defaults.

## Arguments

Parse the arguments from: $ARGUMENTS

- `content` (required): The memory content to store (first quoted string)
- `--type`: Memory type — `decision`, `pattern` (alias: `procedural`), `preference`, `gotcha`, `discovery`
- `--tier`: Explicit consolidation tier — `working`, `episodic`, `semantic`. If omitted, brain derives from `--importance` and type defaults.
- `--importance`: `low` | `medium` | `high`. Brain maps `high` → `semantic`, `low` → `working`, `medium` → `episodic` when `--tier` is not passed.
- `--tags`: Comma-separated tags for categorization

## Execution

Pass all arguments through to the brain skill unchanged:

```
Skill(skill="wicked-brain-memory", args="store {content} --type {type} --tier {tier} --importance {importance} --tags {tags}")
```

Brain handles type normalization (including `procedural` → `pattern`), importance→tier derivation, per-type TTL defaults, entity enrichment, and FTS indexing.

## Examples

```bash
# Store a decision (brain auto-tiers decisions to semantic)
/wicked-garden:mem:store "Chose PostgreSQL for transaction support" --type decision --tags database,architecture

# Store a debugging outcome as a discovery
/wicked-garden:mem:store "Fixed auth bug: JWT was expiring too early" --type discovery --tags auth,bugfix

# Store a reusable pattern
/wicked-garden:mem:store "Use early returns for validation, then happy path" --type pattern --tags code-style

# Force semantic tier for a high-importance gotcha
/wicked-garden:mem:store "Never call datetime() on ISO-Z strings in SQLite" --type gotcha --importance high
```
