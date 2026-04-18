---
description: Show session state and recent context for debugging
argument-hint: "[--state] [--events N] [--json]"
---

# /wicked-garden:smaht:debug

Show session state and recent events for debugging context assembly. v6 removed
the per-turn push orchestrator (#428), so there is no HOT/FAST/SLOW routing log
to surface. This command now shows what lives in `SessionState` plus the last N
events on the bus.

## Usage

```bash
/wicked-garden:smaht:debug              # SessionState + last 10 events
/wicked-garden:smaht:debug --state       # SessionState only
/wicked-garden:smaht:debug --events 20   # Show last 20 events
/wicked-garden:smaht:debug --json        # Raw JSON output
```

## Instructions

### 1. Load SessionState

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from _session import SessionState
state = SessionState.load()
print(json.dumps(state.to_dict() if hasattr(state, 'to_dict') else state.__dict__, indent=2, default=str))
"
```

### 2. Display Session State

```markdown
## Session State

**Turn count**: {turn_count}
**Active chain**: {active_chain_id or "(none)"}
**Active crew project**: {active_project or "(none)"}
**Current phase**: {current_phase or "(none)"}
**Session goal**: {session_goal or "(not set)"}
```

### 3. Display Recent Events

Pull the last N events from the wicked-bus (default 10):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
try:
    from _bus import tail_events
    events = tail_events(limit=${EVENTS_LIMIT:-10})
    for e in events:
        print(f\"  [{e.get('event_type','?')}] {e.get('data',{}).get('summary','')}\")
except Exception as exc:
    print(f'bus unavailable: {exc}')
"
```

```markdown
## Recent Events (last N)

{bulleted list of event_type + summary}
```

### 4. Display Active Project Context (if any)

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

Display:

```markdown
## Active Crew Project

**Slug**: {slug}
**Phase**: {current_phase}
**Rigor tier**: {rigor_tier}
**Process plan**: `{project_dir}/process-plan.md`
```

## v5 → v6 Notes

The v5 HistoryCondenser + PressureTracker + ticket rail have all been removed.
Session context now lives in `SessionState` (simple key/value state) and the
wicked-bus event log. The facilitator's `process-plan.md` is the durable
artifact that used to be the "ticket rail."
