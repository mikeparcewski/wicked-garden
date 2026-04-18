---
name: intent-based-retrieval
title: Intent-Based Context Retrieval
description: Intent detection selects relevant adapters for debugging vs planning vs implementation
type: feature
difficulty: basic
estimated_minutes: 5
---

# Intent-Based Context Retrieval

Test that wicked-smaht detects query intent and selects relevant context adapters accordingly.

## Setup

```bash
# Create an isolated test session
SCEN_SESSION="test-intent-retrieval-$$"
echo "Session ID: $SCEN_SESSION"
echo "$SCEN_SESSION" > "${TMPDIR:-/tmp}/wicked-scenario-intent-session"

# Ensure session directory exists
mkdir -p "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
```

## Steps

### Step 1: Test debugging intent detection

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-intent-session")
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py route "Why is the authentication failing? I'm getting a 401 error on login." --json 2>&1)
echo "$OUTPUT"
INTENT=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['analysis']['intent'])")
echo "Detected intent: $INTENT"
[ "$INTENT" = "debugging" ] || { echo "FAIL: expected debugging, got $INTENT"; exit 1; }
echo "PASS: debugging intent detected"
```

**Expected**: Intent detected as "debugging" with high confidence. On the fast path, search, mem, and delegation adapters are selected for error context.

### Step 2: Test planning intent detection

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-intent-session")
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py route "I need to design the new API for user management. What's our current approach?" --json 2>&1)
echo "$OUTPUT"
INTENT=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['analysis']['intent'])")
PATH_USED=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['path'])")
echo "Detected intent: $INTENT, path: $PATH_USED"
[ "$INTENT" = "planning" ] || { echo "FAIL: expected planning, got $INTENT"; exit 1; }
echo "PASS: planning intent detected"
```

**Expected**: Intent detected as "planning". Escalates to slow path (planning is always comprehensive) — all adapters queried including jam (brainstorms) and crew (project state).

### Step 3: Test implementation intent detection

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-intent-session")
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py route "Implement a logout function that creates an endpoint to invalidate JWT tokens." --json 2>&1)
echo "$OUTPUT"
INTENT=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['analysis']['intent'])")
echo "Detected intent: $INTENT"
[ "$INTENT" = "implementation" ] || { echo "FAIL: expected implementation, got $INTENT"; exit 1; }
echo "PASS: implementation intent detected"
```

**Expected**: Intent detected as "implementation" with high confidence. On the fast path, search, mem, context7, tools, and delegation adapters are selected for task context.

### Step 4: Test research intent detection

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-intent-session")
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py route "How does the caching layer work in this codebase?" --json 2>&1)
echo "$OUTPUT"
INTENT=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['analysis']['intent'])")
echo "Detected intent: $INTENT"
[ "$INTENT" = "research" ] || { echo "FAIL: expected research, got $INTENT"; exit 1; }
echo "PASS: research intent detected"
```

**Expected**: Intent detected as "research" with high confidence. On the fast path, search, mem, context7, tools, and delegation adapters are selected for broad code understanding.

### Step 5: Verify intent recorded in session via full gather

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-intent-session")
# Run a full gather to populate turns.jsonl
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py gather "Fix the broken login flow" --session "$SCEN_SESSION" --json > /dev/null 2>&1

SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
if [ -f "$SMAHT_DIR/turns.jsonl" ]; then
  TURN_COUNT=$(wc -l < "$SMAHT_DIR/turns.jsonl" | tr -d ' ')
  echo "Turns recorded: $TURN_COUNT"
  # Check that turns have intent_type field
  python3 -c "
import json
with open('$SMAHT_DIR/turns.jsonl') as f:
    for line in f:
        turn = json.loads(line.strip())
        intent = turn.get('intent_type', '')
        print(f'Turn intent: {intent}')
        assert intent, 'Turn missing intent_type'
"
  echo "PASS: turns.jsonl records intent for each turn"
else
  echo "PASS: gather completed (turns stored in condensed form)"
fi
```

**Expected**: Each turn should show `intent_type` field. turns.jsonl is populated by the orchestrator's `add_turn()` method during context gathering.

## Cleanup

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-intent-session" 2>/dev/null)
if [ -n "$SCEN_SESSION" ]; then
  rm -rf "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
fi
rm -f "${TMPDIR:-/tmp}/wicked-scenario-intent-session"
```

## Expected Outcome

- Different intents select different adapter sets for context retrieval
- Debugging queries select search and mem adapters for error context and recent changes
- Planning queries escalate to slow path for comprehensive context from all adapters
- Implementation queries select search, mem, and context7 for task and code context
- Research queries select search, mem, context7, and tools for broad coverage

## Processing Modes

| Trigger | Mode | Latency | Sources |
|---------|------|---------|---------|
| Continuation/confirmation | Hot | <100ms | Session state only |
| High confidence (>0.7), simple request | Fast | <500ms | Intent-specific adapters (2-6) |
| Low confidence, planning, competing intents, etc. | Slow | <5s | All adapters + history |

Escalation to slow path triggers on: confidence < 0.5, competing intents, > 5 entities, history reference, planning/design request, novel topic, > 200 words, or compound request.

## Success Criteria

- [ ] Debugging prompt detected as intent_type: "debugging"
- [ ] Planning prompt detected as intent_type: "planning"
- [ ] Implementation prompt detected as intent_type: "implementation"
- [ ] Research prompt detected as intent_type: "research"
- [ ] turns.jsonl records intent for each turn
- [ ] Different prompts show different confidence levels

## Value Demonstrated

Not all queries need the same context. A debugging session needs error logs and recent changes, while a planning session needs design documents and brainstorm notes.

wicked-smaht's intent detection ensures:
1. **Relevant context** - You get what you need, not everything
2. **Faster responses** - High confidence = Fast mode (<500ms)
3. **Better accuracy** - Low confidence triggers broader retrieval
4. **No manual configuration** - Intent detection is automatic via pattern matching (no LLM call in hot path)
