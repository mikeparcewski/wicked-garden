---
name: mcp-server-integration
title: Context7 MCP Server Integration Validation
description: Validates that the bundled context7 MCP server is functional — library lookup, doc retrieval, and error handling
type: integration
difficulty: intermediate
estimated_minutes: 12
---

# Context7 MCP Server Integration Validation

Tests that the context7 MCP server bundled by wicked-garden is correctly configured and usable within Claude Code sessions. context7 provides live, up-to-date library documentation for thousands of packages — replacing stale knowledge-cutoff data with fresh docs on demand.

wicked-garden bundles only context7. There is no atlassian MCP server in this plugin.

## Setup

Ensure wicked-garden is installed and context7 is configured:

```bash
# Verify plugin is installed
claude plugin list | grep wicked-garden

# Check context7 MCP configuration
cat ~/.claude/mcp.json | grep -A 6 '"context7"'
```

Expected context7 configuration:
```json
"context7": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp@latest"],
  "env": {}
}
```

## Steps

### 1. Verify MCP Server Configuration Parameters

```bash
cat ~/.claude/mcp.json | python3 -c "import json,sys; cfg = json.load(sys.stdin); c7 = cfg.get('context7', {}); print('type:', c7.get('type')); print('command:', c7.get('command')); print('args:', c7.get('args'))"
```

Expected:
- `type: stdio`
- `command: npx`
- `args: ["-y", "@upstash/context7-mcp@latest"]`

### 2. Test Library Lookup — Resolve a Library ID

In a Claude Code conversation:

```
Use the context7 MCP server to find the library ID for the Python requests library.
```

Expected: Claude calls context7's `resolve-library-id` tool and returns a context7-compatible library ID (e.g., `/psf/requests` or similar). The library should be found with a description, snippet count, and reputation score.

### 3. Test Documentation Retrieval

In a Claude Code conversation:

```
Use context7 to get documentation about how to use sessions and connection pooling in the Python requests library.
```

Expected:
- Claude calls `resolve-library-id` first to get the library ID
- Then calls `get-library-docs` with the resolved ID and query
- Returns relevant documentation excerpts with code examples
- Documentation is current and accurate (not from Claude's training data)

### 4. Test Multi-Query Documentation Retrieval

In a Claude Code conversation:

```
Using context7, find documentation for:
1. React useEffect cleanup functions
2. FastAPI dependency injection
3. PostgreSQL connection pooling with asyncpg
```

Expected: Claude makes three separate context7 calls (or parallel calls if supported) and returns relevant documentation for each. All three queries should return results — these are well-documented libraries with high coverage in context7.

### 5. Test Version-Specific Query (if applicable)

In a Claude Code conversation:

```
Use context7 to find documentation about authentication in Next.js. I need to know whether this applies to the App Router or Pages Router.
```

Expected: Documentation retrieved and includes version context (App Router vs Pages Router distinction). context7 tracks library versions and can surface version-specific information.

### 6. Test Error Handling — Unknown Library

In a Claude Code conversation:

```
Use context7 to find documentation for a library called "nonexistent-fictional-library-xyz".
```

Expected: Claude gracefully handles the case where context7 cannot resolve the library ID. It should report that no matching library was found rather than hallucinating documentation. This validates that context7 is doing live lookups rather than falling back to training data.

### 7. Test Error Handling — MCP Server Unavailable

```bash
# Temporarily corrupt context7 config to test fallback behavior
python3 -c "
import json
with open('$HOME/.claude/mcp.json') as f:
    cfg = json.load(f)
cfg['context7']['command'] = 'nonexistent-command'
with open('/tmp/mcp-backup.json', 'w') as f:
    json.dump(cfg, f, indent=2)
import shutil
shutil.copy('$HOME/.claude/mcp.json', '/tmp/mcp-original.json')
with open('$HOME/.claude/mcp.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print('Config corrupted for test')
"
```

Open a new Claude Code session and attempt to use context7:

```
Try to use context7 to look up Python documentation.
```

Expected: Claude reports that context7 is unavailable or failed to start, and either attempts fallback or explains that MCP server is not accessible. Claude should NOT silently return training-data documentation as if context7 responded.

```bash
# Restore original config
cp /tmp/mcp-original.json ~/.claude/mcp.json
echo "Config restored"
```

### 8. Test Version Strategy — Latest Tag

Verify context7 uses `@latest` for automatic updates:

```bash
cat ~/.claude/mcp.json | python3 -c "
import json, sys
cfg = json.load(sys.stdin)
args = cfg.get('context7', {}).get('args', [])
has_latest = any('@latest' in a for a in args)
print('Uses @latest:', has_latest)
print('Args:', args)
"
```

Expected: `Uses @latest: True`. The `@upstash/context7-mcp@latest` arg ensures the MCP server auto-updates when npx fetches it, so users always get the latest documentation coverage without manual updates.

### 9. Real-World Integration Test

In a Claude Code conversation, simulate a realistic development task that benefits from context7:

```
I'm implementing JWT authentication in a FastAPI application. Use context7 to find:
1. How to install and configure python-jose for JWT handling
2. FastAPI's security utilities for OAuth2 password flow
3. How to set token expiration correctly

Then give me a minimal working example combining all three.
```

Expected:
- Claude makes context7 calls for each query
- Returns accurate, current documentation from all three areas
- Synthesizes a working code example based on live docs rather than potentially outdated training data
- Total time for all context7 calls should be under 30 seconds

## Expected Outcome

- context7 MCP server is correctly configured with `@upstash/context7-mcp@latest`
- Library ID resolution works for well-known packages (requests, React, FastAPI, asyncpg)
- Documentation retrieval returns current, accurate content with code examples
- Unknown library queries fail gracefully without hallucination
- MCP unavailability is reported clearly, not silently worked around
- `@latest` version tag confirmed for automatic update behavior
- Real-world multi-query integration completes in reasonable time

## Success Criteria

- [ ] context7 configured in mcp.json with correct type, command, and args
- [ ] `@upstash/context7-mcp@latest` present in args (auto-update strategy)
- [ ] Library ID resolution succeeds for Python requests library
- [ ] Documentation retrieval returns content for requests connection pooling
- [ ] Multi-query test returns results for React, FastAPI, and asyncpg
- [ ] Unknown library query fails gracefully (no hallucination)
- [ ] MCP unavailability reported clearly when server command is invalid
- [ ] Real-world JWT/FastAPI integration test completes under 30 seconds
- [ ] No atlassian or other unexpected MCP server present from this plugin

## Value Demonstrated

context7 transforms Claude Code from an assistant with a knowledge cutoff into a **connected assistant with live documentation access**:

- **No more stale docs**: Library docs fetched fresh rather than from training data
- **Version awareness**: context7 tracks library versions and surfaces version-specific information
- **Zero configuration**: Bundled by wicked-garden — npx handles installation on first use
- **Auto-updates**: `@latest` tag means improved library coverage arrives automatically

The gap between "Claude thinks this API works this way" and "this is how the API actually works today" is where documentation-related bugs come from. context7 closes that gap.
