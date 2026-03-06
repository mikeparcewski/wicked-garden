# Codex CLI — Usage Patterns

OpenAI Codex CLI for AI-assisted coding, code review, and multi-model collaboration.
Codex excels at code generation, refactoring, and technical analysis.

## Installation and Setup

```bash
# Check if installed
which codex

# Install
brew install codex  # or see https://github.com/openai/codex-cli

# Set API key
export OPENAI_API_KEY="your-key"  # https://platform.openai.com/api-keys
```

## Core Usage Patterns

### Non-Interactive (exec)

```bash
# Simple query
codex exec "Explain this error: ${error_message}"

# With file context (pipe content)
cat src/auth.py | codex exec "Review this authentication code for security issues"

# Specific model
codex exec -m gpt-4o "Analyze this design document" < design.md

# Review a diff
git diff HEAD~1 | codex exec "What are the risks of these changes?"
```

### Interactive Session

```bash
# Start interactive with prompt
codex "Let's review the checkout flow"

# Resume previous session
codex resume --last

# Fork a session to explore alternatives
codex fork --last "What if we used event sourcing instead?"
```

### Code Review

```bash
# Built-in code review command
codex review src/checkout.ts

# Custom review with focus areas
cat src/checkout.ts | codex exec "Review this code. Focus on:
1. Error handling
2. Edge cases
3. Performance implications"

# Apply Codex's suggested changes
codex apply
```

## Multi-Model Collaboration

Use Codex for a second opinion on code and architecture:

```bash
# Get Codex's take on architecture
cat design.md | codex exec "Critique this architecture" > codex_review.md

# Compare with Claude's analysis
# Claude reviews in conversation; Codex via CLI

# Security review from both perspectives
git diff main | codex exec "Flag security issues in these changes"
```

## Kanban Integration

Track Codex insights for team visibility:

```bash
# Create a task for the review
/wicked-garden:kanban:new-task "Code review: auth-service refactor"

# Get Codex's review and add as comment
CODEX_REVIEW=$(cat src/auth.py | codex exec "Security review")
# Add CODEX_REVIEW as kanban comment with attribution
```

## Command Reference

| Command | Description |
|---------|-------------|
| `codex [PROMPT]` | Interactive session |
| `codex exec PROMPT` | Non-interactive, one-shot |
| `codex review [FILE]` | Built-in code review |
| `codex apply` | Apply latest diff |
| `codex resume` | Resume previous session |
| `codex fork` | Fork a previous session |

## Options Reference

| Option | Description |
|--------|-------------|
| `-m MODEL` | Model: `gpt-4o`, `o3`, `gpt-5.2-codex` |
| `-i IMAGE` | Attach image(s) to prompt |
| `--enable FEATURE` | Enable a feature flag |
| `--disable FEATURE` | Disable a feature flag |

## Strengths

| Area | Description |
|------|-------------|
| Code generation | Excels at producing well-structured code from specifications |
| Refactoring | Strong at identifying and applying structural improvements |
| Technical analysis | Deep understanding of code patterns and anti-patterns |
| Diff review | Effective at reviewing git diffs for risks and issues |

## Best Practices

1. **Use exec for automation** — `codex exec` is ideal for scripted workflows
2. **Pipe content** — Use stdin for context rather than describing files
3. **Compare perspectives** — Use Codex alongside Claude for important decisions
4. **Track in kanban** — Record AI insights for team visibility
5. **Resume sessions** — Use `codex resume` to continue complex discussions
6. **Fork for alternatives** — `codex fork` explores "what if" without losing current thread

## Integration with wicked-crew

In design and review phases, add Codex as a review step:

```bash
# Design phase: get Codex architecture critique
cat phases/design/output.md | codex exec "Architecture review: identify risks"

# Build phase: Codex code review on completed work
git diff main | codex exec "Code review: flag issues before PR"
```

## Common Prompts

```bash
# Security-focused
cat src/auth.py | codex exec "Security review: identify vulnerabilities, missing validation, injection risks"

# Architecture-focused
cat design.md | codex exec "Architecture critique: SRP violations, missing abstractions, scaling concerns"

# Error analysis
cat error.log | codex exec "Diagnose this error and suggest root cause + fix"

# Test coverage
cat src/checkout.ts | codex exec "What test cases are missing for this module?"
```
