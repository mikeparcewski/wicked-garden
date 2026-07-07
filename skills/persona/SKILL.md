---
name: wicked-garden-persona
context: fork
description: |
  On-demand persona invocation system for applying named perspectives to any task.
  Use when: invoking a named persona via persona:as, defining or listing
  personas, or reviewing work through a specific role's perspective.
disable-model-invocation: true
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# Persona System

On-demand persona invocation for applying named perspectives to any task.
Personas are behavioral modifiers — they change the lens through which a task
is executed, not the tools available.

## Quick Start

```
/wicked-garden:persona:as engineering "review this auth flow"
/wicked-garden:persona:list
/wicked-garden:persona:define pragmatic-tech-lead --focus "delivery over perfection"
/wicked-garden:persona:submit pragmatic-tech-lead
```

## How It Works

1. **Registry** merges built-in specialists + custom personas + plugin cache
2. **persona:as** looks up a persona and dispatches to persona-agent
3. **persona-agent** executes the task under the persona's behavioral profile
4. **Behavior emerges** from personality, constraints, memories, and preferences

## Commands

| Command | Purpose |
|---------|---------|
| `persona:as <name> <task>` | Invoke a persona for any task |
| `persona:list [--role R]` | List all available personas |
| `persona:define <name> --focus "..." [--save]` | Create or update a custom persona |
| `persona:submit <name>` | PR a custom persona to the repo |

## Built-in Personas

Names come from `.claude-plugin/specialist.json`; their rich profiles live in
`scripts/persona/registry.py::_BUILTIN_RICH`. The built-ins are **illustrative
exemplars**, not the product. A blinded, independently-graded lift eval
(`tests/persona/EVAL_RESULTS.md`, run 2026-06-12) found the built-in personas
produce **lift=0** against a strong base model — it already flags the targeted
failure modes unprompted. So the curated surface was **reduced**: only the three
**methodology exemplars** keep rich profiles (they show the GOOD pattern); the
generic role personas were demoted to thin role records. For real leverage,
define your OWN house persona (see "Custom Personas") — that is the actual product.

### Methodology personas (carry a failure-mode defense — the GOOD pattern)

Their registry records encode `FAILURE MODE — …` constraints + a `not_focus`
scope guard the base model does not reliably self-apply. Kept as illustrative
exemplars of what a worth-keeping persona looks like.

| Name | Role | Defends against |
|------|------|-----------------|
| platform | devsecops | Silent secret exposure, irreversible deploy, privilege creep, unbounded blast radius |
| qe | quality-engineering | Self-graded "done", happy-path-only tests, untested recovery, coverage theater |
| agentic | agentic-architecture | Runaway loops, ungated irreversible actions, over-broad tool access, non-idempotent retries |

(`skeptic`, a fallback persona, is also methodology — it forces an edge case
before any approval.)

### Generic role names (thin lens — no curated profile)

These specialist names still resolve via `persona:as`, but carry **no curated
constraints** — the eval showed the base model already plays these roles, so a
rich profile added surface without lift. They apply the role as a plain lens.
Any role name not in this list (e.g. an ad-hoc one) falls back gracefully —
`persona:as` lists what's available rather than crashing. Want durable value
from one of these lenses? `persona:define` your house version with a failure-mode
constraint.

| Name | Role | Plain lens for |
|------|------|---------|
| engineering | engineering | Code quality, architecture, implementation |
| product | product | Requirements, UX, design review, business strategy |
| data | data-engineering | Pipeline design, ML guidance, analytics |
| jam | brainstorming | Ideation, exploration, multi-perspective analysis |

## Custom Personas

Create your own with `persona:define`. Stored in project-scoped DomainStore.

```
/wicked-garden:persona:define pragmatic-tech-lead \
  --focus "delivery over perfection — ship iteratively, measure, adjust" \
  --traits "direct,pragmatic,cost-aware" \
  --role engineering
```

Use `--save` to promote to plugin-level cache for cross-project reuse:
```
/wicked-garden:persona:define my-persona --focus "..." --save
```

## Persona Schema

Each persona has rich characteristics that create a genuine perspective:

```
name        — kebab-case identifier
description — one-line summary
focus       — the lens this persona applies
traits      — behavioral adjectives
role        — category for --role filtering
personality — style, temperament, humor
constraints — non-negotiable rules (MUST follow)
memories    — formative experiences that inform judgment
preferences — communication, code_style, review_focus, decision_making
```

## Cross-Domain Integration

Route any code review through a persona's lens:
```
/wicked-garden:engineering:review --persona platform
/wicked-garden:engineering:review --persona qe
```

Falls back to the built-in `architect` persona if the named persona is not found.

## Fallback Personas

If specialist.json is unavailable, three built-in personas are always available:
- **architect** — system design, trade-offs, structural decisions
- **skeptic** — challenges assumptions, finds edge cases
- **advocate** — champions end-user perspective and simplicity

## Source Priority

When names collide across sources, higher priority wins:
```
custom (DomainStore) > cache (~/.claude/plugins/...) > builtin > fallback
```

This lets you override a built-in persona with a project-specific version.
