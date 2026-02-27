---
name: ai-conversation
description: |
  Orchestrate multi-AI conversations with persistent context and audit trails.
  Use wicked-kanban as shared memory so Claude, Gemini, Codex, and OpenCode can collaborate.

  Use when:
  - Running multi-model analysis on architecture or design
  - Getting diverse AI perspectives on a decision
  - Need auditable AI-assisted decision making
  - Building consensus from multiple AI sources
---

# Multi-AI Conversation Orchestration

**Purpose**: Coordinate conversations across multiple AI models with shared context, persistent state, and audit trails.

## Why This Matters

Single-AI analysis has blind spots. Multi-model conversations:
- **Catch more issues**: Different models flag different concerns
- **Build confidence**: Consensus across models = higher confidence
- **Create audit trails**: Document which AI said what, when
- **Persist context**: Insights survive session restarts

Most users query one AI. This skill teaches systematic multi-model orchestration.

## Quick Usage

### Inline (Simple)

```markdown
**Task**: Review auth design

**Multi-model check**:
- Claude: [your analysis in this conversation]
- Gemini: `cat design.md | gemini "Review for security"`
- Codex: `cat design.md | codex exec "Review for architecture"`

**Consensus**: All flagged token expiry. High confidence issue.
```

### Structured (Complex)

For important decisions, use full orchestration:
1. Create kanban task for shared context
2. Gather perspectives systematically
3. Synthesize with documented rationale
4. Store decision in wicked-mem

## The Orchestration Process

### Step 1: Establish Shared Context

Create a single source of truth all AIs can reference.

```bash
/wicked-garden:kanban:new-task "Design review: Payment API" --priority P0
```

Add the context document to the task description.

→ See [refs/context.md](refs/context.md) for context management patterns.

### Step 2: Gather Perspectives

Query each AI with the same focused prompt for comparable results.

| AI | Command | Strength |
|----|---------|----------|
| Claude | (in conversation) | Nuanced reasoning |
| Gemini | `cat doc \| gemini "prompt"` | Long context |
| Codex | `cat doc \| codex exec "prompt"` | Code-focused |
| OpenCode | `opencode run "prompt" -f doc` | Multi-provider |

Add each response as a kanban comment with attribution.

→ See [refs/automation.md](refs/automation.md) for scripts.

### Step 3: Synthesize Results

Compare perspectives and identify:

| Signal | Meaning | Action |
|--------|---------|--------|
| **Consensus** (2+ agree) | High confidence issue | Address immediately |
| **Unique insight** | One AI caught something | Evaluate carefully |
| **Disagreement** | Genuine tradeoff | Human decides |
| **Silence** | No AI flagged it | Lower priority |

→ See [refs/examples.md](refs/examples.md) for synthesis templates.

### Step 4: Record and Persist

Store the decision with full attribution:

```bash
/wicked-garden:mem:store "Payment API: Use Stripe webhooks.
Consensus: Claude, Gemini, Codex (idempotency critical).
Unique: OpenCode flagged circuit breaker need.
Decision by: [Human] on [Date]" --type decision --tags payments
```

→ See [refs/auditability.md](refs/auditability.md) for audit patterns.

## Decision Principles

### When to Use Multi-Model

| Situation | Recommendation |
|-----------|----------------|
| Architecture decisions | Yes - high impact |
| Security review | Yes - catch blind spots |
| Quick bug fix | No - overhead not worth it |
| Important PRs | Yes - diverse review |
| Routine code | No - single AI sufficient |

### How to Weight Perspectives

1. **Consensus wins**: 2+ models agreeing = high confidence
2. **Expertise matters**: Codex for code, Gemini for long docs
3. **Unique insights valuable**: Don't dismiss outliers
4. **Human decides conflicts**: AI informs, human chooses

### When to Start Fresh vs. Continue

| Signal | Action |
|--------|--------|
| New topic | Fresh context |
| Building on prior | Continue session |
| Context polluted | Summarize and restart |
| Need unbiased view | Fresh, neutral handoff |

→ See [refs/context.md](refs/context.md) for session patterns.

## Output Format

For formal multi-model reviews:

```markdown
## Multi-Model Review: [Topic]

**Context**: [What was reviewed]
**Models**: Claude, Gemini, Codex, OpenCode

### Consensus (High Confidence)
- Issue 1: [flagged by Claude, Gemini, Codex]
- Issue 2: [flagged by all]

### Unique Insights
- **Gemini**: [insight others missed]
- **OpenCode**: [insight others missed]

### Disagreements
- [Topic]: Claude says X, Codex says Y

### Decision
[What was decided and why]

### Stored
- wicked-garden:mem [memory ID]
- wicked-garden:kanban [task ID]
```

## Quick Reference

| Need | Solution |
|------|----------|
| Shared context | wicked-kanban task |
| Persist decisions | wicked-mem |
| Automate gathering | refs/automation.md scripts |
| Audit trail | refs/auditability.md patterns |
| Session management | refs/context.md |
| Templates | refs/examples.md |

## References

**Process:**
- [Context Management](refs/context.md) - Session state, handoffs, context windows
- [Automation](refs/automation.md) - Scripts for gathering perspectives

**Quality:**
- [Auditability](refs/auditability.md) - Audit trails, compliance, decision tracking
- [Examples](refs/examples.md) - ADR templates, synthesis patterns
