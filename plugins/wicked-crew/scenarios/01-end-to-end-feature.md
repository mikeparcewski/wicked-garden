---
name: end-to-end-feature
title: End-to-End Feature Delivery
description: Complete workflow from idea to implementation with all five phases
type: workflow
difficulty: intermediate
estimated_minutes: 20
---

# End-to-End Feature Delivery

This scenario validates that wicked-crew can orchestrate a complete feature from initial concept through final review, maintaining context and quality gates throughout.

## Setup

Create a realistic Node.js API project with existing patterns:

```bash
# Create test project
mkdir -p ~/test-wicked-crew/api-project
cd ~/test-wicked-crew/api-project

# Initialize Node project
npm init -y

# Create existing auth structure
mkdir -p src/auth
cat > src/auth/login.js <<'EOF'
// Basic username/password login
module.exports = function login(username, password) {
  if (username === 'admin' && password === 'admin') {
    return { token: 'fake-jwt-token' };
  }
  throw new Error('Invalid credentials');
};
EOF

cat > src/server.js <<'EOF'
const express = require('express');
const login = require('./auth/login');
const app = express();
app.use(express.json());

app.post('/login', (req, res) => {
  try {
    const result = login(req.body.username, req.body.password);
    res.json(result);
  } catch (e) {
    res.status(401).json({ error: e.message });
  }
});

app.listen(3000, () => console.log('Server running'));
EOF

# Create package.json dependencies
npm install express --save
```

## Steps

### 1. Start Project

```bash
/wicked-crew:start "Add OAuth2 social login (Google and GitHub) to existing authentication system"
```

**Expected**:
- Project directory created at `~/.something-wicked/wicked-crew/projects/add-oauth2-social-login/`
- Status shows: Phase "clarify", Status "in-progress"
- Lists available plugin integrations (wicked-jam, wicked-search, etc.)
- If plugins missing, notes degradation level

### 2. Clarify Phase - Define Outcome

```bash
/wicked-crew:execute
```

**With wicked-jam available**:
- Dispatches to `/wicked-jam:brainstorm "OAuth2 integration approaches for Node.js API"`
- Facilitator synthesizes into structured outcome

**Without wicked-jam (standalone)**:
- Facilitator agent asks clarifying questions:
  - Which OAuth providers? (Google, GitHub initially)
  - Existing auth preservation? (Yes, keep username/password)
  - User data storage? (Extend existing user model)
- Creates `outcome.md` with success criteria

**Expected Deliverables**:
```
phases/clarify/outcome.md containing:
- Desired Outcome: Enable social login without breaking existing auth
- Success Criteria:
  1. Users can log in via Google OAuth2
  2. Users can log in via GitHub OAuth2
  3. Existing username/password login still works
  4. User profiles merge correctly
- In Scope: Google + GitHub, token generation
- Out of Scope: Facebook, LinkedIn, user migration
```

### 3. Approve Clarify

```bash
/wicked-crew:approve clarify
```

**Expected**:
- Phase marked "completed" in `project.md`
- Current phase advances to "design"
- Status summary shows clarify deliverables

### 4. Design Phase - Research Patterns

```bash
/wicked-crew:execute
```

**With wicked-search available**:
- Dispatches to `/wicked-search:research "OAuth2 implementation patterns passport.js"`
- Finds existing auth patterns in codebase

**Without wicked-search (standalone)**:
- Uses Glob to find existing auth files: `src/auth/*.js`
- Uses Grep to find passport or OAuth references
- Documents current auth architecture

**Expected Deliverables**:
```
phases/design/architecture.md containing:
- Current auth flow diagram
- Proposed OAuth integration points
- Library recommendation (passport.js with google/github strategies)
- Database schema changes
- Environment variables needed
```

### 5. Approve Design

```bash
/wicked-crew:approve design
```

**Expected**: Phase advances to "qe"

### 6. QE Phase - Test Strategy

```bash
/wicked-crew:execute
```

**With wicked-product available**:
- Dispatches to `/wicked-engineering:review --perspectives qe`
- Reviews design artifacts from QE perspective

**Without wicked-product (standalone)**:
- Creates test scenarios inline
- Identifies edge cases

**Expected Deliverables**:
```
phases/qe/test-scenarios.md containing:
- Happy path: Google login for new user
- Happy path: GitHub login for existing user
- Edge case: OAuth provider returns error
- Edge case: Email already exists with different provider
- Security: Token validation
- Security: CSRF protection
```

### 7. Approve QE

```bash
/wicked-crew:approve qe
```

**Expected**: Phase advances to "build"

### 8. Build Phase - Implementation

```bash
/wicked-crew:execute
```

**With wicked-kanban available**:
- Creates tasks in kanban board
- Tracks implementation progress visually
- Updates task status as work completes

**Without wicked-kanban (standalone)**:
- Uses TodoWrite for task tracking
- Tracks in `phases/build/tasks.md`

**Implementation tasks created**:
1. Install passport, passport-google-oauth20, passport-github2
2. Create OAuth configuration in `src/auth/oauth-config.js`
3. Add OAuth routes to `src/server.js`
4. Create callback handlers
5. Implement user profile merging
6. Add environment variable documentation

**Expected Deliverables**:
- Working OAuth implementation
- All test scenarios passing
- Documentation updated

### 9. Approve Build

```bash
/wicked-crew:approve build
```

**Expected**: Phase advances to "review"

### 10. Review Phase - Final Validation

```bash
/wicked-crew:execute
```

**With wicked-product available**:
- Dispatches to `/wicked-engineering:review` with multiple perspectives
- Gets feedback from security, engineering, product perspectives

**Without wicked-product (standalone)**:
- Inline multi-perspective review prompts
- Reviews against outcome criteria

**Expected Deliverables**:
```
phases/review/findings.md containing:
- Engineering: Code quality, patterns consistency
- Security: OAuth implementation, token handling
- QE: Test coverage assessment
- Recommendations: Any improvements needed
- Sign-off: Ready/Not Ready with reasoning
```

### 11. Complete Project

```bash
/wicked-crew:approve review
```

**Expected**:
- Project status: "completed"
- Summary of all deliverables
- Links to phase artifacts
- Completion timestamp

## Expected Outcome

- Project progresses through all five phases sequentially
- Each phase requires explicit approval (quality gate)
- Phase-specific agents/tools are used appropriately
- Context is maintained across phases (design informs QE, QE informs build)
- Degradation works correctly when plugins unavailable
- All artifacts are stored persistently in `.something-wicked/wicked-crew/`

## Success Criteria

- [ ] Project created with unique slug-based directory name
- [ ] All five phases execute in correct order
- [ ] Approval required between each phase (cannot skip)
- [ ] Clarify phase produces measurable success criteria
- [ ] Design phase references actual codebase patterns
- [ ] QE phase creates specific test scenarios
- [ ] Build phase implements according to design and tests
- [ ] Review phase validates against original outcome
- [ ] Works in standalone mode (no plugins)
- [ ] Integrates with available plugins (wicked-jam, wicked-search, etc.)
- [ ] Project state persists across commands
- [ ] Final review references outcome.md success criteria

## Value Demonstrated

**Real-world value**: Software projects often fail because of unclear outcomes, skipped quality gates, or lost context between phases. wicked-crew enforces a structured workflow that prevents "just start coding" syndrome.

By forcing outcome clarification upfront, the team knows what success looks like. By doing QE before build (shift-left testing), bugs are prevented instead of fixed. By maintaining context across phases, decisions made during design inform implementation.

This replaces ad-hoc project management where developers start coding without clear acceptance criteria, skip testing until the end, and then discover they built the wrong thing. The explicit approval gates ensure stakeholder alignment at key decision points.

For teams using wicked-kanban, wicked-search, and wicked-product, the integration provides seamless orchestration across tools. For teams without those plugins, the graceful degradation ensures the workflow still works with built-in alternatives.
