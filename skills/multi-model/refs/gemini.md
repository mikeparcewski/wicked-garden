# Gemini CLI — Usage Patterns

Google Gemini CLI for AI-assisted tasks, long-context analysis, and multi-model collaboration.
Gemini excels at long-context document review and broad analysis.

## Installation and Setup

```bash
# Check if installed
which gemini

# Install
npm install -g @google/gemini-cli
# or: brew install gemini

# Set API key
export GEMINI_API_KEY="your-key"  # https://aistudio.google.com/apikey
```

## Core Usage Patterns

### One-Shot Query (Non-Interactive)

```bash
# Simple query
gemini "Explain this error: ${error_message}"

# With file context (pipe content)
cat src/auth.py | gemini "Review this authentication code for security issues"

# Specific model
gemini -m gemini-2.0-flash "Quick summary of this diff" < git_diff.txt

# Review a diff
git diff HEAD~1 | gemini "What are the risks of these changes?"
```

### Interactive Session

```bash
# Start interactive
gemini

# Start with initial prompt, continue interactively
gemini -i "Let's review the checkout flow"

# Resume previous session
gemini -r
```

### Long-Context Analysis

Gemini's primary strength is handling large documents and codebases:

```bash
# Review entire spec document
cat docs/full-spec.md | gemini "Summarize key technical decisions and flag inconsistencies"

# Cross-file analysis
cat src/*.ts | gemini "Identify patterns and inconsistencies across these modules"

# Large diff review
git diff main...feature-branch | gemini "Review this entire feature branch for issues"
```

### Code Review

```bash
# Review a file
cat src/checkout.ts | gemini "Review this code. Focus on:
1. Error handling
2. Edge cases
3. Performance"

# Review with specific concern
cat src/auth.py | gemini "Security review: focus on authentication, session management, and injection"
```

## Multi-Model Collaboration

Use Gemini for broad coverage and long-context review:

```bash
# Gemini for long docs (strength: context window)
cat docs/architecture-200-pages.md | gemini "Summarize and flag concerns" > gemini_review.md

# Pair with Codex for code-specific details
cat src/auth.py | codex exec "Code-level security review"
```

## Native Task Tracking

```
# Create review task
TaskCreate(
  subject="Architecture review: payment service",
  metadata={
    "event_type": "task",
    "chain_id": "payment-arch-review.root",
    "source_agent": "multi-model:gemini",
    "priority": "P1"
  }
)

# Capture Gemini's perspective and append to the task description via TaskUpdate
# GEMINI_REVIEW=$(cat docs/payment-design.md | gemini "Architecture critique")
# TaskUpdate(taskId, description="{previous}\n\nGemini: ${GEMINI_REVIEW}")
```

## Options Reference

| Option | Description |
|--------|-------------|
| `-m MODEL` | Model: `gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-2.0-pro` |
| `-i PROMPT` | Start interactive with initial prompt |
| `-r` | Resume previous session |
| `-y` | YOLO mode — auto-accept all actions |
| `-s` | Sandbox mode |
| `-e EXT` | Use specific extensions |

## Strengths

| Area | Description |
|------|-------------|
| Long context | Handles very large documents (1M+ tokens on Pro models) |
| Broad analysis | Covers diverse aspects in a single pass |
| Document review | Strong at spec review, ADR analysis, architecture docs |
| Diff summaries | Effective at summarizing large diffs |

## Best Practices

1. **Pipe content** — Use stdin for context rather than describing files
2. **Use for long docs** — Leverage Gemini's context window for large inputs
3. **Be specific** — Focused prompts yield more actionable output
4. **Compare perspectives** — Pair Gemini broad analysis with Codex code-specific review
5. **Track decisions** — Use native TaskUpdate and wicked-garden:mem for team visibility

## Session Management

```bash
# Start and continue a design review session
gemini -i "Let's review the auth design"
# ... interactive discussion ...
# Resume later:
gemini -r

# When context gets stale, summarize first
echo "Summarize our discussion in 5 bullet points" | gemini
# Start fresh with summary as context
```

## Common Prompts

```bash
# Architecture review
cat design.md | gemini "Architecture review: identify scalability concerns, missing components, and design risks"

# Document inconsistency check
cat docs/spec.md | gemini "Find inconsistencies, ambiguities, and missing requirements"

# Security analysis
cat src/auth/ | gemini "Security analysis: authentication, authorization, and data exposure risks"

# API review
cat docs/api-spec.yaml | gemini "Review API design for REST consistency, versioning, and breaking changes"

# Cross-AI handoff
echo "Prior analysis from Claude: ${CLAUDE_ANALYSIS}

Build on this. What did Claude miss? What would you add?" | gemini
```

## Integration with wicked-crew

```bash
# Design phase: Gemini reviews architecture doc
cat phases/design/arch.md | gemini "Review architecture for completeness and risks"

# Review phase: Gemini reviews PR
gh pr diff 123 | gemini "Code review: identify issues, missing tests, doc gaps"
```
