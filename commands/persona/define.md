---
description: Create or update a custom persona for on-demand invocation
argument-hint: "<name> --focus \"<focus>\" [--traits \"<t1,t2>\"] [--role <role>] [--save]"
---

# /wicked-garden:persona:define

Create or update a custom persona definition. Stored in project-scoped DomainStore
by default. Use `--save` to also promote to the plugin-level cache for cross-project reuse.

## Arguments

Parse from: $ARGUMENTS

- `name` (required): First argument — kebab-case persona name
- `--focus` (required): The perspective this persona applies
- `--traits` (optional): Comma-separated behavioral adjectives (e.g., "direct,pragmatic,cost-aware")
- `--role` (optional): Category for filtering (default: "custom")
- `--save` (optional flag): Also save to plugin cache for cross-project reuse

## Execution

### Step 1: Parse and validate inputs

Extract `name` as the first non-flag token from $ARGUMENTS.

If `name` is missing, output:
> "name is required. Usage: /wicked-garden:persona:define <name> --focus \"<focus>\""
And **STOP**.

If `--focus` is not present in $ARGUMENTS, output:
> "focus is required -- describe the perspective this persona applies."
> "Example: /wicked-garden:persona:define pragmatic-tech-lead --focus \"delivery over perfection\""
And **STOP**.

### Step 2: Store in DomainStore (project-scoped)

Build the registry command from parsed arguments:

```bash
RESULT=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py \
  --define "${name}" \
  --focus "${focus}" \
  [--traits "${traits}"] \
  [--role "${role}"] \
  --json)
```

Only include `--traits` and `--role` flags if those arguments were provided.

If the command fails (exit non-zero), show the error from stderr and **STOP**.

### Step 3: Optionally save to plugin cache

If `--save` flag is present in $ARGUMENTS:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py \
  --save-cache "${name}" \
  --json
```

### Step 4: Confirm

Check whether the stored record has `_updated: true` (existing persona was overwritten) or `_updated: false` (new persona created).

If new persona:
> "Created persona '{name}'. Invoke with: `/wicked-garden:persona:as {name} <task>`"

If existing persona updated (upsert):
> "Updated persona '{name}'."

If `--save` was used, add:
> "Saved to plugin cache — available in all projects."

Show the persona definition as a summary:
- **Focus**: {focus}
- **Traits**: {traits as comma-separated or "none"}
- **Role**: {role}
