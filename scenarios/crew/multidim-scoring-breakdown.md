---
name: multidim-scoring-breakdown
title: Multi-Dimensional Complexity Scoring Breakdown
description: Verify smart_decisioning.py computes complexity from all 7 dimensions and exposes breakdown in JSON output
type: unit
difficulty: intermediate
estimated_minutes: 8
---

# Multi-Dimensional Complexity Scoring Breakdown

This scenario validates that `smart_decisioning.py` incorporates four new risk dimensions — `test_complexity`, `documentation`, `coordination`, and `operational` — alongside the original three (impact, reversibility, novelty). The 0-7 complexity scale and all existing behavior must be preserved.

## Setup

No special setup needed. Uses `smart_decisioning.py` directly.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json "test" > /dev/null 2>&1
```

## Steps

### 1. Baseline: Simple change shows zero new dimensions

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json "Fix a typo in README.md"
```

Expected:
1. `complexity_score` is 0 (same as pre-change behavior)
2. JSON output includes `complexity_breakdown` with `test_complexity`, `documentation`, `coordination_cost`, and `operational` keys
3. All four new keys are 0 for a trivial change

### 2. Test complexity signal: integration test setup

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Add end-to-end tests using Playwright with test fixtures, mock services, and CI pipeline integration for the checkout flow"
```

Expected:
1. `complexity_breakdown.test_complexity` >= 1 (test scope detected)
2. `normalized_dimensions` includes `test_complexity` key
3. Complexity score reflects test setup cost

### 3. Documentation signal: API docs + ADR needed

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Redesign the public API contract. Update OpenAPI spec, write ADR, and create migration guide for consumers"
```

Expected:
1. `complexity_breakdown.documentation` >= 1 (API docs + ADR detected)
2. `normalized_dimensions.documentation` > 0
3. Overall complexity increased compared to "Fix a typo"

### 4. Coordination signal: cross-domain handoffs

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Coordinate with platform team and QE specialist to implement auth changes across all microservices. Requires security review and cross-team sign-off"
```

Expected:
1. `complexity_breakdown.coordination_cost` >= 1 (cross-team, specialist handoffs detected)
2. `normalized_dimensions.coordination_cost` > 0
3. Complexity score >= 3

### 5. Operational signal: deployment + migration

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Perform zero-downtime database migration with rollback plan. Requires deployment window, blue-green switch, and ops monitoring"
```

Expected:
1. `complexity_breakdown.operational` >= 1 (deployment + migration + rollback detected)
2. `normalized_dimensions.operational` > 0
3. `complexity_score` reflects operational cost

### 6. All dimensions active simultaneously

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Implement GDPR data deletion pipeline: write integration tests with fixtures, document the API and publish ADR, coordinate with platform and legal teams for review, deploy with migration script and rollback plan"
```

Expected:
1. All 7 dimensions are non-zero in `complexity_breakdown`
2. `complexity_score` == 7 (maximum, all dimensions saturated)
3. `normalized_dimensions` exposes all 7 dimensions
4. `complexity_breakdown` present in JSON output with labeled keys

### 7. Backward compatibility: no regression on existing inputs

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Modify the plugin scoring engine, execution workflow, and dispatch routing for all crew commands"
```

Expected:
1. `complexity_score` >= 3 (same as before new dimensions)
2. Existing breakdown keys (impact, risk_premium, scope, coordination) still present
3. New dimension keys added alongside, not replacing, existing keys
4. No exceptions or missing fields in JSON output

### 8. JSON schema validation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json "Add auth middleware" | python3 -c "
import json, sys
data = json.load(sys.stdin)
required_breakdown = {'impact', 'risk_premium', 'scope', 'coordination', 'test_complexity', 'documentation', 'coordination_cost', 'operational'}
missing = required_breakdown - set(data.get('complexity_breakdown', {}).keys())
assert not missing, f'Missing breakdown keys: {missing}'
required_normalized = {'test_complexity', 'documentation', 'coordination_cost', 'operational'}
missing_norm = required_normalized - set(data.get('normalized_dimensions', {}).keys())
assert not missing_norm, f'Missing normalized_dimensions keys: {missing_norm}'
print('PASS: All required keys present')
"
```

Expected: `PASS: All required keys present`

## Expected Outcome

### Backward compatible
- All existing `complexity_breakdown` keys preserved (impact, risk_premium, scope, coordination)
- Complexity 0-7 scale unchanged
- Existing test inputs produce same or higher scores (new dimensions ADD signal, never inflate baseline for irrelevant inputs)

### New dimensions exposed
- `test_complexity` (0-3): detects test strategy scope, integration test setup, CI needs
- `documentation` (0-3): detects API docs, user guides, ADR requirements
- `coordination_cost` (0-3): detects cross-domain deps, specialist handoffs, review requirements
- `operational` (0-3): detects deployment, migration, rollback requirements

### Scoring accuracy
- Simple changes remain low complexity
- Multi-dimensional changes score proportionally higher
- Maximum complexity (7) is achievable when all dimensions are saturated

## Success Criteria

### New Dimensions Present
- [ ] `test_complexity` key in `complexity_breakdown` JSON output
- [ ] `documentation` key in `complexity_breakdown` JSON output
- [ ] `coordination_cost` key in `complexity_breakdown` JSON output
- [ ] `operational` key in `complexity_breakdown` JSON output

### Keyword Detection Works
- [ ] "end-to-end tests", "test fixtures", "CI pipeline" raise `test_complexity`
- [ ] "OpenAPI spec", "ADR", "migration guide" raise `documentation`
- [ ] "coordinate with", "cross-team", "specialist review" raise `coordination_cost`
- [ ] "deployment", "migration script", "rollback plan" raise `operational`

### Backward Compatibility
- [ ] "Fix a typo" still scores 0 with all new dimensions at 0
- [ ] Infrastructure-framework archetype still hits complexity >= 3
- [ ] No JSON schema regressions (existing keys still present)

### Normalized Dimensions
- [ ] `normalized_dimensions` includes `test_complexity`, `documentation`, `coordination_cost`, `operational`
- [ ] Each normalized value is in [0.0, 1.0]

## Value Demonstrated

Without multi-dimensional scoring, a change requiring extensive test setup, API documentation, cross-team coordination, and operational deployment planning scores the same as a single-file code change of similar word count. This leads to under-resourcing and missed planning. With all 7 dimensions, the scoring accurately reflects the full effort cost of a change.
