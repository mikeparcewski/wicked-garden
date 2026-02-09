---
description: Execute an E2E test scenario by orchestrating CLI tools
---

# /wicked-scenarios:run

Execute an E2E test scenario by orchestrating CLI tools.

## Usage

```
/wicked-scenarios:run <scenario-file> [--junit report.xml] [--verbose]
```

## Instructions

### 1. Parse Scenario

Read the scenario markdown file. Extract YAML frontmatter:
- `name`: Scenario identifier
- `description`: What this tests
- `category`: api|browser|perf|infra|security|a11y
- `tools.required`: CLIs that must be available
- `tools.optional`: CLIs used if available
- `env`: Required environment variables
- `timeout`: Max seconds (default 120)

### 2. CLI Discovery

Run the discovery script:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cli_discovery.py" {space-separated tool names from required + optional}
```

Parse the JSON output. For each tool:
- **Available**: Ready to use
- **Not available**: Mark all steps using this tool as SKIPPED.

Never hard-fail on missing tools. Always degrade to PARTIAL.

### 2.5. Pre-Flight Check

If any **required** or **optional** tools are missing, ask the user if they'd like to install them before proceeding. Use AskUserQuestion:

**Question**: "Some tools needed for this scenario are not installed. Want me to install them?"
**Options**:
- **Install all missing** — Run all install commands, then proceed
- **Install required only** — Install only required tools (skip optional), then proceed
- **Skip and run anyway** — Proceed with missing tools (steps will be SKIPPED)

If the user chooses to install, run the install commands via Bash:
```bash
{install command for each missing tool, e.g. "brew install hurl", "npm i -g pa11y"}
```

After installation, re-run CLI discovery to confirm tools are now available.

If the user chooses to skip, proceed normally — missing tool steps become SKIPPED and overall status degrades to PARTIAL.

### 3. Environment Check

For each entry in frontmatter `env`:
- Check if the environment variable is set
- If missing and variable name does NOT end with `?`: warn but continue (mark affected steps as SKIPPED)
- If missing and variable name ends with `?`: silently skip (it's optional)

### 4. Execute Setup

Parse the markdown body for the `## Setup` section. If present, extract its fenced code block and execute it via Bash. Setup typically sets environment variables and installs prerequisites.

If Setup fails (non-zero exit), warn but continue — steps may still work.

### 5. Execute Steps

Parse the markdown body for step sections (`### Step N: description (cli-name)`).

For each step:
1. Extract the fenced code block
2. Identify the CLI from: code fence language → step header parenthetical → first command in bash block
3. If CLI is not available: record as **SKIPPED**, continue to next step
4. Execute the code block via Bash tool with timeout. For non-bash code blocks (e.g., `hurl`, `javascript`), wrap as a CLI invocation: write the block content to a temp file under `${TMPDIR:-/tmp}` (e.g., `"${TMPDIR:-/tmp}/wicked-scenario-step.hurl"`) and invoke the CLI (`hurl --test <tmpfile>` for hurl blocks, `k6 run <tmpfile>` for JS/k6 blocks). These temp files are cleaned up in the Cleanup section.
5. Capture: stdout, stderr, exit code, wall-clock duration
6. If CLI produces structured output (JSON/XML), collect it as evidence
7. Determine result:
   - Exit code 0 → **PASS**
   - Exit code non-zero → **FAIL**
   - CLI not available → **SKIPPED**

### 6. Execute Cleanup

Parse the markdown body for the `## Cleanup` section. If present, execute its fenced code block via Bash. Cleanup runs regardless of step results (like a `finally` block).

### 7. Aggregate Results

Calculate overall status:
- All steps PASS → **PASS** (exit code 0)
- Any step FAIL → **FAIL** (exit code 1)
- No FAILs but some SKIPPEDs → **PARTIAL** (exit code 2)

### 8. Generate Report

Display results:

```markdown
## Scenario Results: {name}

**Status**: {PASS|FAIL|PARTIAL}
**Duration**: {total seconds}s
**Steps**: {pass_count} passed, {fail_count} failed, {skip_count} skipped

| Step | Status | Duration | Details |
|------|--------|----------|---------|
| {step name} | PASS | 0.5s | |
| {step name} | FAIL | 2.0s | Exit code 1: {stderr snippet} |
| {step name} | SKIPPED | - | Tool 'k6' not installed |

### Missing Tools
| Tool | Install |
|------|---------|
| {tool} | {install command} |

### Evidence
{For failed steps, show stdout/stderr snippets}
```

### 9. JUnit XML (if --junit)

If `--junit <path>` is specified, write JUnit XML:

```bash
cat > {path} << 'JUNIT_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="wicked-scenarios" tests="{total}" failures="{fail_count}" skipped="{skip_count}" time="{total_time}">
  <testsuite name="{scenario_name}" tests="{total}" failures="{fail_count}" skipped="{skip_count}" time="{total_time}">
    <!-- One testcase per step -->
  </testsuite>
</testsuites>
JUNIT_EOF
```
