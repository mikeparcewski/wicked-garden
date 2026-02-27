# Issue Taxonomy

Complete reference of issue categories for agentic system reviews.

## Category 1: Reliability Issues

Issues affecting system stability and uptime.

### R-001: Missing Error Handling
**Description:** No try/catch around LLM calls or external operations
**Severity:** High
**Impact:** System crashes on errors
**Example:**
```python
# Bad
result = await llm.generate(prompt)  # Crashes if API fails

# Good
try:
    result = await llm.generate(prompt)
except Exception as e:
    logger.error(f"LLM call failed: {e}")
    return fallback_response
```

### R-002: No Retry Logic
**Description:** Single attempt at operations that may fail transiently
**Severity:** Medium
**Impact:** Failures that could be resolved with retry
**Example:**
```python
# Bad
response = await api.call()

# Good
@retry(max_attempts=3, backoff=exponential)
async def api_call():
    return await api.call()
```

### R-003: Missing Timeouts
**Description:** Operations can run indefinitely
**Severity:** High
**Impact:** Resource exhaustion, hung processes
**Example:**
```python
# Bad
while not done:
    result = await agent.process()

# Good
async with asyncio.timeout(300):
    while not done:
        result = await agent.process()
```

### R-004: No Circuit Breakers
**Description:** No protection against cascading failures
**Severity:** High
**Impact:** Cascading failures, system-wide outages
**Example:**
```python
# Good
circuit_breaker = CircuitBreaker(failure_threshold=5)
result = await circuit_breaker.call(external_service.request)
```

### R-005: Single Point of Failure
**Description:** Critical component with no redundancy
**Severity:** High
**Impact:** Complete system failure if component fails
**Fix:** Add redundancy, failover mechanisms

### R-006: No Health Checks
**Description:** No way to verify system is healthy
**Severity:** Medium
**Impact:** Can't detect or recover from issues
**Fix:** Implement /health endpoint, monitoring

### R-007: No Graceful Degradation
**Description:** System fails completely rather than providing reduced functionality
**Severity:** Medium
**Impact:** Poor user experience during issues
**Fix:** Implement fallback behaviors

## Category 2: Security Issues

Issues creating security vulnerabilities.

### S-001: No Input Validation
**Description:** User inputs not validated before processing
**Severity:** Critical
**Impact:** SQL injection, command injection, prompt injection
**Example:**
```python
# Bad
query = f"SELECT * FROM users WHERE name = '{user_input}'"

# Good
query = "SELECT * FROM users WHERE name = ?"
cursor.execute(query, (user_input,))
```

### S-002: Credentials in Code
**Description:** API keys, passwords hardcoded in source
**Severity:** Critical
**Impact:** Credential exposure, unauthorized access
**Example:**
```python
# Bad
api_key = "YOUR_API_KEY_HERE"

# Good
api_key = os.getenv("API_KEY")
```

### S-003: Sensitive Data in Logs
**Description:** PII, credentials, secrets logged in plain text
**Severity:** Critical
**Impact:** Data breach, compliance violation
**Fix:** Redact sensitive data, encrypt logs

### S-004: No Authentication
**Description:** Endpoints accessible without authentication
**Severity:** Critical
**Impact:** Unauthorized access
**Fix:** Implement authentication (OAuth, API keys, etc.)

### S-005: No Authorization
**Description:** No check if user authorized for action
**Severity:** Critical
**Impact:** Privilege escalation
**Fix:** Implement RBAC, permission checks

### S-006: Insecure Dependencies
**Description:** Using dependencies with known vulnerabilities
**Severity:** High
**Impact:** Exploitable vulnerabilities
**Fix:** Update dependencies, use vulnerability scanning

### S-007: No Rate Limiting
**Description:** No limits on request frequency
**Severity:** Medium
**Impact:** DOS attacks, abuse
**Fix:** Implement rate limiting per user/IP

## Category 3: Safety Issues

Issues affecting user safety and system behavior.

### SF-001: No Output Validation
**Description:** Agent outputs not validated before use
**Severity:** High
**Impact:** Harmful outputs, system errors
**Example:**
```python
# Good
output = await agent.generate(task)
if not validate_output(output):
    raise UnsafeOutputError()
```

### SF-002: Missing Approval Gates
**Description:** High-stakes actions execute without human approval
**Severity:** Critical
**Impact:** Unintended consequences, data loss
**Fix:** Add human-in-the-loop for risky operations

### SF-003: No Action Whitelisting
**Description:** Agents can execute any action
**Severity:** High
**Impact:** Dangerous operations possible
**Fix:** Whitelist allowed actions, validate against list

### SF-004: Missing Audit Logs
**Description:** No record of agent decisions and actions
**Severity:** High (Critical for regulated industries)
**Impact:** No accountability, compliance violations
**Fix:** Log all decisions and actions with timestamps

### SF-005: No PII Protection
**Description:** PII not detected, redacted, or encrypted
**Severity:** Critical
**Impact:** Privacy violations, compliance issues
**Fix:** Implement PII detection and redaction

### SF-006: No Rollback Capability
**Description:** Can't undo destructive actions
**Severity:** High
**Impact:** Permanent damage from errors
**Fix:** Implement reversible actions, backups

### SF-007: Missing Kill Switch
**Description:** No emergency stop mechanism
**Severity:** Medium
**Impact:** Can't stop runaway processes
**Fix:** Implement kill switch, circuit breaker

## Category 4: Cost Issues

Issues causing unnecessary costs.

### C-001: No Token Tracking
**Description:** Token usage not measured or logged
**Severity:** Medium
**Impact:** Unknown costs, can't optimize
**Fix:** Track tokens per request, agent, user

### C-002: No Cost Budgets
**Description:** No limits on spending
**Severity:** Medium
**Impact:** Runaway costs
**Fix:** Implement per-user, per-session budgets

### C-003: Missing Caching
**Description:** Repeated identical requests to LLM
**Severity:** Medium
**Impact:** Wasted API calls and cost
**Example:**
```python
# Good
@cache(ttl=3600)
async def cached_generate(prompt):
    return await llm.generate(prompt)
```

### C-004: Inefficient Prompts
**Description:** Overly verbose prompts using excess tokens
**Severity:** Low
**Impact:** Higher per-request costs
**Fix:** Optimize prompts, use structured formats

### C-005: Wrong Model Selection
**Description:** Using expensive model when cheaper would suffice
**Severity:** Medium
**Impact:** Unnecessary costs
**Fix:** Use cheapest model meeting quality threshold

### C-006: No Batch Processing
**Description:** Processing items individually when could batch
**Severity:** Low
**Impact:** Higher total costs
**Fix:** Batch similar requests

### C-007: Context Bloat
**Description:** Passing excessive context to agents
**Severity:** Medium
**Impact:** Wasted tokens on irrelevant context
**Fix:** Filter context to relevant information

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
