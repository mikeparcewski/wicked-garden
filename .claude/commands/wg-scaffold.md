---
description: Scaffold a new domain component (skill, agent, command, or hook) in the unified wicked-garden plugin
argument-hint: [type] [name] --domain [domain] [description]
allowed-tools: Read, Write, Bash(python3:*, mkdir:*, ls:*)
---

Scaffold a new component within the unified wicked-garden plugin using the development tools.

## Arguments

Parse the provided arguments: $ARGUMENTS

Expected format: `[type] [name] --domain [domain] [description]`
- **type**: One of `skill`, `agent`, `command`, or `hook`
- **name**: kebab-case name for the component
- **--domain**: Target domain (e.g., `crew`, `qe`, `engineering`, `mem`)
- **description**: Brief description (can be in quotes for multi-word)

## If arguments are provided

Run the scaffold script:

```bash
python3 .claude/skills/scaffolding/scripts/scaffold.py $ARGUMENTS
```

After scaffolding:
1. Show the created directory structure
2. Explain what files were generated
3. Suggest next steps (customize, validate, test)

## If arguments are missing or incomplete

Enter interactive mode - ask the user:

1. What type of component? (skill, agent, command, hook)
2. Which domain? (crew, engineering, platform, qe, product, delivery, data, jam, mem, search, smaht, kanban, startah, workbench, scenarios, patch, agentic, observability)
3. What should it be named? (kebab-case)
4. Brief description of purpose

Then run the scaffold with gathered information.

## Component Types and Generated Paths

### Skill
```bash
/wg-scaffold skill my-skill --domain crew "Brief description"
```
Creates:
```
skills/crew/my-skill/
├── SKILL.md          # ≤200 lines entry point
└── refs/             # Progressive disclosure (add as needed)
```

### Agent
```bash
/wg-scaffold agent my-agent --domain platform "Brief description"
```
Creates:
```
agents/platform/my-agent.md    # Agent with frontmatter
```
Agent subagent_type: `wicked-garden:platform/my-agent`

### Command
```bash
/wg-scaffold command my-command --domain engineering "Brief description"
```
Creates:
```
commands/engineering/my-command.md    # Command with YAML frontmatter
```
Command namespace: `wicked-garden:engineering:my-command`

### Hook
```bash
/wg-scaffold hook my-hook --event PreToolUse "Brief description"
```
Creates:
```
hooks/scripts/my-hook.py    # Hook script (stdlib-only)
```
Updates `hooks/hooks.json` with the new event binding.

### Agent Template

Agents include:
```yaml
---
name: persona-name
description: What this agent does
tools: [Read, Write, Bash, Grep, Glob]
model: sonnet
color: blue  # blue, green, purple, orange, teal
---
```

### Event Format

Events follow: `[domain:entity:action:status]`
- domain: domain name (e.g., `qe`, `crew`, `platform`)
- entity: what's affected (e.g., `review`, `analysis`)
- action: what happened (e.g., `completed`, `started`)
- status: result (e.g., `success`, `error`, `warning`)

## Valid Domains

The 18 domains in wicked-garden:

**Workflow & Intelligence**: crew, smaht, mem, search, jam, kanban
**Specialist Disciplines**: engineering, product, platform, qe, data, delivery, agentic
**Infrastructure & Tools**: startah, workbench, scenarios, patch, observability

## After successful scaffolding

Recommend running validation:
```
/wg-check
```

For full quality assessment:
```
/wg-check --full
```
