---
description: Systematic debugging session with root cause analysis
argument-hint: "<error message, symptom, or issue description>"
---

# /wicked-garden:engineering:debug

Start a systematic debugging session to diagnose issues, trace root causes, and develop fixes.

## Instructions

### 1. Gather Context

Collect information about the issue:
- Error message or symptom
- Steps to reproduce (if known)
- When it started occurring
- Any recent changes

If user provides a stack trace, parse it for:
- Error type and message
- File locations and line numbers
- Call chain

### 2. Dispatch Debugger Agent

```python
Task(
    subagent_type="wicked-garden:engineering:debugger",
    prompt="""Investigate this issue systematically.

## Problem
{description}

## Error Information
Error: {error message if any}
Stack trace: {if available}

## Investigation Steps
1. Trace the error origin
2. Identify contributing factors
3. Form hypotheses for root cause
4. Suggest diagnostic steps

## Return Format
Provide: Root cause, Evidence (file:line), Recommended fix, Prevention strategy.
"""
)
```

### 3. Execute Diagnostics

Based on debugger recommendations, run diagnostics:

- **Read relevant files** at error locations
- **Search for patterns** related to the error
- **Check logs** if available
- **Run targeted tests** to isolate behavior

### 4. Root Cause Analysis

Once root cause is identified, document:

```markdown
## Debug Analysis: {issue title}

### Symptom
{what was observed}

### Root Cause
{underlying issue explanation}

### Contributing Factors
- {factor 1}
- {factor 2}

### Evidence
- `{file}:{line}` - {what we found}
- {log entry or test result}

### Fix
{recommended solution}

### Prevention
{how to prevent recurrence}
```

### 5. Implement Fix

If user approves:
1. Make the code changes
2. Add/update tests to cover the case
3. Verify the fix resolves the issue

## Example

```
User: /wicked-garden:engineering:debug TypeError: Cannot read property 'id' of undefined in UserService

Claude: I'll investigate this TypeError systematically.

[Spawns debugger to analyze]
[Reads UserService.ts and related files]
[Traces data flow to find where undefined occurs]

## Debug Analysis: UserService TypeError

### Symptom
TypeError when accessing .id on undefined value in UserService

### Root Cause
The `getUser()` method doesn't handle the case where the database
query returns null for non-existent users.

### Evidence
- `src/services/UserService.ts:45` - `return user.id` without null check
- Query at line 42 can return null when user not found

### Fix
Add null check before accessing properties:
```typescript
const user = await this.db.users.findById(id);
if (!user) {
  throw new NotFoundError(`User ${id} not found`);
}
return user.id;
```

Shall I implement this fix?
```
