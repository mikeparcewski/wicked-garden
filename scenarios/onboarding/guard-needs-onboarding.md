---
name: guard-needs-onboarding
title: Setup Guard — Needs Onboarding (Config Present, Project Not Onboarded)
description: Verify the onboarding directive is injected when setup_confirmed=true but needs_onboarding=true, and that the guard fails open on corrupt session state
type: testing
difficulty: intermediate
estimated_minutes: 8
---

# Setup Guard — Needs Onboarding (Config Present, Project Not Onboarded)

This scenario tests the soft-gate path in `_check_setup_gate` (AC-277-2, AC-277-6). When
`config.json` is present with `setup_complete=true` and the session sentinel confirms setup,
but `needs_onboarding=true` and `onboarding_complete=false`, the guard must inject an
onboarding directive into `additionalContext` rather than exiting 2. The guard must also
fail open (allow the prompt through) when the session state file is corrupt.

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
```

## Steps

## Step 1: Onboarding directive injected when needs_onboarding=true (AC-277-2)

With setup confirmed but the project not yet onboarded, prompt_submit must inject a directive
into `additionalContext` telling Claude to invoke the onboarding wizard immediately. The prompt
must NOT be hard-blocked (exit 0, `"continue": true`).

```bash
cat > "${TMPDIR}/wicked-garden-session-ac277-2.json" <<'EOF'
{
  "setup_confirmed": true,
  "setup_complete": true,
  "needs_onboarding": true,
  "onboarding_complete": false,
  "setup_in_progress": false
}
EOF

result=$(CLAUDE_SESSION_ID="ac277-2" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "what tasks are in progress?", "session_id": "ac277-2"}' \
  2>/dev/null)

echo "Exit code: $?"
echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ctx = d.get('hookSpecificOutput', {}).get('additionalContext', '') or d.get('additionalContext', '')
has_directive = 'wicked-garden:setup' in ctx or 'Action Required' in ctx
is_continued = d.get('continue', False)
print('DIRECTIVE_INJECTED' if has_directive and is_continued else 'UNEXPECTED')
print('continue=' + str(is_continued))
"
```

### Expected

- Exit code is `0`
- Output contains `DIRECTIVE_INJECTED`
- `continue` is `true` — the prompt is NOT hard-blocked

---

## Step 2: Fail open on corrupt session state file (AC-277-6)

When the session state file contains invalid JSON, the guard must not crash or block the user.
It should fall back to reading config.json directly and allow the prompt through.

```bash
# Write deliberately malformed JSON to the session file
printf '{broken json!!' > "${TMPDIR}/wicked-garden-session-ac277-6.json"

result=$(CLAUDE_SESSION_ID="ac277-6" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "what tasks are in progress?", "session_id": "ac277-6"}' \
  2>/dev/null)

echo "Exit code: $?"
echo "${result}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('PASS_THROUGH' if d.get('continue') else 'BLOCKED')
except Exception as e:
    print('INVALID_JSON_RESPONSE:', e)
"
```

### Expected

- Exit code is `0`
- Output is `PASS_THROUGH` — corrupt session state does not block the user

## Expected Outcome

The onboarding directive is injected as `additionalContext` whenever the project needs
onboarding, without blocking the prompt (exit 2 is reserved for the no-config case). When
session state is unreadable the guard falls back gracefully and always allows the prompt through.

## Success Criteria

- [ ] Onboarding directive present in `additionalContext` when `needs_onboarding=true` (AC-277-2)
- [ ] `"continue": true` in response — not a hard exit 2 (AC-277-2)
- [ ] Directive references `wicked-garden:setup` or `Action Required` text
- [ ] Corrupt session state file results in exit 0 and `"continue": true` (AC-277-6)
- [ ] No Python traceback on stderr when session file is corrupt

## Cleanup

```bash
rm -rf "${TMPDIR}" "${TEST_HOME}"
```
