---
description: Invoke a named persona to perform a task with a specific perspective
argument-hint: "<persona-name> <task description>"
phase_relevance: ["*"]
archetype_relevance: ["*"]
---

# /wicked-garden:persona:as

Invoke a named persona to apply their perspective to any task.

## Arguments

Parse from: $ARGUMENTS

- `persona_name` (required): First word — the persona to invoke
- `task` (required): Everything after the persona name — the task to perform

If $ARGUMENTS is empty or contains only one word (no task), show usage and STOP:

> "Usage: /wicked-garden:persona:as <persona-name> <task description>"
> "Example: /wicked-garden:persona:as engineering 'review my auth flow'"

## Execution

### Step 1: Parse arguments

Split $ARGUMENTS on the first space:
- `persona_name` = first token
- `task` = remaining text

### Step 2: Look up the persona

Run the registry script to resolve the persona definition:

```bash
PERSONA_JSON=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py --get "${persona_name}" --json 2>/dev/null)
REGISTRY_EXIT=$?
```

### Step 3: Handle lookup failure

If the script exits non-zero or PERSONA_JSON is empty or contains `"error"`:

1. Run the list command to get available personas:

```bash
AVAILABLE=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py --list --json 2>/dev/null)
```

2. Show the user:

> "No persona found named '{persona_name}'. Available personas:"

3. List each available persona name with its description (name — description).

4. **STOP** — do not dispatch a Task.

### Step 4: Extract persona fields

From PERSONA_JSON, extract:
- `name`
- `description`
- `focus`
- `traits` (list — format as bullet list, e.g. `- direct\n- pragmatic`)
- `personality` (object with style, temperament, humor)
- `constraints` (list — format as numbered list)
- `memories` (list — format as bullet list)
- `preferences` (object with communication, code_style, review_focus, decision_making)

If traits is empty, use: "No specific traits defined — apply the focus broadly."
If personality is empty, use: "Apply the focus in a direct and professional style."
If constraints is empty, use: "No hard constraints — use your judgment."
If memories is empty, use: "No specific experiences — draw on your focus."
If preferences is empty, use: "No specific preferences — communicate clearly and directly."

### Step 5: Dispatch to persona-agent

```python
Task(
    subagent_type="wicked-garden:persona:persona-agent",
    prompt="""You are **{name}**.

## Your Identity

{description}

## Your Focus

{focus}

## Your Traits

{traits_as_bullets}

## Your Personality

- **Style**: {personality.style}
- **Temperament**: {personality.temperament}
- **Voice**: {personality.humor}

## Your Constraints (MUST follow)

{constraints_as_numbered_list}

## Your Experience

{memories_as_bullet_list}

## Your Preferences

- **Communication**: {preferences.communication}
- **Code style**: {preferences.code_style}
- **Review focus**: {preferences.review_focus}
- **Decision making**: {preferences.decision_making}

## Task

{task}

Respond fully in character as {name}. Open your response with `## {name}` and
a one-line focus statement. Then deliver the task output from this persona's
perspective, honoring all constraints and preferences above.
"""
)
```
