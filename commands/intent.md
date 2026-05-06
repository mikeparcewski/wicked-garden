---
allowed-tools: ["Bash"]
description: "Show or set the session intent variable (simple-edit | feature | rigor | research). Sticky for the session; auto-detect resets next session."
argument-hint: "[simple-edit|feature|rigor|research]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:intent

Show or override the session intent variable — the v10 Phase 1 keystone (#813). Auto-detected on turn 1; sticky for the session; this command overrides explicitly.

**Vocabulary (locked)**: `simple-edit | feature | rigor | research`. To change, run a brainstorm — don't add ad-hoc.

**Usage**:
- `/wicked-garden:intent` — show the effective current value and how it was set
- `/wicked-garden:intent <value>` — explicit override; sticky until session end

```bash
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

After explicit override, the next system-reminder echoes a bare `<wg intent="X" t=N />` label so the model can see the user steered the framework. Auto-detected intent stays invisible (prevents confirmation bias).

References: brain memory `v10-intent-variable-design-decision`, brainstorm `v10-session-01-intent-and-hook-gating`, PR #814 (the original Phase 1 ship), PRs #818/#819 (skill-discovery patches that proved skills under `skills/{domain}/{name}/SKILL.md` don't surface as slash commands — hence this command file).
