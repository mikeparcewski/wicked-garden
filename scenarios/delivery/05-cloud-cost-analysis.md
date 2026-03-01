---
name: cloud-cost-analysis
title: Cloud Cost Risk Monitoring
description: Use the risk-monitor agent to identify and track cost-related delivery risks
type: workflow
difficulty: intermediate
estimated_minutes: 8
---

# Cloud Cost Risk Monitoring

This scenario tests how wicked-delivery handles cost-related delivery risks using the `risk-monitor` agent. The plugin does not provide FinOps-specific cost analysis (no `finops-analyst`, `cost-optimizer`, or `forecast-specialist` agents exist). Instead, wicked-delivery contributes to cost conversations through the risk lens: surfacing cost overruns as delivery risks, tracking them in the risk matrix, and triggering escalation when thresholds are breached.

> **Scope note**: Deep cost analysis (right-sizing, billing breakdowns, reserved capacity modeling) is outside wicked-delivery's current scope. This scenario tests what the plugin actually does — risk identification, prioritization, and escalation tracking for cost-related concerns surfaced from project data.

## Setup

Create project data that includes cost-related signals visible in delivery context:

```bash
# Create test directory
mkdir -p /tmp/wicked-delivery-cost

# Create a project export with cost-adjacent signals
# (infra tasks, untracked resources, over-budget flags)
cat > /tmp/wicked-delivery-cost/platform-sprint.csv <<'EOF'
id,title,status,priority,assignee,labels,created_at,updated_at,closed_at
301,Audit untagged cloud resources,todo,P1,unassigned,infrastructure,2024-11-01,2024-11-01,
302,Right-size staging EC2 instances,todo,P2,unassigned,infrastructure,2024-11-01,2024-11-01,
303,Implement cost allocation tagging,in_progress,P1,alice,infrastructure,2024-10-28,2024-11-13,
304,Set up budget alerts in AWS,blocked,P0,bob,infrastructure,2024-10-25,2024-11-13,
305,Deploy new search service,done,P1,carol,feature,2024-11-04,2024-11-08,2024-11-08
306,Increase Lambda memory limits,done,P2,alice,infrastructure,2024-11-05,2024-11-07,2024-11-07
307,Review data retention policies,todo,P2,unassigned,compliance,2024-11-06,2024-11-06,
308,Migrate logs to cheaper storage tier,todo,P1,unassigned,infrastructure,2024-10-20,2024-11-01,
EOF

# Provide cost context as a separate note file for the risk-monitor
cat > /tmp/wicked-delivery-cost/cost-context.md <<'EOF'
# Cost Risk Context

## Current Situation
- November cloud spend: $74,700 (budget: $65,000)
- Over budget by $9,700 (15%)
- Platform team: $44,500 vs $35,000 budget (27% over)
- Staging EC2 spike: $8,900 (vs $2,890 in October, +208%)
- Untagged resources: $6,100/month and growing (+35% over 3 months)
- Budget alerts not yet configured (task 304 blocked)

## Known Issues
- Task 304 (budget alerts) blocked on AWS permissions approval from Finance
- 3 infra optimization tasks unassigned and aging
- No visibility into which team is driving the staging EC2 spike
EOF

echo "Setup complete."
```

## Steps

### 1. Generate a Delivery Report to Surface Cost Signals

Run the report command against the platform sprint to see what surfaces across personas:

```
/wicked-delivery:report /tmp/wicked-delivery-cost/platform-sprint.csv
```

**Expected Output**:

**Delivery Lead** should flag:
- P0 blocked task (budget alerts) — no visibility into spend without it
- Multiple aging infra tasks unassigned for 2+ weeks
- Sprint has delivery risk: 4 unassigned optimization tasks vs. 1 blocked P0

**Engineering Lead** should flag:
- High infra task load vs. feature work
- Staging cost spike likely tied to recent infra changes (Lambda memory increase, search service deploy)
- Untagged resource debt accumulating

**Product Lead** should flag:
- Only 1 feature task completed this sprint
- Infrastructure backlog consuming team capacity that could go to features

### 2. Run the Risk-Monitor Agent with Cost Context

Invoke the risk-monitor agent with the full cost picture:

```
Task tool: subagent_type="wicked-delivery:risk-monitor"
prompt="Analyze delivery risks for the platform team. Cost context is in /tmp/wicked-delivery-cost/cost-context.md. Key risks: monthly spend is 15% over budget, P0 task for budget alerts is blocked waiting on Finance, staging costs spiked 208% in one month with no root cause identified, $6,100/month in untagged resources is growing 35% quarter-over-quarter."
```

**Expected Output**:
- Risk matrix with at minimum 3 identified risks:
  - **P0**: No budget visibility (alerts blocked on Finance approval) — HIGH likelihood, HIGH impact
  - **P1**: Staging cost anomaly unidentified (+208%) — HIGH likelihood, MEDIUM impact
  - **P1**: Untagged resource creep — MEDIUM likelihood, MEDIUM impact (growing)

- Escalation triggers:
  - P0 unmitigated: budget alerts task blocked >2 days, requires immediate escalation
  - Recommend escalating Finance approval request to engineering leadership

- Mitigation recommendations:
  - Unblock task 304: escalate permissions request
  - Assign task 301 (resource audit) immediately to identify staging spike root cause
  - Set manual cost check cadence until alerts are online

- Dependency analysis:
  - Task 304 depends on Finance team (external)
  - Tasks 301, 302, 308 are unassigned — assign as parallel work while waiting on Finance

### 3. Track Risks in Kanban (if wicked-kanban available)

If wicked-kanban is installed, the risk-monitor agent will update task descriptions with risk assessment findings. Verify the P0 task (304) gets the risk assessment appended:

```
/wicked-kanban:board-status
```

**Expected**: Task 304 description updated with risk assessment section showing P0 priority and escalation trigger.

### 4. Generate a Risk Report for Leadership

Ask the risk-monitor to produce a formatted escalation report:

```
Task tool: subagent_type="wicked-delivery:risk-monitor"
prompt="Generate a risk escalation report I can send to engineering leadership about our cloud cost situation. Focus on the P0 blocked budget alerts task and the staging cost spike."
```

**Expected Output**:
```markdown
## Risk Escalation Report

**Project**: Platform Team - Infrastructure Sprint
**Date**: {date}
**Overall Risk**: HIGH

### Executive Summary
Platform team cloud costs are 15% over budget with no automated visibility — budget alerts are blocked on Finance approval. A 208% staging cost spike remains unidentified. Immediate action needed on both fronts.

### Critical Risks (P0)

| Risk | Likelihood | Impact | Status |
|------|------------|--------|--------|
| No budget visibility (alerts blocked) | HIGH | HIGH | Unmitigated |

**Immediate action required**: Escalate Finance permissions request. Every day without alerts is a day over-budget spend goes undetected.

### High Risks (P1)

| Risk | Likelihood | Impact | Status |
|------|------------|--------|--------|
| Staging cost anomaly (+208%) | HIGH | MEDIUM | Under investigation |
| Untagged resource creep (+35%) | MEDIUM | MEDIUM | Unassigned |

### Escalations Needed
- Finance team: AWS budget alerts permissions (Task 304, blocked >14 days)
- Engineering leadership: Approve resource audit as P1 priority

### Recommended Actions
1. TODAY: Escalate Finance approval request
2. THIS WEEK: Assign resource audit task (301) to identify staging spike
3. THIS SPRINT: Complete cost tagging task (303) to eliminate untagged spend
```

## Expected Outcome

- wicked-delivery surfaces cost-related delivery risks without requiring specialized FinOps tooling
- Risk-monitor agent correctly categorizes cost visibility gaps as P0 delivery risks
- Escalation recommendations are concrete and actionable
- Report is suitable for engineering leadership communication
- Plugin's scope is clear: risk identification and tracking, not billing analysis

## Success Criteria

- [ ] `/wicked-delivery:report` surfaces infra task aging and P0 block across persona reports
- [ ] Risk-monitor agent generates risk matrix with at least 3 cost-related risks
- [ ] P0 risk (blocked budget alerts) identified with HIGH likelihood + HIGH impact
- [ ] Escalation trigger fired for P0 unmitigated past threshold
- [ ] Mitigation recommendations are specific (assign task 301, escalate Finance approval)
- [ ] Risk report format is leadership-appropriate
- [ ] Dependency analysis identifies external dependency (Finance team)
- [ ] Plugin does NOT claim FinOps analysis capabilities it does not have

## What This Plugin Does NOT Cover

The following FinOps capabilities are outside wicked-delivery's current scope and would require a dedicated plugin or specialist:

- Cloud billing data ingestion and cost breakdown by service/team
- Right-sizing analysis from utilization metrics
- Reserved capacity modeling and savings forecasting
- Multi-month trend analysis with anomaly detection

If these are needed, they would be handled by a future `wicked-finops` plugin or a wicked-data analysis workflow.

## Integration Notes

**With wicked-kanban**: Risk findings written to task descriptions for tracking
**With wicked-mem**: Risk patterns stored for recall on similar future projects
**With wicked-search**: Can search codebase for cost-adjacent signals (hardcoded resource sizes, TODO cost-related comments)
**Standalone**: Works from verbal description or project export data

## Cleanup

```bash
rm -rf /tmp/wicked-delivery-cost
```
