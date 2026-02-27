---
name: fresh-install
title: Fresh Installation and First Session
description: Validates plugin installation, hook execution, MCP configuration, and skill availability
type: integration
difficulty: basic
estimated_minutes: 8
---

# Fresh Installation and First Session

Tests the complete installation flow: hook runs silently on session start, context7 MCP server is configured, and all skills are accessible. wicked-startah has a deliberately quiet startup — no nag messages, no setup wizard. Its value is in what it configures and provides, not in what it announces.

## Setup

```bash
# Create a test project directory
mkdir -p /tmp/wicked-startah-test
```

## Steps

### 1. Install the Plugin

```bash
claude plugin install wicked-startah@wicked-garden
```

Expected: Plugin installed successfully, shows version 0.8.0 or later.

### 2. Verify MCP Server Configuration

wicked-startah bundles context7 as the only MCP server. Verify it was added to your project or global MCP configuration:

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

Note: There is no atlassian MCP server bundled with this plugin. context7 is the only MCP server wicked-startah configures.

### 3. Start a New Claude Code Session

Open a new conversation in Claude Code.

Expected: SessionStart hook fires and completes within 2 seconds (2000ms timeout). No output message is displayed — the hook is intentionally silent. The session starts normally without any setup prompt, recommendations, or nag messages.

### 4. Verify Hook Executed Without Error

The session start hook reads stdin and returns `{"continue": true}`. Verify no hook errors appear in the Claude Code output during session initialization.

Expected: Session starts cleanly. No hook failure notifications. The hook's job is to stay out of the way.

### 5. Verify Skills Are Available

Check which skills the plugin provides:

```bash
ls "${CLAUDE_PLUGIN_ROOT}/skills/startah/"
```

Expected — the following skills should be listed:
- `agent-browser` — browser automation via agent-browser CLI
- `ai-conversation` — multi-AI orchestration with kanban as shared memory
- `caching` — unified caching infrastructure for plugins
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
head -15 "${CLAUDE_PLUGIN_ROOT}/skills/startah/ai-conversation/SKILL.md"
head -10 "${CLAUDE_PLUGIN_ROOT}/skills/startah/codex-cli/SKILL.md"
head -10 "${CLAUDE_PLUGIN_ROOT}/skills/startah/runtime-exec/SKILL.md"
```

Expected: Each file starts with valid YAML frontmatter containing `name` and `description` fields, followed by skill content. No file should be empty or malformed.

### 7. Verify Hook Scripts Are Present

```bash
ls "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/"
```

Expected:
- `auto_issue_reporter.py` — fires on PostToolUseFailure to track tool errors
- `session_outcome_checker.py` — fires async on Stop to assess session outcomes

### 8. Verify Issue Reporting Command

```bash
cat "${CLAUDE_PLUGIN_ROOT}/commands/startah/report-issue.md" | head -5
```

Expected: Command file exists with valid YAML frontmatter.

### 9. Verify Cache Infrastructure Is Present

```bash
ls "${CLAUDE_PLUGIN_ROOT}/scripts/startah/"
```

Expected: Cache scripts present — `cache.py`, `cache_setup.py`, `cache_stats.py`, `cache_list.py`, `cache_clear.py`.

### 10. Confirm Session Runs Normally

Open a second new conversation in Claude Code.

Expected: Hook fires again silently. Session starts identically to the first. There is no state from the previous session that changes behavior — wicked-startah's startup is stateless and always silent.

## Expected Outcome

- Plugin installs without errors
- context7 MCP server is configured (the only bundled MCP server)
- SessionStart hook fires and completes silently within 2 seconds
- All 10 skills are installed and have valid YAML frontmatter
- Hook scripts exist for issue reporting and session outcome tracking
- Cache infrastructure scripts are present
- Subsequent sessions behave identically — no first-run vs. repeat-run difference in startup behavior

## Success Criteria

- [ ] Plugin installation completes successfully
- [ ] context7 MCP server configured in mcp.json with `@upstash/context7-mcp@latest`
- [ ] No atlassian or other MCP server erroneously added
- [ ] SessionStart hook fires without errors (no failure notification in Claude Code)
- [ ] Hook completes within 2 seconds (no timeout)
- [ ] No setup message, nag, or prompt displayed on session start
- [ ] All 10 skills present: agent-browser, ai-conversation, caching, codex-cli, gemini-cli, integration-discovery, issue-reporting, opencode-cli, runtime-exec, wickedizer
- [ ] Each skill has valid YAML frontmatter with name and description
- [ ] Hook scripts present: auto_issue_reporter.py, session_outcome_checker.py
- [ ] Cache scripts present: cache.py, cache_setup.py, cache_stats.py, cache_list.py, cache_clear.py

## Value Demonstrated

wicked-startah provides a **low-friction installation experience**: install once, get context7 MCP server configured automatically, and have 10 specialized skills available immediately. The deliberate silence of the SessionStart hook respects the user's workflow — no onboarding interruptions, no setup wizards, just capability that's there when you need it.
