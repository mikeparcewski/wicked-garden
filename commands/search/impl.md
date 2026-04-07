---
description: Find code that implements a documented feature/section
argument-hint: "<doc-section>"
---

# /wicked-garden:search:impl

Find code that implements a documented feature or section by searching the brain knowledge layer.

## Arguments

- `doc-section` (required): Name of the doc section to find implementations for

## Instructions

1. **Search brain for the documented feature**:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"<doc-section>","limit":20}}'
   ```
   If brain is unavailable or returns no results, fall back to Grep:
   ```
   Grep: <doc-section> across all source files (*.py, *.js, *.ts, *.java, *.go, *.rb, *.rs)
   ```
   Suggest `wicked-brain:ingest` to index the codebase for richer implementation mapping.

2. **Filter results** to code files (not docs) that reference or implement the feature.

3. **Use Grep to verify** implementations by searching for class/function definitions in the matched files.

4. Report the code symbols that implement this section, with file locations.

## Example

```
/wicked-garden:search:impl "Repository Layer"
/wicked-garden:search:impl "Security Requirements"
```

## Notes

- Brain search finds both code and doc chunks; filter to code for implementation mapping
- Cross-references are detected during brain ingestion
