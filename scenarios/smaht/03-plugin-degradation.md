---
name: plugin-degradation
title: Graceful Plugin Degradation
description: Verify standalone mode works when specialized plugins unavailable
type: integration
difficulty: intermediate
estimated_minutes: 12
---

# Graceful Plugin Degradation

This scenario validates that wicked-crew degrades gracefully from full plugin integration to standalone mode, maintaining functionality across all degradation levels.

## Setup

Test with three different plugin availability scenarios:

**Level 4 (Full)**: All plugins installed
**Level 2 (Partial)**: Only wicked-mem installed
**Level 1 (Standalone)**: No plugins installed

Note: This scenario tests crew workflow degradation and requires a live Claude Code session with plugin install/uninstall capability. Steps use slash commands that cannot be simulated via CLI scripts alone. When running in isolation, the test project setup below can validate that the project environment is correct, but the integration tests (Tests 1-3) require live execution.

```bash
# Create test project
TEST_DIR="${TMPDIR:-/tmp}/test-wicked-crew-$$"
mkdir -p "$TEST_DIR/ts-api/src"
cd "$TEST_DIR/ts-api"
echo "$TEST_DIR" > "${TMPDIR:-/tmp}/wicked-scenario-degrade-dir"

# Initialize project (minimal, no npm needed for structural test)
cat > package.json <<'EOF'
{"name": "ts-api-test", "version": "1.0.0", "private": true}
EOF

# Create existing code
cat > src/api.ts <<'EOF'
// Existing API with basic error handling
export class ApiClient {
  async fetchUser(id: string): Promise<any> {
    const response = await fetch(`/api/users/${id}`);
    if (!response.ok) {
      throw new Error('Failed to fetch user');
    }
    return response.json();
  }
}
EOF

cat > tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true
  }
}
EOF

echo "Test project created at $TEST_DIR/ts-api"
```

## Steps

### Test 1: Full Integration (Level 4)

**Prerequisites**: Install all wicked plugins
```bash
claude plugin install wicked-jam@wicked-garden
claude plugin install wicked-search@wicked-garden
claude plugin install wicked-product@wicked-garden
claude plugin install wicked-kanban@wicked-garden
claude plugin install wicked-mem@wicked-garden
```

**Execute**:
```bash
/wicked-garden:crew:start "Add retry logic with exponential backoff to API client"
/wicked-garden:crew:status
```

**Expected status output**:
```
Project: add-retry-logic-with-exponential-backoff
Phase: clarify
Status: in-progress

Degradation Level: 4 (Full Integration)
Available Integrations:
  ✓ wicked-jam - brainstorming
  ✓ wicked-search - code research
  ✓ wicked-product - code review
  ✓ wicked-kanban - task tracking
  ✓ wicked-mem - memory persistence
```

**Execute clarify with wicked-jam**:
```bash
/wicked-garden:crew:execute
```

**Expected**:
- Dispatches to `/wicked-garden:jam:brainstorm "retry strategies with exponential backoff"`
- Facilitator synthesizes jam insights into structured outcome
- Mentions in output: "Using wicked-jam for brainstorming"

**Verify integration**:
- Check that wicked-mem stores project context
- Check that jam session results are cached

### Test 2: Partial Integration (Level 2)

**Prerequisites**: Uninstall all except wicked-mem
```bash
claude plugin uninstall wicked-jam
claude plugin uninstall wicked-search
claude plugin uninstall wicked-product
claude plugin uninstall wicked-kanban
# Keep wicked-mem
```

**Execute**:
```bash
/wicked-garden:crew:start "Add request timeout configuration to API client"
/wicked-garden:crew:status
```

**Expected status output**:
```
Project: add-request-timeout-configuration
Phase: clarify
Status: in-progress

Degradation Level: 2 (Partial - Memory Only)
Available Integrations:
  ✗ wicked-jam - using inline brainstorming
  ✗ wicked-search - using Glob/Grep/Read
  ✗ wicked-product - using inline review
  ✗ wicked-kanban - using TodoWrite
  ✓ wicked-mem - memory persistence
```

**Execute clarify without wicked-jam**:
```bash
/wicked-garden:crew:execute
```

**Expected**:
- Facilitator agent runs inline (no jam dispatch)
- Asks structured questions to define outcome
- Mentions: "Running in degraded mode - inline brainstorming"
- Still creates valid `objective.md` and `acceptance-criteria.md`

**Progress to design**:
```bash
/wicked-garden:crew:approve clarify
/wicked-garden:crew:execute
```

**Expected**:
- Uses Glob to find TypeScript files: `src/**/*.ts`
- Uses Grep to search for fetch patterns
- Uses Read to examine existing code
- Mentions: "Using Glob/Grep/Read instead of wicked-search"
- Produces equivalent `architecture.md`

**Progress to build**:
```bash
/wicked-garden:crew:approve design
/wicked-garden:crew:approve test-strategy
/wicked-garden:crew:execute
```

**Expected**:
- Uses TodoWrite for task tracking
- Creates tasks in `phases/build/tasks.md`
- Mentions: "Using TodoWrite instead of wicked-kanban"

### Test 3: Standalone Mode (Level 1)

**Prerequisites**: Uninstall all plugins
```bash
claude plugin uninstall wicked-mem
```

**Execute**:
```bash
/wicked-garden:crew:start "Add request/response logging to API client"
/wicked-garden:crew:status
```

**Expected status output**:
```
Project: add-request-response-logging
Phase: clarify
Status: in-progress

Degradation Level: 1 (Standalone)
Available Integrations:
  ✗ wicked-jam - using inline brainstorming
  ✗ wicked-search - using Glob/Grep/Read
  ✗ wicked-product - using inline review
  ✗ wicked-kanban - using TodoWrite
  ✗ wicked-mem - using file persistence

Note: All project data stored locally via file-based persistence
```

**Complete full workflow standalone**:
```bash
/wicked-garden:crew:execute           # clarify
/wicked-garden:crew:approve clarify
/wicked-garden:crew:execute           # design
/wicked-garden:crew:approve design
/wicked-garden:crew:execute           # test-strategy
/wicked-garden:crew:approve test-strategy
/wicked-garden:crew:execute           # build
/wicked-garden:crew:approve build
/wicked-garden:crew:execute           # review
```

**Expected**:
- All phases complete using inline alternatives
- Project state persists locally between commands
- State survives across commands (reads from local storage)
- No functionality loss, just different implementation paths

**Verify persistence**:
```bash
# Exit and restart Claude Code
# Then:
/wicked-garden:crew:status
```

**Expected**:
- Loads project state from local storage
- Shows current phase and status correctly
- No data loss from lack of wicked-mem

## Cleanup

```bash
TEST_DIR=$(cat "${TMPDIR:-/tmp}/wicked-scenario-degrade-dir" 2>/dev/null)
if [ -n "$TEST_DIR" ] && [ -d "$TEST_DIR" ]; then
  rm -rf "$TEST_DIR"
fi
rm -f "${TMPDIR:-/tmp}/wicked-scenario-degrade-dir"
```

## Expected Outcome

All three degradation levels produce equivalent results:
- Same outcome quality
- Same phase deliverables
- Same approval gates
- Same final implementation

The only differences:
- **Level 4**: Richer brainstorming, visual task board, cross-session memory
- **Level 2**: Inline brainstorming, file-based tasks, session memory only
- **Level 1**: Completely self-contained, file-based persistence

## Success Criteria

### Degradation Detection
- [ ] Status command correctly identifies degradation level
- [ ] Lists which plugins are available vs unavailable
- [ ] Shows inline alternative for each unavailable plugin
- [ ] Warns user but doesn't fail

### Functional Equivalence
- [ ] All five phases work at each degradation level
- [ ] Clarify produces valid `objective.md` and `acceptance-criteria.md` regardless of wicked-jam
- [ ] Design finds patterns regardless of wicked-search
- [ ] Build tracks tasks regardless of wicked-kanban
- [ ] Review validates regardless of wicked-product

### Inline Alternatives
- [ ] Inline brainstorming asks structured questions
- [ ] Glob/Grep/Read finds code patterns effectively
- [ ] TodoWrite tracks tasks adequately
- [ ] Inline review covers key perspectives

### Persistence
- [ ] Level 4: wicked-mem stores/retrieves context
- [ ] Level 2: wicked-mem works, others use files
- [ ] Level 1: File-based persistence works across sessions
- [ ] No data loss when downgrading levels

### Communication
- [ ] Clear messaging about which mode is active
- [ ] Explains what's different in degraded mode
- [ ] Doesn't spam warnings (mentions once per phase)
- [ ] User understands tradeoffs

## Value Demonstrated

**Real-world value**: Not everyone will have the full wicked-garden suite installed. Some users might only want wicked-crew without the dependencies. Others might be in an environment where certain plugins aren't available.

wicked-crew's graceful degradation means it works for everyone, not just users with the complete plugin ecosystem. A developer can start with standalone mode, see value immediately, then optionally enhance with additional plugins later.

This architectural flexibility prevents vendor lock-in and reduces adoption friction. You don't need to install 5 plugins just to try workflow orchestration - wicked-crew works standalone.

The degradation is graceful because functionality doesn't break - it just uses simpler alternatives. A brainstorming session without wicked-jam is still valuable, it's just structured prompting instead of multi-persona simulation. Task tracking without wicked-kanban still works, it's just TodoWrite instead of visual boards.

This proves the core workflow value is in the phase structure and quality gates, not in specific tool integrations. The integrations enhance the experience but aren't required for effectiveness.
