# Copilot CLI — Usage Patterns

GitHub Copilot CLI for AI-assisted coding, code review, and multi-model collaboration.
Copilot supports multiple backend models and excels at codebase-aware analysis.

## Installation and Setup

```bash
# Check if installed
which copilot

# Install
brew install copilot-cli          # macOS (Homebrew)
winget install GitHub.Copilot     # Windows (WinGet)
npm install -g @github/copilot   # all platforms (npm)
curl -fsSL https://gh.io/copilot-install | bash  # macOS/Linux (curl)

# Authenticate
copilot  # launches interactive login flow on first run
```

## Core Usage Patterns

### Non-Interactive (prompt mode)

```bash
# Simple query
copilot -p "Explain this error: ${error_message}" --output-format text

# With file context (pipe content)
cat src/auth.py | copilot -p "Review this authentication code for security issues" --output-format text

# Specific model
copilot -p "Analyze this design document" --model gpt-5.2 --output-format text < design.md

# Review a diff
git diff HEAD~1 | copilot -p "What are the risks of these changes?" --output-format text

# Text-only (no tool use) — best for council dispatch
cat scaffold.md | copilot -p "Answer the questions" --output-format text --available-tools=""
```

### Interactive Session

```bash
# Start interactive
copilot

# Start with a specific model
copilot --model claude-sonnet-4

# With full permissions (no confirmation prompts)
copilot --allow-all
```

### Code Review

```bash
# Review with piped content
cat src/checkout.ts | copilot -p "Review this code. Focus on:
1. Error handling
2. Edge cases
3. Performance implications" --output-format text

# Review a PR diff
git diff main | copilot -p "Flag security issues in these changes" --output-format text
```

## Multi-Model Collaboration

Use Copilot for a second opinion on code and architecture:

```bash
# Get Copilot's take on architecture
cat design.md | copilot -p "Critique this architecture" --output-format text > copilot_review.md

# Security review
git diff main | copilot -p "Flag security issues in these changes" --output-format text

# Council dispatch (text-only, no tools, piped scaffold)
cat "$SCAFFOLD_FILE" | copilot -p "You are evaluating options for a technical decision. Answer the 4 questions below precisely and concisely." --output-format text --available-tools=""
```

## Command Reference

| Flag | Description |
|------|-------------|
| `-p, --prompt <text>` | Non-interactive mode (exits after completion) |
| `--output-format <fmt>` | Output format: `text` (default) or `json` |
| `--model <model>` | Backend model selection |
| `--available-tools <tools>` | Restrict available tools (empty string = none) |
| `--allow-all` | Enable all permissions (tools, paths, URLs) |
| `--allow-all-tools` | Allow all tools without confirmation |
| `--reasoning-effort <lvl>` | Reasoning effort: `low`, `medium`, `high`, `xhigh` |
| `--add-dir <dir>` | Add directory to allowed file access list |
| `--quiet` | Suppress non-essential output |

## Model Options

| Model | Description |
|-------|-------------|
| `claude-sonnet-4` | Anthropic Claude Sonnet 4 |
| `gemini-3-pro-preview` | Google Gemini 3 Pro |
| `gpt-5.4` | OpenAI GPT-5.4 |
| `gpt-5.2-codex` | OpenAI Codex (code-optimized) |

## Strengths

| Area | Description |
|------|-------------|
| Codebase awareness | Deep understanding of project structure and context |
| Multi-model backend | Switch between Claude, GPT, and Gemini models |
| GitHub integration | Native access to GitHub APIs, PRs, issues |
| Tool orchestration | Built-in MCP server support for extensibility |

## Best Practices

1. **Use `-p` for automation** — non-interactive mode is ideal for scripted workflows
2. **Pipe content** — use stdin for context rather than describing files
3. **Disable tools for council** — `--available-tools=""` ensures text-only responses
4. **Use `--output-format text`** — cleaner output for parsing and synthesis
5. **Choose models intentionally** — `--model` lets you pick the best backend for the task

## Integration with wicked-crew

In design and review phases, add Copilot as a review step:

```bash
# Design phase: get Copilot architecture critique
cat phases/design/output.md | copilot -p "Architecture review: identify risks" --output-format text

# Build phase: Copilot code review on completed work
git diff main | copilot -p "Code review: flag issues before PR" --output-format text
```

## Common Prompts

```bash
# Security-focused
cat src/auth.py | copilot -p "Security review: identify vulnerabilities, missing validation, injection risks" --output-format text

# Architecture-focused
cat design.md | copilot -p "Architecture critique: SRP violations, missing abstractions, scaling concerns" --output-format text

# Error analysis
cat error.log | copilot -p "Diagnose this error and suggest root cause + fix" --output-format text

# Test coverage
cat src/checkout.ts | copilot -p "What test cases are missing for this module?" --output-format text
```
