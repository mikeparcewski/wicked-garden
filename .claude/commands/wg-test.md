---
name: wg-test
description: Execute acceptance test scenarios for the wicked-garden plugin
arguments:
  - name: target
    description: "Domain name, or domain/scenario (e.g., mem or mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Scenarios

Dev-tool wrapper that delegates to the best available testing pipeline. QE owns acceptance testing end-to-end; the scenarios domain provides standalone execution as a fallback.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → List domains with scenarios, ask user to pick
- `domain-name` → List scenarios for that domain, ask user to pick
- `domain/scenario-name` → Run that specific scenario
- `domain --all` → Run all scenarios for that domain
- `--all` → Run all scenarios across all domains
- `--issues` flag (combinable with any above) → Auto-file GitHub issues for failures
- `--batch N` → Run scenarios in batches of N in parallel (default: sequential)
- `--debug` → Write debug log capturing tool-usage traces per batch

### 2. Preflight Environment Check

Before running any scenarios, verify the plugin runtime is available:

```bash
if [ "${SKIP_PLUGIN_MARKETPLACE}" = "true" ]; then
  echo "SKIP_PLUGIN_MARKETPLACE=true is set — plugin skills will not be registered."
  echo "Scenarios WILL FAIL because slash commands like /wicked-garden:mem:store cannot resolve."
  echo "Remove this env var or set SKIP_PLUGIN_MARKETPLACE=false to enable plugin loading."
fi
```

If the variable is set, warn the user and ask whether to continue (results will be unreliable) or abort. Use AskUserQuestion with options: "Abort — fix environment first" and "Continue anyway (expect failures)".

### 3. Scenario Discovery

If the user didn't specify a full `domain/scenario` path, discover available scenarios:

```bash
# Find domains with scenarios
for domain_dir in scenarios/*/; do
  if [ -d "${domain_dir}" ]; then
    domain_name=$(basename "$domain_dir")
    scenario_count=$(find "${domain_dir}" -name "*.md" ! -name "README.md" | wc -l | tr -d ' ')
    if [ "$scenario_count" -gt 0 ]; then
      echo "$domain_name: $scenario_count scenarios"
    fi
  fi
done
```

Use AskUserQuestion to let user select domain and/or scenario.

### 4. Detect Available Pipeline

Check which testing capabilities are available in the unified plugin:

```bash
# Check for QE domain (primary pipeline)
ls commands/qe/acceptance.md 2>/dev/null && echo "QE_AVAILABLE=true"

# Check for scenarios domain (execution backend / fallback)
ls commands/scenarios/run.md 2>/dev/null && echo "SCENARIOS_AVAILABLE=true"
```

### 5. Delegate to Pipeline

**Primary path — QE available:**

Delegate to `/wicked-garden:qe:acceptance` which owns the full Writer → Executor → Reviewer pipeline. The QE executor automatically delegates E2E CLI steps to `/wicked-garden:scenarios:run --json` when scenarios are available.

**Single scenario:**
```
Skill(
  skill="wicked-garden:qe:acceptance",
  args="scenarios/${domain}/${scenario_file}"
)
```

**All scenarios for a domain (`--all`):**
```
Skill(
  skill="wicked-garden:qe:acceptance",
  args="scenarios/${domain}/ --all"
)
```

**Fallback path — QE not available, scenarios available:**

Delegate directly to `/wicked-garden:scenarios:run` for standalone execution (exit code PASS/FAIL, no evidence protocol, no independent review):

**Single scenario:**
```
Skill(
  skill="wicked-garden:scenarios:run",
  args="scenarios/${domain}/${scenario_file}"
)
```

**All scenarios (`--all`):**

Run each scenario file sequentially. Note: the glob already yields the full relative path — do NOT re-prefix it:
```
for each scenario_file in scenarios/${domain}/*.md (excluding README.md):
  Skill(
    skill="wicked-garden:scenarios:run",
    args="${scenario_file}"
  )
```

**Neither available:**

Report an error:
```
Error: No testing pipeline available.
The qe and scenarios domains must be present to enable testing.
  - qe: Full acceptance pipeline with evidence protocol and independent review
  - scenarios: Standalone E2E execution with PASS/FAIL verdicts
```

### 5.5 Batch Execution (if --batch)

When `--batch N` is specified with `--all`:

1. Discover all scenario files for the target domain (or all domains)
2. Split into batches of N scenarios each
3. For each batch:
   a. Dispatch N parallel Task() calls, each running the scenario via the detected pipeline
   b. Collect results from all N tasks
   c. Write batch debug log to `~/.something-wicked/wicked-garden/batch-runs/{run-id}/batch-{n}.md`
4. After all batches complete, produce a run summary

**Batch dispatch (QE path):**
```
# Launch up to N scenarios in parallel
for each scenario in current_batch:
  Task(
    subagent_type="wicked-garden:qe:acceptance-test-executor",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

**Batch dispatch (scenarios-only fallback):**
```
for each scenario in current_batch:
  Task(
    subagent_type="wicked-garden:scenarios:scenario-runner",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

**Debug log per batch** (if --debug):
Each batch debug log captures:
- Scenario names and paths
- Pass/fail/skip per scenario
- Duration per scenario
- Which tools/skills/commands were invoked (from Task output)
- Any silent failures detected

**Run summary** written to `~/.something-wicked/wicked-garden/batch-runs/{run-id}/summary.json`:
```json
{
  "run_id": "unique-id",
  "total": 102,
  "passed": 95,
  "failed": 5,
  "errors": 2,
  "skipped": 0,
  "duration_ms": 180000,
  "batches": 13,
  "batch_size": 8,
  "failed_scenarios": ["domain/scenario-name", ...]
}
```

### 6. Issue Filing (if --issues)

After testing completes with failures:

**QE path (primary):** QE acceptance produces structured verdicts (`task_verdicts`, `acceptance_criteria_verdicts`, `failure_analysis`). Invoke report:
```
Skill(
  skill="wicked-garden:scenarios:report",
  args="--auto"
)
```

**Scenarios-only fallback path:** `/wicked-garden:scenarios:run` produces simple exit codes (0/1/2) and markdown output, NOT structured verdicts. The `report` command requires structured fields, so issue filing is **not available** in this degradation path. Instead, display:
```
Failures detected (exit code 1). Automatic issue filing requires the qe domain
for structured test verdicts. File manually: gh issue create --title "test(<domain>): ..." --label bug
```

**Neither available:** No testing occurred, no issue filing.

## Examples

```bash
# List domains with scenarios
/wg-test

# List scenarios for mem domain
/wg-test mem

# Run specific scenario
/wg-test mem/decision-recall

# Run all crew scenarios
/wg-test crew --all

# Run all scenarios and auto-file issues for failures
/wg-test crew --all --issues

# Run all scenarios in batches of 8 with debug logging
/wg-test crew --all --batch 8

# Run all scenarios across all domains in parallel batches
/wg-test --all --batch 8 --debug
```

## Architecture Note

This command (`/wg-test`) is a dev-tool wrapper that adds only:
- Scenario discovery across `scenarios/{domain}/`
- Preflight `SKIP_PLUGIN_MARKETPLACE` check
- Pipeline detection and degradation fallback

Testing intelligence is owned by:
- **qe domain** — acceptance pipeline (Writer/Executor/Reviewer), evidence protocol, assertions
- **scenarios domain** — E2E CLI execution (`/wicked-garden:scenarios:run`), issue filing (`/wicked-garden:scenarios:report`)
