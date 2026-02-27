---
name: search-and-discovery
title: Search and Discovery
description: Search across projects to find tasks and track work
type: feature
difficulty: basic
estimated_minutes: 4
---

# Search and Discovery

Test the search functionality to find tasks across multiple projects.

## Setup

Create multiple projects with various tasks to demonstrate search capabilities.

```bash
# Create first project - Backend API
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Backend API" -d "REST API development"
# Note the project ID

# Get swimlane IDs
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID_1

# Add tasks
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_1 "Implement authentication endpoint" TODO_SWIMLANE -p P1 -d "OAuth2 implementation for user login"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_1 "Add rate limiting middleware" TODO_SWIMLANE -p P2 -d "Prevent API abuse with rate limits"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_1 "Database migration for users" TODO_SWIMLANE -p P0

# Create second project - Frontend
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-project "Frontend UI" -d "React dashboard"
# Note the project ID

# Get swimlane IDs
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py get-project PROJECT_ID_2

# Add tasks
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_2 "Build authentication UI" TODO_SWIMLANE -p P1 -d "Login form and OAuth flows"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_2 "User dashboard layout" TODO_SWIMLANE -p P2
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py create-task PROJECT_ID_2 "Error handling middleware" TODO_SWIMLANE -p P2
```

## Steps

1. **Search for tasks containing "authentication"**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "authentication"
   ```
   Should find tasks from both projects related to authentication.

2. **Search within a specific project**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "middleware" --project PROJECT_ID_1
   ```
   Should only find "Add rate limiting middleware" from Backend API project.

3. **Search by priority keyword**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "dashboard"
   ```
   Should find "User dashboard layout" task.

4. **Verify search matches task descriptions**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "OAuth"
   ```
   Should find tasks even when the search term is in the description, not just the title.

5. **Add a comment and search for it**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py add-comment PROJECT_ID_1 TASK_ID "Need to coordinate with frontend team on OAuth flow"
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py search "coordinate"
   ```
   Should find the task with the comment.

## Expected Outcome

- Search finds tasks across all projects by default
- `--project` flag limits search to specific project
- Search matches against task names, descriptions, and comments
- Search results show task ID, name, project, and current swimlane
- Results are useful for discovering related work

## Success Criteria

- [ ] Global search returns tasks from multiple projects
- [ ] Project-scoped search filters correctly
- [ ] Search matches task names and descriptions
- [ ] Search matches comments on tasks
- [ ] Search results include enough context (project name, swimlane)

## Value Demonstrated

When managing multiple projects or working on a large codebase, finding related tasks is critical. Claude can search across all work to discover dependencies, avoid duplicate effort, and coordinate related tasks even when they're in different projects.
