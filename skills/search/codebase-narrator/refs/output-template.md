# Codebase Narrator — Output Template

## Codebase Narrative: {project_name}

### The Big Picture

{2-3 sentences describing what this project does and how it's built. Pitch it
to a new hire, not an expert.}

### Architecture Style

**{style}** — {why this approach}

### Directory Map

```
{annotated directory tree}

project-root/
├── src/              — main application code
│   ├── api/          — HTTP layer, routes, controllers
│   ├── domain/       — business logic, entities, services
│   ├── data/         — database access, repositories, migrations
│   └── infra/        — config, logging, telemetry
├── tests/            — unit + integration tests (mirrors src/)
├── scripts/          — operational scripts
├── config/           — environment config
├── docs/             — architecture + how-to guides
└── .github/          — CI/CD pipelines
```

### Key Modules

#### {Module 1}: {purpose}

- **Location**: `{path}`
- **Responsibility**: {what it does}
- **Key files**: {important files}
- **Dependencies**: {what it needs}
- **Dependents**: {what needs it}

#### {Module 2}: {purpose}
...

### Data Flow

```
{ASCII diagram or Mermaid}

[Client] → [API Gateway] → [Service Layer]
                                ↓
                           [Repository]
                                ↓
                           [Database]
```

Happy path, error path, async flows, external calls.

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| {area}   | {choice} | {why}  |
| Framework | FastAPI | async support, type hints |
| Database | Postgres | transactions + JSONB |
| Queue | RabbitMQ | team familiarity |

### Code Health

| Signal | Status | Notes |
|--------|--------|-------|
| Complexity | LOW / MED / HIGH | {detail} |
| Test coverage | {%} | {detail} |
| Tech debt | {count} markers | {detail} |
| Documentation | {quality} | {detail} |
| Dependencies | {current / stale / vulnerable} | {detail} |

### Where to Start Reading

1. **{file}** — {why start here}
2. **{file}** — {what you'll learn}
3. **{file}** — {how it connects}

### Gotchas

- {non-obvious pattern or convention}
- {common mistake newcomers make}
- {important but poorly documented behavior}
- {legacy naming that no longer matches the code}
- {any monkey-patched dependency or hand-rolled framework fork}

### Next Steps

- Run `{command}` to bring the app up locally
- Read `docs/{file}.md` for the deeper architectural rationale
- Key people to talk to: {roles / teams}, for {topic}
