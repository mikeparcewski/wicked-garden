---
description: |
  Use when you have a bug, error, or unexpected behavior and need structured hypothesis-driven diagnosis —
  root cause, reproduction steps, fix, and prevention. NOT for code review (use engineering:review)
  or architecture analysis (use engineering:arch).
argument-hint: "<error message, symptom, or issue description>"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:engineering:debug

Start a systematic debugging session to diagnose issues, trace root causes, and develop fixes.

## Run it inline (no dispatch)

1. Parse the error message, symptom, or issue description from the argument.
2. Use `Skill("superpowers:systematic-debugging")` — the full hypothesis-driven debugging
   methodology (gather context, form hypothesis, test, document root cause).
3. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/debug.md")` for garden-specific heuristics:
   check the wicked-bus first, loom/vault availability for gate failures, cross-platform hook issues,
   and the standard debug output format.
4. Apply the six-step process. Read relevant files at error locations, search for related patterns,
   check logs if available.
5. Emit the standard Debug Analysis output format (Symptom, Root Cause with confidence, Evidence,
   Reproduction Steps, Recommended Fix with rationale, Verification, Prevention).
6. If the user approves the fix, implement it, add a regression test, and verify resolution.
