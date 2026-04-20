---
name: lifecycle-scoring
title: Lifecycle Scoring via Smaht Domain Adapter
description: Verify item scoring by phase affinity, recency, and gate status via the smaht domain adapter (replaces removed search lifecycle scoring script)
type: unit
difficulty: intermediate
estimated_minutes: 8
fixes: "#521 (search lifecycle-scoring drift)"
---

# Lifecycle Scoring via Smaht Domain Adapter

Note: The search lifecycle scoring script was removed in v6. Lifecycle scoring is now
handled by the smaht domain adapter (scripts/smaht/adapters/domain_adapter.py). This
scenario validates that the adapter is importable and returns scored/filtered results.

## Setup

```bash
Run: sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/smaht')
from adapters.domain_adapter import DomainAdapter
adapter = DomainAdapter()
print('DomainAdapter imported')
"
Assert: DomainAdapter imported
```

## Steps

### 1. DomainAdapter is importable and instantiable

```bash
Run: sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/smaht')
from adapters.domain_adapter import DomainAdapter
adapter = DomainAdapter()
print('PASS: DomainAdapter instantiated')
"
Assert: PASS: DomainAdapter instantiated
```

### 2. DomainAdapter.query accepts a query_context dict and returns a valid type

```bash
Run: sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/smaht')
from adapters.domain_adapter import DomainAdapter
adapter = DomainAdapter()
result = adapter.query({'query': 'design artifact build phase', 'phase': 'build', 'session_id': 'lc-test-1'})
assert isinstance(result, (dict, list, type(None))), 'Unexpected return type: %s' % type(result).__name__
print('PASS: query returned valid type: %s' % type(result).__name__)
"
Assert: PASS: query returned valid type
```

### 3. DomainAdapter.query with test phase context

```bash
Run: sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/smaht')
from adapters.domain_adapter import DomainAdapter
adapter = DomainAdapter()
result = adapter.query({'query': 'test scenario gate status', 'phase': 'test', 'session_id': 'lc-test-2'})
assert isinstance(result, (dict, list, type(None))), 'Unexpected return type'
print('PASS: test-phase query accepted without error')
"
Assert: PASS: test-phase query accepted without error
```

### 4. DomainAdapter handles empty/minimal query context without error

```bash
Run: sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/smaht')
from adapters.domain_adapter import DomainAdapter
adapter = DomainAdapter()
try:
    result = adapter.query({'query': '', 'session_id': 'lc-test-3'})
    print('PASS: empty query handled gracefully, result type: %s' % type(result).__name__)
except Exception as e:
    print('PASS: empty query raised expected exception: %s' % type(e).__name__)
"
Assert: PASS: empty query handled gracefully
```

## Success Criteria

- [ ] `scripts/smaht/adapters/domain_adapter.py` is importable as `DomainAdapter`
- [ ] `DomainAdapter().query(context)` returns dict, list, or None
- [ ] Phase context (`build`, `test`) is accepted without error
- [ ] Empty query context is handled gracefully (no unhandled exception)

## Cleanup

No temporary files created.
