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

```bash
# Project 1: API Gateway
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "API Gateway" -d "Central API gateway service"
# Note PROJECT_ID_1 from output

# Project 2: Auth Service
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Auth Service" -d "Authentication microservice"
# Note PROJECT_ID_2 from output

# Project 3: User Service
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "User Service" -d "User management microservice"
# Note PROJECT_ID_3 from output

# Project 4: Frontend
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Frontend App" -d "React web application"
# Note PROJECT_ID_4 from output
```

## Steps

1. **Add foundational tasks to Auth Service (must be done first)**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_2 "Implement JWT token generation" -p P0 -d "Core auth functionality"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_2 "Add token validation endpoint" -p P0
   # Note AUTH_TASK_1_ID and AUTH_TASK_2_ID
   ```

2. **Add tasks to User Service that depend on Auth**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_3 "User profile endpoints" -p P1 -d "Requires auth token validation"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_3 "User preferences API" -p P2
   # Note USER_PROFILE_TASK_ID

   # Document cross-project dependency with comments
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_3 USER_PROFILE_TASK_ID "BLOCKED: Waiting for Auth Service JWT validation (Auth Service task: AUTH_TASK_2_ID)"
   ```

3. **Add tasks to API Gateway that depend on both services**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_1 "Route /auth requests" -p P1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_1 "Route /users requests" -p P1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_1 "Implement auth middleware" -p P0
   # Note AUTH_ROUTE_TASK_ID, USERS_ROUTE_TASK_ID, AUTH_MIDDLEWARE_TASK_ID

   # Document dependencies
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_1 AUTH_MIDDLEWARE_TASK_ID "BLOCKED: Needs Auth Service JWT validation endpoint"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_1 USERS_ROUTE_TASK_ID "BLOCKED: Needs User Service profile endpoints"
   ```

4. **Add tasks to Frontend that depend on Gateway**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_4 "Login page" -p P1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_4 "User profile page" -p P1
   # Note LOGIN_PAGE_TASK_ID

   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_4 LOGIN_PAGE_TASK_ID "BLOCKED: Needs Gateway /auth route"
   ```

5. **Work through the dependency chain**

   **Step 5a: Complete Auth Service foundation**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_2 AUTH_TASK_1_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID_2 AUTH_TASK_1_ID "commit-auth-1"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_2 AUTH_TASK_1_ID --swimlane done

   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_2 AUTH_TASK_2_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID_2 AUTH_TASK_2_ID "commit-auth-2"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_2 AUTH_TASK_2_ID --swimlane done

   # Notify dependent projects
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_3 USER_PROFILE_TASK_ID "UNBLOCKED: Auth Service JWT validation complete"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_1 AUTH_MIDDLEWARE_TASK_ID "UNBLOCKED: Auth Service JWT validation complete"
   ```

   **Step 5b: Parallel work on User Service and Gateway (now unblocked)**
   ```bash
   # User Service
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_3 USER_PROFILE_TASK_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID_3 USER_PROFILE_TASK_ID "commit-user-1"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_3 USER_PROFILE_TASK_ID --swimlane done

   # Gateway (auth middleware)
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_1 AUTH_MIDDLEWARE_TASK_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID_1 AUTH_MIDDLEWARE_TASK_ID "commit-gateway-1"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_1 AUTH_MIDDLEWARE_TASK_ID --swimlane done

   # Gateway routing can now proceed
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_1 USERS_ROUTE_TASK_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID_1 USERS_ROUTE_TASK_ID "commit-gateway-2"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_1 USERS_ROUTE_TASK_ID --swimlane done
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_4 LOGIN_PAGE_TASK_ID "UNBLOCKED: Gateway auth route complete"
   ```

   **Step 5c: Frontend can now proceed**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_4 LOGIN_PAGE_TASK_ID --swimlane in_progress
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-commit PROJECT_ID_4 LOGIN_PAGE_TASK_ID "commit-frontend-1"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py update-task PROJECT_ID_4 LOGIN_PAGE_TASK_ID --swimlane done
   ```

6. **Use search to track progress across projects**
   ```bash
   # Find all auth-related work
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "auth"

   # Find all blocked work
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "BLOCKED"

   # Find all unblocked work
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "UNBLOCKED"
   ```

7. **List all projects to see overall status**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py list-projects
   ```

8. **Get detailed view of each project**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID_1
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID_2
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID_3
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID_4
   ```
   Verify task progress across all projects.

## Expected Outcome

- Multiple projects can be managed simultaneously
- Cross-project dependencies are tracked via comments
- Work proceeds in correct order (auth -> services -> gateway -> frontend)
- Search helps find related work across projects
- Search finds BLOCKED and UNBLOCKED comments for coordination
- Comments provide coordination mechanism

## Success Criteria

- [ ] Four projects created and managed independently
- [ ] Cross-project dependencies documented in comments
- [ ] Tasks completed in correct dependency order
- [ ] Search finds related tasks across all projects
- [ ] Search finds BLOCKED/UNBLOCKED comments
- [ ] List-projects shows all active projects
- [ ] Comments on tasks reference work in other projects

## Value Demonstrated

Real software systems involve multiple coordinated components. When building microservices, frontend/backend splits, or coordinating across teams, work often depends on tasks in other projects. Wicked Kanban allows Claude to manage all these projects in one place, search across them, and track dependencies through comments. This provides a unified view of complex, multi-component development efforts that would be impossible with per-session TodoWrite tasks.
