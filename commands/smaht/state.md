---
description: |
  Use when you need to inspect live SessionState, adapter outputs, or smaht directive settings.
  NOT for what-happened-since-last-session (use smaht:briefing).
argument-hint: "[--state] [--events N] [--json]"
---

# /wicked-garden:smaht:state

Snapshot and report current session state and recent events.

## Usage

```bash
/wicked-garden:smaht:state              # SessionState + last 10 events
/wicked-garden:smaht:state --state       # SessionState only
/wicked-garden:smaht:state --events 20   # Show last 20 events
/wicked-garden:smaht:state --json        # Raw JSON output
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

### When context is thin

If the output above doesn't surface what you need, invoke `wicked-garden:ground` to pull richer brain + bus context for the current task.
