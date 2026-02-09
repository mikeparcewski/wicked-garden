---
name: sprint-health-check
title: Sprint Health Check
description: Track delivery metrics, identify blockers, and assess sprint health
type: workflow
difficulty: basic
estimated_minutes: 6
---

# Sprint Health Check

This scenario validates that wicked-delivery can effectively track sprint progress, calculate velocity, identify blockers, and provide actionable delivery insights for engineering managers and tech leads.

## Setup

This scenario works best with wicked-kanban installed to provide real task data. Create a sprint board with realistic task distribution:

```bash
# Ensure wicked-kanban is available
# If using wicked-kanban, create test data:

# Create project for sprint
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-project "Sprint 47 - Payment Refactor" \
  -d "Q1 payment system improvements"

# Note the PROJECT_ID from output, then create tasks with mixed states
PROJECT_ID="<use_actual_id>"

# Completed tasks (velocity contributors)
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Implement Stripe webhook handler" -p P1 -d "Handle payment_intent.succeeded events"
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Add payment method validation" -p P1 -d "Validate card details before charge"
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Update payment confirmation email" -p P2 -d "Include receipt URL in email"

# Move completed tasks to done
# (use actual task IDs from output)

# In-progress tasks
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Implement refund API endpoint" -p P1 -d "POST /payments/{id}/refund"
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Add payment retry logic" -p P1 -d "Exponential backoff for failed charges"

# Blocked task (critical for blocker detection)
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Integrate with accounting system" -p P0 -d "BLOCKED: Waiting for accounting API credentials from Finance team"

# Backlog tasks
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Add payment analytics dashboard" -p P2 -d "Track conversion rates and failure reasons"
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py create-task $PROJECT_ID \
  "Support Apple Pay" -p P3 -d "Add Apple Pay as payment option"
```

**Without wicked-kanban**: The delivery-manager agent will use any available project management data or work with verbal descriptions of sprint status.

## Steps

### 1. Run Sprint Health Check

Invoke the delivery manager to assess current sprint:

```
Task tool: subagent_type="wicked-delivery:delivery-manager"
prompt="Give me a health check on our current sprint for the payment refactor project"
```

**Expected Output**:
- Sprint status summary (X tasks completed, Y in progress, Z blocked)
- Velocity assessment (current vs target)
- Completion rate percentage
- Trend analysis (on track/at risk)

### 2. Identify Blockers

Ask specifically about blockers:

```
Task tool: subagent_type="wicked-delivery:delivery-manager"
prompt="What blockers are slowing down our sprint? How long have they been blocked?"
```

**Expected Output**:
- List of blocked tasks with:
  - Task name and description
  - What it's blocked by
  - Duration blocked
  - Impact assessment (P0 = HIGH impact)
- Recommended escalation path
- Suggested unblocking actions

### 3. Analyze Velocity Trend

Request velocity analysis:

```
Task tool: subagent_type="wicked-delivery:progress-tracker"
prompt="What's our velocity trend? Are we speeding up or slowing down compared to previous sprints?"
```

**Expected Output**:
- Current sprint velocity
- Comparison to previous sprints (if wicked-mem has historical data)
- Velocity trend (increasing/stable/decreasing)
- Contributing factors (blockers, scope changes, team capacity)
- Forecast for sprint completion

### 4. Get Risk Assessment

Ask the risk monitor for potential issues:

```
Task tool: subagent_type="wicked-delivery:risk-monitor"
prompt="What delivery risks should I be aware of for this sprint?"
```

**Expected Output**:
- Identified risks with severity:
  - Blocker dependency on external team (HIGH)
  - In-progress tasks approaching sprint end (MEDIUM)
  - Scope of backlog tasks (LOW)
- Mitigation recommendations
- Escalation triggers

### 5. Generate Sprint Report

Request a formatted report for stakeholders:

```
Task tool: subagent_type="wicked-delivery:delivery-manager"
prompt="Generate a sprint report I can share with my team lead"
```

**Expected Output**:
```markdown
## Sprint Health Check

**Sprint**: Payment Refactor (Sprint 47)
**Date**: {date}
**Status**: AT RISK

### Summary
- Total tasks: 8
- Completed: 3 (38%)
- In Progress: 2 (25%)
- Blocked: 1 (13%)
- Backlog: 2 (25%)

### Velocity
- Current: 3 tasks completed
- Target: 5 tasks
- Trend: Below target

### Critical Issues
1. P0 task blocked: "Integrate with accounting system"
   - Blocked by: External dependency (Finance team)
   - Duration: 3+ days
   - Impact: Blocks payment reconciliation feature

### Recommendations
1. Escalate accounting API credentials request
2. Consider parallel work on non-blocked tasks
3. Re-prioritize Apple Pay to future sprint
```

## Expected Outcome

- Sprint health clearly communicated with actionable metrics
- Blockers identified with duration and impact
- Velocity compared against targets and historical trends
- Risks categorized by severity with mitigation steps
- Stakeholder-ready report generated
- Integration with wicked-kanban provides real task data (when available)

## Success Criteria

- [ ] Sprint status includes task counts by state (completed, in-progress, blocked, backlog)
- [ ] Completion percentage calculated correctly
- [ ] Blocker identified with specific task name and blocking reason
- [ ] Blocker duration tracked (how long blocked)
- [ ] Impact assessment provided for blockers (HIGH/MEDIUM/LOW)
- [ ] Velocity compared to target
- [ ] Trend analysis provided (on track/at risk)
- [ ] Recommendations are actionable (specific next steps)
- [ ] Report format is stakeholder-appropriate (can share with manager)
- [ ] If wicked-kanban available: uses real task data from board

## Value Demonstrated

**Real-world value**: Engineering managers spend significant time compiling sprint metrics manually - pulling data from Jira, calculating velocity in spreadsheets, chasing down blockers through Slack conversations. This context-switching and manual aggregation is time-consuming and error-prone.

wicked-delivery's PMO capabilities provide:

1. **Instant visibility**: Sprint health at a glance without manual data collection
2. **Proactive blocker detection**: Identifies stuck work before it derails the sprint
3. **Historical context**: With wicked-mem, velocity trends span multiple sprints
4. **Stakeholder communication**: Pre-formatted reports save prep time for standups and skip-levels
5. **Escalation triggers**: Clear thresholds for when to raise issues

For teams practicing Agile/Scrum, these capabilities turn reactive firefighting ("why is this late?") into proactive management ("we detected a blocker 2 days ago"). The delivery-manager agent surfaces the information that experienced engineering managers know to look for, but does it consistently and without manual overhead.

## Integration Notes

**With wicked-kanban**: Pulls real task data, calculates actual metrics
**With wicked-mem**: Recalls historical velocity for trend analysis
**With wicked-search**: Finds related blockers and dependencies across codebase
**Standalone**: Works with verbal descriptions, but metrics are estimates

## Cleanup

```bash
# If using wicked-kanban, delete test project
python3 ~/.claude/plugins/wicked-kanban/scripts/kanban.py delete-project $PROJECT_ID
```
