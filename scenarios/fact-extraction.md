---
name: fact-extraction
title: Decision Detection and Topic Tracking
description: Automatic extraction of decisions and topics from conversation turns into summary.json
type: feature
difficulty: intermediate
estimated_minutes: 5
---

# Decision Detection and Topic Tracking

Test that wicked-smaht automatically detects decisions and topics from conversation turns and persists them in summary.json.

## Setup

Start a Claude Code session. The HistoryCondenser initializes a session directory under `~/.something-wicked/wicked-smaht/sessions/{session_id}/` on first use.

Identify your session ID:

```bash
echo $CLAUDE_SESSION_ID
```

## Steps

1. **Make a decision using a recognized pattern**
   ```
   Let's use JWT tokens for authentication instead of session cookies.
   ```

   **Expected**: Decision extracted via "let's use" regex pattern and added to `decisions` in summary.json.

2. **Make a second decision**
   ```
   We'll use Redis for the session store.
   ```

   **Expected**: Second decision ("we'll use redis for the session store") appended to `decisions` list. Up to 5 decisions retained.

3. **Trigger topic extraction**
   ```
   I'm working on the auth.py and jwt_validator.py files.
   ```

   **Expected**: Topics list updated with "auth.py", "jwt_validator.py", and "auth" keyword.

4. **Inspect summary.json**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/summary.json
   ```

   Expected structure:
   ```json
   {
     "topics": ["auth.py", "jwt_validator.py", "auth"],
     "decisions": [
       "use jwt tokens for authentication instead of session cookies",
       "use redis for the session store"
     ],
     "preferences": [],
     "open_threads": [],
     "current_task": "",
     "active_constraints": [],
     "file_scope": ["auth.py", "jwt_validator.py"],
     "open_questions": []
   }
   ```

5. **Inspect turns.jsonl**
   ```bash
   cat ~/.something-wicked/wicked-smaht/sessions/*/turns.jsonl
   ```

   **Expected**: Each turn recorded as a JSON object with `user`, `assistant`, `timestamp`, and `tools_used` fields. Rolling window of last 5 turns.

6. **Verify keyword concept extraction**
   ```
   Let's improve the authentication and security setup.
   ```

   **Expected**: "authentication" and "security" appear in topics (concept keywords are matched from a fixed list).

## Expected Outcome

- Decision phrases ("let's use", "we'll use", "decided on", "chose") are extracted via regex
- File mentions (`.py`, `.ts`, `.js`, `.md`) are tracked as topics and file_scope
- Concept keywords (auth, caching, testing, debugging, etc.) are tracked as topics
- summary.json is written atomically after each turn
- turns.jsonl contains a rolling window of up to 5 turns

## Decision Extraction Patterns

| Pattern | Example Input | Extracted Decision |
|---------|--------------|-------------------|
| `let's use/go with/do` | "Let's use JWT" | "use jwt" |
| `we'll use` | "We'll use Redis" | "use redis for..." |
| `decided on` | "Decided on Postgres" | "postgres" |
| `chose` | "Chose the monorepo" | "the monorepo" |

Matches are length-filtered: must be 10–100 characters to be captured.

## Success Criteria

- [ ] Decision detected from "let's use" pattern
- [ ] Decision detected from "we'll use" pattern
- [ ] File mentions appear in topics and file_scope
- [ ] Concept keywords (auth, security) appear in topics
- [ ] summary.json exists and is valid JSON
- [ ] turns.jsonl contains at least one turn record
- [ ] summary.json capped at 5 decisions (oldest removed when full)

## Value Demonstrated

Decisions made during a session are automatically captured without manual "remember this" commands:
1. **Automatic capture** — No user action needed
2. **Regex-based extraction** — Deterministic, fast, no LLM cost
3. **Session persistence** — Survives tool calls and long conversations
4. **Cross-session seed** — Decisions surface in session_meta.json for future sessions to reference
