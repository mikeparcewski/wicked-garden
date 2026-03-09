# Advanced Usage

## Multi-Model Reviews

When external LLM CLIs are available, wicked-garden can run council-style reviews with multiple AI models analyzing independently, then synthesizing results.

### Supported CLIs

| CLI | Provider | Detection |
|-----|----------|-----------|
| `codex` | OpenAI Codex | Auto-detected on PATH |
| `gemini` | Google Gemini | Auto-detected on PATH |
| `opencode` | OpenCode | Auto-detected on PATH |

### Usage

```bash
# Collaborative review with all available models
/wicked-garden:multi-model:collaborate "Review this authentication implementation"

# Council evaluation (structured scoring)
/wicked-garden:jam:council "Should we use microservices or a monolith?"
```

When no external CLIs are available, the system falls back to Claude-only specialist subagents — same structure, different execution.

## Customization

### Crew Preferences

Configure how crew behaves for your workflow:

```bash
/wicked-garden:crew:profile
```

Options include:
- Default autonomy level (guided, balanced, autonomous)
- Phase plan preferences (always include design, skip ideate, etc.)
- Specialist preferences

### Memory Management

Review and curate your memory store:

```bash
/wicked-garden:mem:review              # browse all memories
/wicked-garden:mem:stats               # see memory health
/wicked-garden:mem:forget "old-id"     # remove stale memories
```

Memories auto-decay based on age, importance, and access frequency. The lifecycle is: active -> archived -> decayed -> deleted.

### Reset State

Selectively clear local state for a fresh start:

```bash
/wicked-garden:reset                   # interactive reset
```

Choose which domains to reset — crew projects, kanban boards, memories, search index, or everything.

## Search Index Management

### Building the Index

The code intelligence features require a built index:

```bash
/wicked-garden:search:index            # build/rebuild
/wicked-garden:search:stats            # check index health
/wicked-garden:search:validate         # verify consistency
```

### External Sources

Index content from outside your repo — documentation sites, wikis, API specs:

```bash
/wicked-garden:search:sources          # manage external sources
```

### Service Architecture Detection

Automatically detect your service architecture from infrastructure files (Docker, Kubernetes, Terraform):

```bash
/wicked-garden:search:service-map
```

## Scenarios (E2E Testing)

Write human-readable test scenarios in markdown that orchestrate real tools:

```markdown
# Login Flow

## Steps

1. POST /api/auth/login with valid credentials
   - Expect: 200 with JWT token

2. GET /api/profile with Authorization header
   - Expect: 200 with user data

3. POST /api/auth/login with invalid password
   - Expect: 401
```

```bash
/wicked-garden:scenarios:run scenarios/auth/login-flow.md
```

Supported tools: curl, Playwright, Cypress, k6 (load testing), Trivy (security), Semgrep (SAST), pa11y (accessibility).

## Patch — Cross-Language Changes

Propagate structural changes across your full stack:

```bash
# Add a field to a Java entity — auto-patches SQL, DAO, API, UI
/wicked-garden:patch:add-field User email:string

# Preview what would change
/wicked-garden:patch:plan User email:string

# Rename a symbol everywhere
/wicked-garden:patch:rename oldName newName
```

## Observability

Monitor the plugin itself:

```bash
/wicked-garden:observability:health    # run health probes
/wicked-garden:observability:traces    # view hook execution traces
/wicked-garden:observability:logs      # operational logs
/wicked-garden:observability:assert    # contract assertions
```

### Engineer Toolchain Discovery

Find what monitoring tools are available in your environment:

```bash
/wicked-garden:observability:toolchain
```

Discovers APM agents, logging CLIs, metrics tools, and cloud monitoring utilities on your PATH.

## Development Commands

These commands are for developing the wicked-garden plugin itself (available when working in the repo):

```bash
# Scaffold new components
/wg-scaffold skill my-skill --domain engineering
/wg-scaffold agent my-agent --domain platform

# Quality checks
/wg-check                     # quick structural validation
/wg-check --full              # full marketplace readiness

# Run acceptance tests
/wg-test scenarios/crew       # domain scenarios
/wg-test --all                # all scenarios

# Resolve GitHub issues
/wg-issue 42                  # triage + implement + PR
/wg-issue --list              # list open issues

# Release
/wg-release --dry-run         # preview changes
/wg-release --bump minor      # release with version bump
```

## Tips

### Let smaht work for you

You don't need to explicitly call context commands before working. The smaht context assembly layer intercepts every prompt and injects relevant context automatically — memories, active tasks, crew state, and code intelligence.

### Use crew for anything non-trivial

Even if you think a task is simple, `crew:start` auto-detects complexity. Simple tasks auto-finish in minutes. Complex ones get the rigor they need. The overhead for simple work is near zero.

### Store decisions, not facts

Memory is most valuable for recording *why* you chose something, not *what* you chose. "Chose Postgres because we need transactions for the payment flow" is more useful than "Using Postgres".

### Let search replace grep

`search:code` understands your codebase structurally. Instead of grepping for a string, search for a symbol and get its definition, references, and dependents in one query.

### Use jam for ambiguous problems

When you're not sure what to build or how to approach something, `jam:quick` gives you 4-6 perspectives in 60 seconds. It's faster than thinking alone and catches blind spots.
