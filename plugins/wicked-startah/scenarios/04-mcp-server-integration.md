---
name: mcp-server-integration
title: MCP Server Integration Validation
description: Validates that bundled MCP servers (atlassian, context7) are functional and accessible
type: integration
difficulty: intermediate
estimated_minutes: 15
---

# MCP Server Integration Validation

Tests that the auto-installed MCP servers (atlassian, context7) are properly configured and functional within Claude Code sessions.

## Setup

Ensure wicked-startah is installed:

```bash
# Verify plugin installation
claude plugin list | grep wicked-startah

# Check MCP configuration
cat ~/.claude/mcp.json | grep -E '"atlassian"|"context7"'
```

## Steps

1. **Verify MCP server configuration**

   ```bash
   # Check atlassian MCP server
   cat ~/.claude/mcp.json | jq '.atlassian'

   # Check context7 MCP server
   cat ~/.claude/mcp.json | jq '.context7'
   ```

   Expected: Both servers configured with:
   - `type: "stdio"`
   - `command: "npx"`
   - Valid args array
   - Empty env object

2. **Test context7 MCP server (no auth required)**

   In Claude Code conversation:
   ```
   Use the context7 MCP server to search for documentation about React hooks.
   ```

   Expected: Claude accesses context7 and retrieves documentation about React hooks.

3. **Verify context7 functionality**

   In Claude Code conversation:
   ```
   Use context7 to find:
   1. Latest Python requests library documentation
   2. PostgreSQL connection pooling best practices
   3. Stripe webhook signature verification
   ```

   Expected: Context7 returns relevant documentation for each query.

4. **Test atlassian MCP server (requires auth)**

   ```bash
   # Authenticate with Atlassian (if not already done)
   npx @anthropic/mcp-server-atlassian auth
   ```

   In Claude Code conversation:
   ```
   List my recent Jira issues using the atlassian MCP server.
   ```

   Expected:
   - If authenticated: Claude retrieves Jira issues
   - If not authenticated: Claude indicates authentication is required and provides instructions

5. **Verify error handling for unavailable servers**

   ```bash
   # Temporarily rename mcp.json to test fallback
   mv ~/.claude/mcp.json ~/.claude/mcp.json.backup
   ```

   In Claude Code conversation:
   ```
   Try to use the context7 MCP server.
   ```

   Expected: Claude gracefully handles missing MCP configuration.

   ```bash
   # Restore mcp.json
   mv ~/.claude/mcp.json.backup ~/.claude/mcp.json
   ```

6. **Test MCP server commands are available**

   In Claude Code conversation:
   ```
   What MCP servers are currently available?
   ```

   Expected: Claude lists atlassian and context7 (and any other configured servers).

7. **Verify MCP server version strategy**

   ```bash
   # Check that context7 uses @latest
   grep -A 3 '"context7"' ~/.claude/mcp.json | grep "@latest"
   ```

   Expected: context7 configured with `@latest` version tag for auto-updates.

8. **Test real-world context7 usage**

   In Claude Code conversation:
   ```
   I'm implementing OAuth2 authentication with PKCE flow. Use context7 to find:
   1. OAuth2 PKCE specification details
   2. Common implementation pitfalls
   3. Security best practices
   ```

   Expected: Context7 retrieves relevant OAuth2/PKCE documentation and provides accurate information.

## Expected Outcome

- Both MCP servers (atlassian, context7) are configured correctly
- context7 works without authentication and retrieves documentation
- atlassian requires authentication (expected behavior)
- MCP servers accessible within Claude Code conversations
- Error handling works gracefully for missing/failing servers
- context7 uses @latest for automatic updates
- Real-world queries return useful, accurate documentation

## Success Criteria

- [ ] atlassian MCP server configured in mcp.json with correct parameters
- [ ] context7 MCP server configured in mcp.json with correct parameters
- [ ] context7 accessible without authentication
- [ ] context7 retrieves documentation for test queries
- [ ] atlassian requires authentication (or works if already authenticated)
- [ ] Claude can list available MCP servers
- [ ] Error handling works when MCP servers unavailable
- [ ] context7 uses @latest version tag
- [ ] Real-world OAuth2 query returns accurate documentation
- [ ] MCP operations complete within reasonable time (< 30 seconds)

## Value Demonstrated

This scenario proves wicked-startah provides **zero-configuration access to essential MCP servers**:

- **context7** gives instant access to up-to-date documentation for thousands of libraries without manual searching or outdated docs
- **atlassian** enables Jira/Confluence integration for teams using Atlassian tools
- **No manual setup** - MCP servers configured automatically on plugin installation
- **Version strategy** (@latest) ensures users get improvements without manual updates

This transforms Claude Code from "code assistant with static knowledge" to **connected assistant with live documentation and project management integration**.
