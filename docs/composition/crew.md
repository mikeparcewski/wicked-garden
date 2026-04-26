# crew composition map

Multi-phase SDLC workflow with specialist routing, gate enforcement, and convergence tracking.

## Surface inventory

| Type | Name | One-line purpose |
|---|---|---|
| command | /wicked-garden:crew:activity | Query the unified event log for cross-domain activity (FTS over SQLite) |
| command | /wicked-garden:crew:approve | Approve a phase and advance to next stage |
| command | /wicked-garden:crew:archive | Archive a completed project (remove from active listings) |
| command | /wicked-garden:crew:auto-approve | Grant or revoke APPROVE-verdict fast-lane for a project |
| command | /wicked-garden:crew:convergence | Show artifact convergence states, stalls, and gate verdict |
| command | /wicked-garden:crew:evidence | Show evidence summary for a task or project |
| command | /wicked-garden:crew:execute | Execute current phase work with adaptive role engagement |
| command | /wicked-garden:crew:explain | Translate jargon-heavy crew output into plain English |
| command | /wicked-garden:crew:feedback | Capture user/stakeholder feedback linked to a crew project |
| command | /wicked-garden:crew:gate | Run QE analysis on a target with configurable rigor |
| command | /wicked-garden:crew:incident | Log a production incident with traceability to a project |
| command | /wicked-garden:crew:just-finish | Execute remaining work with maximum autonomy and guardrails |
| command | /wicked-garden:crew:operate | Enter and manage the operate phase |
| command | /wicked-garden:crew:profile | Adjust autonomy level, verbosity, or plan mode |
| command | /wicked-garden:crew:retro | Generate a retrospective from operate-phase data |
| command | /wicked-garden:crew:start | Start a new project with outcome clarification |
| command | /wicked-garden:crew:status | Show current project status, phase, and next steps |
| command | /wicked-garden:crew:swarm | Check for quality-crisis swarm trigger and recommend coalition |
| agent | wicked-garden:crew:contrarian | Maintains minority challenge position at complexity >= 4 |
| agent | wicked-garden:crew:facilitator | Guides outcome clarification through structured inquiry |
| agent | wicked-garden:crew:gate-adjudicator | Archetype-aware phase-boundary evidence evaluator |
| agent | wicked-garden:crew:gate-evaluator | Fast-path self-check and advisory gate evaluator |
| agent | wicked-garden:crew:implementer | Executes implementation tasks per approved designs |
| agent | wicked-garden:crew:independent-reviewer | Cold-context phase deliverable auditor |
| agent | wicked-garden:crew:phase-executor | Produces phase deliverables for full-rigor (mode-3) projects |
| agent | wicked-garden:crew:qe-orchestrator | Routes to appropriate quality gate and consolidates results |
| agent | wicked-garden:crew:researcher | Explores codebase and gathers context for decisions |
| agent | wicked-garden:crew:reviewer | General code review when no domain specialist is available |
| skill | wicked-garden:crew:adaptive | Autonomy and communication style configuration |
| skill | wicked-garden:crew:change-type-detector | Classifies file paths as ui/api/both/unknown |
| skill | wicked-garden:crew:crew-qe-gate | Value/strategy/execution quality gates at phase transitions |
| skill | wicked-garden:crew:evidence-validation | Validates task completion evidence against complexity tier |
| skill | wicked-garden:crew:explain | Plain-language translation of gate findings and phase summaries |
| skill | wicked-garden:crew:issue-reporting | Automated GitHub issue detection and filing |
| skill | wicked-garden:crew:test-task-factory | Generates test TaskCreate params from change-type output |

## Workflow patterns

### 1. Standard project lifecycle
User wants to ship a feature through the full crew workflow.

```
/crew:start "<description>"          # facilitator → clarify → rubric → propose-process
→ /crew:execute                      # phase-executor / implementer per phase
→ /crew:gate [--rigor standard]      # qe-orchestrator → gate-adjudicator
→ /crew:approve <phase>              # advance on APPROVE
→ /crew:operate                      # post-ship monitoring
→ /crew:retro                        # retrospective from operate data
```

Gate advancement requires score >= `min_gate_score` from `phases.json`. REJECT blocks; CONDITIONAL requires conditions-manifest resolution.

### 2. Mid-flight status check
User wants to know where the project stands.

```
/crew:status                         # phase, next steps, blocking findings
→ /crew:evidence [task-id]           # inspect evidence for a specific task
→ /crew:convergence status           # check artifact lifecycle states
```

### 3. Gate bypass / fast-lane
User has justification to skip normal gate cadence (minimal-rigor projects).

```
/crew:auto-approve <project> --approve --justification "<text>"
```

Full-rigor grants require justification + sentinel. Cooldown blocks re-grant after revoke. See yolo guardrails in `commands/crew/auto-approve.md` and the project README.

### 4. Jargon translation
Non-specialist user encounters a gate finding or reviewer brief.

```
/crew:explain "<text-or-path>"
```

Delegates to the `explain` skill. Outputs grade-8 English, no specialist vocab.

### 5. Quality crisis response
3+ BLOCK/REJECT findings have accumulated.

```
/crew:swarm                          # detect trigger, recommend Quality Coalition
→ /crew:gate --rigor standard        # rerun with full panel
```

`swarm_trigger.py` monitors for the swarm condition. Coalition composition is determined at runtime from agents frontmatter.

### 6. Production incident with crew traceability

```
/crew:incident "<description>" --severity high --components api,auth
```

Links incident to the active project's requirements and code. Use `platform:incident` for live triage without a crew project.

## When to add a new surface

- **New command** — when a user-facing lifecycle action is missing (a phase the user can trigger, a state they need to inspect). Do not add commands that wrap single script calls — expose those through existing commands with flags.
- **New agent** — when a distinct specialist role is needed that is not covered by existing agents. Agents map to roles (facilitator, implementer, reviewer, gate evaluator); add when the role's decision logic is meaningfully different from all existing agents. Do not add agents for rigor-tier variations — those are handled by `gate-policy.json` dispatch.
- **New skill** — when reusable logic is needed across multiple agents/commands and is too large for inline inclusion. Skills in this domain are mostly utilities (change-type-detector, test-task-factory) — add when a utility pattern recurs 2+ times.

## Cross-domain dependencies

```
crew
  calls →  jam:council              (challenge phase, complexity >= 4)
  calls →  engineering, wicked-testing, etc.    (specialist gate reviewers via gate-policy.json)
  calls →  wicked-brain:memory      (cross-session learning at completion + gate failures)

smaht
  reads ←  crew task events         (chain-aware scoring in events adapter)
  reads ←  active_chain_id          (0.8+ score for matching events)

platform
  calls ←  crew:incident            (escalation from live incident triage)

propose-process (skill, root)
  called by → crew:start            (facilitator rubric → phase plan)
```

## Anti-patterns

- **Calling `crew:approve` without gate evidence.** `approve` advances phase state; it does not evaluate evidence. Run `crew:gate` first and resolve findings before approving.
- **Using `crew:just-finish` as the default mode.** `just-finish` is a guardrailed override for situations where autonomy is explicitly wanted. Default to `crew:execute` which respects `crew:profile` settings.
- **Adding a static `enhances` map between agents.** v6 removed the static enhances map. Specialist discovery is dynamic — `propose-process` reads agents frontmatter at runtime. Keep agent descriptions accurate; the facilitator rubric does the routing.
- **Hardcoding phase names in new code.** Phase names are keys in `.claude-plugin/phases.json`. Reference them from there; do not duplicate them in scripts or agents.
