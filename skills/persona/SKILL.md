---
name: persona
description: "Invoke named personas to apply specialist perspectives to any task. Supports built-in specialists (engineering, platform, product, qe, data, delivery, jam, agentic) and custom persona creation. Use when: invoking a persona, acting as a role, applying a perspective, defining or listing personas, reviewing code through a specific lens, or using the --persona flag on commands."
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

Loaded from `.claude-plugin/specialist.json` — 8 specialists available as personas:

| Name | Role | Best for |
|------|------|---------|
| engineering | engineering | Code quality, architecture, implementation |
| platform | devsecops | Security, CI/CD, infrastructure, compliance |
| product | product | Requirements, UX, design review, business strategy |
| qe | quality-engineering | Test strategy, acceptance criteria, quality gates |
| data | data-engineering | Pipeline design, ML guidance, analytics |
| delivery | project-management | Rollout, FinOps, milestone delivery |
| jam | brainstorming | Ideation, exploration, multi-perspective analysis |
| agentic | agentic-architecture | Agent safety, tool design, agentic patterns |

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

Falls back to default senior-engineer if persona not found.

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
