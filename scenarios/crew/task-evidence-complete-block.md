---
name: task-evidence-complete-block
title: Task Evidence Completeness Block
description: Verify that completed tasks include required evidence fields and that evidence validation catches missing items by complexity level
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# Task Evidence Completeness Block

This scenario validates that `scripts/crew/evidence.py` correctly validates task completion evidence against complexity-level requirements, and that `implementer.md` prompts agents to provide structured evidence in their task outcomes.

## Setup

No special setup needed. Uses `evidence.py` directly.

```bash
python3 -c "from scripts.crew.evidence import validate_evidence; print('evidence.py importable')" 2>/dev/null || \
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/evidence.py" --help > /dev/null 2>&1 && echo "evidence.py available"
```

## Steps

### 1. Low complexity (score 1-2): requires code_diff + test_results

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import validate_evidence

# Minimal passing evidence for low complexity
task_desc = '''## Outcome
Fixed the null pointer in user_service.py line 42.

## Evidence
- Test: test_user_service.py::test_get_user — PASS
- File: src/user_service.py — modified
- Code diff: removed None check at line 42, replaced with Optional type

## Assumptions
- Only affects internal callers, no API contract changes
'''

result = validate_evidence(task_desc, complexity_score=2)
print('valid:', result['valid'])
print('missing:', result['missing'])
print('warnings:', result['warnings'])
assert result['valid'], f'Expected valid but got missing: {result[\"missing\"]}'
print('PASS: Low complexity evidence accepted')
"
```

Expected: `PASS: Low complexity evidence accepted`

### 2. Low complexity: missing evidence fields blocked

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import validate_evidence

# Missing test results and code diff
task_desc = '''## Outcome
Fixed the null pointer in user_service.py line 42.

## Evidence
- File: src/user_service.py — modified
'''

result = validate_evidence(task_desc, complexity_score=2)
print('valid:', result['valid'])
print('missing:', result['missing'])
assert not result['valid'], 'Expected invalid but got valid'
assert any('test' in m.lower() or 'code' in m.lower() for m in result['missing']), f'Missing should mention test or code, got: {result[\"missing\"]}'
print('PASS: Missing evidence detected for complexity 2')
"
```

Expected: `PASS: Missing evidence detected for complexity 2`

### 3. Medium complexity (score 3-4): requires code_diff + test_results + verification

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import validate_evidence

# Has code diff + tests but missing verification step
task_desc = '''## Outcome
Refactored auth middleware to support OAuth2 flows.

## Evidence
- Test: tests/auth/test_oauth.py — PASS
- File: src/middleware/auth.py — modified
- Code diff: extracted token validation into separate function

## Assumptions
- OAuth2 is the primary auth path for external clients
'''

result = validate_evidence(task_desc, complexity_score=4)
print('valid:', result['valid'])
print('missing:', result['missing'])
assert not result['valid'], 'Expected invalid (missing verification)'
assert any('verif' in m.lower() for m in result['missing']), f'Expected verification missing, got: {result[\"missing\"]}'
print('PASS: Verification required for complexity 4')
"
```

Expected: `PASS: Verification required for complexity 4`

### 4. Medium complexity: full evidence passes

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import validate_evidence

# Complete medium complexity evidence
task_desc = '''## Outcome
Refactored auth middleware to support OAuth2 flows.

## Evidence
- Test: tests/auth/test_oauth.py — PASS
- File: src/middleware/auth.py — modified
- Code diff: extracted token validation into separate function
- Verification: curl -X POST /auth/token returns 200 with valid JWT

## Assumptions
- OAuth2 is the primary auth path for external clients
'''

result = validate_evidence(task_desc, complexity_score=4)
print('valid:', result['valid'])
print('missing:', result['missing'])
assert result['valid'], f'Expected valid but got missing: {result[\"missing\"]}'
print('PASS: Full medium complexity evidence accepted')
"
```

Expected: `PASS: Full medium complexity evidence accepted`

### 5. High complexity (score 5+): requires performance + assumptions

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import validate_evidence

# High complexity missing performance data
task_desc = '''## Outcome
Implemented distributed caching layer across all microservices.

## Evidence
- Test: tests/cache/test_distributed.py — PASS
- File: src/cache/distributed.py — created
- Code diff: added Redis cluster client with consistent hashing
- Verification: cache hit rate 94% in staging environment

## Assumptions
- Redis cluster is pre-provisioned in production
'''

result = validate_evidence(task_desc, complexity_score=6)
print('valid:', result['valid'])
print('missing:', result['missing'])
assert not result['valid'], 'Expected invalid (missing performance metrics)'
assert any('perf' in m.lower() or 'benchmark' in m.lower() or 'metric' in m.lower() for m in result['missing']), f'Expected performance missing, got: {result[\"missing\"]}'
print('PASS: Performance metrics required for complexity 6')
"
```

Expected: `PASS: Performance metrics required for complexity 6`

### 6. High complexity: complete evidence passes

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import validate_evidence

# Full high complexity evidence
task_desc = '''## Outcome
Implemented distributed caching layer across all microservices.

## Evidence
- Test: tests/cache/test_distributed.py — PASS
- File: src/cache/distributed.py — created
- Code diff: added Redis cluster client with consistent hashing
- Verification: cache hit rate 94% in staging environment
- Performance: p99 latency dropped from 450ms to 80ms under 1000 RPS load
- Benchmark: redis-benchmark reports 95k ops/sec throughput

## Assumptions
- Redis cluster is pre-provisioned in production
- Cluster failover tested with 2/3 nodes healthy
'''

result = validate_evidence(task_desc, complexity_score=6)
print('valid:', result['valid'])
print('missing:', result['missing'])
assert result['valid'], f'Expected valid but got missing: {result[\"missing\"]}'
print('PASS: High complexity evidence accepted')
"
```

Expected: `PASS: High complexity evidence accepted`

### 7. EVIDENCE_SCHEMA is exported and inspectable

```bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/crew')
from evidence import EVIDENCE_SCHEMA
assert isinstance(EVIDENCE_SCHEMA, dict), 'EVIDENCE_SCHEMA should be a dict'
assert 'low' in EVIDENCE_SCHEMA, 'Should have low complexity schema'
assert 'medium' in EVIDENCE_SCHEMA, 'Should have medium complexity schema'
assert 'high' in EVIDENCE_SCHEMA, 'Should have high complexity schema'
print('PASS: EVIDENCE_SCHEMA exported correctly')
print('Schema:', EVIDENCE_SCHEMA)
"
```

Expected: `PASS: EVIDENCE_SCHEMA exported correctly`

### 8. Implementer agent prompt contains evidence format section

```bash
grep -l "## Evidence" "${CLAUDE_PLUGIN_ROOT}/agents/crew/implementer.md" && echo "PASS: Evidence section found in implementer.md"
```

Expected: Path to implementer.md printed + `PASS: Evidence section found in implementer.md`

### 9. Reviewer agent prompt contains evidence check section

```bash
grep -l "Evidence" "${CLAUDE_PLUGIN_ROOT}/agents/crew/reviewer.md" && echo "PASS: Evidence check found in reviewer.md"
```

Expected: Path to reviewer.md printed + `PASS: Evidence check found in reviewer.md`

## Expected Outcome

### evidence.py module
- `EVIDENCE_SCHEMA` dict exported with `low`, `medium`, `high` tier schemas
- `validate_evidence(task_description, complexity_score)` returns `{valid: bool, missing: list, warnings: list}`
- Complexity 1-2: requires `code_diff` + `test_results`
- Complexity 3-4: adds `verification` to requirements
- Complexity 5+: adds `performance` + requires `assumptions`

### Agent prompts updated
- `implementer.md` includes structured evidence format with `## Evidence` section
- `reviewer.md` includes evidence check in review process

### Evidence format
```markdown
## Outcome
{what was accomplished}

## Evidence
- Test: {test name} — PASS/FAIL
- File: {path} — created/modified
- Verification: {command output}

## Assumptions
- {assumption and rationale}
```

## Success Criteria

### evidence.py
- [ ] EVIDENCE_SCHEMA exported as dict with low/medium/high tiers
- [ ] validate_evidence() returns valid=True for complete evidence at each tier
- [ ] validate_evidence() returns valid=False with missing list for incomplete evidence
- [ ] Complexity 1-2 requires code_diff + test_results
- [ ] Complexity 3-4 additionally requires verification
- [ ] Complexity 5+ additionally requires performance + assumptions

### Agent prompt updates
- [ ] implementer.md contains "## Evidence" section with format template
- [ ] reviewer.md contains evidence check instructions
- [ ] Evidence format includes: Test, File, Verification, Assumptions fields

## Value Demonstrated

Without structured evidence requirements, completed tasks may lack verifiable proof of correctness. A task marked "completed" with only prose description provides no audit trail for reviewers. With evidence validation, every task completion includes test results, file references, verification commands, and for complex work, performance benchmarks — giving reviewers and future engineers the context they need.
