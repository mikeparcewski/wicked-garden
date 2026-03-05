---
name: multi-project-management
title: Multiple Concurrent Projects
description: Manage multiple projects simultaneously with independent contexts
type: workflow
difficulty: basic
estimated_minutes: 8
---

# Multiple Concurrent Projects

This scenario validates that wicked-crew can manage multiple projects concurrently without context leakage or state confusion.

## Setup

Create three different project scenarios representing common real-world situations:

```bash
# Project 1: Frontend feature
mkdir -p ~/test-wicked-crew/multi-project/web-app
cd ~/test-wicked-crew/multi-project/web-app
cat > App.jsx <<'EOF'
import React from 'react';
export default function App() {
  return <div>Welcome</div>;
}
EOF

# Project 2: Backend bug fix
mkdir -p ~/test-wicked-crew/multi-project/api-service
cd ~/test-wicked-crew/multi-project/api-service
cat > api.py <<'EOF'
from flask import Flask
app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'ok'}
EOF

# Project 3: Database migration
mkdir -p ~/test-wicked-crew/multi-project/db-schema
cd ~/test-wicked-crew/multi-project/db-schema
cat > schema.sql <<'EOF'
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE
);
EOF
```

## Steps

### 1. Start Three Projects

```bash
# Start project 1
cd ~/test-wicked-crew/multi-project/web-app
/wicked-garden:crew:start "Add dark mode toggle to React app"
```

Note the project directory created: `~/.something-wicked/wicked-garden/local/wicked-crew/projects/add-dark-mode-toggle/`

```bash
# Start project 2 (different working directory)
cd ~/test-wicked-crew/multi-project/api-service
/wicked-garden:crew:start "Fix 500 error on /health endpoint when database is down"
```

Note second project: `~/.something-wicked/wicked-garden/local/wicked-crew/projects/fix-500-error-on-health/`

```bash
# Start project 3 (different working directory)
cd ~/test-wicked-crew/multi-project/db-schema
/wicked-garden:crew:start "Add user roles and permissions to database schema"
```

Note third project: `~/.something-wicked/wicked-garden/local/wicked-crew/projects/add-user-roles-and-permissions/`

### 2. Work on Projects in Mixed Order

**Work on project 1** (CWD is web-app, so it's the active project):
```bash
/wicked-garden:crew:execute  # clarify phase for project 1
```

Expected: Discusses dark mode toggle (React context) — project 1 is active because the current working directory is `~/test-wicked-crew/multi-project/web-app` where it was started.

**Advance project 1**:
```bash
/wicked-garden:crew:approve clarify
/wicked-garden:crew:execute  # design phase for project 1
```

Expected: Design for dark mode (CSS variables, localStorage)

**Note on project switching**: The active project is determined by the current working directory (CWD). When you run `/wicked-garden:crew:execute` or `/wicked-garden:crew:status`, it operates on the project whose workspace matches the CWD. To switch to a different project, change to the directory where that project was started.

### 3. Verify Independent State

Check that each project maintains independent state:

```bash
cd ~/test-wicked-crew/multi-project/web-app
/wicked-garden:crew:status
```

**Expected output**:
```
Project: add-dark-mode-toggle
Phase: design
Status: in-progress
Last Updated: [timestamp]

Deliverables:
  ✓ phases/clarify/objective.md
  ⧗ phases/design/architecture.md (in progress)
```

**Note**: The active project is determined by the current working directory (CWD). Run `/wicked-garden:crew:status` from `~/test-wicked-crew/multi-project/web-app` to see project 1's status.

### 4. Complete One Project While Others Remain Active

Complete project 2 (smallest scope). Navigate to the api-service directory so project 2 becomes the active project:

```bash
/wicked-garden:crew:approve clarify
/wicked-garden:crew:execute  # design
/wicked-garden:crew:approve design
/wicked-garden:crew:execute  # test-strategy
/wicked-garden:crew:approve test-strategy
/wicked-garden:crew:execute  # build
/wicked-garden:crew:approve build
/wicked-garden:crew:execute  # review
/wicked-garden:crew:approve review
```

**Expected**: Project 2 completes successfully

**Verify other projects unaffected**:
```bash
/wicked-garden:crew:status
```

Expected: Shows project 2 as completed (CWD is still api-service). Other projects remain at their previous phases when checked from their respective directories.

```bash
cd ~/test-wicked-crew/multi-project/db-schema
/wicked-garden:crew:status
```

Expected: Still in clarify phase (unchanged)

### 5. Check All Project States

List all projects using the filesystem (no dedicated list command):

```bash
ls -lt ~/.something-wicked/wicked-garden/local/wicked-crew/projects/ | head -10
```

Then check each project status:

```bash
/wicked-garden:crew:status
```

**Expected**: Shows the project matching the current working directory. To check a specific project, navigate to its associated working directory and run status.

## Expected Outcome

- Multiple projects coexist without interference
- Each project maintains independent state (phase, deliverables, context)
- Active project is determined by current working directory (CWD-based selection)
- Status command shows the project for the current working directory
- Completing one project doesn't affect others
- All project data persists independently

## Success Criteria

### Project Isolation
- [ ] Three projects created with unique names/slugs
- [ ] Each project has separate directory in `~/.something-wicked/wicked-garden/local/wicked-crew/projects/`
- [ ] Active project resolved from current working directory (CWD-based)
- [ ] No cross-contamination of deliverables between projects

### State Persistence
- [ ] Each project tracks phase independently
- [ ] Deliverables stored in correct project directory
- [ ] Status command shows project for current working directory
- [ ] Project state persists across sessions

### Context Switching
- [ ] Can work on project 1, switch to project 2, return to project 1
- [ ] Switching CWD changes the active project
- [ ] Execute command operates on project for current working directory

### Completion Independence
- [ ] Completing project 2 doesn't affect project 1 or 3
- [ ] Completed projects still visible in list
- [ ] Active projects continue normally after another completes

### Project Listing
- [ ] All projects visible via filesystem listing of `~/.something-wicked/wicked-garden/local/wicked-crew/projects/`
- [ ] Status command shows current active project
- [ ] Completed projects remain in project directory

## Value Demonstrated

**Real-world value**: Developers rarely work on just one thing at a time. A typical day might involve:
- Feature work on project A
- Bug fix on project B (urgent interruption)
- Code review on project C
- Back to feature work on project A

Traditional project management tools force you to "close" one project before opening another, or they mix all tasks together into one list. wicked-crew's CWD-based project detection means the project in your current workspace is always the active one — matching how developers naturally switch between directories.

The independent state management prevents common mistakes:
- Running design phase on wrong project
- Approving the wrong phase because you forgot which project is active
- Losing track of where each project stands

Each project is fully independent with its own state in `~/.something-wicked/wicked-garden/local/wicked-crew/projects/`. The CWD-based selection ensures you're always working on the project that belongs to your current workspace.

For teams, this means pair programming doesn't require syncing project state. Each developer can work on their own projects, and collaboration happens at the artifact level (reviewing the generated designs, test scenarios, etc.) rather than at the state level.

The status command provides a quick view of the current active project, and filesystem listing gives an overview of all in-flight work, helping with daily standup updates and context switching decisions.

## Cleanup

```bash
/wicked-garden:crew:archive add-dark-mode-toggle
/wicked-garden:crew:archive fix-500-error-on-health
/wicked-garden:crew:archive add-user-roles-and-permissions
rm -rf ~/test-wicked-crew/multi-project
```
