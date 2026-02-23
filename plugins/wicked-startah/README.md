# wicked-startah

The foundation plugin that configures Context7 live documentation, shared caching infrastructure, smart script execution, multi-AI CLI integration, and browser automation in a single install — so every other wicked-garden plugin works better from day one.

**Install this first.**

## Quick Start

```bash
# 1. Install
claude plugin install wicked-startah@wicked-garden

# 2. Verify setup and get plugin recommendations
cat ~/.something-wicked/wicked-startah/recommended-plugins.txt

# 3. Start using skills immediately — no API keys needed for core features
/wickedizer rewrite this PR description to remove AI tells
```

## Workflows

### Remove AI tells from any writing

The `wickedizer` skill applies automatically when you write or rewrite prose, but you can also invoke it directly:

```
/wickedizer rewrite this PR description

Input:
  "I'm excited to introduce a comprehensive solution that leverages
   cutting-edge approaches to enhance the user experience..."

Output:
  "Replaces the modal confirmation dialog with inline validation.
   Reduces form submission errors by catching required fields before submit.
   No API changes."
```

The skill strips hedging, fluff, and chatbot artifacts. It works on PR descriptions, commit messages, ADRs, Jira tickets, executive summaries, and code comments.

### Run a Python script without dependency headaches

```bash
/runtime-exec analyze.py
```

The `runtime-exec` skill picks the right executor automatically:

```
Detected: pyproject.toml with uv.lock
Using: uv run python analyze.py

Installing missing packages... done
Running analyze.py...
```

Priority order for Python: `uv` → `poetry` → `.venv/bin/python` → `python3`.
Priority order for Node: `pnpm` → `npm` → `yarn`.

### Get up-to-date library documentation in-context

Context7 is configured automatically on install — no API key required:

```
/context7 How do I use React Query's optimistic updates?
```

Context7 fetches current library documentation for the version in your project, not from Claude's training data. Works for React, Next.js, FastAPI, SQLAlchemy, TypeScript, and hundreds of other libraries.

### Run a multi-AI design review

```bash
/ai-conversation review this architecture diagram
```

Sends your prompt to Claude, Gemini, and Codex simultaneously (requires API keys for non-Claude models), then surfaces where they agree and disagree. Useful for architecture decisions, security reviews, and API design trade-offs.

### File a GitHub issue automatically

When a tool call fails or an outcome is unmet, wicked-startah's hooks capture the context and queue an issue report:

```bash
/wicked-startah:report-issue bug
```

Produces a structured GitHub issue with steps to reproduce, expected vs actual behavior, and acceptance criteria. Files it automatically if `gh` CLI is installed.

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-startah:report-issue` | File a structured GitHub issue for a bug, UX friction, or unmet outcome | `/wicked-startah:report-issue bug` |

## Skills

| Skill | What It Does | Example |
|-------|-------------|---------|
| `wickedizer` | Strip AI tells, humanize writing, produce PRDs and work items in your team's voice | `/wickedizer rewrite this ADR` |
| `integration-discovery` | Map any task to the right skill, agent, or tool across all 17 plugins | `/integration-discovery security review capabilities` |
| `runtime-exec` | Execute Python and Node scripts using the best available package manager | `/runtime-exec script.py` |
| `agent-browser` | Browser screenshots, scraping, and accessibility audits via headless Chrome | `/agent-browser screenshot https://example.com` |
| `ai-conversation` | Multi-AI design reviews combining Claude, Gemini, and Codex responses | `/ai-conversation review this architecture` |
| `gemini-cli` | Google Gemini CLI integration and prompt guidance | `/gemini-cli` |
| `codex-cli` | OpenAI Codex CLI integration and prompt guidance | `/codex-cli` |
| `opencode-cli` | Multi-provider AI coding CLI integration | `/opencode-cli` |
| `caching` | Shared caching API for plugin developers: namespace isolation, TTL, file-based invalidation | See skill for Python API |
| `issue-reporting` | Auto-detect and structure GitHub issues from session context | `/issue-reporting` |

## MCP Servers (Auto-Configured)

| Server | Purpose | Auth |
|--------|---------|------|
| Context7 | Up-to-date library documentation in every conversation | None required |

## How It Works

**SessionStart hook** — On every session, `session_start.py` checks for missing optional tools, generates `recommended-plugins.txt` on first run, and writes a working-memory summary of available capabilities.

**PostToolUseFailure hook** — When any tool call fails, `auto_issue_reporter.py` captures the tool name, inputs, error, and surrounding context into `~/.something-wicked/wicked-startah/unfiled-issues/`.

**Stop hook (async)** — After each session ends, `session_outcome_checker.py` reviews the session for unmet outcomes and queues them as potential issue reports. Runs async so it never blocks the user.

**Caching infrastructure** — The `cache.py` script under `scripts/` provides a shared `namespace(plugin_name)` API used by wicked-smaht, wicked-patch, wicked-search, and others. Namespace isolation means one plugin's cache never pollutes another's.

## Optional API Keys

Core skills work without any keys. Add keys to unlock multi-AI features:

```bash
export GEMINI_API_KEY="your-key"    # Gemini CLI and ai-conversation
export OPENAI_API_KEY="your-key"    # Codex CLI and ai-conversation
npm install -g agent-browser        # Browser automation skill
```

Skills work as reference guides even when the underlying CLIs are not installed.

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-kanban | Task context in multi-AI conversations; shared state for `ai-conversation` results | Conversation outputs not persisted to task board |
| wicked-mem | Persistent storage for `wickedizer` voice profiles and past issue patterns | Session-only context; writing style not remembered |
| wicked-engineering | Architecture expertise available in `ai-conversation` design reviews | No specialized agents; conversation stays general |
| `gh` CLI | Auto-file GitHub issues from `report-issue` command | Issues saved to `~/.something-wicked/wicked-startah/unfiled-issues/` for manual filing |

## License

MIT
