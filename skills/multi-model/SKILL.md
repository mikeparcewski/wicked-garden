---
name: wicked-garden:multi-model
context: fork
description: |
  Multi-model AI collaboration: discover installed LLM CLIs and orchestrate
  council sessions, cross-model reviews, and diverse perspective gathering.
  Detects 20+ agentic/chat/local CLIs at runtime from a machine-readable
  registry (scripts/jam/agentic_cli_registry.py) and usability-probes them
  (scripts/jam/detect_clis.py --probe) so auth-revoked / unconfigured /
  daemon-down CLIs are excluded.
  Decisions stored in wicked-brain:memory. Transcripts persisted via jam scripts.

  Use when: running a council session across multiple LLM CLIs, getting a
  second opinion from a different model on a decision, or doing a cross-model
  code or architecture review.
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# Multi-Model Collaboration Skill

Orchestrate multi-model AI collaboration using external LLM CLIs.
Each council member is a different model provider for genuine perspective diversity.

## How It Works

The multi-model system uses **external LLM CLIs** discovered + probed at runtime
from the registry — never a hand-maintained `which` list:

1. **Detect + Probe** — `detect_clis.py --probe` reads the registry, `shutil.which`-es
   each binary, then runs each detected CLI's headless form (with registry trust
   flags) on a trivial prompt to classify **usable** vs **installed-but-unusable**
   (auth revoked / no provider / daemon down). Captures version strings to
   disambiguate binary collisions (`grok`, `agent`, `forge`, `q`).
2. **Quorum Check** — Council requires 2+ **usable external** CLIs; below that,
   fill seats with `Task()` subagents so a real council always convenes.
3. **Question Scaffold** — All models answer the same fixed 4-question set
4. **Parallel Dispatch** — Each usable CLI is invoked per its registry `input_mode`,
   isolated + sandboxed + timeboxed, runs independently
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

The supported-CLI list is **not maintained here** — it lives in the registry
(`scripts/jam/agentic_cli_registry.py`), one record per CLI with its headless
invocation, input mode, model-flag style, trust flags, auth hint, and install
commands. Run `detect_clis.py --list` to dump it. This is the de-drift source
of truth; do not re-list flags in prose.

The registry currently covers **20+ CLIs** across three categories:

- **agentic-coder** — `claude`, `codex`, `gemini`, `agy` (Antigravity), `pi`,
  `opencode`, `aider`, `copilot`, `goose`, `cursor-agent`, `amp`, `droid`,
  `qwen`, `crush`, `openhands`, `gptme`, `interpreter` (+ confirm-on-probe:
  `grok`, `forge`, `continue`, `cline`).
- **chat** — `llm`, `aichat`, `mods`, `sgpt`, `q` (Amazon Q / `kiro-cli`).
- **local-runner** — `ollama` (needs a running daemon + a pulled model).

Records flagged `confirm-on-probe` have an uncertain headless flag — the probe
verifies them before the council relies on them. Deprecated / winding-down
tools (`cody`, `plandex`) ship `enabled_for_council=False`.

Claude always participates as a council member (in-process host) alongside the
usable external CLIs.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  /jam:council Command                                │
│  - Parses topic, options, criteria                   │
│  - Dispatches to council agent                       │
├─────────────────────────────────────────────────────┤
│  Council Agent (agents/jam/council.md)               │
│  - detect_clis.py --probe (registry-driven)          │
│  - Builds question scaffold (4 fixed questions)      │
│  - Renders each usable CLI per its input_mode        │
│  - Claude answers the same scaffold independently    │
├─────────────────────────────────────────────────────┤
│  Detect + Probe (scripts/jam/detect_clis.py)         │
│  - registry → shutil.which → headless usability probe│
│  - usable vs installed-but-unusable (auth/provider/  │
│    daemon); version strings for collision disambig   │
│  - <2 usable external → Task() subagent fallback tier│
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
- Retrievable via `wicked-brain:query` for past session context

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

Quorum is counted over **usable external** CLIs (post-probe), not raw
detections. When fewer than 2 are usable, council fills the empty seats with
`Task()` subagents (distinct framing personas, isolated + parallel) so a real
council always convenes — these in-harness seats are weaker diversity than
external vendors and are labelled as such in the synthesis. With exactly 1
usable external CLI it runs as "single external guest" (optionally topped up
with subagent seats). Only if neither external CLIs nor subagents are available
does it suggest `/jam:brainstorm` (single-model, multi-persona).

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
