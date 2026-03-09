# Issue Taxonomy: Reliability, Security & Safety

Complete reference of issue categories for agentic system reviews covering reliability, security, safety, and cost issues.

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
