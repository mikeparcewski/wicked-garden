---
description: Generate multi-perspective delivery reports from project data
argument-hint: "<file> [--personas <list>] [--all] [--output <dir>]"
---

# /wicked-garden:delivery:report

Generate multi-perspective stakeholder reports from project data.

## Arguments

- `file`: Input file (outcome.md, project brief, or crew phase data)
- `--personas <list>`: Comma-separated perspectives to include (default: all)
  - Options: `delivery`, `engineering`, `product`, `qe`, `architecture`, `devsecops`
- `--all`: Include all available perspectives
- `--output <dir>`: Write report to directory (default: stdout)

## Instructions

### 1. Parse Arguments

Extract `file`, `--personas`, `--all`, and `--output` from the provided arguments.
If no file provided, use current crew project context.

### 2. Gather Project Context

Read the input file or collect context from the active crew project:
```bash
# If crew project active
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/crew/phase_manager.py" status
```

### 3. Delegate to Stakeholder Reporter

```
Task(
  subagent_type="wicked-garden:delivery:stakeholder-reporter",
  prompt="Generate a multi-perspective stakeholder report.

Input: {file_contents_or_project_context}

Personas to cover: {personas_list or 'all six: Delivery, Engineering, Product, QE, Architecture, DevSecOps'}

For each persona, produce a focused section addressing what that stakeholder cares most about:
- **Delivery**: Progress, blockers, timeline, risk status
- **Engineering**: Technical debt, architecture decisions, code quality signals
- **Product**: Feature completeness, scope changes, user story coverage
- **QE**: Test coverage, quality gate results, known defects
- **Architecture**: Design decisions, trade-offs, technical risks
- **DevSecOps**: Security findings, deployment readiness, compliance status

Format as a single cohesive stakeholder report with a 3-bullet executive summary at the top.

Output directory: {output_dir or 'stdout'}"
)
```

## Examples

```bash
# Report from outcome file
/wicked-garden:delivery:report outcome.md

# Engineering and QE perspectives only
/wicked-garden:delivery:report outcome.md --personas engineering,qe

# All perspectives, save to reports/
/wicked-garden:delivery:report outcome.md --all --output reports/
```
