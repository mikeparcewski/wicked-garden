---
description: Audit evidence collection and compliance verification
argument-hint: "<framework: soc2|hipaa|gdpr|pci> [control ID]"
---

# /wicked-platform:audit

Collect audit evidence, verify controls, and generate compliance artifacts.

## Instructions

### 1. Determine Audit Scope

Parse the framework and optional control:
- **Framework**: SOC2, HIPAA, GDPR, PCI
- **Control ID**: Specific control to verify (e.g., SOC2-CC6.1)

### 2. Dispatch to Auditor

```python
Task(
    subagent_type="wicked-platform:auditor",
    prompt="""Collect audit evidence for compliance verification.

Framework: {framework}
Control: {specific control or 'all'}

Evidence Collection:
1. Control implementation - Code and configuration proving control exists
2. Configuration artifacts - Settings, policies, rules
3. Access control documentation - Authentication and authorization setup
4. Audit log samples - Examples of control in action
5. Policy documentation - Written policies and procedures

Return Format:
- Control evidence with file:line references
- Code snippets proving implementation
- Configuration samples
- Verification checklist (implemented, configured, enforced, documented)
- Pass/Partial/Fail status per control
- Gaps identified
- Auditor notes for compliance team
"""
)
```

### 3. Collect Evidence

For each control, gather:
- Code implementing the control
- Configuration files
- Log samples showing control in action
- Documentation

### 4. Verify Controls

Check implementation against requirements:
- [ ] Control exists
- [ ] Control is properly configured
- [ ] Control is actively enforced
- [ ] Evidence is available

### 5. Deliver Audit Package

```markdown
## Audit Evidence Package

**Framework**: {framework}
**Scope**: {controls covered}
**Date**: {timestamp}

### Control Evidence

#### {Control ID}: {Control Name}

**Requirement**: {what the control requires}

**Implementation**:
- Location: {file:line}
- Description: {how it's implemented}

**Evidence**:
```
{code snippet or configuration}
```

**Verification**:
- [x] Control implemented
- [x] Configuration correct
- [x] Logs available
- [ ] Documentation complete

**Status**: PASS / PARTIAL / FAIL

### Evidence Artifacts
| Artifact | Location | Description |
|----------|----------|-------------|
| {name} | {path} | {description} |

### Gaps Identified
1. {gap requiring remediation}

### Auditor Notes
{observations for audit team}
```

## Example

```
User: /wicked-platform:audit soc2 CC6.1

Claude: I'll collect evidence for SOC2 CC6.1 (Logical Access Controls).

[Spawns auditor agent]
[Searches for access control implementation]
[Collects configuration evidence]

## Audit Evidence: SOC2 CC6.1

**Control**: CC6.1 - Logical Access Security
**Requirement**: Implement logical access controls to protect system resources

### Evidence Collected

#### Authentication Implementation

**Location**: `src/middleware/auth.ts`
**Description**: JWT-based authentication middleware

```typescript
export const authenticate = async (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    req.user = await User.findById(payload.sub);
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid token' });
  }
};
```

**Verification**:
- [x] Authentication required for protected routes
- [x] Tokens validated with cryptographic verification
- [x] Failed attempts rejected with 401

#### Authorization Implementation

**Location**: `src/middleware/authorize.ts`
**Description**: Role-based access control

```typescript
export const authorize = (...roles: Role[]) => {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Forbidden' });
    }
    next();
  };
};
```

**Verification**:
- [x] Role-based access control implemented
- [x] Unauthorized access rejected with 403
- [x] Roles defined and enforced

### Audit Log Evidence

**Location**: `logs/auth.log`
```
2024-01-15 14:23:45 INFO auth.login user=john@example.com ip=192.168.1.1 success=true
2024-01-15 14:23:46 WARN auth.login user=hacker@evil.com ip=10.0.0.1 success=false reason=invalid_password
2024-01-15 14:24:01 INFO auth.logout user=john@example.com session_duration=3600s
```

### Control Status: PASS

All CC6.1 requirements satisfied with evidence.

### Evidence Artifacts
| Artifact | Location | Description |
|----------|----------|-------------|
| Auth middleware | src/middleware/auth.ts | JWT authentication |
| RBAC middleware | src/middleware/authorize.ts | Role authorization |
| Auth logs | logs/auth.log | Login/logout audit trail |
```
