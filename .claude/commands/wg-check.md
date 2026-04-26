---
description: Check plugin quality (structural + optional full assessment)
argument-hint: [--full]
---

Check the wicked-garden plugin quality. Fast structural checks by default, full marketplace readiness with --full.

## Arguments

Parse: $ARGUMENTS

- **--full**: Run comprehensive assessment including product value evaluation
- **--agents**: Run only the agent trigger frequency analysis (Section 10) in detail

The check always targets the repo root (the single unified plugin). No path argument needed.

If `--agents` is passed, skip all other sections and run only Section 10 (Agent Trigger Analysis) with detailed output.

## Quick Check (Default)

Fast structural validation suitable for development iteration and CI.

> **Note**: Bash snippets below use `{path}` as a template placeholder. Replace with the actual component path.

### 1. Plugin Structure

```bash
# Validate plugin.json exists and is valid
if [[ ! -f ".claude-plugin/plugin.json" ]]; then
  echo "ERROR: Missing .claude-plugin/plugin.json"
fi

# Validate version is semver (permits optional pre-release suffix like -beta.1)
version=$(jq -r '.version' ".claude-plugin/plugin.json")
if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]]; then
  echo "ERROR: Invalid semver version: $version"
fi

if ! python3 -m json.tool ".claude-plugin/plugin.json" > /dev/null 2>&1; then
  echo "ERROR: Invalid JSON in plugin.json"
fi

# Validate wicked_testing_version field exists and is a valid semver range
python3 -c "
import json, re, sys
data = json.load(open('.claude-plugin/plugin.json'))
field = data.get('wicked_testing_version')
if field is None:
    print('ERROR: plugin.json missing required field: wicked_testing_version (expected a semver range string, e.g. \"^0.2.0\")')
    sys.exit(1)
if not isinstance(field, str):
    print(f'ERROR: plugin.json wicked_testing_version must be a string, got {type(field).__name__}')
    sys.exit(1)
# Accept caret, tilde, exact, X-ranges, comparison operators, hyphen ranges, and logical-or (||)
semver_range = re.compile(
    r'^'
    r'(\|\||\s*&&\s*)?'  # allow combining operators
    r'(\s*'
    r'([~^]?[0-9*x]+(\.[0-9*x]+){0,2}(-[A-Za-z0-9.-]+)?(\+[A-Za-z0-9.-]+)?'  # caret/tilde/exact/X-range
    r'|[<>]=?\s*[0-9]+(\.[0-9]+){0,2}(-[A-Za-z0-9.-]+)?'  # comparison range
    r'|\*'  # wildcard any
    r')'
    r'\s*(\|\|\s*[~^]?[0-9*x]+(\.[0-9*x]+){0,2}(-[A-Za-z0-9.-]+)?)*'  # or-clauses
    r')+\$'
)
if not semver_range.match(field.strip()):
    print(f'ERROR: plugin.json wicked_testing_version \"{field}\" is not a valid semver range (accepted forms: ^1.0.0, ~1.2, 1.x, >=1.0.0, 1.0.0 - 2.0.0, *)')
    sys.exit(1)
print(f'OK: wicked_testing_version = \"{field}\"')
" 2>/dev/null || python -c "
import json, re, sys
data = json.load(open('.claude-plugin/plugin.json'))
field = data.get('wicked_testing_version')
if field is None:
    print('ERROR: plugin.json missing required field: wicked_testing_version (expected a semver range string, e.g. \"^0.2.0\")')
    sys.exit(1)
if not isinstance(field, str):
    print('ERROR: plugin.json wicked_testing_version must be a string')
    sys.exit(1)
semver_range = re.compile(r'^[~^]?[0-9*xX]+(\.[0-9*xX]+){0,2}(-[A-Za-z0-9.-]+)?(\+[A-Za-z0-9.-]+)?(\s*\|\|\s*[~^]?[0-9*xX]+(\.[0-9*xX]+){0,2}(-[A-Za-z0-9.-]+)?)*\$|^[<>]=?\s*[0-9]+(\.[0-9]+){0,2}(-[A-Za-z0-9.-]+)?(\s*\|\|\s*[<>]=?\s*[0-9]+(\.[0-9]+){0,2}(-[A-Za-z0-9.-]+)?)*\$|^\*\$')
if not semver_range.match(field.strip()):
    print('ERROR: plugin.json wicked_testing_version is not a valid semver range')
    sys.exit(1)
print('OK: wicked_testing_version = \"' + field + '\"')
"
```

### 1b. Gate Policy — wicked-testing Tier-1 Allowlist

Validate that every `wicked-testing:*` reviewer reference in `gate-policy.json` is
a Tier-1 agent from INTEGRATION.md §3, and that no stale legacy qe reviewer names or
bare `qe-evaluator` references remain.

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'scripts')
from _wicked_testing_tier1 import validate_gate_policy, TIER2_AGENTS
import re

# --- 1. gate-policy.json Tier-1 check ---
try:
    gp = json.loads(open('.claude-plugin/gate-policy.json').read())
except Exception as e:
    print(f'ERROR: Could not parse gate-policy.json: {e}')
    sys.exit(1)

violations = validate_gate_policy(gp)
for v in violations:
    print(f'ERROR: [gate-policy] Unknown or stale reviewer: \"{v}\" — not in INTEGRATION.md §3 Tier-1 list')

# --- 2. Scan key files for any wicked-testing:* references ---
scan_paths = [
    '.claude-plugin/gate-policy.json',
    '.claude-plugin/specialist.json',
    'scripts/crew/phase_manager.py',
    'scripts/crew/gate_dispatch.py',
]

import os, glob as glob_mod
for pattern in ['agents/**/*.md', 'commands/**/*.md']:
    for p in glob_mod.glob(pattern, recursive=True):
        scan_paths.append(p)

wt_pattern = re.compile(r'wicked-testing:[a-z0-9:-]+')
found_violations = []
for path in scan_paths:
    if not os.path.exists(path):
        continue
    try:
        text = open(path).read()
    except Exception:
        continue
    for m in wt_pattern.finditer(text):
        name = m.group(0)
        from _wicked_testing_tier1 import is_valid_wt_reviewer
        if not is_valid_wt_reviewer(name):
            found_violations.append((path, name))
    # Flag Tier-2 names in gate-policy.json and specialist.json (not in agent/command docs)
    if path in ('.claude-plugin/gate-policy.json', '.claude-plugin/specialist.json'):
        for t2 in TIER2_AGENTS:
            if t2 in text:
                found_violations.append((path, f'{t2} (Tier-2 — not a valid gate reviewer)'))

for path, name in found_violations:
    print(f'ERROR: [wg-check] Unknown wicked-testing reviewer: \"{name}\" in {path}')

total_errors = len(violations) + len(found_violations)
if total_errors == 0:
    print('OK: gate-policy.json wicked-testing Tier-1 allowlist — PASS')
else:
    sys.exit(1)
" 2>/dev/null || python -c "
import json, sys, os, re
sys.path.insert(0, 'scripts')
try:
    from _wicked_testing_tier1 import validate_gate_policy
    gp = json.loads(open('.claude-plugin/gate-policy.json').read())
    violations = validate_gate_policy(gp)
    for v in violations:
        print('ERROR: [gate-policy] Unknown or stale reviewer: \"' + v + '\"')
    if not violations:
        print('OK: gate-policy.json wicked-testing Tier-1 allowlist -- PASS')
except Exception as e:
    print('WARNING: Could not validate wicked-testing Tier-1 allowlist: ' + str(e))
"
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

### 3a. Agent Line Counts (#664)

Agents that exceed 200 lines are conflation candidates: prompts that long usually
encode rubrics, multi-step procedures, or persona archetype tables that belong in
a sibling skill / refs file. Lessons from PR #666 (jam slim) and PR #670
(propose-process slim) showed that bloated single-file agents accumulate the kind
of content that should live behind progressive disclosure. Threshold rationale:
warn at >200 (matches the skill ceiling); hard error at >400 (effectively
two-skills-in-an-agent territory).

```bash
# Threshold rationale: see #664. Warn ≥ 200 (skill ceiling parity), error ≥ 400
# (two-skills-in-an-agent). The error threshold is intentionally generous so the
# existing roster only flips a small number of files; the warn threshold gives
# authors a continuous nudge without blocking releases.
AGENT_WARN_LINES=200
AGENT_ERROR_LINES=400

for agent in $(find "./agents" -name "*.md" 2>/dev/null); do
  lines=$(wc -l < "$agent")
  rel=$(echo "$agent" | sed 's|^\./||')
  if [[ "$lines" -gt "$AGENT_ERROR_LINES" ]]; then
    echo "ERROR: $rel is $lines lines (max ${AGENT_ERROR_LINES} — split rubric/persona content into a sibling skill, see #664)"
  elif [[ "$lines" -gt "$AGENT_WARN_LINES" ]]; then
    echo "WARNING: $rel is $lines lines (>${AGENT_WARN_LINES} — conflation candidate per #664; consider extracting refs/* or moving rubric steps to a skill)"
  fi
done
```

### 3b. Skill-as-Agent Conflation Heuristic (#664)

For each skill, look for a sibling agent in the same domain and grep both files
for shared content classes. If 3+ classes overlap, warn that the skill and the
agent likely duplicate rubric / persona / mechanics content — this is the
Pattern A migration smell from #652.

The check is intentionally cheap (no LLM, no diff): four regex probes per file,
domain-scoped pairing only. False positives are acceptable because the warning is
informational; the cost of a missed conflation (twin sources of truth) is much
higher than the cost of a false flag.

```bash
sh "${CLAUDE_PLUGIN_ROOT:-.}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT:-.}/scripts/wg/check_conflation.py" 2>/dev/null \
  || python3 -c "
import os, re, sys
from pathlib import Path

# Conflation content classes — each is a regex probe. A class 'matches' a file
# if the file contains the pattern at least once. If 3+ classes match BOTH the
# SKILL.md and a sibling agent in the same domain, warn (#664 / #652 Pattern A).
PROBES = {
    'persona-archetype-list': re.compile(r'(persona[\s-]?archetype|archetype[\s-]?pool|persona pool|focus group personas?)', re.IGNORECASE),
    'rubric-step-block': re.compile(r'(^|\n)(#{2,4}\s*)?step\s*[0-9]+\s*[-:—]', re.IGNORECASE),
    'convergence-or-round-mechanics': re.compile(r'(convergence (check|mode|signal)|round\s*[0-9]+|after each round|next round)', re.IGNORECASE),
    'transcript-event-bus-emit': re.compile(r'(save_transcript|store the full transcript|emit (a|an) (event|synthesis event)|event log|bus emit|emit_event)', re.IGNORECASE),
}
THRESHOLD = 3

skills_root = Path('./skills')
agents_root = Path('./agents')
if not skills_root.is_dir() or not agents_root.is_dir():
    sys.exit(0)

def probe(text):
    return {name for name, rx in PROBES.items() if rx.search(text)}

def candidate_agents(domain, skill_name):
    domain_dir = agents_root / domain
    if not domain_dir.is_dir():
        return []
    out = []
    sk = skill_name.lower().replace('_', '-')
    for md in sorted(domain_dir.glob('*.md')):
        stem = md.stem.lower()
        if stem == sk or sk in stem or stem in sk:
            out.append(md)
            continue
        if sk in ('skill', domain) and stem.endswith(('-facilitator', '-orchestrator', '-coordinator')):
            out.append(md)
    if not out:
        for md in sorted(domain_dir.glob('*.md')):
            out.append(md)
    return out

flagged = 0
for skill_md in sorted(skills_root.rglob('SKILL.md')):
    parts = skill_md.relative_to(skills_root).parts
    if not parts:
        continue
    domain = parts[0]
    skill_name = parts[1] if len(parts) >= 3 else domain
    try:
        skill_text = skill_md.read_text(errors='replace')
    except Exception:
        continue
    skill_classes = probe(skill_text)
    if len(skill_classes) < THRESHOLD:
        continue
    for agent_md in candidate_agents(domain, skill_name):
        try:
            agent_text = agent_md.read_text(errors='replace')
        except Exception:
            continue
        agent_classes = probe(agent_text)
        shared = skill_classes & agent_classes
        if len(shared) >= THRESHOLD:
            flagged += 1
            rel_skill = skill_md.relative_to(Path('.'))
            rel_agent = agent_md.relative_to(Path('.'))
            print(f'WARNING: skill-as-agent conflation detected — {rel_skill} and {rel_agent} share {len(shared)} content classes ({sorted(shared)}). See #652 Pattern A migration.')

if flagged == 0:
    print('OK: no skill-as-agent conflation patterns detected (#664)')
" 2>/dev/null || python -c "print('WARNING: could not run conflation heuristic')"
```

**What this catches**: A SKILL.md that still owns rubric steps + persona pools +
convergence/round mechanics + transcript/bus emit instructions while a sibling
agent in the same domain also encodes the same four classes. The fix is the
Pattern A migration: keep the orchestration prose in the agent, slim the skill
to navigation + entry-points (~50-100 lines).

**Acceptable false positives**: any skill that legitimately documents what its
sibling agent does (links + brief overview). The signal is most useful when both
files contain *full* rubric / mechanics blocks — exactly the duplication that
PRs #666 and #670 cleaned up.

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

### 9. Self-Referential Integrity

Verify the plugin's own references resolve correctly — prevents the "cobbler's children" problem where refactors break internal paths.

```bash
# 9a. Script paths in commands/agents actually exist
BROKEN=0
for md in $(find ./commands ./agents -name "*.md" 2>/dev/null); do
  refs=$(grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/[^ "]+\.(py|sh)' "$md" 2>/dev/null | sed 's|\${CLAUDE_PLUGIN_ROOT}/||')
  for ref in $refs; do
    if [[ ! -f "./$ref" ]]; then
      echo "ERROR: $(echo $md | sed 's|^\./||'): broken script path: $ref"
      BROKEN=$((BROKEN + 1))
    fi
  done
done
if [[ "$BROKEN" -gt 0 ]]; then
  echo "ERROR: $BROKEN broken script references in commands/agents"
fi
```

```bash
# 9b. hooks.json script paths resolve
python3 -c "
import json, re, sys
from pathlib import Path
root = Path('.')
hooks = json.loads((root / 'hooks/hooks.json').read_text())
broken = 0
for event, matchers in hooks.get('hooks', {}).items():
    for m in matchers:
        for h in m.get('hooks', []):
            for p in re.findall(r'\\\$\{CLAUDE_PLUGIN_ROOT\}/([^ \"]+\.py)', h.get('command', '')):
                if not (root / p).exists():
                    print(f'ERROR: hooks.json [{event}]: script not found: {p}')
                    broken += 1
if broken:
    print(f'ERROR: {broken} broken hook script references')
else:
    print('OK: All hook script paths resolve')
" 2>/dev/null || python -c "print('WARNING: Could not validate hook script paths')"
```

```bash
# 9c. specialist.json roles match what specialist_discovery.py accepts
python3 -c "
import json, re, sys
from pathlib import Path
root = Path('.')
specs = json.loads((root / '.claude-plugin/specialist.json').read_text())
disc = (root / 'scripts/crew/specialist_discovery.py').read_text()
m = re.search(r'ROLE_CATEGORIES\s*=\s*\{([^}]+)\}', disc, re.DOTALL)
if not m:
    print('WARNING: Could not parse ROLE_CATEGORIES')
    sys.exit(0)
role_keys = set(re.findall(r'\"([^\"]+)\"\s*:', m.group(1)))
bad = 0
for s in specs.get('specialists', []):
    role = s.get('role', '')
    if role and role not in role_keys:
        print(f\"ERROR: specialist '{s.get(\"name\",\"?\")}' has role '{role}' not in ROLE_CATEGORIES\")
        bad += 1
if bad:
    print(f'ERROR: {bad} specialist roles not recognized by discovery')
else:
    print(f'OK: All {len(specs.get(\"specialists\", []))} specialist roles match ROLE_CATEGORIES')
" 2>/dev/null || python -c "print('WARNING: Could not validate specialist roles')"
```

### 10. Agent Trigger Analysis

Analyze agent descriptions for trigger quality, overlap, and coverage gaps.

```bash
# 10a. Count agents per domain and check description quality
python3 -c "
import os, re, sys
from pathlib import Path
from collections import defaultdict

agents_root = Path('./agents')
domains = sorted(d.name for d in agents_root.iterdir() if d.is_dir())

# Parse agent frontmatter
agents = []
for domain in domains:
    domain_path = agents_root / domain
    for md in sorted(domain_path.glob('*.md')):
        content = md.read_text()
        m = re.match(r'^---\n(.*?\n)---', content, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        name_m = re.search(r'^name:\s*(.+)', fm, re.MULTILINE)
        name = name_m.group(1).strip() if name_m else md.stem

        # Extract description (handles multiline YAML with blank lines)
        desc_m = re.search(r'^description:\s*\|?\s*\n((?:(?:[ \t]+.*|)\n)*)', fm, re.MULTILINE)
        if desc_m:
            desc = desc_m.group(1).strip()
        else:
            desc_m = re.search(r'^description:\s*(.+)', fm, re.MULTILINE)
            desc = desc_m.group(1).strip() if desc_m else ''

        has_example = '<example>' in desc
        agents.append({
            'domain': domain,
            'name': name,
            'desc': desc,
            'desc_len': len(desc),
            'has_example': has_example,
            'file': str(md),
        })

# 10a. Summary table
print('### Agent Trigger Analysis')
print()
domain_counts = defaultdict(int)
for a in agents:
    domain_counts[a['domain']] += 1
print('| Domain | Agent Count |')
print('|--------|------------|')
for d in sorted(domain_counts):
    print(f\"| {d} | {domain_counts[d]} |\")
print(f'| **Total** | **{len(agents)}** |')
print()

# 10b. Short descriptions (<50 chars)
short = [a for a in agents if a['desc_len'] < 50]
if short:
    print(f'WARNING: {len(short)} agents with short descriptions (<50 chars) — may not trigger well:')
    for a in short:
        print(f'  {a[\"domain\"]}/{a[\"name\"]}: {a[\"desc_len\"]} chars')
    print()

# 10c. Missing example blocks
no_examples = [a for a in agents if not a['has_example']]
if no_examples:
    print(f'WARNING: {len(no_examples)} agents missing <example> blocks in description:')
    for a in no_examples:
        print(f'  {a[\"domain\"]}/{a[\"name\"]}')
    print()

# 10d. Trigger phrase overlap detection
# Extract 'Use when:' phrases and key trigger words
trigger_words = defaultdict(list)
for a in agents:
    use_when = re.search(r'Use when:\s*(.+)', a['desc'])
    if use_when:
        phrases = [w.strip().lower() for w in re.split(r'[,;]', use_when.group(1)) if w.strip()]
        for phrase in phrases:
            # Normalize and collect 2+ word phrases
            words = phrase.split()
            for i in range(len(words)):
                for j in range(i+2, min(i+4, len(words)+1)):
                    bigram = ' '.join(words[i:j])
                    if len(bigram) > 5:
                        trigger_words[bigram].append(f'{a[\"domain\"]}/{a[\"name\"]}')

# Find overlapping trigger phrases (shared by 2+ agents in different domains)
overlaps = {}
for phrase, agent_list in trigger_words.items():
    domains_seen = set(a.split('/')[0] for a in agent_list)
    if len(agent_list) >= 2 and len(domains_seen) >= 2:
        overlaps[phrase] = agent_list

if overlaps:
    # Deduplicate: keep only the longest overlapping phrase per agent pair
    print(f'NOTICE: {len(overlaps)} trigger phrases shared across domains (potential overlap):')
    shown = set()
    for phrase in sorted(overlaps, key=lambda p: (-len(overlaps[p]), p)):
        agents_key = tuple(sorted(set(overlaps[phrase])))
        if agents_key not in shown and len(shown) < 15:
            shown.add(agents_key)
            print(f'  \"{phrase}\" -> {\" , \".join(sorted(set(overlaps[phrase])))}')
    print()
else:
    print('OK: No cross-domain trigger phrase overlaps detected')
    print()

# Summary
errors = len(short) + len(no_examples)
if errors == 0:
    print('Agent Trigger Analysis: PASS')
else:
    print(f'Agent Trigger Analysis: {len(short)} short descriptions, {len(no_examples)} missing examples')
" 2>/dev/null || python -c "print('WARNING: Could not run agent trigger analysis')"
```

```bash
# 10e. Detailed per-domain breakdown (shown with --agents flag, or on --full)
# When running with --agents, also show per-agent detail:
python3 -c "
import os, re, sys
from pathlib import Path

agents_root = Path('./agents')
domains = sorted(d.name for d in agents_root.iterdir() if d.is_dir())

print('### Detailed Agent Inventory')
print()
for domain in domains:
    domain_path = agents_root / domain
    mds = sorted(domain_path.glob('*.md'))
    if not mds:
        continue
    print(f'#### {domain} ({len(mds)} agents)')
    print('| Agent | Desc Len | Has Example | Trigger Phrases |')
    print('|-------|----------|-------------|-----------------|')
    for md in mds:
        content = md.read_text()
        m = re.match(r'^---\n(.*?\n)---', content, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        name_m = re.search(r'^name:\s*(.+)', fm, re.MULTILINE)
        name = name_m.group(1).strip() if name_m else md.stem
        desc_m = re.search(r'^description:\s*\|?\s*\n((?:(?:[ \t]+.*|)\n)*)', fm, re.MULTILINE)
        if desc_m:
            desc = desc_m.group(1).strip()
        else:
            desc_m = re.search(r'^description:\s*(.+)', fm, re.MULTILINE)
            desc = desc_m.group(1).strip() if desc_m else ''
        has_ex = 'yes' if '<example>' in desc else 'NO'
        use_when = re.search(r'Use when:\s*(.+)', desc)
        triggers = use_when.group(1).strip()[:60] if use_when else '(none)'
        status = 'short' if len(desc) < 50 else ''
        print(f'| {name} | {len(desc)}{\" !!\" if len(desc) < 50 else \"\"} | {has_ex} | {triggers} |')
    print()
" 2>/dev/null || python -c "print('WARNING: Could not run detailed agent inventory')"
```

**When to run each part**:
- Section 10a-10d (summary + warnings) runs as part of every quick check
- Section 10e (detailed inventory) runs only with `--agents` or `--full` flags

### 11. Pattern A Migration Validation Gate (#665)

When a PR shrinks a `skills/**/SKILL.md` substantially AND adds a new
`agents/**/*.md` in the same diff, that's the Pattern A migration shape from
#666 (jam slim) and #670 (propose-process slim). The gate enforces the rule
codified in #665: **every Pattern A migration must ship with a passing
acceptance scenario** so reviewers can verify the new agent is wired correctly
and the slimmed skill still delegates to the right place.

**Signal**: a `SKILL.md` shrunk by ≥40% (lines-removed / lines-before) AND a new
`agents/**/*.md` file added in the same `git diff origin/main...HEAD`.

**Requirement on detection**: the same diff must add a scenario file matching
one of these patterns (any domain):

- `scenarios/**/*-pattern-a.md`
- `scenarios/**/*-shape.md`
- `scenarios/**/*-dispatch.md`
- `scenarios/**/*pattern*.md`, `scenarios/**/*shape*.md`, `scenarios/**/*dispatch*.md`

**Behavior**: ERROR (blocks CI) if signal detected and no matching scenario.
Fail-open if `git diff origin/main...HEAD` returns empty (running on main with
no PR context). The 40% threshold + same-PR new-agent requirement is calibrated
so that incremental skill polish never trips the gate — only true Pattern A
migrations do.

```bash
sh "${CLAUDE_PLUGIN_ROOT:-.}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT:-.}/scripts/wg/check_pattern_a_gate.py" 2>/dev/null \
  || python3 -c "
import os, re, subprocess, sys
from pathlib import Path

# Threshold rationale: see #665. SKILL.md must shrink by >= SHRINK_RATIO of its
# pre-diff size to count as 'slimmed'. Combined with a same-PR new agent file,
# this is the Pattern A signal. Tuning lower would catch normal polish PRs;
# tuning higher would miss legitimate slim migrations like PR #666 (jam went
# from ~120 lines to 43, a 64% drop).
SHRINK_RATIO = 0.40

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ''
    except Exception:
        return ''

base_ref = os.environ.get('WG_PR_BASE_REF') or os.environ.get('GITHUB_BASE_REF') or 'origin/main'
if base_ref and not base_ref.startswith('origin/') and base_ref != 'main':
    base_ref = f'origin/{base_ref}'

diff_range = f'{base_ref}...HEAD'

name_status = run(['git', 'diff', '--name-status', diff_range])
if not name_status.strip():
    print('OK: no PR diff against ' + base_ref + ' — Pattern A gate skipped (fail-open)')
    sys.exit(0)

slimmed_skills = []
new_agents = []
new_scenarios = []

for line in name_status.splitlines():
    parts = line.split('\t')
    if len(parts) < 2:
        continue
    status = parts[0].strip()
    path = parts[-1].strip()
    if status.startswith('A') and path.startswith('agents/') and path.endswith('.md'):
        new_agents.append(path)
    if status.startswith('A') and path.startswith('scenarios/') and path.endswith('.md'):
        new_scenarios.append(path)
    if path.startswith('skills/') and path.endswith('SKILL.md') and status.startswith(('M', 'R')):
        numstat = run(['git', 'diff', '--numstat', diff_range, '--', path])
        if not numstat.strip():
            continue
        for nl in numstat.splitlines():
            np = nl.split('\t')
            if len(np) < 3:
                continue
            try:
                added = int(np[0]); deleted = int(np[1])
            except ValueError:
                continue
            base_blob = run(['git', 'show', f'{base_ref}:{path}'])
            base_lines = base_blob.count('\n') if base_blob else 0
            if base_lines == 0:
                continue
            shrink = (deleted - added) / base_lines if base_lines else 0
            if shrink >= SHRINK_RATIO:
                slimmed_skills.append((path, base_lines, shrink))

if not slimmed_skills or not new_agents:
    if slimmed_skills:
        for p, bl, sr in slimmed_skills:
            print(f'INFO: {p} shrunk by {sr*100:.0f}% (was {bl} lines) — no new agent in this PR, not a Pattern A migration')
    print('OK: no Pattern A migration signal in this PR (#665)')
    sys.exit(0)

SCENARIO_PATTERNS = [
    re.compile(r'^scenarios/.+-pattern-a\.md$'),
    re.compile(r'^scenarios/.+-shape\.md$'),
    re.compile(r'^scenarios/.+-dispatch\.md$'),
    re.compile(r'^scenarios/.*pattern.*\.md$', re.IGNORECASE),
    re.compile(r'^scenarios/.*shape.*\.md$', re.IGNORECASE),
    re.compile(r'^scenarios/.*dispatch.*\.md$', re.IGNORECASE),
]

matching = [s for s in new_scenarios if any(p.match(s) for p in SCENARIO_PATTERNS)]

print('Pattern A migration detected:')
for p, bl, sr in slimmed_skills:
    print(f'  slimmed skill: {p} (was {bl} lines, shrunk {sr*100:.0f}%)')
for a in new_agents:
    print(f'  new agent:     {a}')

if matching:
    for s in matching:
        print(f'OK: Pattern A migration covered by scenario: {s} (#665)')
    sys.exit(0)

print('ERROR: Pattern A migration detected but no matching scenario added in this PR (#665).')
print('       Add a scenario in scenarios/{domain}/ matching one of:')
print('         *-pattern-a.md, *-shape.md, *-dispatch.md, *pattern*.md, *shape*.md, *dispatch*.md')
print('       Reference scenarios: scenarios/crew/process-facilitator-pattern-a.md (PR #670),')
print('       scenarios/jam/quick-facilitator-shape.md (PR #666).')
sys.exit(1)
" 2>/dev/null || python -c "print('WARNING: Could not run Pattern A migration gate')"
```

**Override**: there is no env-var bypass. The gate is intentionally narrow
(40% shrink + same-PR new agent) so genuine non-migration work never trips it.
If a legitimate Pattern A migration ships with the scenario in a follow-up PR,
add a placeholder scenario file (`scenarios/{domain}/{name}-pattern-a.md` with
a short "TODO: implement" body) and replace it in the follow-up.

### Quick Check Output

```markdown
## Quick Check: wicked-garden

| Check | Status |
|-------|--------|
| plugin.json | ✓/✗ |
| Version (semver) | ✓/✗ |
| wicked_testing_version (semver range) | ✓/✗ |
| gate-policy.json Tier-1 allowlist | ✓/✗ |
| JSON validity | ✓/✗ |
| Skills ≤200 lines | ✓/✗ |
| Agent line counts (#664) | ✓/⚠/✗ |
| Skill-as-agent conflation (#664) | ✓/⚠ |
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
| Self-referential integrity | ✓/✗ |
| Agent trigger analysis | ✓/⚠ |
| Pattern A migration gate (#665) | ✓/✗/skip |

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
