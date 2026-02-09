# Error Pattern Analysis Guide

Detailed investigation guides for common error patterns.

## ERROR_SPIKE

Sudden increase in error rate (>2x baseline in short time).

### Typical Causes

1. **Recent deployment**
   - New bugs introduced
   - Breaking changes
   - Configuration errors
   - Migration issues

2. **Traffic spike**
   - Unexpected load
   - Resource exhaustion
   - Rate limiting triggered
   - Cache invalidation

3. **Dependency failure**
   - External API down
   - Database issues
   - Third-party service degradation
   - Network problems

4. **Configuration change**
   - Environment variable changes
   - Feature flag toggles
   - Infrastructure updates
   - Security policy changes

### Investigation Steps

1. **Check deployment timeline**
   - When was last deployment?
   - What changed in that deployment?
   - Were there any rollbacks recently?

2. **Compare error messages pre/post spike**
   - Are these new error messages?
   - Are existing errors occurring more frequently?
   - What services are affected?

3. **Check dependency health**
   - Query APM for external service health
   - Check database performance metrics
   - Review third-party service status pages

4. **Review recent configuration changes**
   - Environment variable changes
   - Feature flag modifications
   - Infrastructure or scaling changes

### Recommended Actions

If error rate >5x baseline:
- Consider immediate rollback
- Engage incident response
- Notify stakeholders

If error rate 2-5x baseline:
- Investigate root cause
- Prepare rollback plan
- Monitor for escalation

## NEW_ERROR

Error message never seen before (or not in last 30 days).

### Typical Causes

1. **New code path**
   - Recently deployed features
   - New integrations
   - Refactored code
   - New dependencies

2. **New edge case**
   - Unexpected input data
   - Rare race conditions
   - Boundary conditions
   - Data type mismatches

3. **Data format change**
   - API contract changes
   - Database schema migration
   - External data source changes
   - Serialization issues

4. **Integration change**
   - Third-party API updates
   - New external dependencies
   - Authentication changes
   - Network routing changes

### Investigation Steps

1. **Identify when first seen**
   - Exact timestamp of first occurrence
   - How many times since first seen?
   - Is frequency increasing?

2. **Find related code changes**
   - Git log around first occurrence time
   - Deployment records
   - PR/commit analysis via wicked-search

3. **Review stack trace for new code**
   - Files/functions in the trace
   - Recently modified code
   - New dependencies or imports

4. **Check for new integrations or data sources**
   - External API calls
   - Database queries
   - File system operations
   - Network requests

### Recommended Actions

For critical path errors:
- Immediate investigation
- Disable feature if possible
- Prepare hotfix or rollback

For non-critical errors:
- Log detailed context
- Create bug ticket
- Schedule fix in next sprint

## CASCADING_FAILURE

One error causing downstream errors in dependent services.

### Typical Causes

1. **Service timeout propagation**
   - Upstream service slow/failing
   - Timeout values too long
   - No circuit breaker
   - Synchronous calls blocking

2. **Missing circuit breaker**
   - Failures propagate to callers
   - Resource exhaustion
   - Thread pool saturation
   - Connection pool exhaustion

3. **Retry storms**
   - Aggressive retry logic
   - No exponential backoff
   - No jitter in retries
   - Amplifies load on failing service

4. **Resource exhaustion**
   - Memory leaks
   - Connection leaks
   - Thread exhaustion
   - File descriptor limits

### Investigation Steps

1. **Use traces to map service dependencies**
   - Identify call chain
   - Find root failing service
   - Analyze error propagation path

2. **Identify root failing service**
   - Which service failed first?
   - What triggered the failure?
   - Check service health metrics

3. **Check timeout configurations**
   - Are timeouts set appropriately?
   - Are they too long (blocking)?
   - Are they too short (false failures)?

4. **Look for retry logic amplification**
   - How many retries per request?
   - Is there exponential backoff?
   - Is jitter applied?
   - What's the total load multiplier?

### Recommended Actions

Immediate:
- Implement circuit breaker if missing
- Reduce retry aggressiveness
- Add timeout if missing
- Scale failing service if possible

Long-term:
- Review resilience patterns
- Implement bulkhead isolation
- Add health check endpoints
- Monitor circuit breaker state

## USER_CLUSTER

Same users experiencing multiple different errors.

### Typical Causes

1. **User-specific data issue**
   - Corrupted user data
   - Invalid data format
   - Missing required fields
   - Data migration errors

2. **Session corruption**
   - Serialization issues
   - Session storage problems
   - Token expiration
   - Cache inconsistency

3. **Authentication problem**
   - Invalid credentials
   - Expired tokens
   - Permission issues
   - OAuth flow errors

4. **Client version issue**
   - Old mobile app version
   - Browser compatibility
   - API version mismatch
   - Feature flag inconsistency

### Investigation Steps

1. **Analyze user characteristics**
   - Geographic region
   - Client version/platform
   - Account age/type
   - Feature flags enabled

2. **Check user data integrity**
   - Query user record
   - Validate data format
   - Check for missing fields
   - Review recent data changes

3. **Review session management**
   - Session creation/validation
   - Token handling
   - Cache consistency
   - Storage backend health

4. **Check for client-side issues**
   - Client version distribution
   - Browser/OS compatibility
   - Network conditions
   - Local storage issues

### Recommended Actions

If affecting many users:
- Identify common characteristics
- Disable feature for affected segment
- Fix data issue or rollback

If affecting few users:
- Support ticket resolution
- Manual data correction
- Client update recommendation
