---
name: persona-transcript-session-retrieval
title: Persona Transcript Session Retrieval
description: Verify that individual persona thinking and full conversation transcripts are stored and retrievable after brainstorming sessions
type: workflow
difficulty: intermediate
estimated_minutes: 10
---

# Persona Transcript Session Retrieval

This scenario verifies that wicked-jam records and exposes individual persona contributions throughout a brainstorming session, so users can understand why synthesis reached its conclusions and revisit overruled perspectives.

## Setup

```bash
# Confirm jam.py is accessible
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" --help
```

## Steps

### 1. Run a Full Brainstorm Session

```bash
/wicked-garden:jam:brainstorm "should we use event sourcing or CRUD for our order management system"
```

Expected: Facilitator runs a full session with 4-6 personas, stores individual transcript entries during the session.

### 2. Retrieve the Full Transcript

```bash
/wicked-garden:jam:transcript
```

Expected: Full chronological conversation from the most recent session, showing each persona's raw contribution labeled with their name, archetype, and round number.

Verify the output:
- Contains multiple entries (at least one per persona per round)
- Each entry shows `persona_name`, `round`, `entry_type`, and `raw_text`
- Synthesis entry appears at the end with `entry_type: synthesis`
- Entries are ordered chronologically

### 3. Retrieve a Specific Persona's Contributions

```bash
/wicked-garden:jam:persona "Technical Architect"
```

Expected: All contributions from the Technical Architect persona across all rounds, including how their position evolved.

Verify the output:
- Shows only entries where `persona_name` matches (case-insensitive)
- Includes entries from multiple rounds if the persona participated in more than one
- Displays round numbers so evolution is visible
- Reports "No contributions found" if persona name doesn't match any entry

### 4. Retrieve All Pre-Synthesis Perspectives

```bash
/wicked-garden:jam:thinking
```

Expected: All individual perspectives before synthesis — the raw thinking, including minority views that synthesis may have de-emphasized.

Verify the output:
- Shows only `entry_type: perspective` entries (no synthesis)
- Includes ALL personas, not just those whose views "won"
- Orders by round then persona within round
- Does NOT include the synthesis or council_response entries

### 5. Test with Session ID Flag

```bash
# First get the session ID from list-sessions
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" list-sessions --json

# Then retrieve transcript for that specific session
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" transcript --session-id <SESSION_ID>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" persona "Cost Optimizer" --session-id <SESSION_ID>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" thinking --session-id <SESSION_ID>
```

Expected: All three subcommands accept `--session-id` and retrieve data from the specified session, not just the latest.

### 6. Test JSON Output

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" transcript --json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" thinking --json
```

Expected: Valid JSON output with `entries` array and `session_id` at the top level. Suitable for programmatic use by other scripts.

### 7. Run a Council Session and Verify Council Transcripts

```bash
/wicked-garden:jam:council "PostgreSQL vs DynamoDB for high-volume write workload" --options "PostgreSQL,DynamoDB"
```

Expected: Council persists each model's independent response with `entry_type: council_response` and `persona_name` set to the model name (e.g., "Gemini", "Codex").

```bash
/wicked-garden:jam:transcript
```

Verify:
- Council responses appear with `entry_type: council_response`
- `persona_name` reflects the external model name
- Claude's own evaluation is included with `persona_name: Claude`

### 8. Test Error Handling

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" transcript --session-id nonexistent-id-xyz
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jam/jam.py" persona "Nobody Real"
```

Expected: Graceful output like "No transcript found for session: nonexistent-id-xyz" and "No contributions found for persona: Nobody Real". Exit code 0 (not a crash).

## Expected Outcome

After a brainstorm session:
- `transcript` command shows the full chronological conversation with roles and rounds clearly labeled
- `persona` command lets users quote specific experts and understand their full position
- `thinking` command surfaces all pre-synthesis perspectives including minority views
- All three commands support `--session-id` for historical lookups and `--json` for scripting
- Council sessions also persist individual model responses for the same retrieval

## Success Criteria

- [ ] Facilitator agent stores transcript entries during brainstorm (perspective + synthesis)
- [ ] Council agent stores council_response entries for each external model
- [ ] `jam.py transcript` returns all entries ordered chronologically
- [ ] `jam.py persona <name>` returns only matching persona's entries
- [ ] `jam.py thinking` returns only `perspective` entries (no synthesis)
- [ ] All subcommands accept `--session-id` for historical access
- [ ] All subcommands accept `--json` for machine-readable output
- [ ] Human-readable output clearly labels persona, archetype, round, and entry type
- [ ] Missing session or persona returns a helpful message, not a stack trace
- [ ] Existing `list-sessions` subcommand continues to work unchanged

## Value Demonstrated

**Real-world value**: Brainstorm synthesis inevitably compresses and loses nuance. A skeptic's concern may be buried in a bullet point even if it's the most important consideration for your specific context. This feature lets users:

1. **Audit synthesis quality** — compare raw perspectives to the synthesis and judge if important concerns were captured
2. **Quote specific personas** — "The Cost Optimizer said X, which supports our budget constraint argument"
3. **Revisit minority views** — the perspective that lost the synthesis vote may be exactly right for your situation
4. **Build institutional memory** — combine with wicked-mem to recall not just conclusions but the reasoning path

This transforms brainstorm sessions from ephemeral thinking to a persistent, queryable knowledge asset.
