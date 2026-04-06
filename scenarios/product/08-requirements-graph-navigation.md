---
name: requirements-graph-navigation
title: Navigate and Query a Requirements Graph
description: Read, refresh meta.md, check coverage, find gaps, and lint an existing requirements graph
type: requirements
difficulty: intermediate
estimated_minutes: 10
depends_on: 07-requirements-graph-authoring
---

# Navigate and Query a Requirements Graph

This scenario tests the requirements-navigate skill's ability to read, query, refresh, and lint an existing requirements graph. It assumes a graph has been authored (from scenario 07 or manually).

## Setup

Create a pre-built requirements graph with known properties:

```bash
mkdir -p ~/test-wicked-navigate/requirements/auth/US-001
mkdir -p ~/test-wicked-navigate/requirements/auth/US-002
mkdir -p ~/test-wicked-navigate/requirements/notifications/US-001

cd ~/test-wicked-navigate

# Root meta.md (intentionally stale — missing notifications area)
cat > requirements/meta.md <<'YAML'
---
type: requirements-root
project: test-project
created: 2026-04-01
status: draft
generated_at: 2026-04-01T00:00:00Z
children: 1
---

# Requirements: Test Project

A test project for navigation scenarios.

## Areas

| Area | Stories | ACs | P0 ACs | Coverage |
|------|---------|-----|--------|----------|
| auth | 2 | 3 | 2 | 0% |
YAML

# Auth area meta.md
cat > requirements/auth/meta.md <<'YAML'
---
id: auth
type: area
status: draft
tags: [authentication]
---

# Authentication

## Stories

| Story | Title | Priority | ACs | Status |
|-------|-------|----------|-----|--------|
| US-001 | Login | P0 | 2 | draft |
| US-002 | Logout | P1 | 1 | draft |
YAML

# Story with 2 ACs
cat > requirements/auth/US-001/meta.md <<'YAML'
---
id: auth/US-001
type: user-story
priority: P0
complexity: S
persona: end-user
status: draft
tags: [login]
---

# US-001: User Login

**As a** end-user
**I want** to log in with email and password
**So that** I can access my account

## Acceptance Criteria

| AC | Description | Priority | Category |
|----|-------------|----------|----------|
| AC-001 | Valid login | P0 | happy-path |
| AC-002 | Invalid login | P0 | error |
YAML

# AC with trace (implemented)
cat > requirements/auth/US-001/AC-001-valid-login.md <<'YAML'
---
id: auth/US-001/AC-001
type: acceptance-criterion
priority: P0
category: happy-path
story: auth/US-001
traces:
  - target: src/auth/login.ts
    type: IMPLEMENTED_BY
tags: [login]
---

Given valid email and password
When user submits login form
Then session is created and user sees dashboard
YAML

# AC without traces (gap)
cat > requirements/auth/US-001/AC-002-invalid-login.md <<'YAML'
---
id: auth/US-001/AC-002
type: acceptance-criterion
priority: P0
category: error
story: auth/US-001
tags: [login, error]
---

Given invalid password
When user submits login form
Then error message is shown and no session is created
YAML

# Logout story with 1 AC
cat > requirements/auth/US-002/meta.md <<'YAML'
---
id: auth/US-002
type: user-story
priority: P1
complexity: S
persona: end-user
status: draft
---

# US-002: User Logout

**As a** end-user
**I want** to log out
**So that** my session is terminated

## Acceptance Criteria

| AC | Description | Priority | Category |
|----|-------------|----------|----------|
| AC-001 | Clean logout | P1 | happy-path |
YAML

cat > requirements/auth/US-002/AC-001-clean-logout.md <<'YAML'
---
id: auth/US-002/AC-001
type: acceptance-criterion
priority: P1
category: happy-path
story: auth/US-002
tags: [logout, session]
---

Given active session
When user clicks logout
Then session is destroyed and user is redirected to login page
YAML

# Notifications area — exists but root meta.md doesn't list it (staleness test)
cat > requirements/notifications/meta.md <<'YAML'
---
id: notifications
type: area
status: draft
tags: [notifications, slack]
---

# Notifications

## Stories

| Story | Title | Priority | ACs | Status |
|-------|-------|----------|-----|--------|
| US-001 | Slack alerts | P1 | 1 | draft |
YAML

cat > requirements/notifications/US-001/meta.md <<'YAML'
---
id: notifications/US-001
type: user-story
priority: P1
complexity: M
persona: team-lead
status: draft
---

# US-001: Slack Alerts

**As a** team-lead
**I want** to receive Slack alerts on task changes
**So that** I stay informed without checking the app

## Acceptance Criteria

| AC | Description | Priority | Category |
|----|-------------|----------|----------|
| AC-001 | Task assignment alert | P1 | happy-path |
YAML

cat > requirements/notifications/US-001/AC-001-assignment-alert.md <<'YAML'
---
id: notifications/US-001/AC-001
type: acceptance-criterion
priority: P1
category: happy-path
story: notifications/US-001
tags: [slack, notifications]
---

Given a task is assigned to a team member
When the assignment is saved
Then a Slack message is sent to the assignee's channel
YAML

# Scope and questions
cat > requirements/_scope.md <<'YAML'
---
type: scope
---

# Scope

## In Scope
- Email/password authentication
- Slack notification integration

## Out of Scope
- OAuth/SSO
- SMS notifications
YAML

cat > requirements/_questions.md <<'YAML'
---
type: questions
---

# Open Questions

- [ ] Session timeout duration?
- [ ] Which Slack events trigger notifications?
YAML
```

## Steps

### 1. Progressive Reading (Depth Levels)

**Depth 0 — frontmatter scan**:

Ask the agent to list all ACs with their priority and trace status by reading only frontmatter.

**Expected**:
- [ ] Agent reads frontmatter from AC files without loading full content
- [ ] Reports 4 ACs total: 2 P0 (auth), 2 P1 (auth + notifications)
- [ ] Identifies AC-001-valid-login has IMPLEMENTED_BY trace
- [ ] Identifies remaining 3 ACs have no traces

**Depth 1 — meta.md reading**:

Ask the agent to summarize the auth area.

**Expected**:
- [ ] Agent reads `requirements/auth/meta.md` (not individual ACs)
- [ ] Reports 2 stories, 3 ACs

**Depth 2 — specific node**:

Ask about the valid login acceptance criterion specifically.

**Expected**:
- [ ] Agent reads `requirements/auth/US-001/AC-001-valid-login.md`
- [ ] Shows Given/When/Then and trace to `src/auth/login.ts`

### 2. Staleness Detection and meta.md Refresh

The root meta.md is intentionally stale — it lists only auth but notifications also exists.

Ask the agent to check if meta.md is current and refresh it.

**Expected**:
- [ ] Agent detects root meta.md is stale (missing notifications area)
- [ ] Regenerates root meta.md with both areas
- [ ] Updated table shows: auth (2 stories, 3 ACs) + notifications (1 story, 1 AC)
- [ ] `generated_at` timestamp is updated
- [ ] `children` count is updated

### 3. Coverage Query

Ask the agent for a coverage report.

**Expected output** (format may vary):
```
Coverage Report:
  auth/US-001/AC-001: IMPLEMENTED_BY ✓, TESTED_BY ✗
  auth/US-001/AC-002: IMPLEMENTED_BY ✗, TESTED_BY ✗
  auth/US-002/AC-001: IMPLEMENTED_BY ✗, TESTED_BY ✗
  notifications/US-001/AC-001: IMPLEMENTED_BY ✗, TESTED_BY ✗

  Total: 4 ACs
  Implemented: 1/4 (25%)
  Tested: 0/4 (0%)
  P0 gaps: AC-002 (auth/US-001) — no implementation
```

**Check**:
- [ ] All 4 ACs reported
- [ ] Correctly identifies AC-001 as partially covered (implemented, not tested)
- [ ] Correctly identifies P0 gap (AC-002 has no traces)
- [ ] Provides actionable summary

### 4. Gap Analysis

Ask the agent to find structural problems in the graph.

**Expected findings**:
- [ ] Stale root meta.md (if not already refreshed in step 2)
- [ ] P0 AC without IMPLEMENTED_BY (auth/US-001/AC-002)
- [ ] No ACs have TESTED_BY traces (test coverage = 0%)
- [ ] No broken trace targets flagged (the one trace target doesn't exist on disk, but that's expected pre-implementation)

### 5. Add a Trace and Re-query

Simulate implementation by adding a trace to AC-002:

```bash
# Update AC-002 to add an IMPLEMENTED_BY trace
```

Ask the agent to update `auth/US-001/AC-002-invalid-login.md` frontmatter with:
```yaml
traces:
  - target: src/auth/login.ts
    type: IMPLEMENTED_BY
```

Then re-run coverage.

**Expected**:
- [ ] Coverage now shows 2/4 implemented (50%)
- [ ] P0 gap resolved for AC-002
- [ ] Agent refreshes story meta.md if asked

## Expected Outcome

- Agent demonstrates progressive reading (frontmatter → meta.md → full content)
- Staleness detected and meta.md regenerated correctly
- Coverage report accurately reflects trace state
- Gap analysis finds actionable issues
- Trace updates reflected in re-queried coverage

## Success Criteria

- [ ] Progressive depth reading works (agent doesn't load all content upfront)
- [ ] Stale meta.md detected and refreshed with correct counts
- [ ] Coverage report accurate (1/4 implemented initially)
- [ ] Gap analysis identifies P0 AC without traces
- [ ] Trace addition reflected in subsequent coverage query
- [ ] Agent uses navigate skill patterns (not ad-hoc grep)

## Cleanup

```bash
rm -rf ~/test-wicked-navigate
```

## Value Demonstrated

**Real-world value**: Requirements graphs are only useful if they can be queried efficiently. The navigate skill enables:

- **Gate automation**: Crew gates check coverage from meta.md before allowing phase advancement
- **Progressive context loading**: Agent loads 5 tokens per AC (frontmatter) instead of 800 tokens (full monolith) to assess coverage
- **Living documentation**: meta.md regeneration keeps summaries accurate as the graph evolves
- **Actionable gaps**: "P0 AC-002 has no implementation trace" is more useful than "requirements are incomplete"
