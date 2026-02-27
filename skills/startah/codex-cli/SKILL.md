---
name: codex-cli
description: |
  Use the OpenAI Codex CLI for AI-assisted coding, code review, and multi-model collaboration.
  Codex excels at code generation, refactoring, and technical analysis.

  Use when:
  - Getting a second opinion on code or architecture
  - Code review from a different AI perspective
  - Complex refactoring analysis
  - Running parallel analysis with multiple AI models
---

# Codex CLI

Use the `codex` CLI for AI-assisted coding and multi-model collaboration.

## Prerequisites

```bash
# Check if installed
which codex

# If not installed
brew install codex  # or see https://github.com/openai/codex-cli

# Set API key
export OPENAI_API_KEY="your-key"  # https://platform.openai.com/api-keys
```

## Usage Patterns

### Non-Interactive (exec)

```bash
# Simple query
codex exec "Explain this error: ${error_message}"

# With file context (pipe content)
cat src/auth.py | codex exec "Review this authentication code for security issues"

# With specific model
codex exec -m gpt-5.2-codex "Analyze this design document" < design.md
```

### Interactive Session

```bash
# Start interactive with prompt
codex "Let's review the checkout flow"

# Resume previous session
codex resume --last
```

### Code Review

```bash
# Use the built-in review command
codex review src/checkout.ts

# Custom review
cat src/checkout.ts | codex exec "Review this code. Focus on:
1. Error handling
2. Edge cases
3. Performance"

# Review a diff
git diff HEAD~1 | codex exec "What are the risks of these changes?"
```

### Apply Changes

```bash
# Apply Codex's suggested changes
codex apply
```

## Multi-Model Collaboration

Use Codex alongside Claude for diverse perspectives:

```bash
# Get Codex's take on architecture
cat design.md | codex exec "Critique this architecture" > codex_review.md

# Use wicked-kanban to track the conversation
/wicked-garden:kanban:new-task "Architecture review" --priority P1
```

## Integration with wicked-kanban

For persistent cross-AI conversations:

```bash
# Create a task for the discussion
/wicked-garden:kanban:new-task "Design review: Auth system"

# Add Codex's perspective as a comment
codex exec "Review auth design" | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT TASK "Codex: $(cat)"

# Claude can then respond with its own perspective
```

## Available Commands

| Command | Description |
|---------|-------------|
| `codex [PROMPT]` | Interactive session |
| `codex exec PROMPT` | Non-interactive, one-shot |
| `codex review` | Built-in code review |
| `codex apply` | Apply latest diff |
| `codex resume` | Resume previous session |
| `codex fork` | Fork a previous session |

## Available Options

| Option | Description |
|--------|-------------|
| `-m MODEL` | Specify model (gpt-5.2-codex, o3, etc.) |
| `-i IMAGE` | Attach image(s) to prompt |
| `--enable FEATURE` | Enable a feature flag |
| `--disable FEATURE` | Disable a feature flag |

## Best Practices

1. **Use exec for automation**: `codex exec` is ideal for scripted workflows
2. **Pipe content**: Use stdin for context rather than file paths
3. **Compare perspectives**: Use both Codex and Claude for important decisions
4. **Track in kanban**: Record AI insights in wicked-kanban for team visibility
5. **Resume sessions**: Use `codex resume` to continue complex discussions
