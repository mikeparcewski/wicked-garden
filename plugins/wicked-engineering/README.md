# wicked-engineering

10 coordinated specialist agents -- senior engineers, architects, frontend/backend specialists, tech writers, and API documentarians -- that deliver architecture review, security findings, and code quality feedback in a single pass, not a single "looks good to me."

## Quick Start

```bash
# Install
claude plugin install wicked-engineering@wicked-garden

# Review code before a PR
/wicked-engineering:review src/auth.ts

# Debug a production issue
/wicked-engineering:debug "Auth fails after 30 minutes"
```

## Workflows

### Pre-PR code review

Run a review against a file or directory and get actionable findings, not a summary:

```
/wicked-engineering:review src/auth.ts

Strengths:
- Clear separation of concerns
- Comprehensive error handling

Issues:
1. Password validation logic duplicated (L45, L89)
   -> Extract to shared validator
2. No rate limiting on login attempts
   -> Add exponential backoff
3. Session tokens not rotated on privilege escalation
   -> Implement token rotation

Recommendations:
- Use bcrypt rounds >= 12
- Add audit logging for auth events
```

### New feature planning

Plan before you write code, then check the design:

```bash
# 1. Plan the approach and get file-level steps
/wicked-engineering:plan "Add real-time notifications"

# 2. Review architecture of the new component
/wicked-engineering:arch src/notifications/

# 3. Generate API docs for the new endpoints
/wicked-engineering:docs src/api/notifications/
```

### Production debugging

Systematic root cause analysis -- not just "check your logs":

```bash
/wicked-engineering:debug "Users see 500 errors on checkout"
# Collects: stack traces, recent changes, reproduction steps
# Produces: root cause hypothesis, fix recommendation, regression tests
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-engineering:review` | Code review with senior engineering perspective on quality, patterns, and maintainability | `/wicked-engineering:review src/auth.ts --focus security` |
| `/wicked-engineering:debug` | Systematic debugging session with root cause analysis | `/wicked-engineering:debug "Memory leak in production"` |
| `/wicked-engineering:arch` | Architecture analysis and design recommendations | `/wicked-engineering:arch src/services/ --scope service` |
| `/wicked-engineering:plan` | Implementation planning with file-level steps and risk assessment | `/wicked-engineering:plan "Migrate to microservices"` |
| `/wicked-engineering:docs` | Generate or improve API docs, READMEs, guides, or inline comments | `/wicked-engineering:docs src/api/ --type api` |

## Agents

| Agent | Focus |
|-------|-------|
| `senior-engineer` | Code quality, design patterns, implementation guidance |
| `debugger` | Root cause analysis, systematic debugging |
| `solution-architect` | End-to-end system design, technology choices |
| `system-designer` | Component boundaries, interfaces, modularity |
| `data-architect` | Data models, storage strategies, schema design |
| `integration-architect` | API contracts, service boundaries, protocol choices |
| `frontend-engineer` | React, CSS, browser APIs, accessibility |
| `backend-engineer` | APIs, databases, server-side patterns |
| `technical-writer` | Clear documentation, structure, audience-appropriate language |
| `api-documentarian` | OpenAPI specs, API references, endpoint docs |

## Skills

| Skill | What It Covers |
|-------|---------------|
| `architecture` | High-level system design and technology selection |
| `system-design` | Component boundaries, interfaces, and modularity |
| `integration` | API contracts, service integration, and protocol patterns |
| `engineering` | Code quality, SOLID principles, and best practices |
| `debugging` | Systematic debugging strategies and root cause analysis |
| `frontend` | Frontend engineering patterns and browser APIs |
| `backend` | Backend engineering patterns, databases, and server-side design |
| `generate` | Documentation generation from code |
| `sync` | Keeping docs in sync with code changes |
| `audit` | Documentation coverage and gap analysis |

## Integration

| Plugin | What It Unlocks | Without It |
|--------|----------------|------------|
| wicked-qe | Quality engineering and test strategy layered on top of code review | Engineering-only reviews without test coverage analysis |
| wicked-crew | Auto-engaged during design, build, and review phases | Use commands directly |
| wicked-mem | Cross-session learning -- past fixes and patterns surfaced per review | Session-only context, no recall of previous decisions |
| wicked-workbench | Dashboard visualization of review findings | Text output only |

## License

MIT
