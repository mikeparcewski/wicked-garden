# Schemas

JSON contract schemas used by the observability assertion system (`/wicked-garden:observability:assert`).

## Purpose

These schemas define the expected JSON output shape for key observability scripts. The contract assertion runner (`scripts/observability/assert_contracts.py`) loads each schema, invokes the corresponding script, and validates the output matches the contract.

This catches silent regressions — if a script's output shape changes (missing fields, wrong types, new enum values), the assertion fails before users hit runtime errors.

## Files

| Schema | Validates Output Of | What It Checks |
|--------|---------------------|----------------|
| `assert_contracts.json` | `assert_contracts.py --health-check` | Array of contract results with ts, plugin, script, result (pass/timeout/empty/malformed), violations, duration_ms |
| `health_probe.json` | `health_probe.py --health-check` | Health status (healthy/degraded/unhealthy), violation list with severity, summary counts |
| `plugin_status.json` | `plugin_status.py --health-check` | Plugin metadata (name, version, status), component counts (domains, commands, agents, skills, hooks) |

## Usage

```bash
# Run all contract assertions
/wicked-garden:observability:assert

# Or directly via script
python3 scripts/observability/assert_contracts.py --json
```

## Adding a New Schema

1. Create `schemas/{script-name}.json` with a JSON Schema defining the expected output
2. The assertion runner discovers it automatically and matches it to `scripts/**/{script-name}.py`
