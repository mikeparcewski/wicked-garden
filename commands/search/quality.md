---
description: Run quality crew to validate and improve index accuracy to >=95%
argument-hint: "[--max-iterations N]"
---

# /wicked-garden:search:quality

Run the Index Quality Crew - coordinated agents that validate index quality and automatically fill gaps until >=95% accuracy is achieved.

## Architecture

```
Scout Agent → Strategy Agent → Validator Agent → Executor
   (explores)     (plans)        (approves)      (runs)
```

## Arguments

- `--max-iterations` (optional): Maximum iterations before stopping (default: 10)
- `--project` (optional): Project to improve

## Instructions

1. First, check current index quality via the local unified index:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats
   ```

2. Run validation to establish baseline:
   ```
   /wicked-garden:search:validate ${project:+--project "${project}"}
   ```

3. If accuracy < 95%, iterate:

   **Scout phase**: Use Grep/Glob to discover patterns in the codebase that should be indexed:
   - Annotation patterns (`@Service`, `@Entity`, `@Controller`)
   - ORM patterns (`models.Model`, `@Column`)
   - Component files (PascalCase `.tsx`)

   **Strategy phase**: Create extraction plan based on discoveries.

   **Execute phase**: Re-index with the discovered patterns:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py index "<project_path>" --force
   ```

   **Validate phase**: Re-run `/wicked-garden:search:validate` to check improvement.

4. Stop when: >=95% accuracy achieved, OR plateau detected, OR max iterations reached.

## Example

```
/wicked-garden:search:quality
/wicked-garden:search:quality --max-iterations 3
/wicked-garden:search:quality --project my-app
```
