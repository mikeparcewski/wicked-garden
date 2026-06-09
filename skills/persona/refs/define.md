# persona:define — Create / Update Persona Rubric

Full rubric sourced from `commands/persona/define.md`.
Stores a custom persona in the project-scoped DomainStore.

## Step 1: Parse and Validate

Extract from `$ARGUMENTS`:

- `name` (required): first non-flag token — kebab-case
- `--focus` (required): the perspective this persona applies
- `--traits` (optional): comma-separated behavioral adjectives
- `--role` (optional): category for filtering (default: "custom")
- `--save` (optional flag): also promote to plugin cache for cross-project reuse

If `name` is missing:
> "name is required. Usage: /wicked-garden:persona:define <name> --focus \"<focus>\""
> STOP.

If `--focus` is absent:
> "focus is required — describe the perspective this persona applies."
> "Example: /wicked-garden:persona:define pragmatic-tech-lead --focus \"delivery over perfection\""
> STOP.

## Step 2: Store in DomainStore

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

Only include `--traits` and `--role` if those args were provided.

If the command fails (exit non-zero), show the error from stderr and STOP.

## Step 3: Optionally Save to Plugin Cache

If `--save` flag is present:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py \
  --save-cache "${name}" \
  --json
```

## Step 4: Confirm

Check whether `_updated: true` (existing persona overwritten) or `_updated: false` (new).

If new persona:
> "Created persona '{name}'. Invoke with: `/wicked-garden:persona:as {name} <task>`"

If existing updated:
> "Updated persona '{name}'."

If `--save` was used, add:
> "Saved to plugin cache — available in all projects."

Show persona summary:
- **Focus**: {focus}
- **Traits**: {traits comma-separated or "none"}
- **Role**: {role}
