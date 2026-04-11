---
name: crew-auto-routing
title: Crew Auto-Routing — Complexity Heuristic and Hint Lifecycle
description: Verify _estimate_complexity scoring, crew hint injection on SLOW path, once-per-session gate, and suppression when active_project_id is set
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Crew Auto-Routing — Complexity Heuristic and Hint Lifecycle

This scenario tests the crew routing logic added to `prompt_submit.py` (AC-279-1 through
AC-279-5). The `_estimate_complexity` function is exercised directly, and the full hook is
run to verify hint injection, the `crew_hint_shown` gate, and suppression when a crew
project is already active.

## Setup

```bash
export TMPDIR=$(mktemp -d)
export TEST_HOME=$(mktemp -d)

mkdir -p "${TEST_HOME}/.something-wicked/wicked-garden"
cat > "${TEST_HOME}/.something-wicked/wicked-garden/config.json" <<'EOF'
{
  "endpoint": "http://localhost:18889",
  "mode": "local",
  "setup_complete": true
}
EOF

# Shared fully-onboarded session state (no active project, hint not shown)
write_state() {
  local session="$1"
  local active_project="${2:-null}"
  local hint_shown="${3:-false}"
  cat > "${TMPDIR}/wicked-garden-session-${session}.json" <<STATEEOF
{
  "setup_confirmed": true,
  "setup_complete": true,
  "onboarding_complete": true,
  "needs_onboarding": false,
  "setup_in_progress": false,
  "active_project_id": ${active_project},
  "crew_hint_shown": ${hint_shown}
}
STATEEOF
}
```

## Steps

## Step 1: _estimate_complexity returns >= 3 for a complex multi-domain prompt (AC-279-1)

Import `_estimate_complexity` directly and assert it scores a maximally-complex prompt at 3.

```bash
python3 -c "
import sys, os
from pathlib import Path
plugin_root = Path(os.environ.get('CLAUDE_PLUGIN_ROOT', '.')).resolve()
sys.path.insert(0, str(plugin_root / 'scripts'))
sys.path.insert(0, str(plugin_root / 'scripts' / 'smaht' / 'v2'))
from smaht.v2.router import Router

prompt = (
    'Help me plan and architect a complete migration of our monolith to microservices. '
    'First design the service boundaries, then implement the first service with full testing, '
    'and after that build the full data migration pipeline with rollback support across '
    'multiple systems including the authentication, billing, and notification pipelines.'
)
score = Router()._estimate_complexity(prompt)
print(f'score={score}')
print('PASS' if score >= 3 else f'FAIL (expected >= 3, got {score})')
"
```

### Expected

- Output contains `score=3`
- Output contains `PASS`

---

## Step 2: Crew suggestion text includes `/wicked-garden:crew:start` (AC-279-2)

Run the full hook with a complexity-3 prompt and verify the suggestion text appears in
`additionalContext` with the correct crew command.

```bash
write_state "ac279-2" "null" "false"

result=$(CLAUDE_SESSION_ID="ac279-2" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "Help me plan and architect a complete migration of our monolith to microservices. First design the service boundaries, then implement the first service with full testing, and after that build the full data migration pipeline with rollback support across multiple systems.", "session_id": "ac279-2"}' \
  2>/dev/null)

echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ctx = d.get('hookSpecificOutput', {}).get('additionalContext', '') or d.get('additionalContext', '')
has_crew = '/wicked-garden:crew:start' in ctx
print('CREW_SUGGESTION_PRESENT' if has_crew else 'NO_SUGGESTION')
"
```

### Expected

- Output is `CREW_SUGGESTION_PRESENT`

---

## Step 3: crew_hint_shown=True written to session state after suggestion fires (AC-279-3)

After the hint is shown, the `crew_hint_shown` flag must be persisted to session state so
the hint is not re-shown on the next normal prompt.

```bash
write_state "ac279-3" "null" "false"

CLAUDE_SESSION_ID="ac279-3" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "Help me plan and architect a complete migration of our monolith to microservices. First design the service boundaries, then implement the first service with full testing, and after that build the full data migration pipeline with rollback support across multiple systems.", "session_id": "ac279-3"}' \
  2>/dev/null > /dev/null

python3 -c "
import json, glob
session_files = glob.glob('${TMPDIR}/wicked-garden-session-ac279-3*.json')
if not session_files:
    print('NO_SESSION_FILE')
else:
    d = json.loads(open(session_files[0]).read())
    print('FLAG_SET' if d.get('crew_hint_shown') else 'FLAG_NOT_SET')
"
```

### Expected

- Output is `FLAG_SET`

---

## Step 4: No second suggestion on next prompt when crew_hint_shown=True (AC-279-3)

The once-per-session gate must prevent the hint from firing again when `crew_hint_shown` is
already true and complexity is 2 (not the complexity=3 re-fire threshold).

```bash
# crew_hint_shown=true, complexity-2 prompt (long but not max)
write_state "ac279-4" "null" "true"

result=$(CLAUDE_SESSION_ID="ac279-4" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "I need to design a new authentication system with OAuth2 providers and database schema migrations across three API services", "session_id": "ac279-4"}' \
  2>/dev/null)

echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ctx = d.get('hookSpecificOutput', {}).get('additionalContext', '') or d.get('additionalContext', '')
count = ctx.count('/wicked-garden:crew:start')
print(f'hint_count={count}')
print('NO_REPEAT' if count == 0 else 'HINT_REPEATED')
"
```

### Expected

- Output contains `hint_count=0`
- Output contains `NO_REPEAT`

---

## Step 5: No suggestion when active_project_id is set (AC-279-5)

When an active crew project exists in the workspace, the hint must be suppressed entirely
even for a maximally-complex prompt.

```bash
write_state "ac279-5" '"my-active-project"' "false"

result=$(CLAUDE_SESSION_ID="ac279-5" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "Help me plan and architect a complete migration of our monolith to microservices. First design the service boundaries, then implement the first service with full testing, and after that build the full data migration pipeline with rollback support across multiple systems.", "session_id": "ac279-5"}' \
  2>/dev/null)

echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ctx = d.get('hookSpecificOutput', {}).get('additionalContext', '') or d.get('additionalContext', '')
print('SUPPRESSED' if '/wicked-garden:crew:start' not in ctx else 'NOT_SUPPRESSED')
"
```

### Expected

- Output is `SUPPRESSED`

## Expected Outcome

`_estimate_complexity` correctly scores multi-signal prompts at 3. The crew routing logic
in prompt_submit injects the hint exactly when needed: SLOW path, high complexity, no active
project, hint not yet shown. The `crew_hint_shown` flag is persisted and prevents re-firing
except at complexity=3. An active project always suppresses the hint.

## Success Criteria

- [ ] `_estimate_complexity` returns 3 for a prompt with length, architecture, planning, and multi-step signals (AC-279-1)
- [ ] `/wicked-garden:crew:start` present in `additionalContext` for qualifying prompts (AC-279-2)
- [ ] `crew_hint_shown=True` written to session state after hint fires (AC-279-3)
- [ ] Hint does not re-fire on the next prompt at complexity=2 when `crew_hint_shown=True` (AC-279-3)
- [ ] Hint suppressed when `active_project_id` is set to a non-null value (AC-279-5)

## Cleanup

```bash
rm -rf "${TMPDIR}" "${TEST_HOME}"
```
