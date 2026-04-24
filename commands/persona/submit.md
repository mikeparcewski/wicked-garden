---
description: |
  Use when you want to contribute a locally-defined custom persona back to the wicked-garden repository
  as a built-in specialist. NOT for creating a persona (use persona:define) or invoking one (use persona:as).
argument-hint: "<persona-name>"
---

# /wicked-garden:persona:submit

Submit a custom persona to the wicked-garden repository as a new specialist entry via pull request.
The persona will be added to `.claude-plugin/specialist.json` and proposed for inclusion as a built-in.

## Arguments

Parse from: $ARGUMENTS

- `name` (required): The persona name to submit

If `name` is missing, output:
> "Usage: /wicked-garden:persona:submit <persona-name>"
And **STOP**.

## Execution

### Step 1: Look up the persona

```bash
PERSONA_JSON=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/scripts/_run.py" \
  scripts/persona/registry.py --get "${name}" --json 2>/dev/null)
REGISTRY_EXIT=$?
```

If exit non-zero or PERSONA_JSON is empty:
> "Persona '{name}' not found. Run `/wicked-garden:persona:list` to see available personas."
And **STOP**.

Extract `source` from PERSONA_JSON.

If `source` is `"builtin"`:
> "'{name}' is already a built-in specialist. Nothing to submit."
And **STOP**.

### Step 2: Read current specialist.json

```bash
cat "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/specialist.json"
```

Parse the JSON. Check that no existing specialist has the same name. If a duplicate exists:
> "A specialist named '{name}' already exists in specialist.json. Choose a different name or update the existing entry manually."
And **STOP**.

### Step 3: Create branch

```bash
git checkout -b "persona/${name}"
```

If the branch already exists, use `git checkout persona/${name}` to switch to it.

### Step 4: Add persona to specialist.json

Extract from PERSONA_JSON: `name`, `role`, `description`.

Add a new entry to the `specialists` array in specialist.json:

```json
{
  "name": "{name}",
  "role": "{role}",
  "description": "{description}",
  "enhances": ["*"]
}
```

Use the Edit tool to write the updated specialist.json. Preserve existing formatting and array structure.

### Step 5: Commit and push

```bash
git add "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/specialist.json"
git commit -m "feat: add ${name} persona to specialist registry"
git push -u origin "persona/${name}"
```

### Step 6: Open PR

Extract from PERSONA_JSON: `focus`, `traits` (join with ", " or "none"), `description`, `role`.

```bash
gh pr create \
  --title "feat: add persona ${name}" \
  --body "$(cat <<'PREOF'
## Persona Card

**Name**: {name}
**Role**: {role}
**Focus**: {focus}
**Traits**: {traits_comma_separated}

## Description

{description}

## Intended Use Cases

This persona can be invoked via:
\`\`\`
/wicked-garden:persona:as {name} <task>
\`\`\`

It provides a {focus}-focused perspective on any task.

---
Submitted via \`/wicked-garden:persona:submit\`
PREOF
)"
```

### Step 7: Return to original branch

```bash
git checkout -
```

### Step 8: Confirm

Show:
> "PR opened: {pr_url}"
> "Reviewers can merge to make '{name}' a built-in persona available to all wicked-garden users."
