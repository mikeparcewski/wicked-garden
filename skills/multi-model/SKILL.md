---
name: wicked-garden-multi-model
context: fork
description: |
  DEPRECATED — collapsed into the jam council surface. The multi-model council
  now lives entirely in `wicked-garden-jam` (its `council` sub-action) and the
  worker `wicked-garden-jam-council`. This stub only keeps existing
  registry/manifest references resolving; it dispatches nothing.

  Use `wicked-garden-jam` with `council <topic> --options "A, B, C"` instead.
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# Multi-Model Collaboration (deprecated — see jam council)

The multi-model council is **not maintained here**. It was consolidated into the
jam domain during the skills-only cutover; this file previously duplicated that
mechanism and pointed at retired paths (`agents/jam/council.md`, and the
`/jam:council` · `/jam:quick` · `/jam:brainstorm` slash commands) that no longer
exist. One council surface, not two.

**Where it actually lives now:**

| You want… | Use |
|-----------|-----|
| A multi-model council verdict on defined options | `wicked-garden-jam` → `council <topic> --options "A, B, C"` |
| The council worker (detect+probe CLIs, 4-question scaffold, isolated parallel dispatch, 3-stage synthesis, verdict) | `wicked-garden-jam-council` (dispatched by jam's `council` sub-action) |
| A single-model, multi-persona brainstorm | `wicked-garden-jam` → `brainstorm <topic>` |
| A fast gut-check | `wicked-garden-jam` → `quick <topic>` |

The CLI registry, probe logic, quorum/fallback, and synthesis framework are all
owned by `wicked-garden-jam-council` — see `skills/jam-council/SKILL.md`. Do not
re-document them here.

## Routing note (council-is-the-router)

Intent / work-shape routing is a **native model capability** — the former
wicked-signals classifier product was archived on that basis. The always-on
router is `wicked-garden-classify` (one model classifying the prompt with full
tool access). `wicked-garden-jam-council` is the **escalation** council for
genuinely hard / high-stakes routing or decision calls — not a per-prompt
router. See `skills/classify/SKILL.md` → "Routing model".
