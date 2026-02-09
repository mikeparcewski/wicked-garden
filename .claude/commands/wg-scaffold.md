---
description: Scaffold a new marketplace component (plugin, skill, agent, or hook)
argument-hint: [type] [name] [description]
allowed-tools: Read, Write, Bash(python3:*, mkdir:*, ls:*)
---

Scaffold a new marketplace component using the wicked-garden development tools.

## Arguments

Parse the provided arguments: $ARGUMENTS

Expected format: `[type] [name] [description]`
- **type**: One of `plugin`, `specialist`, `skill`, `agent`, or `hook`
- **name**: kebab-case name for the component (plugins should start with `wicked-`)
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

1. What type of component? (plugin, specialist, skill, agent, hook)
2. What should it be named? (kebab-case, plugins should start with `wicked-`)
3. Brief description of purpose

Then run the scaffold with gathered information.

## For plugins with additional options

If creating a plugin, ask if they want to include:
- Example commands (--with-commands)
- Example skills (--with-skills)
- Example agents (--with-agents)
- Example hooks (--with-hooks)

## Specialist Plugins (v3)

For specialist plugins that integrate with wicked-crew:

```bash
/wg-scaffold specialist wicked-myspec "My specialist description"
```

This generates:
```
plugins/wicked-myspec/
├── .claude-plugin/
│   ├── plugin.json           # Plugin manifest
│   └── specialist.json       # Specialist contract (v3)
├── agents/
│   ├── persona-1.md          # Agent per persona
│   └── persona-2.md
├── hooks/
│   └── hooks.json            # Event subscriptions
├── skills/
│   └── primary-skill/
│       ├── SKILL.md          # ≤200 lines
│       └── refs/             # Progressive disclosure
├── scripts/
│   └── helper.py
└── README.md
```

### Specialist Roles

Valid roles for `specialist.json`:
- `ideation` - Brainstorming, exploration (e.g., wicked-jam)
- `business-strategy` - ROI, value analysis (e.g., wicked-product)
- `project-management` - Delivery tracking (e.g., wicked-delivery)
- `quality-engineering` - Testing, QE (e.g., wicked-qe)
- `devsecops` - Security, CI/CD (e.g., wicked-platform)
- `engineering` - Code implementation (e.g., wicked-engineering)
- `architecture` - System design (e.g., wicked-arch)
- `ux` - User experience (e.g., wicked-ux)
- `product` - Product management (e.g., wicked-product)
- `compliance` - Governance, audit (e.g., wicked-compliance)
- `data-engineering` - Data, ML (e.g., wicked-data)

### Agent Template (v3)

Agents now include:
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

Events follow: `[namespace:entity:action:status]`
- namespace: plugin short name (e.g., `qe`, `arch`, `ux`)
- entity: what's affected (e.g., `review`, `analysis`)
- action: what happened (e.g., `completed`, `started`)
- status: result (e.g., `success`, `error`, `warning`)

## After successful scaffolding

Recommend running validation:
```
/wg-validate [path-to-new-component]
```

For quality assessment:
```
/wg-score [path-to-new-component]
```
