---
name: initiative-planning
title: Initiative Planning
description: Claude helps plan and execute a time-boxed initiative
type: workflow
difficulty: intermediate
estimated_minutes: 7
---

# Initiative Planning

Test initiative creation and management for time-boxed work.

## Setup

Create a project with several tasks ready for initiative assignment.

```bash
# Create project
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-project "Q1 Features" -d "First quarter development"
# Note PROJECT_ID from output
```

## Steps

1. **Add several tasks to the backlog**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "User dashboard" -p P1 -d "Interactive dashboard for user metrics"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "API rate limiting" -p P1 -d "Implement rate limiting middleware"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Email notifications" -p P2 -d "Send email alerts for important events"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Analytics dashboard" -p P2 -d "Admin dashboard for analytics"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-task PROJECT_ID "Mobile responsive" -p P3 -d "Make UI responsive for mobile devices"
   # Note DASHBOARD_TASK_ID, RATE_LIMIT_TASK_ID, EMAIL_TASK_ID, ANALYTICS_TASK_ID, MOBILE_TASK_ID
   ```

2. **Create an initiative for the next two weeks**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py create-initiative PROJECT_ID "Initiative 1" \
     --start 2024-01-15 --end 2024-01-29 \
     --goal "Complete core dashboard features"
   # Note INITIATIVE_ID from output
   ```

3. **List initiatives to verify creation**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-initiatives PROJECT_ID
   ```
   Initiative should be in "planning" status.

4. **Assign high-priority tasks to the initiative**
   ```bash
   # Assign dashboard task to the initiative
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID DASHBOARD_TASK_ID --initiative INITIATIVE_ID

   # Assign rate limiting task to the initiative
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID RATE_LIMIT_TASK_ID --initiative INITIATIVE_ID
   ```

5. **Verify tasks are assigned to initiative**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-tasks PROJECT_ID --initiative INITIATIVE_ID
   ```
   Should show only the two tasks assigned to the initiative.

6. **Activate the initiative**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-initiative PROJECT_ID INITIATIVE_ID --status active
   ```

7. **Work through initiative tasks**
   ```bash
   # Start first task
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID DASHBOARD_TASK_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-comment PROJECT_ID DASHBOARD_TASK_ID "Implementing chart components"

   # Complete it
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-commit PROJECT_ID DASHBOARD_TASK_ID "abc123"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID DASHBOARD_TASK_ID --swimlane done

   # Work on second task
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID RATE_LIMIT_TASK_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-commit PROJECT_ID RATE_LIMIT_TASK_ID "def456"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-task PROJECT_ID RATE_LIMIT_TASK_ID --swimlane done
   ```

8. **Complete the initiative**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py update-initiative PROJECT_ID INITIATIVE_ID --status completed
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py add-project-comment PROJECT_ID "Initiative 1 complete: Delivered dashboard and rate limiting"
   ```

9. **List initiatives to see history**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py list-initiatives PROJECT_ID
   ```
   Should show Initiative 1 with "completed" status.

10. **Get initiative details**
    ```bash
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban/kanban.py get-initiative PROJECT_ID INITIATIVE_ID
    ```
    Should show initiative with goal, dates, and status.

## Expected Outcome

- Initiative created with goal and dates
- Tasks can be assigned to initiatives via CLI
- Initiative moves through statuses: planning -> active -> completed
- Initiative provides time-boxed focus for work
- Initiative history is preserved for retrospectives

## Success Criteria

- [ ] Initiative created with start/end dates and goal
- [ ] Initiative starts in "planning" status
- [ ] Tasks can be assigned to initiative via `--initiative` flag
- [ ] Tasks can be listed by initiative with `--initiative` filter
- [ ] Initiative status updates correctly (planning -> active -> completed)
- [ ] Multiple initiatives can exist in a project
- [ ] Initiative list shows all initiatives with their statuses
- [ ] Completed initiative preserves history for retrospectives

## Value Demonstrated

Time-boxed initiatives help organize work into focused iterations with clear goals. Claude can help plan initiatives, assign tasks, and track progress against initiative goals entirely through the CLI.
