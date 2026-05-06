---
name: intent
description: |
  Show or set the session intent variable. Intent gates how loud the
  framework is — simple-edit (silent), feature/research (synthesis
  directive), rigor (full crew context). Auto-detected on turn 1;
  this skill overrides explicitly. Sticky for the session.

  Use when: "set intent", "intent override", "/wicked-garden:intent",
  "make the framework quiet", "force rigor", "what's my intent".
---

# /wicked-garden:intent

Session intent is the keystone of v10's steer-not-block model. It's auto-detected from the first turn's prompt and made sticky for the rest of the session. This skill lets you (or a command on your behalf) override that auto-detection without using flags or fighting validators.

## Vocabulary

Four values, locked. To change the vocabulary, run a brainstorm — don't add ad-hoc.

| Intent | When to set | What fires |
|---|---|---|
| `simple-edit` | Trivial turns, status checks, continuations | Nothing — silent |
| `feature` | Building / fixing / refactoring code | Synthesis directive (wicked-brain pull) |
| `research` | Conceptual questions, "explain how", "why does" | Synthesis directive (wicked-brain pull) |
| `rigor` | Crew sessions, multi-phase work, audit trail required | Synthesis directive + active-chain context |

## Usage

```
/wicked-garden:intent              # show effective current value
/wicked-garden:intent rigor        # set explicit override
/wicked-garden:intent simple-edit  # quiet the framework
```

## Behavior

- Sets `state.intent` and `state.intent_explicit=True` in session state via `scripts/_session.py::SessionState.update`.
- Sticky for the rest of the session; reset by SessionEnd hook.
- Explicit override echoes a bare `<wg intent="X" t=N />` label in the next system-reminder so the model knows the user (or a command) steered the framework.
- Auto-detected intent stays invisible to the model — prevents confirmation bias.

## Implementation (≤30 lines, slim-skill shape per v10 Phase 2)

```bash
# Show or set session intent. Pass nothing to display; pass a value to override.
# Heredoc is single-quoted (<<'PY') so the shell does NOT expand $variables
# inside the Python source — the script reads CLAUDE_PLUGIN_ROOT via
# os.environ instead, which is inherited by the subprocess.
ARG="${1:-}"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" - "$ARG" <<'PY'
import os
import sys

plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if not plugin_root:
    print("error: CLAUDE_PLUGIN_ROOT not set", file=sys.stderr)
    sys.exit(1)
sys.path.insert(0, os.path.join(plugin_root, "scripts"))

from _session import SessionState

VALID = ("simple-edit", "feature", "rigor", "research")
arg = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
state = SessionState.load()

if not arg:
    eff = state.intent or "(not set; auto-detect runs on next turn)"
    src = "explicit" if state.intent_explicit else "auto-detected" if state.intent else "n/a"
    print(f"intent: {eff}  ({src})")
    sys.exit(0)

if arg not in VALID:
    print(f"error: '{arg}' not in {VALID}", file=sys.stderr)
    sys.exit(1)

state.update(intent=arg, intent_explicit=True)
print(f"intent set: {arg}  (explicit override; sticky until session end)")
PY
```

## Notes

- **Auto-detection runs once** on the first 1-2 turns and is sticky thereafter. If auto-detect picks the wrong value, override with this skill once and it sticks for the session.
- **Commands may self-declare** by calling this skill internally as their first action — e.g. a future `crew:start` could call `/wicked-garden:intent rigor` to ensure the rigor directive fires from turn 1, even if the user's first prompt was short.
- **Issue #813** for the design rationale + brainstorm record.
