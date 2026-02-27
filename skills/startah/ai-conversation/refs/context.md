# Context: Maintaining AI Conversation State

How to maintain context across AI sessions, manage context windows, and decide when to continue vs. start fresh.

## The Context Challenge

Each AI CLI has its own session management:
- **Claude Code**: Persistent within session, summarizes on overflow
- **Gemini**: Can resume sessions with `-r`
- **Codex**: Has `resume` and `fork` commands
- **OpenCode**: Session IDs with `-c` and `-s`

Cross-AI context requires external coordination.

## Context Layers

```
┌─────────────────────────────────────────┐
│  Shared Context (wicked-kanban)         │  ← All AIs can reference
├─────────────────────────────────────────┤
│  Per-AI Session State                   │  ← CLI-specific memory
├─────────────────────────────────────────┤
│  Prompt Context (files, snippets)       │  ← What you send each time
└─────────────────────────────────────────┘
```

## Strategy 1: Kanban as Shared Memory

Use a wicked-kanban task as the source of truth all AIs reference.

### Setup

```bash
# Create the shared context task
/wicked-garden:kanban:new-task "Design discussion: Auth system" --priority P1

# Add the context document
# (paste or link the design doc in the task description)
```

### Cross-AI Workflow

```bash
# When querying any AI, reference the kanban task
CONTEXT=$(cat docs/auth-design.md)
PRIOR_COMMENTS=$(# fetch prior AI comments from kanban)

# Gemini with full context
echo "$CONTEXT

Prior AI feedback:
$PRIOR_COMMENTS

Your task: Build on the prior feedback. What's missing?" | gemini

# Same pattern for Codex, OpenCode
```

### Why This Works

- Single source of truth
- All perspectives visible in one place
- Humans can inject corrections
- Natural audit trail

## Strategy 2: Context Documents

For longer discussions, maintain a context document.

### Structure

```markdown
# Context: Auth System Design

## Current State
[Latest version of design]

## Constraints
- Must support SSO
- Max 100ms auth latency
- HIPAA compliant

## AI Feedback Summary

### Round 1 (2026-01-25)
- **Claude**: Flagged token expiry concerns
- **Gemini**: Suggested rate limiting
- **Codex**: Recommended repository pattern

### Open Questions
1. Token refresh strategy?
2. Session invalidation approach?

## Decisions Made
- Use JWT with 15min/7day expiry (per Claude's recommendation)
```

### Usage

```bash
# Each AI gets the context doc
cat context-auth.md | gemini "Address the open questions"

# Update context doc with responses
# Repeat with next AI
```

## Strategy 3: Session Continuity

Use each CLI's native session management for deep dives.

### Gemini

```bash
# Start a session
gemini -i "Let's review the auth design"

# ... interactive discussion ...

# Later, resume
gemini -r  # Resumes last session
```

### Codex

```bash
# Interactive session
codex "Review the payment flow"

# ... discussion ...

# Resume later
codex resume --last

# Or fork to explore alternatives
codex fork --last "What if we used event sourcing instead?"
```

### OpenCode

```bash
# Non-interactive with continuation
opencode run "Review auth design" -f design.md

# Continue the conversation
opencode run -c "What about the token refresh?"

# Or specify session ID
opencode run -s abc123 "Follow up question"
```

## When to Start Fresh vs. Continue

### Start Fresh When

- Switching topics entirely
- Previous context is misleading
- Context window is polluted with irrelevant discussion
- You want an unbiased perspective

### Continue When

- Building on prior analysis
- Multi-step reasoning needed
- AI needs to remember constraints discussed earlier
- Iterating on a design

### Reset Signals

Watch for these signs that you should start fresh:
- AI references things you didn't discuss
- Responses become repetitive or circular
- AI seems confused about the current state
- You've pivoted significantly from original topic

## Context Window Management

### The Problem

Each AI has limited context. Too much history = lost important details.

### Solutions

**Summarize periodically:**
```bash
# Ask the AI to summarize before context overflow
echo "Summarize our discussion so far in 5 bullet points" | gemini

# Save summary, start new session with summary as context
```

**Prioritize recent + key decisions:**
```markdown
# Context for new session

## Key Decisions (from prior sessions)
1. Using JWT with 15min expiry
2. Rate limiting at API gateway
3. Repository pattern for auth

## Current Focus
[Only the relevant recent context]
```

**Use refs for stable context:**
```bash
# Don't repeat stable context every time
# Reference a file that all AIs can read
cat refs/architecture-decisions.md docs/current-design.md | gemini "Given these constraints, review X"
```

## Cross-AI Context Handoff

When handing context from one AI to another:

### Pattern: Explicit Handoff

```bash
# Get Claude's analysis
CLAUDE_ANALYSIS="[Claude's response from the conversation]"

# Hand off to Gemini with context
echo "Prior analysis from Claude:
$CLAUDE_ANALYSIS

Build on this analysis. What did Claude miss? What would you add?" | gemini
```

### Pattern: Neutral Handoff

```bash
# Don't bias the second AI
echo "Review this design for security concerns.

Note: Another AI has already reviewed this. After your independent review,
I'll share their feedback for comparison." | codex exec

# Then compare independently-generated perspectives
```

### Pattern: Adversarial Handoff

```bash
# Explicitly ask for critique
echo "Another AI recommended using JWT with 15min expiry.
Argue against this recommendation. What are the downsides?" | gemini
```

## Quick Reference

| Situation | Approach |
|-----------|----------|
| Multi-AI on same topic | Kanban task as shared context |
| Deep dive with one AI | Use native session management |
| Long-running discussion | Context document with summaries |
| Unbiased second opinion | Start fresh, neutral handoff |
| Building on prior work | Continue session or explicit handoff |
| Context getting stale | Summarize, start fresh with summary |

## Anti-Patterns

### Context Pollution

```bash
# BAD: Accumulating irrelevant context
echo "$ENTIRE_CODEBASE
$ALL_PRIOR_DISCUSSIONS
$UNRELATED_DOCS
Review the login function" | gemini

# GOOD: Focused context
echo "$LOGIN_FUNCTION
$AUTH_REQUIREMENTS
Review for security issues" | gemini
```

### Assumption Leakage

```bash
# BAD: AI assumes context it doesn't have
# "As we discussed..." (but you didn't discuss it)

# GOOD: Always provide explicit context
# Don't assume AI remembers prior sessions
```

### Echo Chamber

```bash
# BAD: Telling AI what other AIs said before independent review
echo "Claude said X, Gemini said Y. What do you think?" | codex

# GOOD: Get independent opinion first
echo "Review this design" | codex
# THEN share and compare perspectives
```
