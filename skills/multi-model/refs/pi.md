# Pi CLI — Usage Patterns

Inflection Pi-Mono CLI for conversational reasoning and multi-model collaboration.
Pi excels at empathetic perspective-taking, nuanced reasoning, and user-focused analysis.

## Installation and Setup

```bash
# Check if installed
which pi

# Install
brew install pi-mono  # or see https://github.com/inflection-ai/pi-mono

# Set API key
export PI_API_KEY="your-key"  # https://developers.inflection.ai
```

## Core Usage Patterns

### Non-Interactive (exec)

```bash
# Simple query
pi exec "Evaluate this user onboarding flow for clarity and warmth"

# With file context (pipe content)
cat src/emails/welcome.md | pi exec "Review this welcome email for tone and empathy"

# Specific model
pi exec -m pi-3.5 "Analyze the trade-offs between these two approaches" < options.md

# With file flag
pi exec -f design.md "How will users experience this change?"
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
# Human factors analysis
cat decision.md | pi exec "What are the human factors in this technical decision?"

# Communication review
cat announcement.md | pi exec "How will different stakeholders interpret this announcement?"

# User journey review
cat flows/checkout.md | pi exec "Where will users get confused or frustrated?"
```

## Pi's Distinct Role in Multi-Model Sessions

Pi provides a perspective that technical-first models often miss: the human and empathetic angle.

```bash
# Technical review: Codex + Claude cover code quality
cat src/auth.py | codex exec "Technical security review"

# User impact review: Pi covers human factors
cat src/auth.py | pi exec "How will error states and edge cases affect the user experience?"

# Communication review: Pi evaluates tone
cat docs/deprecation-notice.md | pi exec "Is this message clear and empathetic to affected users?"
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

## Kanban Integration

```bash
# Create review task
/wicked-garden:kanban:new-task "UX impact review: new auth flow" --priority P1

# Get Pi's perspective
PI_REVIEW=$(cat design.md | pi exec "User experience analysis")
# Add as kanban comment: "Pi (user advocacy): ${PI_REVIEW}"
```

## Command Reference

| Command | Description |
|---------|-------------|
| `pi [PROMPT]` | Interactive session |
| `pi exec PROMPT` | Non-interactive, one-shot |
| `pi resume` | Resume previous session |

## Options Reference

| Option | Description |
|--------|-------------|
| `-m MODEL` | Model: `pi-3.5`, `pi-3` |
| `-i PROMPT` | Start interactive with initial prompt |
| `-f FILE` | Attach file to prompt |

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
5. **Track insights** — Record Pi's perspectives in wicked-kanban or wicked-mem

## Common Prompts

```bash
# Error message review
cat src/errors.ts | pi exec "Are these error messages helpful and non-alarming for users?"

# Onboarding flow
cat docs/onboarding.md | pi exec "Where will new users get confused? What's missing?"

# Technical decision — user impact
cat decision.md | pi exec "What is the user impact of this technical choice? \
  Who is most affected and how?"

# Stakeholder communication
cat announcement.md | pi exec "How will engineers, managers, and end-users \
  each interpret this announcement? What's unclear or alarming?"

# Trade-off analysis
cat options.md | pi exec "Analyze these options from a human perspective. \
  Which is more intuitive? Which creates more user burden?"
```
