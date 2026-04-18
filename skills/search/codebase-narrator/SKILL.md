---
name: codebase-narrator
description: |
  Narrate codebase structure and architecture for orientation — directory layout,
  key modules, data flows, technical decisions, and code health. A query +
  synthesis capability rather than a persistent role; produces a guided
  reading order and flags gotchas for newcomers.

  Use when: "give me an architecture walkthrough", "narrate this codebase",
  "explain how this project is organized", "code navigation", "where should
  I start reading".
---

# Codebase Narrator

Analyzes a codebase and produces a **narrative** — not a file list, but a story
of how the project is organized, why things are where they are, what to read
first, and what the non-obvious gotchas are. Works on any language or stack.

## Quick Start

Invoke this skill when a human (or a subagent) needs orientation on an
unfamiliar codebase. Typical outputs:

- Big-picture summary (what this project does and how it's built)
- Directory map with annotations
- Key modules with responsibilities, dependencies, dependents
- Data flow ASCII diagram
- Technical-decision table
- Code-health signals
- Reading order ("start here, then here, then here")
- Gotchas list (non-obvious patterns, common newcomer mistakes)

## First Strategy: Use wicked-* Ecosystem

- **Search**: Use wicked-garden:search to find symbols, imports, and patterns
- **Memory**: Use wicked-garden:mem to recall past architecture decisions
- **Native tasks**: Inspect current work via TaskCreate/TaskUpdate with
  `metadata={event_type, chain_id, source_agent, phase}`

If wicked-* tools are available, prefer them over manual grep/find.

## Process

### 1. Scan Project Structure

```bash
# Depth-limited directory tree
find . -maxdepth 3 -type f | head -100
```

Or use the search index:
```
/wicked-garden:search:code "class |function |def |interface " --path .
```

Identify:
- **Language(s)**: primary + secondary
- **Framework(s)**: web framework, ORM, test framework
- **Build system**: how the project builds
- **Package manager**: dependency management

### 2. Identify Key Modules

Find the architectural pillars:
- **Entry points**: main files, server startup, CLI entry
- **Core domain**: business logic, models, entities
- **API layer**: routes, controllers, endpoints
- **Data layer**: database models, migrations, repositories
- **Infrastructure**: config, deployment, CI/CD

For each module: what does it do? what does it depend on? what depends on it?

### 3. Trace Data Flows

```
User Request → API Layer → Business Logic → Data Layer → Response
     ↓              ↓            ↓              ↓
  Validation    Auth/Authz   Processing    Persistence
```

Map: happy path, error paths, async flows (background jobs, events, queues),
external calls (third-party API integrations).

### 4. Surface Technical Decisions

Visible in the code:
- **Architecture style**: monolith, microservices, serverless
- **Design patterns**: repository, factory, observer, etc.
- **Configuration approach**: env vars, config files, secrets management
- **Testing strategy**: unit, integration, e2e coverage

### 5. Assess Code Health

- **Complexity hotspots**: large files, deep nesting
- **Tech debt markers**: TODO/FIXME/HACK counts
- **Test coverage**: test-to-code ratio
- **Documentation**: README quality, inline comments
- **Dependency health**: outdated or vulnerable deps

### 6. Generate Narrative

See [refs/output-template.md](refs/output-template.md) for the full structure.

## Narrative Quality

Good codebase narratives:
- **Tell a story** — not just a file list, but why things are where they are
- **Prioritize** — start with the most important modules
- **Connect the dots** — show how pieces relate
- **Flag surprises** — call out non-obvious patterns
- **Guide exploration** — give a reading order, not just a map

## Common Pitfalls

- Listing every file without explaining relationships
- Assuming reader knows the framework conventions
- Skipping the "why" behind architectural choices
- Ignoring test structure (tests reveal intent)
- Missing configuration and deployment patterns

## See Also

- [refs/output-template.md](refs/output-template.md) — full output format
- `/wicked-garden:search:blast-radius` — for impact analysis of specific symbols
- `/wicked-garden:search:stats` — quick index stats before diving in
