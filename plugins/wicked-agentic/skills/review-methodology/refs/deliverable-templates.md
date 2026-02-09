# Review Deliverable Templates

Complete templates for all review report types.

## 1. Issue Inventory (Detailed Report)

```markdown
# Agentic System Review - Issue Inventory
Date: 2026-02-05
Reviewer: [Name]

## Summary
- Total Issues: 47
- Critical: 3
- High: 12
- Medium: 20
- Low: 12

## Critical Issues (P0)

### ISSUE-001: No input validation
**Severity:** Critical
**Category:** Security
**Component:** UserInputHandler

**Description:**
User inputs are passed directly to SQL queries without validation or sanitization.

**Evidence:**
```python
query = f"SELECT * FROM users WHERE name = '{user_input}'"
```

**Impact:**
SQL injection vulnerability allowing arbitrary database access.

**Root Cause:**
No input validation layer implemented.

**Recommendation:**
Implement parameterized queries and input validation.

**Effort Estimate:** 3 days

**Priority:** P0

[Additional issues...]
```

## 2. Executive Summary (1-Pager)

```markdown
# Executive Summary - Agentic System Review

## Overall Assessment
The system shows promise but has critical security and reliability gaps
that must be addressed before production deployment.

## Critical Findings
1. Input validation is missing, creating SQL injection risk (ISSUE-001)
2. No circuit breakers, leading to cascading failures (ISSUE-005)
3. Credentials stored in code (ISSUE-008)

## Top 3 Recommendations
1. Implement comprehensive input validation (1 week)
2. Add circuit breakers and retry logic (3 days)
3. Move credentials to secure vault (1 day)

## Estimated Effort
- Critical fixes: 2 weeks
- High priority: 4 weeks
- Total: 6 weeks to production-ready

## Maturity Assessment
Current Level: 1 (Functional)
Target Level: 3 (Production)
Gap: Safety, Reliability, Observability
```

## 3. Remediation Roadmap

```markdown
# Remediation Roadmap

## Phase 1: Critical Fixes (Week 1-2)
- [ ] Add input validation (ISSUE-001)
- [ ] Remove hardcoded credentials (ISSUE-008)
- [ ] Add circuit breakers (ISSUE-005)

## Phase 2: High Priority (Week 3-6)
- [ ] Implement observability (ISSUE-010)
- [ ] Add resource limits (ISSUE-012)
- [ ] Externalize prompts (ISSUE-015)

## Phase 3: Medium Priority (Week 7-10)
- [ ] Add caching (ISSUE-020)
- [ ] Improve documentation (ISSUE-025)
- [ ] Optimize token usage (ISSUE-030)

## Quick Wins (Can do anytime)
- [ ] Add type hints (ISSUE-040)
- [ ] Fix linting errors (ISSUE-045)
```

## 4. Metrics Dashboard

```
Issue Distribution by Severity:
Critical  [███░░░░░░░] 3
High      [█████████░] 12
Medium    [██████████] 20
Low       [██████░░░░] 12

Issue Distribution by Category:
Security      [█████░░░░░] 8
Reliability   [██████████] 15
Safety        [███░░░░░░░] 5
Cost          [████░░░░░░] 6
Performance   [███░░░░░░░] 5
Quality       [█████░░░░░] 8

Maturity Score:
Reliability:    ████░ 2.0/4.0
Observability:  ██░░░ 1.0/4.0
Safety:         ███░░ 1.5/4.0
Testing:        ██░░░ 1.0/4.0
Overall:        ██░░░ 1.4/4.0 (Functional)
```

## 5. Finding Documentation Template

```markdown
## Issue: [Short Title]

**ID:** ISSUE-001
**Severity:** Critical | High | Medium | Low
**Category:** Reliability | Security | Safety | Cost | Performance | Quality
**Component:** [Which agent/module]

### Description
[What is the issue?]

### Evidence
[Code snippets, logs, metrics]

### Impact
[What are the consequences?]

### Root Cause
[Why does this exist?]

### Recommendation
[How to fix it?]

### Effort Estimate
[Hours/Days/Weeks]

### Priority
[P0/P1/P2/P3]
```

## Review Checklist

Complete checklist for comprehensive review.

### Architecture
- [ ] Agent roles clearly defined
- [ ] Communication patterns documented
- [ ] State management strategy clear
- [ ] Error handling strategy defined

### Code Quality
- [ ] Prompts externalized
- [ ] No hardcoded values
- [ ] Proper error handling
- [ ] Logging implemented
- [ ] Type hints present
- [ ] Code documented

### Safety & Security
- [ ] Input validation
- [ ] Output validation
- [ ] Action whitelisting
- [ ] Human-in-the-loop gates
- [ ] PII detection
- [ ] Audit logging
- [ ] No credentials in code

### Reliability
- [ ] Error handling
- [ ] Retry logic
- [ ] Circuit breakers
- [ ] Timeouts
- [ ] Graceful degradation

### Observability
- [ ] Structured logging
- [ ] Distributed tracing
- [ ] Metrics collection
- [ ] Dashboards
- [ ] Alerting

### Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] Test coverage > 70%
- [ ] CI/CD pipeline

### Performance & Cost
- [ ] Token usage monitored
- [ ] Cost tracking
- [ ] Caching implemented
- [ ] Resource limits

### Documentation
- [ ] Architecture documented
- [ ] API documented
- [ ] Runbooks exist
- [ ] README complete

## Anti-Pattern Grep Commands

Quick detection commands for common issues:

```bash
# Hardcoded credentials
grep -r "api_key\s*=\s*['\"]" .
grep -r "password\s*=\s*['\"]" .

# No error handling
grep -r "await.*generate" . | grep -v "try"

# Hardcoded prompts in code
grep -r "You are a" . --include="*.py"

# No input validation
grep -r "user_input" . | grep -v "validate"

# Missing timeouts
grep -r "while True" .
grep -r "await" . | grep -v "timeout"
```
