---
name: wg-test
description: Execute plugin scenarios as user acceptance tests
arguments:
  - name: target
    description: "Plugin name, or plugin/scenario (e.g., wicked-mem or wicked-mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Plugin Scenarios

Execute plugin scenarios to validate functionality. Scenarios run in subagents where **hooks fire naturally** - this is real user acceptance testing.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → List plugins with scenarios, ask user to pick
- `plugin-name` → List scenarios for that plugin, ask user to pick
- `plugin-name/scenario-name` → Run that specific scenario
- `plugin-name --all` → Run all scenarios for that plugin
- `--issues` flag (combinable with any above) → Auto-file GitHub issues for failures via `/wg-issue`

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

### 4. Execute Scenario via Subagent

**CRITICAL**: Spawn a subagent to execute the scenario. Subagents run in interactive mode where hooks fire naturally.

For each scenario to run:

1. Read the scenario file content
2. Spawn a `general-purpose` subagent with this prompt:

```
You are executing a UAT scenario. This is a USER ACCEPTANCE TEST - interact naturally as a user would.

## Rules
1. Use the Skill tool for slash commands (e.g., /wicked-crew:start)
2. Use the Task tool for agent invocations mentioned in the scenario
3. Hooks will fire automatically - you don't need to do anything special
4. After completing all steps, verify the Success Criteria
5. Report PASS or FAIL with details

## Scenario
[INSERT SCENARIO CONTENT HERE]

## Verification
After executing all steps:
1. Check each Success Criterion
2. Verify expected files/state exist
3. Report results in this format:

---RESULTS---
SCENARIO: [name]
STATUS: PASS or FAIL
CRITERIA:
- [criterion]: PASS/FAIL (reason)
- [criterion]: PASS/FAIL (reason)
NOTES: [any observations]
---END---
```

### 5. Collect and Report Results

After subagent completes:
- Parse the RESULTS section
- Report pass/fail status
- If running multiple scenarios, aggregate results

### 6. File GitHub Issues for Failures

**Trigger**: Any scenario has STATUS: FAIL (always when `--issues` flag is set; otherwise ask the user).

If there are failures:

1. **Without `--issues` flag**: Use AskUserQuestion — "N scenario(s) failed. File GitHub issues for the failures?"
   - "Yes, file issues for all failures"
   - "Let me pick which ones"
   - "No, just show the results"

2. **With `--issues` flag**: Skip the prompt, file issues for all failures automatically.

#### Filing Issues

For each failure (or selected failures), use `gh issue create` via Bash. Construct the title, labels, and body from the test results — the template below shows the structure (substitute actual values):

**Title**: `test(<plugin>): <scenario> scenario failure`
**Labels**: `bug`, `<plugin-name>`
**Body template**:

```markdown
## UAT Scenario Failure

**Plugin**: <plugin-name>
**Scenario**: <scenario-name> (`plugins/<plugin-name>/scenarios/<scenario-file>`)
**Run date**: <UTC timestamp>

## Failed Criteria

- <criterion>: FAIL — <reason>
- <criterion>: FAIL — <reason>

## Evidence

<failure evidence and notes from test runner>

## Scenario Description

<description from scenario frontmatter>

## Suggested Resolution

Run `/wg-issue <this-issue-number>` to start a crew project that resolves this failure.
```

**Two-step filing**: Use `gh issue create` with `--json number` to capture the issue number, then update the body's "Suggested Resolution" section with the actual number via `gh issue edit`.

**Grouping**: If multiple scenarios fail for the **same plugin**, combine them into a single issue rather than one per scenario. Title becomes: `test(<plugin>): <count> scenario failures` and the body lists all failed scenarios with their criteria.

**Deduplication**: Before filing, check for existing open issues with a matching title prefix:

```bash
gh issue list --state open --search "test(<plugin-name>):" --json number,title --limit 5
```

If a matching issue exists, skip filing and note the existing issue number instead.

#### Post-Filing Summary

After filing, display:

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

# Run a specific scenario and file an issue if it fails
/wg-test wicked-patch/01-add-field-propagation --issues
```

## Why Subagents?

Subagents run in **interactive mode** where:
- SessionStart hooks fire on agent start
- PostToolUse hooks fire after each tool
- PreToolUse hooks fire before each tool
- All plugin integration works naturally

This is TRUE user acceptance testing - the subagent experiences exactly what a user would.
