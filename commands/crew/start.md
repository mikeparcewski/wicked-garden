---
description: Start a new wicked-crew project with outcome clarification
argument-hint: "<project description>"
---

# /wicked-garden:crew:start

Create a new project and begin the clarify phase.

## Router (v6 facilitator vs legacy rule engine)

**Read the `WG_FACILITATOR` env var** (default: `new` on the `feat/v6-rebuild` branch).

```bash
# Detect the routing mode — defaults to "new" on this branch.
WG_FACILITATOR="${WG_FACILITATOR:-new}"
echo "[crew:start] router mode: ${WG_FACILITATOR}"
```

- **`WG_FACILITATOR=new`** (default): run the **Facilitator Path** (Section A below). The
  `wicked-garden:crew:propose-process` skill produces the full task chain + process-plan.md.
- **`WG_FACILITATOR=legacy`**: run the **Legacy Rule Engine Path** (Section B below,
  starting at "Parse Arguments"). Same behavior as before Gate 3.

**Fail-open**: if the facilitator path errors (skill invocation fails, JSON parse fails,
plan write fails), emit a single stderr warning of the form
`[crew:start] facilitator failed: <reason> — falling back to legacy` and continue with
Section B. Do NOT silently swallow; the operator needs to know.

---

## Section A — Facilitator Path (WG_FACILITATOR=new)

### A.1 Parse Arguments

Extract the project description from `$ARGUMENTS`. If empty, ask the user for one and
STOP. Do not proceed with an empty description.

**v6 flags (orthogonal axes):**

| Flag | Axis | Effect |
|---|---|---|
| `--yolo` / `--just-finish` | interaction mode | Run to completion without user confirmations; auto-approve APPROVE gates; escalate only on REJECT or intent-changing CONDITIONAL. Does **not** change phase plan, rigor, or specialists — the facilitator already chose those. |
| `--rigor={minimal\|standard\|full}` | override | Override the facilitator's rigor tier (rarely needed). Sanity check: facilitator's selection is usually right. |
| `--force` | override | Suppress complexity-based stop prompts (e.g. low-complexity → single-task recommendation). |
| `--consensus-threshold=N` | gate policy | Pass through to gates as in legacy. |

**Removed from v6** (were v5 conflations):
- `--quick` — was shorthand for "minimal rigor AND yolo mode." These are now orthogonal.
  Use `--rigor=minimal` for fewer phases, `--yolo` for no user prompts, or both.
- `--no-auto-finish` — no longer needed. Yolo is opt-IN via `--yolo`, not opt-OUT.

The facilitator decides phase plan + specialists + rigor tier from the work itself.
Flags only adjust interaction mode or override downstream gate behavior.

### A.2 Generate Project Slug

Use the same three-stage theme-aware slug algorithm as legacy (theme prefix + key
concepts + assembly), truncated to 64 characters on a word boundary. The slug feeds
into `chain_id` as `{slug}.root`.

### A.3 Check for Existing Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

Same four-option prompt as legacy (Resume / Rename / Cancel / Switch). Identical
semantics — see Section B.3 for details.

### A.4 Create Project Shell

Create the project via `phase_manager` so the DomainStore record and project dir exist
before the facilitator writes `process-plan.md`:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {slug} create \
  --description "{description}" \
  --json
```

Parse the JSON response for `project_dir`. This path is where `process-plan.md` will
land in step A.7.

### A.5 Invoke the Facilitator Skill

Invoke the new `wicked-garden:crew:propose-process` skill with the description. The
skill is a rubric (Tier-1/2/3 progressive disclosure) that reasons over the 9 factors
and emits a full plan.

```
Skill(
  skill="wicked-garden:crew:propose-process",
  args={
    "description": "{description}",
    "mode": "propose",
    "project_slug": "{slug}",
    "output": "json"
  }
)
```

The skill returns a single JSON object matching
`skills/crew/propose-process/refs/output-schema.md` — with `project_slug`, `summary`,
`factors`, `specialists`, `phases`, `rigor_tier`, `complexity`, `open_questions`,
`tasks[]`. Each task carries full metadata (chain_id, event_type, source_agent:
"facilitator", phase, test_required, test_types, evidence_required, rigor_tier).

**Failure modes (fail-open)**:

- Skill not available → log warning, fall back to Section B.
- Skill returns non-JSON or invalid JSON → log warning with first 200 chars of output,
  fall back to Section B.
- Required fields missing (`tasks`, `phases`, `rigor_tier`) → log warning, fall back to
  Section B.

### A.6 Open Questions Gate

If `open_questions` is non-empty AND `rigor_tier == "full"` AND `--force` was NOT passed:
STOP and surface the questions to the user as a numbered plain-text list. Do NOT create
tasks yet. Store the facilitator's draft plan to `${project_dir}/process-plan.draft.md`
for resumption. The user's answers feed a follow-up invocation with
`mode: "propose"` + their answers appended to the description.

For `standard` or `minimal` rigor, questions are surfaced but do NOT block task creation
— they're included in `process-plan.md` for the clarify phase to answer.

### A.7 Persist `process-plan.md`

Render the returned JSON into the Markdown template at
`skills/crew/propose-process/refs/plan-template.md`. Write to
`${project_dir}/process-plan.md` using the Write tool.

Also persist the raw JSON alongside for audit at
`${project_dir}/process-plan.json` so re-evaluation runs can diff cleanly.

### A.8 Emit the Task Chain

For each task in the JSON's `tasks[]` array, issue one `TaskCreate` call:

```
TaskCreate(
  subject="<task.title>",
  description="<optional longer description if present>",
  blockedBy=<task.blockedBy>,
  metadata={
    "chain_id": "<task.metadata.chain_id>",     # e.g. "{slug}.root"
    "event_type": "<task.metadata.event_type>", # "task" | "coding-task" | ...
    "source_agent": "facilitator",              # always
    "phase": "<task.metadata.phase>",
    "test_required": <bool>,
    "test_types": [...],
    "evidence_required": [...],
    "rigor_tier": "<minimal|standard|full>"
  }
)
```

Use **parallel TaskCreate calls** when the chain has multiple tasks with no
inter-dependencies within a phase. `blockedBy` captures the DAG, so downstream
tasks wait on upstream ones regardless of creation order.

### A.9 Persist Plan Metadata on Project

Store the facilitator-derived fields on the crew project record so `status` /
`execute` / downstream commands can read them without re-invoking the skill:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {slug} update \
  --data '{"phase_plan": ["clarify","design","build","test","review"], "phase_plan_mode": "facilitator", "complexity_score": <N>, "rigor_tier": "<tier>", "facilitator_version": "propose-process-v1", "initiative": "{slug}"}' \
  --json
```

### A.10 Store Decision in wicked-brain

Record the planning decision as a memory so future runs can surface it as a prior:

```
Skill(
  skill="wicked-brain:memory",
  args={"action": "store", "type": "decision",
        "title": "crew:start facilitator plan for {slug}",
        "content": "<summary from JSON + factor readings + rigor_tier + specialist list>",
        "tags": ["crew", "facilitator", "process-plan", "{slug}"],
        "importance": 6}
)
```

Fail-open: if the brain is unavailable, skip silently. The plan file is the system
of record; brain storage is an enhancement.

### A.11 Report to User

Summarize the facilitator's decision in a short markdown report:

```markdown
## Project Created: {slug}

**Rigor**: {standard | minimal | full} — {rigor_why}
**Complexity**: {N}/7 — {complexity_why}

### Factors (facilitator reading)
- Reversibility: {LOW/MED/HIGH} — {why}
- Blast radius: {LOW/MED/HIGH} — {why}
- ... (rest of 9 factors)

### Specialists
{bulleted list with one-sentence why per pick}

### Phases
{ordered list of phases with one-sentence why}

### Task chain
{count} tasks created. See `process-plan.md` for the full table.

### Next step
Run `/wicked-garden:crew:execute` to begin the first phase (`{first_phase}`).
```

Then exit. Do NOT fall through to Section B.

---

## Section B — Legacy Rule Engine Path (WG_FACILITATOR=legacy)

The sections below are the pre-Gate-3 behavior, preserved verbatim as the rollback
escape hatch. Enter this section only when `WG_FACILITATOR=legacy` OR when Section A
falls back.

## Instructions

### 1. Parse Arguments

Extract the project description from arguments. If no description provided, ask for one.

**Flags**:
- `--force` — Skip the pre-flight complexity gate entirely. Use when you know crew is the right tool.
- `--quick` — Use a lightweight phase plan: build + review only. Skips clarify, design, test-strategy, and test phases. Useful for well-understood, low-risk changes.
- `--no-auto-finish` — Disable automatic just-finish execution for low-complexity changes (routing_lane "auto" or "fast"). Without this flag, complexity <= 2 automatically applies the quick phase plan and chains into just-finish mode.
- `--consensus-threshold=N` — Override the per-phase consensus threshold (default: 5). Gate decisions for phases with `consensus_threshold` configured will use multi-perspective consensus when project complexity >= N. Set to 0 to always use consensus, or 8 to disable. Stored in project extras for the lifetime of the project.

### 2. Generate Project Name

Use a three-stage theme-aware slug algorithm:

**Stage 1: Detect theme prefix** — scan the description (case-insensitive) for the first matching signal group:

| Signal Keywords | Theme Prefix |
|-----------------|--------------|
| "issue", "gh-", "github issue", `#\d+` | `issue` |
| "bug", "fix", "broken", "regression", "crash" | `fix` |
| "refactor", "cleanup", "clean up", "reorganize" | `refactor` |
| "docs", "documentation", "readme", "changelog" | `docs` |
| "feature", "feat", "add", "implement", "new", "introduce" | `feat` |
| (no match) | (no prefix — fall through to Stage 3 fallback) |

**Stage 2: Extract key concepts** — from the description, remove the matched theme keywords and stop words ("the", "a", "an", "for", "to", "of", "in", "and", "with"), then take the first 3–4 remaining meaningful nouns or phrases and kebab-case each one.

**Stage 3: Assemble** — join as `{theme-prefix}-{concept1}-{concept2}-{concept3}`. Truncate at 64 characters on a word boundary (never split mid-word). If no theme prefix was matched in Stage 1, fall back to the plain kebab-case behavior: lowercase the full description, replace spaces with hyphens, strip special characters, truncate at 64 characters.

**Examples**:

| Description | Generated Name |
|-------------|----------------|
| "Resolve GitHub issues #252, #258, and smart naming" | `issue-resolve-252-258-smart-naming` |
| "Fix broken auth token refresh on mobile" | `fix-auth-token-refresh-mobile` |
| "Add parallel worktree build support to crew" | `feat-parallel-worktree-build-crew` |

### 3. Check for Existing Project

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/crew.py find-active --json
```

Parse the JSON result. If an active project exists, ask user to choose one of four options:

1. **Resume** — continue working on the existing project (abort new project creation)
2. **Rename** — rename the new project to avoid conflict, then proceed with creation
3. **Cancel** — abort entirely
4. **Switch** — pause the current project and create the new one

If the user chooses **Switch**:
1. Set `paused: true` on the existing project via phase_manager so it no longer appears as active:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {existing-project} update \
     --data '{"paused": true}' \
     --json
   ```
2. The old project's state remains intact (not archived, not deleted) and can be resumed later by setting `paused: false`
3. Proceed to Step 4 to create the new project

### 4. Create Project

Create the project via phase_manager (persists via DomainStore — local JSON):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} create \
  --description "{description}" \
  --json
```

This creates the DomainStore record, initializes the clarify phase, and sets up local deliverable templates (project.md, outcome.md, phases/clarify/status.md) in one operation.

Parse the JSON response to get `project_dir` for later use.

### 4.5 Recall Prior Learnings

```
/wicked-garden:mem:recall "crew learnings and user preferences" --limit 10
```

Include recalled learnings in the project context. They inform signal analysis, phase selection, and specialist routing.

### 5. Dynamic Archetype Pre-Analysis

**Before running signal analysis, dynamically detect what TYPE of project this is.** Quality means different things for different projects — a content site needs messaging consistency, a UI app needs design coherence, infrastructure needs reliability, ML needs evaluation rigor.

1. **Read project descriptor files** in the working directory (any that exist):
   - `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `agent.md`, `README.md` (load `AGENTS.md` first for general agent context, then `CLAUDE.md` for Claude-specific overrides)
   - `package.json`, `pyproject.toml`, `Cargo.toml` for tech stack
   - `.claude-plugin/plugin.json` if it's a plugin project

2. **Query memories** (if wicked-garden:mem available):
   ```
   /wicked-garden:mem:recall "project type and quality dimensions for this codebase" --limit 5
   /wicked-garden:mem:recall --tags onboarding --limit 10
   ```
   Onboarding memories contain foundational knowledge: tech stack, architecture pattern,
   entry points, key flows, and quality signals. Use these to inform archetype detection.

3. **Analyze codebase structure** :
   - `/wicked-garden:search:scout` for pattern detection (component library? API routes? data pipelines? content templates?)

4. **Explore codebase for affected files** (pre-analysis for smart decisioning):

   Dispatch an Explore subagent to identify files that would be affected based on the project description. This populates `--files` for impact scoring in step 5.5.

   ```
   Task(
     subagent_type="wicked-garden:search:code",
     prompt="Based on this project description, identify file paths in the codebase that would likely be affected or are most relevant. Use Glob and Grep to find relevant files by examining the directory structure, key source files, and any modules or components related to: {description}. Return a plain comma-separated list of up to 20 relative file paths, nothing else."
   )
   ```

   **Timeout**: If the exploration subagent does not return results within 15 seconds or returns an error, skip file hints entirely — set `FILE_HINTS_CSV` to an empty string and proceed without `--files`. File hints are an enhancement, not a blocker.

   Capture the result as `FILE_HINTS_CSV` (the comma-separated file paths returned by the subagent). If the result is empty or the subagent was skipped, `FILE_HINTS_CSV` remains empty.

5. **Build archetype hints** as JSON — define what quality dimensions matter for this project:
   ```json
   {
     "archetype-name": {
       "confidence": 0.8,
       "impact_bonus": 2,
       "inject_signals": {"architecture": 0.3},
       "min_complexity": 3,
       "description": "Why this archetype matters for quality"
     }
   }
   ```
   You can use built-in archetypes (content-heavy, ui-heavy, api-backend, infrastructure-framework, data-pipeline, mobile-app, ml-ai, compliance-regulated, monorepo-platform, real-time) OR define new ones dynamically.

6. **Store archetype hints** via phase_manager update as `archetype_hints` for reuse at checkpoints (do NOT write project.json directly — use the update command in step 5.5).

### 5.4 Agent Dimension Scoring

Dispatch an agent to semantically score risk dimensions that keyword matching misses. The agent understands context that regex cannot — e.g., "eliminate the control plane" implies high reversibility risk even though it doesn't contain the word "migration".

```
Task(
  subagent_type="Explore",
  prompt="Score the risk dimensions (0-3 each) for this project description. Consider the affected files and archetype context provided.

PROJECT: {description}

AFFECTED FILES: {FILE_HINTS_CSV}

ARCHETYPE: {primary archetype and description}

Score each dimension 0-3:
- impact: How much production behavior changes? Consider that in AI-native projects, prompts, commands, skills, and agent definitions (.md files in commands/, skills/, agents/) are behavioral programs — changing them is as impactful as changing source code. Also consider breadth: how many files/domains are touched?
- reversibility: How hard to undo? Removing core abstractions, changing data formats, breaking interfaces = high. Additive changes, feature flags = low.
- novelty: How new/unfamiliar is this pattern? First-time architectural patterns, greenfield approaches = high. Routine bug fixes, well-trodden patterns = low.
- test_complexity: How complex is the test strategy? Cross-domain integration testing, new test infrastructure needed = high. Unit tests for isolated changes = low.
- coordination_cost: How much cross-domain/cross-team coordination? Changes touching many domains that must stay consistent = high. Single-domain changes = low.
- operational: Deployment/migration/rollback complexity? Data migrations, breaking changes requiring coordination = high. Drop-in replacements = low.
- documentation: How much documentation needs updating? API changes, architecture decisions, migration guides = high. Internal refactors = low.

Return ONLY a JSON object like: {\"impact\": 3, \"reversibility\": 2, \"novelty\": 1, \"test_complexity\": 2, \"coordination_cost\": 2, \"operational\": 1, \"documentation\": 1}
No explanation, just the JSON."
)
```

Parse the agent's response as JSON. If it fails to parse or the agent errors, set `DIMENSION_HINTS_JSON` to empty and proceed without dimension hints — this is an enhancement, not a blocker.

Capture the valid JSON as `DIMENSION_HINTS_JSON`.

### 5.5 Analyze Input with Smart Decisioning

Run smart decisioning with archetype hints, file impact scoring, and agent dimension hints.

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/smart_decisioning.py --json \
  --archetype-hints '${ARCHETYPE_HINTS_JSON}' \
  ${FILE_HINTS_CSV:+--files "${FILE_HINTS_CSV}"} \
  ${DIMENSION_HINTS_JSON:+--dimension-hints '${DIMENSION_HINTS_JSON}'} \
  "{description}"
```

This returns:
- **signals**: Detected signal types (security, performance, product, etc.)
- **complexity**: Score 0-7, adjusted by archetype (impact bonus, min complexity floor)
- **archetypes**: Detected project archetypes with confidence scores
- **recommended_specialists**: Which plugins would help
- **memory_payload**: (if significant) A payload for the caller to store via `/wicked-garden:mem:store`

**If `memory_payload` is present** in the JSON output, store it using Claude's native tool system:
```
/wicked-garden:mem:store "{memory_payload.content}" --type {memory_payload.type} --tags "{memory_payload.tags}" --importance {memory_payload.importance}
```
Scripts never call other plugins directly — Claude's tool system is the universal API.

Store analysis via phase_manager update (persists via DomainStore):

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"signals_detected": ["security", "data"], "complexity_score": 4, "specialists_recommended": ["qe", "product"], "archetype_hints": {}}' \
  --json
```

**If `--consensus-threshold=N` was passed**: Store the override in project extras so it applies to all gate decisions for this project:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"extras": {"consensus_threshold": N}}' \
  --json
```

### 5.6 Pre-Flight Complexity Gate

After smart decisioning completes, read the `routing_lane` field from the JSON output (added in #201). If the field is absent, default to `"standard"` and skip the gate.

**Store `preflight_lane` in project state** regardless of which branch is taken:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"preflight_lane": "{routing_lane}"}' \
  --json
```

**If `--force` flag was passed**: skip the rest of this step and proceed directly to Step 6.

**If `--quick` flag was passed**: skip the rest of this step, proceed directly to Step 6, and override the phase plan in Step 7 (see below).

**If (`routing_lane == "auto"` OR `routing_lane == "fast"`) AND `--no-auto-finish` was NOT passed AND `--force` was NOT passed**:

This request has low complexity (score <= 2). Automatically apply the quick phase plan and chain into just-finish execution — no user prompt required.

Set an internal flag `AUTO_FINISH=true` to be used in Step 9.

The `--quick` phase plan will be applied in Step 7 (build + review only).

Then proceed to Step 6 normally. Do NOT ask the user for confirmation.

**If `routing_lane == "auto"` AND `--no-auto-finish` WAS passed AND `--force` was NOT passed**:

This request has low complexity (score 0-1 out of 7). Crew may be heavier than needed. Present a choice to the user.

**In normal mode** — use `AskUserQuestion`:

```
AskUserQuestion(
  question="This request has low complexity (score: {complexity_score}/7). Crew may be heavier than needed.\n\nRecommended approach: use native TaskCreate + direct tools instead.\n\nOptions:\n1. Continue with crew anyway\n2. Switch to a single task (TaskCreate and proceed without crew phases)\n3. Cancel\n\n(Pass --force to bypass this check next time)",
  options=["1", "2", "3"]
)
```

**In dangerous mode** (when session briefing contains `[Question Mode] Dangerous mode is active`):

Do NOT use `AskUserQuestion`. Present as plain text and STOP — wait for the user to reply before continuing:

```
This request has low complexity (score: {complexity_score}/7). Crew may be heavier than needed.

Recommended approach: use native TaskCreate + direct tools instead.

Options:
1. Continue with crew anyway
2. Switch to a single task (TaskCreate and proceed without crew phases)
3. Cancel

(Pass --force to bypass this check next time)

Please reply with 1, 2, or 3.
```

Do NOT proceed until the user replies with their selection.

**Handling the selection**:

- **Option 1 (Continue with crew)**: Proceed to Step 6 normally.
- **Option 2 (Switch to a single task)**: Invoke `TaskCreate(subject="{description}", metadata={"event_type":"task","chain_id":"{project-slug}.root","source_agent":"crew:start"})` and exit. Do not continue the crew setup.
- **Option 3 (Cancel)**: Inform the user the operation was cancelled and exit.

**If `routing_lane == "fast"` AND `--no-auto-finish` WAS passed AND `--quick` was NOT passed AND `--force` was NOT passed**:

Suggest `--quick` as a lighter option, but do not block:

```
Note: This request has moderate complexity (score: {complexity_score}/7). Consider using --quick for a
lightweight build+review-only run. Continuing with full crew phase plan.
```

Then proceed to Step 6 normally.

### 6. Discover Available Specialists

Run specialist discovery:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/specialist_discovery.py --json
```

This returns available specialist plugins and their roles:
- **jam**: ideation (clarify phase)
- **qe**: quality-engineering (all phases)
- **product**: business-strategy (design, review)
- **delivery**: project-management (reporting)
- **platform**: devsecops (build phase)

### 7. Select Phase Plan

**If `--quick` flag was passed OR `AUTO_FINISH` is true**: Skip all phase selection logic below. Use a static phase plan of `["build", "review"]` only:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"phase_plan": ["build", "review"], "phase_plan_mode": "static"}' \
  --json
```

Then proceed directly to Step 8. Do not read phases.json or run signal-based phase selection.

**Otherwise** (no `--quick` flag): Run the full phase selection:

Read `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/phases.json` to see all available phases with their triggers, complexity ranges, and skip rules.

Select which phases to include based on the signal analysis and complexity score:

1. **Always include** phases where `is_skippable` is `false` (e.g., clarify, build, review)
2. **Include test-strategy by default** if `complexity_score` >= 2 (testing should be the norm, not the exception)
3. **Include test by default** if `complexity_score` >= 2 OR any code-modifying signals detected
4. **Include if signals match**: For each remaining skippable phase, include it if any of its `triggers` appear in `signals_detected`
5. **Include if complexity warrants**: Include if `complexity_score` falls within the phase's `complexity_range`
6. **Consider specialist availability**: Prefer phases where a matching specialist is installed

Order the selected phases by their `depends_on` relationships.

Store the ordered phase list and planning mode via phase_manager:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"phase_plan": ["clarify", "test-strategy", "build", "test", "review"], "phase_plan_mode": "dynamic"}' \
  --json
```

**Dynamic mode** (default): Phase plan can be adjusted at checkpoints via signal re-analysis (see execute.md Section 4.5). Set `"phase_plan_mode": "static"` to lock the plan.

**Legacy alias**: The old `qe` phase name maps to `test-strategy` in phases.json. Both names work.

### 8. Task Lifecycle Initialization

Initialize task tracking metadata via phase_manager:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
  --data '{"task_lifecycle": {"staleness_threshold_minutes": 30, "recovery_mode": "auto", "user_overrides": {}}}' \
  --json
```

### 8.5 Initiative Setup

Every crew project should record an initiative name so tasks created during the project can be grouped under it in native task views.

**Goal**: store the initiative *name* on the crew project record so session_start can recover it without a round-trip.

1. **Store initiative name** via phase_manager:
   ```bash
   sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" scripts/crew/phase_manager.py {name} update \
     --data '{"initiative": "{project-name}"}' \
     --json
   ```

2. **All crew tasks must include initiative metadata**:
   ```
   metadata: {"event_type": "task", "chain_id": "{project-name}.root", "source_agent": "crew:execute", "initiative": "{project-name}"}
   ```
   The PreToolUse hook (`pretool_taskcreate.py`) injects `initiative` automatically when an active crew project is detected, so explicit metadata is not required in every TaskCreate call — but including it is safe.

This ensures crew project tasks render grouped under their project initiative, while general fixes/bugs fall under the default "Issues" initiative.

### 9. Report to User

Show:
- Project created
- Current phase (clarify, or build when `AUTO_FINISH` is true)
- **Signal analysis** (what complexity was detected)
- **Recommended specialists** (which plugins will help)
- **Available specialists** (what's actually installed)
- **Auto-finish notice** (when `AUTO_FINISH` is true)
- Next step: run `/wicked-garden:crew:execute` to begin clarifying (omit when `AUTO_FINISH` is true — just-finish runs automatically)

Example output (standard):
```markdown
## Project Created: {name}

**Current Phase**: clarify

### Signal Analysis
- **Complexity**: Medium (4/7)
- **Signals**: security, performance, data
- **Clarity**: Needs clarification

### Specialist Recommendations
| Specialist | Role | Status |
|------------|------|--------|
| jam | ideation | ✅ Available |
| qe | quality | ✅ Available |
| product | review | ❌ Not installed |

### Task Lifecycle
- Staleness detection: 30 minutes
- Recovery mode: automatic
- Override mechanism: available via phase_manager update

### Next Step
Run `/wicked-garden:crew:execute` to begin the clarify phase.
```

Example output (auto-finish — complexity <= 2):
```markdown
## Project Created: {name}

**Current Phase**: build

### Signal Analysis
- **Complexity**: Low ({complexity_score}/7)
- **Signals**: {signals}

### Specialist Recommendations
| Specialist | Role | Status |
|------------|------|--------|
| qe | quality | ✅ Available |

### Task Lifecycle
- Staleness detection: 30 minutes
- Recovery mode: automatic
- Override mechanism: available via phase_manager update

**Auto-finish**: Complexity <= 2 detected. Running in just-finish mode with quick phase plan (build + review).
To disable: pass `--no-auto-finish` to crew:start.
```

**If `AUTO_FINISH` is true**: after displaying the report above, immediately invoke:

```
Skill(skill="wicked-garden:crew:just-finish")
```

Do not prompt the user to run any command — just-finish executes automatically.
