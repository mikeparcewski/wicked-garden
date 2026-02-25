---
description: Run evidence-gated acceptance testing with three-agent separation (Writer/Executor/Reviewer)
arguments:
  - name: target
    description: "PLUGIN SCENARIO SCENARIO_FILE — or multiple triplets for batch mode. Append --report to auto-invoke /wicked-scenarios:report on failures."
    required: true
---

# /wicked-scenarios:acceptance

Run evidence-gated acceptance testing using the three-agent architecture: **Writer** (converter) designs evidence requirements, **Executor** (runner) captures artifacts, **Reviewer** evaluates evidence independently.

Supports single scenario or **batch mode** (multiple scenarios with aggregated results).

## Architecture

```
Scenario ──→ [Converter/Writer] ──→ Kanban Tasks ──→ [Executor] ──→ Evidence ──→ [Reviewer] ──→ Verdict
                  │                    (per task)        │                    │
             reads impl code      evidence requirements  no judgment      independent evaluation
             flags spec bugs      + assertions per task  captures artifacts  cites evidence
```

## Instructions

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine mode:

**Single mode** (3 positional args):
- `PLUGIN`: Plugin name (e.g., `wicked-mem`)
- `SCENARIO`: Scenario name (e.g., `decision-recall`)
- `SCENARIO_FILE`: Path to scenario markdown file (e.g., `plugins/wicked-mem/scenarios/decision-recall.md`)

**Batch mode** (multiple triplets separated by `--next`):
```
wicked-mem decision-recall plugins/wicked-mem/scenarios/decision-recall.md --next wicked-mem store-recall plugins/wicked-mem/scenarios/store-recall.md
```

**Flags**:
- `--report`: After all scenarios complete, auto-invoke `/wicked-scenarios:report` for any failures
- `--report-auto`: Same as `--report` but files issues without prompting (passes `--auto` to report)

For single mode, all three positional args are required. If missing, report error and exit.

For batch mode, parse each triplet between `--next` delimiters. If any triplet is incomplete, report error and exit.

### 2. Convert Scenario to Kanban Tasks (Writer Phase)

Spawn the `wicked-scenarios:scenario-converter` agent to decompose the scenario into evidence-gated test tasks on a kanban board. Pass the scenario **file path** — the converter reads it directly. Do NOT inline scenario content.

```
Task(
  subagent_type="wicked-scenarios:scenario-converter",
  prompt="Convert this scenario into kanban-tracked, evidence-gated test tasks.

PLUGIN: ${PLUGIN}
SCENARIO: ${SCENARIO}
SCENARIO_FILE: ${SCENARIO_FILE}

Read the scenario file at the path above. Do NOT expect it inline — use the Read tool."
)
```

The converter (serving the Writer role):
1. Reads the scenario AND the implementation code
2. Creates a kanban project: `UAT: ${PLUGIN}/${SCENARIO}`
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

### 3. Execute Tasks Sequentially (Executor Phase)

For each task from the converter output (in order, respecting `depends_on`):

1. **Check dependencies** — if any dependency task errored, mark this task as `skipped` by adding a comment and moving to Done:
   ```bash
   cd plugins/wicked-kanban && uv run python scripts/kanban.py add-comment "${project_id}" "${kanban_task_id}" "SKIPPED: Dependency ${dep_id} could not execute"
   cd plugins/wicked-kanban && uv run python scripts/kanban.py add-artifact "${project_id}" "${kanban_task_id}" "L3:test:skipped" --type document --path "n/a"
   cd plugins/wicked-kanban && uv run python scripts/kanban.py update-task "${project_id}" "${kanban_task_id}" --swimlane "${done_swimlane_id}"
   ```

2. **Move to In Progress**:
   ```bash
   cd plugins/wicked-kanban && uv run python scripts/kanban.py update-task "${project_id}" "${kanban_task_id}" --swimlane "${in_progress_swimlane_id}"
   ```

3. **Spawn executor subagent** for the task. Pass the **task ID** — the executor pulls details via TaskGet. Do NOT inline task JSON.
   ```
   Task(
     subagent_type="wicked-scenarios:scenario-executor",
     prompt="Execute this test task and capture evidence. Do NOT judge pass/fail.

   PROJECT_ID: ${project_id}
   KANBAN_TASK_ID: ${kanban_task_id}
   DONE_SWIMLANE_ID: ${done_swimlane_id}
   PLUGIN: ${PLUGIN}
   TASK_ID: ${task_id}

   Use TaskGet to read the full task description and evidence requirements.
   Execute the action described. Capture ALL required evidence.
   Record evidence as a kanban artifact. Do NOT evaluate assertions — just capture.
   Do NOT read the full scenario."
   )
   ```

4. **Check execution status** — after executor completes, note whether it reported EXECUTED, SKIPPED, or ERROR.

**IMPORTANT**: Each executor gets only its own task — NOT the full scenario. This prevents token overflow.

### 4. Independent Review (Reviewer Phase)

After all tasks execute, collect evidence and spawn an independent reviewer.

**a) Gather evidence from kanban artifacts:**

Evidence is stored inline in kanban artifacts (named `L3:test:{task_id}`). Retrieve it:

```bash
cd plugins/wicked-kanban && uv run python scripts/kanban.py get-project "${project_id}"
```

Parse each task's `artifacts` array — artifacts with names starting with `L3:test:` contain evidence in their `content` field.

**b) Spawn the reviewer:**

If wicked-qe is installed (check `ls plugins/wicked-qe/.claude-plugin/plugin.json 2>/dev/null`):

Pass evidence **inline from kanban artifacts** — the reviewer does NOT need file paths.

```
Task(
  subagent_type="wicked-qe:acceptance-test-reviewer",
  prompt="""Review evidence against the test plan assertions.

## Scenario
${SCENARIO} (${SCENARIO_FILE})

## Specification Notes
${specification_notes from converter — keep brief, max 5 lines}

## Evidence Location
Evidence is stored inline in kanban artifacts for project ${project_id}.
Run: cd plugins/wicked-kanban && uv run python scripts/kanban.py get-project "${project_id}"
Look for artifacts named L3:test:{task_id} — evidence is in the "content" field.

## Task IDs
${list of task IDs from converter — one per line}

Use TaskGet for each task ID to read its description, evidence requirements, and assertions.

## Instructions
1. Retrieve kanban project and extract evidence from artifact content fields
2. Use TaskGet to pull task descriptions and assertion definitions
3. Verify evidence completeness — is every required artifact present?
4. Evaluate each assertion against its evidence using the specified operator
5. Render task-level verdicts (PASS, FAIL, INCONCLUSIVE, SKIPPED)
6. Map results to original acceptance criteria
7. Produce overall verdict with failure analysis and cause attribution

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

**c) If wicked-qe is NOT installed**, fall back to basic self-grading: retrieve evidence from kanban artifacts and evaluate the assertions yourself. This is less reliable but still functional.

### 5. Aggregate and Return Results

Parse the reviewer's verdict and the kanban project state:

```bash
cd plugins/wicked-kanban && uv run python scripts/kanban.py get-project "${project_id}"
```

Display results using the reviewer's verdicts:

```markdown
## Test Results: ${PLUGIN}/${SCENARIO}

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
  - **Evidence**: Kanban artifact `L3:test:task-03-verify` on project ${project_id}

### View Full Evidence
Run `/wicked-kanban:board-status` or check project ${project_id} for task artifacts with inline evidence.
```

**Overall verdict logic** (from reviewer):
- All task verdicts PASS → **PASS**
- Any task verdict FAIL → **FAIL**
- All automated pass but human review items pending → **PARTIAL**
- Missing evidence prevents evaluation → **INCONCLUSIVE**

## Why This Architecture?

**Token efficiency**: Each subagent receives only ONE task definition, not the full scenario. A 300-line scenario with 11 steps becomes 11 focused tasks of ~20 lines each.

**No false positives**: Execution and grading are separated. The executor captures evidence verbatim. The reviewer evaluates assertions against cold evidence independently.

**Specification bug detection**: The converter reads implementation code before designing tests, catching mismatches early — before any test runs.

**Evidence tracking**: Evidence is stored inline in kanban task artifacts using wicked-crew's `{tier}:{type}:{detail}` naming convention. No external files — evidence lives with the task.

**Failure isolation**: If task 3 of 11 errors, remaining tasks can still execute. Evidence for the failure is in the task's artifact.

**Graceful degradation**: If wicked-qe is not installed, falls back to self-grading. Results are less reliable but the system still works.

**Hooks still fire**: Subagents run in interactive mode where SessionStart, PostToolUse, PreToolUse, and all plugin hooks fire naturally.

## Batch Mode

When multiple scenarios are provided (via `--next` delimiters), execute each scenario through the full pipeline (steps 2-5) **sequentially**. Collect results from each run.

### Batch Execution Loop

For each scenario triplet `(PLUGIN, SCENARIO, SCENARIO_FILE)`:
1. Run steps 2-5 as normal for that scenario
2. Store the result: `{plugin, scenario, scenario_file, overall_verdict, task_verdicts, acceptance_criteria_verdicts, failure_analysis, specification_notes}`
3. Continue to the next scenario regardless of the previous result

### Batch Aggregation

After all scenarios complete, display an aggregate summary:

```markdown
## Batch Results: N scenarios

| # | Plugin | Scenario | Verdict |
|---|--------|----------|---------|
| 1 | wicked-mem | decision-recall | PASS |
| 2 | wicked-mem | store-recall | FAIL |
| 3 | wicked-crew | phase-flow | PASS |

**Summary**: N passed, N failed, N partial, N inconclusive

### Failures
<For each FAIL scenario, show the condensed failure table from step 5>
```

**Aggregate verdict logic**:
- All scenarios PASS → **ALL PASS**
- Any scenario FAIL → **FAILURES DETECTED** (count)
- Mix of PASS/PARTIAL/INCONCLUSIVE with no FAIL → **PARTIAL**

### Report Integration

If `--report` or `--report-auto` flag is present and any scenario has FAIL verdict:

```
Skill(
  skill="wicked-scenarios:report",
  args="${'--auto' if report_auto else ''}"
)
```

The report command reads failure details from conversation context and handles GitHub issue filing, deduplication, and grouping.
