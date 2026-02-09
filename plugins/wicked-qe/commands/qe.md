---
description: Quality Engineering review - requirements, design, architecture, code, deployment
argument-hint: "<target> --focus requirements|ux|ui|arch|code|deploy|all"
---

# /wicked-qe:qe

Quality Engineering review across the full delivery lifecycle. QE's purpose is **enabling faster delivery** - catching issues early when they're cheap to fix.

## Philosophy

> **Testing is what allows you to deliver faster.**

QE is not a gate that slows you down. It's the foundation that enables:
- Confident refactoring
- Fearless deployments
- Rapid iteration
- Reduced debugging time

## Focus Areas

| Focus | What It Reviews | Why It Matters |
|-------|-----------------|----------------|
| `requirements` | Testability, clarity, acceptance criteria | Unclear requirements → rework |
| `ux` | User flows, error handling, edge cases | Poor UX → support burden |
| `ui` | Visual consistency, accessibility, responsiveness | UI bugs → user frustration |
| `arch` | Testability, deployability, observability | Bad arch → slow everything |
| `code` | Test coverage, code quality, maintainability | Untested code → fear of change |
| `deploy` | Rollback plan, feature flags, monitoring | Risky deploy → slow releases |
| `all` | Full spectrum review | Comprehensive quality check |

## Instructions

### 1. Determine Focus

If `--focus` not specified, infer from target:
- `.md` files with requirements → `requirements`
- Figma/design files mentioned → `ux` or `ui`
- System design docs → `arch`
- Source code → `code`
- CI/CD configs, deploy scripts → `deploy`

### 2. Requirements Review (`--focus requirements`)

```
Task(
  subagent_type="wicked-product:requirements-analyst",
  prompt="""Review these requirements for quality and testability.

## Requirements Content
{requirements content}

## Evaluation Checklist
1. Clarity - Can developers understand exactly what to build?
2. Testability - Can each requirement be verified with tests?
3. Completeness - Are edge cases and error states defined?
4. Acceptance criteria - Are they specific and measurable?
5. Dependencies - Are external dependencies identified?

## Return Format
Provide testability assessment with:
- Testability score (1-5)
- Issues table (requirement | issue | impact | recommendation)
- Missing scenarios list
- Recommendations for improving testability
"""
)
```

Output:
```markdown
## Requirements QE Review

### Testability Score: {1-5}

### Issues Found
| Requirement | Issue | Impact | Recommendation |
|-------------|-------|--------|----------------|
| {req} | Vague acceptance criteria | Can't verify | Add specific metrics |

### Missing Scenarios
- [ ] What happens when {edge case}?
- [ ] Error handling for {failure mode}?

### Recommendations
1. {action to improve testability}
```

### 3. UX Review (`--focus ux`)

```
Task(
  subagent_type="wicked-product:ux-designer",
  prompt="""Review user experience for quality issues.

## UX Artifacts
{user flows, wireframes, or implementation}

## Evaluation Checklist
1. User flow completeness - All paths covered (happy, error, edge)?
2. Error states - Clear, helpful error messages?
3. Edge cases - Empty states, loading, timeouts handled?
4. Accessibility - Keyboard navigation, screen readers supported?
5. Consistency - Follows established patterns and conventions?

## Return Format
Provide UX assessment with:
- Flow coverage table (flow | happy path | error states | edge cases)
- Accessibility gaps list
- Test scenarios needed for each flow
"""
)
```

Output:
```markdown
## UX QE Review

### Flow Coverage
| Flow | Happy Path | Error States | Edge Cases |
|------|------------|--------------|------------|
| {flow} | ✓ | Missing timeout | No empty state |

### Accessibility Gaps
- [ ] {a11y issue}

### Test Scenarios Needed
- User completes {flow} successfully
- User sees {error} when {condition}
- User with {disability} can {action}
```

### 4. UI Review (`--focus ui`)

```
Task(
  subagent_type="wicked-product:ui-reviewer",
  prompt="""Review UI implementation for quality.

## UI Artifacts
{component code or screenshots}

## Evaluation Checklist
1. Design system adherence - Using standard components?
2. Visual consistency - Spacing, colors, typography correct?
3. Responsive behavior - All breakpoints work correctly?
4. Loading states - Skeleton screens, spinners implemented?
5. Animation/transitions - Smooth, purposeful, not jarring?

## Return Format
Provide UI assessment with:
- Design system compliance table (component | status | issue)
- Visual bugs list with breakpoints
- Test scenarios needed (visual regression, responsive tests)
"""
)
```

Output:
```markdown
## UI QE Review

### Design System Compliance
| Component | Status | Issue |
|-----------|--------|-------|
| {component} | ⚠️ | Custom color not in palette |

### Visual Bugs
- [ ] {visual issue at breakpoint}

### Test Scenarios Needed
- Visual regression tests for {components}
- Responsive tests at {breakpoints}
```

### 5. Architecture Review (`--focus arch`)

```
Task(
  subagent_type="wicked-engineering:solution-architect",
  prompt="""Review architecture for testability and deployability.

## Architecture Artifacts
{architecture docs or code structure}

## Evaluation Checklist
1. Testability - Can components be tested in isolation?
2. Deployability - Can we deploy independently without cascading failures?
3. Observability - Logging, metrics, tracing in place?
4. Failure modes - Graceful degradation for dependencies?
5. Rollback - Can we safely roll back changes?

## Return Format
Provide architecture assessment with:
- Testability table (component | unit testable | integration testable | issue)
- Deployment concerns list
- Observability gaps list
- Risk areas table (area | risk level | mitigation)
"""
)
```

Output:
```markdown
## Architecture QE Review

### Testability Assessment
| Component | Unit Testable | Integration Testable | Issue |
|-----------|---------------|---------------------|-------|
| {component} | ✓ | ✗ | Hardcoded external dependency |

### Deployment Concerns
- [ ] No feature flag for {risky change}
- [ ] Missing health check endpoint

### Observability Gaps
- [ ] No metrics for {critical path}
- [ ] Missing trace context propagation

### Risk Areas
| Area | Risk | Mitigation |
|------|------|------------|
| {area} | High | {recommendation} |
```

### 6. Code Review (`--focus code`)

```
Task(
  subagent_type="wicked-qe:test-strategist",
  prompt="""Review code for test coverage and quality.

## Source Code
{source code}

## Evaluation Checklist
1. Test coverage - Are critical paths tested?
2. Test quality - Meaningful, specific assertions?
3. Testability - Is code structured for easy testing?
4. Edge cases - Boundary conditions covered?
5. Error handling - Are failures tested?

## Return Format
Provide code assessment with:
- Coverage gaps identified
- Test quality notes
- Testability issues
- Missing edge cases
- Error handling gaps
"""
)
```

(Also leverages existing scenarios/qe-plan/qe-review commands)

### 7. Deployment Review (`--focus deploy`)

```
Task(
  subagent_type="wicked-platform:release-engineer",
  prompt="""Review deployment readiness.

## Deployment Artifacts
{deploy configs, CI/CD, release plan}

## Evaluation Checklist
1. Rollback plan - Can we revert quickly if needed?
2. Feature flags - Are risky features behind flags?
3. Canary/progressive - Gradual rollout configured?
4. Monitoring - Alerts set for regressions and key metrics?
5. Runbook - Clear incident response documented?

## Return Format
Provide deployment assessment with:
- Release readiness checklist
- Risk assessment table (change | risk | mitigation)
- Monitoring requirements (alerts, dashboards)
"""
)
```

Output:
```markdown
## Deployment QE Review

### Release Readiness Checklist
- [ ] Feature flags configured for {features}
- [ ] Rollback tested and documented
- [ ] Canary deployment configured
- [ ] Alerts set for key metrics
- [ ] Runbook updated

### Risk Assessment
| Change | Risk | Mitigation |
|--------|------|------------|
| {change} | High | Behind feature flag, 1% canary |

### Monitoring Requirements
- Alert on: {metric} > {threshold}
- Dashboard: {what to watch}
```

### 8. Full Review (`--focus all`)

Run all focus areas in sequence, aggregate findings:

```markdown
## Full QE Review: {target}

### Summary
| Area | Score | Critical Issues |
|------|-------|-----------------|
| Requirements | 4/5 | 1 |
| UX | 3/5 | 2 |
| UI | 4/5 | 0 |
| Architecture | 3/5 | 1 |
| Code | 4/5 | 0 |
| Deployment | 2/5 | 3 |

### Release Recommendation
**HOLD** - Address 3 critical deployment issues before release

### Priority Actions
1. [Critical] Add rollback procedure
2. [Critical] Configure feature flag for {feature}
3. [High] Add acceptance criteria to {requirement}
```

## Example

```
User: /wicked-qe:qe src/auth/ --focus all

Claude: I'll perform a comprehensive QE review of the auth module.

[Reviews requirements docs]
[Reviews user flows]
[Reviews component implementation]
[Reviews architecture]
[Reviews test coverage]
[Reviews deploy config]

## Full QE Review: src/auth/

### Summary
| Area | Score | Critical Issues |
|------|-------|-----------------|
| Requirements | 4/5 | 0 |
| UX | 3/5 | 1 - No timeout handling |
| UI | 4/5 | 0 |
| Architecture | 4/5 | 0 |
| Code | 3/5 | 1 - Missing error path tests |
| Deployment | 4/5 | 0 |

### Release Recommendation
**PROCEED WITH CAUTION** - Address UX timeout handling

### Priority Actions
1. [High] Add timeout handling to login flow
2. [Medium] Add tests for auth error scenarios
```

## E2E Scenario Awareness

When **wicked-scenarios** is installed, QE reviews automatically discover available E2E scenarios and include coverage information:

- **Code review**: Reports which scenario categories cover the target code's risk areas
- **Architecture review**: Maps infrastructure scenarios to identified risks
- **Full review**: Reports scenario coverage across all risk areas and identifies gaps

Scenario **execution** happens in quality gates (via `code-analyzer` in execution gates), not during standalone QE reviews. Discovery uses `discover_scenarios.py` to find scenario metadata.

## Integration

QE reviews integrate with:
- **wicked-crew**: Quality gates in delivery phases
- **wicked-scenarios**: E2E scenario discovery and execution (optional)
- **wicked-kanban**: Track QE findings as tasks
- **wicked-product**: Requirements and UX expertise
- **wicked-platform**: Deployment and release expertise
