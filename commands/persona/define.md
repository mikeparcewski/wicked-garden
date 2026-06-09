---
description: Create or update a custom persona for on-demand invocation
argument-hint: "<name> --focus \"<focus>\" [--traits \"<t1,t2>\"] [--role <role>] [--save]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:persona:define

Create or update a custom persona definition. Stored in project-scoped DomainStore
by default. Use `--save` to also promote to the plugin-level cache for cross-project reuse.

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/persona/refs/define.md")` — the rubric:
   argument parsing + validation, DomainStore script call, optional cache-save,
   and confirm output.
2. Apply the rubric directly using `$ARGUMENTS`.
