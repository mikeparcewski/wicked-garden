---
name: multi-project-coordination
title: Multi-Project Coordination
description: Coordinate work across multiple projects with cross-project dependencies
type: workflow
difficulty: advanced
estimated_minutes: 8
---

# Multi-Project Coordination

Test managing multiple related projects with dependencies between them, simulating a microservices architecture or multi-team coordination.

## Setup

Create multiple projects representing different components of a system that need to be coordinated.

```
/wicked-garden:kanban:new-task "Implement JWT token generation" --project "Auth Service" --priority P0
/wicked-garden:kanban:new-task "Add token validation endpoint" --project "Auth Service" --priority P0
```

This automatically creates the "Auth Service" project with two foundational tasks.

## Steps

1. **Create tasks across multiple projects**
   ```
   /wicked-garden:kanban:new-task "User profile endpoints" --project "User Service" --priority P1
   /wicked-garden:kanban:new-task "User preferences API" --project "User Service" --priority P2
   ```
   ```
   /wicked-garden:kanban:new-task "Route /auth requests" --project "API Gateway" --priority P1
   /wicked-garden:kanban:new-task "Implement auth middleware" --project "API Gateway" --priority P0
   /wicked-garden:kanban:new-task "Route /users requests" --project "API Gateway" --priority P1
   ```
   ```
   /wicked-garden:kanban:new-task "Login page" --project "Frontend App" --priority P1
   /wicked-garden:kanban:new-task "User profile page" --project "Frontend App" --priority P1
   ```

2. **Document cross-project dependencies with comments**
   ```
   /wicked-garden:kanban:comment USER_PROJECT_ID PROFILE_TASK_ID "BLOCKED: Waiting for Auth Service JWT validation"
   /wicked-garden:kanban:comment GATEWAY_PROJECT_ID MIDDLEWARE_TASK_ID "BLOCKED: Needs Auth Service JWT validation endpoint"
   /wicked-garden:kanban:comment FRONTEND_PROJECT_ID LOGIN_TASK_ID "BLOCKED: Needs Gateway /auth route"
   ```

3. **View the full board to understand the dependency landscape**
   ```
   /wicked-garden:kanban:board-status
   ```
   Should show 4 projects with tasks in their respective To Do swimlanes.

4. **Complete Auth Service foundation first**
   Use `TaskUpdate` to start and complete the Auth Service tasks:
   - Move JWT token generation to `in_progress`, then `completed`
   - Move token validation to `in_progress`, then `completed`

   Notify dependent projects:
   ```
   /wicked-garden:kanban:comment USER_PROJECT_ID PROFILE_TASK_ID "UNBLOCKED: Auth Service JWT validation complete"
   /wicked-garden:kanban:comment GATEWAY_PROJECT_ID MIDDLEWARE_TASK_ID "UNBLOCKED: Auth Service JWT validation complete"
   ```

5. **Parallel work on User Service and Gateway (now unblocked)**
   Use `TaskUpdate` to start and complete tasks in parallel:
   - User Service: profile endpoints to `in_progress`, then `completed`
   - Gateway: auth middleware to `in_progress`, then `completed`
   - Gateway: /users route to `in_progress`, then `completed`

   Notify frontend:
   ```
   /wicked-garden:kanban:comment FRONTEND_PROJECT_ID LOGIN_TASK_ID "UNBLOCKED: Gateway auth route complete"
   ```

6. **Frontend can now proceed**
   Use `TaskUpdate` to start and complete the login page task.

7. **Review cross-project progress**
   ```
   /wicked-garden:kanban:board-status
   ```
   Should show Auth Service fully complete, Gateway mostly complete, User Service partially complete, Frontend in progress.

## Expected Outcomes

- Multiple projects are managed simultaneously on the same board
- Cross-project dependencies are documented via BLOCKED/UNBLOCKED comments
- Work proceeds in correct dependency order (auth -> services -> gateway -> frontend)
- Board status shows progress across all projects at a glance
- Comments provide a coordination mechanism across project boundaries
- Each project maintains its own task backlog and progress

## Success Criteria

- [ ] Four projects created and visible on the board
- [ ] Cross-project dependencies documented in comments
- [ ] Tasks completed in correct dependency order
- [ ] BLOCKED/UNBLOCKED comments track coordination state
- [ ] Board status shows all projects with accurate swimlane counts
- [ ] Parallel work on unblocked projects proceeds correctly

## Value Demonstrated

Real software systems involve multiple coordinated components. When building microservices, frontend/backend splits, or coordinating across teams, work often depends on tasks in other projects. Wicked Kanban allows Claude to manage all these projects in one place, track dependencies through comments, and provide a unified board view of complex, multi-component development efforts. This coordination is impossible with per-session TodoWrite tasks.
