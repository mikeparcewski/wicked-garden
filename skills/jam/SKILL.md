---
name: wicked-garden-jam
user-invocable: true
description: |
  Orchestrates AI-powered brainstorming sessions with dynamic focus groups.
  quick sessions are ephemeral (no storage). brainstorm and council sessions
  are tracked as native tasks (process) and stored in wicked-brain:memory (outcome).
  Use when: "brainstorm this", "explore ideas", "get different perspectives",
  "focus group", "what do you think about", "pros and cons", "quick check",
  "jam quick <idea>", "jam brainstorm <topic>", "jam council <topic> with
  options A/B/C", "multi-model evaluation", "council verdict",
  "jam revisit <decision>", "how did that decision work out".
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# Brainstorming Skill

Generate diverse perspectives through structured focus group sessions.
This is the single entry point for the jam domain — route the user's request
to one of the sub-actions below.

## Routing

| Sub-action | When | How it runs |
|------------|------|-------------|
| `quick` | Gut-check, rapid exploration (~60s) | Inline — apply `refs/quick.md` directly |
| `brainstorm` | Important decisions, complex problems | Fork → `wicked-garden-jam-brainstorm-facilitator` |
| `council` | Defined options needing a rigid verdict | Fork → `wicked-garden-jam-council` |
| `revisit` | Record the outcome of a past decision | Inline — follow `refs/revisit.md` |

> **Progression**: `quick` (60s gut-check, ephemeral) → `brainstorm` (full
> session with evidence + decision storage) → `council` (structured verdict
> with external LLMs, final step). Key distinction: `quick` = ideation,
> `brainstorm` = free-form exploration, `council` = rigid evaluation of
> defined options.

## Quick-Start

```
# Fast gut-check (ephemeral, ~60s)
jam quick "Should we use feature flags or config files here?"

# Full session with evidence and decision storage
jam brainstorm "Architecture approach for the new event bus"

# High-stakes council with external LLM challenge
jam council "Go/no-go on the v9 storage migration" --options "go, no-go"

# Record how a past decision worked out
jam revisit "event bus architecture"
```

## Sub-action: quick

**Args**: `<idea or question>`

Quick 60-second exploration with 4 personas and 1 round. Run it inline — no
dispatch:

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/quick.md")` — the single-pass
   rubric: 4 personas, 1 forced round, synthesis format (Key Insights / Action
   Items / Open Questions), hard constraints (no storage, no multi-AI, ≤200 words).
2. Apply the rubric directly to the topic. Do NOT run additional rounds. Do NOT store.

## Sub-action: brainstorm

**Args**: `<topic> [--personas list] [--rounds n] [--converge fast]`

Full brainstorm with evidence-backed perspectives. The facilitator gathers
evidence from the ecosystem (past decisions, code context, brainstorm
outcomes) before assembling personas, so they argue from data — not just
opinions. After synthesis, a structured decision record is automatically
stored via wicked-brain:memory for organizational memory.

**Convergence modes** (pass through as `convergence_mode`):

- **normal** (default): Run all requested rounds (2-3), then synthesize.
- **fast** (`--converge fast`): After each round, assess whether there is
  enough signal to synthesize; skip remaining rounds when personas converge.

Dispatch to the forked facilitator skill (it owns the convergence checks,
native-task tracking, transcript storage, and bus events):

```
Skill(skill="wicked-garden-jam-brainstorm-facilitator",
      args="Run a full brainstorm session on: {topic}. Options: {personas}, {rounds}, convergence_mode={converge|'normal'}.")
```

## Sub-action: council

**Args**: `<topic> --options "A, B, C" [--criteria "perf, cost, risk"]`

Structured evaluation tool that uses real external LLM CLIs — registry-driven
(20+ CLIs: Codex, Gemini, Copilot, OpenCode, Pi, Aider, Goose, Amp, Droid, …;
see `scripts/jam/agentic_cli_registry.py`) — to get genuinely independent
model perspectives. Installed CLIs are detected AND usability-probed via
`scripts/jam/detect_clis.py --probe` (auth-revoked / unconfigured /
daemon-down CLIs are excluded). When fewer than 2 usable external CLIs are
present, council seats are filled with forked subagent seats so deliberation
always happens. Unlike brainstorm (free-form creative exploration), council is
a **rigid evaluation tool** for when you have defined options and need a
verdict.

Natural workflow: `brainstorm → identify candidates → council → decide`

Dispatch to the forked council skill:

```
Skill(skill="wicked-garden-jam-council",
      args="Run a council evaluation on: {topic}. Options: {options}. Criteria: {criteria}.")
```

**After the fork returns**: read
`${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/council-verdict.md` — it holds the
caller-side heuristics for acting on the verdict (when to proceed, when to
surface raw votes and pause for human adjudication, hard-gate archetype rules)
and the `raw_votes` output envelope contract
(`consensus.py::build_council_output`, `WG_COUNCIL_OUTPUT=both|synth|raw`).

## Sub-action: revisit

**Args**: `<topic or decision keyword>`

Revisit a past brainstorm decision to record whether it was validated,
invalidated, or modified. Light workflow — run it inline, no fork:

1. `Read("${CLAUDE_PLUGIN_ROOT}/skills/jam/refs/revisit.md")` — the 5-step
   workflow: recall the decision via wicked-brain:memory (`--filter_type
   decision`), display the decision summary, ask
   validated/invalidated/modified, store the outcome (tags `jam,outcome`,
   importance high), report. Degrades gracefully when wicked-brain is absent.
2. Follow it step by step, waiting for the user's outcome answer in step 3.

## Workers (forked skills)

- `skills/jam-brainstorm-facilitator/SKILL.md` — multi-round, evidence gathering, transcript storage, decision record
- `skills/jam-council/SKILL.md` — registry-driven multi-model council with isolation-enforced parallel dispatch

(`jam quick` runs inline via `refs/quick.md` — the former quick-facilitator
agent was retired; the ref is the sole, up-to-date rubric.)

## References

- `refs/quick.md` — the single-pass quick-jam rubric (personas, round, synthesis shape, hard constraints)
- `refs/revisit.md` — the decision-outcome revisit workflow
- `refs/council-verdict.md` — caller-side verdict heuristics + raw_votes output contract
- `refs/facilitation-patterns.md` — persona archetype pool, session length guidance, anti-patterns
- `refs/synthesis-patterns.md` — synthesis structure, quality checklist, decision record format
