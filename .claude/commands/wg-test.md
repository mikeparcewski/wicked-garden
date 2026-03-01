---
name: wg-test
description: Execute acceptance test scenarios for the wicked-garden plugin
arguments:
  - name: target
    description: "Domain name, or domain/scenario (e.g., mem or mem/decision-recall). Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Scenarios

Dev-tool wrapper that delegates to the best available testing pipeline. QE owns acceptance testing end-to-end; the scenarios domain provides standalone execution as a fallback.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → List domains with scenarios, ask user to pick
- `domain-name` → List scenarios for that domain, ask user to pick
- `domain/scenario-name` → Run that specific scenario
- `domain --all` → Run all scenarios for that domain
- `--all` → Run all scenarios across all domains
- `--issues` flag (combinable with any above) → Auto-file GitHub issues for failures
- `--batch N` → Run scenarios in batches of N in parallel (default: sequential)
- `--debug` → Write debug log capturing tool-usage traces per batch

### 2. Preflight Environment Check

Before running any scenarios, verify the plugin runtime is available:

```bash
if [ "${SKIP_PLUGIN_MARKETPLACE}" = "true" ]; then
  echo "SKIP_PLUGIN_MARKETPLACE=true is set — plugin skills will not be registered."
  echo "Scenarios WILL FAIL because slash commands like /wicked-garden:mem:store cannot resolve."
  echo "Remove this env var or set SKIP_PLUGIN_MARKETPLACE=false to enable plugin loading."
fi
```

If `SKIP_PLUGIN_MARKETPLACE=true`, warn the user and ask whether to continue (results will be unreliable) or abort. Use AskUserQuestion with options: "Abort — fix environment first" and "Continue anyway (expect failures)".

Also check whether the control plane is running — many scenarios depend on it for storage, memory, and kanban operations:

```bash
# Probe control plane health
CP_HEALTH=$(curl -s --connect-timeout 2 http://localhost:18889/health 2>/dev/null)
if echo "$CP_HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null | grep -qE "^(ok|healthy)$"; then
  CP_VERSION=$(echo "$CP_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','unknown'))" 2>/dev/null)
  echo "CP_STATUS=healthy (v${CP_VERSION})"
else
  echo "CP_STATUS=unreachable"
fi
```

If the control plane is unreachable:

1. **Attempt auto-start** (if `~/Projects/wicked-viewer` exists):
   ```bash
   VIEWER_PATH="${HOME}/Projects/wicked-viewer"
   if [ -d "${VIEWER_PATH}" ] && [ -f "${VIEWER_PATH}/package.json" ]; then
     echo "Starting control plane from ${VIEWER_PATH}..."
     cd "${VIEWER_PATH}" && PORT=18889 pnpm run dev &
     # Poll for up to 8 seconds
     for i in $(seq 1 16); do
       sleep 0.5
       if curl -s --connect-timeout 1 http://localhost:18889/health 2>/dev/null | python3 -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('status') in ('ok','healthy') else 1)" 2>/dev/null; then
         echo "CP_STATUS=healthy (auto-started)"
         break
       fi
     done
   fi
   ```

2. **If still unreachable after auto-start attempt**, warn the user and ask whether to continue:
   - Scenarios that use `/wicked-garden:mem:store`, `/wicked-garden:kanban:*`, or crew workflows will have **degraded results** (silent failures, empty recalls, local-only storage)
   - Use AskUserQuestion with options: "Continue without CP (expect degraded results)" and "Abort — start CP first (`cd ~/Projects/wicked-viewer && PORT=18889 pnpm run dev`)"

Also check whether the plugin runtime actually loaded:

```bash
echo "CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-NOT_SET}"
```

If `CLAUDE_PLUGIN_ROOT` is not set, the plugin commands (like `/wicked-garden:qe:acceptance` and `/wicked-garden:scenarios:run`) are NOT registered as invokable skills — even if the command files exist on disk. This is normal when running in environments where the plugin marketplace isn't active (e.g., Claude Code on the web). The inline execution fallback in Step 5 handles this case.

### 3. Scenario Discovery

If the user didn't specify a full `domain/scenario` path, discover available scenarios:

```bash
# Find domains with scenarios
for domain_dir in scenarios/*/; do
  if [ -d "${domain_dir}" ]; then
    domain_name=$(basename "$domain_dir")
    scenario_count=$(find "${domain_dir}" -name "*.md" ! -name "README.md" | wc -l | tr -d ' ')
    if [ "$scenario_count" -gt 0 ]; then
      echo "$domain_name: $scenario_count scenarios"
    fi
  fi
done
```

Use AskUserQuestion to let user select domain and/or scenario.

### 4. Detect Available Pipeline

Determine which execution path to use. There are three tiers — check in order:

**Tier 1 — Plugin skills invokable (best):**

The plugin is loaded and commands are registered as skills. This is the case when `CLAUDE_PLUGIN_ROOT` is set.

```bash
# Check if plugin runtime is active
if [ -n "${CLAUDE_PLUGIN_ROOT}" ]; then
  echo "PLUGIN_LOADED=true"
  ls "${CLAUDE_PLUGIN_ROOT}/commands/qe/acceptance.md" 2>/dev/null && echo "QE_SKILL=true"
  ls "${CLAUDE_PLUGIN_ROOT}/commands/scenarios/run.md" 2>/dev/null && echo "SCENARIOS_SKILL=true"
else
  echo "PLUGIN_LOADED=false"
fi
```

**Tier 2 — Command files exist but plugin not loaded (inline fallback):**

The command markdown files exist on disk but aren't registered as invokable skills. Scenarios can still be executed inline by reading each scenario file, parsing its steps, and running them directly via Bash.

```bash
# Check for command files on disk (fallback detection)
ls commands/qe/acceptance.md 2>/dev/null && echo "QE_FILE=true"
ls commands/scenarios/run.md 2>/dev/null && echo "SCENARIOS_FILE=true"
```

**Tier 3 — Nothing available (error):**

Neither command files nor plugin skills exist.

### 5. Delegate to Pipeline

Use the tier detected in Step 4 to select the execution path. Try Tier 1 first; if the Skill call fails with "Unknown skill", fall through to Tier 2.

---

**Tier 1 — Skill delegation (plugin loaded OR skills registered):**

Delegate to `/wicked-garden:qe:acceptance` (primary) or `/wicked-garden:scenarios:run` (fallback) via the Skill tool.

**Primary — QE acceptance (full Writer → Executor → Reviewer pipeline):**

Single scenario:
```
Skill(
  skill="wicked-garden:qe:acceptance",
  args="scenarios/${domain}/${scenario_file}"
)
```

All scenarios for a domain (`--all`):
```
Skill(
  skill="wicked-garden:qe:acceptance",
  args="scenarios/${domain}/ --all"
)
```

**Fallback — scenarios:run (standalone, exit code PASS/FAIL, no evidence protocol):**

Single scenario:
```
Skill(
  skill="wicked-garden:scenarios:run",
  args="scenarios/${domain}/${scenario_file}"
)
```

All scenarios (`--all`) — run sequentially; the glob already yields the full relative path — do NOT re-prefix:
```
for each scenario_file in scenarios/${domain}/*.md (excluding README.md):
  Skill(
    skill="wicked-garden:scenarios:run",
    args="${scenario_file}"
  )
```

**If Skill calls fail with "Unknown skill"**: The plugin commands exist on disk but aren't registered in the current runtime. Fall through to Tier 2.

---

**Tier 2 — Inline execution (command files exist but skills not invokable):**

When plugin skills can't be invoked (common in web environments or when `CLAUDE_PLUGIN_ROOT` isn't set), execute scenarios directly by reading each scenario file and running its steps inline.

For each scenario file:

1. **Read the scenario markdown** using the Read tool
2. **Parse YAML frontmatter** — extract `name`, `description`, `tools.required`, `tools.optional`, `env`, `timeout`
3. **Run CLI discovery** (if the script exists):
   ```bash
   python3 scripts/scenarios/cli_discovery.py {space-separated tools from required + optional}
   ```
   If the discovery script doesn't exist, check tools manually with `which {tool}`.
4. **Execute Setup** — find the `## Setup` section, extract its fenced code block, run via Bash
5. **Execute Steps** — for each `### Step N:` section:
   - Extract the fenced code block
   - If the code block contains slash commands (e.g., `/wicked-garden:agentic:review ...`), invoke them via the Skill tool instead of Bash
   - If CLI not available, record as **SKIPPED**
   - Otherwise execute via Bash with the scenario's timeout (default 120s)
   - Capture: stdout, stderr, exit code, duration
   - Exit code 0 → **PASS**, non-zero → **FAIL**, CLI missing → **SKIPPED**
6. **Execute Cleanup** — if a `## Cleanup` section exists, run its code block via Bash
7. **Aggregate** — All PASS → **PASS** (0), Any FAIL → **FAIL** (1), No FAILs but SKIPs → **PARTIAL** (2)
8. **Report** — produce the markdown results table:

```markdown
## Scenario Results: {name}

**Status**: {PASS|FAIL|PARTIAL}
**Duration**: {total seconds}s
**Steps**: {pass_count} passed, {fail_count} failed, {skip_count} skipped

| Step | Status | Duration | Details |
|------|--------|----------|---------|
| {step name} | PASS | 0.5s | |
| {step name} | FAIL | 2.0s | Exit code 1: {stderr snippet} |
| {step name} | SKIPPED | - | Tool not installed |
```

---

**Tier 3 — Nothing available (error):**

Neither command files nor plugin skills exist:
```
Error: No testing pipeline available.
The qe and scenarios domains must be present to enable testing.
  - qe: Full acceptance pipeline with evidence protocol and independent review
  - scenarios: Standalone E2E execution with PASS/FAIL verdicts
```

### 5.5 Batch Execution (if --batch)

When `--batch N` is specified with `--all`:

1. Discover all scenario files for the target domain (or all domains)
2. Split into batches of N scenarios each
3. For each batch:
   a. Dispatch N parallel Task() calls, each running the scenario via the detected pipeline
   b. Collect results from all N tasks
   c. Write batch debug log to `~/.something-wicked/wicked-garden/batch-runs/{run-id}/batch-{n}.md`
4. After all batches complete, produce a run summary

**Batch dispatch (QE path):**
```
# Launch up to N scenarios in parallel
for each scenario in current_batch:
  Task(
    subagent_type="wicked-garden:qe:acceptance-test-executor",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

**Batch dispatch (scenarios-only fallback):**
```
for each scenario in current_batch:
  Task(
    subagent_type="wicked-garden:scenarios:scenario-executor",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

> **Note**: Use `scenario-executor` (not `scenario-runner`) — it has Skill tool access and can invoke slash commands. Fall back to `scenario-runner` only if `scenario-executor` is unavailable.

**Debug log per batch** (if --debug):
Each batch debug log captures:
- Scenario names and paths
- Pass/fail/skip per scenario
- Duration per scenario
- Which tools/skills/commands were invoked (from Task output)
- Any silent failures detected

**Run summary** written to `~/.something-wicked/wicked-garden/batch-runs/{run-id}/summary.json`:
```json
{
  "run_id": "unique-id",
  "total": 102,
  "passed": 95,
  "failed": 5,
  "errors": 2,
  "skipped": 0,
  "duration_ms": 180000,
  "batches": 13,
  "batch_size": 8,
  "failed_scenarios": ["domain/scenario-name", ...]
}
```

### 6. Issue Filing (if --issues)

After testing completes with failures:

**QE path (primary):** QE acceptance produces structured verdicts (`task_verdicts`, `acceptance_criteria_verdicts`, `failure_analysis`). Invoke report:
```
Skill(
  skill="wicked-garden:scenarios:report",
  args="--auto"
)
```

**Scenarios-only fallback path:** `/wicked-garden:scenarios:run` produces simple exit codes (0/1/2) and markdown output, NOT structured verdicts. The `report` command requires structured fields, so issue filing is **not available** in this degradation path. Instead, display:
```
Failures detected (exit code 1). Automatic issue filing requires the qe domain
for structured test verdicts. File manually: gh issue create --title "test(<domain>): ..." --label bug
```

**Neither available:** No testing occurred, no issue filing.

## Examples

```bash
# List domains with scenarios
/wg-test

# List scenarios for mem domain
/wg-test mem

# Run specific scenario
/wg-test mem/decision-recall

# Run all crew scenarios
/wg-test crew --all

# Run all scenarios and auto-file issues for failures
/wg-test crew --all --issues

# Run all scenarios in batches of 8 with debug logging
/wg-test crew --all --batch 8

# Run all scenarios across all domains in parallel batches
/wg-test --all --batch 8 --debug
```

## Architecture Note

This command (`/wg-test`) is a dev-tool wrapper that adds only:
- Scenario discovery across `scenarios/{domain}/`
- Preflight `SKIP_PLUGIN_MARKETPLACE` check
- Pipeline detection and degradation fallback

Testing intelligence is owned by:
- **qe domain** — acceptance pipeline (Writer/Executor/Reviewer), evidence protocol, assertions
- **scenarios domain** — E2E CLI execution (`/wicked-garden:scenarios:run`), issue filing (`/wicked-garden:scenarios:report`)
