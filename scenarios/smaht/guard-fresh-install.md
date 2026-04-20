---
name: guard-fresh-install
title: Setup Guard — Fresh Install (No Config)
description: Verify the prompt_submit guard blocks all prompts when no config.json exists, and passes setup/help commands through unconditionally
type: testing
difficulty: beginner
estimated_minutes: 8
---

# Setup Guard — Fresh Install (No Config)

This scenario tests the hard-block path in `_check_setup_gate` (AC-277-1, AC-277-3, AC-277-4,
AC-277-5). When the wicked-garden config (path resolved via `scripts/resolve_path.py`) does not exist, any prompt that
is not a setup/help command must exit 2. Setup commands must always pass through, and once a
config with `setup_complete=true` plus a session sentinel exist, normal prompts must be allowed.

## Setup

```bash
export TMPDIR=$(mktemp -d)
export TEST_HOME=$(mktemp -d)
```

## Steps

## Step 1: Non-setup prompt blocked when config absent

With no config file and no session state, `prompt_submit.py` must exit 2 and write a message
to stderr directing the user to run `/wicked-garden:setup`.

```bash
# Ensure no config exists under the synthetic home
WG_CONFIG="${TEST_HOME}/.something-wicked/wicked-garden/config.json"

# Write an empty session state (no setup_confirmed sentinel)
cat > "${TMPDIR}/wicked-garden-session-ac277-1.json" <<'EOF'
{}
EOF

CLAUDE_SESSION_ID="ac277-1" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "show me all open tasks", "session_id": "ac277-1"}' \
  2>&1
echo "Exit code: $?"
```

### Expected

- Exit code is `2`
- stderr contains `wicked-garden requires setup` or equivalent
- stdout does NOT contain a JSON response with `"continue": true`

---

## Step 2: Setup command passes through when config absent (AC-277-3)

Even without a config file, prompts that start with `/wicked-garden:setup` must be allowed
through so the user can actually complete setup.

```bash
cat > "${TMPDIR}/wicked-garden-session-ac277-3.json" <<'EOF'
{}
EOF

result=$(CLAUDE_SESSION_ID="ac277-3" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "/wicked-garden:setup", "session_id": "ac277-3"}' \
  2>/dev/null)

echo "Exit code: $?"
echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('PASS_THROUGH' if d.get('continue') else 'BLOCKED')
"
```

### Expected

- Exit code is `0`
- Output is `PASS_THROUGH`

---

## Step 3: Help command passes through when config absent (AC-277-3 variant)

```bash
cat > "${TMPDIR}/wicked-garden-session-ac277-3b.json" <<'EOF'
{}
EOF

result=$(CLAUDE_SESSION_ID="ac277-3b" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "/wicked-garden:help", "session_id": "ac277-3b"}' \
  2>/dev/null)

echo "Exit code: $?"
echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('PASS_THROUGH' if d.get('continue') else 'BLOCKED')
"
```

### Expected

- Exit code is `0`
- Output is `PASS_THROUGH`

---

## Step 4: Normal prompt allowed after config + session sentinel set (AC-277-4, AC-277-5)

Create a valid config and a session state with `setup_confirmed=true`. The guard fast-path
should read the sentinel and skip the config.json I/O entirely, letting the prompt through.

```bash
mkdir -p "${TEST_HOME}/.something-wicked/wicked-garden"
cat > "${TEST_HOME}/.something-wicked/wicked-garden/config.json" <<'EOF'
{
  "mode": "local",
  "setup_complete": true
}
EOF

cat > "${TMPDIR}/wicked-garden-session-ac277-5.json" <<'EOF'
{
  "setup_confirmed": true,
  "setup_complete": true,
  "onboarding_complete": true,
  "needs_onboarding": false,
  "setup_in_progress": false
}
EOF

result=$(CLAUDE_SESSION_ID="ac277-5" \
HOME="${TEST_HOME}" \
  python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" \
  <<< '{"prompt": "show me open tasks", "session_id": "ac277-5"}' \
  2>/dev/null)

echo "Exit code: $?"
echo "${result}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('PASS_THROUGH' if d.get('continue') else 'BLOCKED')
"
```

### Expected

- Exit code is `0`
- Output is `PASS_THROUGH`
- No setup directive appears in the response

## Expected Outcome

The guard exits 2 for any non-setup prompt when no config exists, passes setup/help commands
through unconditionally, and uses the `setup_confirmed` session sentinel to skip redundant
config.json I/O on every subsequent turn once setup is complete.

## Success Criteria

- [ ] Non-setup prompt exits 2 with informative stderr when no config.json (AC-277-1)
- [ ] `/wicked-garden:setup` passes through with exit 0 when no config (AC-277-3)
- [ ] `/wicked-garden:help` passes through with exit 0 when no config (AC-277-3)
- [ ] Normal prompt passes through after config + `setup_confirmed=true` sentinel (AC-277-4, AC-277-5)
- [ ] No setup directive injected into response after full setup confirmed

## Cleanup

```bash
rm -rf "${TMPDIR}" "${TEST_HOME}"
```
