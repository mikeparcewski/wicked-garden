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
/wicked-crew:start "Add dark mode toggle to React app"
```

Note the project directory created: `~/.something-wicked/wicked-crew/projects/add-dark-mode-toggle/`

```bash
# Start project 2 (different working directory)
cd ~/test-wicked-crew/multi-project/api-service
/wicked-crew:start "Fix 500 error on /health endpoint when database is down"
```

Note second project: `~/.something-wicked/wicked-crew/projects/fix-500-error-on-health/`

```bash
# Start project 3 (different working directory)
cd ~/test-wicked-crew/multi-project/db-schema
/wicked-crew:start "Add user roles and permissions to database schema"
```

Note third project: `~/.something-wicked/wicked-crew/projects/add-user-roles-and-permissions/`

### 2. Work on Projects in Mixed Order

**Work on project 1**:
```bash
cd ~/test-wicked-crew/multi-project/web-app
/wicked-crew:execute  # clarify phase
```

Expected: Discusses dark mode toggle (React context)

**Switch to project 2**:
```bash
cd ~/test-wicked-crew/multi-project/api-service
/wicked-crew:execute  # clarify phase
```

Expected: Discusses error handling (Python/Flask context), NOT dark mode

**Switch back to project 1**:
```bash
cd ~/test-wicked-crew/multi-project/web-app
/wicked-crew:status
```

Expected: Shows project 1 status (dark mode), still in clarify phase

**Advance project 1**:
```bash
/wicked-crew:approve clarify
/wicked-crew:execute  # design phase for project 1
```

Expected: Design for dark mode (CSS variables, localStorage), NOT error handling

**Work on project 3**:
```bash
cd ~/test-wicked-crew/multi-project/db-schema
/wicked-crew:execute  # clarify phase for project 3
```

Expected: Discusses roles/permissions schema, no mention of dark mode or error handling

### 3. Verify Independent State

Check that each project maintains independent state:

```bash
cd ~/test-wicked-crew/multi-project/web-app
/wicked-crew:status
```

**Expected output**:
```
Project: add-dark-mode-toggle
Working Directory: ~/test-wicked-crew/multi-project/web-app
Phase: design
Status: in-progress
Last Updated: [timestamp]

Deliverables:
  ✓ phases/clarify/objective.md
  ⧗ phases/design/architecture.md (in progress)
```

```bash
cd ~/test-wicked-crew/multi-project/api-service
/wicked-crew:status
```

**Expected output**:
```
Project: fix-500-error-on-health
Working Directory: ~/test-wicked-crew/multi-project/api-service
Phase: clarify
Status: in-progress
Last Updated: [timestamp]

Deliverables:
  ⧗ phases/clarify/objective.md (in progress)
```

```bash
cd ~/test-wicked-crew/multi-project/db-schema
/wicked-crew:status
```

**Expected output**:
```
Project: add-user-roles-and-permissions
Working Directory: ~/test-wicked-crew/multi-project/db-schema
Phase: clarify
Status: in-progress
Last Updated: [timestamp]

Deliverables:
  ⧗ phases/clarify/objective.md (in progress)
```

### 4. Complete One Project While Others Remain Active

Complete project 2 (smallest scope):

```bash
cd ~/test-wicked-crew/multi-project/api-service
/wicked-crew:approve clarify
/wicked-crew:execute  # design
/wicked-crew:approve design
/wicked-crew:execute  # test-strategy
/wicked-crew:approve test-strategy
/wicked-crew:execute  # build
/wicked-crew:approve build
/wicked-crew:execute  # review
/wicked-crew:approve review
```

**Expected**: Project 2 completes successfully

**Verify other projects unaffected**:
```bash
cd ~/test-wicked-crew/multi-project/web-app
/wicked-crew:status
```

Expected: Still in design phase (unchanged)

```bash
cd ~/test-wicked-crew/multi-project/db-schema
/wicked-crew:status
```

Expected: Still in clarify phase (unchanged)

### 5. List All Projects

```bash
/wicked-crew:list
```

**Expected output**:
```
Active Projects:

1. add-dark-mode-toggle (design)
   ~/test-wicked-crew/multi-project/web-app
   Last activity: 5 minutes ago

2. fix-500-error-on-health (completed)
   ~/test-wicked-crew/multi-project/api-service
   Completed: 1 minute ago

3. add-user-roles-and-permissions (clarify)
   ~/test-wicked-crew/multi-project/db-schema
   Last activity: 10 minutes ago
```

## Expected Outcome

- Multiple projects coexist without interference
- Each project maintains independent state (phase, deliverables, context)
- Working directory determines active project
- Status command always shows correct project for current directory
- Completing one project doesn't affect others
- All project data persists independently

## Success Criteria

### Project Isolation
- [ ] Three projects created with unique names/slugs
- [ ] Each project has separate directory in `~/.something-wicked/wicked-crew/projects/`
- [ ] Changing directories switches active project context
- [ ] No cross-contamination of deliverables between projects

### State Persistence
- [ ] Each project tracks phase independently
- [ ] Deliverables stored in correct project directory
- [ ] Status command shows correct project based on working directory
- [ ] Project state persists across directory changes

### Context Switching
- [ ] Can work on project 1, switch to project 2, return to project 1
- [ ] Context is correct after every switch
- [ ] No confusion about which project is active
- [ ] Execute command operates on correct project

### Completion Independence
- [ ] Completing project 2 doesn't affect project 1 or 3
- [ ] Completed projects still visible in list
- [ ] Active projects continue normally after another completes

### List Command
- [ ] Shows all projects (active and completed)
- [ ] Displays phase for each project
- [ ] Shows working directory association
- [ ] Indicates last activity time

## Value Demonstrated

**Real-world value**: Developers rarely work on just one thing at a time. A typical day might involve:
- Feature work on project A
- Bug fix on project B (urgent interruption)
- Code review on project C
- Back to feature work on project A

Traditional project management tools force you to "close" one project before opening another, or they mix all tasks together into one list. wicked-crew's directory-based project detection means switching contexts is as simple as `cd different-project`.

The independent state management prevents common mistakes:
- Running design phase on wrong project
- Approving the wrong phase because you forgot which project you're in
- Losing track of where each project stands

This mirrors how developers actually work with git branches - each project/branch is independent, and switching is instant. wicked-crew brings the same mental model to workflow orchestration.

For teams, this means pair programming doesn't require syncing project state. Each developer can work on their own projects, and collaboration happens at the artifact level (reviewing the generated designs, test scenarios, etc.) rather than at the state level.

The list command provides a quick overview of all in-flight work, helping with daily standup updates and context switching decisions. "I have 3 projects active: 2 in build phase, 1 in design. Let me focus on finishing the ones in build first."
