---
name: plugin-json-schema
description: |
  Official Claude Code plugin.json schema reference and validation guide.
  Use when creating or troubleshooting plugin.json manifest files.
  Covers all fields, auto-discovery behavior, path formats, and common validation errors.
---

# Claude Code plugin.json Schema Reference

Complete reference for Claude Code plugin manifest files.

## Minimal Valid plugin.json

For plugins using standard directory structures, this is all you need:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Brief description of the plugin"
}
```

**Auto-discovery** will automatically load components from standard locations.

## Complete Schema

```json
{
  "name": "plugin-name",
  "version": "1.2.0",
  "description": "Brief plugin description",
  "author": {
    "name": "Author Name",
    "email": "author@example.com",
    "url": "https://github.com/author"
  },
  "homepage": "https://docs.example.com/plugin",
  "repository": "https://github.com/author/plugin",
  "license": "MIT",
  "keywords": ["keyword1", "keyword2"],
  "commands": "./custom/commands/",
  "agents": "./custom/agents/",
  "skills": "./custom/skills/",
  "hooks": "./config/hooks.json",
  "mcpServers": "./mcp-config.json",
  "outputStyles": "./styles/",
  "lspServers": "./.lsp.json"
}
```

## Field Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier, kebab-case, max 64 chars |
| `version` | string | Semantic version (x.y.z) |
| `description` | string | Brief explanation of the plugin |

### Optional Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `author` | object | `{name, email?, url?}` |
| `homepage` | string | Documentation URL |
| `repository` | string | Source code URL |
| `license` | string | License identifier (MIT, Apache-2.0, etc.) |
| `keywords` | array | Discovery tags (strings) |

### Component Path Fields

| Field | Type | Auto-Discovery Location |
|-------|------|-------------------------|
| `commands` | string \| array | `commands/` |
| `agents` | string \| array | `agents/` |
| `skills` | string \| array | `skills/` |
| `hooks` | string \| object | `hooks/hooks.json` |
| `mcpServers` | string \| object | `.mcp.json` |
| `lspServers` | string \| object | `.lsp.json` |
| `outputStyles` | string \| array | (none) |

## Auto-Discovery

Claude Code automatically loads components from standard directories **without** needing explicit paths in plugin.json:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json      # Only manifest required here
├── commands/            # Auto-discovered: all .md files
├── agents/              # Auto-discovered: all .md files
├── skills/              # Auto-discovered: subdirs with SKILL.md
├── hooks/
│   └── hooks.json       # Auto-discovered
├── .mcp.json            # Auto-discovered
└── .lsp.json            # Auto-discovered
```

**Key insight**: If using standard directories, **omit the fields entirely** from plugin.json. Explicit paths are only needed for non-standard locations.

## When to Use Explicit Paths

Use explicit paths **only** when components are in non-standard locations:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Plugin with custom paths",
  "commands": "./src/custom-commands/",
  "agents": ["./ai/agents/reviewer.md", "./ai/agents/tester.md"],
  "hooks": "./config/hooks.json"
}
```

Custom paths **supplement** (don't replace) auto-discovered components.

## Path Format Rules

### Correct Path Formats

```json
// Directory path
"commands": "./custom/commands/"

// Single file path
"hooks": "./config/hooks.json"

// Array of paths
"agents": ["./agents/agent1.md", "./agents/agent2.md"]
```

### Invalid Path Formats (Will Cause Validation Errors)

```json
// WRONG: Missing leading ./
"commands": "commands/"

// WRONG: Absolute path
"commands": "/Users/me/plugins/commands/"

// WRONG: Path traversal (../)
"commands": "../shared/commands/"

// WRONG: Relative to plugin.json location
"commands": "../commands"
```

## Inline Configuration

`hooks`, `mcpServers`, and `lspServers` can be inline objects instead of file paths:

### Inline Hooks

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh"
          }
        ]
      }
    ]
  }
}
```

### Inline MCP Servers

```json
{
  "mcpServers": {
    "database": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
      "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"]
    }
  }
}
```

## Common Validation Errors

### "hooks: Invalid input"
- **Cause**: Using path traversal (`../`) or wrong type
- **Fix**: Use `./hooks/hooks.json` or omit field for auto-discovery

### "commands: Invalid input"
- **Cause**: Wrong path format or invalid type
- **Fix**: Use string (`"./commands/"`) or array (`["./cmd.md"]`), or omit for auto-discovery

### "agents: Invalid input"
- **Cause**: Wrong path format, often using object instead of string/array
- **Fix**: Use string (`"./agents/"`) or array (`["./agent.md"]`), or omit for auto-discovery

### General Validation Failures
1. Check all paths start with `./`
2. Remove component fields if using standard directories
3. Verify no path traversal (`../`)
4. Ensure arrays contain only strings (paths)

## Best Practices

1. **Prefer minimal manifests** - Only specify what's non-standard
2. **Use auto-discovery** - Put components in standard directories
3. **Avoid explicit paths for standard locations** - Don't add `"commands": "./commands"` if that's the default
4. **Use `${CLAUDE_PLUGIN_ROOT}`** - In hook scripts for portable paths
5. **Validate before publishing** - Run `claude plugin validate /path/to/plugin`

## Directory Structure Template

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json       # Minimal manifest
├── README.md             # Plugin documentation
├── commands/             # Slash commands (auto-discovered)
│   ├── deploy.md
│   └── status.md
├── agents/               # Agents (auto-discovered)
│   └── reviewer.md
├── skills/               # Skills (auto-discovered)
│   └── analysis/
│       └── SKILL.md
├── hooks/                # Hooks (auto-discovered)
│   ├── hooks.json
│   └── scripts/
│       └── post-edit.py
└── scripts/              # Shared scripts
    └── utils.py
```

## Debugging

```bash
# Validate plugin structure
claude plugin validate /path/to/plugin

# Debug mode for detailed loading info
claude --debug

# Check what components are loaded
claude /help  # Lists available commands from plugins
```
