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

Ask Claude Code to list available skills:

```
/wicked-garden:help
```

Expected — the help output should list skills across domains, including root-level skills such as:
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

Ask Claude about a specific skill to confirm it loads correctly:

```
Tell me about the ai-conversation skill. What does it do?
```

Expected: Claude responds with a description drawn from the skill's frontmatter and SKILL.md content, confirming the skill is loaded and well-formed. Repeat for one or two other skills (e.g., codex-cli, runtime-exec) to spot-check.

### 7. Verify Hooks Are Active

Start a new session and confirm the SessionStart hook runs without error:

```
# Simply start a new Claude Code session
```

Expected: Session starts cleanly with no hook failure notifications. The SessionStart hook fires silently and completes within 2 seconds.

### 8. Verify Issue Reporting Command

Run the issue reporting command to confirm it is registered:

```
/wicked-garden:report-issue --help
```

Expected: Command is recognized and shows usage information or prompts for input.

### 9. Confirm Session Runs Normally

Open a second new conversation in Claude Code.

Expected: Hook fires again silently. Session starts identically to the first. There is no state from the previous session that changes behavior — startup is stateless and always silent.

## Expected Outcome

- Plugin installs without errors
- context7 MCP server is configured (bundled MCP server)
- SessionStart hook fires and completes silently within 2 seconds
- Root-level skills are discoverable and load correctly
- Hooks fire silently during session lifecycle
- Subsequent sessions behave identically — no first-run vs. repeat-run difference in startup behavior

## Success Criteria

- [ ] Plugin installation completes successfully
- [ ] context7 MCP server configured in mcp.json with `@upstash/context7-mcp@latest`
- [ ] SessionStart hook fires without errors (no failure notification in Claude Code)
- [ ] Hook completes within 2 seconds (no timeout)
- [ ] No setup message, nag, or prompt displayed on session start
- [ ] Root-level skills discoverable via `/wicked-garden:help`: agent-browser, ai-conversation, codex-cli, gemini-cli, integration-discovery, issue-reporting, opencode-cli, runtime-exec, wickedizer
- [ ] Skills load correctly when queried (frontmatter and content accessible)
- [ ] Hooks fire silently on session start with no error notifications

## Value Demonstrated

wicked-garden provides a **low-friction installation experience**: install once, get context7 MCP server configured automatically, and have specialized skills available immediately. The deliberate silence of the SessionStart hook respects the user's workflow — no onboarding interruptions, no setup wizards, just capability that's there when you need it.
