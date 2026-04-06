# Migration Guide: wicked-garden < 4.0 to wicked-search

This guide is for users who previously used the `search` domain inside wicked-garden and are upgrading to wicked-garden 4.0+, where search capabilities are provided by the standalone wicked-search plugin.

## What Changed

In wicked-garden 4.0, the `search` domain was extracted into the standalone `wicked-search` plugin. This removes tree-sitter as a hard dependency from wicked-garden, making the base plugin lighter for users who do not need AST-level code intelligence.

Your existing search indexes are fully compatible — no reindex required.

## Upgrade Steps

1. Update wicked-garden:

```bash
claude plugin update wicked-garden
```

2. Install wicked-search to restore search capabilities:

```bash
claude plugin install wicked-search
```

3. Verify the index is intact:

```bash
/wicked-search:validate
```

If validation reports missing symbols, run a full reindex:

```bash
/wicked-search:index --full
```

## Command Namespace Change

Commands moved from the `wicked-garden:search` namespace to `wicked-search`:

| Before (wicked-garden < 4.0)           | After (wicked-search 1.0+)        |
|----------------------------------------|-----------------------------------|
| `/wicked-garden:search:index`          | `/wicked-search:index`            |
| `/wicked-garden:search:code`           | `/wicked-search:code`             |
| `/wicked-garden:search:docs`           | `/wicked-search:docs`             |
| `/wicked-garden:search:blast-radius`   | `/wicked-search:blast-radius`     |
| `/wicked-garden:search:lineage`        | `/wicked-search:lineage`          |
| `/wicked-garden:search:impact`         | `/wicked-search:impact`           |
| `/wicked-garden:search:service-map`    | `/wicked-search:service-map`      |
| `/wicked-garden:search:hotspots`       | `/wicked-search:hotspots`         |
| `/wicked-garden:search:coverage`       | `/wicked-search:coverage`         |
| `/wicked-garden:search:stats`          | `/wicked-search:stats`            |
| `/wicked-garden:search:validate`       | `/wicked-search:validate`         |
| `/wicked-garden:search:scout`          | `/wicked-search:scout`            |
| `/wicked-garden:search:categories`     | `/wicked-search:categories`       |
| `/wicked-garden:search:refs`           | `/wicked-search:refs`             |
| `/wicked-garden:search:sources`        | `/wicked-search:sources`          |
| `/wicked-garden:search:quality`        | `/wicked-search:quality`          |
| `/wicked-garden:search:impl`           | `/wicked-search:impl`             |

## If You Do Not Install wicked-search

wicked-garden 4.0 without wicked-search falls back to keyword-based search via wicked-brain (if installed) or native file search. You will not have:

- AST-level symbol extraction
- ORM relationship mapping
- Blast-radius and lineage analysis
- Service map generation

All other wicked-garden domains (crew, engineering, qe, mem, jam, kanban, delivery) continue to work without wicked-search.

## Storage Compatibility

Index files are stored at:

```
~/.something-wicked/wicked-garden/local/search/
```

wicked-search 1.0 reads from the same path. No data migration is needed.
