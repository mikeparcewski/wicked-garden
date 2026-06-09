# jam:transcript — Full Session Transcript Retrieval Rubric

Full rubric sourced from `commands/jam/transcript.md`.
Displays the full chronological conversation from a brainstorm or council session.

## Purpose

Audit how synthesis reached its conclusions, or retrieve a complete record of a
session — every persona contribution, building exchange, and the final synthesis.

## Step 1: Run the Script

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/jam/jam.py transcript $ARGUMENTS
```

Where `$ARGUMENTS` may include `--session-id ID` and/or `--json`.

Without `--session-id`, the script uses the most recent session.

## Step 2: Present the Output

After the script runs, present its output. If the output is in human-readable
format (not `--json`), add a brief header:

> Session: {topic if visible} — {total entry count} entries

## Step 3: Handle Missing Data

If no transcript is available (session ran before transcript persistence was
added, or no sessions exist):

> "Transcripts are stored automatically after each brainstorm. No transcript
> found for {session or 'the most recent session'}.
> Run `/wicked-garden:jam:brainstorm` to start a session that stores a transcript."
