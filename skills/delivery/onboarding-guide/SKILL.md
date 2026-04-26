---
name: onboarding-guide
description: |
  Guide new developers through team onboarding. Analyzes project health,
  team patterns, delivery metrics, and codebase structure to produce a
  personalized onboarding plan with specific first tasks, graduated
  complexity, and human connections. A guided walkthrough, not an agent
  identity.

  Use when: "onboard a new developer", "getting-started guide", "team
  orientation for new hire", "first week plan", "day-one productivity".
---

# Onboarding Guide

Produces a personalized onboarding path for a new developer by combining team
health signals, codebase structure, and sprint state into a structured
week-by-week plan with concrete first tasks.

## Quick Start

Invoke this skill when someone new is joining the team. Typical outputs:

- Team health snapshot (sprint state, velocity, blockers)
- Recommended first tasks (ranked by learning value + risk + impact)
- Key systems overview (what to learn in what order)
- Team patterns (branching, review, testing, communication)
- Structured weekly plan (orientation → first contribution → independence)
- People to connect with (who owns what)

## First Strategy: Use wicked-* Ecosystem

- **Delivery reports**: `/wicked-garden:delivery:report` for team health overview
- **Memory**: `wicked-brain:memory` (recall mode) for team conventions and past decisions
- **Search**: `wicked-garden:search` for codebase navigation (backed by the
  **codebase-narrator** skill for architectural overview)
- **Tasks**: Inspect native tasks via TaskCreate/TaskUpdate with
  `metadata={event_type, chain_id, source_agent, phase}`

## Process

### 1. Gather Team Context

**From delivery reports** (if CSV/export available):
```
/wicked-garden:delivery:report {data_file}
```

**From native tasks**:
Read session tasks under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/` — filter
by `metadata.event_type=="task"` for human-visible items.

**From memory**:
```
Skill(skill="wicked-brain:memory", args="recall \"team conventions\"")
Skill(skill="wicked-brain:memory", args="recall \"architecture decisions\"")
Skill(skill="wicked-brain:memory", args="recall \"onboarding\"")
```

**From codebase**:
```
/wicked-garden:search:docs README
/wicked-garden:search:code "TODO|FIXME|HACK"
```

### 2. Assess Team Health

- **Sprint status**: in flight, blocked, done
- **Velocity**: tasks/week, points/sprint
- **Blockers**: what's stuck and why
- **Team capacity**: who's working on what

Present as a concise snapshot, not a data dump.

### 3. Identify Good First Tasks

Rank candidates by:
1. **Learning value** — introduces key systems
2. **Risk** — low-risk preferred (isolated blast radius)
3. **Team impact** — helpful contributions preferred
4. **Independence** — minimal coordination needed

Sources: unassigned low-priority items, documentation gaps, small bugs, test
coverage gaps.

### 4. Map Key Systems

Create a systems overview:
- Core services — what the project does
- Architecture — high-level component map
- Data flow — how data moves through the system
- Deployment — how code ships to production
- Dependencies — external services and integrations

Hand off to the **codebase-narrator** skill for the full architectural walk.

### 5. Explain Team Patterns

Document:
- **Branching strategy** (trunk-based, git-flow, etc.)
- **Review process** (PR template, required reviewers, merge criteria)
- **Testing approach** (what tests are expected per change)
- **Communication** (where decisions happen — Slack, meetings, docs)
- **On-call / support** (how incidents are handled)

### 6. Build the Week-by-Week Plan

See [refs/plan-template.md](refs/plan-template.md) for the full structure.

Shape:
- **Week 1 — Orientation**: read docs, set up env, meet people, pick first task
- **Week 2 — First Contribution**: complete first task with pair programming,
  submit first PR, attend sprint ceremonies
- **Week 3 — Independence**: take a medium-complexity task, review someone
  else's PR, identify an improvement, share feedback

## Quality Standards

Good onboarding plans have:
- **Concrete first tasks** — not "explore the codebase" but specific tickets
- **Context before code** — team health and patterns before diving in
- **Graduated complexity** — easy → medium → harder
- **Human connections** — who to talk to about what
- **Feedback loop** — check-in points to adjust the plan

## Common Pitfalls

- Information overload on day one
- Assuming knowledge of team-specific tools
- Skipping team culture and patterns
- Starting with the hardest problem
- No check-in points to course-correct

## See Also

- [refs/plan-template.md](refs/plan-template.md) — full output template
- `skills/search/codebase-narrator` — architectural walk-through
- `/wicked-garden:delivery:report` — team health input
