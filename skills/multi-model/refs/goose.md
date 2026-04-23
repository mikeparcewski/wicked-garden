# Goose CLI — Usage Patterns

Block's open-source AI agent. Goose is designed to *do things* — run tools, execute commands, read files — not just answer questions. In council mode it operates as a read-only responder via `goose run -i -`.

## Installation and Setup

```bash
# Install
brew install block-goose-cli

# Check the setup
goose doctor

# Configure provider
goose configure
# ...walks you through picking provider (OpenAI, Anthropic, Gemini, Ollama, Bedrock, Azure)
# ...and model
# ...writes ~/.config/goose/config.yaml
```

## Core Usage Patterns

### Non-Interactive (instructions from stdin)

```bash
# Read scaffold from stdin
cat scaffold.md | goose run -i -

# Pin a system prompt + read scaffold
cat scaffold.md | goose run -i - \
  --system "Answer the 4 questions precisely and concisely."

# Instructions inline
goose run -t "Evaluate Option A vs Option B for JWT session storage."

# From a file
goose run -i scaffold.md --system "Answer precisely."
```

### Sessions + Recipes (NOT used for council)

```bash
# Interactive agent session
goose session start

# Recipe — reusable parameterized agent
goose run --recipe design-review.yaml

# Scheduled jobs, terminal integration, MCP — outside council scope
goose sched list
goose term
goose mcp ...
```

## Goose's Distinct Role in Multi-Model Sessions

Goose has a stronger *agentic* reflex than the other CLIs — it tends to think about tools, MCP servers, and execution paths. That produces trade-off framings that notice automation surface and integration friction. Complementary to aider's edit-level reasoning and Pi's human-factor framing.

```bash
# Agentic framing in the council mix
cat "$SCAFFOLD" | codex exec "Architectural review"
cat "$SCAFFOLD" | goose run -i - --system "Evaluate with emphasis on automation, \
  tool integration, and operational blast radius."
```

## Strengths

| Area | Description |
|------|-------------|
| Agentic framing | Naturally reasons about tools, automation, and blast radius |
| Multi-provider | OpenAI, Anthropic, Gemini, Ollama, Bedrock, Azure |
| MCP-native | Can run as an ACP / MCP server; first-class tool-use integration |
| Recipes | YAML-defined agents for repeatable review scenarios |
| Open source | Apache-2.0, actively maintained by Block |

## Important Flags for Council Use

| Flag | Purpose |
|------|---------|
| `-i FILE` | Instruction file — use `-` for stdin |
| `-t TEXT` | Inline instruction text |
| `--system TEXT` | Additional system prompt |
| `--recipe NAME` | Named recipe file |
| `--params KEY=VALUE` | Parameters passed to the recipe |
| `--explain` | Show recipe metadata without running |

## Caveats

1. **Goose is an agent.** Without a narrow system prompt it may try to use tools, call MCP servers, or read the current directory. Pin `--system "Answer precisely, do not use tools"` when the council needs a pure response.
2. **Config is machine-wide.** `~/.config/goose/config.yaml` sets the provider + model. Switching per-invocation is possible via env overrides but less ergonomic than `llm -m` or `aichat -m`.
3. **Heavier install.** Binary + assets weigh ~280 MB vs ~10 MB for `aichat` / `llm`. Worth it for the agent surface; overkill for pure Q&A.

## Command Reference (council subset)

| Command | Description |
|---------|-------------|
| `goose run -t TEXT` | One-shot instruction |
| `goose run -i FILE` | Instructions from file |
| `cat FILE \| goose run -i -` | Instructions from stdin |
| `goose run --system TEXT -i FILE` | System prompt + instructions |
| `goose configure` | Pick provider + model |
| `goose doctor` | Verify config |
