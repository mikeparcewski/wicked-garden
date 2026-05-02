---
description: "Context-aware next-step suggestions — what should I do next? Stuck? Need next steps? Use this for context-aware command discovery."
argument-hint: "[workspace]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:crew:guide

Inspect the current workspace state and return a ranked list of "what to do
next" suggestions. Each suggestion includes the exact slash command to invoke
and a one-line rationale. Use this when you are stuck, unsure what to run
next, or want context-aware command discovery.

> **Read-only** — this command never writes state.

> **Context-aware (Issue #725)**: when an active crew project exists, the
> suggestion list is filtered by the project's current phase + detected
> archetype. With no active project, the bootstrap entry-point set surfaces
> instead — derived from `phase_relevance: ["bootstrap"]` frontmatter, not a
> hand-curated starter list.

## Instructions

### 1. Run the guide inspector

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/crew/guide.py" \
  "${ARGUMENTS}" --json
```

Parse the JSON list from stdout. Each item has:
- `rank` (int) — priority order, 1 = highest urgency
- `command` (str) — the exact slash command to invoke
- `rationale` (str) — one-line explanation of why this is suggested

### 2. Display suggestions

Present the suggestions as a numbered list:

```
## What to do next

1. `/wicked-garden:crew:gate`
   Open CONDITIONAL gate with unresolved conditions in phase(s): design — review and clear before advancing.

2. `/wicked-garden:crew:execute`
   Project 'my-project' has been on phase 'build' for 6h — run execute to advance.
```

If the list is empty, output: "No suggestions — context is clear."

### 3. Offer to invoke the top suggestion

After displaying the list, ask the user:
"Run suggestion 1 now? (yes / no / pick a number)"

If the user confirms, dispatch the corresponding command inline.

> Do NOT auto-invoke without confirmation. The guide is informational first.
