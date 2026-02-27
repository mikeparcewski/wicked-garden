---
description: Check plugin quality (structural + optional full assessment)
argument-hint: [--full]
---

Check the wicked-garden plugin quality. Fast structural checks by default, full marketplace readiness with --full.

## Arguments

Parse: $ARGUMENTS

- **--full**: Run comprehensive assessment including product value evaluation

The check always targets the repo root (the single unified plugin). No path argument needed.

## Quick Check (Default)

Fast structural validation suitable for development iteration and CI.

> **Note**: Bash snippets below use `{path}` as a template placeholder. Replace with the actual component path.

### 1. Plugin Structure

```bash
# Validate plugin.json exists and is valid
if [[ ! -f ".claude-plugin/plugin.json" ]]; then
  echo "ERROR: Missing .claude-plugin/plugin.json"
fi

# Validate version is semver
version=$(jq -r '.version' ".claude-plugin/plugin.json")
if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: Invalid semver version: $version"
fi

if ! python3 -m json.tool ".claude-plugin/plugin.json" > /dev/null 2>&1; then
  echo "ERROR: Invalid JSON in plugin.json"
fi
```

### 2. JSON Validity

```bash
for json_file in $(find "." -name "*.json" 2>/dev/null); do
  if ! python3 -m json.tool "$json_file" > /dev/null 2>&1; then
    echo "ERROR: Invalid JSON: $json_file"
  fi
done
```

### 3. Skill Line Counts

Skills MUST be ≤200 lines:

```bash
for skill in $(find "./skills" -name "SKILL.md" 2>/dev/null); do
  lines=$(wc -l < "$skill")
  name=$(dirname "$skill" | xargs basename)
  if [[ "$lines" -gt 200 ]]; then
    echo "ERROR: $name is $lines lines (max 200)"
  else
    echo "OK: $name ($lines lines)"
  fi
done
```

### 4. Agent Frontmatter

```bash
for agent in $(find "./agents" -name "*.md" 2>/dev/null); do
  name=$(basename "$agent")
  if ! grep -q "^description:" "$agent"; then
    echo "WARNING: $name missing 'description' in frontmatter"
  fi
done
```

### 5. Specialist Schema (if applicable)

```bash
if [[ -f "./.claude-plugin/specialist.json" ]]; then
  plugin_name=$(jq -r '.name' ".claude-plugin/plugin.json")
  specialist_name=$(jq -r '.specialist.name' "./.claude-plugin/specialist.json")
  if [[ "$plugin_name" != "$specialist_name" ]]; then
    echo "ERROR: specialist.name does not match plugin.json name"
  fi

  role=$(jq -r '.specialist.role' "./.claude-plugin/specialist.json")
  valid_roles="ideation business-strategy project-management quality-engineering devsecops engineering architecture ux product compliance data-engineering research"
  if ! echo "$valid_roles" | grep -qw "$role"; then
    echo "ERROR: Invalid specialist role: $role"
  fi
fi
```

### 6. Capability-Based Discovery Compliance

Skills should discover integrations by capability, not hardcoded tool names.

```bash
DISCOVERY_PATTERNS="check for (sentry|datadog|zendesk|jira|amplitude|aws|azure)|use (sentry|datadog|zendesk|jira|amplitude|aws|azure)"

for skill in $(find "./skills" -name "SKILL.md" 2>/dev/null); do
  if grep -iE "$DISCOVERY_PATTERNS" "$skill" > /dev/null; then
    echo "WARNING: $(basename $(dirname $skill)) may have hardcoded tool discovery"
  fi
done
```

**Allowed**: wicked-* references, capability names, example output data
**Flagged**: Discovery instructions naming specific external tools

### 7. README Style Guide

Validate README against the canonical style guide (see `skills/startah/readme-style-guide/`):

```bash
readme="./README.md"

# 7a. README exists
if [[ ! -f "$readme" ]]; then
  echo "ERROR: Missing README.md"
fi

# 7b. Has tagline (first non-heading, non-empty line after h1)
tagline=$(awk '/^# /{found=1; next} found && /^[^#|`>]/ && NF{print; exit}' "$readme")
if [[ -z "$tagline" ]]; then
  echo "ERROR: No tagline after h1 heading"
fi

# 7c. Has Quick Start section
if ! grep -q "## Quick Start" "$readme"; then
  echo "ERROR: Missing ## Quick Start section"
fi

# 7d. Has Commands section
if ! grep -q "## Commands" "$readme"; then
  echo "ERROR: Missing ## Commands section"
fi

# 7e. Integration table has "Without It" column
if ! grep -q "## Integration" "$readme"; then
  echo "ERROR: Missing ## Integration section"
elif ! grep -q "Without It" "$readme"; then
  echo "ERROR: Integration table missing 'Without It' column"
fi

# 7f. Has at least one code example
if ! grep -q '```' "$readme"; then
  echo "WARNING: No code examples in README"
fi

# 7g. No unresolved template placeholders
if grep -E '\{(path|verb|source)\}' "$readme" | grep -v '<!--' > /dev/null 2>&1; then
  echo "WARNING: Unresolved template placeholders found"
fi
```

### Quick Check Output

```markdown
## Quick Check: wicked-garden

| Check | Status |
|-------|--------|
| plugin.json | ✓/✗ |
| Version (semver) | ✓/✗ |
| JSON validity | ✓/✗ |
| Skills ≤200 lines | ✓/✗ |
| Agent frontmatter | ✓/✗ |
| Specialist schema | ✓/✗/- |
| Capability compliance | ✓/✗ |
| README style guide | ✓/✗ |

**Result**: PASS / FAIL

[If PASS] Run `/wg-check --full` for marketplace readiness assessment.
[If FAIL] Fix errors above before proceeding.
```

---

## Full Assessment (--full flag)

Comprehensive marketplace readiness check. Runs quick check first, then adds:

### 8. Official Validation

Invoke the `plugin-dev:plugin-validator` agent via Task tool:

```
subagent_type: plugin-dev:plugin-validator
prompt: "Validate the plugin at . for structure, configuration, and compliance."
```

### 9. Skill Quality Review

Invoke the `plugin-dev:skill-reviewer` agent via Task tool:

```
subagent_type: plugin-dev:skill-reviewer
prompt: "Review the skills in . for quality and best practices."
```

### 10. Graceful Degradation

Check that plugin works standalone with optional enhancements:

```bash
# Check README documents integration behavior
grep -A 10 "## Integration" "./README.md"

# Look for graceful degradation patterns in scripts
grep -r "try:" "./scripts/" 2>/dev/null | head -3
grep -r "except" "./scripts/" 2>/dev/null | head -3
```

### 11. Product Value Assessment

Evaluate (read README and understand the component):

- **Problem Clarity**: Is it obvious what this solves?
- **Ease of Use**: Can someone start quickly?
- **Differentiation**: Does something similar exist?
- **Honest Take**: Would you actually install this?

### Full Assessment Output

```markdown
## Full Assessment: {component-name}

### Structure: PASS/FAIL
[Quick check results]

### Validation: PASS/FAIL
[plugin-dev:plugin-validator output]

### Skill Review: PASS/N/A
[plugin-dev:skill-reviewer output]

### Context Efficiency: PASS/WARN/FAIL

| Skill | Lines | Status |
|-------|-------|--------|
| name | 150 | ✓ |

### Graceful Degradation: PASS/WARN/FAIL

- **Standalone**: Yes/No
- **Integration docs**: Present/Missing

### Product Value:

- **Problem Clarity**: Clear/Vague
- **Ease of Use**: Easy/Moderate/Complex
- **Differentiation**: Unique/Overlap/Duplicate
- **Honest Take**: [Assessment]

---

## Verdict: READY / NEEDS WORK

[If NEEDS WORK, specific items to fix]
```

---

## Exit Behavior

For CI integration:
- **PASS**: All checks passed, suggest next step
- **FAIL**: Errors found, list specific fixes needed
- **WARN**: Warnings only (does not block release)

Collect all errors before reporting (don't fail-fast) to give complete feedback.

---

## Migration Notes

This command replaces:
- `/wg-validate` → `/wg-check` (quick structural checks)
- `/wg-lint` → `/wg-check` (line counts + skill review in --full)
- `/wg-score` → `/wg-check --full` (complete assessment)
