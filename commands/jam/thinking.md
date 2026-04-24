---
description: |
  Use when you want the raw pre-synthesis perspectives from a brainstorm — minority views, strong dissents,
  and nuances that synthesis may have compressed. NOT for the full session (use jam:transcript).
argument-hint: "[--session-id ID] [--json]"
---

# /wicked-garden:jam:thinking

Display all pre-synthesis perspectives from a brainstorm session — the raw, unfiltered thinking from every persona before Claude distilled them into synthesis insights. This exposes minority views, strong dissents, and nuances that synthesis may have de-emphasized.

Unlike `transcript` (which includes synthesis and council responses), `thinking` shows only `perspective` entries — the authentic voice of each persona.

Without `--session-id`, shows the most recent session's pre-synthesis perspectives.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/jam/jam.py thinking $ARGUMENTS
```

After running the script, present the output. Add a brief framing note: compare the perspective count to what the synthesis captured — if the synthesis listed 3 insights but there were 12 distinct perspectives, that compression ratio signals significant information loss worth examining.

If no transcript is found, explain that perspective data is stored automatically during brainstorm sessions and suggest running `/wicked-garden:jam:brainstorm`.
