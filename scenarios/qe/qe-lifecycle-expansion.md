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

## Scenario 1: Facilitator Routes Quality-Themed Work to QE

v6 replaced the v5 `SIGNAL_KEYWORDS` / `SIGNAL_TO_SPECIALISTS` maps with the
`wicked-garden:propose-process` facilitator rubric (#428). This scenario
validates that quality-themed descriptions still route to QE specialists and
phases in the facilitator's output plan.

### Setup

- wicked-garden plugin checked out; `scenarios/crew/facilitator-rubric/*` passing
- No external services required

### Steps

#### 1. QE lifecycle agents are discoverable by the facilitator

The facilitator reads `agents/**/*.md` frontmatter directly. Validate the QE
lifecycle agent files exist and their body mentions quality/testing cues.

```bash
python3 -c "
import re
from pathlib import Path
plugin_root = Path('${CLAUDE_PLUGIN_ROOT}')
qe_agents = [
    'agents/qe/requirements-quality-analyst.md',
    'agents/qe/testability-reviewer.md',
    'agents/qe/continuous-quality-monitor.md',
    'agents/qe/production-quality-engineer.md',
]
quality_cues = {'quality', 'test', 'acceptance', 'reliability', 'slo', 'monitoring'}
for rel in qe_agents:
    p = plugin_root / rel
    assert p.exists(), f'missing {rel}'
    words = set(re.findall(r'\w+', p.read_text().lower()))
    hits = quality_cues & words
    assert hits, f'{rel} has no quality-related cues'
    print(f'PASS: {p.name} cues={sorted(hits)[:3]}')
"
```

**Expected**: 4 `PASS` lines.

#### 2. Facilitator picks QE specialists for quality-themed prompts

Invoke the facilitator rubric on quality-themed descriptions. Verify each
returned plan includes at least one QE specialist AND at least one of
`test-strategy`, `test`, or `review` in the phase list.

Descriptions to exercise:
- "Add TDD tests for the payment module"
- "Define SLO for the checkout API and add canary rollback"
- "Write acceptance criteria for the shopping cart checkout"
- "Design a rollback plan for the accounts database migration"

For each, invoke:

```
Skill(
  skill="wicked-garden:propose-process",
  args={"description": "<prompt>", "mode": "propose", "output": "json"}
)
```

Inspect the returned JSON:

- `specialists[]` must contain at least one QE-aligned role
  (`test-strategist`, `requirements-quality-analyst`, `testability-reviewer`,
  `production-quality-engineer`, or `continuous-quality-monitor`).
- `phases[]` must contain at least one of `test-strategy`, `test`, `review`.

The specific picks may change as the roster evolves — the contract is that
QE involvement is non-zero for quality-themed work.

**Expected**: all 4 descriptions return plans satisfying both constraints.

### Success Criteria

- [ ] All 4 QE lifecycle agent markdown files exist with quality cues
- [ ] Facilitator returns >= 1 QE-aligned specialist on all 4 quality prompts
- [ ] Facilitator includes >= 1 of test-strategy / test / review phases

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

#### 2. Verify phases.json has qe in clarify and design

```bash
python3 -c "
import json
from pathlib import Path

plugin_root = '${CLAUDE_PLUGIN_ROOT}'
data = json.loads((Path(plugin_root) / '.claude-plugin/phases.json').read_text())

for phase_name in ['clarify', 'design']:
    phase = data['phases'][phase_name]
    specialists = phase['specialists']
    assert 'qe' in specialists, f'qe missing from {phase_name} specialists: {specialists}'
    print(f'PASS: qe in {phase_name} specialists: {specialists}')
"
```

**Expected**:
```
PASS: qe in clarify specialists: ['product', 'jam', 'qe']
PASS: qe in design specialists: ['engineering', 'agentic', 'product', 'qe']
```

### Success Criteria

- [ ] `specialist.json` QE `enhances` includes both `clarify` and `design`
- [ ] 3 new personas registered: Requirements Quality Analyst, Testability Reviewer, Production Quality Engineer
- [ ] `phases.json` clarify phase `specialists` includes `qe`
- [ ] `phases.json` design phase `specialists` includes `qe`

## Value Demonstrated

**Problem solved**: QE was previously a build-phase-only concern. Issues discovered late in development are expensive — vague requirements lead to implementation rework, poor design leads to untestable code, and production blind spots allow silent quality degradation.

**Real-world value**:
- **Clarify gate**: Requirements Quality Analyst catches untestable ACs before a line of code is written
- **Design gate**: Testability Reviewer ensures architecture is mockable and components isolatable
- **Build signals**: Continuous Quality Monitor catches complexity and coverage gaps in real-time
- **Production monitoring**: Production Quality Engineer defines and monitors SLO targets and rollback criteria

This transforms QE from a review-time activity into a lifecycle-long quality practice — catch quality issues at the earliest and cheapest point where they can be fixed.
