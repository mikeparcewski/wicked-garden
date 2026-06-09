---
description: Code review with senior engineering perspective on quality, patterns, and maintainability
argument-hint: "[file or directory path] [--focus security|performance|patterns|tests] [--scenarios] [--persona <name>]"
phase_relevance: ["build", "review"]
archetype_relevance: ["code-repo", "schema-migration", "config-infra"]
---

# /wicked-garden:engineering:review

Senior-engineer code review on quality, patterns, maintainability. Use `--focus security|performance|
patterns|tests` to deepen one area. Use `--persona <name>` to apply a registered persona's lens.
Use `--scenarios` to emit wicked-scenarios regression blocks per Critical/High finding.
Use `engineering:arch` for component/system-level architecture review.

## Run it inline (no dispatch)

1. Parse scope (path or git-diff target), `--focus`, `--persona`, and `--scenarios`.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/review.md")` — R1–R6 Bulletproof Coding
   Standards, T1–T6 Bulletproof Testing Standards, agent overstepping checklist, focus lane
   definitions, persona routing instructions, wicked-scenarios format, and output template.
3. **Persona branch** (only if `--persona <name>` present): resolve the persona via
   `scripts/persona/registry.py --get {name} --json`. If found, apply the review through that
   persona's frame. If not found, warn and fall through.
4. Read the target file(s) / diff. Apply R1–R6 to all code; add T1–T6 when `--focus tests` or
   reviewing test files. If `--focus` given, deepen that lane. Flag agent overstepping (scope creep,
   commented-out code, over-engineering) with `file:line` citations.
5. Emit the standard Engineering Review output (Strengths, Issues table with rule + location,
   Architecture Notes, Maintainability Concerns, Agent Overstepping, Recommendations).
   If `--scenarios`, append wicked-scenarios blocks for each Critical/High finding.
