---
name: review-methodology
description: |
  Systematic review methodology for agentic codebases with issue detection, analysis, and reporting.
  Use when: "review agentic code", "audit agent system", "check agent quality", "agentic code review"
---

# Agentic Review Methodology

Systematic approach to reviewing agentic systems and codebases for issues, risks, and improvement opportunities.

## Four-Phase Review Process

### Phase 1: Detect (Discovery)

**Goal:** Identify all potential issues

**Activities:**
1. Code analysis (static analysis, anti-patterns)
2. Configuration review (prompts, secrets, limits)
3. Runtime analysis (logs, traces, metrics)
4. Documentation review

**Tools:**
- Static analyzers (pylint, mypy, eslint)
- Custom grep patterns for agentic anti-patterns
- Log aggregation tools

**Deliverable:** Raw issue inventory

### Phase 2: Analyze (Assessment)

**Goal:** Understand each issue's impact and root cause

**For Each Issue:**
1. Classify type (see `refs/issue-taxonomy.md`)
2. Determine severity (Critical/High/Medium/Low)
3. Assess impact (Reliability/Security/Cost/Performance)
4. Identify root cause
5. Estimate fix effort

**Analysis Framework:**
- What is the issue?
- Why is it a problem?
- What are the consequences?
- What is the root cause?
- How should it be fixed?

**Deliverable:** Analyzed issue list with severity and impact

### Phase 3: Score (Prioritization)

**Goal:** Prioritize issues for remediation

**Severity Levels:**

**Critical (P0):** Security vulnerabilities, data loss risks, system crashes, compliance violations. Fix immediately.

**High (P1):** Reliability issues, performance problems, cost inefficiencies, safety gaps. Fix within 1 week.

**Medium (P2):** Code quality issues, minor performance issues, missing observability. Fix within 1 month.

**Low (P3):** Style issues, optimization opportunities, nice-to-have features. Backlog.

**Prioritization Matrix:**
```
Impact vs Effort:
           Low Effort    High Effort
High       Quick Wins    Major Projects
Impact     (Do First)    (Plan)

Low        Easy Wins     Avoid
Impact     (Do Later)    (Skip)
```

**Deliverable:** Prioritized roadmap

### Phase 4: Report (Communication)

**Goal:** Communicate findings effectively to stakeholders

**Report Components:**
1. Executive Summary (1 page) - Overall assessment and top recommendations
2. Issue Inventory (Detailed) - All issues with severity and recommendations
3. Remediation Roadmap - Phased approach with quick wins
4. Metrics Dashboard - Issue counts and maturity score

**Deliverable:** Comprehensive review report

See `refs/deliverable-templates.md` for complete templates.

## Issue Severity Classification

### Determining Severity

1. Can it cause data loss? → Critical
2. Can it cause security breach? → Critical
3. Does it crash the system? → Critical/High
4. Does it violate compliance? → Critical
5. Does it affect reliability? → High/Medium
6. Does it waste money? → High/Medium
7. Is it a code quality issue? → Medium/Low

### Examples by Severity

**Critical:**
- No input validation (SQL injection risk)
- Credentials in code
- No error handling (system crashes)
- Production deletes without approval
- Missing audit logs for compliance

**High:**
- No circuit breakers (cascading failures)
- Missing observability (can't debug)
- No resource limits (runaway costs)
- Hardcoded prompts (can't iterate)
- No testing (high bug risk)

**Medium:**
- Inefficient token usage
- Missing documentation
- No caching (higher costs)
- Verbose logging
- Code duplication

**Low:**
- Style inconsistencies
- Missing type hints
- Suboptimal variable names
- Minor optimizations

See `refs/issue-taxonomy.md` for complete classification guide.

## Finding Documentation Template

For each issue, document:

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

## When to Use

Trigger phrases indicating you need this skill:
- "Review my agentic codebase"
- "Audit my agent system"
- "Is my system production-ready?"
- "Find issues in my agents"
- "What's wrong with my implementation?"

## Tips for Effective Reviews

1. **Be Systematic:** Follow all four phases
2. **Be Objective:** Focus on facts, not opinions
3. **Be Specific:** Provide code examples and evidence
4. **Be Constructive:** Suggest solutions, not just problems
5. **Be Prioritized:** Don't overwhelm with low-priority issues
6. **Be Clear:** Use simple language in reports

## References

- `refs/issue-taxonomy.md` - Complete issue category reference and anti-pattern detection
- `refs/deliverable-templates.md` - Detailed report templates and review checklist
