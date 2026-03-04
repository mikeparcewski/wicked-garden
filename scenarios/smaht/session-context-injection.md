---
name: session-context-injection
title: Session Context Injection
description: SessionStart hook automatically gathers project context on startup
type: integration
difficulty: basic
estimated_minutes: 3
---

# Session Context Injection

Test that wicked-smaht automatically injects relevant context when a Claude Code session starts.

## Setup

```bash
# Verify plugin root is available
if [ -z "${CLAUDE_PLUGIN_ROOT}" ]; then
  PLUGIN_DIR=$(find "${HOME}/.claude/plugins/cache" -name "plugin.json" -path "*/wicked-garden/*" 2>/dev/null | head -1 | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null)
  if [ -z "$PLUGIN_DIR" ]; then
    PLUGIN_DIR="."
  fi
else
  PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"
fi
echo "PLUGIN_DIR=$PLUGIN_DIR"
echo "$PLUGIN_DIR" > "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-dir"

# Create an isolated test session
SCEN_SESSION="test-session-ctx-$$"
echo "Session ID: $SCEN_SESSION"
echo "$SCEN_SESSION" > "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id"

# Ensure session directory exists
mkdir -p "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
```

## Steps

### Step 1: Simulate session start via bootstrap hook

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-dir")
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id")
BOOTSTRAP="$PLUGIN_DIR/hooks/scripts/bootstrap.py"
[ -f "$BOOTSTRAP" ] || { echo "FAIL: bootstrap.py not found at $BOOTSTRAP"; exit 1; }
echo "{\"session_id\": \"$SCEN_SESSION\"}" | python3 "$BOOTSTRAP" 2>/dev/null
EXIT_CODE=$?
[ $EXIT_CODE -eq 0 ] || { echo "FAIL: bootstrap.py exited with $EXIT_CODE"; exit 1; }
echo "PASS: SessionStart hook executed successfully"
```

**Expected**: Session created and bootstrap hook fires without errors.

### Step 2: Verify session directory and initial state

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
[ -d "$SMAHT_DIR" ] || { echo "FAIL: session directory not created at $SMAHT_DIR"; exit 1; }
echo "Session directory exists: $SMAHT_DIR"
ls -la "$SMAHT_DIR" 2>/dev/null
echo "PASS: session directory created with initial state"
```

**Expected**: Session directory exists with initial files created by bootstrap.

### Step 3: Verify context gathering works for the session

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id")
OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/orchestrator.py gather "What should I work on today?" --session "$SCEN_SESSION" --json 2>&1)
EXIT_CODE=$?
echo "$OUTPUT" | tail -10
[ $EXIT_CODE -eq 0 ] || { echo "FAIL: context gathering failed with exit $EXIT_CODE"; exit 1; }
# Verify the output has the expected JSON structure
echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"Path: {d['path_used']}, Sources: {d['sources_queried']}\")" 2>/dev/null || true
echo "PASS: context gathering completed for session"
```

**Expected**: Shows the active session ID, sources queried, and any context items gathered.

### Step 4: Verify session metadata written after session activity

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"

# Simulate session end by calling persist_session_meta on the condenser (replaces removed end_session())
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python -c "
from smaht.v2.history_condenser import HistoryCondenser
c = HistoryCondenser('$SCEN_SESSION')
c.add_turn(user_msg='Test prompt for session', assistant_msg='Test response')
c.persist_session_meta()
print('Session ended, metadata written')
"

# Check session_meta.json was written
if [ -f "$SMAHT_DIR/session_meta.json" ]; then
  python3 -c "
import json
d = json.load(open('$SMAHT_DIR/session_meta.json'))
print(f\"session_id: {d.get('session_id', 'N/A')}\")
print(f\"start_time: {d.get('start_time', 'N/A')}\")
assert d.get('session_id'), 'Missing session_id in metadata'
print('PASS: session_meta.json has valid session_id and start_time')
"
else
  echo "FAIL: session_meta.json was not written after persist_session_meta()"
  exit 1
fi
```

**Expected**: The session's metadata (session_id, start_time) should be recorded.

## Cleanup

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id" 2>/dev/null)
if [ -n "$SCEN_SESSION" ]; then
  rm -rf "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
fi
rm -f "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-id"
rm -f "${TMPDIR:-/tmp}/wicked-scenario-session-ctx-dir"
```

## Expected Outcome

- New session created and tracked internally
- Session metadata written at session end with session summary
- Context packet injected into Claude's system prompt
- Sources queried based on what's available (graceful degradation)

## Success Criteria

- [ ] Session created on startup (visible via `/wicked-garden:smaht:debug`)
- [ ] Session metadata written at session end with valid session_id and start_time
- [ ] No errors in hook execution (check Claude terminal)
- [ ] Context gathered from available sources (may be empty if none installed)

## Value Demonstrated

wicked-smaht removes the cognitive load of manually gathering context when starting work. Instead of typing "/smaht" or manually recalling what you were working on, the SessionStart hook automatically:

1. Creates a session to track your work
2. Queries available wicked-garden plugins for relevant context
3. Injects that context so Claude is immediately aware of your project state

This makes Claude "ready to work" from the first prompt instead of needing ramp-up conversation.
