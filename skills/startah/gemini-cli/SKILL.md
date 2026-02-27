---
name: gemini-cli
description: |
  Use the Gemini CLI for AI-assisted tasks, code review, and multi-model collaboration.
  Gemini provides a second perspective on code, designs, and decisions.

  Use when:
  - Getting a second opinion on code or architecture
  - Reviewing designs from a different AI perspective
  - Running parallel analysis with multiple AI models
  - Needing Gemini-specific capabilities (long context, etc.)
---

# Gemini CLI

Use the `gemini` CLI for AI-assisted tasks and multi-model collaboration.

## Prerequisites

```bash
# Check if installed
which gemini

# If not installed
brew install gemini  # or npm install -g @google/gemini-cli

# Set API key
export GEMINI_API_KEY="your-key"  # https://aistudio.google.com/apikey
```

## Usage Patterns

### One-Shot Query (Non-Interactive)

```bash
# Simple query
gemini "Explain this error: ${error_message}"

# With file context (pipe content)
cat src/auth.py | gemini "Review this authentication code for security issues"

# With specific model
gemini -m gemini-2.0-flash "Quick summary of this diff" < git_diff.txt
```

### Interactive Session

```bash
# Start interactive
gemini

# Start with initial prompt, continue interactively
gemini -i "Let's review the checkout flow"
```

### Code Review

```bash
# Review a file
cat src/checkout.ts | gemini "Review this code. Focus on:
1. Error handling
2. Edge cases
3. Performance"

# Review a diff
git diff HEAD~1 | gemini "What are the risks of these changes?"
```

## Multi-Model Collaboration

Use Gemini alongside Claude for diverse perspectives:

```bash
# Get Gemini's take, then compare with Claude
cat design.md | gemini "Critique this architecture" > gemini_review.md

# Use wicked-kanban to track the conversation
/wicked-garden:kanban:new-task "Architecture review" --priority P1
# Add both AI perspectives as comments
```

## Integration with wicked-kanban

For persistent cross-AI conversations:

```bash
# Create a task for the discussion
/wicked-garden:kanban:new-task "Design review: Auth system"

# Add Gemini's perspective as a comment
gemini "Review auth design" | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT TASK "Gemini: $(cat)"

# Claude can then respond with its own perspective
```

## Available Options

| Option | Description |
|--------|-------------|
| `-m MODEL` | Specify model (gemini-2.0-flash, gemini-1.5-pro, etc.) |
| `-i PROMPT` | Start interactive with initial prompt |
| `-y` | YOLO mode - auto-accept all actions |
| `-s` | Sandbox mode |
| `-e EXT` | Use specific extensions |
| `-r` | Resume previous session |

## Best Practices

1. **Be specific**: Gemini works best with clear, focused prompts
2. **Pipe content**: Use stdin for context rather than describing files
3. **Compare perspectives**: Use both Gemini and Claude for important decisions
4. **Track decisions**: Use wicked-kanban or wicked-mem to record AI insights
