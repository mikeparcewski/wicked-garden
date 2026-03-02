---
name: collaboration
title: Human-Claude Collaboration
description: Human and Claude collaborate through shared kanban state
type: integration
difficulty: basic
estimated_minutes: 5
---

# Human-Claude Collaboration

Test that humans and Claude can collaborate on the same kanban board through the shared Control Plane.

## Setup

Understand that wicked-kanban data is served by the Control Plane (CP), which allows both humans (via the CP dashboard) and Claude (via slash commands and native task tools) to access the same data.

Verify the CP is accessible:
```
/wicked-garden:kanban:start-api
```

## Steps

1. **Claude creates a project with tasks**
   ```
   /wicked-garden:kanban:new-task "Implement feature A" --project "Shared Work" --priority P1
   /wicked-garden:kanban:new-task "Write documentation" --project "Shared Work" --priority P2
   ```

2. **Verify tasks appear on the board**
   ```
   /wicked-garden:kanban:board-status
   ```
   Both tasks should appear under the "Shared Work" project in the "To Do" swimlane.

3. **Claude adds context for human collaborators**
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID_1 "Started implementation, estimated 2 hours. Using the adapter pattern for extensibility."
   ```

4. **Human can access the same board via CP dashboard**
   The Control Plane serves the board at `http://localhost:18889`. Humans can:
   - View the board visually in their browser
   - See task status, comments, and activity
   - Update tasks through the dashboard interface

5. **Simulate human updating a task**
   In a real scenario, a human would use the CP dashboard. For this test, use the slash command to simulate:
   Use `TaskUpdate` to move the first task to `in_progress`.

6. **Claude sees the updated status**
   ```
   /wicked-garden:kanban:board-status
   ```
   The board should reflect the status change, showing the task in "In Progress".

7. **Claude completes work and documents it**
   Use `TaskUpdate` to mark the task as `completed`, then add a comment:
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID_1 "Implementation complete - PR #42 ready for review"
   ```

8. **Final board state shows collaboration**
   ```
   /wicked-garden:kanban:board-status
   ```
   Board shows 1 task done, 1 in To Do, with comments from both "human" and Claude interactions.

## Expected Outcomes

- Both human and Claude can create, view, and modify the same board
- Changes made by either party are visible to the other via board-status
- Comments provide context for collaborators
- The Control Plane serves as the single source of truth
- No conflicts or data corruption when both access the board

## Success Criteria

- [ ] Tasks created via slash commands are visible on the board
- [ ] Board status reflects changes from all parties
- [ ] Comments provide collaboration context
- [ ] CP dashboard is accessible for human interaction
- [ ] Status changes sync correctly between interfaces

## Value Demonstrated

The Control Plane architecture allows humans and Claude to collaborate naturally. Humans can use the CP dashboard for visual interaction while Claude uses efficient slash commands and native task tools. Both see the same state because the CP is the single source of truth. This enables workflows where Claude does the heavy lifting while humans review and adjust priorities.
