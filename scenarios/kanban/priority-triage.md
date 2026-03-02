---
name: priority-triage
title: Priority-Based Triage
description: Use priority levels to manage urgent work and plan capacity
type: workflow
difficulty: intermediate
estimated_minutes: 5
---

# Priority-Based Triage

Test using priority levels (P0-P3) to triage incoming work and manage urgent issues.

## Setup

Simulate a realistic scenario where urgent production issues arrive while planned work is in progress.

```
/wicked-garden:kanban:new-task "Add dark mode support" --project "Sprint 3 - January" --priority P2
/wicked-garden:kanban:new-task "Improve search performance" --project "Sprint 3 - January" --priority P2
/wicked-garden:kanban:new-task "Update documentation" --project "Sprint 3 - January" --priority P3
```

Start work on the dark mode task using `TaskUpdate` (status: `in_progress`).

## Steps

1. **Production issue arrives - create P0 critical task**
   ```
   /wicked-garden:kanban:new-task "FIX: Authentication service down" --project "Sprint 3 - January" --priority P0
   ```
   Add context via comment:
   ```
   /wicked-garden:kanban:comment PROJECT_ID P0_TASK_ID "Error logs show database connection timeout - users getting 503 errors on login"
   ```

2. **Drop everything for P0 - pause current work**
   Use `TaskUpdate` to move the dark mode task back to `pending` and add a comment:
   ```
   /wicked-garden:kanban:comment PROJECT_ID DARK_MODE_TASK_ID "Paused for P0 production issue"
   ```
   Then use `TaskUpdate` to move the P0 task to `in_progress`.

3. **Resolve P0 issue**
   Add a comment documenting the fix:
   ```
   /wicked-garden:kanban:comment PROJECT_ID P0_TASK_ID "Increased connection pool size and restarted service. Monitoring for stability."
   ```
   Use `TaskUpdate` to mark the P0 task as `completed`.

4. **New P1 high-priority request arrives**
   ```
   /wicked-garden:kanban:new-task "Add enterprise SSO support" --project "Sprint 3 - January" --priority P1
   ```
   ```
   /wicked-garden:kanban:comment PROJECT_ID P1_TASK_ID "Customer contract depends on this - needed by end of sprint"
   ```

5. **Review the board to assess priority landscape**
   ```
   /wicked-garden:kanban:board-status
   ```
   The board should clearly show the priority distribution: P0 resolved, P1 tasks queued, P2/P3 in backlog.

## Expected Outcomes

- P0 task is immediately identifiable as critical on the board
- Current work can be paused (moved back to pending) to address emergencies
- P1 tasks are clearly distinguished from P2/P3
- Comments document the rationale for priority decisions
- Board status provides a clear view of what needs attention first
- Completed P0 shows the team handled the incident

## Success Criteria

- [ ] P0 task created and visible with critical priority
- [ ] Current work paused to address P0 emergency
- [ ] P0 resolved and moved to done with fix documentation
- [ ] P1 task created with business context in comments
- [ ] Board status shows priority-organized task distribution
- [ ] Comments provide audit trail of triage decisions

## Value Demonstrated

Real-world development requires constant prioritization. Production incidents (P0) must interrupt planned work. Customer commitments (P1) take precedence over nice-to-haves (P3). Claude can help manage this dynamic prioritization, quickly identifying what's critical and adjusting plans as urgency shifts. The kanban structure with priorities makes it immediately clear what needs attention first.
