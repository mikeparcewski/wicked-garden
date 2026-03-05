---
name: tdd-enforcement-red-green-refactor
title: TDD Enforcement Red-Green-Refactor Cycle
description: Verify execute.md build phase enforces TDD coach dispatch for complexity >= 2 tasks, and traceability_generator.py maps test criteria to completed tasks
type: workflow
difficulty: intermediate
estimated_minutes: 12
---

# TDD Enforcement Red-Green-Refactor Cycle

This scenario validates that:
1. The build phase in `execute.md` dispatches a TDD coach agent for the red phase before implementation
2. The implementer handles the green phase after failing tests exist
3. The TDD coach verifies the refactor phase
4. `traceability_generator.py` reads test-strategy deliverables and produces a traceability matrix
5. The `evidence-taxonomy.md` reference file provides a table of evidence types

## Setup

```bash
# Verify traceability_generator.py is available
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability_generator.py" --help > /dev/null 2>&1 && echo "traceability_generator.py available"

# Verify evidence-taxonomy.md exists
test -f "${CLAUDE_PLUGIN_ROOT}/skills/qe/qe-strategy/refs/evidence-taxonomy.md" && echo "evidence-taxonomy.md exists"
```

## Steps

### 1. execute.md build phase contains TDD coach dispatch instruction

```bash
grep -q "tdd-coach\|tdd coach\|TDD coach" "${CLAUDE_PLUGIN_ROOT}/commands/crew/execute.md" && echo "PASS: TDD coach referenced in execute.md"
```

Expected: `PASS: TDD coach referenced in execute.md`

### 2. execute.md describes red-green-refactor pattern

```bash
grep -q "red phase\|green phase\|refactor" "${CLAUDE_PLUGIN_ROOT}/commands/crew/execute.md" && echo "PASS: Red-green-refactor described"
```

Expected: `PASS: Red-green-refactor described`

### 3. execute.md complexity threshold for TDD dispatch

```bash
grep -q "complexity.*2\|complexity >= 2\|>= 2" "${CLAUDE_PLUGIN_ROOT}/commands/crew/execute.md" && echo "PASS: Complexity threshold found"
```

Expected: `PASS: Complexity threshold found`

### 4. traceability_generator.py generates matrix from test-strategy directory

```bash
# Create minimal test-strategy phase directory for testing
mkdir -p /tmp/tdd-test-scenario/phases/test-strategy
cat > /tmp/tdd-test-scenario/phases/test-strategy/test-strategy.md << 'STRATEGY'
# Test Strategy

## Acceptance Criteria

| ID | Criterion | Test File |
|----|-----------|-----------|
| AC-001 | User can log in with valid credentials | tests/auth/test_login.py |
| AC-002 | Invalid login returns 401 | tests/auth/test_login.py |
| AC-003 | Session expires after 30 minutes | tests/auth/test_session.py |
STRATEGY

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability_generator.py" \
  --phases-dir /tmp/tdd-test-scenario/phases \
  --output /tmp/tdd-test-scenario/phases/build/traceability-matrix.md \
  --dry-run 2>&1 | head -20 && echo "PASS: traceability_generator.py ran without error"
```

Expected: Output shows criteria discovery and `PASS: traceability_generator.py ran without error`

### 5. traceability_generator.py produces markdown table with correct columns

```bash
mkdir -p /tmp/tdd-test-scenario/phases/test-strategy /tmp/tdd-test-scenario/phases/build
cat > /tmp/tdd-test-scenario/phases/test-strategy/test-strategy.md << 'STRATEGY'
# Test Strategy

## Acceptance Criteria
| ID | Criterion | Test File |
|----|-----------|-----------|
| AC-001 | User can log in | tests/auth/test_login.py |
| AC-002 | Password reset works | tests/auth/test_reset.py |
STRATEGY

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability_generator.py" \
  --phases-dir /tmp/tdd-test-scenario/phases \
  --output /tmp/tdd-test-scenario/phases/build/traceability-matrix.md

cat /tmp/tdd-test-scenario/phases/build/traceability-matrix.md | python3 -c "
import sys
content = sys.stdin.read()
print('Content preview:', content[:500])
required_cols = ['Criterion ID', 'Description', 'Test File', 'Build Task', 'Status']
for col in required_cols:
    assert col in content, f'Missing column: {col}'
print('PASS: All required columns present in traceability matrix')
"
```

Expected: `PASS: All required columns present in traceability matrix`

### 6. evidence-taxonomy.md exists with required table

```bash
python3 -c "
import os
path = os.environ.get('CLAUDE_PLUGIN_ROOT', '${CLAUDE_PLUGIN_ROOT}') + '/skills/qe/qe-strategy/refs/evidence-taxonomy.md'
with open(path) as f:
    content = f.read()
required = ['visual', 'payload', 'logging', 'test results', 'code diff', 'performance']
missing = [r for r in required if r.lower() not in content.lower()]
assert not missing, f'Missing evidence types: {missing}'
print('PASS: evidence-taxonomy.md contains all required evidence types')
"
```

Expected: `PASS: evidence-taxonomy.md contains all required evidence types`

### 7. evidence-taxonomy.md has "when required" column

```bash
grep -i "when.*required\|required.*when\|required for" "${CLAUDE_PLUGIN_ROOT}/skills/qe/qe-strategy/refs/evidence-taxonomy.md" && echo "PASS: When required column present"
```

Expected: `PASS: When required column present`

### 8. traceability_generator.py --help shows expected options

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability_generator.py" --help
```

Expected: Help output showing `--phases-dir`, `--output`, `--project` options

## Expected Outcome

### execute.md build phase additions
- TDD coach dispatch instruction for tasks with complexity >= 2
- Three-step pattern documented: red phase (tdd-coach) → green phase (implementer) → refactor verification (tdd-coach)
- For tasks with complexity < 2: TDD guidance included in implementer prompt

### traceability_generator.py
- Reads test-strategy deliverables from `phases/test-strategy/`
- Maps acceptance criteria to tasks via TaskList metadata
- Outputs `phases/build/traceability-matrix.md` as markdown table
- Columns: Criterion ID | Description | Test File/Scenario | Build Task | Status

### evidence-taxonomy.md
- Table with evidence types: visuals, payloads, logging, test results, code diff, performance
- When each type is required (complexity level or gate type)
- Located at `skills/qe/qe-strategy/refs/evidence-taxonomy.md`

## Success Criteria

### execute.md
- [ ] TDD coach dispatch referenced for complexity >= 2 tasks
- [ ] Red-green-refactor phases described
- [ ] Low complexity (< 2) TDD guidance in implementer prompt instead

### traceability_generator.py
- [ ] Reads phases/test-strategy/ directory
- [ ] Outputs markdown table with 5 required columns
- [ ] --phases-dir, --output, --dry-run CLI options work
- [ ] Runs without error even with minimal test-strategy file

### evidence-taxonomy.md
- [ ] All 6 evidence types covered (visual, payload, logging, test results, code diff, performance)
- [ ] "When required" guidance present for each type
- [ ] File exists at skills/qe/qe-strategy/refs/evidence-taxonomy.md

## Value Demonstrated

Without TDD enforcement, implementation happens before tests exist, making test coverage an afterthought and regression detection unreliable. With the red-green-refactor cycle enforced through dispatcher instructions, every build task starts with failing tests (red), implements to pass them (green), and verifies clean refactoring — producing verifiable, test-backed artifacts. The traceability matrix closes the loop by mapping acceptance criteria from the test-strategy phase to completed build tasks.
