# wicked-crew

Run multi-phase projects from idea to delivery. Smart decisioning analyzes your input and automatically engages the right specialists at the right time.

## Quick Start

```bash
# Install
claude plugin install wicked-crew@wicked-garden

# Start a new project
/wicked-crew:start "Build user authentication with OAuth2"

# Execute the current phase
/wicked-crew:execute

# Or let it run autonomously
/wicked-crew:just-finish
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-crew:start` | Create a project with signal analysis | `/wicked-crew:start "Add caching layer"` |
| `/wicked-crew:execute` | Execute the current phase | `/wicked-crew:execute` |
| `/wicked-crew:just-finish` | Autonomous completion with guardrails | `/wicked-crew:just-finish` |
| `/wicked-crew:status` | Show project state, signals, specialists | `/wicked-crew:status` |
| `/wicked-crew:approve` | Approve and advance to next phase | `/wicked-crew:approve clarify` |
| `/wicked-crew:gate` | Run quality gate checks | `/wicked-crew:gate` |
| `/wicked-crew:evidence` | Generate evidence reports | `/wicked-crew:evidence` |
| `/wicked-crew:profile` | Configure engagement preferences | `/wicked-crew:profile` |

## How It Works

```
Your Description → Signal Detection → Phase Planning → Specialist Engagement
                      │                    │                    │
                      ├── Security?        ├── clarify          ├── wicked-platform
                      ├── Performance?     ├── design           ├── wicked-engineering
                      ├── Ambiguity?       ├── test-strategy    ├── wicked-jam
                      └── Data?            ├── build            └── wicked-product
                                           ├── test
                                           └── review
```

### Smart Decisioning

When you `/start` a project, crew analyzes your description for:

| Signal | Detected From | Engages |
|--------|--------------|---------|
| Security | auth, encrypt, token, jwt | wicked-platform |
| Performance | scale, optimize, cache | wicked-engineering |
| Product | user, feature, story | wicked-product |
| Complexity | integration, migrate, refactor | wicked-delivery |
| Ambiguity | maybe, should we, options | wicked-jam |

**Complexity scoring** (0-7) determines how many phases you need:
- **0-2**: clarify → build → review
- **3-4**: + design, test-strategy
- **5-7**: + ideate, test, full specialist engagement

### Graceful Degradation

Crew works fully standalone with built-in agents. Specialist plugins enhance it when available:

| If Installed | Enhancement | Without It |
|-------------|-------------|------------|
| wicked-jam | AI brainstorming in clarify | Built-in facilitator |
| wicked-engineering | Architecture + code review | Built-in reviewer |
| wicked-product | Requirements + UX review | Built-in facilitator |
| wicked-platform | Security + CI/CD checks | Built-in implementer |
| wicked-qe | Test strategy + automation | Built-in reviewer |
| wicked-delivery | PMO + risk tracking | Built-in researcher |

## Workflows

### Standard Project

```bash
# 1. Start - analyzes signals, plans phases
/wicked-crew:start "Migrate auth from sessions to JWT"

# 2. Execute each phase
/wicked-crew:execute          # clarify phase
/wicked-crew:approve clarify  # approve and advance
/wicked-crew:execute          # design phase
/wicked-crew:approve design
# ... continues through build, review

# 3. Check status anytime
/wicked-crew:status
```

### Autonomous Mode

```bash
# Start and let it run
/wicked-crew:start "Add caching to API endpoints"
/wicked-crew:just-finish

# Crew will:
# - Execute all phases
# - Engage specialists automatically
# - Run quality gates
# - Only pause for guardrails (deployments, deletions, security)
```

## Built-in Agents

| Agent | Role | Used When |
|-------|------|-----------|
| `facilitator` | Requirements and ideation | Clarify phase, no wicked-jam |
| `researcher` | Analysis and design | Design phase, no wicked-engineering |
| `implementer` | Code generation | Build phase |
| `reviewer` | Quality assurance | Review phase, no specialist |
| `orchestrator` | Multi-agent coordination | Complex phases |

## Evidence Tracking

Every phase produces evidence in 4 tiers:

| Tier | What | Example |
|------|------|---------|
| L1 | Observations | "47 lines changed in auth.js" |
| L2 | Analysis | "No hardcoded secrets found" |
| L3 | Reasoning | "OAuth2 flow meets requirements" |
| L4 | Decisions | "Approved build phase" |

## Configuration

Autonomy modes via `/wicked-crew:profile`:
- **ask-first**: Pause at every decision
- **balanced** (default): Auto-proceed on minor decisions
- **just-finish**: Maximum autonomy with guardrails

## License

MIT
