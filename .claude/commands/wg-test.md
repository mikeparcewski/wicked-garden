---
name: wg-test
description: Execute acceptance test scenarios for the wicked-garden plugin
arguments:
  - name: target
    description: "Domain name, domain/scenario, --skills, or --skills domain. Append --issues to auto-file GitHub issues for failures."
    required: false
---

# Test Scenarios

Dev-tool wrapper that delegates to the best available testing pipeline. QE owns acceptance testing end-to-end; the qe domain (E2E scenarios) provides standalone execution as a fallback. The `--skills` mode validates plugin skills against standards using the skill-creator skill.

## Process

### 1. Parse Arguments

Parse `$ARGUMENTS` to determine what to test:
- No args → Run skill validation (Step 7) THEN list domains with scenarios and ask user to pick
- `domain-name` → Run skill validation for that domain (Step 7), then list scenarios for that domain and ask user to pick
- `domain/scenario-name` → Run skill validation for that domain (Step 7), then run that specific scenario
- `domain --all` → Run skill validation for that domain (Step 7), then run all scenarios for that domain
- `--all` → Run skill validation for all domains (Step 7), then run all scenarios across all domains
- `--skills-only` → Run ONLY skill validation (Step 7), skip scenarios entirely
- `--skills-only domain-name` → Run ONLY skill validation for a specific domain
- `--no-skills` → Skip skill validation, run scenarios only (legacy behavior)
- `--fix` → During skill validation, auto-fix issues found
- `--issues` flag (combinable with any above) → Auto-file GitHub issues for failures
- `--batch N` → Run scenarios in batches of N in parallel (default: sequential)
- `--debug` → Write debug log capturing tool-usage traces per batch

**Execution order**: Skill validation (Step 7) always runs first unless `--no-skills` is specified. Scenario execution (Steps 2-6) runs after, unless `--skills-only` is specified.

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

Also check whether the plugin runtime actually loaded:

```bash
echo "CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-NOT_SET}"
```

If `CLAUDE_PLUGIN_ROOT` is not set, the plugin commands (like `/wicked-testing:execution`) are NOT registered as invokable skills — even if the command files exist on disk. This is normal when running in environments where the plugin marketplace isn't active (e.g., Claude Code on the web). The inline execution fallback in Step 5 handles this case.

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

Delegate to `/wicked-testing:execution` (primary) via the Skill tool.

**Primary — wicked-testing execution (full pipeline):**

Single scenario:
```
Skill(
  skill="wicked-testing:execution",
  args="scenarios/${domain}/${scenario_file}"
)
```

All scenarios for a domain (`--all`):
```
Skill(
  skill="wicked-testing:execution",
  args="scenarios/${domain}/ --all"
)
```

All scenarios (`--all`) — run sequentially; the glob already yields the full relative path — do NOT re-prefix:
```
for each scenario_file in scenarios/${domain}/*.md (excluding README.md):
  Skill(
    skill="wicked-testing:execution",
    args="${scenario_file}"
  )
```

**If Skill calls fail with "Unknown skill"**: The plugin commands exist on disk but aren't registered in the current runtime. Fall through to Tier 2.

---

**Tier 2 — Inline execution (command files exist but skills not invokable):**

When plugin skills can't be invoked (common in web environments or when `CLAUDE_PLUGIN_ROOT` isn't set), execute scenarios directly by reading each scenario file and running its steps inline.

For each scenario file:

1. **Read the scenario markdown** using the Read tool
2. **Parse YAML frontmatter** — extract `name`, `description`, `execution`, `tools.required`, `tools.optional`, `env`, `timeout`
3. **Honor `execution: manual`** — if frontmatter declares `execution: manual`, the scenario expects an interactive Claude runtime to dispatch its slash commands. Do NOT treat this as a SKIP — emit verdict **MANUAL-ONLY** and continue. This separates "needs human or live LLM dispatcher" from "tool missing" so the summary table tracks true automation coverage.
4. **Run CLI discovery** — check tools manually with `which {tool}` for each required/optional tool.
5. **Execute Setup** — find the `## Setup` section, extract its fenced code block, run via Bash
6. **Execute Steps** — for each `### Step N:` section:
   - Extract the fenced code block
   - If the code block contains slash commands (e.g., `/wicked-garden:agentic:review ...`), invoke them via the Skill tool instead of Bash
   - If CLI not available, record as **SKIPPED**
   - Otherwise execute via Bash with the scenario's timeout (default 120s)
   - Capture: stdout, stderr, exit code, duration
   - Exit code 0 → **PASS**, non-zero → **FAIL**, CLI missing → **SKIPPED**
7. **Execute Cleanup** — if a `## Cleanup` section exists, run its code block via Bash
8. **Aggregate** — All PASS → **PASS** (0), Any FAIL → **FAIL** (1), No FAILs but SKIPs → **PARTIAL** (2). Scenarios with `execution: manual` skip aggregation entirely and emit **MANUAL-ONLY** (3).
9. **Report** — produce the markdown results table:

```markdown
## Scenario Results: {name}

**Status**: {PASS|FAIL|PARTIAL|MANUAL-ONLY}
**Duration**: {total seconds}s
**Steps**: {pass_count} passed, {fail_count} failed, {skip_count} skipped

| Step | Status | Duration | Details |
|------|--------|----------|---------|
| {step name} | PASS | 0.5s | |
| {step name} | FAIL | 2.0s | Exit code 1: {stderr snippet} |
| {step name} | SKIPPED | - | Tool not installed |
| {step name} | MANUAL-ONLY | - | Requires Claude runtime to dispatch slash commands |
```

---

**Tier 3 — Nothing available (error):**

Neither command files nor plugin skills exist:
```
Error: No testing pipeline available.
The qe and qe domain (E2E scenarios)s must be present to enable testing.
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

**Batch dispatch (primary path):**
```
# Launch up to N scenarios in parallel
for each scenario in current_batch:
  Task(
    subagent_type="wicked-garden:crew:reviewer",
    prompt="Execute scenario: {scenario_path}. Return structured results."
  )
```

**Batch dispatch (scenarios-only fallback):**
```
for each scenario in current_batch:
  Task(
    subagent_type="wicked-garden:crew:implementer",
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

**Primary path:** wicked-testing execution produces structured verdicts (`task_verdicts`, `acceptance_criteria_verdicts`, `failure_analysis`). Invoke report:
```
Skill(
  skill="wicked-testing:insight",
  args="--auto"
)
```

**Inline fallback path:** Inline execution produces simple exit codes (0/1/2) and markdown output, NOT structured verdicts. The `insight` command requires structured fields, so issue filing is **not available** in this degradation path. Instead, display:
```
Failures detected (exit code 1). Automatic issue filing requires wicked-testing
for structured test verdicts. File manually: gh issue create --title "test(<domain>): ..." --label bug
```

**Neither available:** No testing occurred, no issue filing.

### 7. Skill Validation (if --skills)

When `--skills` is specified, validate plugin skills against standards using the `skill-creator:skill-creator` skill. This bypasses the scenario pipeline entirely.

#### 7a. Discover Skills

```bash
# Find all skills, optionally filtered by domain
if [ -n "${target_domain}" ]; then
  skill_dirs=$(find "skills/${target_domain}" -name "SKILL.md" -type f 2>/dev/null)
else
  skill_dirs=$(find "skills" -name "SKILL.md" -type f 2>/dev/null)
fi

echo "Found $(echo "$skill_dirs" | wc -l | tr -d ' ') skills to validate"
```

If no skills found, report error and exit.

#### 7b. Structural Pre-Check

Before invoking skill-creator, run fast structural checks on each skill (same as wg-check Steps 3 and 6):

For each SKILL.md:
1. **Line count** — MUST be ≤200 lines
2. **YAML frontmatter** — MUST have `name` and `description` fields
3. **Refs directory** — If `refs/` exists, each file MUST be ≤300 lines
4. **Hardcoded tool references** — Flag any hardcoded external tool names (Sentry, Datadog, Jira, etc.)
5. **Description quality** — `description` field MUST include trigger phrases (lines starting with "Use when")

```bash
for skill_file in ${skill_dirs}; do
  skill_dir=$(dirname "$skill_file")
  skill_name=$(basename "$skill_dir")
  domain=$(basename "$(dirname "$skill_dir")")

  # Line count
  lines=$(wc -l < "$skill_file")
  if [ "$lines" -gt 200 ]; then
    echo "FAIL: ${domain}/${skill_name} — ${lines} lines (max 200)"
  fi

  # YAML frontmatter check
  if ! head -1 "$skill_file" | grep -q "^---"; then
    echo "FAIL: ${domain}/${skill_name} — missing YAML frontmatter"
  fi

  # Check required frontmatter fields
  frontmatter=$(sed -n '/^---$/,/^---$/p' "$skill_file")
  if ! echo "$frontmatter" | grep -q "^name:"; then
    echo "FAIL: ${domain}/${skill_name} — missing 'name' in frontmatter"
  fi
  if ! echo "$frontmatter" | grep -q "^description:"; then
    echo "FAIL: ${domain}/${skill_name} — missing 'description' in frontmatter"
  fi

  # Trigger phrases in description
  if ! echo "$frontmatter" | grep -qi "use when"; then
    echo "WARN: ${domain}/${skill_name} — description missing trigger phrases ('Use when...')"
  fi

  # Refs line counts
  if [ -d "${skill_dir}/refs" ]; then
    for ref_file in "${skill_dir}"/refs/*.md; do
      if [ -f "$ref_file" ]; then
        ref_lines=$(wc -l < "$ref_file")
        if [ "$ref_lines" -gt 300 ]; then
          ref_name=$(basename "$ref_file")
          echo "FAIL: ${domain}/${skill_name}/refs/${ref_name} — ${ref_lines} lines (max 300)"
        fi
      fi
    done
  fi
done
```

Record structural results. Skills that fail structural checks are still passed to skill-creator for quality review — structural failures don't block the quality assessment.

#### 7c. Skill-Creator Quality Review

Dispatch skill validation to `skill-creator:skill-creator` via the Skill tool. To avoid overwhelming context, batch skills by domain and run one review per domain.

For each domain with skills:

```
Skill(
  skill="skill-creator:skill-creator",
  args="Review and validate the following skills in the '${domain}' domain of the wicked-garden plugin for quality, standards compliance, and completeness. Do NOT create or modify any files — analysis only.

## Standards to Check

1. **Progressive Disclosure**: SKILL.md is a concise entry point (≤200 lines). Detailed content lives in refs/ (≤300 lines each). SKILL.md should link to refs/ when they exist.
2. **Frontmatter Quality**: name matches directory name, description is clear and includes trigger phrases ('Use when...') so the skill loader can match user intent.
3. **Content Structure**: Has clear sections — what the skill does, when to use it, key concepts, integration points.
4. **Actionability**: Provides concrete guidance, not just abstract principles. Includes examples, templates, or decision frameworks.
5. **Cross-References**: Links to related skills/commands use the correct namespace format (wicked-garden:{domain}:{name}).
6. **No Duplication**: Content doesn't duplicate what's in other skills or in CLAUDE.md.
7. **Refs Quality**: If refs/ exist, they provide depth without redundancy. Each ref file has a focused topic.

## Skills to Review

${list each skill path in this domain}

## Output Format

For each skill, provide:
- **Status**: PASS / WARN / FAIL
- **Issues**: List of specific problems found (if any)
- **Suggestions**: Concrete improvements (if any)

End with a domain summary: X passed, Y warnings, Z failures."
)
```

If `--fix` flag is present, change the prompt to include: "For any issues found, also generate the corrected content. Apply fixes directly to the skill files."

#### 7d. Aggregate Results

After all domains are reviewed, produce a summary report:

```markdown
## Skill Validation Results

**Mode**: ${--fix ? "Validate + Fix" : "Validate Only"}
**Scope**: ${target_domain || "All domains"}
**Skills Checked**: ${total_count}

### Structural Checks

| Domain | Skill | Lines | Frontmatter | Triggers | Refs | Status |
|--------|-------|-------|-------------|----------|------|--------|
| ${domain} | ${skill_name} | ${lines}/200 | OK/FAIL | OK/WARN | OK/FAIL/- | PASS/FAIL |

### Quality Review (via skill-creator)

| Domain | Skill | Quality | Issues | Suggestions |
|--------|-------|---------|--------|-------------|
| ${domain} | ${skill_name} | PASS/WARN/FAIL | ${count} | ${count} |

### Summary

- **Structural**: ${pass_count} passed, ${warn_count} warnings, ${fail_count} failures
- **Quality**: ${pass_count} passed, ${warn_count} warnings, ${fail_count} failures
- **Overall**: ${PASS|WARN|FAIL}

${if failures}
### Required Fixes

${numbered list of all FAIL items with specific fix instructions}
${endif}

${if warnings}
### Recommended Improvements

${numbered list of all WARN items with improvement suggestions}
${endif}
```

#### 7e. Issue Filing (if --issues with --skills)

If `--issues` is specified alongside `--skills` and there are failures:

For each FAIL result, file a GitHub issue:
```bash
gh issue create \
  --title "skill(${domain}/${skill_name}): ${brief description of failure}" \
  --label "bug,skills" \
  --body "${detailed failure description with fix instructions}"
```

Group related failures into a single issue per skill (not per check).

## Examples

```bash
# Validate all skills, then list domains with scenarios
/wg-test

# Validate engineering skills, then list its scenarios
/wg-test engineering

# Validate mem skills, then run specific scenario
/wg-test mem/decision-recall

# Validate crew skills, then run all crew scenarios
/wg-test crew --all

# Full run: validate all skills + all scenarios + file issues
/wg-test --all --issues

# Skills validation only (no scenarios)
/wg-test --skills-only

# Skills validation for one domain only
/wg-test --skills-only engineering

# Skills validation with auto-fix
/wg-test --skills-only --fix

# Scenarios only, skip skill validation (legacy behavior)
/wg-test crew --all --no-skills

# Scenarios in parallel batches with debug logging
/wg-test --all --batch 8 --debug --no-skills
```

## Architecture Note

This command (`/wg-test`) is a dev-tool wrapper that adds only:
- Scenario discovery across `scenarios/{domain}/`
- Skill validation via `skill-creator:skill-creator` (--skills mode)
- Preflight `SKIP_PLUGIN_MARKETPLACE` check
- Pipeline detection and degradation fallback

Testing intelligence is owned by:
- **wicked-testing plugin** — execution pipeline, evidence protocol, assertions, issue filing
- **skill-creator** — skill quality assessment, standards validation, and improvement suggestions
