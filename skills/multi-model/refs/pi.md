# Pi CLI — Usage Patterns

`pi` is a coding-agent CLI (`@mariozechner/pi-coding-agent` on npm). Configurable across Google, OpenAI, Anthropic, and more; works as a council member via non-interactive `-p` mode with `@file` attachments.

> **Note:** This is *not* the retired Inflection Pi-Mono CLI. That project ended; `pi` today is Mario Zechner's coding agent.

## Installation and Setup

```bash
# Check if installed
which pi

# Install (npm global)
npm install -g @mariozechner/pi-coding-agent

# Configure provider — picks Google by default
# Set provider API keys as env vars
export GEMINI_API_KEY="..."       # default provider
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."

# Override default provider/model per call
pi --provider anthropic --model claude-sonnet-4-5 "..."
pi --model openai/gpt-4o "..."
pi --model sonnet:high "..."      # thinking-level shorthand
```

## Core Usage Patterns

### Non-Interactive (`-p` / `--print`)

```bash
# Simple query
pi -p "Evaluate this user onboarding flow for clarity and warmth"

# Attach files via @file syntax
pi -p "Review this welcome email for tone and empathy" @src/emails/welcome.md

# Multiple attachments
pi -p "Answer the 4 questions in the attached scaffold." @scaffold.md

# Specific provider + model
pi --provider anthropic --model claude-sonnet-4-5 -p "Analyze trade-offs" @options.md

# Thinking level
pi --thinking high -p "Solve this complex decision" @context.md

# Ephemeral — do not save session
pi --no-session -p "One-off question" @scaffold.md
```

### Interactive Session

```bash
# Start interactive
pi

# Start with initial prompt
pi "Let's discuss the user experience implications of this design"

# Continue previous session
pi --continue "What did we decide?"

# Select a session to resume
pi --resume
```

### Decision Evaluation

```bash
# Human factors analysis
pi -p "What are the human factors in this technical decision?" @decision.md

# Communication review
pi -p "How will different stakeholders interpret this announcement?" @announcement.md

# User journey review
pi -p "Where will users get confused or frustrated?" @flows/checkout.md
```

## Pi's Distinct Role in Multi-Model Sessions

Pi is configurable across providers, so its "voice" depends on which model is selected. When pointed at a capable conversational model, it contributes empathetic perspective-taking and stakeholder framing — a useful counterweight to the code-editor framing of `aider` or the architectural framing of `codex`.

```bash
# Technical review via codex
cat src/auth.py | codex exec "Technical security review"

# Human-factor framing via pi (anthropic Sonnet)
pi --provider anthropic --model claude-sonnet-4-5 -p \
  "How will error states and edge cases affect the user experience?" @src/auth.py

# Communication review via pi (google)
pi -p "Is this message clear and empathetic to affected users?" @docs/deprecation-notice.md
```

## Strengths

| Area | Description |
|------|-------------|
| Empathetic reasoning | Evaluates human factors and emotional impact |
| Communication tone | Analyzes and improves tone, clarity, and warmth |
| User advocacy | Champions end-user experience in technical decisions |
| Balanced perspective | Provides nuanced trade-off analysis |
| Stakeholder analysis | Considers diverse stakeholder responses |

## Multi-Model Collaboration

Pi provides the human-factor voice in council sessions:

```bash
CONTEXT="docs/auth-design.md"

# Technical reviews
cat "$CONTEXT" | codex exec "Architecture review: technical risks"
cat "$CONTEXT" | gemini "Security and scalability analysis"

# Human factors review (Pi's unique contribution)
cat "$CONTEXT" | pi exec "User experience and human factors: where will users struggle? \
  What error states are confusing? What emotional impact does this design have?"

# Synthesize all perspectives
```

## Native Task Tracking

```
# Create review task
TaskCreate(
  subject="UX impact review: new auth flow",
  metadata={
    "event_type": "task",
    "chain_id": "ux-review.root",
    "source_agent": "multi-model:pi",
    "priority": "P1"
  }
)

# Get Pi's perspective and append to the task description via TaskUpdate
# PI_REVIEW=$(cat design.md | pi exec "User experience analysis")
# TaskUpdate(taskId, description="{previous}\n\nPi (user advocacy): ${PI_REVIEW}")
```

## Command Reference

| Command | Description |
|---------|-------------|
| `pi [PROMPT]` | Interactive session |
| `pi -p PROMPT` | Non-interactive, one-shot |
| `pi -p PROMPT @FILE` | Non-interactive with file attached |
| `pi --continue` | Continue previous session |
| `pi --resume` | Select a session to resume |

## Options Reference

| Option | Description |
|--------|-------------|
| `-p`, `--print` | Non-interactive mode |
| `--provider NAME` | `google` (default), `openai`, `anthropic`, `github-copilot`, etc. |
| `--model PATTERN` | e.g. `claude-sonnet-4-5`, `openai/gpt-4o`, `sonnet:high` |
| `--thinking LEVEL` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| `--system-prompt TEXT` | Override default system prompt |
| `--append-system-prompt TEXT` | Append to default system prompt |
| `--no-tools` | Disable tool use (pure Q&A) |
| `--no-session` | Do not persist this session |
| `@FILE` | Attach file content to the message |

## Council Sessions

Pi is particularly valuable in `/wicked-garden:jam:council` sessions. Pi's voice represents
user empathy and human-centered design in a panel of technical perspectives:

```bash
/wicked-garden:jam:council "Should we use biometric auth or PIN codes for mobile login?"
# Pi's persona argues for user comfort, accessibility, and emotional safety
# Technical personas argue implementation and security trade-offs
```

## Best Practices

1. **Use for human factors** — Pi excels at evaluating user impact and communication
2. **Review communications** — Error messages, announcements, onboarding copy all benefit from Pi
3. **Pipe content** — Use stdin or `-f` for context
4. **Council sessions** — Pi's empathetic voice is essential in decision councils
5. **Track insights** — Record Pi's perspectives via native TaskUpdate or wicked-brain:memory

## Common Prompts

```bash
# Error message review
pi -p "Are these error messages helpful and non-alarming for users?" @src/errors.ts

# Onboarding flow
pi -p "Where will new users get confused? What's missing?" @docs/onboarding.md

# Technical decision — user impact
pi -p "What is the user impact of this technical choice? Who is most affected and how?" @decision.md

# Stakeholder communication
pi -p "How will engineers, managers, and end-users each interpret this announcement? What's unclear or alarming?" @announcement.md

# Trade-off analysis
pi --thinking high -p "Analyze these options from a human perspective. Which is more intuitive? Which creates more user burden?" @options.md
```
