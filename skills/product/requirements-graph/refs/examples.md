# Requirements Graph: Worked Examples

## Example 1: Authentication Feature

### Directory Structure

```
requirements/
  meta.md
  _scope.md
  _risks.md
  _questions.md
  auth/
    meta.md
    US-001/
      meta.md
      AC-001-valid-login.md
      AC-002-invalid-credentials.md
      AC-003-account-lockout.md
    US-002/
      meta.md
      AC-001-reset-email.md
      AC-002-reset-link-expiry.md
    NFR-001-login-performance.md
    NFR-002-password-encryption.md
  _decisions/
    DEC-001-bcrypt-over-argon2.md
```

### Root meta.md

```yaml
---
type: requirements-root
project: user-portal
created: 2026-04-05
status: draft
---

# Requirements: User Portal

Self-service portal for user account management and dashboard access.

## Areas

| Area | Stories | ACs | P0 ACs | Coverage |
|------|---------|-----|--------|----------|
| auth | 2 | 5 | 3 | 0% |

## Scope
See: [_scope.md](_scope.md)

## Open Questions
See: [_questions.md](_questions.md)
```

### AC Node: AC-001-valid-login.md

```yaml
---
id: auth/US-001/AC-001
type: acceptance-criterion
priority: P0
category: happy-path
story: auth/US-001
tags: [login, session, redirect]
---

Given valid email and password
When user submits the login form
Then user is redirected to /dashboard and a session cookie is set
```

### AC Node with traces (after implementation):

```yaml
---
id: auth/US-001/AC-001
type: acceptance-criterion
priority: P0
category: happy-path
story: auth/US-001
tags: [login, session, redirect]
traces:
  - target: src/routes/auth/login.ts
    type: IMPLEMENTED_BY
  - target: src/middleware/session.ts
    type: IMPLEMENTED_BY
  - target: tests/auth/login.test.ts
    type: TESTED_BY
---

Given valid email and password
When user submits the login form
Then user is redirected to /dashboard and a session cookie is set
```

### Story meta.md: US-001/meta.md

```yaml
---
id: auth/US-001
type: user-story
priority: P0
complexity: M
persona: end-user
status: draft
traces:
  - target: phases/design/auth-flow.md
    type: TRACES_TO
tags: [authentication, login]
---

# US-001: User Login

**As a** end-user
**I want** to log in with my email and password
**So that** I can access my personalized dashboard

## Acceptance Criteria

| AC | Description | Priority | Category |
|----|-------------|----------|----------|
| AC-001 | Valid login redirects to dashboard | P0 | happy-path |
| AC-002 | Invalid creds show error message | P0 | error |
| AC-003 | Account locks after 3 failures | P1 | edge-case |

## Dependencies
- Session store (Redis) configured
- Email validation library

## Open Questions
- Session timeout: 30 min or user-configurable?
```

### NFR Node: NFR-001-login-performance.md

```yaml
---
id: auth/NFR-001
type: nfr
priority: P1
category: performance
target: "< 2s response time at 1000 concurrent logins"
measured_by: k6 load test in CI
tags: [performance, auth, load-testing]
---

Login endpoint must respond within 2 seconds under load of 1000
concurrent authentication requests. Measured via k6 load test
running against staging environment in CI pipeline.
```

### Decision Node: DEC-001-bcrypt-over-argon2.md

```yaml
---
id: _decisions/DEC-001
type: decision
status: accepted
date: 2026-04-05
tags: [security, password-hashing]
---

# DEC-001: Use bcrypt over Argon2 for password hashing

## Context
Need a password hashing algorithm for user authentication.

## Decision
Use bcrypt with cost factor 12.

## Rationale
- Wider library support across our stack (Node.js, Python)
- Argon2 requires native compilation — complicates CI
- bcrypt at cost 12 meets our security bar per OWASP guidelines

## Consequences
- Slightly less memory-hard than Argon2
- May revisit when Argon2 library support improves
```

## Example 2: Simple Feature (3 ACs)

For a small feature, the graph is still lean:

```
requirements/
  meta.md
  csv-export/
    meta.md
    US-001/
      meta.md
      AC-001-export-button.md
      AC-002-csv-format.md
      AC-003-large-dataset.md
```

Total files: 6 (3 meta.md + 3 ACs). Each AC is ~10 lines.
Compare to the old monolith: 1 file at 200+ lines.

The graph approach scales down cleanly — no empty sections, no
boilerplate for risks/assumptions/appendices unless you need them.

## Token Cost Comparison

Reading the auth example above:

| Approach | Tokens |
|----------|--------|
| Old monolith (full auth requirements) | ~800 |
| Graph: root meta.md only (depth 1) | ~100 |
| Graph: area meta.md (depth 1) | ~80 |
| Graph: story meta.md (depth 1) | ~120 |
| Graph: single AC (depth 2) | ~40 |
| Graph: all frontmatter (depth 0) | ~60 |

The agent loads only what it needs. Gate checks read meta.md.
Implementation reads specific ACs. No wasted context.
