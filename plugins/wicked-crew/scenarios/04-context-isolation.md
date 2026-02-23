---
name: context-isolation
title: SADD Pattern Context Isolation
description: Verify Spawn-Agent-Dispatch-Destroy pattern maintains clean context
type: feature
difficulty: advanced
estimated_minutes: 10
---

# SADD Pattern Context Isolation

This scenario validates that wicked-crew's SADD (Spawn-Agent-Dispatch-Destroy) pattern properly isolates context between phases and prevents context pollution.

## Setup

Create a project with intentionally complex, confusing existing code:

```bash
# Create test project with multiple conflicting patterns
mkdir -p ~/test-wicked-crew/legacy-app
cd ~/test-wicked-crew/legacy-app

# Create messy codebase with competing patterns
cat > auth-v1.js <<'EOF'
// OLD: Session-based auth (deprecated, don't use this!)
module.exports.authenticateSession = function(sessionId) {
  // Legacy session lookup
  return { userId: 'session-' + sessionId };
};
EOF

cat > auth-v2.js <<'EOF'
// CURRENT: JWT-based auth (this is the pattern to follow)
const jwt = require('jsonwebtoken');
module.exports.authenticateJWT = function(token) {
  return jwt.verify(token, process.env.JWT_SECRET);
};
EOF

cat > users-old.js <<'EOF'
// OLD: Direct DB queries (deprecated)
const db = require('./db');
module.exports.getUser = async (id) => {
  return await db.query('SELECT * FROM users WHERE id = ?', [id]);
};
EOF

cat > users-new.js <<'EOF'
// CURRENT: Repository pattern (this is the pattern to follow)
class UserRepository {
  async findById(id) {
    // Modern approach with ORM
    return User.findOne({ where: { id } });
  }
}
module.exports = UserRepository;
EOF

cat > README.md <<'EOF'
# Legacy App

IMPORTANT: We're migrating from session auth (auth-v1.js) to JWT (auth-v2.js).
Also migrating from direct DB (users-old.js) to repository pattern (users-new.js).

NEW CODE MUST USE: auth-v2.js and users-new.js patterns!
EOF
```

## Steps

### 1. Start Project

```bash
/wicked-crew:start "Add password reset functionality using email verification"
```

### 2. Design Phase - Pattern Detection

```bash
/wicked-crew:approve clarify
/wicked-crew:execute  # design phase
```

**Expected behavior with SADD**:

The design agent should:
1. **Spawn** with fresh context (no clarify phase discussion in memory)
2. **Read** the codebase files
3. **Identify** competing patterns (v1 vs v2, old vs new)
4. **Choose** correct patterns (JWT, Repository) based on README
5. **Document** decision with reasoning
6. **Return** summary to orchestrator
7. **Destroy** (context discarded)

**Verify in output**:
- Mentions finding BOTH auth-v1.js AND auth-v2.js
- Explicitly states "using auth-v2.js pattern (JWT) per README"
- Does NOT confuse session-based with JWT-based approach
- Creates architecture.md that clearly specifies JWT + Repository pattern

### 3. Build Phase - Pattern Application

```bash
/wicked-crew:approve design
/wicked-crew:approve qe
/wicked-crew:execute  # build phase
```

**Expected behavior with SADD**:

The implementer agent should:
1. **Spawn** with fresh context (no design discussion in memory)
2. **Read** `phases/design/architecture.md` (the decision, not the exploration)
3. **Read** auth-v2.js and users-new.js (the chosen patterns)
4. **Implement** password reset using those patterns
5. **NOT** read or reference deprecated files
6. **Return** implementation summary
7. **Destroy**

**Verify implementation**:
```bash
# After build phase completes, check the created code
cat ~/test-wicked-crew/legacy-app/auth-reset.js
```

**Expected**:
- Uses `jwt` for token generation (not sessions)
- Uses `UserRepository` pattern (not direct DB)
- Follows auth-v2.js style
- Does NOT mix patterns from old files

### 4. Test Context Pollution

Create a scenario designed to test if context leaks between phases:

```bash
# Create a new project with misleading discussion
/wicked-crew:start "Add rate limiting to API endpoints"
```

During clarify, manually add confusing information:

```bash
User: "Actually, I'm thinking maybe we should use Redis for rate limiting. Or maybe memory-based? I saw this library called express-rate-limit but I'm not sure if it's good. What do you think about rolling our own solution? I heard Nginx can do this too..."
```

Let the facilitator respond and create the clarify deliverables (`objective.md` and `acceptance-criteria.md`).

Then proceed to design:

```bash
/wicked-crew:approve clarify
/wicked-crew:execute  # design phase
```

**Test for context isolation**:

The design agent should:
- **NOT** see the rambling discussion from clarify
- **ONLY** see `phases/clarify/objective.md` and `phases/clarify/acceptance-criteria.md` (the decisions)
- Research patterns based on the objective, not on clarify discussion
- Not be biased by the "Redis or memory or Nginx or custom" confusion

**Verify in design output**:
- Shows research methodology: searched codebase, evaluated options
- Makes fresh recommendation based on evidence, not clarify discussion
- If `acceptance-criteria.md` said "use express-rate-limit", design validates that choice
- Does NOT reference the rambling questions from clarify phase

### 5. Measure Context Size

Track token usage across phases to verify SADD reduces context:

**Without SADD** (hypothetical - all discussion in one context):
- Clarify: 5000 tokens of discussion
- Design: 5000 (clarify) + 8000 (research) = 13000 tokens
- QE: 13000 + 6000 (scenarios) = 19000 tokens
- Build: 19000 + 15000 (implementation) = 34000 tokens
- Review: 34000 + 5000 (review) = 39000 tokens

**With SADD** (actual - fresh context per phase):
- Clarify: 5000 tokens
- Design: ~2000 (objective.md + acceptance-criteria.md) + 8000 (research) = 10000 tokens
- QE: ~3000 (design artifacts) + 6000 (scenarios) = 9000 tokens
- Build: ~4000 (design + QE) + 15000 (implementation) = 19000 tokens
- Review: ~2000 (acceptance-criteria.md) + 5000 (review) = 7000 tokens

**Expected**: Each phase starts with minimal context (only artifacts, not discussion)

## Expected Outcome

**Context Isolation**:
- Each phase agent only sees deliverables from previous phases
- No discussion history leaks between phases
- Agents make decisions based on artifacts, not conversations
- Context size remains manageable throughout project

**Pattern Detection**:
- Design phase correctly identifies competing patterns
- Build phase follows chosen patterns consistently
- No mixing of deprecated and current approaches
- Clear documentation of pattern decisions

**Token Efficiency**:
- SADD reduces cumulative context growth
- Later phases don't carry full history of earlier phases
- Focus remains on deliverables, not process

## Success Criteria

### SADD Implementation
- [ ] Each phase uses Task tool to spawn subagent
- [ ] Subagent receives focused prompt with artifacts only
- [ ] Subagent doesn't see previous phase discussions
- [ ] Orchestrator summarizes subagent results
- [ ] Subagent context is discarded after task

### Context Isolation
- [ ] Design phase only reads `objective.md` and `acceptance-criteria.md` (not clarify discussion)
- [ ] Build phase only reads design/QE artifacts (not discussions)
- [ ] Review phase only reads outcome + final code (not process)
- [ ] Agents don't reference conversations from previous phases

### Pattern Correctness
- [ ] Design identifies multiple competing patterns
- [ ] Design chooses correct pattern with reasoning
- [ ] Build implements using chosen pattern consistently
- [ ] No mixing of deprecated patterns into new code

### Token Efficiency
- [ ] Design phase context < 15k tokens
- [ ] Build phase context < 25k tokens
- [ ] Review phase context < 10k tokens
- [ ] No exponential context growth across phases

### Error Resistance
- [ ] Confusing clarify discussion doesn't poison design decisions
- [ ] Rambling explorations don't leak into implementation
- [ ] Each phase can make clean decisions based on deliverables

## Value Demonstrated

**Real-world value**: Long-running projects accumulate massive context that slows down AI responses and increases costs. The SADD pattern solves this by treating each phase as a fresh task with only essential inputs.

This mirrors how real teams work - the implementation engineer doesn't need to attend every brainstorming session, they just need the requirements doc. The code reviewer doesn't need the full design debate, just the outcome and the code.

By isolating context, wicked-crew:
1. **Reduces tokens**: Each phase stays under 25k instead of growing to 100k+
2. **Improves focus**: Agents aren't distracted by irrelevant discussion history
3. **Prevents poisoning**: Confused explorations don't bias later decisions
4. **Enables specialization**: Each agent gets exactly the context it needs

In the legacy codebase scenario, SADD prevents the "pattern confusion" problem where the AI sees both old and new patterns and mixes them together. The design agent reads everything and makes a decision. The build agent only sees that decision and the chosen patterns, not the deprecated alternatives.

This is critical for real legacy codebases where deprecated code must remain (for backwards compatibility) but new code must follow modern patterns. Without context isolation, the AI would constantly mix old and new approaches.

The token efficiency means you can run larger projects without hitting context limits, and responses stay fast even in late phases. The cost savings compound - a 5-phase project might use 50k tokens total instead of 200k+.
