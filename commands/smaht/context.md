---
description: Build structured context packages for subagent dispatches
argument-hint: build --task "<description>" [--project <name>] [--dispatch] [--prompt]
---

# /wicked-garden:smaht:context

Build structured context packages for subagent dispatches. Assembles task-scoped context from session state, memory, search, and project state — replacing unstructured prose dumps.

## Usage

```
/smaht:context build --task "Review auth implementation" --project myproject --dispatch --prompt
/smaht:context build --task "Execute design phase" --json
```

## Instructions

### Parse Arguments

- `--task` (required): Description of the work for context scoping
- `--project`: Crew project name for project-specific context
- `--files`: Specific file paths to include
- `--dispatch`: Include ecosystem orientation for subagents (installed plugins, available skills)
- `--prompt`: Output as prompt-ready text
- `--json`: Output as structured JSON

### Execute

```bash
cd "${CLAUDE_PLUGIN_ROOT}" && uv run python scripts/_run.py scripts/smaht/context_package.py build \
  --task "{task description}" \
  {--project "{project-name}"} \
  {--dispatch} {--prompt}
```

### Output

The context package provides structured fields:
- **task**: Scoped task description
- **constraints**: Active constraints and requirements
- **decisions**: Prior decisions relevant to this task
- **files**: File paths in scope
- **project_state**: Phase, complexity, deliverables
- **memories**: Relevant memories from wicked-garden:mem
- **ecosystem**: Installed plugins, available skills (with `--dispatch`)

### Report

Return the context package output. Callers should include this in subagent Task() prompts instead of raw deliverable text.
