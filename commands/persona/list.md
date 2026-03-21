---
description: List all available personas with their focus and invocation syntax
argument-hint: "[--role <role>]"
---

# /wicked-garden:persona:list

Discover all available personas — built-in specialists, custom personas, and cached personas.

## Arguments

Parse from: $ARGUMENTS

- `--role` (optional): Filter by role category (e.g., engineering, devsecops, product, quality-engineering)

## Execution

### Step 1: Fetch persona list

Build the command with optional role filter:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py --list [--role "${role}"] --json
```

If `--role` is present in $ARGUMENTS, include `--role <value>` in the command.

### Step 2: Format output

Present as tables grouped by source. Each row MUST include the exact invocation
command so no separate documentation lookup is needed.

```markdown
## Available Personas

### Built-in Specialists
| Name | Focus | Invoke |
|------|-------|--------|
| engineering | Full-stack engineering expertise... | `/wicked-garden:persona:as engineering <task>` |
| platform | DevSecOps specialist for security... | `/wicked-garden:persona:as platform <task>` |
| product | Product and design expertise... | `/wicked-garden:persona:as product <task>` |
| qe | Quality Engineering specialist... | `/wicked-garden:persona:as qe <task>` |
| data | Data engineering specialist... | `/wicked-garden:persona:as data <task>` |
| delivery | Feature delivery specialist... | `/wicked-garden:persona:as delivery <task>` |
| jam | Multi-perspective brainstorming... | `/wicked-garden:persona:as jam <task>` |
| agentic | Validates agentic application... | `/wicked-garden:persona:as agentic <task>` |
| design | Visual design, UX analysis... | `/wicked-garden:persona:as design <task>` |

### Custom Personas
| Name | Focus | Invoke |
|------|-------|--------|
| pragmatic-tech-lead | Delivery over perfection | `/wicked-garden:persona:as pragmatic-tech-lead <task>` |

### Cached Personas (cross-project)
| Name | Focus | Invoke |
|------|-------|--------|
| my-persona | Shared focus | `/wicked-garden:persona:as my-persona <task>` |
```

Rules:
- Truncate the focus/description column at 60 characters if needed (add "...")
- Only show sections that have personas (omit Custom and Cached sections if empty)
- If `--role` was specified and returns zero results, show: "No personas found with role '{role}'."
- Fallback personas (architect, skeptic, advocate) are shown in a "### Fallback Personas" section when specialist.json is unavailable

### Step 3: Show tip

After the table(s), add:

```
**Tip:** Use `/wicked-garden:persona:define <name> --focus "<focus>"` to create your own persona.
Use `/wicked-garden:engineering:review --persona <name>` to route a code review through any persona's lens.
```
