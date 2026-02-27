---
name: sprint-health-check
title: Sprint Health Check
description: Generate a multi-perspective sprint health report from a project data export
type: workflow
difficulty: basic
estimated_minutes: 6
---

# Sprint Health Check

This scenario validates that wicked-delivery can assess sprint health from project management data exports. The `/wicked-delivery:report` command produces multi-persona analysis covering velocity, blockers, and risk — giving engineering managers and tech leads a complete delivery picture without manual aggregation.

## Setup

Create a sprint export CSV simulating realistic in-flight sprint data:

```bash
# Create test directory
mkdir -p /tmp/wicked-delivery-sprint

# Sprint 47 data — Payment Refactor sprint with a realistic task distribution
cat > /tmp/wicked-delivery-sprint/sprint-47.csv <<'EOF'
id,title,status,priority,assignee,labels,story_points,created_at,updated_at,closed_at
201,Implement Stripe webhook handler,done,P1,alice,payments,5,2024-11-01,2024-11-04,2024-11-04
202,Add payment method validation,done,P1,bob,payments,3,2024-11-01,2024-11-05,2024-11-05
203,Update payment confirmation email,done,P2,carol,payments,2,2024-11-02,2024-11-06,2024-11-06
204,Implement refund API endpoint,in_progress,P1,alice,payments,5,2024-11-04,2024-11-13,
205,Add payment retry logic,in_progress,P1,bob,payments,3,2024-11-05,2024-11-13,
206,Integrate with accounting system,blocked,P0,carol,payments,8,2024-11-02,2024-11-13,
207,Add payment analytics dashboard,todo,P2,unassigned,payments,5,2024-11-06,2024-11-06,
208,Support Apple Pay,todo,P3,unassigned,payments,8,2024-11-06,2024-11-06,
EOF

echo "Sprint 47 export created at /tmp/wicked-delivery-sprint/sprint-47.csv"
```

**Without the CSV**: The report command also works with verbal sprint descriptions provided inline as context — but the CSV path gives deterministic, data-driven output.

## Steps

### 1. Run Sprint Health Check

Generate a health report for the sprint:

```
/wicked-delivery:report /tmp/wicked-delivery-sprint/sprint-47.csv
```

**Expected Output** — Delivery Lead perspective should surface:
- Sprint status: 3 done, 2 in-progress, 1 blocked, 2 todo (8 total)
- Completion rate: 37% (3/8 tasks)
- P0 blocked task: "Integrate with accounting system"
- Velocity assessment: below target with P0 blocker unresolved
- Trend: AT RISK

**Engineering Lead perspective should surface**:
- Two in-progress tasks approaching sprint end — capacity concern
- P0 block creates downstream risk for payment reconciliation features
- Unassigned backlog items will not fit in sprint at current pace

**Product Lead perspective should surface**:
- Core payment refactor features (webhook, validation, email) delivered
- P0 accounting integration blocked — impacts product milestone
- Apple Pay and analytics dashboard are stretch goals, safe to defer

### 2. Identify Blockers and Escalation Paths

Run the risk-monitor agent for delivery risk analysis:

```
Task tool: subagent_type="wicked-delivery:risk-monitor"
prompt="Analyze delivery risks for Sprint 47 - Payment Refactor. The sprint has 8 tasks: 3 done, 2 in-progress, 1 blocked (P0: accounting integration waiting on Finance team credentials), 2 in backlog. Sprint ends in 2 days."
```

**Expected Output**:
- Risk matrix with the P0 block categorized as HIGH likelihood + HIGH impact = P0 priority
- Escalation trigger: P0 unmitigated, requires immediate action
- Dependency identified: external team (Finance) on critical path
- Mitigation recommendation: escalate credentials request, parallel work on non-blocked tasks
- Suggested re-scoping: move Apple Pay (P3) to next sprint

### 3. Generate a Stakeholder-Ready Report

Save the report for sharing with a team lead:

```
/wicked-delivery:report /tmp/wicked-delivery-sprint/sprint-47.csv --output /tmp/wicked-delivery-sprint/reports/
```

**Expected Output**:
- Report files written to output directory
- One file per persona (delivery-lead.md, engineering-lead.md, product-lead.md)
- Manifest listing generated reports with file paths
- Reports formatted in professional markdown suitable for sharing

### 4. Run Full Six-Persona Analysis

For steering committee or skip-level reporting, get all perspectives:

```
/wicked-delivery:report /tmp/wicked-delivery-sprint/sprint-47.csv --all
```

**Additional perspectives**:
- QE Lead: limited test data visible in export (opportunity to flag coverage gaps)
- Architecture Lead: payment integration complexity and external API dependency surface as architectural risk
- DevSecOps Lead: Stripe webhook handler and external auth credentials flow are relevant concerns

## Expected Outcome

- Sprint health communicated with multi-perspective analysis from a single data file
- Blocked P0 task surfaced prominently across delivery and engineering perspectives
- Velocity and completion rate calculated from task data
- Risk-monitor agent provides escalation guidance when invoked directly
- Stakeholder-ready report written to output directory
- Integration with wicked-mem (if available) stores sprint insights for trend analysis

## Success Criteria

- [ ] `/wicked-delivery:report` processes sprint-47.csv without errors
- [ ] Delivery Lead report identifies P0 blocked task by name
- [ ] Completion rate (37%) correctly derived from task status counts
- [ ] Engineering Lead report flags capacity risk from in-progress tasks near sprint end
- [ ] Product Lead report identifies deferred backlog items (Apple Pay, analytics)
- [ ] Risk-monitor agent generates risk matrix with P0 priority for accounting integration block
- [ ] Risk-monitor recommends escalation path for external dependency
- [ ] `--output` flag writes per-persona report files and manifest
- [ ] `--all` flag generates six persona reports
- [ ] Report format is professional and shareable (clean markdown)

## Value Demonstrated

Engineering managers spend significant time compiling sprint metrics manually — pulling data from Jira, calculating velocity in spreadsheets, chasing down blockers through Slack. wicked-delivery's report command replaces this with:

1. **Instant multi-perspective analysis** — Delivery, Engineering, and Product leads each see what matters to them, generated from one data file
2. **Blocker surfacing** — P0 blocks appear prominently without hunting through every ticket
3. **Stakeholder-ready output** — Professional markdown reports ready to drop into a Slack thread or steering committee doc
4. **Risk-monitor integration** — The risk-monitor agent adds escalation guidance and dependency chain analysis on top of the report data

The combination of `/wicked-delivery:report` for data-driven analysis and the `risk-monitor` agent for escalation logic turns reactive firefighting ("why is this late?") into proactive delivery management.

## Integration Notes

**With wicked-mem**: Stores sprint snapshots for velocity trend analysis across sprints
**With wicked-kanban**: Live task data feeds the report instead of a static CSV export
**Standalone**: Works with any CSV export from Jira, GitHub Issues, Linear, or Azure DevOps

## Cleanup

```bash
rm -rf /tmp/wicked-delivery-sprint
```
