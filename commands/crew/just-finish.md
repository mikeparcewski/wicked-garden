---
description: Execute remaining work with maximum autonomy and guardrails
argument-hint: "[--yolo --justification \"<text>\"] [--autonomy=ask|balanced|full]"
---

# /wicked-garden:crew:just-finish

> **Deprecation notice (v8-PR-6, Issue #593)**: The `--yolo` flag on this
> command is a compatibility shim. Prefer `--autonomy=full` instead; it is
> equivalent and routes through the new single autonomy layer
> (`scripts/crew/autonomy.py`). The `--yolo` flag will be removed in a future
> version.  The execution behaviour of `just-finish` itself is preserved.
>
> **Autonomy layer shim step** — when `--yolo` is passed, emit the one-shot
> deprecation warning and resolve mode via the autonomy layer before executing:
> ```bash
> sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
> import sys
> sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
> from crew.autonomy import emit_deprecation_warning, get_mode, AutonomyMode
> emit_deprecation_warning('--yolo', '--autonomy=full')
> mode = get_mode()
> print('autonomy_mode:', mode.value)
> "
> ```
> If `--autonomy=<mode>` is passed explicitly, skip the deprecation warning and
> use the specified mode directly. Default (no flag) resolves to `ask`.

Continue project with maximum autonomy, respecting safety guardrails.

## When to use this vs the others

| Command | What it does |
|---------|-------------|
| `crew:execute` | Run a **single phase** to completion |
| `crew:just-finish` | Run **ALL remaining phases** to completion |
| `crew:auto-approve` | Toggle the APPROVE-auto-advance flag (**no execution**) |

## Flags

- `--yolo`: Grant auto-approve inline before running remaining phases. Applies the same
  guardrails as `crew:auto-approve --approve` (justification required at full rigor,
  cooldown enforced, second-persona review sentinel required). CONDITIONAL and REJECT
  verdicts always surface to the user regardless. Equivalent to running
  `crew:auto-approve --approve` then `crew:just-finish` in sequence.
- `--justification "<text>"`: Required with `--yolo` at full rigor (>= 40 chars).

## Instructions

### 1. Load Project State

Locate the active project and read state from both `project.json` (for phase progress) and `process-plan.json` (for v6 facilitator plan):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

From `project.json`:
- Current phase
- Remaining phases
- What's been completed

From `${project_dir}/process-plan.json` (schema: `skills/propose-process/refs/output-schema.md`):
- **factors**: 9 factor entries (reversibility, blast_radius, compliance_scope, etc.) — each entry carries both `reading` (HIGH/MEDIUM/LOW; HIGH=safest, backward-compat per #627) and `risk_level` (low_risk/medium_risk/high_risk; user-facing). Use `reading` for internal threshold/diff logic; use `risk_level` for any text shown to the user. Replaces `signals_detected`
- **complexity**: 0-7 integer
- **rigor_tier**: `minimal | standard | full`
- **specialists**: facilitator-picked roster — replaces `specialists_recommended`
- **phases**: ordered phase plan with per-phase `primary` specialist list

### 2. Discover Available Specialists

Run specialist discovery:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/specialist_discovery.py --json
```

Match available specialists against the facilitator's picks (`process-plan.json` `specialists[]` and `phases[].primary`) for auto-engagement.

### 2.5 Gather Context via wicked-smaht (if available)

Before starting phase work, assemble structured context from the ecosystem. This ensures specialists and fallback agents receive rich context — not just raw deliverable text.

```
Skill(skill="wicked-garden:smaht:context", args="build --task \"Execute {current_phase} phase for {project-name}\" --project \"{project-name}\" --dispatch --prompt")
```

Include the context package output in ALL subagent Task() dispatches. If the command fails, proceed with project.json signals and deliverable text only.

### 2.6 Orchestrator-Only Principle

**CRITICAL: The main agent is an ORCHESTRATOR only.** It must NOT perform complex analysis, implementation, or review work inline. Instead:

- **ALL processing** goes through subagent `Task()` dispatches to specialists or fallback agents
- The main agent ONLY: reads project state, makes routing decisions, dispatches subagents, tracks task lifecycle, and reports progress
- Manage context through tools (TaskList, TaskGet, Read) — do NOT accumulate large working state in the main conversation
- When in doubt, delegate to a subagent rather than doing work inline

### 2.7 Fresh-Start Phase Dispatch

**CRITICAL: Each phase MUST execute via a fresh `Task()` dispatch (subagent) so context does not accumulate across phases.** The main orchestrator loop stays lean and never carries forward phase-specific working state.

The orchestrator loop for each phase:

1. **Load project state** via phase_manager:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} status --json
   ```

2. **Dispatch the phase** as a fresh subagent via `Task()`. The subagent bootstraps its own context from persistent state rather than inheriting the orchestrator's conversation history. Include bootstrap instructions in the Task prompt so the subagent knows how to self-orient.

3. **After the Task() returns**, the orchestrator verifies completion (deliverables exist, task counts met), runs checkpoint analysis if the phase has `checkpoint: true`, and approves the phase.

**Context bootstrap order** (for the subagent to follow inside the Task):

1. **Project metadata** — phase_manager status --json (current phase, signals, complexity, phase plan)
2. **Outcome** — outcome.md (desired outcome, success criteria)
3. **Prior phase deliverables** — read deliverables from the immediately preceding phase(s) in `phases/{prev-phase}/`
4. **Task evidence** — TaskList filtered to project name for in-progress and completed tasks
5. **Smaht context** — if available, `Skill(skill="wicked-garden:smaht:context", args="build --task \"...\" --project \"...\" --dispatch --prompt")` for ecosystem-wide context

**Why fresh dispatch matters:**

- Prevents context window bloat — each subagent starts with only the state it needs
- Enables parallel phase execution for independent phases
- Makes phase retries clean — a failed phase can be re-dispatched without leftover state
- The orchestrator remains stateless and can always reconstruct progress from phase_manager + TaskList

### 3. Autonomy Mode

In "just-finish" mode:
- Proceed without asking for minor decisions
- Auto-approve routine choices
- **Auto-engage specialists** when signal thresholds are met
- Only pause at guardrails
- **For the clarify phase**: Make reasonable assumptions based on the project description and signal analysis. Document all assumptions in the phase deliverables. **After the clarify subagent writes `objective.md`, `acceptance-criteria.md`, and `complexity.md`**, halt and present a summary:

  ```markdown
  ## Clarify Phase Complete — Confirmation Required

  ### Assumptions Made
  {List each assumption from the clarify deliverables}

  ### Key Decisions
  - **Scope**: {in-scope summary}
  - **Complexity**: {score}/7
  - **Acceptance Criteria**: {count} criteria defined

  ### Deliverables Written
  - phases/clarify/objective.md
  - phases/clarify/acceptance-criteria.md
  - phases/clarify/complexity.md

  **Review the deliverables above.** These define the success criteria for all
  subsequent phases.

  Proceed with these assumptions? (Y/n)
  ```

  **The clarify gate MUST NOT run until the user acknowledges.** This halt applies even in automated runs — the session pauses at this boundary. In dangerous mode (where `AskUserQuestion` auto-completes), wait 30 seconds, log "Autonomous clarify: assumptions accepted by timeout (dangerous mode)", then proceed. This prevents circular self-grading where the same model writes requirements and then validates work against those same requirements without human review.

  **HITL judge (Issue #575)**: Before deciding whether to halt, call the rule-based judge:

  ```bash
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
  from crew.hitl_judge import should_pause_clarify, write_hitl_decision_evidence
  from pathlib import Path
  d = should_pause_clarify(
      complexity=<complexity from clarify>,
      facilitator_confidence=<facilitator self-rated confidence 0..1>,
      open_questions=<count of unresolved questions>,
      yolo=True,
  )
  write_hitl_decision_evidence(Path('<project_dir>'), 'clarify', 'hitl-decision.json', d)
  print(d.pause)
  "
  ```

  Pause when the judge returns `pause=True`. Skip the halt when the judge returns `pause=False` — the rule table reads: yolo + facilitator confidence ≥ 0.7 + complexity < 5 + 0 open questions ⇒ auto-proceed. Operator override: `WG_HITL_CLARIFY=auto|pause|off` (default `auto`). The judge always writes `phases/clarify/hitl-decision.json` so the verdict is auditable in the evidence bundle.
- **Track assumptions**: When making any assumption, immediately record it in project.json:
  ```json
  {
    "assumptions": [
      {"phase": "clarify", "assumption": "Requirements are for the current codebase", "reason": "No alternate target specified"},
      {"phase": "build", "assumption": "Backward compatibility preserved", "reason": "No breaking change request"}
    ]
  }
  ```
- **Document assumptions**: At project completion, include an "Assumptions Made" appendix listing every tracked assumption

### 3.5 Facilitator Plan (yolo mode)

**v6**: the facilitator's `process-plan.md` (written during `/wicked-garden:crew:start`)
is the source of truth for phase plan, rigor_tier, and specialists. `just-finish` does
NOT re-run archetype detection — the facilitator already folded archetype context into
its factor readings.

1. **Read project descriptor files** for context that might have changed since start:
   AGENTS.md, CLAUDE.md, README.md, package.json (load AGENTS.md first, CLAUDE.md overrides).
2. **Query memories** for prior patterns:
   ```
   Skill(skill="wicked-brain:memory", args={"action": "recall", "query": "project type and quality dimensions for {project-name}"})
   ```
3. **Read `${project_dir}/process-plan.json`** to load the facilitator's cached plan.
4. If the plan is missing (legacy project created before v6), invoke the facilitator
   now with `mode: "propose"` + `--rigor=` as specified in flags, and write the plan
   before proceeding.

In yolo mode, skip the interactive confirmations but preserve the rigor tier, gates,
and evidence requirements from the facilitator plan. Yolo is an interaction-mode
axis, not a phase-plan or rigor axis.

### 4. Guardrails (ALWAYS pause)

Never auto-proceed on:
- **Deployment**: Any action that deploys to production/staging
- **Deletions**: Removing files, directories, or data
- **Security**: Auth changes, secrets, permissions
- **External Services**: API calls, database changes
- **Irreversible Actions**: Anything that can't be undone

When hitting a guardrail:
```markdown
## Guardrail: {type}

**Action**: {what you want to do}
**Risk**: {why this needs approval}

Proceed? (Y/n)
```

### 4.5 Checkpoint Re-Evaluation

**Same as execute.md Section 4.5 — run after every checkpoint phase completes.**

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` and check if the completed
phase has `"checkpoint": true` (clarify, design, build).

When a checkpoint phase completes:

1. Gather phase artifacts from `phases/{phase}/`
2. Re-invoke the facilitator in `re-evaluate` mode:
   ```
   Skill(
     skill="wicked-garden:propose-process",
     args={
       "description": "{summary of deliverables}",
       "mode": "re-evaluate",
       "project_slug": "{slug}",
       "prior_plan_path": "${project_dir}/process-plan.json",
       "output": "json"
     }
   )
   ```
3. Compare new factor `reading` values against project.json `factors[].reading`
   (internal diff — `reading` is the canonical comparison key; #627)
4. If factor readings shift or complexity increases:
   - Update project.json (factors, complexity, specialists) — persist BOTH
     `reading` and `risk_level` from the facilitator output verbatim; never
     drop `risk_level` on the way to disk (#627)
   - Check if phases NOT in `phase_plan` should be injected (see execute.md Section 4.5 for injection rules)
   - When reporting injections to the user (even in yolo mode), surface
     `risk_level` (low_risk / medium_risk / high_risk), not raw `reading`
5. Maximum 2 injections per checkpoint

**Skip if**: project.json has `"phase_plan_mode": "static"`.

### 4.6 Issue Deliberation Pre-Step

**Same as execute.md — run before clarify or design phase execution.**

Before accepting requirements at face value, run the deliberator on each issue:

```
Skill(skill="wicked-garden:deliberate", args="{issue description or GH#}")
```

In just-finish mode, make autonomous decisions based on the deliberation briefs EXCEPT:
- If the deliberator recommends **Close** or **Defer** — flag to user (removing scope needs visibility)
- If the deliberator recommends **Redesign** with scope expansion > 2x — flag to user

Otherwise, incorporate tech debt opportunities and scope changes into deliverables automatically.

### 5. Execute Remaining Work

Read project.json `phase_plan` for the ordered list of phases. For each remaining phase:

1. Check if phase is complete or needs work
2. **Auto-engage specialists** based on phase and signals (use dynamic routing from execute.md — signal analysis + specialist.json `enhances` declarations)
3. Execute phase work via specialists or built-in fallbacks
4. **Run mandatory quality gate** (see Section 5.5 below)
5. **Get sign-off** using the **Gate Reviewer Policy** (see `.claude-plugin/gate-policy.json` and execute.md section 8):
   - Route reviewer by gate type × complexity score (not a flat priority chain)
   - Council required at complexity >= 5 execution gates, >= 4 strategy gates
   - Escalate to council on security/compliance signals, CONDITIONAL gates, or prior REJECT
   - Human sign-off required at complexity >= 6 execution gates (even in just-finish)
   - Fallback chain: Council → Third-party CLI → Specialist → Generic → Human
6. Auto-approve if deliverables meet criteria AND sign-off is `approved`
7. **Run checkpoint re-analysis** if phase has `checkpoint: true` (Section 4.5)
8. **Gate then approve** — before calling `phase_manager approve`, verify gate completion:
   - If `gate_required` is `true` for this phase AND no `gate-result.json` exists in
     `phases/{phase}/` yet: go back to step 4 (run the gate now — do NOT skip it).
   - If gate ran and returned **APPROVE** or **CONDITIONAL**: call approve without
     `--override-gate`:
     ```bash
     sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} approve --phase {phase}
     ```
   - If gate ran and returned **REJECT**: STOP. Do not call approve. Report to user.
   - If approve fails due to **missing deliverables**: STOP. Do NOT pass `--override-deliverables`
     automatically. Report the missing deliverables to the user and wait for them to be created or
     for explicit user instruction to bypass. Autonomous deliverable overrides are not permitted.
   - `--override-gate` is reserved for exceptional circumstances only (e.g., gate ran
     externally, CI result already available). If used, `--reason` is REQUIRED:
     ```bash
     sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} approve \
       --phase {phase} --override-gate --reason "Gate ran via CI; result APPROVE, job #1234"
     ```
9. Continue until done or guardrail hit

**Sign-off in just-finish mode**: Route reviewer per Gate Reviewer Policy (gate type × complexity). Council is used when policy requires it (high complexity or escalation triggers). If sign-off returns `rejected`, STOP and report to user. If `conditional`, apply AC-4.4 CONDITIONAL auto-resolution (see below). Human review is skipped in just-finish mode EXCEPT at complexity >= 5 execution gates (build, test, review) where human approval is mandatory.

### 5.5 Mandatory Quality Gate

**Same as execute.md Section 7.5 — run after deliverables are complete, before sign-off.**

> **CAUTION**: Fast-pass (complexity <= 1, no security signals) uses a generic reviewer
> instead of the full QE gate orchestrator — but it STILL records a `gate:` block in
> `phases/{phase}/status.md`. This satisfies `_check_gate_run()` in phase_manager.
> Do NOT call `phase_manager approve --override-gate` as a substitute for fast-pass.
> Use the fast-pass path in Section 5.5 step 1.

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` for the current phase's `gate_required` and `gate_type`.

If `gate_required` is `true`:

1. **Fast-pass**: complexity <= 1 AND no security/compliance signals AND phase is NOT review → generic reviewer only, but still record gate result in status.md (`gate: {type: fast-pass, result: approved}`)
2. **Run full gate** (when fast-pass does NOT apply): `/wicked-garden:crew:gate phases/{phase}/ --gate {gate_type}`
3. **Handle outcome**:
   - **APPROVE**: Proceed to sign-off
   - **CONDITIONAL**: Apply AC-4.4 auto-resolution (see below)
   - **REJECT**: **STOP**. Report to user. Do NOT auto-proceed past a rejected gate.

#### AC-4.4 CONDITIONAL Gate Auto-Resolution (just-finish mode)

When a gate returns CONDITIONAL, classify each condition:

**Auto-resolvable**: spec gap, arithmetic error, missing definition, or mechanical fix that does NOT change acceptance criteria or project intent. For each auto-resolvable condition:
- Make the fix inline
- Document in `phases/{phase}/conditions-manifest.json` with `"auto_resolved": true` and the resolution
- Re-run the gate after all auto-resolvable conditions are fixed

**Escalate to council**: condition requires changing acceptance criteria, altering the definition of done, shifting architectural approach, or making a tradeoff that affects project intent. For each escalate condition:
```
Skill(skill="wicked-garden:jam:council",
      args="Gate condition requires intent decision: {condition}. Options: A) Resolve as proposed B) Reject resolution, keep current spec C) Defer")
```

**Classification rule**: "Does resolving this change what we're building or how we measure success?" If uncertain — escalate (err on the side of caution).

Log all conditions and resolutions in status.md before proceeding to sign-off.

**Testing enforcement**: Before executing phases, verify that `phase_plan` includes test-strategy and test if complexity >= 2. If they're missing from the plan but complexity warrants them, inject them before proceeding (same injection rules as execute.md Section 4.5).

#### Phase Documentation Requirements

**Every phase MUST produce a `phases/{phase}/status.md`** — no exceptions:

- **Executed phases**: Update status.md with deliverables, task stats, and outcome summary
- **Skipped phases**: Use phase_manager `skip` action which auto-creates status.md with skip reason and approver
- **Review phase is NEVER skippable**: Even for simple/tactical work, always run at least a basic review

If skipping a skippable phase, always use phase_manager which documents the skip:
```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {project} skip --phase {phase} --reason "{specific reason}" --approved-by "just-finish"
```

**Testing is mandatory.** The test phase is non-skippable (`is_skippable: false` in phases.json). Do not skip it, do not suggest manual verification as a replacement, do not claim visual-only changes don't need testing. UI changes require JS error checking and feature verification. API changes require direct endpoint testing. Both require positive and negative scenarios. The only valid skip reasons are `user_explicit_request` and `ci_equivalent_exists`.

### 6. Progress Reporting

Provide periodic updates:

```markdown
## Progress Update

**Phase**: {current}
**Status**: {what's happening}

### Completed
- {Item}

### In Progress
- {Item}

### Upcoming
- {Item}
```

### 7. Completion

When all phases complete:

```markdown
## Project Complete

**Project**: {name}
**Duration**: {time from start to finish}

### Summary

{What was accomplished}

### Artifacts Created

- {List of files/deliverables}

### Assumptions Made

{List every assumption made during autonomous execution, organized by phase}

- **Clarify**: {assumptions about requirements, scope, priorities}
- **Build**: {assumptions about approach, trade-offs, defaults}
- **Review**: {assumptions about acceptance criteria}

### Recommendations

- {Any follow-up suggestions}
```

### 7.5 Learning Capture (AC-4.6)

**At every gate that returns CONDITIONAL or REJECT**, store the learning:

```
Skill(skill="wicked-brain:memory", args={"content": "Crew learning: {what went wrong and why}", "type": "procedural", "tags": "crew,learning", "importance": "medium"})
```

**At project completion (review phase approved)**, store:

1. **User preferences observed** (if any new patterns noticed):
   ```
   Skill(skill="wicked-brain:memory", args={"content": "{preference observed}", "type": "preference", "tags": "crew,user-preference", "importance": "medium"})
   ```

2. **What worked well** (reusable patterns):
   ```
   Skill(skill="wicked-brain:memory", args={"content": "Crew pattern: {what worked and why}", "type": "procedural", "tags": "crew,pattern,success", "importance": "medium"})
   ```

3. **What to avoid** (anti-patterns discovered):
   ```
   Skill(skill="wicked-brain:memory", args={"content": "Crew anti-pattern: {what failed and why}", "type": "procedural", "tags": "crew,anti-pattern", "importance": "high"})
   ```

These are GENERAL learnings, not project-specific. They inform future projects.

### 8. Error Handling

If blocked or encountering errors:
- Stop autonomous execution
- Report the issue clearly
- Ask for guidance
- Don't attempt workarounds that might cause damage
