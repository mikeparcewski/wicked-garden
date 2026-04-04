---
name: lifecycle-scoring
title: Lifecycle Scoring Pipeline
description: Verify lifecycle_scoring.py scores items by phase affinity, recency, gate status, and combined pipeline
type: unit
difficulty: intermediate
estimated_minutes: 8
---

# Lifecycle Scoring Pipeline

Validates that `lifecycle_scoring.py` correctly applies composable scorers (phase_weighted, recency_decay, gate_status) individually and in combination, producing sorted output with score breakdowns.

## Setup

Create a JSON file with test items spanning different types, states, and ages:

```bash
cat > "${TMPDIR:-/tmp}/items.json" <<'EOF'
[
  {"id": "item-1", "type": "design", "state": "APPROVED", "created_at": "2026-04-03T10:00:00Z"},
  {"id": "item-2", "type": "requirement", "state": "DRAFT", "created_at": "2026-01-01T10:00:00Z"},
  {"id": "item-3", "type": "test_strategy", "state": "VERIFIED", "created_at": "2026-04-04T08:00:00Z"},
  {"id": "item-4", "type": "evidence", "state": "IN_REVIEW", "created_at": "2026-03-15T10:00:00Z"}
]
EOF
```

## Steps

### 1. Phase-weighted scoring in build phase

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --phase build --scorers phase_weighted < "${TMPDIR:-/tmp}/items.json"
```

**Expected**: Design items (item-1) get 1.5x boost in build phase. Requirement items (item-2) get 1.3x. Output is sorted by `_score` descending. Each item has `_score_breakdown.phase_weighted` reflecting the multiplier.

### 2. Recency decay scoring

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --scorers recency_decay < "${TMPDIR:-/tmp}/items.json"
```

**Expected**: Recent items (item-3, created today) score higher than old items (item-2, created months ago). Each item has `_score_breakdown.recency_decay` between 0 and 1. Output is sorted by `_score` descending.

### 3. Gate status multiplier

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --scorers gate_status < "${TMPDIR:-/tmp}/items.json"
```

**Expected**: APPROVED (item-1) gets 1.3x, DRAFT (item-2) gets 0.7x, VERIFIED (item-3) gets 1.4x, IN_REVIEW (item-4) gets 1.0x. Verify via `_score_breakdown.gate_status` on each item.

### 4. Combined pipeline with all three scorers

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --phase test --scorers phase_weighted,recency_decay,gate_status < "${TMPDIR:-/tmp}/items.json"
```

**Expected**: Each item has `_score_breakdown` containing keys `phase_weighted`, `recency_decay`, and `gate_status`. The `_score` reflects the product of all three multipliers. Output is sorted descending.

### 5. Score breakdown tracking in combined output

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --phase test --scorers phase_weighted,recency_decay,gate_status < "${TMPDIR:-/tmp}/items.json" | python3 -c "
import json, sys
items = json.load(sys.stdin)
for item in items:
    bd = item.get('_score_breakdown', {})
    assert 'phase_weighted' in bd, 'Missing phase_weighted in %s' % item['id']
    assert 'recency_decay' in bd, 'Missing recency_decay in %s' % item['id']
    assert 'gate_status' in bd, 'Missing gate_status in %s' % item['id']
print('PASS: All items have complete score breakdowns')
"
```

**Expected**: Prints `PASS: All items have complete score breakdowns`.

### 6. Default scorers (no --scorers flag)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --phase build < "${TMPDIR:-/tmp}/items.json" | python3 -c "
import json, sys
items = json.load(sys.stdin)
bd_keys = set()
for item in items:
    bd_keys.update(item.get('_score_breakdown', {}).keys())
assert 'phase_weighted' in bd_keys, 'Default scorers missing phase_weighted'
assert 'recency_decay' in bd_keys, 'Default scorers missing recency_decay'
assert 'gate_status' in bd_keys, 'Default scorers missing gate_status'
print('PASS: Default scorers applied: %s' % sorted(bd_keys))
"
```

**Expected**: Default scorers include `phase_weighted`, `recency_decay`, `traceability_boost`, and `gate_status`. Prints PASS.

### 7. Empty input returns empty array

```bash
echo '[]' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/search/lifecycle_scoring.py" score --phase build | python3 -c "
import json, sys
result = json.load(sys.stdin)
assert isinstance(result, list), 'Expected list, got %s' % type(result).__name__
assert len(result) == 0, 'Expected empty list, got %d items' % len(result)
print('PASS: Empty input returns empty array')
"
```

**Expected**: Returns `[]` with exit code 0. Prints `PASS: Empty input returns empty array`.

## Success Criteria

- [ ] Phase-weighted scoring boosts design items 1.5x in build phase
- [ ] Recency decay ranks recent items higher than old items
- [ ] Gate status applies correct multipliers (APPROVED=1.3, DRAFT=0.7, VERIFIED=1.4)
- [ ] Combined pipeline produces all three breakdown keys per item
- [ ] Output is always sorted by `_score` descending
- [ ] Default scorers are applied when `--scorers` flag is omitted
- [ ] Empty input produces empty output without errors

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/items.json"
```
