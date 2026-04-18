# OpenCode CLI — Usage Patterns

OpenCode CLI for AI-assisted coding with multiple providers. Supports OpenAI, Anthropic,
Google, and more. Includes TUI mode, session continuity, and GitHub PR integration.

## Installation and Setup

```bash
# Check if installed
which opencode

# Install
brew install opencode  # or see https://github.com/sst/opencode

# Authentication (supports multiple providers)
opencode auth  # Interactive auth setup
```

## Core Usage Patterns

### Non-Interactive (run)

```bash
# Simple query
opencode run "Explain this error: ${error_message}"

# With file context
opencode run "Review this code for security issues" -f src/auth.py

# Multiple files
opencode run "How do these modules interact?" -f src/api.ts -f src/db.ts

# Specific model
opencode run -m anthropic/claude-3-5-sonnet "Analyze this design" -f design.md

# Continue previous session
opencode run -c "What about error handling?"

# Continue specific session by ID
opencode run -s SESSION_ID "Follow-up question"
```

### Interactive TUI Session

```bash
# Start in current directory
opencode

# Start in specific project
opencode /path/to/project

# Open web interface
opencode web
```

### GitHub Integration

```bash
# Fetch and review a PR
opencode pr 123

# Work with GitHub agent
opencode github
```

## Model Selection

OpenCode's key differentiator: switch providers without changing workflow.

```bash
# OpenAI models
opencode run -m openai/gpt-4o "Query"
opencode run -m openai/o1 --variant high "Complex analysis"

# Anthropic models
opencode run -m anthropic/claude-3-5-sonnet "Query"

# Google models
opencode run -m google/gemini-1.5-pro "Query"

# List available models
opencode models
opencode models openai
opencode models anthropic
```

## Multi-Provider Comparison

Use OpenCode to get the same query answered by multiple providers:

```bash
PROMPT="Review this auth design for security issues"
FILE="docs/auth-design.md"

# GPT-4o perspective
opencode run -m openai/gpt-4o "$PROMPT" -f "$FILE" > gpt4o_review.md

# Claude perspective (via OpenCode, not current session)
opencode run -m anthropic/claude-3-5-sonnet "$PROMPT" -f "$FILE" > claude_review.md

# Gemini perspective
opencode run -m google/gemini-1.5-pro "$PROMPT" -f "$FILE" > gemini_review.md
```

## Native Task Tracking

```
# Create review task
TaskCreate(
  subject="Multi-provider review: checkout flow",
  metadata={
    "event_type": "task",
    "chain_id": "checkout-review.root",
    "source_agent": "multi-model:opencode",
    "priority": "P1"
  }
)

# Capture GPT-4o perspective and append via TaskUpdate
# OPENCODE_REVIEW=$(opencode run -m openai/gpt-4o "Review" -f src/checkout.ts)
# TaskUpdate(taskId, description="{previous}\n\nopencode (gpt-4o): ${OPENCODE_REVIEW}")
```

## Command Reference

| Command | Description |
|---------|-------------|
| `opencode` | Interactive TUI session |
| `opencode run "message"` | Non-interactive one-shot |
| `opencode run -f file "query"` | Query with file context |
| `opencode run -c "follow up"` | Continue last session |
| `opencode pr 123` | Work on GitHub PR |
| `opencode models` | List available models |
| `opencode auth` | Configure provider authentication |
| `opencode web` | Open web interface |

## Options Reference

| Option | Description |
|--------|-------------|
| `-m provider/model` | Select model |
| `-f path` | Attach file(s) |
| `-c` | Continue last session |
| `-s SESSION_ID` | Continue specific session |
| `--variant high` | Reasoning effort variant |

## Strengths

| Area | Description |
|------|-------------|
| Multi-provider | One CLI, any provider — ideal for comparison |
| Session continuity | `-c` flag continues conversations naturally |
| GitHub integration | Native PR review and issue management |
| TUI mode | Full interactive coding sessions |

## Best Practices

1. **Use for multi-provider comparison** — OpenCode's main advantage is provider flexibility
2. **Session continuity** — Use `-c` for follow-up questions without losing context
3. **PR reviews** — `opencode pr 123` for native GitHub PR review
4. **File context** — Use `-f` to attach files cleanly (vs piping)

## Session Management

```bash
# Start a session
opencode run "Let's review the auth design" -f design.md

# Continue naturally
opencode run -c "What about the token refresh strategy?"
opencode run -c "How does this compare to session-based auth?"

# Or use specific session ID for parallel threads
SESSION_A=$(opencode run -m openai/gpt-4o "Review" -f design.md | grep "session:" | awk '{print $2}')
opencode run -s "$SESSION_A" -c "Deeper dive on security"
```

## Common Prompts

```bash
# Architecture review with GPT-4o
opencode run -m openai/gpt-4o "Architecture review: scalability, coupling, and missing abstractions" -f design.md

# PR review
opencode pr 123  # Interactive; or:
gh pr diff 123 | opencode run "Code review: flag issues and missing tests"

# Multi-provider comparison
for model in openai/gpt-4o anthropic/claude-3-5-sonnet google/gemini-1.5-pro; do
  echo "=== $model ===" && opencode run -m "$model" "Security review" -f src/auth.py
done
```
