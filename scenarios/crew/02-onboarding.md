---
name: onboarding
title: Forced Onboarding Enforcement
description: Verify onboarding directives fire for each partial-state combination and that the setup command is never blocked
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Forced Onboarding Enforcement

This scenario verifies the OR-based onboarding check introduced in T2-1. Three distinct states
are tested: memories absent (full setup directive), index absent with memories present (soft
index directive), and both present (no directive). It also verifies the per-turn re-check in
prompt_submit.py and that the setup command is never blocked.

## Setup

```bash
export TMPDIR=$(mktemp -d)
```

## Steps

### 1. Full setup directive fires when memories absent

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "onboarding_complete": false,
  "needs_onboarding": true,
  "setup_in_progress": false
}
EOF

echo '{"prompt": "show me the current task list", "session_id": "sess-1"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('SETUP_DIRECTIVE' if 'wicked-garden:setup' in ctx else 'NO_DIRECTIVE')"
```

**Expected**: `SETUP_DIRECTIVE`

### 2. Index-only directive fires when memories present but index absent (AC-2.3 guard)

This step validates the AND-to-OR fix. The index-only case must produce a softer directive
pointing to `search:index`, not the full setup wizard invocation.

```bash
# Simulate the state that bootstrap writes when: memories=present, index=absent
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "onboarding_complete": false,
  "needs_onboarding": true,
  "setup_in_progress": false,
  "_test_hint": "memories_present_index_absent"
}
EOF

# The directive content depends on bootstrap.py correctly writing needs_onboarding=True
# for the index-only case. Verify by inspecting bootstrap output after removing only the DB.
# For this scenario, we verify that the prompt_submit output when needs_onboarding=True
# does NOT contain the full setup wizard call when onboarding_complete remains False.
# The distinction between full vs. soft directive is set by bootstrap — test via bootstrap output.

echo "Step 2: Verify via bootstrap output inspection"
echo "Run bootstrap.py with search DB removed and memories present."
echo "Assert: bootstrap output contains 'search:index' directive."
echo "Assert: bootstrap output does NOT contain full 'wicked-garden:setup' invocation."
```

**Note**: Full verification of this step requires running bootstrap.py in an environment where
the search database is absent but wicked-mem has onboarding memories. In automated testing,
this is done by removing the search index under `~/.something-wicked/wicked-garden/projects/{project-slug}/` and
confirming memories exist in the local memory store before running bootstrap.py.

### 3. No directive fires when both memories and index present

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "onboarding_complete": true,
  "needs_onboarding": false,
  "setup_in_progress": false
}
EOF

echo '{"prompt": "show me current tasks", "session_id": "sess-3"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('NO_DIRECTIVE' if 'wicked-garden:setup' not in ctx and 'search:index' not in ctx else 'DIRECTIVE_FOUND')"
```

**Expected**: `NO_DIRECTIVE`

### 4. Setup command passes through even when onboarding required

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"onboarding_complete": false, "needs_onboarding": true, "setup_in_progress": false}
EOF

echo '{"prompt": "/wicked-garden:setup", "session_id": "sess-4"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null
echo "Exit code: $?"
```

**Expected**: exit code 0 (not blocked)

### 5. Per-turn re-check skipped when onboarding_complete=True

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"onboarding_complete": true, "needs_onboarding": false, "setup_in_progress": false}
EOF

echo '{"prompt": "what tasks are pending?", "session_id": "sess-5"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('CLEAN' if 'setup' not in ctx.lower() else 'UNEXPECTED_DIRECTIVE')"
```

**Expected**: `CLEAN`

### 6. Regression guard: setup_in_progress=True prevents blocking loop

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"onboarding_complete": false, "needs_onboarding": true, "setup_in_progress": true}
EOF

result=$(echo '{"prompt": "what is next?", "session_id": "sess-6"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null; echo $?)

echo "Exit code: ${result}"
```

**Expected**: exit code 0 (setup already in progress, not re-blocked)

## Expected Outcome

The onboarding gate fires with the appropriate directive strength for each state combination.
Users with partial setup are never blocked from using `/wicked-garden:setup` to complete it.
Once fully onboarded, the per-turn re-check is bypassed entirely.

## Success Criteria

- [ ] Full setup directive fires when needs_onboarding=True in session state
- [ ] No directive fires when onboarding_complete=True
- [ ] Setup command is not blocked during onboarding required state
- [ ] Per-turn re-check skipped when onboarding_complete=True
- [ ] setup_in_progress=True prevents re-blocking mid-wizard
- [ ] bootstrap.py writes onboarding_complete=True only when both memories and index present (AC-2.3)
- [ ] bootstrap.py emits index-only directive when memories present but index absent (AC-2.3)

## Value Demonstrated

The AND-to-OR fix prevents silent onboarding gaps where a project has memories but no search
index, or vice versa. Each missing component gets a specific, targeted directive rather than
a catch-all that either fires for both or neither.

## Cleanup

```bash
rm -rf "${TMPDIR}"
```
