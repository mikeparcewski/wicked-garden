# llm CLI — Usage Patterns

Simon Willison's `llm` — a pipe-native multi-provider aggregator. One command, many providers, everything via plugins. Ideal fit for council scaffolds: `cat scaffold | llm "prompt"` just works.

## Installation and Setup

```bash
# Install
brew install llm
# or: pipx install llm

# Configure providers via keys
llm keys set openai
llm keys set anthropic
llm keys set gemini

# Install plugin-backed providers
llm install llm-anthropic
llm install llm-gemini
llm install llm-mistral
llm install llm-groq
llm install llm-ollama           # local models via Ollama

# Set a default model
llm models default claude-sonnet-4-5
llm models default gpt-4o
```

## Core Usage Patterns

### Non-Interactive (pipe-native)

```bash
# Simple pipe
echo "Evaluate this trade-off..." | llm

# Pipe with a system prompt
cat scaffold.md | llm "You are evaluating options for a technical decision. \
  Answer the 4 questions below precisely and concisely."

# Pick a specific model for this call
cat scaffold.md | llm -m claude-sonnet-4-5 "Evaluate options"
cat scaffold.md | llm -m gpt-4o "Evaluate options"
cat scaffold.md | llm -m groq/llama-3.3-70b "Evaluate options"
cat scaffold.md | llm -m mistral-large "Evaluate options"

# Inline prompt — no pipe
llm "Which option do you recommend for session storage: JWT or sticky sessions?"
```

### Attach Files

```bash
# Attach the scaffold as an input, pass system prompt positionally
llm -a scaffold.md "Answer the 4 questions in the attached file."

# Multiple attachments (images, text, URLs)
llm -a diagram.png -a spec.md "Critique this design."
```

### Conversational (for iteration, NOT council)

```bash
# Continue the previous exchange
llm -c "Elaborate on the security angle."

# Named conversation thread
llm --cid design-review "Initial take?"
llm --cid design-review -c "Now weigh in on cost."
```

## llm's Distinct Role in Multi-Model Sessions

`llm` is the **universal adapter**. If the council needs a model no other CLI wraps — Groq's Llama 3.3, Mistral Large, a local Ollama model, a Bedrock endpoint — `llm` reaches it without adding a whole new tool to the roster.

```bash
# Council with local + cloud diversity via a single CLI
cat "$SCAFFOLD" | llm -m claude-sonnet-4-5 "Evaluate"          # cloud
cat "$SCAFFOLD" | llm -m ollama/llama3.1:70b "Evaluate"        # local
cat "$SCAFFOLD" | llm -m groq/mixtral-8x22b "Evaluate"         # edge
```

## Strengths

| Area | Description |
|------|-------------|
| Pipe-native | Designed for Unix composition; stdin in, text out |
| Multi-provider | OpenAI, Anthropic, Gemini, Mistral, Groq, Bedrock, Ollama, Azure |
| Plugin ecosystem | `llm install llm-*` adds providers without changing the CLI |
| Persistent log | All prompts + responses saved to `~/.local/share/llm/logs.db` (SQLite) |
| Templates | `llm -t template-name` stores reusable system prompts |

## Important Flags for Council Use

| Flag | Purpose |
|------|---------|
| `-m MODEL` | Override default model for this call |
| `-s TEXT` | System prompt |
| `-a FILE\|URL` | Attach a file or URL |
| `--no-stream` | Disable streaming; return one block |
| `-o KEY VALUE` | Provider-specific option (e.g. `-o temperature 0`) |
| `-t NAME` | Apply a stored template |

## Caveats

1. **Default model matters.** `llm` uses whatever `llm models default` points at unless `-m` is given. Council dispatches should pin the model explicitly if provider attribution matters.
2. **Logs everything.** All prompts go to `~/.local/share/llm/logs.db`. Disable with `--no-log` per call, or turn off globally with `llm logs off`.
3. **Plugins are per-install.** `llm install llm-anthropic` is not automatic — check `llm plugins` before relying on a provider.

## Command Reference (council subset)

| Command | Description |
|---------|-------------|
| `llm "PROMPT"` | One-shot with default model |
| `cat FILE \| llm "PROMPT"` | Pipe content as input |
| `llm -m MODEL "PROMPT"` | Pick a specific model |
| `llm -a FILE "PROMPT"` | Attach a file |
| `llm models` | List available models |
| `llm plugins` | List installed plugins |
| `llm logs -n 5` | Last 5 logged prompts |
