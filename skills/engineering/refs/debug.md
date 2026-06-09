# debug — garden-specific debug rubric

Wicked-garden preferred debug process. For the full systematic methodology, invoke
`superpowers:systematic-debugging` which covers hypothesis-driven debugging in depth.
This ref captures garden-specific heuristics and the standard output format.

## Garden-specific debug heuristics

### 1. Check the bus first (wicked-bus events)

Most garden failures surface as missing or malformed events. Before reading code:
```bash
wicked-bus query --limit 20 --format json   # recent events
wicked-bus query --event "domain:*:failed"  # failure events
```

### 2. Check wicked-loom / wicked-vault availability

Gate failures that say `"gate: unavailable"` are almost always a loom/vault resolution issue, not a logic bug:
- Is `WICKED_LOOM_BIN` set correctly?
- Is `wicked-vault` available via `npx`?
- Is `WICKED_LOOM_CUTOVER=off` accidentally set?

### 3. Hook scripts: always run with `python3 -c "..."` test first

Hook issues are commonly cross-platform JSON output failures. Test the hook script standalone:
```bash
python3 scripts/hooks/script.py '{"event": "test"}' 2>&1
```

### 4. Scope creep as a bug category

When reviewing a diff that triggers a bug report, check if the diff contains changes *outside* the stated scope — scope creep often introduces subtle regressions.

## Six-step debugging process

1. **Understand** — expected vs actual behavior, reproduction steps, when it started
2. **Gather evidence** — logs, stack traces, recent changes, config drift
3. **Form hypothesis** — most likely cause + what would disprove it
4. **Test hypothesis** — targeted test, not random changes
5. **Implement fix** — minimal fix, verify resolution, add regression test
6. **Document** — root cause, fix rationale, prevention measure

## Issue categories

| Category | Examples |
|----------|---------|
| Logic errors | Wrong conditions, off-by-one, missing edge cases |
| State errors | Race conditions, stale closures, shared mutable state |
| Integration errors | API contract mismatch, auth failures, timeout, format mismatch |
| Performance | N+1 queries, missing indexes, memory leaks, unbounded loops |
| Environment | Config differences, missing env vars, version mismatches, permissions |
| Garden-specific | Loom unavailable, vault unresolvable, bus consumer not registered, hook cross-platform failure |

## Standard output format

```markdown
## Debug Analysis: {issue title}

### Symptom
{what was observed — exact error message or behavior}

### Root Cause
{underlying issue — not just the symptom}

**Confidence**: HIGH / MEDIUM / LOW

### Why This Happened
{explain the causal chain from trigger to symptom}

### Evidence
- `{file}:{line}` — {what was found}
- {log entry or test result}

### Reproduction Steps
1. {step}
2. {step}
3. Observe: {expected} vs {actual}

### Recommended Fix

```diff
- {bad code}
+ {fixed code}
```

**Rationale**: {why this fixes the root cause, not just the symptom}

### Verification
1. {how to verify the fix works}
2. {what to monitor after deploying}

### Prevention
- {test to add}
- {monitoring/alerting to add}
- {code pattern to avoid}

### Alternative Explanations
{only if confidence is not HIGH — other possible causes}
```

## Debugging techniques

### Stack trace analysis — work backwards

```
Error: Cannot read property 'id' of undefined
  at getUserName (user.js:42)   ← What is undefined here?
  at renderProfile (profile.js:15)  ← What data was passed?
  at App.render (App.js:88)   ← Where did this come from?
```

### Binary search with git bisect

```bash
git bisect start
git bisect bad HEAD
git bisect good v1.2.0
# test each commit git bisect suggests
```

### Async timing issues — common pattern

```javascript
// Bug: result is undefined — await missing
let result;
fetchData().then(data => result = data);
console.log(result);  // undefined!

// Fix
const result = await fetchData();
```

### Null/undefined — prefer optional chaining

```javascript
// Bug
user.profile.name  // profile might be null

// Fix
user?.profile?.name ?? 'Unknown'
```
