---
name: scaffold
description: |
  Component scaffolding toolkit for creating skills, agents, commands, and hooks within the unified wicked-garden plugin.
  Generates complete, valid structures that pass validation out-of-the-box.
  Use when creating new domain components, setting up boilerplate, or ensuring proper structure from the start.
---

# Scaffold Tool

Quick-start generator for wicked-garden domain components.

## Purpose

Generates production-ready component structures within the unified plugin:
- **Skills** - SKILL.md with proper YAML frontmatter and refs/ directory
- **Agents** - Agent .md files with tools and frontmatter
- **Commands** - Slash commands with YAML frontmatter
- **Hooks** - hooks.json entries with Python scripts

All scaffolded components pass validation immediately.

## Usage

### Interactive Mode

```bash
python .claude/skills/scaffolding/scripts/scaffold.py

# Interactive prompts:
# > Component type? (skill/agent/command/hook)
# > Domain? (crew, engineering, platform, ...)
# > Name? (kebab-case)
# > Description?

# Result:
# Skill created: skills/crew/my-skill/
# Namespace: wicked-garden:crew:my-skill
```

### Command Line Mode

```bash
# Skill
python .claude/skills/scaffolding/scripts/scaffold.py skill \
  --name my-skill \
  --domain crew \
  --description "What this skill does"

# Agent
python .claude/skills/scaffolding/scripts/scaffold.py agent \
  --name my-agent \
  --domain platform \
  --description "What this agent does" \
  --tools "Read,Write,Bash"

# Command
python .claude/skills/scaffolding/scripts/scaffold.py command \
  --name my-command \
  --domain engineering \
  --description "What this command does"

# Hook
python .claude/skills/scaffolding/scripts/scaffold.py hook \
  --event PreToolUse \
  --script validate-tool-use \
  --description "Validates tool usage"
```

## Generated Paths

Components are placed in domain-specific subdirectories:

```
wicked-garden/                    # Plugin root
├── skills/{domain}/{name}/       # Skills
│   └── SKILL.md
├── agents/{domain}/{name}.md     # Agents
├── commands/{domain}/{name}.md   # Commands
├── hooks/scripts/{name}.py       # Hook scripts
└── hooks/hooks.json              # Hook bindings (updated)
```

### Naming Conventions

- Commands: `wicked-garden:{domain}:{command}` (colon-separated)
- Agents: `wicked-garden:{domain}/{agent}` (slash for agent path)
- Skills: `wicked-garden:{domain}:{skill}` (colon-separated)

#### Command Template Selection

When scaffolding a command, the tool checks if `agents/{domain}/*.md` exists:
- **If agents exist**: Uses `command-with-agent.md` template with `Task(subagent_type=...)` dispatch
- **If no agents**: Uses inline `command.md` template

This ensures new commands follow the delegation standard from the start.

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

## Patterns

Common patterns this skill enables:
- Pattern 1
- Pattern 2

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

## Valid Domains

The 16 domains in wicked-garden:

**Workflow & Intelligence**: crew, smaht, mem, search, jam, kanban
**Specialist Disciplines**: engineering, product, platform, qe, data, delivery, agentic
**Infrastructure & Tools**: scenarios, patch, observability

### Template Variables

Available in all `.tpl` files:

| Variable | Description | Example |
|----------|-------------|---------|
| `{name}` | Component name (kebab-case) | `risk-assessor` |
| `{Name}` | Component name (Title Case) | `Risk Assessor` |
| `{NAME}` | Component name (UPPER_CASE) | `RISK_ASSESSOR` |
| `{description}` | Brief description | `Assess project risks` |
| `{domain}` | Domain name | `qe` |

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
  --name wicked-perf-analyzer \
  --description "Performance analysis and optimization" \
  --with-commands analyze,optimize \
  --with-skills analysis,optimization \
  --with-agents optimizer \
  --author "Your Name"

# Result:
# plugins/wicked-perf-analyzer/
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
