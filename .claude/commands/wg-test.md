---
name: wg-test
description: Execute plugin scenarios as evidence-gated acceptance tests
arguments:
  - name: target
    description: "Plugin name, or plugin/scenario (e.g., wicked-mem or wicked-mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Plugin Scenarios

Thin wrapper around `/wicked-scenarios:acceptance` that adds argument parsing, scenario discovery, and GitHub issue filing. The actual three-agent UAT pipeline (Writer → Executor → Reviewer) is owned by wicked-scenarios.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → List plugins with scenarios, ask user to pick
- `plugin-name` → List scenarios for that plugin, ask user to pick
- `plugin-name/scenario-name` → Run that specific scenario
- `plugin-name --all` → Run all scenarios for that plugin
- `--issues` flag (combinable with any above) → Auto-file GitHub issues for failures

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

### 3. If Listing Needed

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

Use AskUserQuestion to let user select.

### 4. Run Acceptance Tests

Once the specific `plugin_name`, `scenario_name`, and `scenario_file` are resolved, delegate to `/wicked-scenarios:acceptance`:

```
Skill(
  skill="wicked-scenarios:acceptance",
  args="${plugin_name} ${scenario_name} plugins/${plugin_name}/scenarios/${scenario_file}"
)
```

If running `--all` scenarios for a plugin, invoke `/wicked-scenarios:acceptance` once per scenario file (sequentially). Collect all results.

Parse the output to extract:
- Overall verdict (PASS/FAIL/PARTIAL/INCONCLUSIVE)
- Task verdicts and failure analysis
- Specification notes

### 5. File GitHub Issues for Failures

**Trigger**: Any scenario has FAIL verdict (always when `--issues` flag is set; otherwise ask the user).

If there are failures:

1. **Without `--issues` flag**: Use AskUserQuestion — "N scenario(s) failed. File GitHub issues for the failures?"
   - "Yes, file issues for all failures"
   - "Let me pick which ones"
   - "No, just show the results"

2. **With `--issues` flag**: Skip the prompt, file issues for all failures automatically.

#### Filing Issues

For each failure, use `gh issue create` via Bash.

**Title**: `test(<plugin>): <scenario> scenario failure`
**Labels**: `bug`, `<plugin-name>`
**Body template**:

```markdown
## UAT Scenario Failure

**Plugin**: <plugin-name>
**Scenario**: <scenario-name> (`plugins/<plugin-name>/scenarios/<scenario-file>`)
**Run date**: <UTC timestamp>

## Failed Tasks

| # | Task | Assertion | Verdict | Cause |
|---|------|-----------|---------|-------|
| <n> | <description> | <assertion> | FAIL | <cause from reviewer> |

## Evidence Details

<For each failed task, include key evidence excerpts from the reviewer>

## Failure Analysis

<Reviewer's cause attribution and recommendations>

## Suggested Resolution

Run `/wg-issue <this-issue-number>` to start a crew project that resolves this failure.
```

**Grouping**: If multiple scenarios fail for the **same plugin**, combine them into a single issue. Title becomes: `test(<plugin>): <count> scenario failures`.

**Deduplication**: Before filing, check for existing open issues:

```bash
gh issue list --state open --search "test(<plugin-name>):" --json number,title --limit 5
```

If a matching issue exists, skip filing and note the existing issue number instead.

#### Post-Filing Summary

```markdown
## Issues Filed

| # | Plugin | Scenarios | Title |
|---|--------|-----------|-------|
| <number> | <plugin> | <count> | <title> |

Resolve with: `/wg-issue <number>`
```

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

The testing pipeline is owned by `wicked-scenarios:acceptance`, which implements the three-agent pattern (Writer → Executor → Reviewer) with kanban-tracked execution and evidence separation. This command (`/wg-test`) is a dev-tool wrapper that adds:
- Scenario discovery across the monorepo
- Preflight environment checks
- GitHub issue filing for failures

Any plugin or tool can invoke `/wicked-scenarios:acceptance` directly for programmatic acceptance testing without the wg-test wrapper.
