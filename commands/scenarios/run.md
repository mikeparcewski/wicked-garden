---
description: Execute an E2E test scenario by orchestrating CLI tools
---

# /wicked-garden:scenarios:run

Execute an E2E test scenario by orchestrating CLI tools.

## Usage

```
/wicked-garden:scenarios:run <scenario-file> [--junit report.xml] [--verbose] [--json]
```

**Modes:**
- **Interactive** (default): Markdown report, install prompts, PASS/FAIL verdicts
- **JSON** (`--json`): Machine-readable output, no prompts, no verdicts — pure execution artifacts for programmatic consumption (e.g., QE executor delegation)

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

### 2.1. Skill Discovery (Fallback for Missing Tools)

For any tools marked **not available** by CLI discovery, check if an equivalent skill can serve as a fallback. Skills from the ecosystem can substitute for missing CLI tools:

| Missing CLI | Fallback Skill | Notes |
|-------------|---------------|-------|
| `python3` (for test scripts) | `wicked-garden:startah:runtime-exec` | Smart Python/Node execution with automatic dependency resolution (uv, poetry, pip) |
| `playwright` | `wicked-garden:startah:agent-browser` | Only if `agent-browser` CLI is available (skill wraps agent-browser, not playwright directly) |

**Note**: `wicked-garden:scenarios:setup` can auto-install missing tools, but it is interactive (prompts user). In `--json` mode, setup is NOT invoked — missing tools go into the `missing_tools` array instead. In interactive mode, setup can be suggested during the Pre-Flight Check.

**Detection**: Check if the skill's parent plugin is installed:
```bash
ls plugins/wicked-startah/.claude-plugin/plugin.json 2>/dev/null && echo "STARTAH_AVAILABLE=true"
```

If a fallback skill is available, mark the tool as **available via skill** and adjust the step execution to use the Skill tool instead of Bash:
- Instead of `python3 <script>` via Bash, use `Skill(skill="wicked-garden:startah:runtime-exec", args="<script>")`
- Instead of `playwright test <url>` via Bash (when agent-browser is available), use `Skill(skill="wicked-garden:startah:agent-browser", args="<url> --screenshot")`

In `--json` mode, skill-based execution is still recorded in the same step format (stdout/stderr/exit_code/duration_ms). Note the execution method in a `method` field: `"method": "cli"` or `"method": "skill"`.

If no fallback skill is available, the tool remains marked as not available and steps using it will be SKIPPED as before.

### 2.5. Pre-Flight Check

**If `--json` mode**: Do NOT prompt for installation. Collect all missing tools (both required and optional) into a `missing_tools` array (with tool name and install command). Steps using missing tools will be recorded in `skipped_steps`. Continue to execution.

**If interactive mode (default)**:

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

### 8. Output Results

**If `--json` mode**: Output a single JSON object to the user. Do NOT include markdown report, PASS/FAIL verdicts, or JUnit XML. The JSON is the only output:

```json
{
  "scenario": "{name from frontmatter}",
  "steps": [
    {
      "name": "{step description}",
      "tool": "{cli tool used}",
      "method": "cli",
      "exit_code": 0,
      "stdout": "{captured stdout}",
      "stderr": "{captured stderr}",
      "duration_ms": 234
    }
  ],
  "setup": {"exit_code": 0, "stdout": "...", "stderr": ""},
  "cleanup": {"exit_code": 0, "stdout": "...", "stderr": ""},
  "missing_tools": [
    {"tool": "k6", "install": "brew install k6"}
  ],
  "skipped_steps": [
    {"name": "{step description}", "reason": "Tool 'k6' not available"}
  ]
}
```

Field notes:
- `setup`/`cleanup`: Include only if the scenario has Setup/Cleanup sections. Omit if absent.
- `missing_tools`: Array of tools that were required/optional but not found. Empty array if all tools available.
- `skipped_steps`: Steps not executed due to missing tools or missing env vars.
- `steps`: Only includes steps that were actually executed (not skipped).
- `method`: `"cli"` if executed via Bash, `"skill"` if executed via a fallback skill (e.g., `wicked-garden:startah:agent-browser`).
- No PASS/FAIL verdict — the consumer (e.g., QE executor) evaluates exit codes.
- `duration_ms`: Wall-clock time in milliseconds for each step.

Exit code follows the same convention: 0 (all succeeded), 1 (any non-zero exit), 2 (skips only).

**If interactive mode (default)**: Generate the markdown report.

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

### 9. JUnit XML (if --junit, interactive mode only)

If `--junit <path>` is specified and NOT in `--json` mode, write JUnit XML:

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
