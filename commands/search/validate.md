---
description: Validate index accuracy using consistency checks and optional deep completeness analysis
argument-hint: [--sample-size N] [--format table|json] [--deep]
---

# /wicked-garden:search:validate

Validate the accuracy of wicked-search indexing using consistency-based checks. Adapts validation strategies based on detected language/framework. Reports accuracy with a 95% target.

## Arguments

- `--sample-size` (optional): Number of samples per check (default: 100)
- `--format` (optional): Output format - table, json (default: table)
- `--deep` (optional): Run deep completeness check to discover missing symbols

## Instructions

1. Run the accuracy validator (see `skills/unified-search/refs/script-runner.md` for runner details):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python accuracy_validator.py --db /path/to/graph.db --project /path/to/project --sample-size 100 --format table
   ```

2. For deep completeness checking (slower but finds missing items):
   ```bash
   cd ${CLAUDE_PLUGIN_ROOT}/scripts && uv run python accuracy_validator.py --db /path/to/graph.db --project /path/to/project --deep
   ```

4. Report the validation results:
   - **Overall accuracy**: Combined accuracy across all checks
   - **Per-check breakdown**: Each validation category
   - **Target status**: Whether 95% accuracy is met
   - **Issues found**: Details on failing checks

## Examples

```bash
# Validate with default settings
/wicked-garden:search:validate

# Larger sample for more thorough validation
/wicked-garden:search:validate --sample-size 200

# Deep check to find missing symbols
/wicked-garden:search:validate --deep

# JSON output for CI integration
/wicked-garden:search:validate --format json
```

## Output

```markdown
## Accuracy Validation Report

**Project**: /path/to/project
**Languages**: java, typescript
**Frameworks**: spring

### Summary

- **Overall Accuracy**: 96.2%
- **Target (95%)**: ✓ MET
- **Checks Passed**: 4/4

### Validation Results

| Check | Category | Accuracy | Valid | Invalid | Status |
|-------|----------|----------|-------|---------|--------|
| symbol_existence | existence | 98.0% | 98 | 2 | ✓ |
| reference_targets | reference | 97.0% | 97 | 3 | ✓ |
| lineage_endpoints | traceability | 95.0% | 95 | 5 | ✓ |
| spring_entity_mappings | framework | 94.0% | 94 | 6 | ✗ |
| completeness | completeness | 92.0% | 230 | 20 | ✗ |
```

## Validation Checks

| Check | Category | What it validates |
|-------|----------|-------------------|
| `symbol_existence` | existence | Indexed symbols exist at stated file/line locations |
| `reference_targets` | reference | Reference targets exist in the symbol graph |
| `lineage_endpoints` | traceability | Lineage path endpoints are valid |
| `spring_entity_mappings` | framework | Spring @Column annotations match entity fields |
| `django_model_fields` | framework | Django model fields are properly indexed |
| `completeness` | completeness | Symbols found in source are in the index (--deep) |

## Validation Modes

### Standard Mode (default)
Validates **consistency** - checks that what's in the index is correct:
- Symbol locations are accurate
- References point to valid targets
- Lineage paths have valid endpoints
- Framework patterns match source

### Deep Mode (--deep)
Validates **completeness** - discovers what's potentially missing:
- Samples files from the project
- Uses language-aware patterns to find symbols
- Compares against indexed symbols
- Reports coverage gaps

## Framework Detection

The validator auto-detects frameworks and runs appropriate checks:

| Framework | Detection | Validation |
|-----------|-----------|------------|
| Spring | pom.xml, @Controller | Entity field → column mappings |
| Django | manage.py, models.Model | Model field definitions |
| Rails | Gemfile, ApplicationRecord | ActiveRecord associations |
| Express | package.json, express() | Route handlers |
| FastAPI | FastAPI() | Endpoint definitions |
| NestJS | nest-cli.json | Controller/Injectable patterns |

## Use Cases

- **CI/CD Integration**: Fail builds if accuracy drops below 95%
- **Regression Testing**: Verify indexer changes don't reduce accuracy
- **Quality Assurance**: Validate before production deployment
- **Coverage Analysis**: Use --deep to find gaps in indexing
- **Debugging**: Identify which extraction patterns need improvement

## Exit Codes

- `0`: All checks passed (accuracy ≥ 95%)
- `1`: One or more checks failed (accuracy < 95%)

## Notes

- Requires indexing first with `/wicked-garden:search:index`
- Larger sample sizes give more accurate metrics but take longer
- Some variance is expected due to sampling
- Deep mode is slower but provides completeness insights
- Framework-specific checks only run when framework is detected
