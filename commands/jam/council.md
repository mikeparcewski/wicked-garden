---
description: Structured multi-model evaluation using external LLM CLIs for independent perspectives
argument-hint: "<topic>" --options "A, B, C" [--criteria "perf, cost, risk"]
---

# /wicked-garden:jam:council

Structured evaluation tool that uses real external LLM CLIs (Codex, Gemini, OpenCode, Pi) to get genuinely independent model perspectives. Unlike brainstorm (free-form creative exploration), council is a **rigid evaluation tool** for when you have defined options and need a verdict.

**Key distinction**: `quick` = 60s ideation, `brainstorm` = full session (generation/explore), `council` = structured evaluation (decide).

> **Progression**: `quick` → `brainstorm` → `council` (this command, final step).
> See also: `/wicked-garden:jam:quick`, `/wicked-garden:jam:brainstorm`

Natural workflow: `brainstorm → identify candidates → council → decide`

Delegate to the council agent:

```
Task(subagent_type="wicked-garden:jam:council",
     prompt="Run a council evaluation on: {topic}. Options: {options}. Criteria: {criteria}.")
```

## Post-synthesis HITL judge (Issue #575)

After the council agent returns its synthesis (verdict + per-model votes + confidences), call the rule-based HITL judge to decide whether the verdict is strong enough to auto-proceed or whether the orchestrator should halt for human adjudication.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
from crew.hitl_judge import should_pause_council, write_hitl_decision_evidence
from pathlib import Path
votes = [
    {'model': 'codex',    'verdict': 'APPROVE', 'confidence': 0.9},
    {'model': 'gemini',   'verdict': 'APPROVE', 'confidence': 0.9},
    {'model': 'opencode', 'verdict': 'REJECT',  'confidence': 0.7},
    {'model': 'pi',       'verdict': 'APPROVE', 'confidence': 0.6},
]
d = should_pause_council(votes=votes)
write_hitl_decision_evidence(Path('<project_dir>'), 'council', 'council-decision.json', d)
print(d.pause, d.rule_id)
"
```

Pause rules (auto mode):

- top two verdicts within 2 votes (3-1 or closer) ⇒ pause (`council.split-verdict`)
- any model confidence < 0.6 ⇒ pause (`council.low-confidence-vote`)
- otherwise ⇒ auto-proceed and persist the votes to `council-decision.json` for the evidence bundle

Operator override: `WG_HITL_COUNCIL=auto|pause|off` (default `auto`).

## Raw per-model votes (Issue #584)

Default output now carries both the synthesised verdict AND a `raw_votes` list so callers can see per-model nuance even on unanimous verdicts. Assemble the envelope via `scripts/jam/consensus.py::build_council_output(votes, synthesized)` — it returns `{"synthesized": {...}, "raw_votes": [{"model", "verdict", "confidence", "rationale"}, ...]}` where each `rationale` is the model's own one-liner (or the first 240 chars of its response) and missing confidences stay `null`, not `0.0`.

Operator override: `WG_COUNCIL_OUTPUT=both|synth|raw` (default `both`). Use `synth` for the legacy single-key shape; use `raw` when tooling only wants the unvarnished per-model layer.
