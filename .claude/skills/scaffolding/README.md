# Scaffold Tool

Component scaffolding for Wicked Garden marketplace - generates plugins, skills, agents, and hooks with proper structure.

## Quick Start

```bash
cd tools/scaffold

# Interactive mode
python3 scripts/scaffold.py

# Command line mode
python3 scripts/scaffold.py plugin --name wicked-new-plugin --description "My plugin"
python3 scripts/scaffold.py skill --name my-skill --plugin wicked-memory --description "My skill"
python3 scripts/scaffold.py agent --name my-agent --plugin wicked-memory --description "My agent"
python3 scripts/scaffold.py hook --event PreToolUse --plugin wicked-memory --script my-hook --description "My hook"
```

## Usage

### Plugin

Creates a complete plugin structure with optional components:

```bash
python3 scripts/scaffold.py plugin \
  --name wicked-my-plugin \
  --description "Brief description" \
  --author "Your Name" \
  --with-commands \
  --with-skills \
  --with-agents \
  --with-hooks
```

Generated structure:
```
plugins/wicked-my-plugin/
├── .claude-plugin/
│   └── plugin.json
├── commands/          # If --with-commands
│   └── example.md
├── agents/            # If --with-agents
│   └── example-agent.md
├── skills/            # If --with-skills
│   └── example-skill/
│       └── SKILL.md
├── hooks/             # If --with-hooks
│   ├── hooks.json
│   └── scripts/
│       └── example-hook.py
├── scripts/
├── README.md
└── .gitignore
```

### Skill

Creates a skill in an existing plugin:

```bash
python3 scripts/scaffold.py skill \
  --name my-skill \
  --plugin wicked-memory \
  --description "What this skill does" \
  --use-when "when to use it"
```

Generated structure:
```
plugins/wicked-memory/skills/my-skill/
└── SKILL.md
```

### Agent

Creates an agent in an existing plugin:

```bash
python3 scripts/scaffold.py agent \
  --name my-agent \
  --plugin wicked-memory \
  --description "What this agent does" \
  --domain "domain of expertise" \
  --tools "Read,Write,Bash"
```

Generated structure:
```
plugins/wicked-memory/agents/
└── my-agent.md
```

### Hook

Creates a hook in an existing plugin:

```bash
python3 scripts/scaffold.py hook \
  --event PreToolUse \
  --plugin wicked-memory \
  --script validate-tools \
  --description "Validate tool use" \
  --matcher "Write|Edit|Bash"
```

Generated structure:
```
plugins/wicked-memory/hooks/
├── hooks.json
└── scripts/
    └── validate-tools.py
```

Valid events:
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution
- `UserPromptSubmit` - After user submits prompt
- `Stop` - When session stops
- `SubagentStop` - When subagent stops
- `SessionStart` - When session starts
- `SessionEnd` - When session ends
- `PreCompact` - Before context compaction
- `Notification` - On notifications

## Interactive Mode

Run without arguments for interactive prompts:

```bash
python3 scripts/scaffold.py

=== Component Scaffold ===

Component types:
  1. Plugin
  2. Skill
  3. Agent
  4. Hook

Select type (1-4): 1

=== Plugin Scaffold ===

Plugin name (kebab-case): wicked-test
Description: Test plugin
Author [Mike Parcewski]:
Include example command? (y/n) [n]: y
Include example skill? (y/n) [n]: y
Include example agent? (y/n) [n]: n
Include example hooks? (y/n) [n]: n

Creating plugin: wicked-test
  ✓ Created .claude-plugin/plugin.json
  ✓ Created README.md
  ✓ Created .gitignore
  ✓ Created commands/example.md
  ✓ Created skills/example-skill/SKILL.md

✓ Plugin created: /path/to/plugins/wicked-test
```

## Templates

Templates are located in `templates/`:

- `plugin/` - Plugin templates
  - `plugin.json` - Manifest
  - `README.md` - Documentation
  - `command.md` - Command template
  - `gitignore` - Git ignore patterns
- `skill/` - Skill template
  - `SKILL.md` - Skill documentation
- `agent/` - Agent template
  - `agent.md` - Agent definition
- `hook/` - Hook templates
  - `hooks.json` - Hooks manifest
  - `script.py` - Hook script

### Template Variables

Variables are replaced during generation:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{name}}` | Component name (kebab-case) | `wicked-memory` |
| `{{Name}}` | Title Case | `Wicked Memory` |
| `{{NAME}}` | UPPER_CASE | `WICKED_MEMORY` |
| `{{description}}` | Description | `Unified caching system` |
| `{{author}}` | Author name | `Something Wicked Community` |

## Validation

All generated names are validated:

- **Format**: kebab-case (lowercase, numbers, hyphens)
- **Length**: Max 64 characters
- **Reserved prefixes**: Cannot start with `claude-code-`, `anthropic-`, `official-`, `agent-skills`
- **Plugin convention**: Should start with `wicked-` for marketplace consistency

## Examples

### Full Plugin

```bash
python3 scripts/scaffold.py plugin \
  --name wicked-perf-optimizer \
  --description "Performance analysis and optimization" \
  --author "John Doe" \
  --with-commands \
  --with-skills \
  --with-agents
```

### Skill Only

```bash
python3 scripts/scaffold.py skill \
  --name validation-patterns \
  --plugin wicked-memory \
  --description "Input validation patterns for cache keys" \
  --use-when "validating cache keys or namespace names"
```

### Agent Only

```bash
python3 scripts/scaffold.py agent \
  --name cache-optimizer \
  --plugin wicked-memory \
  --description "Analyzes cache usage and suggests optimizations" \
  --domain "cache optimization" \
  --tools "Read,Bash"
```

### Hook Only

```bash
python3 scripts/scaffold.py hook \
  --event PreToolUse \
  --plugin wicked-memory \
  --script validate-namespace \
  --description "Validate namespace names before cache operations" \
  --matcher "Bash"
```

## Integration with Validation

Generated components are designed to pass validation:

```bash
# After scaffolding
cd tools/validate
python3 scripts/validate.py ../../plugins/wicked-new-plugin

# Should output:
# ✓ Structure validation passed
# ✓ Security validation passed
# ✓ Compliance validation passed
```

## Next Steps After Scaffolding

1. **Review generated files** - Customize templates to your needs
2. **Update README.md** - Add specific usage examples and documentation
3. **Implement functionality** - Add actual logic to commands/skills/agents
4. **Test thoroughly** - Ensure everything works as expected
5. **Validate** - Run validation tools to ensure compliance
6. **Update marketplace.json** - Add plugin to marketplace registry

## Troubleshooting

### "Plugin already exists"

The target directory already exists. Either:
- Choose a different name
- Delete the existing directory
- Update the existing plugin manually

### "Plugin not found"

When adding skills/agents/hooks, the plugin must exist. Run:
```bash
python3 scripts/scaffold.py plugin --name wicked-my-plugin --description "Description"
```

### "Invalid name format"

Names must be:
- Lowercase
- Numbers and hyphens only
- Cannot start/end with hyphen
- Max 64 characters

Examples:
- ✓ `wicked-memory`
- ✓ `my-plugin-123`
- ✗ `My-Plugin` (uppercase)
- ✗ `my_plugin` (underscore)
- ✗ `-wicked` (starts with hyphen)

## References

- SKILL.md - Full documentation
- Requirements: `.something-wicked/wicked-feature-dev/specs/something-wicked-v2/requirements.md` (FR-005)
- Design: `.something-wicked/wicked-feature-dev/specs/something-wicked-v2/design.md`
- Naming conventions: `CLAUDE.md` (Naming Conventions section)
- Cross-tool context: Plugins should load `AGENTS.md` before `CLAUDE.md` when reading project descriptors. `AGENTS.md` is read-only.
