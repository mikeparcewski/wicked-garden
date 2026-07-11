---
name: scaffold
description: |
  Component scaffolding toolkit for creating skills, context:fork worker skills, and hooks within the unified wicked-garden plugin.
  Generates complete, valid structures that pass validation out-of-the-box.
  Use when creating new domain components, setting up boilerplate, or ensuring proper structure from the start.
---

# Scaffold Tool

Quick-start generator for wicked-garden components. The plugin is **skills-only**:
the former `commands/` and `agents/` trees were absorbed into `skills/`, so this
tool scaffolds skills, workers, and hooks — never a `commands/` or `agents/` file.

## Purpose

Generates production-ready component structures within the unified plugin:
- **Skills** — a sub-skill `skills/{domain}/{name}/SKILL.md` (Tier-2 navigation + refs/)
- **Worker skills** — a standalone `context: fork` worker `skills/{domain}-{role}/SKILL.md` (the former "agent"), dispatched via `Skill(skill="wicked-garden-{domain}-{role}")`
- **Hooks** — hooks.json entries with Python scripts

Former **commands** are now **actions** of the consolidated per-domain router
skill (`skills/{domain}/SKILL.md`); the `command` subcommand is retired and only
prints guidance for adding an action.

All scaffolded components pass validation immediately.

## Usage

### Interactive Mode

```bash
python .claude/skills/scaffolding/scripts/scaffold.py

# Interactive prompts:
# > Component type? (1 skill / 2 worker / 3 action-guidance / 4 hook)
# > Domain? (crew, engineering, platform, ...)
# > Name? (kebab-case)
# > Description?

# Result (skill):
# Skill created: skills/crew/my-skill/
# Skill id: my-skill (routed by the crew domain skill)
```

### Command Line Mode

```bash
# Skill (a sub-skill under a domain)
python .claude/skills/scaffolding/scripts/scaffold.py skill \
  --name my-skill \
  --domain crew \
  --description "What this skill does" \
  --use-when "trigger conditions"

# Worker skill (context:fork — the former agent). `agent` is a back-compat alias.
python .claude/skills/scaffolding/scripts/scaffold.py worker \
  --name my-worker \
  --domain platform \
  --description "What this worker does" \
  --tools "Read,Write,Bash"

# Action (former command) — RETIRED. Prints guidance to add the action to the
# domain router skill; writes no file.
python .claude/skills/scaffolding/scripts/scaffold.py command \
  --name my-action \
  --domain engineering \
  --description "What this action does"

# Hook
python .claude/skills/scaffolding/scripts/scaffold.py hook \
  --event PreToolUse \
  --script validate-tool-use \
  --description "Validates tool usage"
```

## Generated Paths

Components are placed in the skills-only layout at the repo root:

```
wicked-garden/                     # Plugin root
├── skills/{domain}/{name}/        # Sub-skills
│   └── SKILL.md
├── skills/{domain}-{role}/        # Worker skills (context:fork — former agents)
│   └── SKILL.md
├── hooks/scripts/{name}.py        # Hook scripts
└── hooks/hooks.json               # Hook bindings (updated)
```

There is no `commands/` or `agents/` tree.

### Naming Conventions

- Sub-skill id: the leaf directory name, routed by its domain skill
- Worker skill name: `wicked-garden-{domain}-{role}` (dash-separated), declared
  in frontmatter `name:` and dispatched via `Skill(skill="…")`
- Domain router skill name: `wicked-garden-{domain}`

#### Action stub (former command-with-agent)

A former "command that dispatched to an agent" is now an **action of the domain
router skill** that dispatches to a worker skill. Copy the stub in
`templates/plugin/command-with-agent.md` into the router body and wire it with:

```
Skill(skill="wicked-garden-{domain}-{role}", args="… | target: <target>")
```

### Skill Template

```markdown
---
name: {skill-name}
description: |
  What this skill does (capabilities).
  Use when [trigger conditions and keywords].
---

# {Skill Title}

Brief introduction to the skill's purpose.

## Purpose
What problem this skill solves.

## Usage
Examples.

## References
- Related docs / source files
```

### Worker Skill Template (context:fork)

```markdown
---
name: wicked-garden-{domain}-{role}
description: What this worker specializes in
context: fork
allowed-tools: ["Read", "Write", "Bash"]
model: sonnet
color: blue
---

# {Worker Title}

You are the {Worker Title} worker, specialized in {domain}. You run in an
isolated context:fork subagent, dispatched via Skill(skill="…").

## Expertise
- Capability 1 / 2 / 3

## Working Style
1. Step 1 / 2 / 3

## Quality Standards
- Standard 1 / 2

## Constraints
- Constraint 1 / 2
```

`context: fork` worker skills are exempt from the ≤200-line Tier-2 cap — they
load into an isolated subagent context, not the parent.

### Hook Template

#### hooks.json

```json
{
  "hooks": [
    {
      "event": "{event}",
      "script": "scripts/{script-name}.py",
      "description": "{description}",
      "enabled": true
    }
  ]
}
```

#### Hook Script

```python
#!/usr/bin/env python3
"""
{Event} hook for {plugin-name}.

Exit codes:
  0 - Success, continue
  2 - Blocking error (message sent to Claude)
  Other - Non-blocking error (logged)
"""

import sys
import json

def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    # Hook logic here. Access: data['tool'], data['arguments'], data['context']
    if data.get('tool') == 'Bash':
        command = data.get('arguments', {}).get('command', '')
        if 'rm -rf /' in command:
            print("Blocked dangerous command: rm -rf /")
            sys.exit(2)  # Block execution

    sys.exit(0)

if __name__ == "__main__":
    main()
```

## Valid Domains

Domains are discovered dynamically from `.claude-plugin/components.json`
("domains"), falling back to the top-level directories under `skills/`
(excluding the `{domain}-{role}` worker dirs). New domains are valid as soon as
they appear in the manifest / skills tree.

Current domains: agentic, crew, data, engineering, jam, mem, persona, platform,
product, qe, search, smaht.

### Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{name}}` | Component name (kebab-case) | `risk-assessor` |
| `{{title}}` | Component name (Title Case) | `Risk Assessor` |
| `{{skill_name}}` | Worker skill dash name | `wicked-garden-qe-risk-assessor` |
| `{{description}}` | Brief description | `Assess project risks` |
| `{{domain}}` | Area of expertise / domain | `qe` |
| `{{tools}}` | Allowed-tools list (rendered) | `"Read", "Write"` |

## Best Practices

### Naming

- Use kebab-case for all names, max 64 characters
- No reserved prefixes (`claude-code-`, `anthropic-`, `official-`)
- Worker skills carry the dash-qualified `wicked-garden-{domain}-{role}` name

### Structure

- Put reusable logic in `scripts/`
- Use `skills/{domain}/` for the domain router + its actions (former commands)
- Use `skills/{domain}-{role}/` for context:fork worker skills (former agents)
- Use `hooks/` for deterministic event automation

### Documentation

- Write clear, concise descriptions and include usage examples
- Document dependencies and configuration options

### Security

- All scripts should use `${CLAUDE_PLUGIN_ROOT}` for paths
- Quote shell variables: `"$VAR"`
- Validate input before processing; no hardcoded secrets

## Examples

### Sub-skill only

```bash
python .claude/skills/scaffolding/scripts/scaffold.py skill \
  --name validation-patterns \
  --domain engineering \
  --description "Input validation patterns" \
  --use-when "reviewing input handling"

# Result:
# skills/engineering/validation-patterns/SKILL.md
```

### Worker skill (context:fork)

```bash
python .claude/skills/scaffolding/scripts/scaffold.py worker \
  --name risk-assessor \
  --domain qe \
  --description "Assesses release risk" \
  --tools "Read,Bash"

# Result:
# skills/qe-risk-assessor/SKILL.md   (name: wicked-garden-qe-risk-assessor, context: fork)
# Dispatch via: Skill(skill="wicked-garden-qe-risk-assessor")
```

### Hook with Script

```bash
python .claude/skills/scaffolding/scripts/scaffold.py hook \
  --event PreToolUse \
  --script validate-tool-use \
  --description "Validate tool use before execution"

# Result:
# hooks/hooks.json (updated)
# hooks/scripts/validate-tool-use.py
```

## References

- Naming conventions: `.claude/CLAUDE.md` (Naming Conventions section)
- Component manifest: `.claude-plugin/components.json` (domains + skills)
- Cross-tool context: Plugins that read project descriptor files should load `AGENTS.md` before `CLAUDE.md` (general → specific). `AGENTS.md` is read-only.
