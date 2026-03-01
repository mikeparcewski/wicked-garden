---
name: fresh-install
title: Fresh Installation and First Session
description: Validates plugin installation, hook execution, MCP configuration, and skill availability
type: integration
difficulty: basic
estimated_minutes: 8
---

# Fresh Installation and First Session

Tests the complete installation flow: hooks run silently on session start, context7 MCP server is configured, and all skills are accessible. wicked-garden has a deliberately quiet startup — no nag messages, no setup wizard. Its value is in what it configures and provides, not in what it announces.

## Setup

```bash
# Create a test project directory
mkdir -p /tmp/wicked-garden-test
```

## Steps

### 1. Install the Plugin

```bash
claude plugin install mikeparcewski/wicked-garden
```

Expected: Plugin installed successfully, shows current version.

### 2. Verify MCP Server Configuration

wicked-garden bundles context7 as an MCP server. Verify it was added to your project or global MCP configuration:

```bash
cat ~/.claude/mcp.json | grep -A 5 '"context7"'
```

Expected: context7 is present with the following configuration:
```json
"context7": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp@latest"],
  "env": {}
}
```

### 3. Start a New Claude Code Session

Open a new conversation in Claude Code.

Expected: SessionStart hook fires and completes within 2 seconds (2000ms timeout). No output message is displayed — the hook is intentionally silent. The session starts normally without any setup prompt, recommendations, or nag messages.

### 4. Verify Hook Executed Without Error

The session start hook reads stdin and returns `{"continue": true}`. Verify no hook errors appear in the Claude Code output during session initialization.

Expected: Session starts cleanly. No hook failure notifications. The hook's job is to stay out of the way.

### 5. Verify Skills Are Available

Check that root-level skills are present:

```bash
ls "${CLAUDE_PLUGIN_ROOT}/skills/"
```

Expected — skills should include (among domain-scoped skills):
- `agent-browser` — browser automation via agent-browser CLI
- `ai-conversation` — multi-AI orchestration with kanban as shared memory
- `codex-cli` — OpenAI Codex CLI integration for code review
- `gemini-cli` — Gemini CLI integration for multi-model analysis
- `integration-discovery` — capability router for tool selection decisions
- `issue-reporting` — automated GitHub issue filing from session failures
- `opencode-cli` — OpenCode CLI integration with multi-provider support
- `runtime-exec` — smart script execution with package manager detection
- `wickedizer` — content humanizer and voice alignment tool

### 6. Verify Skill Documentation Is Valid

Spot-check a few skills for valid structure:

```bash
head -15 "${CLAUDE_PLUGIN_ROOT}/skills/ai-conversation/SKILL.md"
head -10 "${CLAUDE_PLUGIN_ROOT}/skills/codex-cli/SKILL.md"
head -10 "${CLAUDE_PLUGIN_ROOT}/skills/runtime-exec/SKILL.md"
```

Expected: Each file starts with valid YAML frontmatter containing `name` and `description` fields, followed by skill content. No file should be empty or malformed.

### 7. Verify Hook Scripts Are Present

```bash
ls "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/"
```

Expected: Hook scripts present including `bootstrap.py`, `stop.py`, `post_tool.py`, etc.

### 8. Verify Issue Reporting Command

```bash
cat "${CLAUDE_PLUGIN_ROOT}/commands/report-issue.md" | head -5
```

Expected: Command file exists with valid YAML frontmatter.

### 9. Confirm Session Runs Normally

Open a second new conversation in Claude Code.

Expected: Hook fires again silently. Session starts identically to the first. There is no state from the previous session that changes behavior — startup is stateless and always silent.

## Expected Outcome

- Plugin installs without errors
- context7 MCP server is configured (bundled MCP server)
- SessionStart hook fires and completes silently within 2 seconds
- Root-level skills are installed and have valid YAML frontmatter
- Hook scripts exist for session lifecycle management
- Subsequent sessions behave identically — no first-run vs. repeat-run difference in startup behavior

## Success Criteria

- [ ] Plugin installation completes successfully
- [ ] context7 MCP server configured in mcp.json with `@upstash/context7-mcp@latest`
- [ ] SessionStart hook fires without errors (no failure notification in Claude Code)
- [ ] Hook completes within 2 seconds (no timeout)
- [ ] No setup message, nag, or prompt displayed on session start
- [ ] Root-level skills present: agent-browser, ai-conversation, codex-cli, gemini-cli, integration-discovery, issue-reporting, opencode-cli, runtime-exec, wickedizer
- [ ] Each skill has valid YAML frontmatter with name and description
- [ ] Hook scripts present in hooks/scripts/

## Value Demonstrated

wicked-garden provides a **low-friction installation experience**: install once, get context7 MCP server configured automatically, and have specialized skills available immediately. The deliberate silence of the SessionStart hook respects the user's workflow — no onboarding interruptions, no setup wizards, just capability that's there when you need it.
