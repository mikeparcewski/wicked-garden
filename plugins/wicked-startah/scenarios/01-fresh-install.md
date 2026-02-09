---
name: fresh-install
title: Fresh Installation and First Session
description: Validates plugin installation, MCP server configuration, and first-session setup flow
type: integration
difficulty: basic
estimated_minutes: 10
---

# Fresh Installation and First Session

Tests the complete installation flow including MCP server configuration, hook execution, and recommended plugin prompts.

## Setup

Start with a clean Claude Code environment (or isolated test environment):

```bash
# Optional: Create a test project directory
mkdir -p /tmp/wicked-startah-test
cd /tmp/wicked-startah-test

# Ensure no previous setup marker exists
rm -rf ~/.something-wicked/wicked-startah/setup-complete
```

## Steps

1. **Install the plugin**
   ```bash
   claude plugin install wicked-startah@wicked-garden
   ```

   Expected: Plugin installed successfully, shows version 0.1.4 or later.

2. **Verify MCP servers are configured**
   ```bash
   cat ~/.claude/mcp.json | grep -A 10 '"atlassian"'
   cat ~/.claude/mcp.json | grep -A 10 '"context7"'
   ```

   Expected: Both `atlassian` and `context7` MCP servers are present with correct configuration.

3. **Start a new Claude Code session**

   Open a new conversation in Claude Code.

   Expected: SessionStart hook triggers and displays setup message offering recommended plugins.

4. **Verify hook message content**

   The message should contain:
   - Mention of "wicked-startah detected"
   - List of recommended plugins from claude-plugins-official
   - Instructions to run `/wicked-startah:help` or create marker file

5. **Check skills are available**
   ```bash
   ls ~/.claude/plugins/wicked-startah/skills/
   ```

   Expected: Should list: `ai-conversation`, `codex-cli`, `gemini-cli`, `opencode-cli`

6. **Verify skill documentation is readable**
   ```bash
   head -20 ~/.claude/plugins/wicked-startah/skills/gemini-cli/SKILL.md
   ```

   Expected: Valid YAML frontmatter with name and description, followed by skill content.

7. **Create setup marker to test skip behavior**
   ```bash
   mkdir -p ~/.something-wicked/wicked-startah
   touch ~/.something-wicked/wicked-startah/setup-complete
   ```

8. **Start another session**

   Open a new conversation in Claude Code.

   Expected: No setup prompt (hook runs but exits silently because marker exists).

## Expected Outcome

- Plugin installs without errors
- MCP servers (atlassian, context7) are configured in mcp.json
- First session displays setup prompt with plugin recommendations
- All four skills are installed and accessible
- Subsequent sessions after marker creation show no setup prompt
- Hook executes quickly (under 10 seconds timeout)

## Success Criteria

- [ ] Plugin installation completes successfully
- [ ] atlassian MCP server is configured in mcp.json
- [ ] context7 MCP server is configured in mcp.json
- [ ] SessionStart hook displays setup message on first session
- [ ] Setup message includes recommended plugins list
- [ ] All four skills (ai-conversation, codex-cli, gemini-cli, opencode-cli) are installed
- [ ] Each skill has valid YAML frontmatter
- [ ] Creating setup marker suppresses future setup prompts
- [ ] Hook completes within timeout (10 seconds)

## Value Demonstrated

This scenario proves wicked-startah provides a **zero-configuration onboarding experience** for Claude Code users. New users get essential MCP servers and are guided to recommended plugins without manual configuration, reducing setup time from hours to minutes.
