# Debugging Process & Checklists

## Systematic Debugging Process

### 1. Understand the Problem
- What is expected vs actual behavior?
- When did it start? Can it be reproduced?
- What changed recently?
- Is it environment-specific?
- Does it happen consistently?

### 2. Gather Evidence
- Read logs and stack traces
- Review recent changes (git log)
- Identify patterns
- Collect error messages
- Check monitoring/metrics
- Review environment variables

### 3. Form Hypothesis
- What is the most likely cause?
- What evidence supports this?
- What would disprove this?
- Are there alternative explanations?

### 4. Test Hypothesis
- Design targeted test
- Observe results
- Document findings
- Refine hypothesis if needed

### 5. Implement Fix
- Develop minimal fix
- Verify resolution
- Add regression tests
- Test edge cases

### 6. Document
- Root cause and fix
- Add monitoring/alerting
- Update runbooks
- Share learnings

## Issue Categories

### Logic Errors
- Incorrect conditions (>, >=, ==, ===)
- Off-by-one errors
- Wrong operators
- Missing edge cases

### State Errors
- Race conditions
- Stale closures
- Shared mutable state
- Incorrect state initialization

### Integration Errors
- API mismatch (contract changed)
- Auth issues (expired tokens)
- Timeouts (slow external service)
- Network errors

### Performance Issues
- N+1 queries
- Missing indexes
- Memory leaks
- Inefficient algorithms
- Unoptimized database queries

### Environment Issues
- Config differences (dev vs prod)
- Missing environment variables
- Permission problems
- Dependency version mismatches

## Output Template

```markdown
## Debug Analysis: {Issue}

### Problem Summary
{Clear description}

### Evidence
- {Key findings}

### Root Cause
{Most likely cause}

**Confidence**: HIGH / MEDIUM / LOW

### Why This Happened
{Underlying cause}

### Reproduction
1. {Step 1}
2. {Observe: expected vs actual}

### Recommended Fix
```diff
{Code change}
```

**Rationale**: {Why this fixes it}

### Verification
- {How to verify}
- {What to monitor}

### Prevention
- {How to avoid}
- {Tests to add}
```

## Tools by Environment

### Browser DevTools
- Console: Logging, errors, warnings
- Network: Request/response inspection
- Sources: Breakpoint debugging
- Performance: Profiling, timeline
- Memory: Heap snapshots, leak detection

### Node.js
- `node --inspect`: Chrome DevTools debugging
- Error stack traces: Call hierarchy
- `console.trace()`: Full stack trace
- Profiling: `node --prof`

### Database
- EXPLAIN plans: Query execution analysis
- Slow query logs: Performance issues
- Connection monitoring: Pool usage
- Index analysis: Missing indexes

## Severity Levels

### CRITICAL
- Production down
- Data loss
- Security breach
- Payment processing broken
- Users completely blocked

**Action**: Immediate fix, all hands

### HIGH
- Major functionality broken
- Performance severely degraded
- Many users affected
- Revenue impacting

**Action**: Fix within hours, escalate

### MEDIUM
- Feature broken
- Workaround available
- Some users affected
- Degraded experience

**Action**: Fix within days, prioritize

### LOW
- Minor issue
- Edge case
- Cosmetic problem
- Few users affected

**Action**: Backlog, fix when convenient

## Debugging Checklist

### Initial Investigation
- [ ] Can you reproduce the issue?
- [ ] What are the exact error messages?
- [ ] When did it start happening?
- [ ] What changed recently?
- [ ] Is it environment-specific?

### Evidence Gathering
- [ ] Checked application logs
- [ ] Reviewed stack traces
- [ ] Inspected network requests
- [ ] Checked database queries
- [ ] Reviewed recent commits

### Testing
- [ ] Isolated the problem area
- [ ] Tested hypothesis
- [ ] Verified fix resolves issue
- [ ] Tested edge cases
- [ ] Checked for side effects

### Prevention
- [ ] Added regression test
- [ ] Updated documentation
- [ ] Added monitoring/alerting
- [ ] Shared learnings with team
