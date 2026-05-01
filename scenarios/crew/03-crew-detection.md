---
name: crew-detection
title: Crew Project Detection During Prompts
description: Verify crew hints fire for complex prompts, are suppressed when a project is active, and require complexity >= 3
type: testing
difficulty: beginner
estimated_minutes: 8
---

# Crew Project Detection During Prompts

This scenario verifies that the crew hint fires when no active project exists and a prompt
scores complexity >= 3 (Router._estimate_complexity 0-3 scale), is suppressed when an active
project is in the workspace, and does NOT re-fire at complexity=3 when crew_hint_shown=True
(the once-per-session gate is not bypassed by high complexity — that was the old behaviour).

## Setup

```bash
export TMPDIR=$(mktemp -d)
```

## Steps

### 1. Crew hint fires on complexity=3 prompt with no active project

The crew hint gate requires `Router._estimate_complexity(prompt) >= 3`. The 0-3 scale awards:
+1 for >80 words, +1 for migration/architecture/refactor keywords, +1 for plan/design/strategy keywords.
A prompt must score all three to trigger the hint.

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "active_project_id": null,
  "crew_hint_shown": false,
  "onboarding_complete": true,
  "needs_onboarding": false
}
EOF

echo '{"prompt": "Add a help command to the crew CLI that prints available subcommands.", "session_id": "sess-1"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `HINT_FOUND`

### 2. Crew hint suppressed when active project exists

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "active_project_id": "my-auth-project",
  "crew_hint_shown": false,
  "onboarding_complete": true,
  "needs_onboarding": false
}
EOF

echo '{"prompt": "I need to design and implement a new authentication system with OAuth2 providers, database schema migrations, and changes to three API services", "session_id": "sess-2"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `NO_HINT`

### 3. Crew hint suppressed when crew_hint_shown=True (once per session)

The hint gate checks `crew_hint_shown` and does NOT re-fire at any complexity level.
Once shown, crew_hint_shown=True suppresses all subsequent hints.

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "active_project_id": null,
  "crew_hint_shown": true,
  "onboarding_complete": true,
  "needs_onboarding": false
}
EOF

echo '{"prompt": "Help me plan and architect a complete migration of our monolith to microservices — first design the service boundaries, then implement the first service with full testing and after that build the full data migration pipeline with rollback support", "session_id": "sess-3"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `NO_HINT` (suppressed by crew_hint_shown=True — once per session, no re-fire)

### 4. Low-complexity prompt does not trigger hint

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "active_project_id": null,
  "crew_hint_shown": false,
  "onboarding_complete": true,
  "needs_onboarding": false
}
EOF

echo '{"prompt": "fix a typo in README", "session_id": "sess-4"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `NO_HINT`

### 5. crew_hint_shown flag is written after first hint

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"active_project_id": null, "crew_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "I need to design and implement a complete OAuth2 migration with database changes and API versioning strategy across multiple services", "session_id": "sess-5"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null > /dev/null

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, os, glob
session_files = glob.glob('${TMPDIR}/wicked-garden-session-*.json')
if session_files:
    d = json.loads(open(session_files[0]).read())
    print('FLAG_SET' if d.get('crew_hint_shown') else 'FLAG_NOT_SET')
else:
    print('NO_SESSION_FILE')
"
```

**Expected**: `FLAG_SET`

### 6. Regression guard: hint never appears when crew_hint_shown=True

With crew_hint_shown=True in session state, `crew:start` must never appear in output —
the once-per-session gate is respected regardless of complexity.

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"active_project_id": null, "crew_hint_shown": true, "onboarding_complete": true, "needs_onboarding": false}
EOF

output=$(echo '{"prompt": "Help me plan and architect a complete migration of our monolith to microservices — first design the service boundaries, then implement the first service with full testing and after that build the full data migration pipeline with rollback support", "session_id": "sess-6"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print(ctx.count('crew:start'))")

echo "Hint count in output: ${output}"
[ "${output}" -eq 0 ] && echo "NO_SPAM_OK" || echo "SPAM_DETECTED"
```

**Expected**: `NO_SPAM_OK` (0 crew:start occurrences — gate suppresses all hints once shown)

## Expected Outcome

The crew hint appears precisely when needed: prompts scoring complexity=3 (all three heuristics:
>80 words, migration/architecture/refactor keywords, plan/design/strategy keywords) with no active
project. The hint is gated once per session — crew_hint_shown=True suppresses all subsequent
hints regardless of complexity. There is no re-fire mechanism.

## Success Criteria

- [ ] Crew hint present for complexity=3 prompt with active_project_id=null and crew_hint_shown=False
- [ ] Crew hint absent when active_project_id is set to a project name
- [ ] Crew hint absent when crew_hint_shown=True (no re-fire at any complexity level)
- [ ] Low-complexity ("fix a typo") prompts produce no hint
- [ ] crew_hint_shown flag written to session state after first hint
- [ ] No crew:start appears in output when crew_hint_shown=True (0 occurrences, not just <=1)
- [ ] active_project_id (not cp_project_id) is the gate field used

## Value Demonstrated

The original bug used cp_project_id (a CP UUID) to gate the hint. Any workspace with a crew
project in any state would suppress the hint — even for completed projects. Using
active_project_id (local name, non-complete phase only) ensures the hint fires exactly when
a new crew project would be useful.

## Cleanup

```bash
rm -rf "${TMPDIR}"
```
