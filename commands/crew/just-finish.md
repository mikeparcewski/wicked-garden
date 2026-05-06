---
description: Execute remaining work with maximum autonomy and guardrails
argument-hint: "[--autonomy=ask|balanced|full] [--justification \"<text>\"]"
---

# /wicked-garden:crew:just-finish

Continue project with maximum autonomy, respecting safety guardrails. Runs **ALL remaining phases** to completion. (For a single phase, use `crew:execute`. To toggle the auto-approve flag without running, use `crew:auto-approve`.)

> **Deprecation**: `--yolo` is a compatibility shim for `--autonomy=full`. Resolves through `scripts/crew/autonomy.py` (emits the one-shot deprecation warning, returns the resolved mode). Will be removed in a future release.

## 1. Resolve autonomy + load project state

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import sys
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
from crew.autonomy import emit_deprecation_warning, get_mode
import os
if '--yolo' in os.environ.get('WG_ARGS', ''): emit_deprecation_warning('--yolo', '--autonomy=full')
print('autonomy_mode:', get_mode().value)
"
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

Read `${project_dir}/process-plan.json` for: 9 factors (each carries `reading` for internal logic + `risk_level` for user-facing text — see #627), `complexity` (0–7), `rigor_tier` (`minimal` / `standard` / `full`), `specialists`, ordered `phases[]` with per-phase `primary` specialist list. Discover available specialists via `scripts/crew/specialist_discovery.py --json` and match against the facilitator's picks.

## 2. Orchestrator-only principle (CRITICAL)

The main agent is an **orchestrator only** — never inline implementation, analysis, or review work. ALL processing dispatches to subagents via `Task()` with the relevant `subagent_type`. The orchestrator only: reads project state, makes routing decisions, dispatches subagents, tracks task lifecycle via `TaskList`/`TaskGet`, reports progress.

Each phase MUST execute via a fresh `Task()` so context does not accumulate across phases. Subagent prompts include this bootstrap order: (1) `scripts/crew/phase_manager.py {project} status --json`, (2) `outcome.md`, (3) prior phase deliverables under `phases/{prev}/`, (4) `TaskList` filtered to project, (5) `Skill('wicked-garden:smaht', args="build --task ... --project ... --dispatch --prompt")` if available.

## 3. Autonomy mode

In `--autonomy=full`: proceed without asking for minor decisions, auto-approve routine choices, auto-engage specialists when signal thresholds met, only pause at guardrails (Section 4) and the clarify HITL gate (Section 3.5). Track every assumption in `project.json::assumptions[]` with `{phase, assumption, reason}` and surface them in the final completion report.

### 3.5 Clarify HITL gate (#575)

After the clarify subagent writes `objective.md`, `acceptance-criteria.md`, and `complexity.md`, call the rule-based judge:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
from crew.hitl_judge import should_pause_clarify, write_hitl_decision_evidence
from pathlib import Path
d = should_pause_clarify(complexity=<N>, facilitator_confidence=<0..1>, open_questions=<count>, yolo=True)
write_hitl_decision_evidence(Path('<project_dir>'), 'clarify', 'hitl-decision.json', d)
print(d.pause)
"
```

Pause when `pause=True`. Skip when `pause=False`. Operator override: `WG_HITL_CLARIFY=auto|pause|off` (default `auto`). The judge writes `phases/clarify/hitl-decision.json` for audit. In dangerous mode (`AskUserQuestion` auto-completes), wait 30s then proceed with logged "auto-accepted by timeout."

### 3.6 Facilitator plan (yolo mode)

`process-plan.json` is the source of truth — `just-finish` does NOT re-run archetype detection. If the plan is missing (legacy projects pre-v6), invoke the facilitator now in `mode: "propose"` with the resolved `--rigor=` and write the plan before proceeding. Yolo skips interactive confirmations but preserves the facilitator-chosen rigor, gates, and evidence requirements.

## 4. Guardrails (ALWAYS pause)

Auto-proceed is forbidden on: deployment, deletions, security/auth/secrets, external services (API, DB), irreversible actions. On a guardrail hit, prompt:

```
## Guardrail: {type}
Action: {what}    Risk: {why}
Proceed? (Y/n)
```

## 5. Execute remaining work — per phase

For each phase in `project.json::phase_plan`:

1. Skip if complete; otherwise dispatch the matched specialist subagent (Section 1's discovery).
2. Run the **mandatory quality gate** when `gate_required: true` per `.claude-plugin/phases.json`:
   - Fast-pass (complexity ≤ 1, no security/compliance signals, phase ≠ review): generic reviewer; record `gate: {type: fast-pass, result: approved}` in `phases/{phase}/status.md`.
   - Otherwise: `/wicked-garden:crew:gate phases/{phase}/ --gate {gate_type}`.
3. Handle gate outcome:
   - **APPROVE**: proceed to sign-off.
   - **CONDITIONAL**: apply AC-4.4 auto-resolution (below).
   - **REJECT**: STOP, report to user.
4. **Sign-off via the Gate Reviewer Policy** (`.claude-plugin/gate-policy.json`): route reviewer by gate type × complexity. Council required at complexity ≥ 5 execution gates / ≥ 4 strategy gates, or on security/compliance signals, CONDITIONAL gates, or prior REJECT. Human sign-off required at complexity ≥ 6 execution gates even in just-finish.
5. **Checkpoint re-evaluation** when `phases.json::{phase}.checkpoint == true`: re-invoke the facilitator in `re-evaluate` mode with the prior plan, compare new factor `reading` values, persist updated `factors`/`complexity`/`specialists` (preserve BOTH `reading` and `risk_level`; never drop `risk_level`). Surface injections to user using `risk_level` not `reading`. Max 2 injections per checkpoint. Skip if `phase_plan_mode: "static"`.
6. **Approve via phase_manager** — verify gate completion first; reject auto-skip of `--override-gate` and `--override-deliverables`:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} approve --phase {phase}
   ```
   If approve fails on missing deliverables, STOP and report — autonomous deliverable overrides are not permitted.

### AC-4.4 CONDITIONAL auto-resolution

Classify each condition by the rule "Does resolving this change what we're building or how we measure success?" — if no, auto-resolve and document in `phases/{phase}/conditions-manifest.json` with `auto_resolved: true`; if yes (or uncertain), escalate via `Skill('wicked-garden:jam:council', ...)` with the condition options. Re-run the gate after all auto-resolvable conditions are fixed.

### Testing-strategy guard

Before executing phases at complexity ≥ 2, verify `phase_plan` includes `test-strategy` and `test`. If missing, inject before proceeding (same injection rules as execute.md §4.5). Test phase is **non-skippable** (`is_skippable: false`); valid skip reasons restricted to `user_explicit_request` or `ci_equivalent_exists`.

## 6. Issue deliberation pre-step

Before clarify/design phase execution, run `Skill('wicked-garden:deliberate', args="<issue>")` on each issue. In just-finish, autonomously incorporate the deliberator's recommendations EXCEPT: flag to user if recommendation is **Close** / **Defer**, or if **Redesign** with scope expansion > 2×.

## 7. Progress reporting + completion

Periodic updates: brief markdown with `Phase` / `Status` / `Completed` / `In Progress` / `Upcoming`. At project completion, render summary covering: artifacts created, **assumptions made** (organized by phase from `project.json::assumptions[]`), and any follow-up recommendations.

### 7.5 Learning capture (AC-4.6)

At every gate returning CONDITIONAL or REJECT, store one `procedural` memory describing what went wrong. At review-phase approval, store: any new user preferences (`preference`), patterns that worked (`procedural`, importance medium), anti-patterns discovered (`procedural`, importance high). All via `Skill('wicked-brain:memory', ...)` — generalisable lessons, NOT project-specific.

## 8. Error handling

On block / unrecoverable error: stop autonomous execution, report the issue plainly, ask for guidance. Do not attempt workarounds that risk damage.
