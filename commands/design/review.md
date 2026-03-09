---
description: Systematic visual design review — design system adherence, spacing, typography, color, component patterns
argument-hint: "<target> [--quick]"
---

# /wicked-garden:design:review

Systematic visual design review of UI code or components. Checks design system
adherence, spacing, typography, color consistency, and component patterns.

## Usage

```bash
# Review a component
/wicked-garden:design:review src/components/Button

# Review a directory
/wicked-garden:design:review src/components/

# Quick scan for obvious violations
/wicked-garden:design:review src/ --quick
```

## Instructions

### 1. Parse Arguments

Extract `<target>` (file, component, or directory). Note `--quick` flag if present.

### 2. Gather Context

Read the target file(s). If a directory, read key component files.

Also check for design token definitions:
- `tokens.css`, `design-tokens.json`, `theme.ts`, `tailwind.config.js`

### 3. Delegate to Visual Reviewer

```
Task(
  subagent_type="wicked-garden:design:visual-reviewer",
  prompt="""Perform a visual design review of the following UI code.

## Target
{target path}

## Code
{file contents}

## Design Tokens (if found)
{token definitions}

## Mode
{Full review | Quick scan (--quick flag)}

Review for:
- Design token adherence (no hardcoded colors/spacing)
- Typography hierarchy and scale
- Spacing and grid consistency
- Component state coverage (hover, focus, disabled, error)
- Responsive layout patterns

Return a scored review with findings by category and top fix recommendations."""
)
```

### 4. Present Results

Display the visual reviewer's output directly to the user.

## Quick Mode

With `--quick`: scan for the top 3 most critical violations only.
Return in under 15 seconds with a short findings list.

## Integration

- **wicked-kanban**: Issues are tracked by the reviewer agent
- **wicked-mem**: Design token patterns stored for future reviews
- **engineering**: Coordinate fixes with code review
