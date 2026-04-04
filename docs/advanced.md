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
/wicked-garden:smaht:collaborate "Review this authentication implementation"

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
/wicked-garden:qe:run scenarios/auth/login-flow.md
```

Supported tools: curl, Playwright, Cypress, k6 (load testing), Trivy (security), Semgrep (SAST), pa11y (accessibility).

## Patch — Cross-Language Changes

Propagate structural changes across your full stack:

```bash
# Add a field to a Java entity — auto-patches SQL, DAO, API, UI
/wicked-garden:engineering:add-field User email:string

# Preview what would change
/wicked-garden:engineering:plan User email:string

# Rename a symbol everywhere
/wicked-garden:engineering:rename oldName newName
```

## Observability

Monitor the plugin itself:

```bash
/wicked-garden:platform:health    # run health probes
/wicked-garden:platform:traces    # view hook execution traces
/wicked-garden:platform:logs      # operational logs
/wicked-garden:platform:assert    # contract assertions
```

### Engineer Toolchain Discovery

Find what monitoring tools are available in your environment:

```bash
/wicked-garden:platform:toolchain
```

Discovers APM agents, logging CLIs, metrics tools, and cloud monitoring utilities on your PATH.

## Event Log (v3.0+)

Every domain write is logged to a unified event store. Query cross-domain activity:

```bash
# What happened in the last 7 days?
/wicked-garden:smaht:events-query --since 7d

# What happened on a specific project?
/wicked-garden:smaht:events-query --project my-project

# Search for auth-related activity across all domains
/wicked-garden:smaht:events-query --fts "auth migration"

# Session briefing — what happened since last time
/wicked-garden:smaht:briefing
```

The event log is consumed automatically by smaht context assembly, mem:recall (cross-domain supplementation), and the briefing command. Events are retained for 90 days.

### Knowledge Graph Integration (v3.4.0+)

Events are also consumed by the knowledge graph (`scripts/smaht/knowledge_graph.py`), which maintains typed entities (requirements, designs, tasks, tests, decisions, incidents, acceptance criteria, evidence) and their relationships. The knowledge graph provides structured traversal that complements the event log's chronological view. See [Architecture: Knowledge Graph](architecture.md#knowledge-graph-v340) for details.

## Cross-Phase Intelligence (v3.4.0+)

v3.4.0 added 9 modules across 5 domains that make crew phases aware of each other. Instead of isolated phases that hand off deliverables, phases now share traceability links, artifact state, verification evidence, and impact analysis.

Key capabilities:

- **Traceability links** between requirements, designs, code, tests, and evidence
- **Artifact state machine** enforcing lifecycle transitions (DRAFT through CLOSED)
- **6-point verification protocol** for evidence-based review gates
- **Cross-phase impact analysis** combining traceability, knowledge graph, and phase metadata
- **Phase-aware memory scoring** so recall prioritizes relevant context for the current phase
- **Council consensus** with structured dissent tracking for multi-model decisions

For the full guide with CLI examples, see [Cross-Phase Intelligence](cross-phase-intelligence.md).

## Council Consensus (v3.4.0+)

The jam domain's `consensus.py` provides a structured 3-stage protocol for council sessions where multiple AI models (or specialist personas) evaluate a question independently.

### 3-Stage Protocol

1. **Independent Proposals** -- Each participant submits a proposal with rationale, confidence score (0.0-1.0), and concerns
2. **Cross-Review** -- Participants review each other's proposals, noting agreements, disagreements (with counter-rationale), and questions
3. **Synthesis** -- Consensus points are identified via word-overlap clustering; dissenting views are extracted and classified by strength

### Dissent Tracking

Dissenting views are classified into three levels:

- **Strong**: Raised by 2+ personas, or has detailed counter-rationale (>50 characters)
- **Moderate**: Raised by 1 persona with rationale
- **Mild**: Noted as concern or unresolved question without strong objection

### Memory Integration

`format_for_memory()` converts consensus results into a dict suitable for `mem:store`, preserving the decision, confidence, participant count, and strong dissents as structured metadata.

```bash
# Run full consensus protocol
consensus.py synthesize --proposals proposals.json --reviews reviews.json --question "Should we use microservices?"

# Score consensus without synthesis
consensus.py score --proposals proposals.json

# Format results for display (with dissent)
consensus.py format --result result.json --show-dissent
```

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
