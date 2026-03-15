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

### 4a. Agent Skills 2.0 Compliance

Verify agents have required Skills 2.0 frontmatter fields:

```bash
VALID_MODELS="haiku sonnet opus"
VALID_TOOLS="Read Write Edit Bash Grep Glob Skill Agent WebSearch WebFetch AskUserQuestion"

for agent in $(find "./agents" -name "*.md" 2>/dev/null); do
  name=$(basename "$agent")
  fm=$(sed -n '2,/^---$/p' "$agent" | head -n -1)

  # Check allowed-tools present
  if ! echo "$fm" | grep -q "^allowed-tools:"; then
    echo "ERROR: $name missing 'allowed-tools' in frontmatter"
  else
    # Validate tool names
    tools_line=$(echo "$fm" | grep "^allowed-tools:" | cut -d: -f2-)
    for tool in $(echo "$tools_line" | tr ',' '\n' | tr -d ' '); do
      if [[ -n "$tool" ]] && ! echo "$VALID_TOOLS" | grep -qw "$tool"; then
        echo "WARNING: $name has non-standard tool: $tool"
      fi
    done
  fi

  # Check model is valid
  model=$(echo "$fm" | grep "^model:" | awk '{print $2}')
  if [[ -n "$model" ]] && ! echo "$VALID_MODELS" | grep -qw "$model"; then
    echo "ERROR: $name has invalid model: $model"
  fi
done
```

### 4b. Agent tool-capabilities Compliance

Verify agent tool-capabilities declarations reference valid registry capability names:

```bash
VALID_CAPABILITIES=$(python3 -c "
import sys; sys.path.insert(0, 'scripts')
from _capability_registry import CAPABILITY_REGISTRY
print(' '.join(CAPABILITY_REGISTRY.keys()))
" 2>/dev/null || echo "code-search code-edit code-execution web-access project-management security-scanning error-tracking documentation version-control ci-cd subagent-dispatch data-query")

find "./agents" -name "*.md" 2>/dev/null | while IFS= read -r agent; do
  name=$(basename "$agent")
  fm=$(sed -n '2,/^---$/p' "$agent" | head -n -1)

  # Check if tool-capabilities is present
  if echo "$fm" | grep -q "^tool-capabilities:"; then
    # Extract capability names
    caps=$(echo "$fm" | sed -n '/^tool-capabilities:/,/^[^ -]/p' | grep '^ *- ' | sed 's/^ *- //')

    if [ -z "$caps" ]; then
      echo "WARNING: $name has empty tool-capabilities list"
      continue
    fi

    # Validate each capability name
    echo "$caps" | while IFS= read -r cap; do
      if [ -n "$cap" ] && ! echo "$VALID_CAPABILITIES" | grep -qw "$cap"; then
        echo "ERROR: $name declares unknown capability: $cap"
      fi
    done

    # Check for duplicates
    dup_count=$(echo "$caps" | grep -v '^$' | sort | uniq -d | wc -l | tr -d ' ')
    if [ "$dup_count" -gt 0 ]; then
      echo "WARNING: $name has duplicate tool-capabilities entries"
    fi
  fi
done
```

### 4c. Agent Description Budget (≤600 chars)

Agent descriptions are loaded for every routing decision — keep them lean.

```bash
for agent in $(find "./agents" -name "*.md" 2>/dev/null); do
  desc_chars=$(python3 -c "
import re, sys
content = open('$agent').read()
m = re.match(r'^---\n(.*?\n)---', content, re.DOTALL)
if m:
    dm = re.search(r'^description:\s*\|?\s*\n((?:[ \t]+.*\n?)+)', m.group(1), re.MULTILINE)
    print(len(dm.group(1)) if dm else 0)
else:
    print(0)
" 2>/dev/null || echo 0)
  name=$(basename "$agent")
  if [[ "$desc_chars" -gt 600 ]]; then
    echo "WARNING: $name description is $desc_chars chars (budget: 600)"
  fi
done
```

**Budget breakdown** (~400 chars healthy, 600 hard ceiling):
- ~120 chars — 1-2 sentence role summary
- ~60 chars — "Use when: ..." trigger clause
- ~220 chars — `<example>` block (Context + user + commentary)

### 5. Specialist Schema (if applicable)

```bash
if [[ -f "./.claude-plugin/specialist.json" ]]; then
  # specialist.json structure: {"plugin": "name", "specialists": [{name, role, ...}]}
  plugin_name=$(jq -r '.name' ".claude-plugin/plugin.json")
  spec_plugin=$(jq -r '.plugin // empty' "./.claude-plugin/specialist.json")
  if [[ -n "$spec_plugin" && "$plugin_name" != "$spec_plugin" ]]; then
    echo "ERROR: specialist.json .plugin does not match plugin.json name"
  fi

  valid_roles="ideation brainstorming business-strategy project-management quality-engineering devsecops engineering architecture ux product compliance data-engineering agentic-architecture research"
  jq -r '.specialists[]?.role // empty' "./.claude-plugin/specialist.json" 2>/dev/null | while read -r role; do
    if [[ -n "$role" ]] && ! echo "$valid_roles" | grep -qw "$role"; then
      echo "ERROR: Invalid specialist role: $role"
    fi
  done
fi
```

### 5b. Skill Portability Compliance

Skills tagged `portability: portable` must not contain runtime dependencies:

```bash
PROHIBITED_PATTERNS="python3|uv run|DomainStore|_domain_store|CLAUDE_PLUGIN_ROOT|Task\("

for skill in $(find "./skills" -name "SKILL.md" 2>/dev/null); do
  if grep -q "portability: portable" "$skill"; then
    name=$(dirname "$skill" | xargs basename)
    body=$(sed -n '/^---$/,/^---$/!p' "$skill" | tail -n +2)
    violations=$(echo "$body" | grep -cE "$PROHIBITED_PATTERNS" 2>/dev/null || echo 0)
    if [[ "$violations" -gt 0 ]]; then
      echo "ERROR: Portable skill $name has $violations runtime dependency references"
    fi
  fi
done
```

### 5c. Skill Invocation Control Audit

Verify `user-invocable` and `disable-model-invocation` are used appropriately:

```bash
# Count skills with invocation control
ui_false=$(grep -rl "user-invocable: false" ./skills 2>/dev/null | wc -l | tr -d ' ')
dmi_true=$(grep -rl "disable-model-invocation: true" ./skills 2>/dev/null | wc -l | tr -d ' ')
portable=$(grep -rl "portability: portable" ./skills 2>/dev/null | wc -l | tr -d ' ')

echo "Skills 2.0 Frontmatter:"
echo "  user-invocable: false — $ui_false skills (background/infrastructure)"
echo "  disable-model-invocation: true — $dmi_true skills (user-only invocation)"
echo "  portability: portable — $portable skills (cross-platform compatible)"
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

### 7. Implementation Rationalization

Skills, commands, and agents must reference implementation artifacts that actually exist.
Scan for known eliminated patterns (stale after CP removal in v1.30.0):

```bash
# Eliminated patterns — these no longer exist in the codebase
STALE_PATTERNS="StorageManager|ControlPlaneClient|_control_plane|_storage\.py|AgentBridge|CollaborationService|AgentRuntime|AuthStorage"

STALE_COUNT=0
for doc in $(find ./skills ./commands ./agents -name "*.md" 2>/dev/null); do
  # Skip generic API examples in engineering/architecture skills
  rel=$(echo "$doc" | sed 's|^\./||')
  case "$rel" in
    skills/engineering/*|skills/observability/refs/toolchain*) continue ;;
  esac
  matches=$(grep -cE "$STALE_PATTERNS" "$doc" 2>/dev/null || echo 0)
  if [[ "$matches" -gt 0 ]]; then
    echo "WARNING: $rel has $matches stale implementation references"
    STALE_COUNT=$((STALE_COUNT + matches))
  fi
done

if [[ "$STALE_COUNT" -gt 0 ]]; then
  echo "WARNING: $STALE_COUNT total stale references found — docs reference eliminated infrastructure"
  echo "  Eliminated: StorageManager, ControlPlaneClient, _storage.py, _control_plane.py"
  echo "  Current:    DomainStore (_domain_store.py), SqliteStore (_sqlite_store.py)"
fi
```

**Why this matters**: Skills that reference non-existent classes/modules mislead both Claude and users.
The current storage layer is `DomainStore` (local JSON + integration-discovery) and `SqliteStore` (direct SQLite).
Any reference to `StorageManager`, `_storage.py`, `ControlPlaneClient`, or `_control_plane.py` is stale.

**Allowed**: References to DomainStore, SqliteStore, _domain_store.py, _sqlite_store.py, _session.py, _agents.py.
**Flagged**: StorageManager, ControlPlaneClient, _control_plane, _storage.py, AgentBridge, CollaborationService, AuthStorage.

### 8. README Style Guide

Validate README against the canonical style guide (see `skills/readme-style-guide/`).
Note: sub-checks below use legacy 7x numbering for backward compatibility:

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

### 7h. README Freshness (Component Counts)

Check that README header counts match actual component counts:

```bash
readme="./README.md"

# Extract counts from README tagline
readme_commands=$(grep -oE '[0-9]+ commands' "$readme" | head -1 | grep -oE '[0-9]+')
readme_agents=$(grep -oE '[0-9]+ specialist agents' "$readme" | head -1 | grep -oE '[0-9]+')
readme_skills=$(grep -oE '[0-9]+ skills' "$readme" | head -1 | grep -oE '[0-9]+')

# Count actual components
actual_commands=$(find commands -name '*.md' -not -name '_*' 2>/dev/null | wc -l | tr -d ' ')
actual_agents=$(find agents -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
actual_skills=$(find skills -name 'SKILL.md' 2>/dev/null | wc -l | tr -d ' ')

# Compare
if [[ "$readme_commands" != "$actual_commands" ]]; then
  echo "WARNING: README says $readme_commands commands, actual is $actual_commands"
fi
if [[ "$readme_agents" != "$actual_agents" ]]; then
  echo "WARNING: README says $readme_agents agents, actual is $actual_agents"
fi
if [[ "$readme_skills" != "$actual_skills" ]]; then
  echo "WARNING: README says $readme_skills skills, actual is $actual_skills"
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
| Agent Skills 2.0 (allowed-tools, model) | ✓/✗ |
| Agent tool-capabilities compliance | ✓/✗ |
| Agent description budget (≤600 chars) | ✓/⚠ |
| Skill portability compliance | ✓/✗ |
| Skill invocation control audit | ✓/info |
| Specialist schema | ✓/✗/- |
| Capability compliance | ✓/✗ |
| Implementation rationalization | ✓/✗ |
| README style guide | ✓/✗ |
| README freshness | ✓/✗ |

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

### 9b. Storage Layer Smoke Test

Verify the storage layer (DomainStore + SqliteStore) is functional:

```bash
python3 -c "
import sys
sys.path.insert(0, 'scripts')
from _domain_store import DomainStore
ds = DomainStore('wicked-mem')
items = ds.list('memories', limit=1)
print(f'DomainStore: OK ({len(items) if items else 0} memories)')
" 2>&1 || echo "WARNING: DomainStore smoke test failed"
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

### 12. Capability Resolution Dry Run

Test the capability resolution pipeline end-to-end:

```bash
python3 -c "
import sys
sys.path.insert(0, 'scripts')
from pathlib import Path
from _capability_resolver import resolve_all_agents, discover_mcp_servers
from _agents import AgentLoader

loader = AgentLoader()
agents = loader.load_disk_agents(Path('agents'))
mcp = discover_mcp_servers()
resolutions = resolve_all_agents(agents, config=None, mcp_servers=mcp)

print(f'Resolved {len(resolutions)} agents with tool-capabilities:')
for name, tools in sorted(resolutions.items()):
    print(f'  {name}: {\", \".join(tools)}')
if not resolutions:
    print('  (no agents have tool-capabilities declared)')
" 2>&1 || echo "WARNING: Capability resolution dry run failed"
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
