# Auditability: Tracking AI Conversations

How to maintain audit trails for multi-AI conversations. Essential for compliance, team visibility, and learning from past decisions.

## Why Auditability Matters

1. **Compliance**: Some domains require documentation of AI-assisted decisions
2. **Team visibility**: Others can see what AI perspectives informed a decision
3. **Learning**: Review past AI conversations to improve prompts and workflows
4. **Accountability**: Know which AI said what, when

## The Audit Trail Stack

```
┌─────────────────────────────────────────┐
│  wicked-mem (long-term decisions)       │  ← Persist important decisions
├─────────────────────────────────────────┤
│  wicked-kanban (conversation tracking)  │  ← Track active discussions
├─────────────────────────────────────────┤
│  Local logs (session artifacts)         │  ← Raw AI outputs
└─────────────────────────────────────────┘
```

## Level 1: Local Logging

Capture raw AI outputs for immediate reference.

### Simple File Logging

```bash
# Log each AI response with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="./ai-logs/$(date +%Y-%m)"
mkdir -p "$LOG_DIR"

# Gemini
cat design.md | gemini "Review for security" | tee "$LOG_DIR/gemini_${TIMESTAMP}.md"

# Codex
cat design.md | codex exec "Review for architecture" | tee "$LOG_DIR/codex_${TIMESTAMP}.md"
```

### Structured Logging

```bash
#!/bin/bash
# log-ai-response.sh

MODEL=$1
PROMPT=$2
RESPONSE=$3
CONTEXT_FILE=$4

LOG_FILE="./ai-logs/$(date +%Y-%m-%d).jsonl"

jq -n \
  --arg ts "$(date -Iseconds)" \
  --arg model "$MODEL" \
  --arg prompt "$PROMPT" \
  --arg response "$RESPONSE" \
  --arg context "$CONTEXT_FILE" \
  '{timestamp: $ts, model: $model, prompt: $prompt, response: $response, context: $context}' \
  >> "$LOG_FILE"
```

## Level 2: Kanban Task Tracking

Use wicked-kanban for active conversations that need team visibility.

### Creating an Auditable Task

```bash
# Create task with audit metadata
/wicked-kanban:new-task "Design review: Payment API" \
  --priority P1 \
  --labels "ai-review,audit-required"
```

### Adding AI Perspectives as Comments

Each AI response becomes a comment with attribution:

```markdown
## Gemini Analysis (2026-01-25 14:32 UTC)

**Prompt**: Review for security vulnerabilities

**Response**:
[Gemini's full response here]

---
Model: gemini-2.0-flash | Context: docs/payment-api.md
```

### Comment Template

```bash
# Function to add attributed AI comment
add_ai_comment() {
  local TASK_ID=$1
  local MODEL=$2
  local PROMPT=$3
  local RESPONSE=$4

  COMMENT="## ${MODEL} Analysis ($(date -u +"%Y-%m-%d %H:%M UTC"))

**Prompt**: ${PROMPT}

**Response**:
${RESPONSE}

---
Model: ${MODEL} | Logged by: $(whoami)"

  # Add to kanban (adjust for your kanban CLI)
  echo "$COMMENT" | /wicked-kanban:comment "$TASK_ID"
}
```

## Level 3: Decision Persistence (wicked-mem)

For decisions that matter long-term, persist to wicked-mem.

### What to Store

| Type | Store When | Example |
|------|------------|---------|
| **Decision** | AI consensus led to architectural choice | "Use Stripe based on multi-model security review" |
| **Dissent** | One AI flagged something others missed | "Gemini flagged rate limiting gap" |
| **Pattern** | Discovered effective prompt pattern | "Security review prompt that catches edge cases" |
| **Lesson** | AI was wrong, corrected later | "Codex suggested X, but Y was correct because..." |

### Storage Patterns

```bash
# Store a decision with full attribution
/wicked-mem:store "Payment API: Use webhook-based async processing.
Consensus from Claude, Gemini, Codex (2026-01-25).
Key factors: idempotency, retry handling, audit trail.
Dissent: None.
Task: KANBAN-123" \
  --type decision \
  --tags payments,architecture,ai-consensus

# Store a dissent/unique insight
/wicked-mem:store "Auth review: Gemini uniquely flagged JWT refresh token rotation.
Other models missed this. Added to security checklist." \
  --type procedural \
  --tags security,auth,gemini-insight

# Store a lesson learned
/wicked-mem:store "AI code review limitation: All models missed SQL injection
in dynamic query builder. Add explicit SQL injection check to review prompts." \
  --type episodic \
  --tags lesson-learned,security,ai-limitation
```

## Audit Record Template

For formal audits, use this structure:

```markdown
# AI-Assisted Decision Record

## Metadata
- **Decision ID**: ADR-2026-001
- **Date**: 2026-01-25
- **Decision Maker**: [Human who approved]
- **AI Models Consulted**: Claude, Gemini, Codex

## Context
[What problem were we solving?]

## AI Consultation

### Claude (via Claude Code)
- **Timestamp**: 2026-01-25 14:00 UTC
- **Prompt**: [exact prompt used]
- **Key Points**: [summary of response]
- **Full Response**: [link or inline]

### Gemini (via gemini CLI)
- **Timestamp**: 2026-01-25 14:05 UTC
- **Prompt**: [exact prompt used]
- **Key Points**: [summary of response]
- **Full Response**: [link or inline]

### Codex (via codex CLI)
- **Timestamp**: 2026-01-25 14:10 UTC
- **Prompt**: [exact prompt used]
- **Key Points**: [summary of response]
- **Full Response**: [link or inline]

## Synthesis
[How human synthesized AI inputs]

## Decision
[Final decision made]

## Rationale
[Why this decision, including which AI inputs were influential]

## Dissenting Views
[Any AI perspectives that were noted but not followed, and why]
```

## Compliance Patterns

### Healthcare/HIPAA

```bash
# Never include PHI in AI prompts
# Log that AI was consulted without logging content
echo "$(date -Iseconds) | AI_CONSULT | gemini | code-review | NO_PHI" >> audit.log
```

### Financial/SOX

```bash
# Include decision chain
/wicked-mem:store "Trade algorithm change approved.
AI review: Claude, Gemini confirmed no regression risk.
Human approval: [Name] on [Date].
Change ticket: JIRA-456" \
  --type decision \
  --tags sox-audit,trading,ai-review
```

### General Best Practices

1. **Always log the prompt** - What you asked matters as much as the answer
2. **Attribute clearly** - Which model, which version, when
3. **Human in the loop** - Record who made the final decision
4. **Store dissent** - Minority AI opinions may be valuable later
5. **Link artifacts** - Connect logs to kanban tasks to mem entries

## Quick Reference

| Need | Solution |
|------|----------|
| Raw AI outputs | Local file logging |
| Team visibility | wicked-kanban comments |
| Long-term decisions | wicked-mem storage |
| Formal compliance | Audit record template |
| Cross-reference | Link task ID in all artifacts |
