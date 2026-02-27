---
name: brainstorming
description: |
  Orchestrates AI-powered brainstorming sessions with dynamic focus groups.
  Use when user wants to brainstorm, explore ideas, get feedback on concepts,
  or run a focus group discussion. Handles idea capture, context gathering,
  persona generation, round execution, and synthesis.
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
if has_plugin("wicked-mem"):
    prior = recall(topic)
    inject_context(prior)
```

At session end:
```python
if has_plugin("wicked-mem") and user_approves:
    store(insights, type="decision", tags=[topic])
```

### With wicked-crew

Called during clarify phase to explore project approaches.

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
