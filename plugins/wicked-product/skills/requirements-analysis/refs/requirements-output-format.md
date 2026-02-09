# Requirements Output Format

Standard format for documenting requirements analysis results.

## Overview

This document defines the expected output structure when conducting requirements analysis. The format ensures:
- Consistency across projects
- Complete traceability
- Clear handoff to design and QE
- Integration with wicked-kanban and wicked-mem

## Standard Output Structure

```markdown
# Requirements Analysis: {Project/Feature Name}

**Date**: {YYYY-MM-DD}
**Analyzed By**: {Name/Role}
**Stakeholders**: {Comma-separated list}
**Status**: {Draft/Review/Approved}

## Executive Summary

{2-3 sentence overview of what is being built and why}

## Context

### Business Goals
- {Goal 1}
- {Goal 2}

### User Needs
- {Need 1}
- {Need 2}

### Constraints
- {Constraint 1: technical, timeline, budget, etc.}
- {Constraint 2}

## Personas

### {Persona 1 Name}
- **Role**: {Title/Description}
- **Goals**: {What they want to achieve}
- **Pain Points**: {Current problems}
- **Technical Proficiency**: {Low/Medium/High}

### {Persona 2 Name}
- **Role**: {Title/Description}
- **Goals**: {What they want to achieve}
- **Pain Points**: {Current problems}
- **Technical Proficiency**: {Low/Medium/High}

## User Stories

### US-{ID}: {Story Title}

**As a** {persona}
**I want** {capability}
**So that** {benefit}

**Priority**: {P0/P1/P2/P3}
**Complexity**: {S/M/L/XL}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}
2. Given {error condition}, When {action}, Then {error handling}
3. Given {edge case}, When {action}, Then {graceful behavior}

**Dependencies**: {List of dependencies}
**Assumptions**: {List of assumptions}
**Open Questions**: {List of questions}

{Repeat for each user story}

## Functional Requirements

### {Feature Area 1}
1. **REQ-{ID}**: {Requirement description}
   - **Rationale**: {Why this is needed}
   - **Acceptance**: {How to verify}
   - **Priority**: {P0/P1/P2/P3}

### {Feature Area 2}
{Repeat structure}

## Non-Functional Requirements

### Performance
- **REQ-PERF-{ID}**: {Performance requirement}
  - Target: {Metric and threshold}
  - Measured by: {How to measure}

### Security
- **REQ-SEC-{ID}**: {Security requirement}
  - Compliance: {Standards/regulations}
  - Verification: {How to verify}

### Scalability
- **REQ-SCALE-{ID}**: {Scalability requirement}
  - Target: {Growth expectations}
  - Strategy: {How to achieve}

### Usability
- **REQ-UX-{ID}**: {Usability requirement}
  - Standard: {WCAG, mobile-first, etc.}
  - Verification: {User testing, automated checks}

## Scope Definition

### In Scope
- {Feature/capability 1}
- {Feature/capability 2}

### Out of Scope
- {Explicitly excluded item 1}
- {Explicitly excluded item 2}

### Future Considerations
- {Nice-to-have for future releases}

## Dependencies

### Internal
- {Team/system dependency}
- {Prerequisite work}

### External
- {Third-party service}
- {External API}

## Assumptions

1. {Assumption 1}
2. {Assumption 2}

## Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| {Risk description} | {H/M/L} | {H/M/L} | {Mitigation strategy} |

## Open Questions

- [ ] {Question requiring stakeholder input}
- [ ] {Technical decision needed}
- [ ] {Clarification needed}

## Traceability

- **Source Document**: {Link to original brief/request}
- **Design Phase**: {Link to phases/design/}
- **Test Scenarios**: {Link to phases/qe/}
- **Kanban**: {Link to wicked-kanban tasks}
- **Memory**: {wicked-mem tags for recall}

## Appendices

### A. Glossary
- **{Term}**: {Definition}

### B. References
- {Document/URL}

### C. Revision History
| Date | Author | Changes |
|------|--------|---------|
| {YYYY-MM-DD} | {Name} | {Description} |
```

## Minimal Output Format

For smaller features or rapid analysis:

```markdown
# Requirements: {Feature Name}

## Summary
{1-2 sentence description}

## User Stories

### US-001: {Title}
**As a** {persona}
**I want** {capability}
**So that** {benefit}

**Acceptance Criteria**:
1. Given {context}, When {action}, Then {outcome}

{Repeat for 3-5 core stories}

## Out of Scope
- {Excluded item}

## Open Questions
- [ ] {Question}
```

## Domain-Specific Examples

### Example 1: Authentication Feature

```markdown
# Requirements Analysis: User Authentication System

**Date**: 2026-01-24
**Analyzed By**: Product Team
**Stakeholders**: Engineering, QE, Security, Customer Success
**Status**: Review

## Executive Summary

Build a secure authentication system supporting email/password login with password reset capabilities. Enables customers to create accounts, securely access their data, and manage credentials.

## Context

### Business Goals
- Enable user account creation for personalized experiences
- Meet security compliance requirements (SOC2)
- Reduce support tickets related to access issues

### User Needs
- Quick account creation
- Secure login
- Easy password recovery
- Persistent sessions

### Constraints
- Must launch within 6 weeks
- Integrate with existing user database schema
- GDPR compliance required for EU users

## Personas

### New Customer
- **Role**: First-time visitor wanting to create account
- **Goals**: Quickly sign up and access features
- **Pain Points**: Forgot password, complex registration flows
- **Technical Proficiency**: Low to Medium

### Returning Customer
- **Role**: Existing user returning to service
- **Goals**: Quick, secure access to account
- **Pain Points**: Remembering credentials, account lockouts
- **Technical Proficiency**: Medium

### Support Agent
- **Role**: Customer support helping with access issues
- **Goals**: Quickly help users regain access
- **Pain Points**: Unable to reset passwords, no visibility into account status
- **Technical Proficiency**: High

## User Stories

### US-AUTH-001: User Registration

**As a** new customer
**I want to** register with email and password
**So that** I can create an account and save my preferences

**Priority**: P0
**Complexity**: M

**Acceptance Criteria**:
1. Given valid email and password (8+ chars), When I submit registration, Then account created
2. Given email already registered, When I submit, Then error "Email already in use"
3. Given weak password (<8 chars), When I submit, Then error with strength requirements
4. Given successful registration, When account created, Then confirmation email sent

**Dependencies**: Email service integration
**Assumptions**: Email verification required before full access
**Open Questions**:
- [ ] Support social login (Google, GitHub)?
- [ ] Password strength requirements (special chars, numbers)?

### US-AUTH-002: User Login

**As a** returning customer
**I want to** log in with email and password
**So that** I can access my account and data

**Priority**: P0
**Complexity**: S

**Acceptance Criteria**:
1. Given valid credentials, When I submit login, Then redirected to dashboard
2. Given invalid password, When I submit, Then error "Invalid email or password"
3. Given account locked, When I submit, Then error "Account locked. Reset password."
4. Given successful login, When I close browser and return within 24h, Then still logged in

**Dependencies**: Session management
**Assumptions**: Sessions expire after 24 hours of inactivity
**Open Questions**:
- [ ] "Remember me" functionality?
- [ ] Multi-device session limits?

### US-AUTH-003: Password Reset

**As a** customer who forgot password
**I want to** reset my password via email
**So that** I can regain access to my account

**Priority**: P0
**Complexity**: M

**Acceptance Criteria**:
1. Given registered email, When I request reset, Then reset link sent to email
2. Given valid reset link, When I submit new password, Then password updated
3. Given expired reset link (>24h), When I try to reset, Then error "Link expired"
4. Given non-existent email, When I request reset, Then generic success message (no disclosure)

**Dependencies**: Email service, token generation
**Assumptions**: Reset links expire after 24 hours
**Open Questions**:
- [ ] Security questions as alternative?
- [ ] SMS-based reset option?

## Functional Requirements

### Authentication
1. **REQ-AUTH-001**: Support email/password authentication
   - **Rationale**: Primary authentication method
   - **Acceptance**: User can register and login
   - **Priority**: P0

2. **REQ-AUTH-002**: Hash passwords with bcrypt (cost factor 12)
   - **Rationale**: Security best practice
   - **Acceptance**: Passwords never stored in plaintext
   - **Priority**: P0

3. **REQ-AUTH-003**: Lock account after 3 failed login attempts
   - **Rationale**: Prevent brute force attacks
   - **Acceptance**: Account locked, only unlockable via password reset
   - **Priority**: P1

### Session Management
1. **REQ-SESS-001**: Sessions expire after 24 hours of inactivity
   - **Rationale**: Balance security and convenience
   - **Acceptance**: User logged out after 24h inactive
   - **Priority**: P1

2. **REQ-SESS-002**: Support session persistence across browser restarts
   - **Rationale**: User convenience
   - **Acceptance**: User stays logged in if within 24h window
   - **Priority**: P2

## Non-Functional Requirements

### Performance
- **REQ-PERF-001**: Login response time <500ms (95th percentile)
  - Target: Fast, responsive login
  - Measured by: Application performance monitoring

### Security
- **REQ-SEC-001**: All authentication endpoints must use HTTPS
  - Compliance: SOC2, GDPR
  - Verification: SSL/TLS enforcement

- **REQ-SEC-002**: Password reset tokens must be single-use
  - Compliance: Security best practice
  - Verification: Token invalidated after use

- **REQ-SEC-003**: Log all authentication events (login, logout, failed attempts)
  - Compliance: Audit requirements
  - Verification: Events logged to security audit trail

### Usability
- **REQ-UX-001**: Error messages must not disclose whether email is registered
  - Standard: Security best practice (prevent enumeration)
  - Verification: Consistent messaging for valid/invalid emails

- **REQ-UX-002**: Mobile-responsive login/registration forms
  - Standard: Mobile-first design
  - Verification: Forms usable on 320px+ screens

## Scope Definition

### In Scope
- Email/password registration
- Email/password login
- Password reset via email
- Session management
- Account lockout after failed attempts

### Out of Scope
- Social login (Google, GitHub) - future consideration
- Two-factor authentication (2FA) - future consideration
- SSO/SAML integration - future consideration
- Password strength meter UI - nice-to-have
- Biometric authentication - future consideration

### Future Considerations
- 2FA for high-security accounts
- OAuth2 integration for third-party apps
- Passwordless authentication (magic links)

## Dependencies

### Internal
- Email service for verification and reset emails
- Database schema updates for user table
- Frontend team for login/registration UI

### External
- Email delivery service (SendGrid/SES)
- Session storage (Redis or database)

## Assumptions

1. Email service is reliable with >99% delivery rate
2. Users have access to email for verification
3. Existing user table can be extended for auth fields
4. 24-hour session timeout is acceptable for users

## Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Email delivery failures | High | Medium | Implement retry logic, provide alternative contact |
| Credential stuffing attacks | High | Medium | Account lockout, rate limiting, monitoring |
| Password reset token leakage | High | Low | Short expiry, single-use tokens, secure transport |
| Poor mobile UX | Medium | Medium | Responsive design, user testing |

## Open Questions

- [ ] Should we support "remember me" functionality?
- [ ] What password complexity requirements? (special chars, numbers, length)
- [ ] Support social login in this phase or defer?
- [ ] Multi-device session limits (e.g., max 5 active sessions)?
- [ ] Account deletion/deactivation flow needed?

## Traceability

- **Source Document**: outcome.md
- **Design Phase**: phases/design/auth-architecture.md
- **Test Scenarios**: phases/qe/auth-test-scenarios.md
- **Kanban**: wicked-kanban tasks tagged "auth"
- **Memory**: Tags: auth, security, user-management

## Appendices

### A. Glossary
- **Session**: Server-side authentication state
- **Token**: Single-use, time-limited credential for password reset
- **Account Lockout**: Temporary disabling of account after failed login attempts

### B. References
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [SOC2 Authentication Requirements](https://example.com)
- [GDPR User Data Guidelines](https://example.com)

### C. Revision History
| Date | Author | Changes |
|------|--------|---------|
| 2026-01-24 | Product Team | Initial draft |
```

### Example 2: Data Export Feature (Minimal Format)

```markdown
# Requirements: CSV Export for Reports

## Summary
Enable managers to export report data to CSV for offline analysis in Excel.

## User Stories

### US-EXPORT-001: Export Report Data

**As a** manager
**I want to** export report data to CSV
**So that** I can analyze trends offline in Excel

**Priority**: P1
**Complexity**: M

**Acceptance Criteria**:
1. Given report data exists, When I click export, Then CSV downloads with all data
2. Given large dataset (10k+ rows), When I export, Then async job with email notification
3. Given no data in report, When I click export, Then message "No data to export"
4. Given CSV contains special characters, When I export, Then properly escaped for Excel

### US-EXPORT-002: Custom Date Range Export

**As a** manager
**I want to** select date range for export
**So that** I can focus on specific time periods

**Priority**: P2
**Complexity**: S

**Acceptance Criteria**:
1. Given date range selected, When I export, Then only data in range included
2. Given invalid date range (start > end), When I try export, Then validation error

## Out of Scope
- PDF export format
- Scheduled/recurring exports
- Custom column selection
- Multiple file format options (Excel, JSON, XML)

## Open Questions
- [ ] Max row limit for synchronous export? (suggest 10k)
- [ ] Column headers customizable?
- [ ] Include metadata (export date, user, filters)?
```

## Integration Points

### With Wicked Kanban
Store requirements as tasks:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/../wicked-kanban/scripts/kanban.py" \
  add-task "Requirements" "US-AUTH-001" \
  --tags "auth,p0" \
  --description "$(cat requirements.md)"
```

### With Wicked Mem
Store for pattern recall:
```bash
/wicked-mem:store "auth-requirements-2026" "$(cat requirements.md)"
```

### With Wicked QE
Requirements feed test scenarios:
```
Requirements → User Stories → Acceptance Criteria → Test Scenarios
```

## Validation Checklist

Before finalizing requirements document:

- [ ] All user stories have persona, capability, benefit
- [ ] All stories have at least 3 acceptance criteria
- [ ] Scope clearly defined (in scope, out of scope)
- [ ] Dependencies documented
- [ ] Open questions captured
- [ ] Traceability links included
- [ ] Non-functional requirements addressed
- [ ] Stakeholders identified
- [ ] Risks assessed

## Output Delivery

Requirements should be saved to:
- `phases/requirements/analysis.md` (in project workflow)
- `requirements.md` (standalone project)
- Linked from `outcome.md`
- Referenced in wicked-kanban tasks

## Templates

### Quick Start Template
```bash
# Copy minimal template for new requirements
cp "${CLAUDE_PLUGIN_ROOT}/templates/requirements-minimal.md" \
   requirements.md
```

### Full Template
```bash
# Copy full template for comprehensive analysis
cp "${CLAUDE_PLUGIN_ROOT}/templates/requirements-full.md" \
   requirements.md
```

## Resources

- **User Story Guide**: `refs/user-story-guide.md`
- **Acceptance Criteria**: See product-management skill
- **Example Projects**: Search wicked-mem for "requirements-example"
