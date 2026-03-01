---
description: Start a new wicked-crew project with outcome clarification
argument-hint: <project description>
---

# /wicked-garden:crew:start

Create a new project and begin the clarify phase.

## Instructions

### 1. Parse Arguments

Extract the project description from arguments. If no description provided, ask for one.

### 2. Generate Project Name

Convert description to kebab-case slug:
- Lowercase
- Replace spaces with hyphens
- Remove special characters
- Max 64 characters

### 3. Check for Existing Project

```bash
ls -d ~/.something-wicked/wicked-garden/local/wicked-crew/projects/*/ 2>/dev/null | xargs -I {} basename {}
```

If project name exists, ask user: resume, rename, or cancel.

### 4. Create Project Structure

Create directory and initial files:

```
~/.something-wicked/wicked-garden/local/wicked-crew/projects/{name}/
├── project.md
├── outcome.md
└── phases/
    └── clarify/
        └── status.md
```

**project.md:**
```markdown
---
name: {project-name}
created: {date}
current_phase: clarify
status: in_progress
---

# Project: {Title}

{Description}

## Current Phase: clarify

Defining outcome and success criteria.

## Phases

| Phase | Status | Notes |
|-------|--------|-------|
| {for each phase in phase_plan} | pending | |
```

**outcome.md:**
```markdown
# Outcome: {Title}

## Desired Outcome

{To be defined during clarify phase}

## Success Criteria

1. {To be defined}

## Scope

### In Scope
- {To be defined}

### Out of Scope
- {To be defined}
```

**phases/clarify/status.md:**
```markdown
---
phase: clarify
status: in_progress
started: {date}
---

# Clarify Phase

Defining the outcome and success criteria.

## Deliverables

- [ ] Outcome statement
- [ ] Success criteria
- [ ] Scope boundaries
```

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

4. **Build archetype hints** as JSON — define what quality dimensions matter for this project:
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

5. **Store archetype hints** in project.json as `archetype_hints` for reuse at checkpoints.

### 5.5 Analyze Input with Smart Decisioning

Run smart decisioning with archetype hints:

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

Store analysis in project.json:

```json
{
  "name": "{name}",
  "created_at": "{ISO 8601 UTC timestamp}",
  "current_phase": "clarify",
  "signals_detected": ["security", "data"],
  "complexity_score": 4,
  "specialists_recommended": ["wicked-qe", "wicked-product"],
  "archetype_hints": {}
}
```

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

Read `${CLAUDE_PLUGIN_ROOT}/phases.json` to see all available phases with their triggers, complexity ranges, and skip rules.

Select which phases to include based on the signal analysis and complexity score:

1. **Always include** phases where `is_skippable` is `false` (e.g., clarify, build, review)
2. **Include test-strategy by default** if `complexity_score` >= 2 (testing should be the norm, not the exception)
3. **Include test by default** if `complexity_score` >= 2 OR any code-modifying signals detected
4. **Include if signals match**: For each remaining skippable phase, include it if any of its `triggers` appear in `signals_detected`
5. **Include if complexity warrants**: Include if `complexity_score` falls within the phase's `complexity_range`
6. **Consider specialist availability**: Prefer phases where a matching specialist is installed

Order the selected phases by their `depends_on` relationships.

Store the ordered phase list and planning mode in project.json:

```json
{
  "phase_plan": ["clarify", "test-strategy", "build", "test", "review"],
  "phase_plan_mode": "dynamic"
}
```

**Dynamic mode** (default): Phase plan can be adjusted at checkpoints via signal re-analysis (see execute.md Section 4.5). Set `"phase_plan_mode": "static"` to lock the plan.

**Legacy alias**: The old `qe` phase name maps to `test-strategy` in phases.json. Both names work.

### 8. Task Lifecycle Initialization

Initialize task tracking metadata in project.json:

```json
{
  "task_lifecycle": {
    "staleness_threshold_minutes": 30,
    "recovery_mode": "auto",
    "user_overrides": {}
  }
}
```

### 8.5 Kanban Initiative Setup

Every crew project should be tracked as a kanban initiative. This provides visibility in the kanban board and dashboards.

**Goal**: store both the initiative *name* and *UUID* in project.json so session_start can reconnect without a kanban round-trip.

1. **Look up existing initiative by name**. If wicked-kanban is installed:
   ```bash
   python3 "${KANBAN_PLUGIN_ROOT}/scripts/kanban_initiative.py" lookup "{project-name}"
   ```
   Returns: `{"found": true, "initiative_id": "a1b2c3d4", "project_id": "..."}` or `{"found": false}`.

   If wicked-kanban is not installed (`discover_script` returns None), skip all kanban steps gracefully — both IDs remain null.

2. **If not found, create the initiative**:
   ```bash
   python3 "${KANBAN_PLUGIN_ROOT}/scripts/kanban_initiative.py" create "{project-name}"
   ```
   Returns: `{"initiative_id": "a1b2c3d4", "project_id": "b5c6d7e8"}`.

3. **Ensure "Issues" initiative exists** for this repo:
   ```bash
   python3 "${KANBAN_PLUGIN_ROOT}/scripts/kanban_initiative.py" ensure-issues
   ```

4. **Store both name and UUID in project.json** as first-class fields:
   ```json
   {
     "kanban_initiative": "{project-name}",
     "kanban_initiative_id": "{uuid-from-kanban}"
   }
   ```

5. **All crew tasks must include initiative metadata**:
   ```
   metadata: {"initiative": "{crew-project-name}"}
   ```
   The PreToolUse hook (`pretool_taskcreate.py`) injects this automatically when an active crew project is detected, so explicit metadata is not required in every TaskCreate call — but including it is safe.

This ensures crew project tasks appear grouped under their project initiative on the kanban board, while general fixes/bugs go to "Issues".

### 9. Report to User

Show:
- Project created at path
- Current phase (clarify)
- **Signal analysis** (what complexity was detected)
- **Recommended specialists** (which plugins will help)
- **Available specialists** (what's actually installed)
- Next step: run `/wicked-garden:crew:execute` to begin clarifying

Example output:
```markdown
## Project Created: {name}

**Path**: ~/.something-wicked/wicked-garden/local/wicked-crew/projects/{name}/
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
- Override mechanism: available via project.json

### Next Step
Run `/wicked-garden:crew:execute` to begin the clarify phase.
```
