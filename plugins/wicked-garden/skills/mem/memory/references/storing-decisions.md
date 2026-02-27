# Storing Decisions and Learnings

Guidelines for capturing memories that provide lasting value.

## What to Store

**Good candidates:**
- Architectural decisions with rationale ("Chose PostgreSQL for ACID compliance")
- Bug fixes with root cause ("Session timeout caused by stale JWT validation")
- Established patterns ("Always use dependency injection for services")
- User preferences ("Prefers functional style over OOP")
- Project conventions ("API routes follow /v1/resource/:id pattern")

**Skip these:**
- Trivial fixes (typos, formatting)
- Temporary workarounds
- Information already in docs
- Context that won't be relevant later

## Structuring Memories

### Decision Memories

```bash
/wicked-garden:mem-store "Chose PostgreSQL over MongoDB for payment system. \
Reasons: ACID compliance, complex joins for reporting, team experience. \
Trade-off: Less schema flexibility." --type decision --tags database,architecture
```

### Procedural Memories

```bash
/wicked-garden:mem-store "Authentication flow: 1) Validate JWT on backend, \
2) Check token not revoked, 3) Extract claims, 4) Set request context. \
Never trust client-side token validation." --type procedural --tags auth,security
```

### Episodic Memories

```bash
/wicked-garden:mem-store "Session bug 2026-01-18: JWT migration broke session \
middleware. Root cause: validation order changed. Fix: moved token check \
before session lookup." --type episodic --tags auth,bug-fix
```

## Tagging Strategy

Use consistent, hierarchical tags:

| Category | Examples |
|----------|----------|
| Domain | `auth`, `payments`, `users`, `api` |
| Type | `bug-fix`, `refactor`, `feature` |
| Tech | `postgres`, `redis`, `graphql` |
| Concern | `security`, `performance`, `testing` |

## Importance Levels

- **high**: Decisions affecting architecture, security, or multiple systems
- **medium**: Standard learnings and patterns (default)
- **low**: Minor preferences or short-term context

## Scope Selection

- **project**: Most memories - specific to current codebase
- **core**: Cross-project learnings (language patterns, tool preferences)

## Anti-patterns

1. **Over-storing**: Not everything needs a memory
2. **Vague content**: "Fixed the auth bug" - missing what/why/how
3. **Missing tags**: Makes recall harder
4. **Wrong type**: Episodic for permanent knowledge loses it after TTL
