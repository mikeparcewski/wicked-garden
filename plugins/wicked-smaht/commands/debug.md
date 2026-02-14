---
description: Show what context was assembled for recent turns
argument-hint: [--turns N] [--state] [--json]
---

# /wicked-smaht:debug

Show the session state document and context assembly details for debugging.

## Usage

```bash
/wicked-smaht:debug          # Show session state + last 3 turns of context
/wicked-smaht:debug --state   # Session state document only
/wicked-smaht:debug --turns 5 # Show last 5 turns
/wicked-smaht:debug --json    # Raw JSON output
```

## Instructions

### 1. Load Session State

Read the session state from the history condenser:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/v2/history_condenser.py" ${CLAUDE_SESSION_ID:-default}
```

### 2. Parse Arguments

- `--state`: Show only the session state document (ticket rail)
- `--turns N`: Show last N turns (default 3)
- `--json`: Output raw JSON instead of formatted markdown

### 3. Display Session State Document

Show the "ticket rail" — the L2 cache that survives context compression:

```markdown
## Session State (Ticket Rail)

**Current task**: {current_task or "(none)"}
**Topics**: {topics}
**Decisions**: {decisions}
**Constraints**: {active_constraints}
**Files in scope**: {file_scope}
**Open questions**: {open_questions}
**Open threads**: {open_threads}
**Preferences**: {preferences}
```

### 4. Display Turn History

Read the last N turns from `~/.something-wicked/wicked-smaht/sessions/{session_id}/turns.jsonl`:

```markdown
## Recent Turns

| Turn | User | Assistant | Path |
|------|------|-----------|------|
| 1 | {user[:80]} | {assistant[:80]} | {fast/slow/hot} |
```

### 5. Display Routing Stats and Session Metrics

Read the turn tracker from `/tmp/wicked-smaht-turns-{session_id}` and metrics from `~/.something-wicked/wicked-smaht/sessions/{session_id}/metrics.json`:

```markdown
## Routing Stats

- **Total turns**: {count}
- **Context path**: hot={hot_count}, fast={fast_count}, slow={slow_count}
- **Session ID**: {session_id}

## Session Metrics

- **Sources pre-loaded**: {items_pre_loaded} across {queries_made} queries
- **Estimated turns saved**: ~{estimated_turns_saved} (context that would have required manual search/recall)
- **Value**: Pre-loaded context eliminated approximately {estimated_turns_saved} additional turns of re-explaining or re-searching
```

### 6. Show Context Package Preview

Run the context package builder to show what a subagent would receive:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_package.py" build --task "current session work" --prompt
```

Display the output under:

```markdown
## Subagent Context Package Preview

{output from context_package.py}
```

This shows exactly what context a subagent would receive if dispatched right now.
