---
name: crew-detection
title: Crew Project Detection During Prompts
description: Verify crew hints fire for complex prompts, are suppressed when a project is active, and re-fire at complexity=3
type: testing
difficulty: beginner
estimated_minutes: 8
---

# Crew Project Detection During Prompts

This scenario verifies that the crew hint fires when no active project exists and a prompt
scores complexity >= 2, is suppressed when an active project is in the workspace, and re-fires
at complexity=3 even after the once-per-session gate has been set.

## Setup

```bash
export TMPDIR=$(mktemp -d)
```

## Steps

### 1. Crew hint fires on complex prompt with no active project

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "active_project_id": null,
  "crew_hint_shown": false,
  "onboarding_complete": true,
  "needs_onboarding": false
}
EOF

echo '{"prompt": "I need to design and implement a new authentication system with OAuth2 providers, database schema migrations, and changes to three API services", "session_id": "sess-1"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
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
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `NO_HINT`

### 3. Crew hint re-fires at complexity=3 even when crew_hint_shown=True

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
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `HINT_FOUND` (re-fired despite crew_hint_shown=True)

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
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('HINT_FOUND' if 'crew:start' in ctx else 'NO_HINT')"
```

**Expected**: `NO_HINT`

### 5. crew_hint_shown flag is written after first hint

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"active_project_id": null, "crew_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "I need to design and implement a complete OAuth2 migration with database changes and API versioning strategy across multiple services", "session_id": "sess-5"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null > /dev/null

python3 -c "
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

### 6. Regression guard: hint fires at most once per prompt turn

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"active_project_id": null, "crew_hint_shown": true, "onboarding_complete": true, "needs_onboarding": false}
EOF

output=$(echo '{"prompt": "Help me plan and architect a complete migration of our monolith to microservices — first design the service boundaries, then implement the first service with full testing and after that build the full data migration pipeline with rollback support", "session_id": "sess-6"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print(ctx.count('crew:start'))")

echo "Hint count in output: ${output}"
[ "${output}" -le 1 ] && echo "SINGLE_HINT_OK" || echo "SPAM_DETECTED"
```

**Expected**: `SINGLE_HINT_OK`

## Expected Outcome

The crew hint appears precisely when needed: high-complexity prompts with no active project.
It is capped at one per prompt turn and respects the workspace-scoped active project detection.
The re-fire at complexity=3 gives a second nudge for genuinely large requests without spamming.

## Success Criteria

- [ ] Crew hint present for complex prompt with active_project_id=null
- [ ] Crew hint absent when active_project_id is set to a project name
- [ ] Crew hint re-fires at complexity=3 even when crew_hint_shown=True
- [ ] Low-complexity ("fix a typo") prompts produce no hint
- [ ] crew_hint_shown flag written to session state after first hint
- [ ] Hint appears at most once per prompt turn (no duplicates)
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
