---
description: |
  Use when you need advanced gh CLI operations — debugging failed workflow runs, bulk PR management,
  or release automation — that go beyond what a plain `gh` man-page example covers.
  NOT for simple git operations (use Bash) or repo health (use platform:health).
argument-hint: "<operation: workflows|prs|releases|repo> [args]"
phase_relevance: ["build", "review", "operate"]
archetype_relevance: ["*"]
---

# /wicked-garden:platform:gh

GitHub CLI operations for workflow debugging, PR management, and release automation.

## Run it inline (no dispatch)

1. Parse `$ARGUMENTS`: `<operation> [args]` (operation = `workflows|prs|releases|repo`).
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/platform/gh/refs/gh.md")` — command reference for each
   operation category, multi-step patterns, and output format.
3. Execute the gh commands directly and deliver: for workflow failures, root cause + fix + re-run command;
   for PR management, status summary + action; for releases, release URL when created.
   For multi-step workflow generation from scratch, also load `skills/platform/actions/refs/actions.md`.
