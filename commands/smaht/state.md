---
description: |
  Use when you need to inspect live SessionState, adapter outputs, or smaht directive settings.
  NOT for what-happened-since-last-session (use smaht:briefing).
argument-hint: "[--state] [--events N] [--project <name>] [--json]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:smaht:state

Snapshot and report current session state and recent events.

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/smaht/refs/state.md")` — the rubric:
   SessionState script, display format, wicked-bus events tail, and v11
   project context lookup (when `--project <name>` is given).
2. Apply the rubric directly using `$ARGUMENTS`.
