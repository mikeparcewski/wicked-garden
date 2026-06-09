---
description: |
  Use when generating API docs, READMEs, guides, or inline comments from existing code, or improving
  documentation that has drifted from implementation. NOT for architecture docs (use engineering:arch).
argument-hint: "<file or component> [--type api|readme|guide|inline]"
phase_relevance: ["design", "build"]
archetype_relevance: ["*"]
---

# /wicked-garden:engineering:docs

Generate documentation from code or improve existing documentation. Supports API docs, READMEs,
guides, and inline comments.

## Run it inline (no dispatch)

1. Parse `<file or component>` and `--type` (api | readme | guide | inline). Infer if absent:
   `.ts/.py/.go` → api or inline; top-level directory → readme; workflow request → guide.
2. `Read("${CLAUDE_PLUGIN_ROOT}/skills/engineering/refs/docs.md")` — type-routing table,
   pre-generation checklist, API/README/guide/inline checklists, OpenAPI template, and quality
   standards.
3. Read the source code: public interfaces, function signatures, types, error conditions, and
   existing docs (check for drift from implementation).
4. Apply the type-appropriate checklist and generate the documentation inline following the
   output template in the rubric.
5. Present the documentation for user review before writing to file. When writing: API docs →
   `docs/api/`; READMEs → component root; guides → `docs/guides/`; inline → Edit tool in-file.
