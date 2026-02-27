---
name: qe-shift-left
title: Shift-Left QE Review
description: Full-spectrum quality review before code is written
type: testing
difficulty: intermediate
estimated_minutes: 12
---

# Shift-Left QE Review

This scenario demonstrates using wicked-qe's QE capabilities to catch quality issues early - reviewing requirements, design, and architecture BEFORE writing code.

## Setup

Create a project with requirements and design docs for a new feature:

```bash
# Create test project
mkdir -p ~/test-wicked-qe/qe-test
cd ~/test-wicked-qe/qe-test

# Create requirements document with quality issues
mkdir -p docs
cat > docs/requirements.md << 'EOF'
# Password Reset Feature Requirements

## Overview
Users should be able to reset their password if they forget it.

## Requirements

### REQ-1: Request Password Reset
- User enters their email address
- System sends a reset link
- User clicks link to reset password

### REQ-2: Reset Password
- User enters new password
- Password is updated
- User can log in with new password

### REQ-3: Security
- Reset links should be secure
- Multiple reset requests should be handled
- Brute force should be prevented

## Acceptance Criteria
- Password reset works
- Email is sent
- Link works
EOF

# Create design document
cat > docs/design.md << 'EOF'
# Password Reset Design

## Flow
1. User enters email on /forgot-password page
2. Backend generates reset token and stores in database
3. Email sent with link containing token
4. User clicks link, redirected to /reset-password?token=xxx
5. User enters new password
6. Backend validates token and updates password
7. User redirected to login

## API Endpoints

### POST /api/auth/forgot-password
Request: { email: string }
Response: { success: true }

### POST /api/auth/reset-password
Request: { token: string, password: string }
Response: { success: true }

## Database Schema
```sql
CREATE TABLE password_reset_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id),
  token VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Security Considerations
- Token should be random
- Token should expire
EOF
```

## Steps

### 1. Review Requirements

```bash
/wicked-qe:qe docs/requirements.md --focus requirements
```

**Expected**: Requirements review should identify:
- Vague acceptance criteria ("password reset works" is not testable)
- Missing edge cases (what if email doesn't exist?)
- Incomplete security requirements (no specifics on expiration, length)
- No error scenarios defined

### 2. Review Design

```bash
/wicked-qe:qe docs/design.md --focus arch
```

**Expected**: Architecture review should identify:
- No token expiration in schema
- No index on token column (slow lookups)
- No rate limiting specified
- Response doesn't indicate if email exists (enumeration)

### 3. Full QE Review

```bash
/wicked-qe:qe docs/ --focus all
```

**Expected**: Comprehensive review across all focus areas.

## Expected Outcome

```markdown
## Requirements QE Review

### Testability Score: 2/5

### Issues Found
| Requirement | Issue | Impact | Recommendation |
|-------------|-------|--------|----------------|
| REQ-1 | No error handling defined | Can't verify behavior for invalid email | Add: "If email not found, show same success message (no enumeration)" |
| REQ-2 | Password requirements undefined | Can't verify password validation | Add: "Password must be 8+ chars with number and special char" |
| REQ-3 | "Secure" is vague | Can't verify security | Add specific: "Token expires in 1 hour, single-use" |
| All | Acceptance criteria too vague | Cannot write test cases | Rewrite with specific, measurable outcomes |

### Missing Scenarios
- [ ] What happens when email doesn't exist in system?
- [ ] What happens when user requests multiple resets?
- [ ] What happens with expired token?
- [ ] What happens with already-used token?
- [ ] What is the password complexity requirement?
- [ ] How long is the token valid?
- [ ] Can user reset while logged in?

### Recommendations
1. Replace "Password reset works" with specific criteria:
   - Given valid email, when reset requested, then email sent within 30 seconds
   - Given valid token, when new password meets requirements, then password updated
   - Given expired token, when reset attempted, then error "Link has expired"

---

## Architecture QE Review

### Testability Assessment
| Component | Unit Testable | Integration Testable | Issue |
|-----------|---------------|---------------------|-------|
| Token generation | Yes | Yes | - |
| Token storage | Yes | Yes | No expiration column |
| Email sending | No | No | No abstraction for testing |
| Token validation | Yes | Yes | No used_at tracking |

### Design Gaps

#### Security
- **Token expiration**: Schema has `created_at` but no `expires_at` or TTL logic
- **Token single-use**: No `used_at` column to prevent reuse
- **Rate limiting**: Not specified - can spam reset requests
- **Email enumeration**: Same response for valid/invalid email (good!) but not documented

#### Testability
- **Email abstraction missing**: Can't test email sending without real SMTP
- **Clock dependency**: Token expiration logic will be hard to test

#### Operational
- **No index on token**: Full table scan on every reset attempt
- **No cleanup strategy**: Old tokens accumulate forever

### Recommendations

```sql
-- Improved schema
CREATE TABLE password_reset_tokens (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id),
  token VARCHAR(64) NOT NULL,  -- Shorter, indexed
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL,  -- Explicit expiration
  used_at TIMESTAMP,  -- Track usage
  UNIQUE(token)  -- Ensure uniqueness + index
);

CREATE INDEX idx_tokens_lookup ON password_reset_tokens(token)
  WHERE used_at IS NULL;  -- Partial index for unused tokens
```

---

## UX QE Review

### Flow Coverage
| Flow | Happy Path | Error States | Edge Cases |
|------|------------|--------------|------------|
| Request reset | Defined | Not defined | Multiple requests |
| Reset password | Defined | Not defined | Back button, refresh |
| Email delivery | Assumed | Not defined | Spam folder, delay |

### Accessibility Gaps
- [ ] Form labels and ARIA attributes not specified
- [ ] Error message announcement for screen readers
- [ ] Keyboard navigation for reset flow

### Test Scenarios Needed
- User completes reset on first attempt
- User with invalid email sees same success message
- User clicks expired link
- User requests reset twice quickly
- User bookmarks reset link, uses later

---

## Full QE Summary

| Area | Score | Critical Issues |
|------|-------|-----------------|
| Requirements | 2/5 | 3 - Vague criteria, missing edge cases |
| Architecture | 3/5 | 2 - No expiration, no rate limit |
| UX | 3/5 | 1 - Error states undefined |
| Code | N/A | Not yet written |
| Deployment | N/A | Not yet defined |

### Release Recommendation
**NOT READY** - Address critical requirements and design issues before implementation.

### Priority Actions
1. [Critical] Define specific acceptance criteria with measurable outcomes
2. [Critical] Add token expiration and single-use tracking to schema
3. [High] Specify rate limiting for reset requests
4. [High] Define all error scenarios and messages
5. [Medium] Add email abstraction interface for testability
```

## Success Criteria

- [ ] Requirements review identifies vague acceptance criteria
- [ ] Missing edge cases are enumerated
- [ ] Security gaps in design are flagged
- [ ] Schema issues identified (no expiration, no index)
- [ ] Rate limiting gap identified
- [ ] Testability issues flagged (email dependency)
- [ ] UX error states identified as missing
- [ ] Concrete schema improvements provided
- [ ] Clear "NOT READY" recommendation with reasons

## Value Demonstrated

**Problem solved**: Quality issues discovered during implementation or testing are expensive to fix. Requirements gaps cause rework. Design flaws become technical debt.

**Real-world value**:
- **Shift-left**: Catch issues when they're cheapest to fix (before code)
- **Complete requirements**: Don't discover missing scenarios during QA
- **Testable design**: Build in testability from the start
- **Security by design**: Address security in requirements, not as afterthought

This replaces the common pattern of:
1. Write vague requirements
2. Implement something
3. QA finds edge cases
4. Rework implementation
5. Repeat

With QE review upfront, the team knows exactly what to build and test before writing code. The feature ships faster because there's less rework.
