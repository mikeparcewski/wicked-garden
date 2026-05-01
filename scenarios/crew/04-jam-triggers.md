---
name: jam-triggers
title: Jam Session Suggestion Triggers
description: Verify jam hints fire on FAST/SLOW paths only; synthesis-path prompts skip all hints
type: testing
difficulty: beginner
estimated_minutes: 6
---

# Jam Session Suggestion Triggers

This scenario verifies that prompts containing exploration and ambiguity signals receive a jam
session suggestion on FAST and SLOW paths. Important: prompts that trigger the synthesis path
(complex + risky or high complexity heuristic score) return early from the hook before any hints
are appended — jam and crew suggestions are never emitted on the synthesis path.

Jam suggestions fire on FAST/SLOW paths only, the suggestion is suppressed when a jam command
is already in the prompt, the one-per-session gate prevents repeat suggestions, and jam hints
do not compete with active onboarding directives.

## Setup

```bash
export TMPDIR=$(mktemp -d)
```

## Steps

### 1. Jam suggestion fires on tradeoff prompt

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "Compare the tradeoffs of caching with Redis versus computing on demand for the leaderboard.", "session_id": "sess-1"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('JAM_FOUND' if 'jam:' in ctx else 'NO_JAM')"
```

**Expected**: `JAM_FOUND`

### 2. Jam suggestion names specific commands

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "Should we use a monorepo or separate repos? Explore the options.", "session_id": "sess-2"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); has_quick='jam:quick' in ctx; has_brainstorm='jam:brainstorm' in ctx; print('NAMED' if has_quick or has_brainstorm else 'UNNAMED')"
```

**Expected**: `NAMED`

### 3. Jam suggestion suppressed when /jam: already in prompt

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "/wicked-garden:jam:quick thinking through tradeoffs for session storage options", "session_id": "sess-3"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); count=ctx.count('jam:'); print('DUPLICATE' if count > 1 else 'OK')"
```

**Expected**: `OK` (no duplicate suggestion appended)

### 4. Session gate prevents second jam suggestion

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": true, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "Should we use option A or B? Compare the alternatives and tradeoffs.", "session_id": "sess-4"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('JAM_FOUND' if '[Suggestion]' in ctx and 'jam:' in ctx else 'NO_JAM')"
```

**Expected**: `NO_JAM`

### 5. jam_hint_shown flag written after first suggestion

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "What are the tradeoffs between GraphQL and REST for our API?", "session_id": "sess-5"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null > /dev/null

sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, glob
files = glob.glob('${TMPDIR}/wicked-garden-session-*.json')
if files:
    d = json.loads(open(files[0]).read())
    print('FLAG_SET' if d.get('jam_hint_shown') else 'FLAG_NOT_SET')
else:
    print('NO_SESSION_FILE')
"
```

**Expected**: `FLAG_SET`

### 6. Jam suggestion can fire alongside an active onboarding directive

Jam and onboarding are independent signals: the user can see both. The hook does not
suppress the jam suggestion when onboarding is active — both are appended and the model
is free to act on whichever is more relevant.

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "jam_hint_shown": false,
  "onboarding_complete": false,
  "needs_onboarding": true,
  "setup_in_progress": false
}
EOF

echo '{"prompt": "What are the tradeoffs between these design options? Compare alternatives.", "session_id": "sess-6"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); has_jam='[Suggestion]' in ctx and 'jam:' in ctx; has_onboarding='setup' in ctx.lower(); print(f'jam={has_jam} onboarding={has_onboarding}')"
```

**Expected**: `jam=True onboarding=True` (independent signals — both appended)

### 7. Synthesis-path prompts do NOT emit jam or crew hints

Prompts that trigger the synthesis path (high complexity + deep-work signals) cause the hook
to return early with only the synthesis directive. The jam suggestion and crew hint code is
never reached. Verify that a clearly synthesis-eligible prompt produces no jam hint.

```bash
export CLAUDE_SESSION_ID=test
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "jam_hint_shown": false,
  "crew_hint_shown": false,
  "active_project_id": null,
  "onboarding_complete": true,
  "needs_onboarding": false
}
EOF

echo '{"prompt": "I need to design and implement a migration strategy — but should we use a strangler fig pattern or big bang? Help me think through the tradeoffs and alternatives across the system architecture", "session_id": "sess-7"}' \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); is_synthesis='path=synthesis' in ctx or 'synthesize' in ctx.lower(); has_jam='[Suggestion]' in ctx and 'jam:' in ctx; print(f'synthesis={is_synthesis} jam={has_jam}')"
```

**Expected**: `synthesis=True jam=False` (synthesis path returns early; jam hint never appended)

## Expected Outcome

Jam suggestions fire precisely for prompts with exploration intent on FAST or SLOW paths, once
per session, without conflicting with onboarding directives or duplicating existing jam
invocations. Prompts that trigger the synthesis path (high complexity/risk) return early and
never reach the jam suggestion code — synthesis and jam are mutually exclusive per prompt turn.

## Success Criteria

- [ ] Jam suggestion appended for prompts with tradeoffs/options/alternatives (FAST/SLOW path)
- [ ] Suggestion names jam:quick or jam:brainstorm (not generic)
- [ ] No duplicate suggestion when prompt already contains /jam:
- [ ] jam_hint_shown=True prevents second suggestion
- [ ] jam_hint_shown flag written to session state after first suggestion
- [ ] Jam suggestion can fire alongside an onboarding directive (independent signals)
- [ ] Synthesis-path prompts produce no jam hint (synthesis and jam are mutually exclusive)

## Value Demonstrated

Jam session suggestions connect ambiguity signals to user-facing guidance. The synthesis path
intentionally takes priority for high-complexity prompts — users on that path get the full
synthesis skill invoked before answering, which is more useful than a jam suggestion alone.
Jam suggestions target the common case: medium-complexity FAST/SLOW path prompts where the user
would benefit from structured thinking but the request doesn't warrant full synthesis.

## Cleanup

```bash
rm -rf "${TMPDIR}"
```
