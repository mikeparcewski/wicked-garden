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

```bash
# Create a project for current sprint
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Sprint 3 - January" -d "Planned work for January sprint"
# Note PROJECT_ID from output

# Add planned P2 (normal) work
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Add dark mode support" -p P2 -d "User-requested feature"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Improve search performance" -p P2 -d "Search taking >2s on large datasets"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Update documentation" -p P3 -d "API docs are outdated"
# Note DARK_MODE_TASK_ID, SEARCH_TASK_ID, DOCS_TASK_ID

# Start work on planned items
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID DARK_MODE_TASK_ID --swimlane in_progress
```

## Steps

1. **Production issue arrives - create P0 critical task**
   ```bash
   # Critical: Users can't log in
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "FIX: Authentication service down" -p P0 -d "Users getting 503 errors on login - production issue"
   # Note P0_TASK_ID

   # Add context
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID P0_TASK_ID "Error logs show database connection timeout"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-artifact PROJECT_ID P0_TASK_ID "Error logs" --type file --path "/var/log/auth-service.log"
   ```

2. **Immediately move P0 to In Progress (drop everything else)**
   ```bash
   # Move current work back to To Do
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID DARK_MODE_TASK_ID --swimlane todo
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID DARK_MODE_TASK_ID "Paused for P0 production issue"

   # Start P0 work
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID P0_TASK_ID --swimlane in_progress
   ```

3. **Resolve P0 issue**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID P0_TASK_ID "hotfix-abc123"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID P0_TASK_ID "Increased connection pool size and restarted service. Monitoring for stability."
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID P0_TASK_ID --swimlane done
   ```

4. **New P1 high-priority request arrives**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID "Add enterprise SSO support" -p P1 -d "New enterprise customer needs SAML authentication"
   # Note P1_TASK_ID
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID P1_TASK_ID "Customer contract depends on this - needed by end of sprint"
   ```

5. **Re-prioritize existing work**
   ```bash
   # Bump search performance to P1 (it affects the customer too)
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID SEARCH_TASK_ID --priority P1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID SEARCH_TASK_ID "Enterprise customer has large datasets - making this P1"

   # Lower dark mode to P3 (can wait)
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID DARK_MODE_TASK_ID --priority P3
   ```

6. **View prioritized work list**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID
   ```
   Observe tasks are organized by swimlane. P0/P1 tasks should be addressed first.

7. **Search for high-priority work**
   ```bash
   # Find all P0 and P1 mentions in comments
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "P0"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "P1"
   ```

## Expected Outcome

- P0 tasks are immediately identifiable as critical
- Team can quickly drop current work to address emergencies
- P1 tasks are prioritized over P2/P3
- Priority changes are reflected immediately
- Comments document priority rationale
- Work can be re-prioritized as needs change

## Success Criteria

- [ ] P0 task created and immediately visible as critical
- [ ] Current work can be paused (moved back to To Do) for P0
- [ ] P1 tasks are clearly distinguished from P2/P3
- [ ] Priorities can be changed on existing tasks
- [ ] Comments document priority decisions
- [ ] Project view shows tasks organized by swimlane

## Value Demonstrated

Real-world development requires constant prioritization. Production incidents (P0) must interrupt planned work. Customer commitments (P1) take precedence over nice-to-haves (P3). Claude can help manage this dynamic prioritization, quickly identifying what's critical and adjusting plans as urgency shifts. The kanban structure with priorities makes it immediately clear what needs attention first.
