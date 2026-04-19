---
name: jam
description: |
  Orchestrates AI-powered brainstorming sessions with dynamic focus groups.
  This skill should be used when the user wants to brainstorm, explore ideas,
  get feedback on concepts, or run a focus group discussion.
  Sessions are tracked as native tasks (process) and stored in wicked-garden:mem (outcome).

  Use when: "brainstorm this", "explore ideas", "get different perspectives",
  "focus group", "what do you think about", "pros and cons"
context: fork
---

# Brainstorming Skill

Generate diverse perspectives through structured focus group sessions.

## When to Use

- User wants to explore an idea
- Decision needs multiple viewpoints
- Problem needs creative approaches
- User says "brainstorm", "perspectives", "focus group", "what do you think about"

## Session Types

### Full Brainstorm (`/brainstorm`)

- 4-6 personas
- 2-3 discussion rounds
- Full synthesis with insights
- Storage offered

Best for: Important decisions, complex problems, strategic thinking

### Quick Jam (`/jam`)

- 4 personas
- 1 round (forced — never extends)
- Brief synthesis (2-3 insights max)
- No storage prompt

Best for: Quick decisions, gut checks, rapid exploration

### Perspectives Only (`/perspectives`)

- 4-6 personas
- 1 round
- No synthesis (user decides)
- Raw viewpoints

Best for: Gathering input, self-directed thinking, discussion prep

## Persona Design

### Archetypes

| Type | Focus | Examples |
|------|-------|----------|
| Technical | How it works | Architect, Debugger, Security |
| User | Who uses it | Power User, Newcomer, Support |
| Business | Why it matters | PM, Skeptic, Evangelist |
| Process | How it ships | Maintainer, Tester, Ops |

### Selection Principles

1. **Relevance**: Choose personas that care about the topic
2. **Diversity**: Cover multiple angles
3. **Genuine**: Each has legitimate concerns (no strawmen)
4. **Buildable**: Personas can respond to each other

## Convergence Modes

| Mode | Flag | Behavior |
|------|------|----------|
| Normal | (default) | Run all planned rounds, then synthesize |
| Fast | `--converge fast` | After each round, check if signal is sufficient; skip remaining rounds if yes |

Fast convergence checks three criteria after each round: (1) at least 2 actionable insights, (2) directional agreement, (3) tensions are well-characterized. If all pass, synthesis begins immediately.

Quick jam (`/jam`) always uses forced fast convergence (1 round, then synthesize).

## Discussion Dynamics

### Round 1: Initial Perspectives

Each persona shares their view:
- Position on the topic
- Key concern
- Suggestion or consideration

*Convergence check (fast mode: synthesize if criteria met)*

### Round 2: Building

Personas respond to each other:
- Build on good ideas
- Challenge assumptions
- Find connections

*Convergence check (fast mode: synthesize if criteria met)*

### Round 3: Convergence (optional)

Find common ground:
- Agreements
- Remaining tensions
- Key tradeoffs

## Synthesis Quality

Good synthesis:
- **3-5 insights** (not 10)
- **Confidence levels** (HIGH/MEDIUM/LOW)
- **Action items** (prioritized)
- **Open questions** (honest about unknowns)

Bad synthesis:
- Just summarizing what personas said
- Too many insights (information overload)
- No confidence assessment
- No actionable next steps

## Integration

### With wicked-garden:mem

At session start:
```python
prior = mem_recall(topic)  # via /wicked-garden:mem:recall
inject_context(prior)
```

At session end:
```python
if user_approves:
    mem_store(insights, type="decision", tags=[topic])  # via /wicked-garden:mem:store
```

### With native tasks

Sessions are tracked as native tasks for process visibility:

```
# On session start
TaskCreate(
  subject="Jam: {topic}",
  metadata={
    "event_type": "task",
    "chain_id": "jam-{topic-slug}.root",
    "source_agent": "jam-facilitator",
    "initiative": "{topic-slug}"
  }
)

# After each persona round — append to description
TaskUpdate(taskId, description="{previous}\n\n{persona_name}: {key_insight}")

# After synthesis
TaskUpdate(taskId, description="{previous}\n\nSynthesis: {summary}")

# On decision
TaskUpdate(taskId, description="{previous}\n\nDecision: {decision_record}")
```

Wrap all task calls in graceful degradation — if TaskCreate/TaskUpdate fail, skip silently.
Native tasks track process; wicked-garden:mem stores outcomes. Both can coexist.

### With wicked-crew

Called during clarify, design, and build phases. See "Crew Engagement" section below.

## Crew Engagement

| Phase | Mode | When |
|-------|------|------|
| Clarify | Quick jam (4 personas, 1 round) | Approach options, framing decisions |
| Design | Full brainstorm (4-6 personas, 2-3 rounds) | Architecture decisions, complex tradeoffs |
| Build checkpoint | Quick jam | Course corrections when unexpected complexity arises |

Jam auto-engages when: ambiguity detected, complexity >= 4, architecture signals present,
or content/documentation-heavy scope.

## References

- `refs/facilitation-patterns.md` — Match persona archetypes to problem types; session length guidance; anti-patterns to avoid
- `refs/synthesis-patterns.md` — Synthesis structure, quality checklist, techniques (non-obvious connections, surprising agreements, productive tensions), decision record format, examples

## Output Structure

Synthesis-first: `## Brainstorm: {Topic}` → `### Key Insights` (read first) → `### Action Items` → `### Open Questions` → `### Session Details` (personas, rounds, summary).
