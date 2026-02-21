---
name: scaffold
description: |
  Component scaffolding toolkit for creating plugins, skills, agents, and hooks.
  Generates complete, valid structures that pass validation out-of-the-box.
  Use when creating new marketplace components, setting up boilerplate, or ensuring proper structure from the start.
---

# Scaffold Tool

Quick-start generator for Something Wicked marketplace components.

## Purpose

Generates production-ready component structures:
- **Plugins** - Full plugin with commands/, agents/, skills/, scripts/
- **Skills** - SKILL.md with proper YAML frontmatter and examples
- **Agents** - Agent .md files with tools and frontmatter
- **Hooks** - hooks.json with event handlers

All scaffolded components pass validation immediately.

## Usage

### Interactive Mode

```bash
cd tools/scaffold
python scripts/scaffold.py

# Interactive prompts:
# > Component type? (plugin/skill/agent/hook)
# > Name? (kebab-case)
# > Description?
# > [Component-specific questions...]

# Result:
# ✓ Created plugins/my-plugin/
# ✓ All files generated
# ✓ Validation passed
```

### Command Line Mode

```bash
# Plugin
python scripts/scaffold.py plugin \
  --name wicked-new-plugin \
  --description "Brief description" \
  --with-commands \
  --with-skills \
  --with-agents

# Skill
python scripts/scaffold.py skill \
  --name my-skill \
  --plugin wicked-existing-plugin \
  --description "What this skill does"

# Agent
python scripts/scaffold.py agent \
  --name my-agent \
  --plugin wicked-existing-plugin \
  --tools "Read,Write,Bash"

# Hook
python scripts/scaffold.py hook \
  --name PreToolUse \
  --plugin wicked-existing-plugin \
  --script validate-tool-use.py
```

## Templates

### Plugin Template Structure

```
plugins/{name}/
├── .claude-plugin/
│   └── plugin.json              # Metadata with name, version, description
├── commands/                     # Optional: slash commands
│   └── example.md
├── agents/                       # Optional: subagents
│   └── example-agent.md
├── skills/                       # Optional: expertise modules
│   └── example-skill/
│       └── SKILL.md
├── hooks/                        # Optional: event handlers
│   ├── hooks.json
│   └── scripts/
│       └── pre-tool-use.py
├── scripts/                      # Helper scripts
│   └── setup.sh
├── README.md                     # Full documentation
└── .gitignore                    # Ignore patterns
```

#### Command Template Selection

When scaffolding a command, check if the target plugin has `agents/*.md` files:
- **If agents exist**: Use `templates/plugin/command-with-agent.md` — includes `Task(subagent_type=...)` dispatch pattern
- **If no agents**: Use `templates/plugin/command.md` — inline execution pattern

This ensures new commands follow the delegation standard from the start.

#### Generated plugin.json

```json
{
  "name": "{name}",
  "version": "0.1.0",
  "description": "{description}",
  "author": "Wicked Agile Team",
  "license": "MIT",
  "marketplace": "wicked-garden",
  "requires": [],
  "tags": []
}
```

#### Generated README.md

```markdown
# {Name}

{Description}

## Installation

Part of the Wicked Garden marketplace:

\`\`\`bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install {name}@wicked-garden
\`\`\`

## Usage

### Commands

- \`/{name}:command\` - Description

### Skills

- \`/{name}:skill\` - Description

## Configuration

[If applicable]

## Examples

[Usage examples]

## Integration

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-cache | Faster repeated operations | Re-computes each time |
| wicked-mem | Cross-session memory | Session-only memory |

## Dependencies

[If any external dependencies]

## License

MIT
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

### Example 1

\`\`\`python
# Code example
\`\`\`

### Example 2

\`\`\`bash
# Shell example
\`\`\`

## Patterns

Common patterns this skill enables:
- Pattern 1
- Pattern 2

## Integration

How to use this skill with other tools:
- Integration 1
- Integration 2

## References

- Related docs
- Source files
```

### Agent Template

```markdown
---
description: What this agent specializes in
tools: ["Read", "Write", "Bash"]
---

# {Agent Name}

You are {agent-name}, specialized in {domain}.

## Expertise

Your core capabilities:
- Capability 1
- Capability 2
- Capability 3

## Working Style

How you approach tasks:
1. Step 1
2. Step 2
3. Step 3

## Quality Standards

What defines success:
- Standard 1
- Standard 2

## Constraints

What you avoid:
- Constraint 1
- Constraint 2

## Tone

[Optional: if agent has specific communication style]
```

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
import os

def main():
    # Read hook data from stdin
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)

    # Hook logic here
    # Access: data['tool'], data['arguments'], data['context']

    # Example validation
    if data.get('tool') == 'Bash':
        command = data.get('arguments', {}).get('command', '')
        if 'rm -rf /' in command:
            print("Blocked dangerous command: rm -rf /")
            sys.exit(2)  # Block execution

    # Allow execution
    sys.exit(0)

if __name__ == "__main__":
    main()
```

## Customization

### Custom Templates

Create `tools/scaffold/templates/custom/`:

```
templates/custom/
├── my-plugin-template/
│   ├── template.json         # Template metadata
│   └── files/                # Template files
│       ├── plugin.json.tpl
│       └── README.md.tpl
```

#### template.json

```json
{
  "name": "my-plugin-template",
  "description": "Custom plugin template for X",
  "type": "plugin",
  "variables": [
    { "name": "plugin_name", "prompt": "Plugin name?" },
    { "name": "author", "prompt": "Author?", "default": "Community" }
  ],
  "files": [
    { "src": "plugin.json.tpl", "dest": ".claude-plugin/plugin.json" },
    { "src": "README.md.tpl", "dest": "README.md" }
  ]
}
```

### Template Variables

Available in all `.tpl` files:

| Variable | Description | Example |
|----------|-------------|---------|
| `{name}` | Component name (kebab-case) | `wicked-memory` |
| `{Name}` | Component name (Title Case) | `Wicked Memory` |
| `{NAME}` | Component name (UPPER_CASE) | `WICKED_MEMORY` |
| `{description}` | Brief description | `Unified caching system` |
| `{author}` | Author name | `Something Wicked Community` |
| `{date}` | Current date (ISO) | `2026-01-13` |
| `{year}` | Current year | `2026` |

## Validation Integration

Scaffold automatically validates generated components:

```python
# In scaffold.py
def scaffold_component(component_type, **options):
    # Generate files
    create_structure(component_type, options)

    # Auto-validate
    from validate import validate_component

    result = validate_component(options['path'])
    if not result['valid']:
        print("Warning: Generated component has validation issues:")
        for error in result['errors']:
            print(f"  - {error}")
    else:
        print("✓ Component passes validation")
```

## Batch Scaffolding

Create multiple components from config:

```yaml
# scaffold-config.yml
components:
  - type: skill
    name: caching
    plugin: wicked-memory
    description: Cache management patterns

  - type: skill
    name: task-api
    plugin: wicked-trackah
    description: Task CRUD operations

  - type: agent
    name: cache-optimizer
    plugin: wicked-memory
    tools: [Read, Write, Bash]
```

```bash
python scripts/scaffold.py batch scaffold-config.yml
# ✓ Created 2 skills, 1 agent
```

## Best Practices

### Naming

- Use kebab-case for all names
- Max 64 characters
- No reserved prefixes (`claude-code-`, `anthropic-`, `official-`)
- Plugin names should start with `wicked-` for marketplace consistency

### Structure

- Put reusable logic in `scripts/`
- Use `commands/` for user-facing operations
- Use `skills/` for Claude expertise
- Use `agents/` for specialized subagents

### Documentation

- Write clear, concise descriptions
- Include usage examples
- Document dependencies
- Explain configuration options

### Security

- All scripts should use `${CLAUDE_PLUGIN_ROOT}` for paths
- Quote shell variables: `"$VAR"`
- Validate input before processing
- No hardcoded secrets

## Examples

### Full Plugin

```bash
python scripts/scaffold.py plugin \
  --name wicked-cache-analyzer \
  --description "Cache performance analysis and optimization" \
  --with-commands analyze,optimize \
  --with-skills analysis,optimization \
  --with-agents optimizer \
  --author "Your Name"

# Result:
# plugins/wicked-cache-analyzer/
# ├── .claude-plugin/plugin.json
# ├── commands/
# │   ├── analyze.md
# │   └── optimize.md
# ├── agents/
# │   └── optimizer.md
# ├── skills/
# │   ├── analysis/SKILL.md
# │   └── optimization/SKILL.md
# ├── scripts/
# │   └── setup.sh
# └── README.md
```

### Skill Only

```bash
python scripts/scaffold.py skill \
  --name validation-patterns \
  --plugin wicked-memory \
  --description "Input validation patterns for cache keys"

# Result:
# plugins/wicked-memory/skills/validation-patterns/
# └── SKILL.md
```

### Hook with Script

```bash
python scripts/scaffold.py hook \
  --name PreToolUse \
  --plugin wicked-crew \
  --description "Validate tool use before execution" \
  --script validate-tool-use.py

# Result:
# plugins/wicked-crew/hooks/
# ├── hooks.json (updated)
# └── scripts/
#     └── validate-tool-use.py
```

## References

- Requirements: `.something-wicked/wicked-feature-dev/specs/something-wicked-v2/requirements.md` (FR-005)
- Design: `.something-wicked/wicked-feature-dev/specs/something-wicked-v2/design.md` (tools/ section)
- Naming conventions: `CLAUDE.md` (Naming Conventions section)
- Component patterns: `CLAUDE.md` (Component Patterns section)
- Cross-tool context: Plugins that read project descriptor files should load `AGENTS.md` before `CLAUDE.md` (general → specific). `AGENTS.md` is read-only.
