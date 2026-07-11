---
name: wicked-garden-persona
user-invocable: true
description: |
  On-demand persona invocation system for applying named perspectives to any task.
  Sub-actions: `as <name> <task>` (invoke a persona), `list [--role R]`
  (discover personas), `define <name> --focus "..." [--save]` (create or
  update a custom persona).
  Use when: invoking a named persona ("as platform, review this auth flow"),
  applying a specific perspective or role lens to a task, listing available
  personas, defining a house persona that encodes a failure-mode defense, or
  reviewing work through a specific role's perspective.
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# Persona System

On-demand persona invocation for applying named perspectives to any task.
Personas are behavioral modifiers — they change the lens through which a task
is executed, not the tools available.

## Sub-Action Routing

Route on the **first token** of the args, then read the matching ref for the
full flow:

| Sub-action | Args | Ref | Purpose |
|------------|------|-----|---------|
| `as` | `<persona-name> <task description>` | `refs/as.md` | Invoke a persona for any task — registry lookup, profile assembly, dispatch to the `wicked-garden-persona-agent` skill |
| `list` | `[--role <role>]` | `refs/list.md` | List all available personas, tiered Methodology vs Generic |
| `define` | `<name> --focus "..." [--traits "..."] [--constraints "FAILURE MODE — ..."] [--not-focus "..."] [--role <role>] [--save]` | `refs/define.md` | Create or update a custom persona — the enterprise house-persona injection mechanism; `--save` promotes to the plugin cache |

If the first token is none of these, treat the args as `as <args>` when they
start with a known persona name followed by a task; otherwise show the routing
table above and STOP.

## Quick Start

```
/wicked-garden-persona as engineering "review this auth flow"
/wicked-garden-persona list
/wicked-garden-persona define pragmatic-tech-lead --focus "delivery over perfection"
```

## How It Works

1. **Registry** merges built-in specialists + custom personas + plugin cache
2. **The `as` action** looks up a persona and dispatches to the
   `wicked-garden-persona-agent` skill (forked context)
3. **persona-agent** executes the task under the persona's behavioral profile
4. **Behavior emerges** from personality, constraints, memories, and preferences

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

These specialist names still resolve via the `as` action, but carry **no curated
constraints** — the eval showed the base model already plays these roles, so a
rich profile added surface without lift. They apply the role as a plain lens.
Any role name not in this list (e.g. an ad-hoc one) falls back gracefully —
the `as` action lists what's available rather than crashing. Want durable value
from one of these lenses? Use the `define` action to create your house version
with a failure-mode constraint.

| Name | Role | Plain lens for |
|------|------|---------|
| engineering | engineering | Code quality, architecture, implementation |
| product | product | Requirements, UX, design review, business strategy |
| data | data-engineering | Pipeline design, ML guidance, analytics |
| jam | brainstorming | Ideation, exploration, multi-perspective analysis |

## Custom Personas

Create your own with the `define` action — the mechanism that lets an
enterprise inject ITS house personas. Stored in project-scoped DomainStore.

```
/wicked-garden-persona define pragmatic-tech-lead \
  --focus "delivery over perfection — ship iteratively, measure, adjust" \
  --traits "direct,pragmatic,cost-aware" \
  --role engineering
```

Use `--save` to promote to plugin-level cache for cross-project reuse:
```
/wicked-garden-persona define my-persona --focus "..." --save
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

Route any code review through a persona's lens via the engineering domain's
review action with `--persona`:
```
engineering review --persona platform
engineering review --persona qe
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
