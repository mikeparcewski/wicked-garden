# Hook Prompt Standards

Standard language and patterns for wicked-garden hook prompts.

## Response Format

All hooks must return valid JSON:
```json
{"ok": true}
```

To block an action (rare):
```json
{"ok": false, "reason": "Specific reason"}
```

## Hook Type Selection

Prefer **command hooks** over prompt/agent hooks:
- Command hooks are deterministic, testable, and support `"async": true`
- Prompt/agent hooks cost LLM tokens and can't run async
- Use `"async": true` for Stop/SessionEnd hooks so they don't block the user

| Need | Hook Type |
|------|-----------|
| File I/O, timestamps, queue processing | `command` (async for Stop) |
| Must block an action based on content | `command` (exit 2 to block) |
| Needs LLM reasoning to decide | `prompt` (single-turn, rare) |
| Needs multi-turn tool use to verify | `agent` (very rare) |

## Canonical References

Hook scripts must reference **canonical plugin components** (agents, commands, skills), not internal script paths that may change. Internal scripts are implementation details; canonical components are stable contracts.

Bad: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mem/memory.py" decay --quiet`
Good: Import from the plugin's own modules within hook scripts

When hook scripts need plugin functionality, import the plugin's Python modules directly rather than shelling out to script paths.

## Efficiency Guidelines

- Quick signal detection first - don't over-analyze
- Use async command hooks for non-blocking cleanup (Stop, SessionEnd)
- Target <5 seconds for sync hooks, <30 seconds for async hooks
- Reserve prompt/agent hooks for cases that genuinely need LLM reasoning

## Prose Style

Keep hook output minimal and direct:
- No greetings or sign-offs
- No "I'll now..." or "Let me..."
- State what was done, not what you're about to do
- One-line summaries when reporting actions

Bad: "I've analyzed the session and found some valuable learnings. Let me extract those for you."
Good: "Extracted: auth pattern decision, API error fix"

## Error Handling

- Fail gracefully - return `{"ok": true}` even on errors
- Log errors to stderr if debugging needed
- Never block user from stopping unless truly critical
- "Truly critical" = broken file state, explicit user request

## Stop Hook Pattern (Async Command)

Stop hooks should be async command hooks that run Python scripts:

```json
{
  "type": "command",
  "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/stop.py\"",
  "async": true,
  "timeout": 30
}
```

The script reads JSON from stdin (includes `session_id`, `transcript_path`, `cwd`),
does its work, and exits 0. Output with `systemMessage` is delivered on next turn.

```python
#!/usr/bin/env python3
import json, sys

hook_input = json.loads(sys.stdin.read())
# ... do work ...
print(json.dumps({"systemMessage": "[Plugin] Summary of what happened"}))
sys.exit(0)
```
