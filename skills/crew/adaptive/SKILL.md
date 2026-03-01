---
name: adaptive
description: |
  Adaptive engagement patterns for wicked-crew based on context, phase, and user preferences.
  Provides role inference, autonomy adaptation, and communication style adjustment.

  Use when the user mentions "autonomy", "just finish", "ask first", "adapt to my style",
  "preference profile", or when determining how to engage based on project context.
---

# Adaptive Engagement Skill

Adjust engagement based on context, preferences, and phase.

## Autonomy Levels

### ask-first

**Behavior**: Pause for approval at every decision point

**When to use**:
- Learning the workflow
- Critical projects
- When user wants full control

**Example**:
```
I've identified 3 potential approaches for authentication:
1. JWT with refresh tokens
2. Session-based with Redis
3. OAuth2 integration

Which would you like me to explore?
```

### balanced (default)

**Behavior**: Proceed on minor decisions, ask on major ones

**Minor (auto-proceed)**:
- File organization
- Variable naming
- Import ordering
- Documentation format

**Major (ask first)**:
- Architecture choices
- External dependencies
- API design
- Security approaches

### just-finish

**Behavior**: Maximum autonomy with safety guardrails

**Auto-proceed on**:
- All technical decisions
- Implementation details
- Refactoring choices
- Test structure

**Always pause (guardrails)**:
- Deployments
- Deletions
- Security changes
- External services

## Guardrails

These ALWAYS require explicit approval regardless of autonomy level:

| Category | Examples |
|----------|----------|
| Deployment | Push to production, staging deploys |
| Deletion | Remove files, drop tables, clear data |
| Security | Auth changes, secrets, permissions |
| External | API calls, third-party services |
| Irreversible | Anything that can't be undone |

## Phase-Based Adaptation

| Phase | Default Role | Engagement Style |
|-------|--------------|------------------|
| clarify | Facilitator | Ask questions, guide discovery |
| design | Collaborator | Propose options, discuss tradeoffs |
| qe | Specialist | Define strategy, identify edge cases |
| build | Executor | Implement according to plan |
| review | Reviewer | Assess objectively, recommend |

## Communication Styles

### verbose

- Detailed explanations
- Full context
- Step-by-step reasoning

### balanced

- Moderate detail
- Key decisions explained
- Summary with important points

### concise

- Brief updates
- Results-focused
- Minimal explanation

## Profile Configuration

Stored under the wicked-crew local storage domain as `preferences.yaml`:

```yaml
autonomy: balanced
communication_style: balanced
review_depth: standard
```

Configure via `/wicked-garden:crew:profile`.
