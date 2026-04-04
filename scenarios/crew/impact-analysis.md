---
name: impact-analysis
title: Cross-Phase Impact Analysis
description: Verify impact_analyzer.py CLI traces direct and transitive impacts, classifies risk, and handles edge cases
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Cross-Phase Impact Analysis

This scenario verifies that `impact_analyzer.py` correctly analyzes cross-phase impacts:
tracing direct and transitive dependencies from a source artifact, classifying risk levels,
reporting affected phases, supporting depth-limited analysis, handling nonexistent sources,
and producing valid JSON under all conditions.

## Setup

```bash
# Clean slate
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" delete --project test-impact 2>/dev/null || true

# Create a chain: req-1 -> design-1 -> task-1 -> test-1
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id req-1 --source-type requirement \
  --target-id design-1 --target-type design \
  --link-type TRACES_TO --project test-impact --created-by setup

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id design-1 --source-type design \
  --target-id task-1 --target-type code \
  --link-type IMPLEMENTED_BY --project test-impact --created-by setup

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id task-1 --source-type code \
  --target-id test-1 --target-type test \
  --link-type TESTED_BY --project test-impact --created-by setup

# Verify impact_analyzer.py is available
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" --help > /dev/null 2>&1 \
  && echo "impact_analyzer.py available" || echo "NOT FOUND"
```

## Steps

### 1. Analyze from requirement

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" analyze \
  --source-id req-1 --project test-impact \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('impacts', d.get('affected', d.get('direct', [])))
all_ids = []
for item in items if isinstance(items, list) else []:
    all_ids.append(item.get('id', item.get('target_id', '')))
# Also check transitive
transitive = d.get('transitive', [])
for item in transitive if isinstance(transitive, list) else []:
    all_ids.append(item.get('id', item.get('target_id', '')))
print('ALL_IDS:', sorted(set(all_ids)))
print('HAS_DESIGN:', any('design-1' in str(i) for i in all_ids))
print('HAS_TASK:', any('task-1' in str(i) for i in all_ids))
print('HAS_TEST:', any('test-1' in str(i) for i in all_ids))
print('VALID_JSON: True')
"
```

**Expected**: Impact report includes design-1 (direct), task-1 and test-1 (transitive). `VALID_JSON: True`.

### 2. Risk classification

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" analyze \
  --source-id req-1 --project test-impact \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
risk = d.get('risk_summary', d.get('risk', {}))
level = risk.get('risk_level', risk.get('level', 'unknown'))
print('RISK_LEVEL:', level)
print('NOT_NONE:', level != 'none')
"
```

**Expected**: `NOT_NONE: True`. With 3+ affected items, risk should be medium or higher.

### 3. Phases affected

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" analyze \
  --source-id req-1 --project test-impact \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
phases = d.get('phases_affected', d.get('phases', []))
print('PHASES:', sorted(phases) if isinstance(phases, list) else phases)
print('MULTI_PHASE:', len(phases) > 1 if isinstance(phases, list) else False)
"
```

**Expected**: `MULTI_PHASE: True` (design, build/code, and test phases affected).

### 4. Shallow analysis

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" analyze \
  --source-id req-1 --project test-impact --depth 1 \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
# With depth=1, should only see direct impacts (design-1), not transitive
items = d.get('impacts', d.get('affected', d.get('direct', [])))
all_ids = []
for item in items if isinstance(items, list) else []:
    all_ids.append(item.get('id', item.get('target_id', '')))
print('IDS:', sorted(set(all_ids)))
print('HAS_DESIGN:', any('design-1' in str(i) for i in all_ids))
# task-1 should not appear at depth 1 (it is 2 hops away)
transitive = d.get('transitive', [])
trans_ids = [item.get('id', item.get('target_id', '')) for item in transitive if isinstance(transitive, list)]
print('TRANSITIVE_COUNT:', len(trans_ids))
"
```

**Expected**: `HAS_DESIGN: True`. Transitive items should be fewer than full-depth analysis.

### 5. No impacts

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" analyze \
  --source-id nonexistent --project test-impact \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('impacts', d.get('affected', d.get('direct', [])))
risk = d.get('risk_summary', d.get('risk', {}))
level = risk.get('risk_level', risk.get('level', 'unknown'))
count = len(items) if isinstance(items, list) else 0
print('EMPTY:', count == 0)
print('RISK_LEVEL:', level)
print('VALID_JSON: True')
"
```

**Expected**: `EMPTY: True`, `RISK_LEVEL: none`, `VALID_JSON: True`.

### 6. Graceful degradation

```bash
# Run analysis against a project with no knowledge graph data
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/impact_analyzer.py" analyze \
  --source-id req-1 --project nonexistent-project \
  | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('VALID_JSON: True')
except:
    print('VALID_JSON: False')
"
echo "Exit: $?"
```

**Expected**: `VALID_JSON: True`. The analyzer produces valid JSON even with no data.

## Success Criteria

- [ ] Full-depth analysis finds direct (design-1) and transitive (task-1, test-1) impacts
- [ ] Risk classification is not "none" when 3+ artifacts are affected
- [ ] Multiple phases reported as affected
- [ ] Depth=1 limits results to direct impacts only
- [ ] Nonexistent source returns empty impacts with risk_level "none"
- [ ] Valid JSON returned even when project has no traceability data

## Cleanup

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" delete --project test-impact 2>/dev/null || true
```
