---
name: wg-test
description: Execute plugin scenarios as evidence-gated acceptance tests
arguments:
  - name: target
    description: "Plugin name, or plugin/scenario (e.g., wicked-mem or wicked-mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Plugin Scenarios

Thin wrapper around `/wicked-scenarios:acceptance` that adds monorepo scenario discovery and preflight checks. All testing logic — the three-agent UAT pipeline, issue filing, batch execution — is owned by wicked-scenarios.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → List plugins with scenarios, ask user to pick
- `plugin-name` → List scenarios for that plugin, ask user to pick
- `plugin-name/scenario-name` → Run that specific scenario
- `plugin-name --all` → Run all scenarios for that plugin
- `--issues` flag (combinable with any above) → Pass `--report-auto` to acceptance for automatic issue filing

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

### 4. Delegate to wicked-scenarios

**Single scenario:**

```
Skill(
  skill="wicked-scenarios:acceptance",
  args="${plugin_name} ${scenario_name} plugins/${plugin_name}/scenarios/${scenario_file}${issues_flag ? ' --report-auto' : ''}"
)
```

**All scenarios for a plugin (`--all`):**

Build a batch command with `--next` delimiters between each scenario triplet:

```
Skill(
  skill="wicked-scenarios:acceptance",
  args="${triplet_1} --next ${triplet_2} --next ${triplet_3}${issues_flag ? ' --report-auto' : ' --report'}"
)
```

The `--report` flag triggers `/wicked-scenarios:report` interactively on failures. The `--report-auto` flag (from `--issues`) files issues without prompting.

wicked-scenarios handles everything from here: the three-agent pipeline, batch aggregation, result display, and issue filing.

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
```

## Architecture Note

The testing pipeline is owned by `wicked-scenarios`, which provides:
- `/wicked-scenarios:acceptance` — Three-agent UAT pipeline with batch support
- `/wicked-scenarios:report` — GitHub issue filing with deduplication and grouping

This command (`/wg-test`) is a monorepo dev-tool wrapper that adds only:
- Scenario discovery across `plugins/*/scenarios/`
- Preflight `SKIP_PLUGIN_MARKETPLACE` check
- Flag translation (`--issues` → `--report-auto`)
