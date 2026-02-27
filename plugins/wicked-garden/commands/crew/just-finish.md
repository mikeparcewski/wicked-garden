---
description: Execute remaining work with maximum autonomy and guardrails
---

# /wicked-garden:crew-just-finish

Continue project with maximum autonomy, respecting safety guardrails.

## Instructions

### 1. Load Project State

Read `project.json` to understand:
- Current phase
- Remaining phases
- What's been completed
- **signals_detected**: Complexity profile
- **complexity_score**: 0-7 scale
- **specialists_recommended**: Which specialists to auto-engage

### 2. Discover Available Specialists

Run specialist discovery:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/specialist_discovery.py" --json
```

Match available specialists to project signals for auto-engagement.

### 2.5 Gather Context via wicked-smaht (if available)

Before starting phase work, assemble structured context from the ecosystem. This ensures specialists and fallback agents receive rich context — not just raw deliverable text.

```bash
# Discover wicked-smaht (graceful degradation if not installed)
SMAHT_PLUGIN_ROOT=$(find ~/.claude/plugins/cache/wicked-garden/wicked-smaht -maxdepth 1 -type d 2>/dev/null | sort -V | tail -1)

if [ -n "$SMAHT_PLUGIN_ROOT" ]; then
  # Build context package for current phase
  cd "${SMAHT_PLUGIN_ROOT}" && uv run python scripts/context_package.py build \
    --task "Execute {current_phase} phase for {project-name}" \
    --project "{project-name}" \
    --dispatch --prompt
fi
```

Include the context package output in ALL subagent Task() dispatches. If wicked-smaht is not available, proceed with project.json signals and deliverable text only.

### 2.6 Orchestrator-Only Principle

**CRITICAL: The main agent is an ORCHESTRATOR only.** It must NOT perform complex analysis, implementation, or review work inline. Instead:

- **ALL processing** goes through subagent `Task()` dispatches to specialists or fallback agents
- The main agent ONLY: reads project state, makes routing decisions, dispatches subagents, tracks task lifecycle, and reports progress
- Manage context through tools (TaskList, TaskGet, Read) — do NOT accumulate large working state in the main conversation
- When in doubt, delegate to a subagent rather than doing work inline

### 3. Autonomy Mode

In "just-finish" mode:
- Proceed without asking for minor decisions
- Auto-approve routine choices
- **Auto-engage specialists** when signal thresholds are met
- Only pause at guardrails
- **For the clarify phase**: Do NOT ask the user for clarification. Make reasonable assumptions based on the project description and signal analysis. Document all assumptions in the phase deliverables.
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

### 3.5 Dynamic Archetype Pre-Analysis

**Same as execute.md Section 4 — run before starting phase work.**

Before loading signal analysis, dynamically detect project archetypes. Quality means different things for different projects. Use the same approach as execute.md:

1. **Read project descriptor files**: AGENTS.md, CLAUDE.md, README.md, package.json, etc. (load AGENTS.md first for general context, CLAUDE.md overrides)
2. **Query memories**: `/wicked-garden:mem-recall "project type and quality dimensions for {project-name}"`
3. **Analyze codebase**: `/wicked-garden:search-scout` and `/wicked-garden:search-blast-radius` if available
4. **Classify archetypes** and build hints JSON
5. **Pass hints** to smart_decisioning via `--archetype-hints`

In just-finish mode, do this analysis ONCE at the start and cache the archetype hints in project.json for reuse at checkpoints. Do NOT re-run the full discovery at every checkpoint unless signals change significantly.

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

### 4.5 Signal Re-Analysis at Checkpoints

**Same as execute.md Section 4.5 — run after every checkpoint phase completes.**

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` and check if the completed phase has `"checkpoint": true` (clarify, design, build).

When a checkpoint phase completes:

1. Gather phase artifacts from `phases/{phase}/`
2. Re-run signal analysis:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" --json "{summary of deliverables}"
   ```
3. Compare new signals against project.json `signals_detected`
4. If new signals found:
   - Update project.json (signals, complexity, specialists)
   - Check if phases NOT in `phase_plan` should be injected (see execute.md Section 4.5 for injection rules)
   - Report injections to user (even in just-finish mode, injections are informational)
5. Maximum 2 injections per checkpoint

**Skip if**: project.json has `"phase_plan_mode": "static"`.

### 5. Execute Remaining Work

Read project.json `phase_plan` for the ordered list of phases. For each remaining phase:

1. Check if phase is complete or needs work
2. **Auto-engage specialists** based on phase and signals (use dynamic routing from execute.md — signal analysis + specialist.json `enhances` declarations)
3. Execute phase work via specialists or built-in fallbacks
4. **Run mandatory quality gate** (see Section 5.5 below)
5. **Get sign-off** using the priority chain (see execute.md section 8):
   - Priority 1: Third-party CLI (Codex, Gemini, OpenCode)
   - Priority 2: Specialist plugin
   - Priority 3: Generic crew reviewer
   - Priority 4: Human (skip in just-finish unless rejected/conditional)
6. Auto-approve if deliverables meet criteria AND sign-off is `approved`
7. **Run checkpoint re-analysis** if phase has `checkpoint: true` (Section 4.5)
8. Advance to next phase using phase_manager:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_manager.py" {project} approve --phase {phase}
   ```
9. Continue until done or guardrail hit

**Sign-off in just-finish mode**: Always attempt third-party CLI sign-off first. If sign-off returns `rejected`, STOP and report to user. If `conditional`, proceed but log the conditions. Human review is skipped in just-finish mode unless automated sign-off rejects.

### 5.5 Mandatory Quality Gate

**Same as execute.md Section 7.5 — run after deliverables are complete, before sign-off.**

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` for the current phase's `gate_required` and `gate_type`.

If `gate_required` is `true`:

1. **Fast-pass**: complexity <= 1 AND no security/compliance signals AND phase is NOT review → generic reviewer only, but still record gate result in status.md (`gate: {type: fast-pass, result: approved}`)
2. **Run full gate** (when fast-pass does NOT apply): `/wicked-garden:crew-gate phases/{phase}/ --gate {gate_type}`
3. **Handle outcome**:
   - **APPROVE**: Proceed to sign-off
   - **CONDITIONAL**: Log conditions, proceed (in just-finish mode)
   - **REJECT**: **STOP**. Report to user. Do NOT auto-proceed past a rejected gate.

**Testing enforcement**: Before executing phases, verify that `phase_plan` includes test-strategy and test if complexity >= 2. If they're missing from the plan but complexity warrants them, inject them before proceeding (same injection rules as execute.md Section 4.5).

#### Phase Documentation Requirements

**Every phase MUST produce a `phases/{phase}/status.md`** — no exceptions:

- **Executed phases**: Update status.md with deliverables, task stats, and outcome summary
- **Skipped phases**: Use phase_manager `skip` action which auto-creates status.md with skip reason and approver
- **Review phase is NEVER skippable**: Even for simple/tactical work, always run at least a basic review

If skipping a skippable phase, always use phase_manager which documents the skip:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_manager.py" {project} skip --phase {phase} --reason "{specific reason}" --approved-by "just-finish"
```

**Testing default**: test-strategy and test phases should be INCLUDED for all projects with complexity >= 2. Only skip if complexity <= 1 AND the user explicitly requests it OR the fast-pass criteria are met. When in doubt, include testing — it's cheaper to run a lightweight test plan than to ship untested code.

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

### 8. Error Handling

If blocked or encountering errors:
- Stop autonomous execution
- Report the issue clearly
- Ask for guidance
- Don't attempt workarounds that might cause damage
