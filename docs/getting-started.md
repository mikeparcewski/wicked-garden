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

Crew analyzes your description, detects signals (security, architecture, etc.), scores complexity, selects phases, and routes to the right specialists. For simple tasks (complexity 0-2), it auto-finishes without prompting you. For complex work, it walks you through clarify, design, test-strategy, build, test, and review phases.

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
/wicked-garden:qe:scenarios "checkout flow"  # generate test scenarios
/wicked-garden:qe:acceptance                  # evidence-gated acceptance testing
/wicked-garden:qe:automate                    # generate test code
```

### "I want to remember decisions across sessions"

```bash
/wicked-garden:mem:store "Chose Postgres over Redis for sessions — need transactions"
# ... 30 sessions later ...
/wicked-garden:mem:recall "session storage decisions"
```

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

When you run a command, a context assembly layer called **smaht** intercepts your prompt and enriches it with relevant context — recent memory, active crew projects, kanban tasks, and code intelligence. This happens automatically on every prompt, not just wicked-garden commands.

Your data is stored locally in `~/.something-wicked/wicked-garden/` as JSON files, scoped per working directory. No data leaves your machine unless you configure external integrations.

## Next Steps

- [Domains](domains.md) — browse all 16 domains and their commands
- [Crew Workflow](crew-workflow.md) — understand the signal-driven workflow engine
- [Architecture](architecture.md) — how storage, routing, and context assembly work
- [Advanced Usage](advanced.md) — multi-model reviews, customization, dev tools
