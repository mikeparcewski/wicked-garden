---
name: artifacts-and-commits
title: Linking Code and Documentation
description: Attach commits and documentation references to tasks for traceability
type: feature
difficulty: intermediate
estimated_minutes: 6
---

# Linking Code and Documentation

Test attaching commits and documentation references to tasks to maintain traceability between work and implementation.

## Setup

No special setup needed beyond an active wicked-garden session with a git repository.

## Steps

1. **Create tasks for a feature**
   ```
   /wicked-garden:kanban:new-task "Add profile API endpoints" --project "User Profile Feature" --priority P1
   /wicked-garden:kanban:new-task "Frontend profile component" --project "User Profile Feature" --priority P1
   /wicked-garden:kanban:new-task "Profile image upload" --project "User Profile Feature" --priority P2
   ```

2. **Start work on the API task**
   Use `TaskUpdate` to move the first task to `in_progress`.

3. **Document design decisions via comments**
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID_1 "API design: REST endpoints for profile CRUD. Using OpenAPI spec at docs/api/profile.yaml"
   ```

4. **Complete the work and document the commit**
   After implementing the feature and committing the code, add a comment linking the work:
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID_1 "Implemented GET/POST/PUT/DELETE endpoints with validation. Commit: a1b2c3d4"
   ```
   Use `TaskUpdate` to mark as `completed`.

5. **Work on frontend task with iterative progress**
   Use `TaskUpdate` to start the second task (`in_progress`).
   Document progress with comments:
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID_2 "Initial component structure with React hooks. Commit: e5f6g7h8"
   ```
   ```
   /wicked-garden:kanban:comment PROJECT_ID TASK_ID_2 "Added form validation and API integration. Commit: i9j0k1l2"
   ```
   Use `TaskUpdate` to mark as `completed`.

6. **View the board to see traceability**
   ```
   /wicked-garden:kanban:board-status
   ```
   Board shows 2 tasks completed with documented commit references, 1 task remaining.

7. **Review task comments for audit trail**
   The comments on each completed task provide a full history of:
   - Design decisions
   - Implementation notes
   - Commit references
   - Progress narrative

## Expected Outcomes

- Tasks are created and tracked through the full lifecycle
- Comments document design decisions, implementation notes, and commit references
- Multiple progress updates are captured as the work evolves
- Board status shows which tasks have associated work
- Full traceability from task to implementation via comment history

## Success Criteria

- [ ] Tasks created with appropriate priorities
- [ ] Comments document design decisions before implementation
- [ ] Commit references linked to tasks via comments
- [ ] Multiple progress comments capture iterative work
- [ ] Board status shows completed tasks with documentation trail
- [ ] Comments provide narrative context connecting tasks to code changes

## Value Demonstrated

Maintaining traceability between tasks and code is essential for understanding why changes were made. Claude can document commits, design decisions, and progress in task comments during development, making it easy to understand the full context of any work item. This is especially valuable during code reviews, debugging, or onboarding new team members who need to understand the history behind the code.
