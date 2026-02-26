---
name: wg-test
description: Execute plugin scenarios as evidence-gated acceptance tests
arguments:
  - name: target
    description: "Plugin name, or plugin/scenario (e.g., wicked-mem or wicked-mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Plugin Scenarios

Thin monorepo wrapper that delegates to the best available testing pipeline. QE owns acceptance testing end-to-end; wicked-scenarios provides standalone execution as a fallback.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → List plugins with scenarios, ask user to pick
- `plugin-name` → List scenarios for that plugin, ask user to pick
- `plugin-name/scenario-name` → Run that specific scenario
- `plugin-name --all` → Run all scenarios for that plugin
- `--issues` flag (combinable with any above) → Auto-file GitHub issues for failures
- `--batch N` → Run scenarios in batches of N in parallel (default: sequential)
- `--debug` → Write debug log capturing tool-usage traces per batch

### 2. Preflight Environment Check

Before running any scenarios, verify the plugin runtime is available:

```bash
if [ "${SKIP_PLUGIN_MARKETPLACE}" = "true" ]; then
  echo "SKIP_PLUGIN_MARKETPLACE=true is set — plugin skills will not be registered."
  echo "Plugin scenarios WILL FAIL because slash commands like /wicked-mem:store cannot resolve."
  echo "Remove this env var or set SKIP_PLUGIN_MARKETPLACE=false to enable plugin loading."
fi
```

If the variable is set, warn the user and ask whether to continue (results will be unreliable) or abort. Use AskUserQuestion with options: "Abort — fix environment first" and "Continue anyway (expect failures)".

### 3. Scenario Discovery

If the user didn't specify a full `plugin/scenario` path, discover available scenarios in this monorepo:

```bash
# Find plugins with scenarios
for plugin_dir in plugins/*/; do
  if [ -d "${plugin_dir}scenarios" ]; then
    plugin_name=$(basename "$plugin_dir")
    scenario_count=$(find "${plugin_dir}scenarios" -name "*.md" ! -name "README.md" | wc -l | tr -d ' ')
    if [ "$scenario_count" -gt 0 ]; then
      echo "$plugin_name: $scenario_count scenarios"
    fi
  fi
done
```

Use AskUserQuestion to let user select plugin and/or scenario.

### 4. Detect Available Pipeline

Check which testing plugins are installed:

```bash
# Check for QE (primary pipeline)
ls plugins/wicked-qe/.claude-plugin/plugin.json 2>/dev/null && echo "QE_AVAILABLE=true"

# Check for scenarios (execution backend / fallback)
ls plugins/wicked-scenarios/.claude-plugin/plugin.json 2>/dev/null && echo "SCENARIOS_AVAILABLE=true"
```

### 5. Delegate to Pipeline

**Primary path — QE installed:**

Delegate to `/wicked-qe:acceptance` which owns the full Writer → Executor → Reviewer pipeline. The QE executor automatically delegates E2E CLI steps to `/wicked-scenarios:run --json` when scenarios is available.

**Single scenario:**
```
Skill(
  skill="wicked-qe:acceptance",
  args="plugins/${plugin_name}/scenarios/${scenario_file}"
)
```

**All scenarios (`--all`):**
```
Skill(
  skill="wicked-qe:acceptance",
  args="plugins/${plugin_name}/scenarios/ --all"
)
```

**Fallback path — QE not installed, scenarios installed:**

Delegate directly to `/wicked-scenarios:run` for standalone execution (exit code PASS/FAIL, no evidence protocol, no independent review):

**Single scenario:**
```
Skill(
  skill="wicked-scenarios:run",
  args="plugins/${plugin_name}/scenarios/${scenario_file}"
)
```

**All scenarios (`--all`):**

Run each scenario file sequentially. Note: the glob already yields the full relative path — do NOT re-prefix it:
```
for each scenario_file in plugins/${plugin_name}/scenarios/*.md (excluding README.md):
  Skill(
    skill="wicked-scenarios:run",
    args="${scenario_file}"
  )
```

**Neither installed:**

Report an error:
```
Error: No testing pipeline available.
Install wicked-qe (recommended) or wicked-scenarios to enable testing.
  - wicked-qe: Full acceptance pipeline with evidence protocol and independent review
  - wicked-scenarios: Standalone E2E execution with PASS/FAIL verdicts
```

### 5.5 Batch Execution (if --batch)

When `--batch N` is specified with `--all`:

1. Discover all scenario files for the target plugin
2. Split into batches of N scenarios each
3. For each batch:
   a. Dispatch N parallel Task() calls, each running the scenario via the detected pipeline
   b. Collect results from all N tasks
   c. Write batch debug log to `~/.something-wicked/wicked-observability/batch-runs/{run-id}/batch-{n}.md`
4. After all batches complete, produce a run summary

**Batch dispatch (QE path):**
```
# Launch up to N scenarios in parallel
for each scenario in current_batch:
  Task(
    subagent_type="wicked-qe:acceptance-test-executor",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

**Batch dispatch (scenarios-only fallback):**
```
for each scenario in current_batch:
  Task(
    subagent_type="wicked-scenarios:scenario-runner",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

**Debug log per batch** (if --debug or always when wicked-observability is installed):
Each batch debug log captures:
- Scenario names and paths
- Pass/fail/skip per scenario
- Duration per scenario
- Which tools/skills/commands were invoked (from Task output)
- Any silent failures detected (if wicked-observability traces available)

**Run summary** written to `~/.something-wicked/wicked-observability/batch-runs/{run-id}/summary.json`:
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
  "failed_scenarios": ["plugin/scenario-name", ...]
}
```

### 6. Issue Filing (if --issues)

After testing completes with failures:

**QE path (primary):** QE acceptance produces structured verdicts (`task_verdicts`, `acceptance_criteria_verdicts`, `failure_analysis`). If wicked-scenarios is also installed, invoke report:
```
Skill(
  skill="wicked-scenarios:report",
  args="--auto"
)
```

**Scenarios-only fallback path:** `/wicked-scenarios:run` produces simple exit codes (0/1/2) and markdown output, NOT structured verdicts. The `report` command requires structured fields, so issue filing is **not available** in this degradation path. Instead, display:
```
Failures detected (exit code 1). Automatic issue filing requires wicked-qe
for structured test verdicts. File manually: gh issue create --title "test(<plugin>): ..." --label bug
```

**Neither installed:** No testing occurred, no issue filing.

## Examples

```bash
# List plugins with scenarios
/wg-test

# List scenarios for wicked-mem
/wg-test wicked-mem

# Run specific scenario
/wg-test wicked-mem/decision-recall

# Run all wicked-crew scenarios
/wg-test wicked-crew --all

# Run all scenarios and auto-file issues for failures
/wg-test wicked-crew --all --issues

# Run all scenarios in batches of 8 with debug logging
/wg-test wicked-crew --all --batch 8

# Run all scenarios for all plugins in parallel batches
/wg-test --all --batch 8 --debug
```

## Architecture Note

This command (`/wg-test`) is a monorepo dev-tool wrapper that adds only:
- Scenario discovery across `plugins/*/scenarios/`
- Preflight `SKIP_PLUGIN_MARKETPLACE` check
- Pipeline detection and degradation fallback

Testing intelligence is owned by:
- **wicked-qe** — acceptance pipeline (Writer/Executor/Reviewer), evidence protocol, assertions
- **wicked-scenarios** — E2E CLI execution (`/wicked-scenarios:run`), issue filing (`/wicked-scenarios:report`)
