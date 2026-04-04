---
name: phase-aware-recall
title: Phase-Aware Memory Recall Scoring
description: Verify phase_scoring.py boosts, scores, and filters memories by crew phase affinity
type: unit
difficulty: intermediate
estimated_minutes: 8
---

# Phase-Aware Memory Recall Scoring

Validates that `phase_scoring.py` correctly applies phase affinity boosts to memories, scores and sorts them for a given active phase, filters by phase, and handles edge cases like null phases and missing fields.

## Setup

Create test memory records as JSON:

```bash
cat > "${TMPDIR:-/tmp}/memories.json" <<'EOF'
[
  {"id": "m1", "content": "Auth must use OAuth2", "type": "decision", "phase": "design", "importance": 8},
  {"id": "m2", "content": "Use PostgreSQL for persistence", "type": "decision", "phase": "clarify", "importance": 5},
  {"id": "m3", "content": "Run load tests before deploy", "type": "procedural", "phase": "test", "importance": 7},
  {"id": "m4", "content": "Brainstorm session notes", "type": "episodic", "phase": "ideate", "importance": 3},
  {"id": "m5", "content": "No phase memory", "type": "decision", "importance": 5}
]
EOF
```

## Steps

### 1. Phase boost calculation (high affinity)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" boost --memory-phase design --active-phase build
```

**Expected**: Returns `{"boost": 1.5}` because design memories have high affinity during the build phase (design is in build's "high" list).

### 2. Phase boost calculation (low affinity)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" boost --memory-phase ideate --active-phase build
```

**Expected**: Returns `{"boost": 0.7}` because ideate memories have low affinity during the build phase.

### 3. Null safety (empty active phase)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" boost --memory-phase design --active-phase ""
```

**Expected**: Returns `{"boost": 1.0}` because no active phase means neutral boost (backward compatible behavior).

### 4. Score memories in build phase

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" score --phase build < "${TMPDIR:-/tmp}/memories.json" | python3 -c "
import json, sys
memories = json.load(sys.stdin)
ids_in_order = [m['id'] for m in memories]
assert '_phase_boost' in memories[0], 'Missing _phase_boost field'
assert '_phase_score' in memories[0], 'Missing _phase_score field'
# design (m1) should be boosted highest: importance 8 * 1.5 = 12
# clarify (m2) should also be high: importance 5 * 1.5 = 7.5
# ideate (m4) should be lowest: importance 3 * 0.7 = 2.1
assert memories[0]['id'] == 'm1', 'Expected m1 first, got %s' % memories[0]['id']
assert memories[-1]['id'] == 'm4', 'Expected m4 last, got %s' % memories[-1]['id']
print('PASS: Memories scored and sorted correctly for build phase')
print('Order: %s' % ids_in_order)
"
```

**Expected**: Design memory (m1) ranked highest with `_phase_boost` = 1.5 and `_phase_score` = 12.0. Ideate memory (m4) ranked lowest with `_phase_boost` = 0.7. All memories have both `_phase_boost` and `_phase_score` fields.

### 5. Filter memories by phase

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" filter --phase design < "${TMPDIR:-/tmp}/memories.json" | python3 -c "
import json, sys
result = json.load(sys.stdin)
assert len(result) == 1, 'Expected 1 memory, got %d' % len(result)
assert result[0]['id'] == 'm1', 'Expected m1, got %s' % result[0]['id']
print('PASS: Filter returned only design-phase memory')
"
```

**Expected**: Returns only m1 (the only memory with `phase` = "design"). Prints PASS.

### 6. Review phase applies neutral boost

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" score --phase review < "${TMPDIR:-/tmp}/memories.json" | python3 -c "
import json, sys
memories = json.load(sys.stdin)
for m in memories:
    assert m['_phase_boost'] == 1.0, 'Expected 1.0 boost in review phase for %s, got %s' % (m['id'], m['_phase_boost'])
print('PASS: Review phase gives 1.0x boost to all memories')
"
```

**Expected**: All memories get `_phase_boost` = 1.0 in the review phase (review has empty high/medium/low lists, so everything is neutral). Prints PASS.

### 7. Memory without phase field gets neutral boost

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" score --phase build < "${TMPDIR:-/tmp}/memories.json" | python3 -c "
import json, sys
memories = json.load(sys.stdin)
m5 = [m for m in memories if m['id'] == 'm5'][0]
assert m5['_phase_boost'] == 1.0, 'Expected 1.0 boost for phaseless memory, got %s' % m5['_phase_boost']
print('PASS: Phaseless memory (m5) gets neutral 1.0x boost')
"
```

**Expected**: Memory m5 (no phase field) gets `_phase_boost` = 1.0 in any active phase. It is not penalized. Prints PASS.

### 8. Detect active phase

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/phase_scoring.py" detect-phase | python3 -c "
import json, sys
result = json.load(sys.stdin)
assert 'phase' in result, 'Missing phase key in output'
print('PASS: detect-phase returned JSON with phase key (value: %s)' % result['phase'])
"
```

**Expected**: Returns JSON with a `phase` key. The value may be `null` if no crew project is active (that is acceptable). Prints PASS.

## Success Criteria

- [ ] High affinity boost returns 1.5 (design in build phase)
- [ ] Low affinity boost returns 0.7 (ideate in build phase)
- [ ] Empty active phase returns neutral 1.0 boost
- [ ] Score command sorts memories by phase-weighted score descending
- [ ] All scored memories have `_phase_boost` and `_phase_score` fields
- [ ] Filter command returns only memories matching the specified phase
- [ ] Review phase applies 1.0x neutral boost to all memories
- [ ] Memories without a phase field get 1.0x neutral boost (backward compatible)
- [ ] detect-phase returns valid JSON (null phase is acceptable)

## Cleanup

```bash
rm -f "${TMPDIR:-/tmp}/memories.json"
```
