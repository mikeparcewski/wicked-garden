---
description: Error analysis and pattern detection
argument-hint: "[service name, error type, or 'recent' for latest errors]"
---

# /wicked-platform:errors

Analyze production errors, detect patterns, and correlate with changes.

## Instructions

### 1. Discover Error Sources

Use capability-based discovery:
```
ListMcpResourcesTool

Look for error-tracking capability:
- Sentry, Rollbar, Bugsnag
- Datadog Errors, New Relic Errors
- CloudWatch, Application Insights
```

### 2. Determine Analysis Scope

Based on argument:
- **Service name**: Errors for specific service
- **Error type**: Specific error class/message
- **"recent"**: Latest errors across all services
- **No arg**: Overview of error trends

### 3. Dispatch to Incident Responder for Analysis

```python
Task(
    subagent_type="wicked-platform:incident-responder",
    prompt="""Analyze production errors and identify patterns.

Scope: {service name, error type, or 'all recent'}
Error Sources: {discovered integrations}

Analysis Checklist:
1. Aggregate error data - Counts, rates, unique types, affected users
2. Extract stack traces - File locations, function calls
3. Detect patterns:
   - Spikes (sudden increases in error rate)
   - New errors (first seen recently)
   - Regressions (fixed errors returning)
   - Clusters (related errors)
4. Correlate with changes - Recent deployments, code changes
5. Impact assessment - User and business impact

Return Format:
- Summary metrics (total errors, unique types, users affected, trends)
- Top errors by count with details
- Pattern analysis (spikes, new, regressions)
- Correlation with deployments or changes
- Prioritized recommendations
"""
)
```

### 4. Correlate with Changes

```bash
# Recent deployments
git log --oneline --since="24 hours ago"

# Changes to error location
git log --oneline -5 -- {file from stack trace}
```

### 6. Deliver Error Report

```markdown
## Error Analysis

**Scope**: {what was analyzed}
**Time Range**: {period}

### Summary
| Metric | Value | Trend |
|--------|-------|-------|
| Total Errors | {count} | {trend} |
| Unique Types | {count} | {trend} |
| Users Affected | {count} | {trend} |

### Top Errors
| Error | Count | Users | First Seen |
|-------|-------|-------|------------|
| {type} | {count} | {users} | {time} |

### Patterns Detected
- {pattern with evidence}

### New Errors (Last 24h)
1. {new error with details}

### Correlation
- {deployment or change correlation}

### Recommendations
1. {priority fix}
```

## Example

```
User: /wicked-platform:errors recent

Claude: I'll analyze recent production errors.

[Discovers Sentry integration]
[Queries last 24 hours of errors]

## Error Analysis: Last 24 Hours

**Time Range**: 2024-01-14 14:00 - 2024-01-15 14:00 UTC

### Summary
| Metric | Value | Trend |
|--------|-------|-------|
| Total Errors | 2,847 | +45% |
| Unique Types | 23 | +3 new |
| Users Affected | 892 | +38% |

### Top Errors
| Error | Count | Users | Service |
|-------|-------|-------|---------|
| TypeError: Cannot read 'id' of null | 1,234 | 456 | user-api |
| ConnectionTimeout | 892 | 234 | payment |
| ValidationError: Invalid email | 412 | 189 | signup |

### New Error (First seen 6h ago)

**TypeError: Cannot read 'id' of null**
- **First seen**: 2024-01-15 08:23 UTC
- **Count**: 1,234 (and growing)
- **Users affected**: 456

**Stack Trace**:
```
TypeError: Cannot read 'id' of null
    at UserService.getProfile (src/services/user.ts:89)
    at ProfileController.show (src/controllers/profile.ts:23)
```

### Correlation

**Deployment**: user-api v3.2.1 at 08:20 UTC (3 min before first error)

**Change**: PR #567 - "Optimize user profile loading"
- Modified: `src/services/user.ts`
- Removed null check on line 88

### Recommendation

1. **Immediate**: Rollback user-api to v3.2.0
2. **Fix**: Restore null check in UserService.getProfile
3. **Prevention**: Add test for null user case
```
