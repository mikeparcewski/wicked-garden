# Issue Taxonomy: Performance, Quality, Observability & Testing

Issue categories for agentic system reviews covering performance, code quality, observability, testing, and severity guidelines.

## Category 5: Performance Issues

Issues affecting system speed and throughput.

### P-001: Sequential Bottlenecks
**Description:** Operations run serially when could be parallel
**Severity:** Medium
**Impact:** Slow response times
**Example:**
```python
# Bad
result1 = await task1()
result2 = await task2()  # Could run in parallel

# Good
result1, result2 = await asyncio.gather(task1(), task2())
```

### P-002: No Connection Pooling
**Description:** Creating new connections for each request
**Severity:** Medium
**Impact:** High latency, resource waste
**Fix:** Use connection pools

### P-003: Blocking I/O
**Description:** Synchronous I/O blocking event loop
**Severity:** Medium
**Impact:** Poor concurrency, slow throughput
**Fix:** Use async I/O

### P-004: No Load Balancing
**Description:** All traffic to single instance
**Severity:** Medium
**Impact:** Single instance saturated
**Fix:** Distribute load across instances

### P-005: Memory Leaks
**Description:** Memory usage grows over time
**Severity:** High
**Impact:** System becomes slow, eventually crashes
**Fix:** Identify and fix leaks, add memory monitoring

### P-006: N+1 Queries
**Description:** Making N database queries when 1 would suffice
**Severity:** Medium
**Impact:** High database load, slow responses
**Fix:** Use joins, batch queries

## Category 6: Code Quality Issues

Issues affecting maintainability and readability.

### Q-001: Hardcoded Prompts
**Description:** Prompts embedded in code
**Severity:** Medium
**Impact:** Hard to iterate, no version control
**Example:**
```python
# Bad
prompt = "You are a helpful assistant that..."

# Good
prompt = load_prompt_template("assistant_v1.txt")
```

### Q-002: No Type Hints
**Description:** Python code without type annotations
**Severity:** Low
**Impact:** Harder to maintain, refactor
**Fix:** Add type hints, use mypy

### Q-003: Code Duplication
**Description:** Same logic repeated in multiple places
**Severity:** Low
**Impact:** Maintenance burden, inconsistency
**Fix:** Extract to shared function

### Q-004: Missing Documentation
**Description:** Code, APIs not documented
**Severity:** Low
**Impact:** Hard for others to understand/use
**Fix:** Add docstrings, API docs, architecture docs

### Q-005: Inconsistent Style
**Description:** Code doesn't follow style guide
**Severity:** Low
**Impact:** Harder to read
**Fix:** Use linter (pylint, black, eslint)

### Q-006: Poor Naming
**Description:** Variables, functions poorly named
**Severity:** Low
**Impact:** Confusing code
**Fix:** Use descriptive names

### Q-007: Large Functions
**Description:** Functions doing too much (>50 lines)
**Severity:** Low
**Impact:** Hard to test, understand
**Fix:** Break into smaller functions

## Category 7: Observability Issues

Issues affecting ability to monitor and debug.

### O-001: No Logging
**Description:** No logs emitted
**Severity:** High
**Impact:** Can't debug issues
**Fix:** Add structured logging

### O-002: Unstructured Logs
**Description:** Logs are plain text, not structured (JSON)
**Severity:** Medium
**Impact:** Hard to parse, search, analyze
**Example:**
```python
# Bad
print(f"Agent processed {task}")

# Good
logger.info("Agent processed task", extra={
    "agent_id": agent.id,
    "task_id": task.id,
    "duration": duration
})
```

### O-003: No Distributed Tracing
**Description:** Can't trace requests across agents
**Severity:** Medium
**Impact:** Hard to debug multi-agent issues
**Fix:** Add tracing (OpenTelemetry)

### O-004: No Metrics
**Description:** No quantitative measurements collected
**Severity:** Medium
**Impact:** Can't measure performance, costs
**Fix:** Collect metrics (requests, latency, errors, costs)

### O-005: No Dashboards
**Description:** Metrics not visualized
**Severity:** Low
**Impact:** Hard to spot trends, issues
**Fix:** Create dashboards (Grafana, etc.)

### O-006: No Alerting
**Description:** No alerts on critical conditions
**Severity:** High
**Impact:** Issues go unnoticed
**Fix:** Set up alerts (PagerDuty, etc.)

### O-007: No Request IDs
**Description:** Can't correlate logs for single request
**Severity:** Medium
**Impact:** Hard to trace request flow
**Fix:** Add correlation IDs to all logs

## Category 8: Testing Issues

Issues affecting test coverage and quality.

### T-001: No Tests
**Description:** No automated tests
**Severity:** High
**Impact:** High bug risk, fear of changes
**Fix:** Add unit, integration tests

### T-002: Low Coverage
**Description:** Test coverage <70%
**Severity:** Medium
**Impact:** Untested code paths
**Fix:** Increase test coverage

### T-003: No Integration Tests
**Description:** Only unit tests, no end-to-end tests
**Severity:** Medium
**Impact:** Integration bugs not caught
**Fix:** Add integration tests

### T-004: Flaky Tests
**Description:** Tests pass/fail randomly
**Severity:** Medium
**Impact:** CI/CD unreliable
**Fix:** Fix race conditions, timing issues

### T-005: No CI/CD
**Description:** Tests not run automatically
**Severity:** High
**Impact:** Broken code can be merged
**Fix:** Set up CI pipeline (GitHub Actions, etc.)

### T-006: No Load Testing
**Description:** System not tested under load
**Severity:** Medium
**Impact:** Don't know scalability limits
**Fix:** Run load tests

### T-007: No Mocking
**Description:** Tests call real LLM APIs
**Severity:** Medium
**Impact:** Slow, expensive tests
**Fix:** Mock LLM responses in tests

## Severity Guidelines

### Critical (P0)
- Security vulnerabilities
- Data loss risks
- Compliance violations
- System crashes
- **Fix:** Immediately (within 24 hours)

### High (P1)
- Reliability issues
- Safety gaps
- Performance problems
- Cost inefficiencies
- **Fix:** Within 1 week

### Medium (P2)
- Code quality issues
- Missing observability
- Incomplete testing
- Documentation gaps
- **Fix:** Within 1 month

### Low (P3)
- Style issues
- Minor optimizations
- Nice-to-haves
- **Fix:** Backlog

## Issue Template

```markdown
## [CATEGORY]-[NUMBER]: [Issue Title]

**Severity:** Critical | High | Medium | Low
**Category:** Reliability | Security | Safety | Cost | Performance | Quality | Observability | Testing
**Component:** [Affected component]
**Instances:** [Number of occurrences]

### Description
[What is the issue?]

### Location
[File:line references]

### Impact
[What are the consequences?]

### Root Cause
[Why does this exist?]

### Recommendation
[How to fix it?]

### Example
```code
[Code example]
```

### Effort
[Hours/Days/Weeks]

### Priority
[P0/P1/P2/P3]
```
