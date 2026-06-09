---
description: View the full conversation transcript from a jam brainstorm or council session
argument-hint: "[--session-id ID] [--json]"
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# /wicked-garden:jam:transcript

Display the full chronological conversation from a brainstorm or council session —
every persona contribution, building exchange, and the final synthesis.

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/transcript.md")` — the rubric:
   script invocation, header format, and missing-data handling.
2. Run the script and present the output per the rubric.
