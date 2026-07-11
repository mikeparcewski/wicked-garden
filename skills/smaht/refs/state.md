# smaht state — Session State + Recent Events Rubric

Full rubric for the `state` sub-action of `skills/smaht/SKILL.md`
(formerly `commands/smaht/state.md`, retired in the skills-only consolidation).
Snapshot and report current session state and recent events — live
SessionState / adapter / directive inspection. NOT for
what-happened-since-last-session (use the `briefing` sub-action,
`refs/briefing.md`).

Args: `[--state] [--events N] [--project <name>] [--json]`

## Step 1: Load SessionState

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

## Step 2: Display Session State

```markdown
## Session State

**Turn count**: {turn_count}
**Active chain**: {active_chain_id or "(none)"}
**Active crew project**: {active_project or "(none)"}
**Current phase**: {current_phase or "(none)"}
**Session goal**: {session_goal or "(not set)"}
```

Skip this section if `--state` is not the only flag (i.e. when `--events` is also given, show both; when `--state` only, skip events).

## Step 3: Display Recent Events

Pull the last N events from the wicked-bus (default 10, override with `--events N`):

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
## Recent Events (last {N})

{bulleted list of event_type + summary}
```

## Step 4: v11 Project Context (when `--project <name>` is given)

The v6-era "active crew project" auto-resolver was deleted in v11. When the
caller passes `--project <name>`, look up via phase_manager:

```markdown
## Project (v11 archetype-mode)

**Name**: {name}
**Archetype**: {v11_archetype}
**Current phase**: {current_phase}
**Phase plan**: {phase_plan}
**Is complete**: {is_complete}
```

## When Context Is Thin

If the output above doesn't surface what you need, invoke `wicked-garden:ground`
to pull richer brain + bus context for the current task.
