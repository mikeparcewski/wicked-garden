# Schemas

JSON contract schemas used by the observability assertion system (`/wicked-garden:platform:assert`).

## Purpose

These schemas define the expected JSON output shape for key observability scripts. The contract assertion runner (`scripts/platform/observability/assert_contracts.py`) loads each schema, invokes the corresponding script, and validates the output matches the contract.

This catches silent regressions — if a script's output shape changes (missing fields, wrong types, new enum values), the assertion fails before users hit runtime errors.

## Files

| Schema | Validates Output Of | What It Checks |
|--------|---------------------|----------------|
| `assert_contracts.json` | `assert_contracts.py --health-check` | Array of contract results with ts, plugin, script, result (pass/timeout/empty/malformed), violations, duration_ms |
| `health_probe.json` | `health_probe.py --health-check` | Health status (healthy/degraded/unhealthy), violation list with severity, summary counts |
| `plugin_status.json` | `plugin_status.py --health-check` | Plugin metadata (name, version, status), component counts (domains, commands, agents, skills, hooks) |

## Standalone contract schemas (`*.schema.json`)

Not observability output contracts — these are versioned data-format contracts
that other tooling validates against directly (the assertion runner finds no
matching script for them and reports a script-missing row; that mismatch is
cosmetic and pre-dates them):

| Schema | Format it defines | Version field | Validated by |
|--------|-------------------|---------------|--------------|
| `wicked-pack.schema.json` | Third-party skill-pack manifest (`wicked-pack.json`) | `spec` (currently 1) | `npx wicked-garden pack check <dir>` (`scripts/pack/check.py`) |
| `campaign-recon.schema.json` | qe campaign recon + plan artifact (capability inventory, environment-manifest ref, dependency-ordered scenario ladder with pass criteria and claim ceilings — ADR 0006) | `spec` (currently 1) | `tests/qe/test_campaign_recon_schema.py` (fixture round-trip + nonconforming rejection). The sibling evidence contract (`scenario_evidence` + `claim_level`) is owned by wicked-ledger (manifest 2.1). |

## Usage

```bash
# Run all contract assertions
/wicked-garden:platform:assert

# Or directly via script
python3 scripts/platform/observability/assert_contracts.py --json
```

## Adding a New Schema

1. Create `schemas/{script-name}.json` with a JSON Schema defining the expected output
2. The assertion runner discovers it automatically and matches it to `scripts/**/{script-name}.py`
