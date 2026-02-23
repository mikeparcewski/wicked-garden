---
name: acceptance-testing-pipeline
title: Evidence-Gated Acceptance Testing Pipeline
description: Test the three-agent Write → Execute → Review acceptance testing pipeline
type: testing
difficulty: advanced
estimated_minutes: 15
---

# Evidence-Gated Acceptance Testing Pipeline

This scenario validates that wicked-qe's acceptance testing pipeline correctly separates test writing, execution, and review — and that the separation catches issues that self-grading would miss.

## Setup

Create a simple feature with a known bug to verify the pipeline catches it:

```bash
# Create test project with a deliberately buggy feature
mkdir -p ~/test-wicked-qe/acceptance-test
cd ~/test-wicked-qe/acceptance-test

# Create a "calculator" with a known bug (multiply is wrong)
mkdir -p src
cat > src/calc.py << 'EOF'
"""Simple calculator with a deliberate bug for testing."""

def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b

def multiply(a: int, b: int) -> int:
    return a + b  # BUG: should be a * b

def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
EOF

# Create a scenario that exercises all operations
cat > scenario-calc.md << 'SCENARIO'
---
name: calculator-ops
title: Calculator Operations
description: Verify all calculator operations work correctly
type: testing
difficulty: basic
estimated_minutes: 5
---

# Calculator Operations

Verify that the calculator module handles basic operations correctly.

## Setup

```bash
cd ~/test-wicked-qe/acceptance-test
```

## Steps

### 1. Test addition

```bash
python3 -c "from src.calc import add; print(f'result={add(3, 4)}')"
```

**Expected**: Output shows result=7

### 2. Test subtraction

```bash
python3 -c "from src.calc import subtract; print(f'result={subtract(10, 3)}')"
```

**Expected**: Output shows result=7

### 3. Test multiplication

```bash
python3 -c "from src.calc import multiply; print(f'result={multiply(3, 4)}')"
```

**Expected**: Output shows result=12

### 4. Test division by zero

```bash
python3 -c "
from src.calc import divide
try:
    divide(10, 0)
    print('ERROR: no exception raised')
except ValueError as e:
    print(f'caught={e}')
"
```

**Expected**: Output shows caught=Cannot divide by zero

## Success Criteria

- [ ] Addition returns correct sum
- [ ] Subtraction returns correct difference
- [ ] Multiplication returns correct product
- [ ] Division by zero raises ValueError with message
SCENARIO
```

## Steps

### 1. Generate Test Plan (Write Phase)

```bash
/wicked-qe:acceptance scenario-calc.md --phase write
```

**Expected**: Test plan is generated with:
- Evidence requirements for each step (stdout capture)
- Concrete assertions (CONTAINS "result=7", CONTAINS "result=12")
- A specification note about the multiply bug (writer reads calc.py and sees `a + b` instead of `a * b`)
- Acceptance criteria map covering all four success criteria

### 2. Execute Test Plan (Execute Phase)

```bash
/wicked-qe:acceptance scenario-calc.md --phase execute --plan <test-plan-from-step-1>
```

**Expected**: Evidence report with:
- stdout captured for each step
- Step 3 (multiply) shows result=7 instead of result=12
- No judgment about pass/fail — just raw evidence

### 3. Review Evidence (Review Phase)

```bash
/wicked-qe:acceptance scenario-calc.md --phase review --plan <test-plan> --evidence <evidence-report>
```

**Expected**: Reviewer produces verdict with:
- STEP-1 (add): PASS — evidence shows result=7
- STEP-2 (subtract): PASS — evidence shows result=7
- STEP-3 (multiply): FAIL — evidence shows result=7, assertion expected result=12
- STEP-4 (divide by zero): PASS — evidence shows caught=Cannot divide by zero
- Overall: FAIL
- Failure cause: IMPLEMENTATION_BUG for multiply

### 4. Run Full Pipeline

```bash
/wicked-qe:acceptance scenario-calc.md
```

**Expected**: Full Write → Execute → Review pipeline runs end-to-end, producing:
- Test plan with specification note about the multiply bug
- Evidence with actual outputs
- Verdict showing multiply FAIL with IMPLEMENTATION_BUG cause

## Expected Outcome

```markdown
## Acceptance Test Results: calculator-ops

### Verdict: FAIL

### Specification Notes
Writer detected that `multiply()` in `src/calc.py` implements `a + b`
instead of `a * b`. This was flagged before execution began.

### Acceptance Criteria
| Criterion | Verdict | Evidence |
|-----------|---------|----------|
| Addition returns correct sum | PASS | stdout: "result=7" |
| Subtraction returns correct difference | PASS | stdout: "result=7" |
| Multiplication returns correct product | FAIL | stdout: "result=7", expected "result=12" |
| Division by zero raises ValueError | PASS | stdout: "caught=Cannot divide by zero" |

### Step Results
| Step | Assertions | Passed | Failed | Verdict |
|------|------------|--------|--------|---------|
| STEP-1 | 2 | 2 | 0 | PASS |
| STEP-2 | 2 | 2 | 0 | PASS |
| STEP-3 | 2 | 1 | 1 | FAIL |
| STEP-4 | 2 | 2 | 0 | PASS |

### Failures
- **STEP-3**: `step-3-output` CONTAINS "result=12" — Expected "result=12"
  in stdout, found "result=7". Cause: IMPLEMENTATION_BUG — `multiply()`
  computes `a + b` instead of `a * b` in src/calc.py line 10.
```

## Success Criteria

- [ ] Write phase produces structured test plan with evidence requirements
- [ ] Write phase reads implementation and flags the multiply bug as specification note
- [ ] Execute phase captures stdout for all four steps without judgment
- [ ] Execute phase records result=7 for multiply (the actual bug output)
- [ ] Review phase correctly evaluates assertions against evidence
- [ ] Review phase marks multiply step as FAIL
- [ ] Review phase attributes cause as IMPLEMENTATION_BUG
- [ ] Full pipeline produces end-to-end verdict with all three phases
- [ ] Writer catches the bug BEFORE execution (specification note)
- [ ] Reviewer independently confirms the bug from evidence alone

## Value Demonstrated

**Problem solved**: Self-grading acceptance tests have 80%+ false positive rate on non-trivial criteria. An executor that ran `multiply(3,4)` and got `7` might self-grade as "command executed successfully = PASS." The three-agent pipeline catches this because:

1. The **writer** reads `calc.py` and flags `a + b` vs `a * b` before any test runs
2. The **executor** records `result=7` without knowing it's wrong
3. The **reviewer** compares `result=7` against assertion `CONTAINS "result=12"` → FAIL

No single agent could reliably catch all three failure modes. The separation of concerns is the mechanism.

## Cleanup

```bash
rm -rf ~/test-wicked-qe/acceptance-test
```
