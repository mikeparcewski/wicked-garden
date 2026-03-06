---
name: qe-lifecycle-expansion
title: QE Lifecycle Expansion — Clarify, Design, and Production Phases
description: Validates that QE specialist participates in clarify/design phases, quality signal routing is active, and all 4 new lifecycle agents are present
type: testing
difficulty: beginner
estimated_minutes: 5
---

# QE Lifecycle Expansion

This scenario validates that QE quality gates now span the full lifecycle: from requirements (clarify)
through design (testability) and into production (monitoring), alongside the existing build phase coverage.

## Scenario 1: Quality Signal Routing

Validates that `smart_decisioning.py` detects quality-related prompts and routes to `wicked-qe`.

### Setup

No external setup required. This tests the signal detection logic directly.

### Steps

#### 1. Verify quality keywords are in SIGNAL_KEYWORDS

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from smart_decisioning import SIGNAL_KEYWORDS, SIGNAL_TO_SPECIALISTS

assert 'quality' in SIGNAL_KEYWORDS, 'quality key missing from SIGNAL_KEYWORDS'
assert 'quality' in SIGNAL_TO_SPECIALISTS, 'quality key missing from SIGNAL_TO_SPECIALISTS'
assert 'wicked-qe' in SIGNAL_TO_SPECIALISTS['quality'], 'wicked-qe not in quality specialists'

quality_keywords = SIGNAL_KEYWORDS['quality']
required = ['tdd', 'slo', 'acceptance criteria', 'testability', 'quality gate', 'shift-left']
for kw in required:
    assert kw in quality_keywords, f'keyword missing: {kw}'

print('PASS: quality signal routing configured correctly')
print(f'  Keywords: {len(quality_keywords)} total')
print(f'  Specialists: {SIGNAL_TO_SPECIALISTS[\"quality\"]}')
"
```

**Expected**: `PASS: quality signal routing configured correctly`

#### 2. Verify signal detection fires on quality prompts

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from smart_decisioning import SIGNAL_KEYWORDS
import re

quality_prompts = [
    'we need better test coverage for the payment service',
    'what is our SLO target for this endpoint',
    'help me define acceptance criteria for the login feature',
    'the rollback criteria for this canary deploy',
    'implement TDD for the new auth module',
]

quality_kws = SIGNAL_KEYWORDS['quality']

def matches(prompt, keywords):
    prompt_lower = prompt.lower()
    for kw in keywords:
        pattern = kw.rstrip('*')
        if re.search(r'\b' + re.escape(pattern), prompt_lower):
            return True
    return False

for prompt in quality_prompts:
    result = matches(prompt, quality_kws)
    status = 'PASS' if result else 'FAIL'
    print(f'{status}: {prompt[:60]}')
"
```

**Expected**: All 5 prompts print `PASS`.

### Success Criteria

- [ ] `quality` key present in `SIGNAL_KEYWORDS` with 15+ keywords
- [ ] `quality` key present in `SIGNAL_TO_SPECIALISTS` mapping to `wicked-qe`
- [ ] Quality-related prompts (TDD, SLO, acceptance criteria, rollback) trigger signal match

---

## Scenario 2: Structural Validation — All 4 Agent Files Exist

Validates that all 4 new QE lifecycle agents are present and have valid YAML frontmatter.

### Setup

No external setup required.

### Steps

#### 1. Check agent files exist

```bash
agents=(
    "${CLAUDE_PLUGIN_ROOT}/agents/qe/requirements-quality-analyst.md"
    "${CLAUDE_PLUGIN_ROOT}/agents/qe/testability-reviewer.md"
    "${CLAUDE_PLUGIN_ROOT}/agents/qe/continuous-quality-monitor.md"
    "${CLAUDE_PLUGIN_ROOT}/agents/qe/production-quality-engineer.md"
)

for f in "${agents[@]}"; do
    if [ -f "$f" ]; then
        echo "PASS: $(basename $f)"
    else
        echo "FAIL: $(basename $f) — file not found"
    fi
done
```

**Expected**: All 4 lines print `PASS`.

#### 2. Validate YAML frontmatter has required fields

```bash
python3 -c "
import re
from pathlib import Path

agents = [
    'agents/qe/requirements-quality-analyst.md',
    'agents/qe/testability-reviewer.md',
    'agents/qe/continuous-quality-monitor.md',
    'agents/qe/production-quality-engineer.md',
]

required_fields = ['name', 'description', 'model']
plugin_root = '${CLAUDE_PLUGIN_ROOT}'

for agent_path in agents:
    path = Path(plugin_root) / agent_path
    content = path.read_text()

    # Extract frontmatter
    fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    assert fm_match, f'{agent_path}: No YAML frontmatter found'
    frontmatter = fm_match.group(1)

    for field in required_fields:
        assert f'{field}:' in frontmatter, f'{agent_path}: Missing field \"{field}\"'

    # Check line count <= 200
    line_count = len(content.splitlines())
    assert line_count <= 200, f'{agent_path}: {line_count} lines exceeds 200 line limit'

    print(f'PASS: {Path(agent_path).name} ({line_count} lines)')
"
```

**Expected**: All 4 agents print `PASS` with line counts under 200.

### Success Criteria

- [ ] All 4 agent `.md` files exist under `agents/qe/`
- [ ] Each file has valid YAML frontmatter with `name`, `description`, `model`
- [ ] No file exceeds 200 lines

---

## Scenario 3: Integration — specialist.json and phases.json

Validates that the QE specialist now enhances clarify and design phases, and that 3 new personas are registered.

### Setup

No external setup required.

### Steps

#### 1. Verify specialist.json QE entry

```bash
python3 -c "
import json
from pathlib import Path

plugin_root = '${CLAUDE_PLUGIN_ROOT}'
data = json.loads((Path(plugin_root) / '.claude-plugin/specialist.json').read_text())

qe = next((s for s in data['specialists'] if s['name'] == 'qe'), None)
assert qe is not None, 'QE specialist not found'

enhances = qe['enhances']
for phase in ['clarify', 'design']:
    assert phase in enhances, f'{phase} not in QE enhances: {enhances}'
print(f'PASS: QE enhances includes clarify and design')
print(f'  enhances: {enhances}')

new_persona_names = [
    'Requirements Quality Analyst',
    'Testability Reviewer',
    'Production Quality Engineer',
]
persona_names = [p['name'] for p in qe['personas']]
for name in new_persona_names:
    assert name in persona_names, f'Persona not found: {name}'
    print(f'PASS: persona registered — {name}')
"
```

**Expected**:
```
PASS: QE enhances includes clarify and design
  enhances: ['clarify', 'design', 'qe', 'build', 'review', '*']
PASS: persona registered — Requirements Quality Analyst
PASS: persona registered — Testability Reviewer
PASS: persona registered — Production Quality Engineer
```

#### 2. Verify phases.json has wicked-qe in clarify and design

```bash
python3 -c "
import json
from pathlib import Path

plugin_root = '${CLAUDE_PLUGIN_ROOT}'
data = json.loads((Path(plugin_root) / '.claude-plugin/phases.json').read_text())

for phase_name in ['clarify', 'design']:
    phase = data['phases'][phase_name]
    specialists = phase['specialists']
    assert 'wicked-qe' in specialists, f'wicked-qe missing from {phase_name} specialists: {specialists}'
    print(f'PASS: wicked-qe in {phase_name} specialists: {specialists}')
"
```

**Expected**:
```
PASS: wicked-qe in clarify specialists: ['wicked-product', 'wicked-jam', 'wicked-qe']
PASS: wicked-qe in design specialists: ['wicked-engineering', 'wicked-agentic', 'wicked-product', 'wicked-qe']
```

### Success Criteria

- [ ] `specialist.json` QE `enhances` includes both `clarify` and `design`
- [ ] 3 new personas registered: Requirements Quality Analyst, Testability Reviewer, Production Quality Engineer
- [ ] `phases.json` clarify phase `specialists` includes `wicked-qe`
- [ ] `phases.json` design phase `specialists` includes `wicked-qe`

## Value Demonstrated

**Problem solved**: QE was previously a build-phase-only concern. Issues discovered late in development are expensive — vague requirements lead to implementation rework, poor design leads to untestable code, and production blind spots allow silent quality degradation.

**Real-world value**:
- **Clarify gate**: Requirements Quality Analyst catches untestable ACs before a line of code is written
- **Design gate**: Testability Reviewer ensures architecture is mockable and components isolatable
- **Build signals**: Continuous Quality Monitor catches complexity and coverage gaps in real-time
- **Production monitoring**: Production Quality Engineer defines and monitors SLO targets and rollback criteria

This transforms QE from a review-time activity into a lifecycle-long quality practice — catch quality issues at the earliest and cheapest point where they can be fixed.
