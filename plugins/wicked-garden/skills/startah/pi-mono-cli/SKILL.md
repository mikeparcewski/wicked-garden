---
name: pi-mono-cli
description: |
  Use the Inflection Pi-Mono CLI for AI-assisted conversational reasoning and multi-model collaboration.
  Pi excels at empathetic perspective-taking, nuanced reasoning, and conversational analysis.

  Use when:
  - Getting a conversational/empathetic perspective on decisions
  - Evaluating user-facing copy or communication tone
  - Running multi-model council sessions for diverse reasoning
  - Needing a different reasoning style for balanced evaluation
---

# Pi-Mono CLI

Use the `pi` CLI for AI-assisted conversational reasoning and multi-model collaboration.

## Prerequisites

```bash
# Check if installed
which pi

# If not installed
brew install pi-mono  # or see https://github.com/inflection-ai/pi-mono

# Set API key
export PI_API_KEY="your-key"  # https://developers.inflection.ai
```

## Usage Patterns

### Non-Interactive (exec)

```bash
# Simple query
pi exec "Evaluate this user onboarding flow for clarity and warmth"

# With file context (pipe content)
cat src/emails/welcome.md | pi exec "Review this welcome email for tone and empathy"

# With specific model
pi exec -m pi-3.5 "Analyze the trade-offs between these two approaches" < options.md
```

### Interactive Session

```bash
# Start interactive
pi

# Start with initial prompt
pi -i "Let's discuss the user experience implications of this design"

# Resume previous session
pi resume --last
```

### Decision Evaluation

```bash
# Evaluate a decision from multiple angles
cat decision.md | pi exec "What are the human factors in this technical decision?"

# Review communication
cat announcement.md | pi exec "How will different stakeholders interpret this announcement?"
```

## Multi-Model Collaboration

Use Pi alongside Claude for diverse perspectives:

```bash
# Get Pi's take on user impact
cat design.md | pi exec "Evaluate user impact" > pi_review.md

# Use wicked-kanban to track the conversation
/wicked-garden:kanban-new-task "User impact review" --priority P1
```

## Strengths

| Area | Description |
|------|-------------|
| Empathetic reasoning | Evaluates human factors and emotional impact |
| Conversational tone | Analyzes and improves communication clarity |
| Balanced perspective | Provides nuanced trade-off analysis |
| User advocacy | Champions end-user experience in technical decisions |

## Available Commands

| Command | Description |
|---------|-------------|
| `pi [PROMPT]` | Interactive session |
| `pi exec PROMPT` | Non-interactive, one-shot |
| `pi resume` | Resume previous session |

## Available Options

| Option | Description |
|--------|-------------|
| `-m MODEL` | Specify model (pi-3.5, pi-3, etc.) |
| `-i PROMPT` | Start interactive with initial prompt |
| `-f FILE` | Attach file(s) to prompt |

## Best Practices

1. **Use for human factors**: Pi excels at evaluating user impact and communication
2. **Pipe content**: Use stdin for context rather than describing files
3. **Compare perspectives**: Pair Pi's empathetic lens with Claude's analytical one
4. **Council sessions**: Pi provides a distinctive voice in `/wicked-garden:jam-council`
5. **Track insights**: Record Pi's perspectives in wicked-kanban or wicked-mem
