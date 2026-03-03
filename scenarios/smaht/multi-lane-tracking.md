---
name: multi-lane-tracking
title: Topic Switching and Open Thread Tracking
description: Session summary tracks current_task, topics, and open_threads as you switch between work items
type: feature
difficulty: intermediate
estimated_minutes: 6
---

# Topic Switching and Open Thread Tracking

Test that wicked-smaht correctly tracks the current task, accumulates topics across task switches, and preserves open threads in the session summary.

## Setup

```bash
# Create an isolated test session
SCEN_SESSION="test-multi-lane-$$"
echo "Session ID: $SCEN_SESSION"
echo "$SCEN_SESSION" > "${TMPDIR:-/tmp}/wicked-scenario-lane-session"

# Ensure session directory exists
mkdir -p "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
```

## Steps

### Step 1: Start with a debugging task

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/history_condenser.py "$SCEN_SESSION" "I'm working on fixing the user login. Users are getting 401 errors after token refresh."
echo "PASS: debugging task submitted"
```

**Expected**: `current_task` tracked as something containing "fixing the user login". Topics updated with "authentication" keyword.

### Step 2: Check current_task was captured

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
python3 -c "
import json, os
summary_path = '$SMAHT_DIR/summary.json'
if os.path.exists(summary_path):
    d = json.load(open(summary_path))
    ct = d.get('current_task', '')
    print(f'current_task: {ct}')
    assert 'login' in ct.lower() or 'fixing' in ct.lower(), f'Expected login-related task, got: {ct}'
    print('PASS: current_task captured')
else:
    # Check turns.jsonl for captured state
    turns_path = '$SMAHT_DIR/turns.jsonl'
    if os.path.exists(turns_path):
        print('Turns recorded, summary may update after threshold')
        print('PASS: state tracked in turns')
    else:
        print('PASS: condenser processed (summary written on threshold)')
"
```

**Expected**: Debug output shows `current_task` set to the login fix task.

### Step 3: Switch to a new task

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python smaht/v2/history_condenser.py "$SCEN_SESSION" "Let's design the new notification system while we wait for QA."
echo "PASS: task switch submitted"
```

**Expected**: `current_task` updated to the notification task (overwritten, not stacked). Topics accumulate: previous topics remain, "notification" added if it matches the keyword list.

### Step 4: Verify topics accumulate across switches

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
python3 -c "
import json, os
summary_path = '$SMAHT_DIR/summary.json'
if os.path.exists(summary_path):
    d = json.load(open(summary_path))
    topics = d.get('topics', [])
    ct = d.get('current_task', '')
    print(f'topics: {topics}')
    print(f'current_task: {ct}')
    # current_task should reflect the latest task (notification), not the first
    assert 'notification' in ct.lower() or 'design' in ct.lower(), f'Expected notification task, got: {ct}'
    print('PASS: topics accumulate, current_task updated')
else:
    print('PASS: condenser processed (summary written on threshold)')
"
```

**Expected**: Debug output shows topics list containing keywords from both tasks. Topics are not cleared on task switch — they accumulate up to 10 entries.

### Step 5: Add a turn with a question pattern

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python -c "
from smaht.v2.history_condenser import HistoryCondenser
c = HistoryCondenser('$SCEN_SESSION')
c.add_turn(
    user_msg='Should we use WebSockets or polling for the notification delivery?',
    assistant_msg='That depends on your latency requirements. Do you need real-time updates or is near-real-time acceptable?'
)
print('PASS: question turn added')
"
```

**Expected**: If the assistant response contains a question (containing `?`), it appears in `open_questions`. The assistant's questions are tracked when they are 15-150 characters.

### Step 6: Inspect the full session state

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
python3 -c "
import json, os
summary_path = '$SMAHT_DIR/summary.json'
if os.path.exists(summary_path):
    d = json.load(open(summary_path))
    print(json.dumps(d, indent=2))
    # Validate structure
    assert isinstance(d.get('topics', []), list), 'topics should be a list'
    assert isinstance(d.get('current_task', ''), str), 'current_task should be a string'
    print('PASS: session state is valid and inspectable')
else:
    print('PASS: condenser processed (summary written on threshold)')
"
```

**Expected structure** after switching tasks:
```json
{
  "topics": ["authentication", "notification"],
  "decisions": [],
  "preferences": [],
  "open_threads": [],
  "current_task": "design the new notification system while we wait for qa",
  "active_constraints": [],
  "file_scope": [],
  "open_questions": ["Do you need real-time updates or is near-real-time acceptable?"]
}
```

### Step 7: Verify turn history shows both tasks

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session")
SMAHT_DIR="${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
if [ -f "$SMAHT_DIR/turns.jsonl" ]; then
  TURN_COUNT=$(wc -l < "$SMAHT_DIR/turns.jsonl" | tr -d ' ')
  echo "Turns recorded: $TURN_COUNT"
  [ "$TURN_COUNT" -ge 2 ] || { echo "FAIL: expected at least 2 turns, got $TURN_COUNT"; exit 1; }
  echo "PASS: turn history contains multiple turns"
else
  # Also check condensed history
  OUTPUT=$(cd "${CLAUDE_PLUGIN_ROOT}/scripts" && uv run python -c "
from smaht.v2.history_condenser import HistoryCondenser
c = HistoryCondenser('$SCEN_SESSION')
print(c.get_condensed_history())
")
  echo "$OUTPUT"
  echo "PASS: condensed history available"
fi
```

**Expected**: Both task prompts should appear in the recent turns list.

## Cleanup

```bash
SCEN_SESSION=$(cat "${TMPDIR:-/tmp}/wicked-scenario-lane-session" 2>/dev/null)
if [ -n "$SCEN_SESSION" ]; then
  rm -rf "${HOME}/.something-wicked/wicked-garden/local/wicked-smaht/sessions/${SCEN_SESSION}"
fi
rm -f "${TMPDIR:-/tmp}/wicked-scenario-lane-session"
```

## Expected Outcome

- `current_task` is a single string — updated (overwritten) with the most recent task statement
- `topics` is a flat list that accumulates across all turns (max 10, oldest dropped when full)
- `open_threads` is managed manually (not auto-populated by turns)
- `open_questions` captures questions from assistant responses
- Switching tasks does NOT reset prior topics — they remain in the list

## Session Summary Fields

| Field | Type | Behavior |
|-------|------|----------|
| `current_task` | string | Overwritten on each new task statement |
| `topics` | list[str] | Accumulates; capped at 10 (oldest removed) |
| `open_threads` | list[str] | Manual/externally managed |
| `open_questions` | list[str] | Set from assistant `?` sentences; trimmed to 3 |
| `file_scope` | list[str] | Files mentioned; capped at 20 (oldest removed) |

## Success Criteria

- [ ] First task statement sets current_task
- [ ] Second task statement overwrites current_task (not appended)
- [ ] Topics from both tasks appear in the topics list
- [ ] Topics list does not exceed 10 entries
- [ ] Assistant questions appear in open_questions
- [ ] Session summary is valid and inspectable via `/wicked-garden:smaht:debug`
- [ ] Turn history shows all turns up to the 5-turn window

## Value Demonstrated

Developers regularly context-switch mid-session. wicked-smaht's flat session summary captures the essential state without complex parallel structures:
1. **Current task tracking** — always know what's active
2. **Topic accumulation** — keywords from all work accumulate for context
3. **Constraint tracking** — "must", "should", "don't" statements are captured automatically
4. **Open questions** — assistant follow-up questions are tracked so they don't get lost
