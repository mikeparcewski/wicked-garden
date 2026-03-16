---
description: View the full conversation transcript from a jam brainstorm or council session
argument-hint: "[--session-id ID] [--json]"
---

# /wicked-garden:jam:transcript

Display the full chronological conversation from a brainstorm or council session — every persona contribution, building exchange, and the final synthesis. Use this to audit how synthesis reached its conclusions or to retrieve a complete record of the discussion.

Without `--session-id`, shows the most recent session's transcript.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/jam/jam.py transcript $ARGUMENTS
```

After running the script, present the output. If the output is in human-readable format, add a brief header summarizing the session topic (if visible) and the total number of entries shown.

If no transcript is available yet (session was run before transcript persistence was added, or no sessions exist), explain that transcripts are stored automatically after each brainstorm and suggest running `/wicked-garden:jam:brainstorm` to start a session.
