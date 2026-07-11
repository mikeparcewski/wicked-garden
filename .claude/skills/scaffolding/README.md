# Scaffold Tool

Component scaffolding for the unified **wicked-garden** plugin. The plugin is
**skills-only**: the former `commands/` and `agents/` trees were absorbed into
`skills/`, so this tool scaffolds skills, context:fork worker skills, and hooks.
It never writes a `commands/` or `agents/` file.

## Quick Start

```bash
# Interactive mode
python3 .claude/skills/scaffolding/scripts/scaffold.py

# Command line mode
python3 .claude/skills/scaffolding/scripts/scaffold.py skill  --name my-skill  --domain crew        --description "My skill"  --use-when "trigger"
python3 .claude/skills/scaffolding/scripts/scaffold.py worker --name my-worker --domain platform     --description "My worker" --tools "Read,Write,Bash"
python3 .claude/skills/scaffolding/scripts/scaffold.py hook   --event PreToolUse --script my-hook     --description "My hook"
```

## Component types

### Skill (sub-skill)

Creates a sub-skill under a domain router:

```bash
python3 .claude/skills/scaffolding/scripts/scaffold.py skill \
  --name my-skill \
  --domain crew \
  --description "What this skill does" \
  --use-when "when to use it"
```

Generated:
```
skills/crew/my-skill/SKILL.md
```

### Worker skill (context:fork — the former agent)

Creates a standalone `context: fork` worker skill dispatched via
`Skill(skill="wicked-garden-{domain}-{role}")`. The `agent` subcommand is a
back-compat alias for `worker`.

```bash
python3 .claude/skills/scaffolding/scripts/scaffold.py worker \
  --name my-worker \
  --domain platform \
  --description "What this worker does" \
  --expertise "domain of expertise" \
  --tools "Read,Write,Bash"
```

Generated:
```
skills/platform-my-worker/SKILL.md
  name: wicked-garden-platform-my-worker
  context: fork
```

### Action (former command) — RETIRED

Commands no longer exist as files. A former command is now an **action** of the
consolidated per-domain router skill (`skills/{domain}/SKILL.md`). The `command`
subcommand writes no file — it prints guidance for adding the action (and, if
the domain router is missing, how to scaffold it):

```bash
python3 .claude/skills/scaffolding/scripts/scaffold.py command \
  --name my-action \
  --domain engineering \
  --description "What this action does"
```

Copy the action stub in `templates/plugin/command-with-agent.md` into the
router body and dispatch to a worker with
`Skill(skill="wicked-garden-{domain}-{role}")`.

### Hook

```bash
python3 .claude/skills/scaffolding/scripts/scaffold.py hook \
  --event PreToolUse \
  --script validate-tools \
  --description "Validate tool use" \
  --matcher "Write|Edit|Bash"
```

Generated:
```
hooks/hooks.json   (updated)
hooks/scripts/validate-tools.py
```

Valid events: `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`,
`SubagentStop`, `SessionStart`, `SessionEnd`, `PreCompact`, `Notification`.

## Interactive Mode

Run without arguments for prompts:

```bash
python3 .claude/skills/scaffolding/scripts/scaffold.py

=== Component Scaffold (wicked-garden, skills-only) ===

Component types:
  1. Skill (sub-skill / standalone)
  2. Worker skill (context:fork — former agent)
  3. Action (former command — folded into the domain skill)
  4. Hook

Select type (1-4):
```

## Templates

Located in `templates/`:

- `skill/SKILL.md` — sub-skill template
- `agent/agent.md` — context:fork worker skill template
- `plugin/command-with-agent.md` — action stub (domain-skill action → worker dispatch)
- `specialist/specialist.json` — specialist manifest template (personas → worker skills)
- `hook/hooks.json`, `hook/script.py` — hook templates

### Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{name}}` | Component name (kebab-case) | `risk-assessor` |
| `{{title}}` | Title Case | `Risk Assessor` |
| `{{skill_name}}` | Worker skill dash name | `wicked-garden-qe-risk-assessor` |
| `{{description}}` | Description | `Assess project risks` |
| `{{domain}}` | Area of expertise / domain | `qe` |
| `{{tools}}` | Rendered allowed-tools list | `"Read", "Write"` |

## Validation

Generated names are validated:

- **Format**: kebab-case (lowercase, numbers, hyphens)
- **Length**: max 64 characters
- **Reserved prefixes**: cannot start with `claude-code-`, `anthropic-`, `official-`, `agent-skills`
- **Domain**: must be a known domain (from `.claude-plugin/components.json`)

Run the repo structural validator afterwards:

```bash
python3 scripts/ci/validate.py
```

## Next Steps After Scaffolding

1. **Review generated files** — customize templates to your needs
2. **Wire the surface** — add a worker's dispatch to a domain router action, or add a sub-skill to its domain router's navigation
3. **Implement functionality** — add the actual rubric/logic
4. **Validate** — `python3 scripts/ci/validate.py`
5. **Sync the manifest** — `python3 scripts/ci/sync_components.py`

## Troubleshooting

### "Skill already exists" / "Worker skill already exists"

The target directory already exists. Choose a different name or edit the
existing skill.

### "Invalid domain"

The domain must be one of the known domains (from
`.claude-plugin/components.json` "domains"). Scaffold the domain router skill
first if the domain is genuinely new.

### "Invalid name format"

Names must be lowercase, numbers and hyphens only, not start/end with a hyphen,
and be at most 64 characters.

- ✓ `risk-assessor`, `my-worker-123`
- ✗ `Risk-Assessor` (uppercase), `my_worker` (underscore), `-worker` (leading hyphen)

## References

- `SKILL.md` — full documentation
- Naming conventions: `.claude/CLAUDE.md` (Naming Conventions section)
- Component manifest: `.claude-plugin/components.json`
- Cross-tool context: Plugins should load `AGENTS.md` before `CLAUDE.md` when reading project descriptors. `AGENTS.md` is read-only.
