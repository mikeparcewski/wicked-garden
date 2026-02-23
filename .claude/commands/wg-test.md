---
name: wg-test
description: Execute plugin scenarios as evidence-gated acceptance tests
arguments:
  - name: target
    description: "Plugin name, or plugin/scenario (e.g., wicked-mem or wicked-mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Plugin Scenarios

Execute plugin scenarios as evidence-gated acceptance tests using the three-agent architecture: **Writer** (converter) designs evidence requirements, **Executor** (runner) captures artifacts, **Reviewer** evaluates evidence independently.

Each scenario is decomposed into individual tasks tracked on a kanban board. Execution and grading are separated to eliminate false positives from self-grading.

## Architecture

```
Scenario ──→ [Converter/Writer] ──→ Kanban Tasks ──→ [Runner/Executor] ──→ Evidence ──→ [Reviewer] ──→ Verdict
                  │                    (per task)          │                    │
             reads impl code      evidence requirements    no judgment      independent evaluation
             flags spec bugs      + assertions per task    captures artifacts  cites evidence
```

**Why three roles?**

- **Converter/Writer** catches specification bugs before execution begins
- **Runner/Executor** can't "imagine" success — must produce artifacts
- **Reviewer** can't be biased by watching execution — evaluates cold evidence

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

### 4. Convert Scenario to Kanban Tasks (Writer Phase)

Read the scenario file, then spawn the `wicked-scenarios:scenario-converter` agent to decompose it into evidence-gated test tasks on a kanban board.

```
Task(
  subagent_type="wicked-scenarios:scenario-converter",
  prompt="Convert this scenario into kanban-tracked, evidence-gated test tasks.

PLUGIN: ${plugin_name}
SCENARIO: ${scenario_name}
SCENARIO_FILE: plugins/${plugin_name}/scenarios/${scenario_file}

[INSERT FULL SCENARIO CONTENT HERE]"
)
```

The converter (serving the Writer role):
1. Reads the scenario AND the implementation code
2. Creates a kanban project: `UAT: ${plugin_name}/${scenario_name}`
3. Creates one task per scenario step with evidence requirements and assertions
4. Sets dependencies between tasks
5. Flags any specification mismatches found
6. Returns a JSON response with the project structure

**Parse the converter output** to extract:
- `project_id`: The kanban project ID
- `specification_notes`: Any mismatches between scenario and implementation
- `swimlanes`: Map of swimlane names to IDs (To Do, In Progress, Done)
- `tasks`: Array of task objects with `{kanban_task_id, id, type, action, evidence, assertions, depends_on, timeout}`
- `acceptance_criteria_map`: How scenario criteria map to assertions
- `evidence_manifest`: Registry of all evidence IDs

**Display specification notes** if any were found — these are bugs caught before execution:

```markdown
### Specification Notes (from Writer)
- **NOTE-1**: {description} — Impact: {impact}
```

### 5. Execute Tasks Sequentially (Executor Phase)

For each task from the converter output (in order, respecting `depends_on`):

1. **Check dependencies** — if any dependency task errored, mark this task as `skipped` by adding a comment and moving to Done:
   ```bash
   cd plugins/wicked-kanban && uv run python scripts/kanban.py add-comment ${project_id} ${kanban_task_id} "SKIPPED: Dependency ${dep_id} could not execute"
   cd plugins/wicked-kanban && uv run python scripts/kanban.py add-artifact ${project_id} ${kanban_task_id} "L3:test:skipped" --type document --path "n/a"
   cd plugins/wicked-kanban && uv run python scripts/kanban.py update-task ${project_id} ${kanban_task_id} --swimlane ${done_swimlane_id}
   ```

2. **Move to In Progress**:
   ```bash
   cd plugins/wicked-kanban && uv run python scripts/kanban.py update-task ${project_id} ${kanban_task_id} --swimlane ${in_progress_swimlane_id}
   ```

3. **Spawn executor subagent** for the task:
   ```
   Task(
     subagent_type="wicked-scenarios:scenario-executor",
     prompt="Execute this test task and capture evidence. Do NOT judge pass/fail.

   PROJECT_ID: ${project_id}
   KANBAN_TASK_ID: ${kanban_task_id}
   DONE_SWIMLANE_ID: ${done_swimlane_id}
   PLUGIN: ${plugin_name}

   TASK:
   ${task_json}

   Execute the action described in the task. Capture ALL required evidence.
   Record evidence as a kanban artifact. Do NOT evaluate assertions — just capture.
   Do NOT read the full scenario."
   )
   ```

4. **Check execution status** — after executor completes, note whether it reported EXECUTED, SKIPPED, or ERROR.

**IMPORTANT**: Each executor gets only its own task — NOT the full scenario. This prevents token overflow.

### 6. Independent Review (Reviewer Phase)

After all tasks execute, collect evidence and spawn an independent reviewer.

**a) Gather all evidence files:**

```bash
evidence_dir="${HOME}/.something-wicked/wg-test/evidence/${project_id}"
ls "${evidence_dir}"/*.json 2>/dev/null
```

Read each evidence JSON file to compile the full evidence report.

**b) Spawn the reviewer:**

If wicked-qe is installed (check `ls plugins/wicked-qe/.claude-plugin/plugin.json 2>/dev/null`):

```
Task(
  subagent_type="wicked-qe:acceptance-test-reviewer",
  prompt="""Review this evidence against the test plan assertions.

## Scenario
${scenario_name} (${scenario_file})

## Specification Notes
${specification_notes from converter}

## Acceptance Criteria Map
${acceptance_criteria_map from converter}

## Evidence Report
For each task, the executor captured the following evidence:

### ${task_id}: ${task_description}
${evidence JSON content for this task}
[Repeat for all tasks]

## Instructions
1. Verify evidence completeness — is every required artifact present?
2. Evaluate each assertion against its evidence using the specified operator
3. Check specification notes from the writer
4. Render task-level verdicts (PASS, FAIL, INCONCLUSIVE, SKIPPED)
5. Map results to original acceptance criteria
6. Produce overall verdict with failure analysis and cause attribution

Return verdicts in this JSON format:
{
  "overall_verdict": "PASS|FAIL|PARTIAL|INCONCLUSIVE",
  "task_verdicts": [
    {"task_id": "...", "verdict": "PASS|FAIL|...", "assertion_results": [...], "failure_cause": null}
  ],
  "acceptance_criteria_verdicts": [
    {"criterion": "...", "verdict": "PASS|FAIL", "evidence": "..."}
  ],
  "failure_analysis": [...],
  "specification_bugs": [...],
  "human_review_items": [...]
}
"""
)
```

**c) If wicked-qe is NOT installed**, fall back to basic self-grading: read each evidence file and evaluate the assertions yourself. This is less reliable but still functional.

### 7. Aggregate Results

Parse the reviewer's verdict and the kanban project state:

```bash
cd plugins/wicked-kanban && uv run python scripts/kanban.py get-project ${project_id}
```

Display results using the reviewer's verdicts:

```markdown
## Test Results: ${plugin_name}/${scenario_name}

**Kanban Project**: ${project_id}
**Overall Verdict**: PASS | FAIL | PARTIAL | INCONCLUSIVE
**Review**: Independent (wicked-qe reviewer) | Self-graded (fallback)

### Specification Notes
{Any mismatches caught by the writer before execution}

### Task Results
| # | Task | Verdict | Evidence Summary |
|---|------|---------|-----------------|
| 1 | Execute setup | PASS | Setup completed, files created |
| 2 | Run /wicked-mem:store | PASS | Evidence shows "stored" in output |
| 3 | Verify recall | FAIL | Evidence shows empty results, expected "ACID" |

### Acceptance Criteria
| Criterion | Verdict | Evidence |
|-----------|---------|----------|
| Memory stored successfully | PASS | store-output contains "stored" |
| Recalled memories are relevant | FAIL | recall-output is empty |

### Failures
- **Task 3 — Verify recall**: Evidence `recall-output` does not contain "ACID"
  - **Cause**: IMPLEMENTATION_BUG — recall function returns empty for tag-based queries
  - **Evidence file**: ~/.something-wicked/wg-test/evidence/${project_id}/task-03-verify.json

### View Full Evidence
Run `/wicked-kanban:board-status` or check project ${project_id} for task artifacts with evidence JSON files.
```

**Overall verdict logic** (from reviewer):
- All task verdicts PASS → **PASS**
- Any task verdict FAIL → **FAIL**
- All automated pass but human review items pending → **PARTIAL**
- Missing evidence prevents evaluation → **INCONCLUSIVE**

### 8. File GitHub Issues for Failures

**Trigger**: Any task has FAIL verdict (always when `--issues` flag is set; otherwise ask the user).

If there are failures:

1. **Without `--issues` flag**: Use AskUserQuestion — "N task(s) failed. File GitHub issues for the failures?"
   - "Yes, file issues for all failures"
   - "Let me pick which ones"
   - "No, just show the results"

2. **With `--issues` flag**: Skip the prompt, file issues for all failures automatically.

#### Filing Issues

For each failure, read the evidence from kanban task artifacts and the reviewer's failure analysis, then use `gh issue create` via Bash.

**Title**: `test(<plugin>): <scenario> scenario failure`
**Labels**: `bug`, `<plugin-name>`
**Body template**:

```markdown
## UAT Scenario Failure

**Plugin**: <plugin-name>
**Scenario**: <scenario-name> (`plugins/<plugin-name>/scenarios/<scenario-file>`)
**Kanban Project**: <project_id>
**Run date**: <UTC timestamp>
**Review type**: Independent (wicked-qe) | Self-graded (fallback)

## Specification Notes
<Any mismatches caught by the writer>

## Failed Tasks

| # | Task | Assertion | Verdict | Cause |
|---|------|-----------|---------|-------|
| <n> | <description> | <assertion> | FAIL | <cause from reviewer> |

## Evidence Details

<For each failed task, include key evidence excerpts from the reviewer>

## Failure Analysis

<Reviewer's cause attribution and recommendations>

## Scenario Description

<description from scenario frontmatter>

## Kanban Evidence

Full evidence available in kanban project `<project_id>` — run `/wicked-kanban:board-status` to view.
Evidence JSON files: `~/.something-wicked/wg-test/evidence/<project_id>/`

## Suggested Resolution

Run `/wg-issue <this-issue-number>` to start a crew project that resolves this failure.
```

**Two-step filing**: Use `gh issue create` with `--json number` to capture the issue number, then update the body's "Suggested Resolution" section with the actual number via `gh issue edit`.

**Grouping**: If multiple scenarios fail for the **same plugin**, combine them into a single issue rather than one per scenario.

**Deduplication**: Before filing, check for existing open issues with a matching title prefix:

```bash
gh issue list --state open --search "test(<plugin-name>):" --json number,title --limit 5
```

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

## Integration with wicked-qe

This command implements the same three-agent pattern as `/wicked-qe:acceptance` (Writer → Executor → Reviewer), adapted for kanban-tracked execution:

| Role | /wg-test | /wicked-qe:acceptance |
|------|----------|----------------------|
| **Writer** | `wicked-scenarios:scenario-converter` | `wicked-qe:acceptance-test-writer` |
| **Executor** | `wicked-scenarios:scenario-executor` (per task) | `wicked-qe:acceptance-test-executor` |
| **Reviewer** | `wicked-qe:acceptance-test-reviewer` (shared) | `wicked-qe:acceptance-test-reviewer` |

Key differences:
- `/wg-test` decomposes scenarios into kanban tasks for **token isolation** — each executor gets ~20 lines, not 300+
- `/wg-test` tracks progress via **kanban board** with artifacts pointing to evidence JSON files
- `/wicked-qe:acceptance` operates as a **standalone pipeline** — useful for non-plugin scenarios or when kanban tracking isn't needed
- Both share the **evidence protocol** and **assertion operators** from wicked-qe's acceptance-testing skill

## Why This Architecture?

**Token efficiency**: Each subagent receives only ONE task definition, not the full scenario. A 300-line scenario with 11 steps becomes 11 focused tasks of ~20 lines each.

**No false positives**: Execution and grading are separated. The executor captures evidence verbatim. The reviewer evaluates assertions against cold evidence independently.

**Specification bug detection**: The converter reads implementation code before designing tests, catching mismatches early — before any test runs.

**Evidence tracking**: Evidence is stored as kanban task artifacts using wicked-crew's `{tier}:{type}:{detail}` naming convention. Artifacts point to evidence JSON files on disk. Compatible with `/wicked-crew:evidence` for tiered evidence display.

**Status visibility**: The orchestrator reads kanban project state and reviewer verdicts — no need to parse prose output from a subagent.

**Failure isolation**: If task 3 of 11 errors, remaining tasks can still execute. Evidence for the failure is in the task's artifact.

**Graceful degradation**: If wicked-qe is not installed, falls back to self-grading. Results are less reliable but the system still works.

**Hooks still fire**: Subagents run in interactive mode where SessionStart, PostToolUse, PreToolUse, and all plugin hooks fire naturally. This is still TRUE user acceptance testing.
