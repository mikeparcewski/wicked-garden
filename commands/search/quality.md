---
description: Run quality crew to validate and improve index accuracy to ≥95%
argument-hint: [--max-iterations N]
---

# /wicked-garden:search:quality

Run the Index Quality Crew - coordinated agents that validate index quality and automatically fill gaps until ≥95% accuracy is achieved.

## Architecture

```
Scout Agent → Strategy Agent → Validator Agent → Executor
   (explores)     (plans)        (approves)      (runs)
```

- **Scout**: Explores codebase to discover actual structure and patterns
- **Strategy**: Creates extraction plans based on discoveries
- **Validator**: Reviews plans to prevent plateaus and loops
- **Executor**: Generates and runs extraction scripts

## Arguments

- `--max-iterations` (optional): Maximum iterations before stopping (default: 10)

## Instructions

1. First, create an initial index (can be empty or partial):
   ```bash
   /wicked-garden:search:index /path/to/project
   ```

2. Run the quality crew (see `skills/unified-search/references/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python index_quality_crew.py --db /path/to/graph.db --project /path/to/project
   ```

3. The crew will iterate until:
   - ≥95% accuracy achieved, OR
   - Plateau detected (no progress possible), OR
   - Max iterations reached

## Example Output

```
=== Index Quality Crew ===
Project: /path/to/project
Target: ≥95%

--- Iteration 1 ---
Current: 0.0% (0 symbols)
Scouting...
  Found: services/annotation_based (90%)
  Found: database/orm_annotations (90%)
  Found: objects/java_classes (95%)
Planning...
  Plan: 5 scripts, ~350 symbols
  Plan approved
Executing...
  Added 139129 symbols

--- Iteration 2 ---
Current: 99.0% (138122 symbols)

✓ Quality threshold met!

=== Final Report ===
Status: PASSED
Iterations: 2
Overall accuracy: 99.0%
Total symbols: 138122

Category accuracies:
  services: 100.0%
  database: 96.0%
  ui: 100.0%
  objects: 100.0%
```

## Discovery Types

The Scout Agent discovers patterns by:

| Method | Confidence | Example |
|--------|------------|---------|
| Annotation-based | 90% | `@Service`, `@Entity`, `@Controller` |
| ORM patterns | 90% | `models.Model`, `@Column` |
| Directory conventions | 70% | `*/service/*`, `*/entity/*` |
| Component files | 80% | PascalCase `.tsx` files |
| Language classes | 95% | Standard class/function patterns |

## Categories Tracked

- **services**: Controllers, endpoints, handlers, routes
- **database**: Entities, models, fields, repositories
- **ui**: Components, hooks, views
- **objects**: Classes, interfaces, functions, types

## Scripts Location

Generated extraction scripts are cached under the search storage root:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-search tmp_scripts
```

## Exit Codes

- `0`: Quality threshold met (≥95%)
- `1`: Quality not met or error

## Plateau Detection

The Validator Agent prevents infinite loops by:
- Tracking plan hashes across iterations
- Rejecting repeated plans
- Detecting accuracy plateaus (no change in 2+ iterations)

## Use Cases

- **New project**: Start from empty index, crew discovers everything
- **Partial index**: Crew identifies and fills gaps
- **Quality gate**: CI/CD check that index meets 95% threshold
- **Debugging**: See which categories need improvement
