---
description: Create or update a custom persona for on-demand invocation
argument-hint: "<name> --focus \"<focus>\" [--traits \"t1,t2\"] [--constraints \"FAILURE MODE — x: ...; ...\"] [--not-focus \"a; b\"] [--role <role>] [--save]"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:persona:define

Create or update a custom persona definition — the mechanism that lets an
enterprise inject ITS house personas. Stored in project-scoped DomainStore by
default. Use `--save` to also promote to the plugin-level cache for cross-project reuse.

A persona only earns its keep if it encodes something the base model does NOT
already supply: a **named failure-mode defense**, a **hard constraint**, or a
**scope guard**. A persona that only restates a role ("act like a senior X") adds
little durable value. The rubric below shows the GOOD pattern.

## Run it inline (no dispatch)

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/persona/refs/define.md")` — the rubric:
   argument parsing + validation, DomainStore script call, optional cache-save,
   and confirm output.
2. Apply the rubric directly using `$ARGUMENTS`.
