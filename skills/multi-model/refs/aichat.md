# aichat CLI — Usage Patterns

`aichat` is an all-in-one LLM CLI written in Rust — fast, pipe-native, multi-provider. Covers OpenAI, Anthropic, Gemini, Mistral, Groq, Ollama, and more via a single YAML config.

## Installation and Setup

```bash
# Install
brew install aichat

# Interactive config wizard (writes ~/.config/aichat/config.yaml)
aichat --info                # inspects current config
aichat                       # first run opens setup

# Configure providers by editing ~/.config/aichat/config.yaml
# clients:
#   - type: openai
#     api_key: ...
#   - type: claude
#     api_key: ...
#   - type: ollama
#     api_base: http://localhost:11434/v1
```

## Core Usage Patterns

### Non-Interactive (pipe-native)

```bash
# Simple stdin
cat scaffold.md | aichat

# Pipe + system prompt
cat scaffold.md | aichat -S "Answer the 4 questions precisely and concisely."

# Pick a model for this call
cat scaffold.md | aichat -m claude:claude-sonnet-4-5 "Evaluate"
cat scaffold.md | aichat -m openai:gpt-4o "Evaluate"
cat scaffold.md | aichat -m ollama:llama3.1:70b "Evaluate"

# Disable streaming for clean capture
cat scaffold.md | aichat -S "Evaluate" -m openai:gpt-4o
```

### Include Files / URLs

```bash
# -f attaches files, directories, or URLs
aichat -f scaffold.md "Answer the 4 questions in the attached file."
aichat -f spec.pdf -f diagram.png "Critique this design."
aichat -f https://example.com/rfc.html "Summarize this RFC."
```

### Roles, Sessions, RAG (NOT used for council)

```bash
# Role — reusable system prompt
aichat --role security-reviewer "Review this snippet"

# Session — keeps context across invocations
aichat -s design-review "Initial take"
aichat -s design-review "Now add the security angle"

# RAG — retrieval over a corpus
aichat --rag my-docs "What does the spec say about retries?"
```

## aichat's Distinct Role in Multi-Model Sessions

`aichat` is a lightweight, fast alternative to `llm` when plugin churn isn't wanted. Config is a single YAML file; providers live there side by side. Good for picking one model per council run without the overhead of `llm`'s plugin system.

```bash
# Provider diversity in one CLI
cat "$SCAFFOLD" | aichat -m claude:claude-sonnet-4-5 "Evaluate"
cat "$SCAFFOLD" | aichat -m gemini:gemini-2.0-flash "Evaluate"
cat "$SCAFFOLD" | aichat -m groq:llama-3.3-70b "Evaluate"
```

## Strengths

| Area | Description |
|------|-------------|
| Single-binary | Rust executable, no Python / node runtime dependency |
| Multi-provider | OpenAI, Anthropic, Gemini, Mistral, Groq, Ollama, Azure, Bedrock |
| RAG + sessions | Built-in retrieval and threaded sessions when needed |
| Shell integration | `-e` shell assistant, `-c` code output mode |
| Config unified | One YAML — no plugins to install |

## Important Flags for Council Use

| Flag | Purpose |
|------|---------|
| `-m MODEL` | `client:model` — e.g. `claude:claude-sonnet-4-5`, `openai:gpt-4o` |
| `--prompt TEXT` | System prompt |
| `-S` | Disable streaming; return one block |
| `-f PATH\|URL` | Include file, directory, or URL |
| `--empty-session` | Force a fresh context |
| `--dry-run` | Show the assembled prompt without sending |

## Caveats

1. **Model selection uses `client:model` syntax.** `-m claude-sonnet-4-5` is wrong; `-m claude:claude-sonnet-4-5` is right.
2. **Default model is implicit.** Council dispatches should pin the model explicitly.
3. **Session files persist.** `~/.config/aichat/sessions/` accumulates — `--empty-session` or `-r ''` avoids carry-over.

## Command Reference (council subset)

| Command | Description |
|---------|-------------|
| `aichat "PROMPT"` | One-shot with default model |
| `cat FILE \| aichat "PROMPT"` | Pipe content as input |
| `aichat -m CLIENT:MODEL "PROMPT"` | Pick a specific model |
| `aichat -f FILE "PROMPT"` | Include a file |
| `aichat --list-models` | List configured models |
| `aichat --info` | Show current config |
