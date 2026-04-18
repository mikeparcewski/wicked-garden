---
name: scenario-executor
description: |
  Runner for acceptance test scenarios — reads scenario markdown, executes
  steps via Bash or Skill tool, and reports PASS/FAIL with evidence. Handles
  mixed bash + slash-command scenarios, prose-only steps, and wicked-scenarios
  format delegation. A tool/runner capability, not an agent identity —
  the test-designer agent owns the role of designing and rendering verdicts.

  Use when: "run this scenario", "execute the acceptance test for X",
  "run the wicked-scenarios file", "test this slash command end-to-end".
---

# Scenario Executor

Runs acceptance test scenarios end-to-end. Parses scenario markdown, executes
each step (bash, slash-command, or prose), captures output, and reports
structured results. This is a **runner tool** — the decision of what a result
means is made by the **test-designer** agent (Phase 3: ANALYZE / VERDICT).

## Quick Start

Invoke this skill when you have a scenario file and need to execute it:

```
Skill(
  skill="wicked-garden:qe:scenario-executor",
  args="{path_to_scenario_file}"
)
```

Typical output:
```
## Results: {scenario name}
**Status**: PASS | FAIL | PARTIAL
**Duration**: {total}s
**Steps**: {N} passed, {M} failed, {K} skipped

| Step | Type | Status | Duration | Details |
```

## When to Invoke

- You need to run a wicked-garden acceptance scenario
- You need to run a wicked-scenarios format file (api/browser/perf/infra/security/a11y)
- A scenario mixes bash commands and `/wicked-garden:*` slash commands
- A scenario has prose-only steps that need interpretation

## QE Pipeline Context

Before executing, detect whether this skill is being invoked inside a QE trio
pipeline (via the test-designer agent) or standalone.

**Detection**: If the invoking context contains a `## Test Plan` header, this
skill is running inside the test-designer agent's Phase 2 (EXECUTE). Skip
further QE checks and proceed with direct execution.

**Standalone**: If no test plan header, the caller is executing a scenario
directly. Consider recommending they dispatch the **test-designer** agent
for evidence-gated acceptance testing instead.

## Execution Process

For each scenario file:

1. **Read** — use Read tool
2. **Parse YAML frontmatter** — name, description, tools (required/optional), env, timeout
3. **Execute `## Setup`** — bash via Bash tool; slash commands via Skill tool
4. **Execute each `### Step N`** in order
5. **Execute `## Cleanup`** — always runs, even on failure
6. **Report results** in the standard format

## Slash-Command Parsing

Slash commands in scenario files follow:
```
/wicked-garden:{domain}:{command} [args...]
```

Shortened form:
```
/wicked-{domain}:{command} [args...]
```

For the Skill tool always use the full form. Examples:

- `/wicked-garden:mem:store --type decision "chose PostgreSQL"`
  → `Skill(skill="wicked-garden:mem:store", args='--type decision "chose PostgreSQL"')`
- `/wicked-garden:crew:start "Add OAuth2"`
  → `Skill(skill="wicked-garden:crew:start", args='"Add OAuth2"')`

## PASS/FAIL Rules

- **Bash steps**: exit code 0 = PASS, non-zero = FAIL
- **Slash-command steps**: Skill tool returns without error = PASS; error or
  failure message = FAIL
- **Mixed steps**: all must succeed for PASS; any failure = FAIL
- **Prose steps**: execute interpreted action + verify expected outcome
- **Missing external CLI tool**: SKIPPED (not FAIL) — only for external CLIs
  not bundled with the plugin
- **Per-scenario**: all PASS → PASS; any FAIL → FAIL

See [refs/prose-interpretation.md](refs/prose-interpretation.md) for the full
prose-step decision tree and interpretation patterns.

## Output Format

```markdown
## Results: {scenario name}

**Status**: {PASS|FAIL|PARTIAL}
**Duration**: {total}s
**Steps**: {pass} passed, {fail} failed, {skip} skipped

| Step | Type | Status | Duration | Details |
|------|------|--------|----------|---------|
| {name} | bash | PASS | 0.5s | |
| {name} | skill | PASS | 2.1s | |
| {name} | skill | FAIL | 1.0s | Error: ... |
| {name} | prose | PASS | 1.5s | Verified field X = Y |
```

## Active Project Handling

Before executing scenarios that invoke `crew:start`, check for an active crew project:

```
Skill(skill="wicked-garden:crew:status")
```

If a project is active, archive it first:
```
Skill(skill="wicked-garden:crew:archive", args="{active-project-slug}")
```

## Rules

- **Sequential execution** — run steps in order, don't parallelize
- **Continue on failure** — record FAIL but keep going
- **Setup/Cleanup always run** — even on failure
- **Respect timeouts** — use `timeout` for bash commands if specified
- **Capture evidence** — save stdout/stderr snippets for failed steps
- **Be honest** — don't mark PASS if output indicates an error, even if exit code is 0
- **Interpret prose** — never skip a step with an executable action just because
  it lacks a code fence

## See Also

- [refs/prose-interpretation.md](refs/prose-interpretation.md) — prose-step
  decision tree
- **test-designer** agent — owns the write + execute + verdict pipeline when
  running evidence-gated acceptance testing
- `/wicked-garden:qe:run` — wicked-scenarios CLI-tool runner (for scenarios
  with `category` frontmatter)
