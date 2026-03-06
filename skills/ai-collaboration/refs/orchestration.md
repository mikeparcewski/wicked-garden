# Multi-Model Orchestration Patterns

Patterns for coordinating multiple AI CLIs: gathering perspectives, managing context,
synthesizing results, and building audit trails.

## The Orchestration Loop

```
1. Establish context (kanban task as shared memory)
2. Gather perspectives (same prompt, multiple CLIs)
3. Synthesize (consensus → unique → disagreements)
4. Persist decision (wicked-mem + kanban attribution)
```

## Context Management

### Kanban as Shared Memory

Use a wicked-kanban task so all AI perspectives are visible to the team:

```bash
# Create the shared context task
/wicked-garden:kanban:new-task "Design review: Auth system" --priority P1

# Build context document all AIs reference
CONTEXT=$(cat docs/auth-design.md)

# Each AI query includes prior feedback
PRIOR=$(# fetch prior AI comments from kanban)
echo "${CONTEXT}

Prior AI feedback:
${PRIOR}

Your task: Build on the prior feedback. What's missing?" | gemini
```

### Context Layers

```
┌────────────────────────────────────────┐
│  Shared Context (wicked-kanban)        │  ← All AIs reference
├────────────────────────────────────────┤
│  Per-AI Session State                  │  ← CLI-specific memory
├────────────────────────────────────────┤
│  Prompt Context (files, snippets)      │  ← What you send each time
└────────────────────────────────────────┘
```

## Gathering Perspectives

### Parallel Collection Script

```bash
#!/bin/bash
# multi-review.sh - Gather perspectives from multiple AI CLIs
CONTEXT_FILE=$1
PROMPT=$2

echo "=== Claude's Perspective ==="
echo "(Inline in current conversation)"
echo

echo "=== Gemini's Perspective ==="
cat "$CONTEXT_FILE" | gemini "$PROMPT" 2>/dev/null || echo "gemini not available"
echo

echo "=== Codex's Perspective ==="
cat "$CONTEXT_FILE" | codex exec "$PROMPT" 2>/dev/null || echo "codex not available"
echo

echo "=== OpenCode (GPT-4o) Perspective ==="
opencode run "$PROMPT" -f "$CONTEXT_FILE" -m openai/gpt-4o 2>/dev/null || echo "opencode not available"
echo

echo "=== Pi's Perspective (human factors) ==="
cat "$CONTEXT_FILE" | pi exec "$PROMPT" 2>/dev/null || echo "pi not available"
```

```bash
chmod +x multi-review.sh
./multi-review.sh docs/design.md "Review for security, scalability, and user impact"
```

### Python Orchestrator

```python
#!/usr/bin/env python3
"""Orchestrate multi-model reviews."""

import subprocess
import sys
from pathlib import Path

def query_model(name: str, cmd: list[str], stdin: str | None = None) -> str | None:
    try:
        proc = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True, timeout=120
        )
        return proc.stdout.strip() if proc.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

def main(context_file: str, prompt: str):
    context = Path(context_file).read_text()

    models = {
        "Gemini": (["gemini", prompt], context),
        "Codex":  (["codex", "exec", prompt], context),
        "OpenCode": (["opencode", "run", prompt, "-f", context_file, "-m", "openai/gpt-4o"], None),
        "Pi": (["pi", "exec", prompt], context),
    }

    for name, (cmd, stdin) in models.items():
        print(f"\n## {name}\n")
        result = query_model(name, cmd, stdin)
        print(result if result else f"({name} not available)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python orchestrate.py <context-file> <prompt>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
```

## Handoff Patterns

### Independent Review (Best Practice)

Get unbiased opinions before sharing other perspectives:

```bash
# Get independent reviews
cat design.md | codex exec "Review for security issues" > codex_review.md
cat design.md | gemini "Review for security issues" > gemini_review.md

# Then share for comparison
echo "Codex found: $(cat codex_review.md)

Given this, what did Codex miss or get wrong?" | gemini
```

### Adversarial Handoff

Explicitly ask for critique of another model's recommendation:

```bash
echo "Codex recommended using JWT with 15min expiry.
Argue against this. What are the downsides?" | gemini
```

### Neutral Handoff

Avoid anchoring bias when you want a fresh perspective:

```bash
echo "Review this design for security concerns.

Note: Another AI has already reviewed this. After your independent review,
I'll share their feedback for comparison." | codex exec
```

## Synthesis Framework

After gathering perspectives, synthesize using this framework:

| Signal | Meaning | Action |
|--------|---------|--------|
| **Consensus** (2+ agree) | High confidence issue | Address immediately |
| **Unique insight** | One AI caught it | Evaluate carefully |
| **Disagreement** | Genuine tradeoff | Human decides |
| **Silence** | No AI flagged it | Lower priority |

### Output Template

```markdown
## Multi-Model Review: [Topic]

**Models**: Claude (inline), Gemini, Codex, OpenCode, Pi
**Context**: [What was reviewed]

### Consensus (High Confidence)
- Issue 1: flagged by Claude, Gemini, Codex
- Issue 2: flagged by all

### Unique Insights
- **Gemini**: [long-context catch others missed]
- **Pi**: [user experience concern]
- **Codex**: [architectural note]

### Disagreements
- [Topic]: Gemini says X, Codex says Y → human decides

### Decision
[What was decided and why]
```

## Session Management

### When to Start Fresh vs. Continue

| Signal | Action |
|--------|--------|
| New topic | Fresh context |
| Building on prior | Continue session |
| Context polluted | Summarize and restart |
| Unbiased view needed | Fresh, neutral handoff |

### Per-CLI Session Commands

```bash
# Gemini
gemini -r                           # Resume last session
gemini -i "Starting fresh on X"     # New with initial prompt

# Codex
codex resume --last                 # Resume
codex fork --last "Alternative: ..." # Fork to explore variant

# OpenCode
opencode run -c "Follow-up..."      # Continue last session
opencode run -s SESSION_ID "..."    # Continue specific session
```

## Persistence

### Store Decisions with Full Attribution

```bash
/wicked-garden:mem:store "Payment API: Use Stripe with async webhooks.
Consensus: Claude, Gemini, Codex (idempotency critical).
Unique: Pi flagged UX confusion on webhook delay messaging.
Dissent: none.
Kanban: TASK-123" \
  --type decision \
  --tags payments,architecture,multi-model-review

# Store unique insights separately
/wicked-garden:mem:store "Insight: Pi caught that our webhook delay message
caused user anxiety (retried purchases). Added 'processing' state indicator." \
  --type episodic \
  --tags ux,pi-insight,payments
```

## Anti-Patterns to Avoid

```bash
# BAD: Too much context
echo "$ENTIRE_CODEBASE $ALL_PRIOR_DISCUSSIONS" | gemini "Review login"

# GOOD: Focused context
echo "$LOGIN_FUNCTION $AUTH_REQUIREMENTS" | gemini "Review login for security"

# BAD: Anchoring second AI before independent review
echo "Claude said X. What do you think?" | codex

# GOOD: Independent first, compare after
cat design.md | codex exec "Review" > codex.md
# Then: "Codex found: $(cat codex.md). What did Codex miss?" | gemini
```
