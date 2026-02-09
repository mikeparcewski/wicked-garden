# Wicked Kanban Test Scenarios

This directory contains real-world test scenarios that demonstrate and validate wicked-kanban functionality.

## Scenario Overview

| Scenario | Type | Difficulty | Time | What It Tests |
|----------|------|------------|------|---------------|
| [basic-task-workflow](basic-task-workflow.md) | workflow | basic | 5 min | Core CRUD operations: create project, tasks, move through swimlanes, add comments |
| [todowrite-sync](todowrite-sync.md) | integration | basic | 3 min | PostToolUse hook that auto-syncs TaskCreate/TaskUpdate calls to kanban |
| [collaboration](collaboration.md) | integration | basic | 5 min | Human and Claude working on same board via shared file storage |
| [session-persistence](session-persistence.md) | integration | basic | 4 min | Data persistence across Claude Code sessions |
| [search-and-discovery](search-and-discovery.md) | feature | basic | 4 min | Search across projects to find tasks by name, description, or comments |
| [task-dependencies](task-dependencies.md) | workflow | intermediate | 5 min | Task dependencies with automatic blocking status |
| [initiative-planning](initiative-planning.md) | workflow | intermediate | 7 min | Time-boxed initiatives with status lifecycle (planning → active → completed) |
| [artifacts-and-commits](artifacts-and-commits.md) | feature | intermediate | 6 min | Linking commits, files, and URLs to tasks for traceability |
| [priority-triage](priority-triage.md) | workflow | intermediate | 5 min | Priority levels (P0-P3) for managing urgent work |
| [multi-project-coordination](multi-project-coordination.md) | workflow | advanced | 8 min | Managing multiple related projects with cross-project dependencies |

## Coverage Map

### Core Features
- **Project Management**: basic-task-workflow, multi-project-coordination
- **Task CRUD**: basic-task-workflow, todowrite-sync, collaboration
- **Swimlanes**: basic-task-workflow, task-dependencies
- **Comments**: basic-task-workflow, artifacts-and-commits, multi-project-coordination
- **Search**: search-and-discovery, multi-project-coordination

### Advanced Features
- **Dependencies**: task-dependencies, multi-project-coordination
- **Priorities**: priority-triage, initiative-planning
- **Initiatives**: initiative-planning
- **Artifacts**: artifacts-and-commits
- **Commits**: artifacts-and-commits, multi-project-coordination

### Integration & Architecture
- **TaskCreate/TaskUpdate Sync**: todowrite-sync
- **File-Based Storage**: collaboration, session-persistence
- **Persistence**: session-persistence
- **wicked-workbench**: collaboration (for visual UI rendering)

## Running Scenarios

Each scenario is self-contained with:
- **Setup** - Initial conditions and commands
- **Steps** - Specific actions to perform
- **Expected Outcome** - What should happen
- **Success Criteria** - Verifiable checkboxes
- **Value Demonstrated** - Why this matters

### Example: Running basic-task-workflow

```bash
# Follow the commands in the scenario file
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Auth Feature" -d "User authentication implementation"
# ... continue with steps from scenario
```

### Verification

After running each scenario:
1. Check CLI output matches expected outcome
2. Verify file-based data at `~/.something-wicked/wicked-kanban/`
3. Confirm all success criteria checkboxes can be marked

## Scenario Design Principles

All scenarios follow these guidelines:

1. **Real-world use cases** - No toy examples; scenarios reflect actual development workflows
2. **Functional testing** - Each scenario proves a feature actually works
3. **Concrete setup** - Clear, executable commands to create test data
4. **Verifiable criteria** - Objective checkboxes that can be tested
5. **Value articulation** - Clear explanation of WHY someone would use this

## Adding New Scenarios

When adding scenarios, include:

```markdown
---
name: scenario-name
title: Human Readable Title
description: One-line description
type: workflow|integration|feature
difficulty: basic|intermediate|advanced
estimated_minutes: N
---

# Title

## Setup
[Concrete setup commands]

## Steps
[Numbered steps with commands]

## Expected Outcome
[What should happen]

## Success Criteria
- [ ] Verifiable criteria 1
- [ ] Verifiable criteria 2

## Value Demonstrated
[Why this matters in real-world usage]
```

## Test Execution

These scenarios can be:
- **Manual testing** - Follow steps during development
- **Onboarding** - Help new users understand capabilities
- **Documentation** - Show real examples of features
- **Regression testing** - Verify nothing broke after changes
- **Value demonstration** - Show prospective users what the plugin does
