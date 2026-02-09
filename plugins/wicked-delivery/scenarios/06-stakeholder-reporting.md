---
name: stakeholder-reporting
title: Multi-Perspective Stakeholder Reporting
description: Generate delivery reports from project exports with specialized persona analysis
type: feature
difficulty: advanced
estimated_minutes: 12
---

# Multi-Perspective Stakeholder Reporting

This scenario validates that wicked-delivery can generate comprehensive delivery reports from project management exports, analyzing data through multiple stakeholder perspectives (Delivery Lead, Engineering Lead, Product Lead, QE Lead, etc.).

## Setup

Create a realistic project export that simulates data from Jira, Linear, or GitHub Projects:

```bash
# Create test project directory
mkdir -p ~/test-wicked-delivery/project-report
cd ~/test-wicked-delivery/project-report

# Create a sprint export (simulating Jira CSV export)
cat > sprint-export.csv <<'EOF'
key,summary,type,status,priority,assignee,created,updated,story_points,labels,sprint
AUTH-101,Implement OAuth2 flow,Story,Done,High,alice,2024-11-01,2024-11-08,5,"auth,security",Sprint 47
AUTH-102,Add password reset endpoint,Story,Done,High,bob,2024-11-01,2024-11-10,3,"auth",Sprint 47
AUTH-103,Fix session timeout bug,Bug,Done,Critical,alice,2024-11-02,2024-11-03,2,"auth,urgent",Sprint 47
AUTH-104,Add MFA support,Story,In Progress,High,carol,2024-11-04,2024-11-12,8,"auth,security",Sprint 47
AUTH-105,Update auth documentation,Task,To Do,Low,unassigned,2024-11-05,2024-11-05,1,"docs",Sprint 47
AUTH-106,Security audit findings,Bug,Blocked,Critical,bob,2024-11-06,2024-11-12,5,"security,blocked",Sprint 47
AUTH-107,Add rate limiting to login,Story,In Progress,Medium,alice,2024-11-07,2024-11-12,3,"auth,performance",Sprint 47
AUTH-108,Refactor auth middleware,Tech Debt,To Do,Medium,unassigned,2024-11-08,2024-11-08,5,"refactor",Sprint 47
AUTH-109,Add auth metrics dashboard,Story,To Do,Low,carol,2024-11-09,2024-11-09,3,"observability",Sprint 47
AUTH-110,Fix CORS issue on login,Bug,Done,High,bob,2024-11-10,2024-11-11,1,"auth,frontend",Sprint 47
PAY-201,Implement Stripe webhooks,Story,In Progress,High,david,2024-11-01,2024-11-12,8,"payments",Sprint 47
PAY-202,Add refund endpoint,Story,To Do,High,unassigned,2024-11-02,2024-11-02,5,"payments",Sprint 47
PAY-203,Fix payment timeout issue,Bug,In Progress,Critical,david,2024-11-08,2024-11-12,3,"payments,urgent",Sprint 47
EOF

# Create team context file
cat > team-context.md <<'EOF'
# Team Context

## Sprint 47 Information
- Sprint dates: Nov 1-14, 2024
- Team size: 4 engineers (Alice, Bob, Carol, David)
- Sprint goal: Complete OAuth2 implementation and start payment improvements
- Committed points: 42
- Engineering days available: 36 (accounting for meetings, PTO)

## Key Stakeholders
- Product: Sarah (PM for Auth/Identity)
- Engineering Manager: Mike
- QE Lead: Lisa
- Security: James (security team liaison)

## Known Context
- AUTH-106 blocked on security team review (James OOO until Nov 13)
- Carol joining mid-sprint (Nov 4), ramping up on codebase
- Black Friday prep affecting PAY priorities
EOF

echo "Setup complete. Project report context created."
```

## Steps

### 1. Generate Quick Report (Default 3 Personas)

Generate a report with the default three perspectives:

```
Task tool: subagent_type="wicked-delivery:stakeholder-reporter"
prompt="Generate a delivery report for Sprint 47 from sprint-export.csv. Include context from team-context.md."
```

**Expected Output**:
Report with three perspectives:

**Delivery Lead Perspective**:
- Sprint health: At Risk (blocked items, unassigned work)
- Velocity: 11 points completed of 42 committed (26%)
- Blockers: 1 critical (AUTH-106 security audit)
- Timeline risk: HIGH - unlikely to hit sprint goal
- Recommendations: Escalate AUTH-106, reassign AUTH-105/108/109

**Engineering Lead Perspective**:
- Technical debt: 1 item in backlog (AUTH-108)
- Team capacity: 4 engineers, uneven distribution
- Implementation concerns: MFA (AUTH-104) is large story in progress
- Code quality: No test coverage mentioned
- Recommendations: Break down AUTH-104, pair programming for Carol

**Product Lead Perspective**:
- Feature delivery: OAuth2 mostly complete (AUTH-101, 102, 103 done)
- User value: Core auth flows working, MFA pending
- Gaps: Documentation lagging (AUTH-105 unassigned)
- Stakeholder communication: Security team dependency
- Recommendations: Deprioritize AUTH-109 for sprint goal focus

### 2. Generate Comprehensive Report (All 6 Personas)

Generate a full report with extended perspectives:

```
Task tool: subagent_type="wicked-delivery:stakeholder-reporter"
prompt="Generate a comprehensive delivery report with all perspectives (--all). Include QE, Architecture, and DevSecOps views."
```

**Expected Output**:
Report adds three more perspectives:

**QE Lead Perspective**:
- Test coverage: Unknown (no test-related labels)
- Defect density: 3 bugs found (AUTH-103, AUTH-106, AUTH-110, PAY-203)
- Quality trends: 2 bugs marked "urgent" - reactive pattern
- Risk areas: MFA (AUTH-104) lacks test scenarios
- Recommendations: Add test requirements to story acceptance criteria

**Architecture Lead Perspective**:
- System impact: Auth changes affect all API endpoints
- Scalability: Rate limiting (AUTH-107) addresses scale concern
- Integration points: Stripe webhook integration (PAY-201)
- Technical decisions: None documented in sprint
- Recommendations: Document auth middleware refactor approach before AUTH-108

**DevSecOps Lead Perspective**:
- Security items: 2 in sprint (AUTH-101 OAuth, AUTH-106 audit)
- Blocked security: AUTH-106 critical and blocked
- CI/CD impact: No deployment-related items
- Operational readiness: AUTH-109 metrics dashboard would help
- Recommendations: Prioritize AUTH-106 resolution before release

### 3. Generate Focused Analysis

Request specific persona perspectives:

```
Task tool: subagent_type="wicked-delivery:stakeholder-reporter"
prompt="Give me just the QE Lead and Security perspectives for this sprint. Focus on risk."
```

**Expected Output**:
- Focused report with only requested perspectives
- QE: Defect patterns, missing tests, quality risks
- Security: AUTH-106 blocked, OAuth implementation review status
- Combined risk assessment from both lenses

### 4. Generate Steering Committee Summary

Create executive-level summary:

```
Task tool: subagent_type="wicked-delivery:stakeholder-reporter"
prompt="Generate a one-page executive summary for the steering committee. They care about: will we hit our goals? What are the risks?"
```

**Expected Output**:
```markdown
## Sprint 47 Executive Summary

### Status: AT RISK

**Sprint Goal**: Complete OAuth2 implementation and start payment improvements
**Progress**: 26% of committed points complete

### Key Metrics
| Metric | Value | Status |
|--------|-------|--------|
| Completed | 11 points (4 items) | Behind |
| In Progress | 22 points (4 items) | In flight |
| Blocked | 5 points (1 item) | CRITICAL |
| Remaining | 9 points (4 items) | Unstarted |

### Critical Risks
1. **AUTH-106** (Security audit) blocked on external dependency
   - Impact: Cannot release auth changes until resolved
   - Mitigation: Escalate to security team manager

2. **Sprint goal at risk**
   - Only 26% complete at mid-sprint
   - 4 items unassigned/unstarted

### Recommendations for Leadership
1. Approve scope reduction (defer AUTH-105, AUTH-109)
2. Support escalation of AUTH-106 blocker
3. Accept revised sprint goal: OAuth2 core complete, MFA partial
```

### 5. Compare to Previous Sprint

If historical data available (via wicked-mem):

```
Task tool: subagent_type="wicked-delivery:stakeholder-reporter"
prompt="How does this sprint compare to Sprint 46? Are we improving or regressing?"
```

**Expected Output** (with wicked-mem):
- Velocity comparison (Sprint 46 vs 47)
- Blocker rate comparison
- Story completion rate trend
- Team capacity changes
- Recommendations based on trend

**Expected Output** (without wicked-mem):
- Note that historical data not available
- Recommendation to store current sprint for future comparison
- Fallback to single-sprint analysis

## Expected Outcome

- Report covers multiple stakeholder perspectives
- Each perspective focuses on their domain concerns
- Recommendations are actionable and specific
- Data-driven insights (not generic observations)
- Executive summary is concise (one page)
- Historical comparison works when memory available
- Graceful degradation without wicked-mem

## Success Criteria

- [ ] Delivery Lead perspective covers: velocity, blockers, timeline risk
- [ ] Engineering Lead perspective covers: tech debt, capacity, complexity
- [ ] Product Lead perspective covers: feature delivery, user value, gaps
- [ ] QE Lead perspective covers: defects, quality trends, test coverage
- [ ] Architecture Lead perspective covers: system impact, integration points
- [ ] DevSecOps Lead perspective covers: security items, operational readiness
- [ ] All perspectives include specific recommendations
- [ ] Recommendations reference actual ticket IDs (AUTH-XXX)
- [ ] Executive summary fits one page/screen
- [ ] Report acknowledges blocked items with impact
- [ ] Report identifies unassigned work as risk
- [ ] Historical comparison available with wicked-mem
- [ ] Report format is professional and shareable

## Value Demonstrated

**Real-world value**: Status reporting is a significant time sink for engineering teams. Managers spend hours each week:
- Pulling data from Jira/Linear/GitHub
- Writing status updates for different audiences
- Translating technical details for executives
- Reconciling different perspectives on "how things are going"

wicked-delivery's reporting capabilities automate the most tedious parts:

1. **Data aggregation**: Pull metrics from export without manual counting
2. **Multi-perspective analysis**: Six specialized viewpoints in one command
3. **Audience targeting**: Executive summary vs detailed engineering view
4. **Pattern detection**: Identifies blockers, unassigned work, anomalies
5. **Actionable output**: Specific recommendations with ticket references

For teams with multiple stakeholders (PM, EM, QE, Security), the multi-persona approach ensures nothing falls through the cracks. The Delivery Lead catches timeline risks. The QE Lead catches quality gaps. The Security Lead catches compliance issues. Each perspective adds value that a single-viewpoint report would miss.

The integration with wicked-mem enables trend analysis - not just "where are we now" but "are we getting better or worse?" This longitudinal view is crucial for continuous improvement.

## Integration Notes

**With wicked-cache**: Caches analysis results for faster repeat runs
**With wicked-mem**: Stores reports for historical comparison
**With wicked-kanban**: Links to tracked project items
**Standalone**: Full functionality with provided export files

## Cleanup

```bash
rm -rf ~/test-wicked-delivery/project-report
```
