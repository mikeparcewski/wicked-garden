---
description: Structured multi-model evaluation using external LLM CLIs for independent perspectives
argument-hint: "<topic>" --options "A, B, C" [--criteria "perf, cost, risk"]
phase_relevance: ["clarify", "design"]
archetype_relevance: ["*"]
---

# /wicked-garden:jam:council

Structured evaluation tool that uses real external LLM CLIs — registry-driven (20+ CLIs: Codex, Gemini, Copilot, OpenCode, Pi, Aider, Goose, Amp, Droid, …; see `scripts/jam/agentic_cli_registry.py`) — to get genuinely independent model perspectives. Installed CLIs are detected AND usability-probed via `scripts/jam/detect_clis.py --probe` (auth-revoked / unconfigured / daemon-down CLIs are excluded). When fewer than 2 usable external CLIs are present, council seats are filled with `Task()` subagents so deliberation always happens. Unlike brainstorm (free-form creative exploration), council is a **rigid evaluation tool** for when you have defined options and need a verdict.

**Key distinction**: `quick` = 60s ideation, `brainstorm` = full session (generation/explore), `council` = structured evaluation (decide).

> **Progression**: `quick` → `brainstorm` → `council` (this command, final step).
> See also: `/wicked-garden:jam:quick`, `/wicked-garden:jam:brainstorm`

Natural workflow: `brainstorm → identify candidates → council → decide`

Delegate to the council agent:

```
Task(subagent_type="wicked-garden:jam:council",
     prompt="Run a council evaluation on: {topic}. Options: {options}. Criteria: {criteria}.")
```

## Acting on the council verdict

The council returns a synthesised verdict plus per-model raw votes. v11
archetypes decide what to do with the result; the council itself does
not gate. Heuristics for the caller:

- **Unanimous APPROVE / REJECT with all confidences ≥ 0.7** — proceed with
  the verdict.
- **Split verdict (3-1 or closer) OR any confidence < 0.6** — surface the
  raw votes to the user and pause for human adjudication. The disagreement
  carries information that the synthesised verdict erases.
- **High-stakes archetypes (`migrate`, `incident`, anything with
  `hard:cutover` / `hard:mitigate`)** — always show the raw votes
  alongside the verdict; never auto-proceed on a synth-only summary.

A v6-era helper (deleted in v11.0.0) encoded these rules in code as part
of the universal-pipeline machinery. v11 deleted the gate it fed into;
the heuristics above are the same shape, applied inline by the agent.

## Raw per-model votes (Issue #584)

Default output now carries both the synthesised verdict AND a `raw_votes` list so callers can see per-model nuance even on unanimous verdicts. Assemble the envelope via `scripts/jam/consensus.py::build_council_output(votes, synthesized)` — it returns `{"synthesized": {...}, "raw_votes": [{"model", "verdict", "confidence", "rationale"}, ...]}` where each `rationale` is the model's own one-liner (or the first 240 chars of its response) and missing confidences stay `null`, not `0.0`.

Operator override: `WG_COUNCIL_OUTPUT=both|synth|raw` (default `both`). Use `synth` for the legacy single-key shape; use `raw` when tooling only wants the unvarnished per-model layer.
