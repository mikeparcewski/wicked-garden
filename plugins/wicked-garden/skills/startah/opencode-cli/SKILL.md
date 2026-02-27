---
name: opencode-cli
description: |
  Use the OpenCode CLI for AI-assisted coding with multiple models and providers.
  OpenCode supports various AI models and includes built-in MCP server management.

  Use when:
  - Getting a second opinion from different AI providers
  - Running parallel analysis with multiple AI models
  - Working with GitHub PRs and issues
  - Need a TUI-based AI coding session
---

# OpenCode CLI

Use the `opencode` CLI for AI-assisted coding and multi-model collaboration.

## Prerequisites

```bash
# Check if installed
which opencode

# If not installed
brew install opencode  # or see https://github.com/sst/opencode

# Authentication (supports multiple providers)
opencode auth  # Interactive auth setup
```

## Usage Patterns

### Non-Interactive (run)

```bash
# Simple query
opencode run "Explain this error: ${error_message}"

# With file context
opencode run "Review this code for security issues" -f src/auth.py

# With multiple files
opencode run "How do these modules interact?" -f src/api.ts -f src/db.ts

# With specific model
opencode run -m anthropic/claude-3-5-sonnet "Analyze this design" -f design.md

# Continue previous session
opencode run -c "What about error handling?"

# Continue specific session
opencode run -s SESSION_ID "Follow up question"
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

OpenCode supports multiple providers:

```bash
# Use specific provider/model
opencode run -m openai/gpt-4o "Query"
opencode run -m anthropic/claude-3-5-sonnet "Query"
opencode run -m google/gemini-1.5-pro "Query"

# With reasoning effort variant
opencode run -m openai/o1 --variant high "Complex analysis"

# List available models
opencode models
opencode models openai
opencode models anthropic
```

## Multi-Model Collaboration

Use OpenCode alongside Claude for diverse perspectives:

```bash
# Get OpenCode's take on architecture
opencode run -m openai/gpt-4o "Critique this architecture" -f design.md > opencode_review.md

# Use wicked-kanban to track the conversation
/wicked-garden:kanban-new-task "Architecture review" --priority P1
```

## Quick Reference

**Common commands:**
- `opencode` - Interactive TUI session
- `opencode run "message"` - Non-interactive one-shot
- `opencode run -f file.py "query"` - Query with file context
- `opencode run -c "follow up"` - Continue last session
- `opencode models` - List available models
- `opencode pr 123` - Work on GitHub PR

**Common options:**
- `-m provider/model` - Select model (e.g., `openai/gpt-4o`)
- `-f path` - Attach file(s) to message
- `-c` - Continue last session
- `-s SESSION_ID` - Continue specific session

For full reference, run `opencode --help` or see https://github.com/sst/opencode
