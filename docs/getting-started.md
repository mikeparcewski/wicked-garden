# Getting Started

## Installation

```bash
claude plugins add mikeparcewski/wicked-garden
```

That's it. No configuration, no API keys, no external services required. Everything works locally out of the box.

## Your First Session

After installing, you can use any command immediately. Here are five ways to start:

### 1. Run a Full Workflow

For any non-trivial task, crew orchestrates the entire delivery:

```bash
/wicked-garden:crew:start "Add user authentication with OAuth2"
```

The facilitator (`skills/propose-process/`) scores 9 factors, detects one of 7 project archetypes, picks specialists by reading their `subagent_type` frontmatter, and selects phases from `phases.json`. A minimal-rigor task gets advisory self-check gates and finishes fast. A full-rigor task (compliance scope, high blast radius, schema migrations) gets multi-reviewer panels, per-archetype evidence demands, and a convergence-verify gate that blocks sign-off until every artifact is integrated.

### 2. Get a Code Review

```bash
/wicked-garden:engineering:review
```

Runs a multi-pass review from a senior engineering perspective — architecture, correctness, security, and maintainability. Works on your current diff or staged changes.

### 3. Search Your Codebase Structurally

```bash
/wicked-garden:search:code "handleAuth"
```

Not grep — structural code intelligence across 73 languages. Find functions, classes, and methods by name. Trace data lineage from UI to database. Analyze blast radius before changing a symbol.

### 4. Brainstorm a Decision

```bash
/wicked-garden:jam:quick "Redis vs Postgres for session storage?"
```

4-6 AI personas debate your question from technical, user, business, and process angles. Returns a synthesis with tradeoffs and a recommendation in about 60 seconds.

### 5. Analyze Data

```bash
/wicked-garden:data:analyze sales.csv "top 10 customers by revenue"
```

Plain English to SQL results via DuckDB. Works on CSV, Excel, Parquet — files up to 10GB+. Zero setup.

## Common Workflows

### "I have a bug to fix"

```bash
/wicked-garden:engineering:debug          # systematic root cause analysis
/wicked-garden:search:blast-radius buggyFunction  # what depends on it?
```

### "I need to understand this codebase"

```bash
/wicked-garden:smaht:onboard             # guided walkthrough of architecture
/wicked-garden:search:service-map         # detect service architecture
/wicked-garden:search:hotspots            # most-referenced symbols
```

### "I need to plan a feature"

```bash
/wicked-garden:crew:start "Add real-time notifications"  # full workflow
# OR standalone:
/wicked-garden:product:elicit             # requirements elicitation
/wicked-garden:jam:brainstorm "notification architecture" # explore approaches
/wicked-garden:engineering:arch           # architecture analysis
```

### "I need to check security/compliance"

```bash
/wicked-garden:platform:security          # OWASP vulnerability scan
/wicked-garden:platform:compliance        # SOC2/HIPAA/GDPR/PCI checks
/wicked-garden:platform:audit             # collect audit evidence
```

### "I need to write and run tests"

```bash
/wicked-testing:authoring "checkout flow"  # generate test scenarios
/wicked-testing:execution                  # evidence-gated acceptance testing
/wicked-testing:authoring                  # generate test code
```

### "I want to remember decisions across sessions"

```bash
/wicked-garden:mem:store "Chose Postgres over Redis for sessions — need transactions"
# ... 30 sessions later ...
/wicked-garden:mem:recall "session storage decisions"
```

### "I need to trace decisions across phases"

```bash
/wicked-garden:crew:evidence            # show evidence and traceability for current project
/wicked-garden:crew:status              # see phase state, artifact lifecycle, linked deliverables
```

Crew automatically creates traceability links between phase deliverables — a design decision in the clarify phase is linked forward to the architecture artifact, implementation, and test plan. Use `crew:evidence` to see the full chain.

## How Commands Work

All commands follow the pattern `/wicked-garden:{domain}:{command}`:

```bash
/wicked-garden:crew:start        # crew domain, start command
/wicked-garden:search:lineage    # search domain, lineage command
/wicked-garden:platform:security # platform domain, security command
```

Every domain also has a help command:

```bash
/wicked-garden:crew:help
/wicked-garden:engineering:help
/wicked-garden:help              # list everything
```

## What Happens Behind the Scenes

When you run a command, a context assembly layer called **smaht** intercepts your prompt and enriches it with relevant context — recent memory, active crew projects, native tasks, and code intelligence. This happens automatically on every prompt, not just wicked-garden commands.

Every `TaskCreate` / `TaskUpdate` carries a structured metadata envelope (`chain_id`, `event_type`, `source_agent`, `phase`, `archetype`) validated by a PreToolUse hook. A SubagentStart hook reads the event type and injects the matching procedure bundle — R1–R6 bulletproof standards for coding-tasks, the Gate Finding Protocol for gate-findings, and per-role procedures for other types.

During crew workflows, the system also tracks **traceability links** between phase deliverables (so a clarify decision connects forward to design artifacts and implementation), manages **artifact states** through a 6-state convergence lifecycle (Designed → Built → Wired → Tested → Integrated → Verified) with stall detection, and runs a **verification protocol** at quality gates to ensure evidence-based advancement.

Your data is stored locally in `~/.something-wicked/wicked-garden/` as JSON files, scoped per working directory. No data leaves your machine unless you configure external integrations.

## Next Steps

- [Domains](domains.md) — browse all 13 domains and their commands
- [Crew Workflow](crew-workflow.md) — facilitator rubric, archetype detection, gates, convergence
- [Architecture](architecture.md) — storage, native task metadata, gate policy, context assembly
- [Advanced Usage](advanced.md) — multi-model reviews, yolo mode, customization, dev tools
- [Cross-Phase Intelligence](cross-phase-intelligence.md) — traceability, verification, convergence, knowledge graph
