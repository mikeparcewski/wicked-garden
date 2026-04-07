---
description: Validate index accuracy using consistency checks
argument-hint: "[--sample-size N] [--format table|json]"
---

# /wicked-garden:search:validate

Validate the accuracy of the brain index using consistency-based checks.

## Arguments

- `--sample-size` (optional): Number of samples per check (default: 100)
- `--format` (optional): Output format - table, json (default: table)

## Instructions

1. **Check brain stats** to get index summary:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"stats","params":{}}'
   ```
   If brain is unavailable, inform the user and suggest starting it with `wicked-brain:server`.

2. **Sample symbols from the brain** by searching for common patterns:
   ```bash
   curl -s -X POST http://localhost:4242/api \
     -H "Content-Type: application/json" \
     -d '{"action":"search","params":{"query":"function class method","limit":100}}'
   ```

3. **For each sampled symbol**, verify it exists at the stated file:line location:
   - Read the file at the stated path
   - Check that the symbol name appears near the stated line
   - Track valid/invalid counts

4. Report the validation results:

   ```markdown
   ## Accuracy Validation Report

   ### Summary
   - **Overall Accuracy**: {percentage}%
   - **Target (95%)**: MET/NOT MET
   - **Checks Passed**: {n}/{total}
   - **Brain Chunks**: {from stats}
   - **Brain Tags**: {from stats}

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
```
