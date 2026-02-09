# wicked-startah

Install one plugin, get 8 skills, 2 MCP servers, and a curated plugin catalog. Zero configuration - everything works immediately.

**Install this first.** It's the fastest way to get value from the wicked-garden ecosystem.

## Quick Start

```bash
claude plugin install wicked-startah@wicked-garden
```

No API keys needed for core skills. Optional keys unlock multi-AI features.

## What You Get

### Skills (Ready Immediately)

| Skill | What It Does | Example |
|-------|-------------|---------|
| `/wickedizer` | Remove AI tells, humanize writing, create PRDs | `/wickedizer rewrite this PR description` |
| `/integration-discovery` | Find which tools help with a task | `/integration-discovery security review capabilities` |
| `/runtime-exec` | Smart Python/Node execution with package detection | `/runtime-exec script.py` |
| `/agent-browser` | Browser screenshots, scraping, a11y audits | `/agent-browser screenshot https://example.com` |
| `/ai-conversation` | Multi-AI design reviews (Claude + Gemini + Codex) | `/ai-conversation review this architecture` |
| `/gemini-cli` | Google Gemini integration | `/gemini-cli` |
| `/codex-cli` | OpenAI Codex integration | `/codex-cli` |
| `/opencode-cli` | Multi-provider AI coding | `/opencode-cli` |

### MCP Servers (Auto-Configured)

| Server | Purpose | Auth |
|--------|---------|------|
| **Context7** | Up-to-date library docs in every conversation | None needed |
| **Atlassian** | Jira/Confluence integration | Browser OAuth |

### Plugin Catalog

First run generates `~/.something-wicked/wicked-startah/recommended-plugins.txt` - a curated list of what to install next based on your workflow.

```bash
cat ~/.something-wicked/wicked-startah/recommended-plugins.txt
claude plugin install hookify@claude-plugins-official
```

## Highlights

**wickedizer** - Stop sounding like a robot:
- Strips AI tells (fluff, hedging, "I'd be happy to")
- Writes PRDs, work items, PR descriptions, ADRs
- Matches your team's voice

**integration-discovery** - "What tool should I use?":
- Maps your question to the right skill, agent, or tool
- One command instead of reading docs for 17 plugins

**runtime-exec** - Run scripts without dependency headaches:
- Auto-detects package managers (uv > poetry > venv, pnpm > npm > yarn)
- Installs missing packages before execution

## Optional AI CLIs

Add API keys for multi-AI features:

```bash
export GEMINI_API_KEY="your-key"    # Gemini
export OPENAI_API_KEY="your-key"    # Codex
npm install -g agent-browser        # Browser automation
```

Skills work as guides even without CLIs installed.

## Integration

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-kanban | Shared context for multi-AI conversations | Manual note-taking |
| wicked-mem | Persistent decision storage | Session-only context |
| wicked-engineering | Architecture expertise for design reviews | No specialized agents |

## License

MIT
