---
name: traceability-links
title: Cross-Phase Traceability Link Management
description: Verify traceability.py CLI creates, walks, reports, filters, and deletes cross-phase links
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Cross-Phase Traceability Link Management

This scenario verifies that `traceability.py` correctly manages cross-phase traceability
links: creating links of all types, walking forward and reverse traces, computing coverage
reports, filtering by link type, rejecting invalid link types, and bulk deletion.

## Setup

```bash
# Verify traceability.py is available
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" --help > /dev/null 2>&1 \
  && echo "traceability.py available" || echo "NOT FOUND"

# Clean slate — delete any leftover links from prior runs
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" delete --project test-trace 2>/dev/null || true
```

## Steps

### 1. Create links across phases

```bash
# req-1 TRACES_TO design-1
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id req-1 --source-type requirement \
  --target-id design-1 --target-type design \
  --link-type TRACES_TO --project test-trace --created-by clarify-phase

# design-1 IMPLEMENTED_BY task-1
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id design-1 --source-type design \
  --target-id task-1 --target-type code \
  --link-type IMPLEMENTED_BY --project test-trace --created-by build-phase

# req-1 TESTED_BY test-1
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id req-1 --source-type requirement \
  --target-id test-1 --target-type test \
  --link-type TESTED_BY --project test-trace --created-by test-phase

# test-1 VERIFIES req-1
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id test-1 --source-type test \
  --target-id req-1 --target-type requirement \
  --link-type VERIFIES --project test-trace --created-by test-phase

# Validate link count
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" list --project test-trace \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('LINK_COUNT:', len(d.get('links', d if isinstance(d, list) else [])))"
```

**Expected**: 4 links created, each returns JSON with source_id, target_id, link_type. `LINK_COUNT: 4`.

### 2. Forward trace from requirement

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" forward \
  --source-id req-1 --project test-trace \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
ids = [n.get('id', n.get('target_id', '')) for n in d.get('trace', d.get('nodes', []))]
print('TRACE_IDS:', sorted(ids))
has_design = any('design-1' in str(i) for i in ids)
print('HAS_DESIGN:', has_design)
"
```

**Expected**: Trace walks from req-1 through design-1 to task-1. `HAS_DESIGN: True`.

### 3. Reverse trace from test

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" reverse \
  --target-id test-1 --project test-trace \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
ids = [n.get('id', n.get('source_id', '')) for n in d.get('trace', d.get('nodes', []))]
has_req = any('req-1' in str(i) for i in ids)
print('WALKS_TO_REQ:', has_req)
"
```

**Expected**: Reverse trace from test-1 walks back to req-1. `WALKS_TO_REQ: True`.

### 4. Coverage report — full coverage

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" coverage \
  --project test-trace \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('TOTAL_REQS:', d.get('total_requirements', 'N/A'))
print('COVERAGE_PCT:', d.get('coverage_pct', 'N/A'))
covered = d.get('covered', [])
print('REQ1_COVERED:', 'req-1' in covered)
"
```

**Expected**: `TOTAL_REQS: 1`, `REQ1_COVERED: True`, `COVERAGE_PCT: 100.0`.

### 5. Coverage gap detection

```bash
# Create a second requirement with no test link
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id req-2 --source-type requirement \
  --target-id design-2 --target-type design \
  --link-type TRACES_TO --project test-trace --created-by clarify-phase

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" coverage \
  --project test-trace \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
pct = d.get('coverage_pct', 100)
gaps = d.get('gaps', d.get('uncovered', []))
print('COVERAGE_DROPPED:', pct < 100)
print('HAS_GAP_REQ2:', 'req-2' in gaps)
"
```

**Expected**: `COVERAGE_DROPPED: True`, `HAS_GAP_REQ2: True`.

### 6. List with filters

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" list \
  --project test-trace --link-type TRACES_TO \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
links = d.get('links', d if isinstance(d, list) else [])
all_traces = all(l.get('link_type') == 'TRACES_TO' for l in links)
print('ALL_TRACES_TO:', all_traces)
print('COUNT:', len(links))
"
```

**Expected**: `ALL_TRACES_TO: True`, `COUNT: 2` (req-1 and req-2 TRACES_TO links).

### 7. Invalid link type rejected

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" create \
  --source-id req-1 --source-type requirement \
  --target-id bogus --target-type design \
  --link-type INVALID --project test-trace --created-by test 2>&1
echo "Exit: $?"
```

**Expected**: Non-zero exit code or error message mentioning invalid link type.

### 8. Delete by project

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" delete --project test-trace \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('DELETED:', d.get('deleted', d.get('count', 0)))
"

# Confirm empty
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" list --project test-trace \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
links = d.get('links', d if isinstance(d, list) else [])
print('EMPTY:', len(links) == 0)
"
```

**Expected**: `DELETED:` > 0, `EMPTY: True`.

## Success Criteria

- [ ] 4 link types (TRACES_TO, IMPLEMENTED_BY, TESTED_BY, VERIFIES) created successfully
- [ ] Forward trace walks req-1 through design-1 to task-1
- [ ] Reverse trace walks test-1 back to req-1
- [ ] Coverage report shows 100% when all requirements have TESTED_BY links
- [ ] Coverage drops and gaps include req-2 when it lacks test links
- [ ] List filter by link-type returns only matching links
- [ ] Invalid link type is rejected with error
- [ ] Delete by project removes all links; subsequent list is empty

## Cleanup

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/traceability.py" delete --project test-trace 2>/dev/null || true
```
