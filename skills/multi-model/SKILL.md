---
name: multi-model
description: |
  Multi-model AI collaboration: discover authenticated providers and orchestrate
  council sessions, cross-model reviews, and diverse perspective gathering.
  Uses the collaboration API to spawn real agent sessions with different models per persona.
  Preferences stored in wicked-mem. Conversations tracked in wicked-kanban.

  Use when:
  - Running multi-model analysis or design review
  - Getting diverse AI perspectives on a decision
  - Council sessions with multiple AI models
  - Second opinion from a different AI
  - Multi-model code review or architecture critique
  - "multi-model", "council", "cross-ai", "diverse perspectives", "second opinion"
---

# Multi-Model Collaboration Skill

Orchestrate multi-model AI collaboration using the collaboration API.
Each council member gets a different model provider for genuine perspective diversity.

## How It Works

The collaboration system **does NOT shell out to CLIs**. Instead:

1. **Model Discovery** — `AuthStorage.create()` checks which providers have valid API keys
   (Anthropic, Google/Gemini, OpenAI/Codex, etc.)
2. **Model Rotation** — `CollaborationService.resolveModelAssignments()` round-robins
   authenticated models across personas so each council member uses a different model
3. **Agent Spawning** — Each persona gets a real `AgentRuntime` session via `AgentBridge.spawn()`
   with its assigned model spec (e.g. `anthropic:claude-opus-4-6`, `google-gemini-cli:gemini-2.5-pro`)
4. **Perspective Collection** — Outputs are captured from each session and persisted as
   `perspectives` on the collaboration record
5. **Synthesis** — The current pi session synthesizes all perspectives with full model attribution

## Quick Start

```bash
# Council mode — spawns agents with different models per persona
/jam:council "Should we use JWT or sessions for auth?"

# Quick jam — single model, 4 personas, fast
/jam:quick "How should we improve the visual design?"

# Full brainstorm — single model, 4-6 personas, 2-3 rounds
/jam:brainstorm "Architecture for the notification system"
```

## Model Assignment

### Automatic (Default)

When no explicit model map is provided, the system:

1. Discovers all authenticated providers via `AuthStorage`
2. Deduplicates by provider family (e.g. `openai-codex` and `openai` count as one)
3. Round-robins assignments across personas

Example with 3 authenticated providers and 5 personas:
```
architect       → anthropic:claude-opus-4-6
security-eng    → google-gemini-cli:gemini-2.5-pro
product-manager → openai-codex:gpt-5.3-codex
ux-designer     → anthropic:claude-opus-4-6    (wraps around)
staff-engineer  → google-gemini-cli:gemini-2.5-pro
```

### Explicit (via config.model_map)

Pass a `model_map` in the collaboration config to override specific roles:

```json
{
  "config": {
    "personas": ["architect", "security-engineer", "ux-designer"],
    "model_map": {
      "architect": "anthropic:claude-opus-4-6",
      "security-engineer": "google-gemini-cli:gemini-2.5-pro",
      "ux-designer": "openai:gpt-5.2"
    }
  }
}
```

Unmapped roles auto-rotate through remaining authenticated models.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  wg-jam.ts Extension (pi session)                    │
│  - /jam:council creates collaboration                │
│  - POST /collaborations/:id/run triggers multi-model │
│  - Receives perspectives, asks pi to synthesize      │
├─────────────────────────────────────────────────────┤
│  CollaborationService.runSession()                   │
│  - resolveModelAssignments() → picks models          │
│  - AgentService.spawn() per persona with model spec  │
│  - Polls for outputs, persists perspectives          │
├─────────────────────────────────────────────────────┤
│  AgentBridge.spawn()                                 │
│  - Creates AgentRuntime with model:                  │
│    getModel(provider, modelId) → PiAgent             │
│  - Each runtime has its own auth + provider          │
├─────────────────────────────────────────────────────┤
│  Model Providers (via @mariozechner/pi-ai)           │
│  - anthropic:claude-opus-4-6                         │
│  - google-gemini-cli:gemini-2.5-pro                  │
│  - openai-codex:gpt-5.3-codex                        │
│  - openai:gpt-5.2                                    │
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

### Automatic (via wg-jam extension)

Council results are automatically persisted:
- Collaboration record with all perspectives + model attribution
- Events emitted: `collaboration:created`, `collaboration:perspective:added`,
  `collaboration:run:completed`
- Each perspective's metadata includes `model` and `session_id`

### Manual (via wicked-mem)

Store decisions with full attribution:

```bash
/memory_write content="Auth: JWT with 15min/7day expiry.
Consensus: Claude, Gemini, Codex (idempotency critical).
Unique: Gemini flagged session store scaling concern.
Dissent: none." type=decision tags=auth,multi-model-review
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

If the `/collaborations/:id/run` endpoint fails (e.g. no agents registered,
bridge unavailable), the council gracefully falls back to single-model
prompt-based jam using the current pi session.

## References

**Orchestration:**
- [Orchestration Patterns](refs/orchestration.md) — API architecture, model rotation, agent spawning
- [Context Management](refs/context.md) — Session state, cross-AI handoffs, context windows

**CLI Providers:**
- [Codex](refs/codex.md) | [Gemini](refs/gemini.md) | [OpenCode](refs/opencode.md) | [Pi](refs/pi.md)

**Quality:**
- [Auditability](refs/auditability.md) — Audit trails, compliance, decision tracking
- [Examples](refs/examples.md) — ADR templates, synthesis patterns, review templates
