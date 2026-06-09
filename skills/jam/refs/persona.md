# jam:persona — Single-Persona Trace Retrieval Rubric

Full rubric sourced from `commands/jam/persona.md`.
Retrieves all contributions from one named persona across all rounds of a session.

## Purpose

Quote a specific expert's position, understand how their view evolved across rounds,
or identify perspectives the synthesis may have compressed for that persona.

## Step 1: Run the Script

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/jam/jam.py persona $ARGUMENTS
```

Where `$ARGUMENTS` must include the persona name (first positional arg), and
optionally `--session-id ID` and/or `--json`.

Persona name matching is case-insensitive. The display name from the session
(e.g. "Technical Architect", "Cost Optimizer", "Security Reviewer").

Without `--session-id`, the script searches the most recent session.

## Step 2: Present the Output

If entries are returned, present them verbatim. Add a note:

> {Persona} participated in {N} round(s). {Did their position shift between rounds?
> Infer from the raw_text content — if so, note the shift briefly.}

## Step 3: Handle No Match

If the script returns no matching persona:

1. Run the transcript script to extract unique persona names:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/jam/jam.py transcript --json $SESSION_ARG
```

2. Extract `persona_name` values from the output.

3. Show:

> "No persona named '{name}' found. Personas in this session:"
> {list of persona names}
