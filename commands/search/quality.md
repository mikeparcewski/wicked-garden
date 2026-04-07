---
description: Run quality crew to validate and improve index accuracy to >=95%
argument-hint: "[--max-iterations N]"
---

# /wicked-garden:search:quality

Run the Index Quality Crew - coordinated agents that validate brain index quality and automatically fill gaps until >=95% accuracy is achieved.

## Architecture

```
Scout Agent → Strategy Agent → Validator Agent → Executor
   (explores)     (plans)        (approves)      (runs)
```

## Arguments

- `--max-iterations` (optional): Maximum iterations before stopping (default: 10)

## Instructions

1. **Check current brain health and stats**:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"stats","params":{}}'
   ```
   If brain is unavailable, inform the user and suggest starting it with `wicked-brain:server`.

2. **Run validation** to establish baseline:
   ```
   /wicked-garden:search:validate
   ```

3. If accuracy < 95%, iterate:

   **Scout phase**: Use Grep/Glob to discover patterns in the codebase that should be indexed:
   - Annotation patterns (`@Service`, `@Entity`, `@Controller`)
   - ORM patterns (`models.Model`, `@Column`)
   - Component files (PascalCase `.tsx`)

   **Strategy phase**: Create extraction plan based on discoveries.

   **Execute phase**: Re-ingest with the discovered content via `wicked-brain:ingest`.

   **Validate phase**: Re-run `/wicked-garden:search:validate` to check improvement.

4. Stop when: >=95% accuracy achieved, OR plateau detected, OR max iterations reached.

## Example

```
/wicked-garden:search:quality
/wicked-garden:search:quality --max-iterations 3
```
