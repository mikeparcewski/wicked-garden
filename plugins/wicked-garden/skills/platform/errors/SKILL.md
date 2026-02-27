---
name: errors
description: |
  Error analysis and pattern detection from discovered error tracking sources.
  Aggregates errors across services, detects patterns, correlates with deployments,
  and assesses user impact. Use for error investigation and incident response.
triggers:
  - error analysis
  - error patterns
  - production errors
  - error investigation
  - why are we seeing errors
---

# Error Analysis Skill

Aggregate and analyze errors from discovered error tracking sources with pattern detection.

## When to Use

- Error spike investigation
- Pattern detection across services
- User impact assessment
- Correlation with deployments
- Error trend analysis
- User asks "errors", "exceptions", "why failing"

## Error Analysis Approach

### 1. Discover Error Tracking Sources

Use capability-based discovery:

```bash
# List available MCP servers
ListMcpResourcesTool

# Scan for error tracking capabilities by analyzing server descriptions:
# - error-tracking capability: Dedicated exception/error tracking
# - apm capability: APM tools that include error tracking
# - logging capability: Log platforms with error search/aggregation
```

### 2. Aggregate Error Data

For each discovered source:
- Current error rate vs baseline
- Top errors by frequency
- New vs recurring errors
- User sessions affected
- Error distribution by service/region

### 3. Detect Patterns

Look for:
- **Error spikes**: Sudden increase in error rate
- **New errors**: First seen in recent time window
- **Error clusters**: Related errors happening together
- **User impact**: Same users hitting multiple errors
- **Service correlation**: Errors across dependent services

### 4. Correlate with Changes

Check for correlation with:
- Recent deployments
- Code changes via wicked-search
- Infrastructure changes
- Traffic patterns
- External dependency changes

### 5. Provide Investigation Path

Based on patterns:
- Root cause hypothesis
- Investigation steps
- Recommended actions (rollback, hotfix, etc.)
- Integration with wicked-engineering for debugging

## Integration Discovery

| Capability | What to Look For | Provides |
|------------|------------------|----------|
| **error-tracking** | Exception tracking, crash reporting, error grouping | Stack traces, user context, grouping |
| **apm** | Performance monitoring with error tracking features | Errors with performance context |
| **logging** | Log platforms with error filtering and search | Error logs, patterns, search |

**Fallback**: Search code for error patterns via wicked-search (catch blocks, error handling, throw statements).

## Output Format

```markdown
## Error Analysis Report

**Analysis Time**: {timestamp}
**Time Range**: {period analyzed}
**Data Sources**: {list of integrations}

### Error Summary

**Current Error Rate**: {rate} ({change} from baseline)
**Total Errors**: {count} in last {period}
**Unique Errors**: {count} distinct error types
**Affected Users**: {count or percentage}

### Top Errors

| Error | Count | Users | First Seen | Trend |
|-------|-------|-------|------------|-------|
| {message} | {count} | {users} | {time} | {↑↓→} |

### Pattern Detection

**Pattern: {Pattern Name}**
- Type: [ERROR_SPIKE | NEW_ERROR | CASCADING | USER_CLUSTER]
- Description: {what the pattern indicates}
- Affected: {services, users, regions}
- Started: {timestamp}
- Correlation: {deployment, code change, etc.}

### Investigation Path

**Hypothesis**: {most likely root cause}

**Evidence**:
1. {supporting evidence point}
2. {supporting evidence point}

**Next Steps**:
1. {specific action to take}
2. {specific action to take}

**Engage**: wicked-garden:engineering-debugger for code-level analysis
```

## Common Error Patterns

Four main patterns to detect. See refs/patterns.md for detailed analysis guides.

### ERROR_SPIKE
Sudden increase in error rate (>2x baseline). Often deployment-related.

### NEW_ERROR
Error never seen before. Indicates new code path or edge case.

### CASCADING_FAILURE
One error causing downstream errors. Check service dependencies.

### USER_CLUSTER
Same users experiencing multiple errors. User-specific data issue.

## Integration with wicked-crew

When crew completes build phase:
1. Compare error rates pre/post deployment
2. Alert on new errors
3. Detect error spikes
4. Recommend rollback if critical

Emit events:
- `observe:error:spike:warning`
- `observe:error:pattern:warning`
- `observe:correlation:found:success`

## Integration with wicked-engineering

When errors detected, engage debugger with context:
- Error stack traces from discovered sources
- Log context from logging integrations
- Recent code changes from git
- Deployment timeline

## Severity Classification

See refs/severity.md for detailed classification.

**CRITICAL**: Error rate >10x baseline, critical path errors, data corruption
**HIGH**: Error rate >3x baseline, affecting >10% users, payment/security errors
**MEDIUM**: Error rate >1.5x baseline, affecting <10% users, non-critical features
**LOW**: Error rate <1.5x baseline, cosmetic issues, logging errors

## Notes

- Focus on error rate changes, not absolute numbers
- New errors often more critical than recurring ones
- Always correlate with deployments and code changes
- Distinguish between symptoms and root causes
- Use traces to understand error propagation
- Consider user impact, not just error count
