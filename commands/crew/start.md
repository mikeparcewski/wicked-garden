---
description: Start a new wicked-crew project with outcome clarification
argument-hint: "<project description>"
---

# /wicked-garden:crew:start

Create a new project and begin the clarify phase.

## Instructions

### 1. Parse Arguments

Extract the project description from arguments. If no description provided, ask for one.

**Flags**:
- `--force` — Skip the pre-flight complexity gate entirely. Use when you know crew is the right tool.
- `--quick` — Use a lightweight phase plan: build + review only. Skips clarify, design, test-strategy, and test phases. Useful for well-understood, low-risk changes.

### 2. Generate Project Name

Convert description to kebab-case slug:
- Lowercase
- Replace spaces with hyphens
- Remove special characters
- Max 64 characters

### 3. Check for Existing Project

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/crew.py" find-active --json
```

Parse the JSON result. If an active project exists, ask user to choose one of four options:

1. **Resume** — continue working on the existing project (abort new project creation)
2. **Rename** — rename the new project to avoid conflict, then proceed with creation
3. **Cancel** — abort entirely
4. **Switch** — pause the current project and create the new one

If the user chooses **Switch**:
1. Set `paused: true` on the existing project via phase_manager so it no longer appears as active:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {existing-project} update \
     --data '{"paused": true}' \
     --json
   ```
2. The old project's state remains intact (not archived, not deleted) and can be resumed later by setting `paused: false`
3. Proceed to Step 4 to create the new project

### 4. Create Project

Create the project via phase_manager (persists via StorageManager — CP-first, local fallback):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} create \
  --description "{description}" \
  --json
```

This creates the StorageManager record, initializes the clarify phase, and sets up local deliverable templates (project.md, outcome.md, phases/clarify/status.md) in one operation.

Parse the JSON response to get `project_dir` for later use.

### 5. Dynamic Archetype Pre-Analysis

**Before running signal analysis, dynamically detect what TYPE of project this is.** Quality means different things for different projects — a content site needs messaging consistency, a UI app needs design coherence, infrastructure needs reliability, ML needs evaluation rigor.

1. **Read project descriptor files** in the working directory (any that exist):
   - `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `agent.md`, `README.md` (load `AGENTS.md` first for general agent context, then `CLAUDE.md` for Claude-specific overrides)
   - `package.json`, `pyproject.toml`, `Cargo.toml` for tech stack
   - `.claude-plugin/plugin.json` if it's a plugin project

2. **Query memories** (if wicked-mem available):
   ```
   /wicked-garden:mem:recall "project type and quality dimensions for this codebase" --limit 5
   ```

3. **Analyze codebase structure** (if wicked-search available):
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

### 5.5 Analyze Input with Smart Decisioning

Run smart decisioning with archetype hints and file impact scoring.

**If `FILE_HINTS_CSV` is non-empty** (populated by the exploration subagent in step 5):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  --archetype-hints '${ARCHETYPE_HINTS_JSON}' \
  --files "${FILE_HINTS_CSV}" \
  "{description}"
```

**If `FILE_HINTS_CSV` is empty** (exploration timed out or was skipped):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  --archetype-hints '${ARCHETYPE_HINTS_JSON}' \
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

Store analysis via phase_manager update (persists via StorageManager):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} update \
  --data '{"signals_detected": ["security", "data"], "complexity_score": 4, "specialists_recommended": ["wicked-qe", "wicked-product"], "archetype_hints": {}}' \
  --json
```

### 5.6 Pre-Flight Complexity Gate

After smart decisioning completes, read the `routing_lane` field from the JSON output (added in #201). If the field is absent, default to `"standard"` and skip the gate.

**Store `preflight_lane` in project state** regardless of which branch is taken:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} update \
  --data '{"preflight_lane": "{routing_lane}"}' \
  --json
```

**If `--force` flag was passed**: skip the rest of this step and proceed directly to Step 6.

**If `--quick` flag was passed**: skip the rest of this step, proceed directly to Step 6, and override the phase plan in Step 7 (see below).

**If `routing_lane == "auto"` AND `--force` was NOT passed**:

This request has low complexity (score 0-1 out of 7). Crew may be heavier than needed. Present a choice to the user.

**In normal mode** — use `AskUserQuestion`:

```
AskUserQuestion(
  question="This request has low complexity (score: {complexity_score}/7). Crew may be heavier than needed.\n\nRecommended approach: use kanban + direct tools instead.\n\nOptions:\n1. Continue with crew anyway\n2. Switch to kanban (creates a task and proceeds without crew phases)\n3. Cancel\n\n(Pass --force to bypass this check next time)",
  options=["1", "2", "3"]
)
```

**In dangerous mode** (when session briefing contains `[Question Mode] Dangerous mode is active`):

Do NOT use `AskUserQuestion`. Present as plain text and STOP — wait for the user to reply before continuing:

```
This request has low complexity (score: {complexity_score}/7). Crew may be heavier than needed.

Recommended approach: use kanban + direct tools instead.

Options:
1. Continue with crew anyway
2. Switch to kanban (creates a task and proceeds without crew phases)
3. Cancel

(Pass --force to bypass this check next time)

Please reply with 1, 2, or 3.
```

Do NOT proceed until the user replies with their selection.

**Handling the selection**:

- **Option 1 (Continue with crew)**: Proceed to Step 6 normally.
- **Option 2 (Switch to kanban)**: Invoke `Skill(skill="wicked-garden:kanban:task", args="create {description}")` and exit. Do not continue the crew setup.
- **Option 3 (Cancel)**: Inform the user the operation was cancelled and exit.

**If `routing_lane == "fast"` AND `--quick` was NOT passed AND `--force` was NOT passed**:

Suggest `--quick` as a lighter option, but do not block:

```
Note: This request has moderate complexity (score: {complexity_score}/7). Consider using --quick for a
lightweight build+review-only run. Continuing with full crew phase plan.
```

Then proceed to Step 6 normally.

### 6. Discover Available Specialists

Run specialist discovery:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/specialist_discovery.py" --json
```

This returns available specialist plugins and their roles:
- **wicked-jam**: ideation (clarify phase)
- **wicked-qe**: quality-engineering (all phases)
- **wicked-product**: business-strategy (design, review)
- **wicked-delivery**: project-management (reporting)
- **wicked-platform**: devsecops (build phase)

### 7. Select Phase Plan

**If `--quick` flag was passed**: Skip all phase selection logic below. Use a static phase plan of `["build", "review"]` only:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} update \
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
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} update \
  --data '{"phase_plan": ["clarify", "test-strategy", "build", "test", "review"], "phase_plan_mode": "dynamic"}' \
  --json
```

**Dynamic mode** (default): Phase plan can be adjusted at checkpoints via signal re-analysis (see execute.md Section 4.5). Set `"phase_plan_mode": "static"` to lock the plan.

**Legacy alias**: The old `qe` phase name maps to `test-strategy` in phases.json. Both names work.

### 8. Task Lifecycle Initialization

Initialize task tracking metadata via phase_manager:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} update \
  --data '{"task_lifecycle": {"staleness_threshold_minutes": 30, "recovery_mode": "auto", "user_overrides": {}}}' \
  --json
```

### 8.5 Kanban Initiative Setup

Every crew project should be tracked as a kanban initiative. This provides visibility in the kanban board and dashboards.

**Goal**: store both the initiative *name* and *UUID* via phase_manager update so session_start can reconnect without a kanban round-trip.

1. **Look up existing initiative by name**:
   ```
   Skill(skill="wicked-garden:kanban:initiative", args="lookup {project-name}")
   ```
   Returns: `{"found": true, "initiative_id": "a1b2c3d4", "project_id": "..."}` or `{"found": false}`.

   If the command fails, skip all kanban steps gracefully — both IDs remain null.

2. **If not found, create the initiative**:
   ```
   Skill(skill="wicked-garden:kanban:initiative", args="create {project-name}")
   ```
   Returns: `{"initiative_id": "a1b2c3d4", "project_id": "b5c6d7e8"}`.

3. **Ensure "Issues" initiative exists** for this repo:
   ```
   Skill(skill="wicked-garden:kanban:initiative", args="ensure-issues")
   ```

4. **Store both name and UUID** via phase_manager:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" {name} update \
     --data '{"kanban_initiative": "{project-name}", "kanban_initiative_id": "{uuid-from-kanban}"}' \
     --json
   ```

5. **All crew tasks must include initiative metadata**:
   ```
   metadata: {"initiative": "{crew-project-name}"}
   ```
   The PreToolUse hook (`pretool_taskcreate.py`) injects this automatically when an active crew project is detected, so explicit metadata is not required in every TaskCreate call — but including it is safe.

This ensures crew project tasks appear grouped under their project initiative on the kanban board, while general fixes/bugs go to "Issues".

### 9. Report to User

Show:
- Project created
- Current phase (clarify)
- **Signal analysis** (what complexity was detected)
- **Recommended specialists** (which plugins will help)
- **Available specialists** (what's actually installed)
- Next step: run `/wicked-garden:crew:execute` to begin clarifying

Example output:
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
| wicked-jam | ideation | ✅ Available |
| wicked-qe | quality | ✅ Available |
| wicked-product | review | ❌ Not installed |

### Task Lifecycle
- Staleness detection: 30 minutes
- Recovery mode: automatic
- Override mechanism: available via phase_manager update

### Next Step
Run `/wicked-garden:crew:execute` to begin the clarify phase.
```
