---
description: Start a new wicked-crew project with outcome clarification
argument-hint: <project description>
---

# /wicked-crew:start

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
ls -d ~/.something-wicked/wicked-crew/projects/*/ 2>/dev/null | xargs -I {} basename {}
```

If project name exists, ask user: resume, rename, or cancel.

### 4. Create Project Structure

Create directory and initial files:

```
~/.something-wicked/wicked-crew/projects/{name}/
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

### 5. Analyze Input with Smart Decisioning

Run smart decisioning on the project description:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/smart_decisioning.py" analyze --project-dir . --json "{description}"
```

This returns:
- **signals**: Detected signal types (security, performance, product, etc.)
- **complexity**: Score 0-7 (low/medium/high)
- **ambiguous**: Whether clarification is needed
- **recommended_specialists**: Which plugins would help

Store analysis in project.json:

```json
{
  "name": "{name}",
  "created_at": "{ISO 8601 UTC timestamp}",
  "current_phase": "clarify",
  "signals_detected": ["security", "data"],
  "complexity_score": 4,
  "specialists_recommended": ["wicked-qe", "wicked-product"]
}
```

### 6. Discover Available Specialists

Run specialist discovery:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/specialist_discovery.py" --json
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

**Two default initiatives per repo:**
1. **"Issues"** — default for general fixes, small tasks, and non-crew work
2. **One per crew project** — named after the project

When creating a crew project, ensure kanban has these:

1. **Check for existing "Issues" initiative** in the kanban project for this repo. If none exists, create it:
   ```
   TaskCreate(subject="Setup: {project-name} - Initialize kanban tracking",
              description="Create default Issues initiative for this repository",
              activeForm="Setting up kanban initiatives")
   ```

2. **All crew tasks must include initiative metadata** so `todo_sync` routes them correctly:
   ```
   metadata: {"initiative": "{crew-project-name}"}
   ```
   Tasks without this metadata go to the "Issues" initiative by default.

3. Store the initiative name in project.json:
   ```json
   {
     "kanban_initiative": "{project-name}"
   }
   ```

This ensures crew project tasks appear grouped under their project initiative on the kanban board, while general fixes/bugs go to "Issues".

### 9. Report to User

Show:
- Project created at path
- Current phase (clarify)
- **Signal analysis** (what complexity was detected)
- **Recommended specialists** (which plugins will help)
- **Available specialists** (what's actually installed)
- Next step: run `/wicked-crew:execute` to begin clarifying

Example output:
```markdown
## Project Created: {name}

**Path**: ~/.something-wicked/wicked-crew/projects/{name}/
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
Run `/wicked-crew:execute` to begin the clarify phase.
```
