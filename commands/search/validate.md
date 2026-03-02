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

1. Get graph statistics:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph stats ${project:+--project "${project}"}
   ```

2. Sample symbols from the graph:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph list --limit "${sample_size:-100}" ${project:+--project "${project}"}
   ```

3. For each sampled symbol, verify it exists at the stated file:line location:
   - Read the file at the stated path
   - Check that the symbol name appears near the stated line
   - Track valid/invalid counts

4. Sample references and verify targets exist:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cp.py" knowledge graph search --q "<symbol_name>" ${project:+--project "${project}"}
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
