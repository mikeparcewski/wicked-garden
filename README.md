# Wicked Garden

**AI-native plugins for Claude Code that make development feel like working with a great team.**

## Quick Start

```bash
# Install the starter kit (includes essential MCP servers)
claude plugins add something-wicked/wicked-startah

# Or install individual plugins
claude plugins add something-wicked/wicked-crew
```

Try it immediately:

```bash
# Brainstorm with AI personas
/wicked-jam:jam "should we use Redis or Postgres for session storage?"

# Search code and docs together
/wicked-search:search "authentication"

# Start a guided workflow
/wicked-crew:start "Add user authentication with OAuth2"
```

## What's Inside

### Core Infrastructure

| Plugin | Purpose |
|--------|---------|
| **[wicked-mem](plugins/wicked-mem)** | Cross-session memory - remembers decisions, learnings, and preferences |
| **[wicked-cache](plugins/wicked-cache)** | Shared caching infrastructure for plugin data |
| **[wicked-kanban](plugins/wicked-kanban)** | AI-native task board with web UI dashboard |

### Workflow & Ideation

| Plugin | Purpose |
|--------|---------|
| **[wicked-crew](plugins/wicked-crew)** | Phase-gated workflow orchestrator (clarify → design → build → review) |
| **[wicked-jam](plugins/wicked-jam)** | AI brainstorming with developer-focused personas |

### Search & Context

| Plugin | Purpose |
|--------|---------|
| **[wicked-search](plugins/wicked-search)** | Unified code + document search with cross-reference detection |
| **[wicked-smaht](plugins/wicked-smaht)** | Intelligent context assembly from wicked-garden sources |

### Specialist Plugins

| Plugin | Purpose |
|--------|---------|
| **[wicked-engineering](plugins/wicked-engineering)** | Senior engineering, QE, architecture, debugging, frontend/backend |
| **[wicked-product](plugins/wicked-product)** | Product management, UX review, requirements, customer feedback |
| **[wicked-platform](plugins/wicked-platform)** | DevSecOps, CI/CD, compliance, incident response, observability |
| **[wicked-delivery](plugins/wicked-delivery)** | PMO, cost analysis, rollouts, developer onboarding |
| **[wicked-data](plugins/wicked-data)** | Data engineering, ML pipelines, analytics, DuckDB analysis |

### Tools & Utilities

| Plugin | Purpose |
|--------|---------|
| **[wicked-workbench](plugins/wicked-workbench)** | Dashboard renderer for visualizing plugin data |
| **[wicked-startah](plugins/wicked-startah)** | Opinionated starter kit with essential MCP servers |

## How They Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR PROJECT                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  /wicked-crew:start "Build auth feature"                        │
│       │                                                         │
│       ├── CLARIFY ──► wicked-jam brainstorms approaches         │
│       │                    └── wicked-mem recalls past decisions│
│       │                                                         │
│       ├── DESIGN ──► wicked-search finds existing patterns      │
│       │                    └── wicked-engineering:arch reviews  │
│       │                                                         │
│       ├── BUILD ───► Implementation with wicked-kanban tracking │
│       │                    └── wicked-platform checks security  │
│       │                                                         │
│       └── REVIEW ──► wicked-engineering:review (multi-pass)     │
│                           └── wicked-mem stores learnings       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

But you don't have to use them all. Each plugin works independently:

```bash
# Just brainstorm
/wicked-jam:jam "microservices vs monolith for this project?"

# Just search
/wicked-search:search "error handling"

# Just review code
/wicked-engineering:review

# Just remember
/wicked-mem:store --title "Why we chose JWT" --type decision
```

## Why Wicked Garden?

Traditional SDLC frameworks (SAFe, Scrum, etc.) were designed for human coordination overhead. AI agents don't need standups, but they do need:

- **Outcome clarity** before jumping into code
- **Quality gates** that prevent shipping broken things
- **Memory** of past decisions and learnings
- **Multiple perspectives** to catch blind spots

Wicked Garden provides these without the ceremony.

### Principles

1. **Lightweight over heavyweight** - No mandatory ceremonies. Use what helps, skip what doesn't.
2. **Guardrails over gates** - Prevent disasters (force push, secret commits) without blocking flow.
3. **Memory over amnesia** - Learn from past sessions. Remember decisions. Build context.
4. **Perspectives over ego** - Multiple reviewers catch what one misses.
5. **Graceful degradation** - Every plugin works standalone. Ecosystem integration is optional.

## Memory That Matters

Claude Code sessions are stateless by default. Wicked Garden changes that:

```bash
# Session 1: Make a decision
/wicked-mem:store --title "Chose PostgreSQL over MongoDB" \
  --type decision \
  --tags "database,architecture"

# Session 47: That decision surfaces automatically
> "Should we add a new database?"
# wicked-mem injects: "Previous decision: Chose PostgreSQL over MongoDB..."
```

Memory types:
- **Episodic** - What happened (bugs fixed, features built)
- **Procedural** - How to do things (patterns, techniques)
- **Decision** - Why we chose X over Y
- **Preference** - User/project preferences

## Guardrails, Not Gates

Wicked Garden doesn't block you. It prevents disasters:

**Always prevented:**
- Force push to main
- Committing secrets
- Destructive operations without confirmation
- Auto-proceeding on deployments

**Always allowed:**
- Moving fast on low-risk changes
- Skipping optional phases
- Overriding suggestions with explicit intent

## Installation

Install individual plugins or the whole ecosystem:

```bash
# Start with the recommended setup
claude plugins add something-wicked/wicked-startah

# Or install individual plugins
claude plugins add something-wicked/wicked-mem
claude plugins add something-wicked/wicked-crew
claude plugins add something-wicked/wicked-engineering
```

## Contributing

This is an open marketplace. Contributions welcome:

1. Fork the repo
2. Create your plugin in `plugins/wicked-yourplugin/`
3. Run `/wg-check plugins/wicked-yourplugin` to validate structure
4. Run `/wg-check plugins/wicked-yourplugin --full` for marketplace readiness
5. Submit a PR

See [.claude/CLAUDE.md](.claude/CLAUDE.md) for development tooling.

## License

MIT - Use it, fork it, make it yours.

---

*Wicked Garden: Because AI-assisted development should feel like having a great team, not fighting a framework.*
