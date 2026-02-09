---
name: wg-test
description: Execute plugin scenarios as user acceptance tests
arguments:
  - name: target
    description: "Plugin name, or plugin/scenario (e.g., wicked-mem or wicked-mem/decision-recall)"
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

### 2. If Listing Needed

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

### 3. Execute Scenario via Subagent

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

### 4. Collect and Report Results

After subagent completes:
- Parse the RESULTS section
- Report pass/fail status
- If running multiple scenarios, aggregate results

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
```

## Why Subagents?

Subagents run in **interactive mode** where:
- SessionStart hooks fire on agent start
- PostToolUse hooks fire after each tool
- PreToolUse hooks fire before each tool
- All plugin integration works naturally

This is TRUE user acceptance testing - the subagent experiences exactly what a user would.
