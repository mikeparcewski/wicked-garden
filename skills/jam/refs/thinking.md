# jam:thinking — Pre-Synthesis Perspective Retrieval Rubric

Full rubric sourced from `commands/jam/thinking.md`.
Displays raw `perspective` entries from a brainstorm session before synthesis.

## Purpose

Expose minority views, strong dissents, and nuances that synthesis may have
compressed. Shows only `perspective` entries — the authentic voice of each
persona before Claude distilled them.

## Step 1: Run the Script

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/jam/jam.py thinking $ARGUMENTS
```

Where `$ARGUMENTS` may include `--session-id ID` and/or `--json`.

Without `--session-id`, the script uses the most recent session.

## Step 2: Present the Output

After the script runs, present its output verbatim. Add a brief framing note:

> Compare the perspective count to what the synthesis captured. If the synthesis
> listed 3 insights but there were 12 distinct perspectives, that compression
> ratio signals significant information loss worth examining.

## Step 3: Handle Missing Data

If the script returns no transcript or an error about no session found:

> "Perspective data is stored automatically during brainstorm sessions.
> No perspective data found for {session or 'the most recent session'}.
> Run `/wicked-garden:jam:brainstorm` to start a session that stores perspectives."
