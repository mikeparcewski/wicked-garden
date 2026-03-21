---
name: test-task-factory
description: |
  Generates test task creation parameters from a detected change type and
  implementation task subject. Routes to the correct test type (visual/endpoint)
  and produces TaskCreate-ready subjects, descriptions, and metadata.

  Use when: creating test tasks after change-type detection, QE task generation,
  "test task factory", "create test tasks", "generate QE tasks", or after
  change-type-detector classifies files as ui/api/both.
---

# Test Task Factory Skill

Generate test task parameters from a change type. The output is ready for
TaskCreate — no further processing needed.

## Quick Reference

| Input | Test Tasks Created |
|-------|--------------------|
| `ui` | 1 task — visual category |
| `api` | 1 task — endpoint category |
| `both` | 2 tasks — visual + endpoint |
| `unknown` | 0 tasks — emit warning, no tasks |

## Algorithm: Step by Step

### Step 1 — Strip phase prefix from impl subject

Remove leading phase label and optional project name from the implementation
task subject to get the clean `impl_description`.

**Pattern to strip**: `^(build|clarify|design|ideate|test-strategy|test|review|implement)\s*:\s*`
(case-insensitive)

**Then strip project prefix**: If the result matches `{project-name} - {description}`,
take only the part after ` - `.

Examples:
- `"Build: my-project - Implement login form"` → `"Implement login form"`
- `"Build: Implement login form"` → `"Implement login form"`
- `"Implement login form"` → `"Implement login form"` (unchanged)

### Step 2 — Generate safe filename fragment

Convert `impl_description` to lowercase, replace non-alphanumeric runs with `-`,
strip leading/trailing dashes, cap at 50 characters. Used in screenshot path
templates in descriptions.

### Step 3 — Route by change type

```
change_type == "unknown"   → return empty test_tasks list + warning (see below)
change_type == "ui"        → create 1 task using ui template
change_type == "api"       → create 1 task using api template
change_type == "both"      → create 2 tasks: ui template first, then api template
unrecognized value         → return empty test_tasks list + warning
```

### Step 4 — Construct subject

```
Test: {project} - {impl_description} ({test_category})
```

Where `test_category` is:
- `visual` for ui tasks
- `endpoint` for api tasks

### Step 5 — Fill description template

See [Test Task Templates](refs/test-task-templates.md) for full template text
per test type.

### Step 6 — Assemble metadata

```json
{
  "initiative": "{project}",
  "priority": "P1",
  "assigned_to": "acceptance-test-executor",
  "test_type": "{ui|api}",
  "evidence_required": [...],
  "evidence_optional": [...],
  "impl_subject": "{original impl_subject}"
}
```

See [Test Evidence Taxonomy](refs/test-evidence-taxonomy.md) for evidence
field values per test type.

## Output Format

```json
{
  "test_tasks": [
    {
      "subject": "Test: my-project - Implement login form (visual)",
      "description": "...",
      "metadata": { ... }
    }
  ]
}
```

For `unknown` or unrecognized change types:

```json
{
  "test_tasks": [],
  "suppressed": true,
  "warning": "change_type is 'unknown' — no test tasks created for '...'. ..."
}
```

## Warning Text (unknown change type)

> change_type is 'unknown' — no test tasks created for '{impl_description}'.
> No UI or API files were detected. If this task touches UI or API code,
> re-run change-type detection with the correct file paths.

## Warning Text (unrecognized change type)

> Unrecognized change_type '{value}' — no test tasks created.

## Usage Example

Input:
- `change_type`: `"both"`
- `impl_subject`: `"Build: checkout - Integrate payment flow"`
- `project`: `"checkout"`

Produces `impl_description = "Integrate payment flow"`, then two tasks:
1. `"Test: checkout - Integrate payment flow (visual)"` with ui template
2. `"Test: checkout - Integrate payment flow (endpoint)"` with api template

See [Test Task Templates](refs/test-task-templates.md) for full template
content and [Test Evidence Taxonomy](refs/test-evidence-taxonomy.md) for
evidence field values.
