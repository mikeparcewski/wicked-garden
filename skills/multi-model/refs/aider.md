# Aider CLI — Usage Patterns

Aider is an AI pair-programmer designed to edit code inside a git repo. For council use it runs in a restricted one-shot mode: no git, no commits, no file edits — just an answer to the scaffold prompt.

## Installation and Setup

```bash
# Install
brew install aider
# or: pipx install aider-chat

# Configure a provider (reads env vars)
export ANTHROPIC_API_KEY="..."     # claude models
export OPENAI_API_KEY="..."        # gpt models
export DEEPSEEK_API_KEY="..."      # deepseek
```

## Core Usage Patterns

### Non-Interactive (one-shot, no git, answer only)

```bash
# Preferred form for council — read scaffold from file
aider --message-file scaffold.md \
  --no-git --yes-always --no-auto-commits --no-stream --no-analytics

# Ad-hoc question without a file
aider --message "Evaluate Option A vs Option B for JWT session storage." \
  --no-git --yes-always --no-auto-commits --no-stream --no-analytics

# Pick a specific model
aider --model sonnet --message-file scaffold.md \
  --no-git --yes-always --no-auto-commits --no-stream
aider --model gpt-4o --message-file scaffold.md \
  --no-git --yes-always --no-auto-commits --no-stream
aider --model deepseek/deepseek-reasoner --message-file scaffold.md \
  --no-git --yes-always --no-auto-commits --no-stream
```

### Interactive (NOT used for council)

```bash
aider                                    # interactive repo-editing session
aider path/to/file.py                    # with file attached
aider --architect                        # architect mode
```

## Aider's Distinct Role in Multi-Model Sessions

Aider's native orientation is code-editor, so it tends to answer from an *engineering-in-the-repo* lens rather than a purely architectural one. That produces concrete, diff-aware trade-offs — complementary to Gemini's broad analysis or Pi's human-factor framing.

```bash
# Council context: three models, three framings
cat "$SCAFFOLD" | codex exec "Architectural review"
cat "$SCAFFOLD" | gemini "Scalability + risk framing"
aider --message-file "$SCAFFOLD" --no-git --yes-always \
  --no-auto-commits --no-stream --no-analytics
```

## Strengths

| Area | Description |
|------|-------------|
| Code-grounded trade-offs | Reasons about diffs, edits, migration steps |
| Repo-awareness | Knows how changes will land in an actual codebase |
| Model flexibility | Supports OpenAI, Anthropic, DeepSeek, OpenRouter, Ollama, Bedrock, Azure |
| Architect + editor split | `--architect` mode for planning; editor for fine-grained diffs |

## Important Flags for Council Use

| Flag | Purpose |
|------|---------|
| `--message-file FILE` | Read the prompt from a file (use this for the scaffold) |
| `--message TEXT` | Inline prompt — escape carefully |
| `--no-git` | Do not initialize or require a git repo |
| `--yes-always` | Auto-accept any confirmation prompts |
| `--no-auto-commits` | Never commit in this run |
| `--no-stream` | Disable token streaming; return one block |
| `--no-analytics` | Disable anonymous usage reporting |
| `--model NAME` | Override the default model |

## Caveats

1. **Aider expects a writable cwd.** It will create `.aider.*` cache/history files. Call it from a scratch tempdir if that matters.
2. **Answers may be diff-flavored.** If aider drifts into proposing SEARCH/REPLACE blocks, treat them as code-ready annotations, not a council verdict.
3. **Interactive escape.** `--yes-always` is required — without it, aider will pause for input the moment a confirmation would normally fire.
4. **Streaming off is deliberate.** Council synthesis runs after all CLIs finish; streamed output wastes buffer and complicates transcript capture.

## Command Reference (council subset)

| Command | Description |
|---------|-------------|
| `aider --message TEXT` | One-shot prompt |
| `aider --message-file FILE` | One-shot prompt from a file |
| `aider --model MODEL` | Override model |
| `aider --architect` | Split planner/editor reasoning (interactive) |
