---
description: Run evidence-gated acceptance testing with Write → Execute → Review pipeline
argument-hint: "<scenario file or directory> [--phase write|execute|review|all] [--plan <existing-plan>] [--evidence <existing-report>]"
---

# /wicked-garden:qe:acceptance

Three-agent acceptance testing pipeline that separates test design, execution, and evaluation for higher-fidelity results than self-grading.

## Architecture

```
Scenario ──→ [Writer] ──→ Test Plan ──→ [Executor] ──→ Evidence ──→ [Reviewer] ──→ Verdict
                │                           │                           │
           reads impl code            no judgment              independent evaluation
           finds spec bugs            captures artifacts       cites evidence
           designs assertions         records everything       attributes causes
```

**Why three agents?**

- **Writer** catches specification bugs before execution begins
- **Executor** can't "imagine" success — must produce artifacts
- **Reviewer** can't be biased by watching execution — evaluates cold evidence

## Instructions

### 0. Resolve Canonical Artifact Paths

Before parsing arguments, resolve canonical paths for QE artifacts. These paths are used throughout the pipeline.

```bash
QE_DIR=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/resolve_path.py wicked-qe 2>/dev/null || echo "${TMPDIR:-/tmp}/wicked-qe-evidence")
SCENARIO_SLUG=$(echo "{scenario_name}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g')
TEST_PLAN="${QE_DIR}/test-plans/${SCENARIO_SLUG}.md"
EVIDENCE="${QE_DIR}/evidence/${SCENARIO_SLUG}.md"
VERDICT="${QE_DIR}/verdicts/${SCENARIO_SLUG}.json"
REGISTRY="${QE_DIR}/evidence/${SCENARIO_SLUG}-registry.json"
```

These canonical paths are passed to executor and reviewer agents so all three agents write to and read from consistent locations.

### 1. Parse Arguments

Parse `$ARGUMENTS`:

- **Scenario target**: File path, directory, or glob pattern
  - Single file: `plugins/wicked-mem/scenarios/01-decision-recall.md`
  - Directory: `plugins/wicked-mem/scenarios/` (runs all `.md` except README)
  - Plugin shorthand: `wicked-mem` (finds scenarios dir automatically)
- **Phase control**:
  - `--phase all` (default): Run full Write → Execute → Review pipeline
  - `--phase write`: Only generate test plan (for review before execution)
  - `--phase execute`: Run execution with existing plan (requires `--plan`)
  - `--phase review`: Run review with existing evidence (requires `--plan` and `--evidence`)
- **Existing artifacts**:
  - `--plan <path>`: Use existing test plan instead of generating one
  - `--evidence <path>`: Use existing evidence report instead of executing

### 2. Discover Scenarios

If target is a directory or plugin name:

```bash
# Find scenario files
for f in ${target_dir}/scenarios/*.md; do
  [ "$(basename "$f")" = "README.md" ] && continue
  echo "$f"
done
```

If multiple scenarios found and not running `--all`, use AskUserQuestion to let user select.

### 3. Phase: Write (Test Plan Generation)

For each scenario:

```
Task(
  subagent_type="wicked-garden:qe:acceptance-test-writer",
  prompt="""Generate an evidence-gated test plan for this acceptance scenario.

## Scenario
{scenario file content}

## Scenario Source
{file path}

## Instructions
1. Read the scenario thoroughly
2. Find and read the implementation code referenced in the scenario
3. Design evidence requirements for every step
4. Write concrete, independently-verifiable assertions
5. Map every success criterion to specific assertions
6. Flag any specification mismatches you discover

Return the complete test plan in the standard format.
"""
)
```

**Output**: Save the test plan and display a summary:

```markdown
## Test Plan Generated: {scenario name}

**Steps**: {count}
**Assertions**: {count}
**Evidence items**: {count}
**Specification notes**: {count} ({list if any})

### Coverage
| Success Criterion | Assertions | Steps |
|-------------------|------------|-------|
| {criterion} | {count} | {step IDs} |
```

If `--phase write`, stop here and present the test plan for review.

### 4. Phase: Execute (Evidence Collection)

```
Task(
  subagent_type="wicked-garden:qe:acceptance-test-executor",
  prompt="""Execute this test plan and collect evidence artifacts.

## Test Plan
{test plan content}

## Rules
1. Execute each step exactly as written
2. Capture ALL required evidence for every step
3. Do NOT judge results — only record what happened
4. Continue to next step even if current step's action fails
5. Record timestamps for every step
6. Capture final environment state after all steps

Return the complete evidence report.
"""
)
```

**Output**: After the executor returns, check the response for the forced recapture directive.

#### Forced Recapture Detection

If the executor's response contains the line `## Forced Recapture Required`:

- **Do NOT dispatch the reviewer** (Step 5).
- Present the recapture directive to the user exactly as the executor emitted it.
- Display an additional notice:

```markdown
## Evidence Collection Incomplete

The executor reported missing evidence items. Review has been blocked until evidence is complete.

**Next steps**:
1. Investigate why the evidence items were not captured (see Forced Recapture Required section above)
2. Fix the issue (e.g., missing file, failing command, misconfigured step)
3. Re-invoke with `--phase execute --plan {TEST_PLAN}` to re-run execution

The reviewer will return INCONCLUSIVE until the artifact registry at `{REGISTRY}` is present and complete.
```

Stop here — do not proceed to Step 5.

If the executor's response does NOT contain `## Forced Recapture Required`, save the evidence report and display execution summary:

```markdown
## Execution Complete: {scenario name}

**Steps executed**: {N} of {M}
**Steps skipped**: {count}
**Duration**: {total seconds}
**Evidence items collected**: {count}
**Registry written**: {YES — path: {REGISTRY} | NO — see execution notes}

### Execution Log
| Step | Status | Duration | Evidence |
|------|--------|----------|----------|
| STEP-1 | Executed | 1.2s | 2 items |
| STEP-2 | Executed | 0.5s | 3 items |
| STEP-3 | Skipped | - | dependency |
```

If `--phase execute`, stop here.

### 5. Phase: Review (Evidence Evaluation)

#### Registry Pre-Check

Before dispatching the reviewer, verify that the artifact registry exists:

```bash
ls "${REGISTRY}" 2>/dev/null && echo "REGISTRY_OK" || echo "REGISTRY_MISSING"
```

If the registry file is missing, attempt to recover it from DomainStore before blocking:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/qe/registry_lookup.py \
  --scenario-slug "${SCENARIO_SLUG}" \
  --output "${REGISTRY}"
```

If `registry_lookup.py` exits 0, the registry has been restored — proceed to dispatch the reviewer as normal.

If `registry_lookup.py` exits non-zero (not found in DomainStore either), do not dispatch the reviewer. Display an error instead:

```markdown
## Review Blocked: Evidence Registry Not Found

The artifact registry was not found at:
`{REGISTRY}`

This means either:
- The executor phase has not been run yet, or
- The executor encountered missing evidence and did not complete the checkpoint

**Required action**: Run the executor phase first:
```
/wicked-garden:qe:acceptance --phase execute --plan {TEST_PLAN}
```

The reviewer will return INCONCLUSIVE without a valid registry.
```

Stop here — do not dispatch the reviewer.

If the registry exists, proceed to dispatch the reviewer:

```
Task(
  subagent_type="wicked-garden:qe:acceptance-test-reviewer",
  prompt="""Review this evidence against the test plan assertions.

## Original Scenario
{scenario content}

## Test Plan
{test plan content}

## Evidence Report
{evidence report content}

## Artifact Registry
Registry path: {REGISTRY}
Scenario slug: {SCENARIO_SLUG}

## Instructions
1. Perform the artifact registry pre-check (Step 1a) — verify the registry at the path above
2. Verify evidence completeness against the registry — is every required artifact present?
3. Verify SHA-256 checksums for each evidence item in the registry
4. Evaluate each assertion against its evidence using the specified operator
5. Check specification notes from the writer
6. Render step-level verdicts
7. Map results to original acceptance criteria
8. Produce overall verdict with failure analysis
   - Return INCONCLUSIVE (not PASS or FAIL) if registry absent or checksums mismatched

Return the complete review verdict.
"""
)
```

### 6. Present Results

Display the final verdict:

```markdown
## Acceptance Test Results: {scenario name}

### Verdict: {PASS | FAIL | PARTIAL | INCONCLUSIVE}

### Acceptance Criteria
| Criterion | Verdict | Evidence |
|-----------|---------|----------|
| {criterion text} | PASS/FAIL | {brief evidence citation} |

### Step Results
| Step | Assertions | Passed | Failed | Verdict |
|------|------------|--------|--------|---------|
| STEP-1 | 3 | 3 | 0 | PASS |
| STEP-2 | 4 | 2 | 2 | FAIL |

### Failures
{For each failure:}
- **{assertion}**: Expected {X}, found {Y}. Cause: {taxonomy}

### Specification Bugs
{Any mismatches between scenario and implementation}

### Human Review Required
{Items flagged for human judgment}
```

### 7. Multi-Scenario Aggregation

When running multiple scenarios, aggregate results:

```markdown
## Acceptance Test Suite Results

### Summary
- **Total scenarios**: {N}
- **Passed**: {N}
- **Failed**: {N}
- **Partial**: {N}
- **Inconclusive**: {N}

### Results
| Scenario | Verdict | Passed | Failed | Duration |
|----------|---------|--------|--------|----------|
| {name} | PASS | 8/8 | 0 | 3.2s |
| {name} | FAIL | 5/7 | 2 | 4.1s |

### All Failures
{Grouped by cause taxonomy}

#### Implementation Bugs
- {scenario}: {assertion} — {description}

#### Specification Bugs
- {scenario}: {assertion} — {description}

#### Environment Issues
- {scenario}: {assertion} — {description}
```

## Examples

```bash
# Full pipeline for one scenario
/wicked-garden:qe:acceptance plugins/wicked-mem/scenarios/01-decision-recall.md

# Generate test plan only (review before running)
/wicked-garden:qe:acceptance wicked-mem/01-decision-recall --phase write

# Execute with existing plan
/wicked-garden:qe:acceptance --phase execute --plan /tmp/test-plan.md

# Review existing evidence
/wicked-garden:qe:acceptance --phase review --plan /tmp/test-plan.md --evidence /tmp/evidence.md

# Run all scenarios for a plugin
/wicked-garden:qe:acceptance wicked-crew --all

# Run scenarios for your own project
/wicked-garden:qe:acceptance tests/acceptance/user-login.md
```

## Integration

- **wicked-crew**: Use during QE phases for evidence-gated quality gates
- **wicked-scenarios**: Executor delegates E2E CLI steps to `/wicked-garden:scenarios:run --json` for machine-readable execution artifacts. Writer understands wicked-scenarios format natively.
- **wicked-kanban**: Track acceptance failures as tasks. When invoked with `--kanban` (or auto-detected when crew is active), creates a kanban project with one task per test plan step, stores evidence inline in kanban artifacts.
- **/wg-test**: Delegates to `/wicked-garden:qe:acceptance` as the primary acceptance pipeline. Falls back to `/wicked-garden:scenarios:run` directly if QE is not installed.

### Degradation Behavior

| QE | Scenarios | `/wg-test` behavior |
|----|-----------|--------------------|
| Yes | Yes | QE acceptance with `scenarios:run --json` backend, kanban tracking. Issue filing via `scenarios:report` when `--issues` flag is passed to `/wg-test`. |
| Yes | No | QE acceptance runs bash steps inline (no CLI tool orchestration). Issue filing not available (no `scenarios:report`). |
| No | Yes | `scenarios:run` directly (exit code PASS/FAIL, no evidence protocol, no independent review). Issue filing not available (report requires structured QE verdicts). |
| No | No | Error: "Install wicked-qe or wicked-scenarios to enable testing" |
