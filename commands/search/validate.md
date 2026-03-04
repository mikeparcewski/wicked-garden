---
description: Validate index accuracy using consistency checks
argument-hint: "[--sample-size N] [--format table|json]"
---

# /wicked-garden:search:validate

Validate the accuracy of the knowledge graph index using consistency-based checks.

## Arguments

- `--sample-size` (optional): Number of samples per check (default: 100)
- `--format` (optional): Output format - table, json (default: table)
- `--project` (optional): Project to validate

## Instructions

1. Run validation via the local unified index (primary):
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py validate
   ```

2. Get detailed statistics:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py stats
   ```

3. For each sampled symbol, verify it exists at the stated file:line location:
   - Read the file at the stated path
   - Check that the symbol name appears near the stated line
   - Track valid/invalid counts

4. Check FTS5 index integrity:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/search/unified_search.py integrity-check
   ```

5. Report the validation results:

   ```markdown
   ## Accuracy Validation Report

   ### Summary
   - **Overall Accuracy**: {percentage}%
   - **Target (95%)**: MET/NOT MET
   - **Checks Passed**: {n}/{total}

   ### Validation Results

   | Check | Accuracy | Valid | Invalid | Status |
   |-------|----------|-------|---------|--------|
   | symbol_existence | 98.0% | 98 | 2 | pass |
   | reference_targets | 97.0% | 97 | 3 | pass |
   ```

## Exit Codes

- `0`: All checks passed (accuracy >= 95%)
- `1`: One or more checks failed (accuracy < 95%)

## Example

```
/wicked-garden:search:validate
/wicked-garden:search:validate --sample-size 200
/wicked-garden:search:validate --project my-app
```
