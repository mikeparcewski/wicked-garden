---
name: multi-model
description: |
  Multi-model AI collaboration: discover installed LLM CLIs and orchestrate
  council sessions, cross-model reviews, and diverse perspective gathering.
  Detects codex, copilot, gemini, opencode, pi, aider, llm, aichat, and goose
  CLIs at runtime via PATH discovery.
  Decisions stored in wicked-brain:memory. Transcripts persisted via jam scripts.

  Use when: running a council session across multiple LLM CLIs, getting a
  second opinion from a different model on a decision, or doing a cross-model
  code or architecture review.
---

# Multi-Model Collaboration Skill

Orchestrate multi-model AI collaboration using external LLM CLIs.
Each council member is a different model provider for genuine perspective diversity.

## How It Works

The multi-model system uses **external LLM CLIs** discovered at runtime:

1. **CLI Discovery** — `which codex copilot gemini opencode pi aider llm aichat goose` detects installed CLIs
2. **Quorum Check** — Council requires 2+ external CLIs; 0 = refuse, 1 = warn
3. **Question Scaffold** — All models answer the same fixed 4-question set
4. **Parallel Dispatch** — Each CLI receives the scaffold via stdin pipe, runs independently
5. **Synthesis** — Claude synthesizes all perspectives with model attribution

## Quick Start

```bash
# Council mode — dispatches to external CLIs in parallel
/jam:council "Should we use JWT or sessions for auth?"

# Quick jam — single model, 4 personas, fast
/jam:quick "How should we improve the visual design?"

# Full brainstorm — single model, 4-6 personas, 2-3 rounds
/jam:brainstorm "Architecture for the notification system"
```

## Supported CLIs

| CLI | Install | Model / Provider |
|-----|---------|------------------|
| `codex` | `brew install codex` | OpenAI Codex |
| `copilot` | `brew install copilot-cli` | GitHub Copilot |
| `gemini` | `npm i -g @google/gemini-cli` | Google Gemini |
| `opencode` | `brew install opencode` | Configurable (OpenAI/Anthropic/local) |
| `pi` | `npm i -g @mariozechner/pi-coding-agent` | Configurable (Google default, OpenAI/Anthropic/etc.) |
| `aider` | `brew install aider` | Configurable — code-editor orientation |
| `llm` | `brew install llm` | Multi-provider aggregator (OpenAI, Anthropic, Mistral, local via plugins) |
| `aichat` | `brew install aichat` | Multi-provider aggregator |
| `goose` | `brew install block-goose-cli` | Block Goose agent (configurable provider) |

Claude always participates as a council member alongside the external CLIs.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  /jam:council Command                                │
│  - Parses topic, options, criteria                   │
│  - Dispatches to council agent                       │
├─────────────────────────────────────────────────────┤
│  Council Agent (agents/jam/council.md)               │
│  - Detects CLIs via `which`                          │
│  - Builds question scaffold (4 fixed questions)      │
│  - Pipes scaffold to each CLI in parallel            │
│  - Claude answers the same scaffold independently    │
├─────────────────────────────────────────────────────┤
│  External CLI Dispatch                               │
│  - cat scaffold.md | codex exec "..."                │
│  - cat scaffold.md | gemini "..."                    │
│  - cat scaffold.md | opencode run "..."              │
│  - pi -p "..." @scaffold.md                          │
│  - aider --message-file scaffold --no-git --yes     │
│  - cat scaffold.md | llm "..."                       │
│  - cat scaffold.md | aichat "..."                    │
│  - cat scaffold.md | goose run -i -                  │
├─────────────────────────────────────────────────────┤
│  Synthesis (3-stage)                                 │
│  - Stage 1: Raw responses per model                  │
│  - Stage 2: Synthesis matrix + risk convergence      │
│  - Stage 3: Verdict (consensus or fault lines)       │
└─────────────────────────────────────────────────────┘
```

## Synthesis Framework

After gathering perspectives from different models, synthesize using:

| Signal | Meaning | Action |
|--------|---------|--------|
| **Consensus** (2+ models agree) | High confidence issue | Address immediately |
| **Unique insight** | One model caught it | Evaluate carefully |
| **Disagreement** | Genuine tradeoff | Human decides |
| **Silence** | No model flagged it | Lower priority |

## Persistence

### Automatic (via save_transcript.py)

Council responses are persisted as transcript entries:
- Each model's response stored with `persona_type: council`
- Synthesis appended as `entry_type: synthesis`
- Retrievable via `/jam:transcript` and `/jam:thinking`

### Manual (via wicked-brain:memory)

Store decisions with full attribution:

```
Skill(skill="wicked-brain:memory", args="store \"Auth: JWT with 15min/7day expiry.\nConsensus: Claude, Gemini, Codex (idempotency critical).\nUnique: Gemini flagged session store scaling concern.\nDissent: none.\" --type decision --tags auth,multi-model-review")
```

## When to Use Multi-Model

| Situation | Recommendation |
|-----------|----------------|
| Architecture decisions | Yes — high impact, catch blind spots |
| Security review | Yes — different models flag different risks |
| Important PRs | Yes — diverse review perspectives |
| Visual/UX design | Yes — different aesthetic sensibilities |
| Quick bug fix | No — overhead not worth it |
| Routine code | No — single AI sufficient |

## Fallback Behavior

If no external CLIs are detected, council refuses and suggests
`/jam:brainstorm` (single-model, multi-persona) as an alternative.
With only 1 CLI, it runs as "brainstorm with external guest" with a warning.

## References

**Orchestration:**
- [Orchestration Patterns](refs/orchestration.md) — CLI dispatch, parallel execution, synthesis
- [Context Management](refs/context.md) — Session state, cross-AI handoffs, context windows

**CLI Providers:**
- [Codex](refs/codex.md) | [Copilot](refs/copilot.md) | [Gemini](refs/gemini.md) | [OpenCode](refs/opencode.md) | [Pi](refs/pi.md)
- [Aider](refs/aider.md) | [llm](refs/llm.md) | [aichat](refs/aichat.md) | [Goose](refs/goose.md)

**Quality:**
- [Auditability](refs/auditability.md) — Audit trails, compliance, decision tracking
- [Examples](refs/examples.md) — ADR templates, synthesis patterns, review templates
