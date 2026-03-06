---
name: ai-collaboration
description: |
  Multi-AI CLI collaboration: discover and orchestrate codex, gemini, opencode, pi, and claude
  CLIs for multi-model analysis, council sessions, and cross-AI review workflows.
  Preferences stored in wicked-mem. Conversations tracked in wicked-kanban.

  Use when:
  - "codex", "gemini", "opencode", "pi cli", "claude cli"
  - Running multi-model analysis or design review
  - Getting diverse AI perspectives on a decision
  - Council sessions with multiple AI models
  - Second opinion from a different AI
  - Multi-model code review or architecture critique
  - "ai collaboration", "multi-model", "cross-ai"
---

# AI Collaboration Skill

Discover and orchestrate AI CLIs for multi-model collaboration. Get diverse perspectives,
run council sessions, and persist decisions with full attribution.

## Quick Start

```bash
# Discover installed AI CLIs
/wicked-garden:ai-collaboration:collaborate --discover

# Multi-model review of a file
/wicked-garden:ai-collaboration:collaborate --review design.md

# Council session on a decision
/wicked-garden:ai-collaboration:collaborate --council "Should we use JWT or sessions?"
```

## CLI Discovery

Use `command -v` to detect installed AI CLIs — no external dependencies:

```bash
# Detect all AI CLIs
command -v codex    &>/dev/null && echo "codex: $(command -v codex)"
command -v gemini   &>/dev/null && echo "gemini: $(command -v gemini)"
command -v opencode &>/dev/null && echo "opencode: $(command -v opencode)"
command -v pi       &>/dev/null && echo "pi: $(command -v pi)"
command -v claude   &>/dev/null && echo "claude: $(command -v claude)"
```

## CLI Reference

| CLI | Install | Strength | Key Command |
|-----|---------|----------|-------------|
| `codex` | `brew install codex` | Code generation, refactoring | `codex exec "..."` |
| `gemini` | `npm i -g @google/gemini-cli` | Long context, broad analysis | `cat file \| gemini "..."` |
| `opencode` | `brew install opencode` | Multi-provider, TUI, GitHub PRs | `opencode run "..." -f file` |
| `pi` | `brew install pi-mono` | Empathetic reasoning, UX tone | `pi exec "..."` |
| `claude` | `npm i -g @anthropic/claude-cli` | In-conversation (current session) | (inline) |

→ See [refs/codex.md](refs/codex.md) — Codex CLI patterns
→ See [refs/gemini.md](refs/gemini.md) — Gemini CLI patterns
→ See [refs/opencode.md](refs/opencode.md) — OpenCode CLI patterns
→ See [refs/pi.md](refs/pi.md) — Pi CLI patterns
→ See [refs/orchestration.md](refs/orchestration.md) — Multi-model orchestration

## Multi-Model Workflow

### 1. Gather Perspectives

Run the same focused prompt across detected CLIs:

```bash
PROMPT="Review this auth design for security and scalability"
CONTEXT_FILE="docs/auth-design.md"

cat "$CONTEXT_FILE" | gemini "$PROMPT"
cat "$CONTEXT_FILE" | codex exec "$PROMPT"
opencode run "$PROMPT" -f "$CONTEXT_FILE" -m openai/gpt-4o
cat "$CONTEXT_FILE" | pi exec "$PROMPT"
```

### 2. Track in Kanban

Create a task so all AI perspectives are visible to the team:

```bash
/wicked-garden:kanban:new-task "Multi-model review: Auth design" --priority P1
# Add each response as a comment with attribution
```

### 3. Synthesize

| Signal | Meaning | Action |
|--------|---------|--------|
| Consensus (2+ agree) | High confidence | Address immediately |
| Unique insight | One AI caught it | Evaluate carefully |
| Disagreement | Genuine tradeoff | Human decides |

### 4. Persist Decision

```bash
/wicked-garden:mem:store "Auth: JWT with 15min/7day expiry.
Consensus: Claude, Gemini, Codex (idempotency critical).
Unique: Pi flagged UX confusion on session expiry messaging." \
  --type decision --tags auth,multi-model-review
```

## When to Use Multi-Model

| Situation | Recommendation |
|-----------|----------------|
| Architecture decisions | Yes — high impact, catch blind spots |
| Security review | Yes — different models flag different risks |
| Important PRs | Yes — diverse review perspectives |
| Quick bug fix | No — overhead not worth it |
| Routine code | No — single AI sufficient |

## Preference Storage

Store preferred CLI configuration in wicked-mem for reuse:

```bash
/wicked-garden:mem:store "AI CLI preferences: gemini for long docs, codex for code review,
pi for UX/tone evaluation, opencode for multi-provider comparison." \
  --type procedural --tags ai-collaboration,preferences
```

Recall preferences:

```bash
/wicked-garden:mem:recall "ai cli preferences"
```

## Output Format

```markdown
## Multi-Model Review: [Topic]
Models: Claude (inline), Gemini, Codex, OpenCode, Pi

### Consensus (flagged by 2+)
- Issue 1
- Issue 2

### Unique Insights
- **Gemini**: [long-context catch]
- **Pi**: [UX/human factor]
- **Codex**: [architectural note]

### Decision
[What was decided and why]

### Stored
- wicked-mem [memory ID]
- wicked-kanban [task ID]
```
