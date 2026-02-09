---
description: {{description}}
argument-hint: <target> [--option value]
---

# /{{plugin_name}}:{{command_name}}

{{description}}.

## Instructions

### 1. Parse Arguments

Extract from arguments:
- `target` (required): The target to analyze
- `--option` (optional): Additional options

### 2. Dispatch to {{agent_name}}

```
Task(
  subagent_type="{{plugin_name}}:{{agent_name}}",
  prompt="""
  {{agent_task_description}}.

  Target: {target}

  Focus areas:
  1. {checklist item 1}
  2. {checklist item 2}
  3. {checklist item 3}

  Return findings as structured markdown with file:line references.
  """
)
```

### 3. Present Results

```markdown
## {{command_name}}: {target}

### Summary
{agent findings summary}

### Details
{structured findings}

### Recommendations
1. {action item}
```
