---
description: UX flow design and analysis — create user flows, map information architecture, evaluate interaction patterns
argument-hint: "<target-or-description> [--mode create|analyze]"
---

# /wicked-garden:product:ux

Design and analyze user flows, interaction patterns, and information architecture.
Use `--mode create` to generate flows from requirements; `--mode analyze` to evaluate
existing flows in code or documents.

## Usage

```bash
# Analyze existing flows in code
/wicked-garden:product:ux src/pages/

# Create a flow from a description
/wicked-garden:product:ux "user registration with email verification" --mode create

# Analyze flows in a requirements document
/wicked-garden:product:ux outcome.md --mode analyze

# Default: auto-detect mode from input type
/wicked-garden:product:ux src/components/Checkout
```

## Instructions

### 1. Parse Arguments

Extract `<target>` (file path, directory, or description string) and `--mode` flag.

Auto-detect mode if not specified:
- Description string (no path) → `create`
- File/directory path → `analyze`

### 2. Gather Content

- If a path: read the target files (components, pages, routing config)
- If a description: use as-is for the agent prompt

### 3. Delegate to UX Analyst

```
Task(
  subagent_type="wicked-garden:product:ux-analyst",
  prompt="""Perform UX flow {analysis | design} for the following.

## Target
{target path or description}

## Content
{file contents or description}

## Mode
{create: generate flows from requirements | analyze: evaluate existing flows}

For create mode:
- Map information architecture
- Design happy path flow diagram (ASCII or Mermaid)
- Define edge cases (empty, error, loading, cancel)
- Note open questions

For analyze mode:
- Trace the existing happy path
- Find dead ends and missing error handling
- Check back navigation and recovery paths
- Score against the flow checklist
- Provide specific improvement recommendations

Return diagrams, IA map, and findings."""
)
```

### 4. Present Results

Display the UX analyst's output directly to the user.

## Integration

- **design:mockup**: Request wireframes for designed flows
- **design:review**: Visual review of the implemented flow
- **wicked-kanban**: Track flow issues discovered during analysis
