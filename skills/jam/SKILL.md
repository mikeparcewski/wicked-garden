---
name: brainstorming
description: |
  Orchestrates AI-powered brainstorming sessions with dynamic focus groups.
  This skill should be used when the user wants to brainstorm, explore ideas,
  get feedback on concepts, or run a focus group discussion.
  Sessions are tracked in kanban (process) and stored in wicked-mem (outcome).

  Use when: "brainstorm this", "explore ideas", "get different perspectives",
  "focus group", "what do you think about", "pros and cons"
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
- 1 round
- Brief synthesis
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

## Discussion Dynamics

### Round 1: Initial Perspectives

Each persona shares their view:
- Position on the topic
- Key concern
- Suggestion or consideration

### Round 2: Building

Personas respond to each other:
- Build on good ideas
- Challenge assumptions
- Find connections

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

### With wicked-mem

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

### With wicked-kanban

Sessions are tracked in kanban for process visibility:

```
# On session start
/wicked-garden:kanban:new-task "Jam: {topic}" --metadata '{"type":"jam-session","personas":[...],"status":"brainstorming"}'

# After each persona round
/wicked-garden:kanban:comment {task_id} "{persona_name}: {key_insight}"

# After synthesis
/wicked-garden:kanban:comment {task_id} "Synthesis: {summary}"

# On decision
/wicked-garden:kanban:comment {task_id} "Decision: {decision_record}"
```

Wrap all kanban calls in graceful degradation — if kanban unavailable, skip silently.
Kanban tracks process; wicked-mem stores outcomes. Both can coexist.

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

Put synthesis first (context efficiency):

```markdown
## Brainstorm: {Topic}

### Key Insights
{Most important - read this first}

### Action Items
{What to do next}

### Open Questions
{What's unresolved}

---

### Session Details
{Personas, rounds, discussion summary}
```
