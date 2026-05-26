# Getting Started

## Installation

```bash
claude plugins add mikeparcewski/wicked-garden
```

No API keys, no external services, no cloud — everything runs locally.

### Required peer plugins

Four companion plugins are **required** — `/wicked-garden:setup` verifies all four and blocks until they are present. They are required at install but resilient at runtime (the garden degrades gracefully if one goes missing mid-session).

```bash
npx wicked-testing install    # wicked-testing — evidence-gated testing
npx wicked-vault-install      # wicked-vault — vault-backed evidence (gates re-derive against it)
/plugin install wicked-brain  # wicked-brain — cross-session memory + search
/plugin install wicked-bus    # wicked-bus — event bridge
```

`wicked-testing` and `wicked-vault` install locally via npm; `wicked-brain` and `wicked-bus` install as Claude Code plugins. Gates re-derive "done" through wicked-vault (fail-closed) — a claim is never self-asserted.

## Your First Session

There is no fixed pipeline. Work is organized around **9 work-shape archetypes** — `triage`, `explore`, `specify`, `decide`, `ship`, `review`, `incident`, `build`, and `migrate`. Each archetype owns its own phase shape, what it produces, and how much human-in-the-loop discipline it demands. After installing, you can use any command immediately. Here are five ways to start:

### 1. Just Describe What You Want

Type a plain prompt and wicked-garden classifies it into one or more archetypes automatically:

```
Add user authentication with OAuth2
```

A schema-changing feature classifies as `build + migrate`; a risky deploy as `ship + review`. The detector returns a *set*, not a single match, and runs them in dependency order. Each archetype then runs its own phase shape — `build` plans, implements, tests, and reviews; `migrate` expands, backfills, cuts over, and contracts.

### 2. Invoke an Archetype Directly

When you already know the shape of the work, skip auto-routing and call the archetype yourself:

```bash
/wicked-garden:archetype:build "Add user authentication with OAuth2"
/wicked-garden:archetype:incident "checkout 500s spiking in prod"
/wicked-garden:archetype:migrate "split orders table into orders + line_items"
/wicked-garden:archetype:decide "Redis vs Postgres for session storage"
```

All nine are available: `triage`, `explore`, `specify`, `decide`, `ship`, `review`, `incident`, `build`, `migrate`. Gates re-derive "done" through wicked-vault (fail-closed) — sign-off is evidence-backed, never self-asserted.

### 3. Use a Domain Skill Directly

Archetypes invoke the domain skill/agent families (engineering, platform, product, data, jam, search, agentic, persona, delivery, smaht) under the hood, but you can call them directly when you want a single focused pass:

```bash
/wicked-garden:engineering:review                          # senior-perspective code review
/wicked-garden:jam:quick "Redis vs Postgres for sessions?" # multi-persona debate, ~60s
/wicked-garden:data:analyze sales.csv "top 10 by revenue"  # plain English → SQL via DuckDB
```

### 4. Compile a Standalone Build Gate

```bash
/wicked-garden:compile ./my-service --trigger hook,ci  # emit a vault-backed gate into ./my-service/.wicked/
```

Detects the repo's test/lint/build commands and emits a self-contained `gate.py` that re-derives the build's claims through wicked-vault — runs with **no wicked-garden runtime present** (resolves the vault via npx). The `--trigger` flag installs a git pre-push hook and/or GitHub Actions workflow.

### 5. Remember Decisions Across Sessions

Memory is provided by the [wicked-brain](https://github.com/mikeparcewski/wicked-brain) peer plugin:

```
Skill(skill="wicked-brain:memory", args="store \"Chose Postgres over Redis for sessions — need transactions\" --type decision")
# ... 30 sessions later ...
Skill(skill="wicked-brain:memory", args="recall \"session storage decisions\" --filter_type decision")
```

Search the same brain instead of grep — `wicked-brain:search "handleAuth"` gives structural code intelligence, lineage, and blast radius.

## Common Workflows

### "I have a bug to fix"

```bash
/wicked-garden:engineering:debug                   # systematic root cause analysis
/wicked-garden:search:blast-radius buggyFunction   # what depends on it?
```

### "Something is on fire in prod"

```bash
/wicked-garden:archetype:incident "checkout 500s spiking"  # triage → investigate → mitigate → resolve → followup
```

### "I need to understand this codebase"

```bash
/wicked-garden:search:service-map         # detect service architecture
/wicked-garden:search:hotspots            # most-referenced symbols
wicked-brain:search "auth flow"           # structural search across the brain
```

### "I need to plan and build a feature"

```bash
/wicked-garden:archetype:build "Add real-time notifications"  # plan → implement → test → review
# OR break it down by hand:
/wicked-garden:archetype:specify "real-time notifications"    # elicit → structure → validate (SMART criteria)
/wicked-garden:archetype:explore "notification architecture"  # frame → diverge → converge
/wicked-garden:engineering:arch                               # architecture analysis
```

### "I need to make a decision"

```bash
/wicked-garden:archetype:decide "monolith vs microservices"  # brief → options → score → record (produces an ADR)
/wicked-garden:jam:council "should we adopt event sourcing?"  # independent multi-model perspectives
```

### "I need to ship and review a change"

```bash
/wicked-garden:archetype:ship "v2 rollout"     # canary → ramp → full → soak
/wicked-garden:archetype:review                # scope → assess → findings → remediate-or-accept
```

### "I need to migrate a schema"

```bash
/wicked-garden:archetype:migrate "split orders into orders + line_items"  # plan → expand → backfill → cutover → contract
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
```

## How Commands Work

Archetype commands follow `/wicked-garden:archetype:{name}`; domain commands follow `/wicked-garden:{domain}:{command}`:

```bash
/wicked-garden:archetype:build   # archetype namespace, build work-shape
/wicked-garden:search:lineage    # search domain, lineage command
/wicked-garden:platform:security # platform domain, security command
```

To list everything:

```bash
/wicked-garden:help              # list every command
```

## What Happens Behind the Scenes

When you submit a prompt, a `UserPromptSubmit` hook runs the archetype detector and emits a steering reminder for the matched work-shape(s). The selected archetype then drives its own phase shape — there is no universal pipeline forcing every kind of work through the same gates.

A context assembly layer called **smaht** enriches prompts with relevant context — recent memory, active work, native tasks, and code intelligence. Every `TaskCreate` / `TaskUpdate` carries a structured metadata envelope (`chain_id`, `event_type`, `source_agent`, `phase`, `archetype`) validated by a PreToolUse hook, and a SubagentStart hook injects the matching procedure bundle — R1–R6 bulletproof standards for coding tasks, the Gate Finding Protocol for review findings, and per-role procedures otherwise.

Gates re-derive every claim through wicked-vault (fail-closed): "done" is *re-derived from evidence*, never self-asserted. Hard gates (incident mitigate, migrate cutover, review final-verdict) require explicit human approval; discrete gates auto-pass only when their produces contract is met.

Your data is stored locally in `~/.something-wicked/wicked-garden/` as JSON files, scoped per working directory. No data leaves your machine unless you configure external integrations.

## Next Steps

- [Archetypes](v11/archetypes.md) — the 9 work-shapes: phases, produces, HITL discipline, cost bands
- [Required Peers](required-peers.md) — wicked-testing, wicked-vault, wicked-brain, wicked-bus
- [Compiler](compiler.md) — emit a standalone, vault-backed build gate into any repo
- [Domains](domains.md) — browse the domain skill/agent families and their commands
