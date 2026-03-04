---
name: jam-triggers
title: Jam Session Suggestion Triggers
description: Verify jam hints fire for ambiguity signals and respect the session gate and path guards
type: testing
difficulty: beginner
estimated_minutes: 6
---

# Jam Session Suggestion Triggers

This scenario verifies that prompts containing exploration and ambiguity signals receive a jam
session suggestion on FAST and SLOW paths, that the suggestion is suppressed when a jam command
is already in the prompt, that the one-per-session gate works, and that jam suggestions do not
compete with active onboarding directives.

## Setup

```bash
export TMPDIR=$(mktemp -d)
```

## Steps

### 1. Jam suggestion fires on tradeoff prompt

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "What are the tradeoffs between using Redis vs Postgres for session storage? Compare the alternatives.", "session_id": "sess-1"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('JAM_FOUND' if 'jam:' in ctx else 'NO_JAM')"
```

**Expected**: `JAM_FOUND`

### 2. Jam suggestion names specific commands

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "Should we use a monorepo or separate repos? Explore the options.", "session_id": "sess-2"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); has_quick='jam:quick' in ctx; has_brainstorm='jam:brainstorm' in ctx; print('NAMED' if has_quick or has_brainstorm else 'UNNAMED')"
```

**Expected**: `NAMED`

### 3. Jam suggestion suppressed when /jam: already in prompt

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "/wicked-garden:jam:quick thinking through tradeoffs for session storage options", "session_id": "sess-3"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); count=ctx.count('jam:'); print('DUPLICATE' if count > 1 else 'OK')"
```

**Expected**: `OK` (no duplicate suggestion appended)

### 4. Session gate prevents second jam suggestion

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": true, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "Should we use option A or B? Compare the alternatives and tradeoffs.", "session_id": "sess-4"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print('JAM_FOUND' if '[Suggestion]' in ctx and 'jam:' in ctx else 'NO_JAM')"
```

**Expected**: `NO_JAM`

### 5. jam_hint_shown flag written after first suggestion

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{"jam_hint_shown": false, "onboarding_complete": true, "needs_onboarding": false}
EOF

echo '{"prompt": "What are the tradeoffs between GraphQL and REST for our API?", "session_id": "sess-5"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null > /dev/null

python3 -c "
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

### 6. Jam suggestion does not fire when onboarding directive is active

```bash
cat > "${TMPDIR}/wicked-garden-session-test.json" <<'EOF'
{
  "jam_hint_shown": false,
  "onboarding_complete": false,
  "needs_onboarding": true,
  "setup_in_progress": false
}
EOF

echo '{"prompt": "What are the tradeoffs between these design options? Compare alternatives.", "session_id": "sess-6"}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); has_jam='[Suggestion]' in ctx and 'jam:' in ctx; has_onboarding='setup' in ctx.lower(); print(f'jam={has_jam} onboarding={has_onboarding}')"
```

**Expected**: `jam=False onboarding=True`

### 7. Jam and crew hints can coexist

```bash
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
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/prompt_submit.py" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); ctx=d.get('additionalContext',''); print(f'crew={\"crew:start\" in ctx} jam={\"jam:\" in ctx}')"
```

**Expected**: `crew=True jam=True`

## Expected Outcome

Jam suggestions fire precisely for prompts with exploration intent, once per session, without
conflicting with onboarding directives or duplicating existing jam invocations. Crew and jam
suggestions can coexist in the same context injection.

## Success Criteria

- [ ] Jam suggestion appended for prompts with tradeoffs/options/alternatives
- [ ] Suggestion names jam:quick or jam:brainstorm (not generic)
- [ ] No duplicate suggestion when prompt already contains /jam:
- [ ] jam_hint_shown=True prevents second suggestion
- [ ] jam_hint_shown flag written to session state after first suggestion
- [ ] No jam suggestion when onboarding directive is active
- [ ] Jam and crew suggestions coexist when both conditions are met

## Value Demonstrated

Jam session suggestions were never emitted before this change — the `jam` intent classification
was used only for FAST-path adapter selection, never for user-facing guidance. Connecting
ambiguity signals to jam suggestions closes the gap between detecting that a prompt needs
structured thinking and actually offering the tool for it.

## Cleanup

```bash
rm -rf "${TMPDIR}"
```
