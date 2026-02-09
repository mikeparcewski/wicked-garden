# wicked-engineering

10 specialist agents -- senior engineers, solution architects, debuggers, frontend/backend specialists, tech writers, and API documentarians -- with coordinated multi-pass workflows. One command gets you architecture review + code quality + security analysis, not just a single "looks good to me." Review, debug, design systems, and plan implementations before you write a line.

## Quick Start

```bash
# Install
claude plugin install wicked-engineering@wicked-garden

# Review code quality
/wicked-engineering:review src/auth.ts

# Debug a production issue
/wicked-engineering:debug "Auth fails after 30 minutes"

# Get architecture feedback
/wicked-engineering:arch src/services/

# Plan an implementation approach
/wicked-engineering:plan "Add OAuth2 support"

# Generate documentation
/wicked-engineering:docs src/api/
```

## Commands

| Command | What It Does | Example |
|---------|-------------|---------|
| `/wicked-engineering:review` | Code review with senior engineering perspective | `/wicked-engineering:review src/auth.ts` |
| `/wicked-engineering:debug` | Systematic debugging and root cause analysis | `/wicked-engineering:debug "Memory leak in production"` |
| `/wicked-engineering:arch` | Architecture analysis and recommendations | `/wicked-engineering:arch src/services/` |
| `/wicked-engineering:plan` | Implementation planning with risk assessment | `/wicked-engineering:plan "Migrate to microservices"` |
| `/wicked-engineering:docs` | Generate or improve documentation | `/wicked-engineering:docs src/api/` |

### Example: Code Review Output

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

## Agents

10 specialist agents for deep collaboration:

| Agent | Focus |
|-------|-------|
| `senior-engineer` | Code quality, patterns, implementation guidance |
| `debugger` | Root cause analysis, systematic debugging |
| `solution-architect` | End-to-end design, technology choices |
| `system-designer` | Component boundaries, interfaces |
| `data-architect` | Data models, storage strategies |
| `integration-architect` | API contracts, service boundaries |
| `frontend-engineer` | React, CSS, browser APIs, accessibility |
| `backend-engineer` | APIs, databases, server-side patterns |
| `technical-writer` | Clear documentation, structure |
| `api-documentarian` | OpenAPI specs, API references |

## Skills

| Skill | Purpose |
|-------|---------|
| `architecture` | High-level system design |
| `system-design` | Component boundaries and interfaces |
| `integration` | API and service integration |
| `engineering` | Code quality and best practices |
| `debugging` | Systematic debugging strategies |
| `frontend` | Frontend engineering patterns |
| `backend` | Backend engineering patterns |
| `generate` | Documentation generation |
| `sync` | Keep docs in sync with code |
| `audit` | Documentation coverage audits |

## Workflows

### Pre-PR Review

```bash
# Quick code review
/wicked-engineering:review src/auth.ts

# Architecture check for larger changes
/wicked-engineering:arch src/services/payment/
```

### New Feature Planning

```bash
# 1. Plan the approach
/wicked-engineering:plan "Add real-time notifications"

# 2. Review architecture
/wicked-engineering:arch src/notifications/

# 3. Generate API docs
/wicked-engineering:docs src/api/notifications/
```

### Production Debugging

```bash
# Systematic root cause analysis
/wicked-engineering:debug "Users see 500 errors on checkout"
```

## Integration

Works standalone. Enhanced with:

| Plugin | Enhancement | Without It |
|--------|-------------|------------|
| wicked-qe | Quality engineering, test strategy | Engineering-only reviews |
| wicked-crew | Auto-engaged in design/build/review phases | Use commands directly |
| wicked-mem | Cross-session learning | Session-only context |
| wicked-workbench | Dashboard visualization | Text output only |

## License

MIT
