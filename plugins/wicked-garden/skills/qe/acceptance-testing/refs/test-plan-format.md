# Test Plan Format Reference

Complete specification for evidence-gated test plans produced by the acceptance-test-writer agent.

## Structure

```markdown
# Test Plan: {scenario_name}

## Metadata
## Specification Notes
## Prerequisites
## Test Steps
## Acceptance Criteria Map
## Evidence Manifest
```

## Metadata Section

```markdown
## Metadata
- **Source**: path/to/scenario.md
- **Generated**: 2024-01-15T10:30:00Z
- **Implementation files**: list of files the writer read during analysis
- **Scenario format**: plugin-acceptance | user-story | e2e-scenario
```

The implementation files list is critical — it documents what the writer inspected. If the implementation changes after the test plan was generated, the plan may be stale.

## Specification Notes

The writer documents mismatches between scenario expectations and actual implementation:

```markdown
## Specification Notes

### NOTE-1: Signal pattern mismatch
The scenario expects "auth question triggers memory injection" but the
implementation's hook uses continuation signal patterns (keywords like
"earlier", "before", "previously") rather than topical matching. An auth
question without continuation signals will NOT trigger injection.

**Impact**: STEP-4 assertions will FAIL unless the test prompt includes
continuation signals.
**Recommendation**: Either update the scenario's test prompt or update the
hook to support topical matching.
```

If no issues found: `No specification issues found.`

## Prerequisites

Conditions that must hold before test execution begins:

```markdown
## Prerequisites

### PRE-1: Plugin is installed
- **Check**: `ls plugins/wicked-mem/.claude-plugin/plugin.json`
- **Evidence**: `pre-1-check` — file listing output
- **Assert**: `pre-1-check` EXISTS

### PRE-2: Clean state
- **Check**: `rm -rf ~/.something-wicked/wicked-mem/memories/ 2>/dev/null; echo "clean"`
- **Evidence**: `pre-2-check` — command output
- **Assert**: `pre-2-check` CONTAINS "clean"
```

## Test Steps

Each step follows this template:

```markdown
### STEP-{N}: {description}
- **Action**: {exact operation to perform}
- **Depends on**: {STEP-M} (optional — only if sequential dependency)
- **Evidence required**:
  - `step-{N}-output` — {what to capture and how}
  - `step-{N}-state` — {what state to snapshot}
  - `step-{N}-file` — {what file to read}
- **Assertions**:
  - `step-{N}-output` {OPERATOR} "{value}"
  - `step-{N}-state` {OPERATOR} "{value}"
```

### Action Types

| Action | How writer specifies | How executor performs |
|--------|---------------------|---------------------|
| Skill invocation | `Invoke Skill: wicked-garden:mem-store, args: "..."` | Skill tool |
| Bash command | `Run: ls -la path/` | Bash tool |
| File read | `Read file: /path/to/file.json` | Read tool |
| File write | `Write file: /path with content: ...` | Write tool |
| Task dispatch | `Dispatch Task: agent-type, prompt: "..."` | Task tool |
| User simulation | `Submit prompt: "How do I..."` | Direct message or Skill |

### Evidence Types

| Type | Description | Capture method |
|------|-------------|----------------|
| `command_output` | stdout + stderr + exit code | Bash tool result |
| `file_content` | File contents at a path | Read tool result |
| `file_exists` | Boolean — does path exist | Glob tool or `ls` |
| `state_snapshot` | System state at a point | Command output (JSON preferred) |
| `tool_result` | Full response from a Claude tool | Tool return text |
| `search_result` | Search matches | Grep/Glob results |

## Assertion Operators

### CONTAINS / NOT_CONTAINS

String search within evidence text. Case-sensitive.

```markdown
- `step-1-output` CONTAINS "stored"
- `step-1-output` NOT_CONTAINS "error"
```

**Multi-value OR**: Use multiple CONTAINS with OR:
```markdown
- `step-1-output` CONTAINS "stored" OR CONTAINS "saved" OR CONTAINS "created"
```

### MATCHES

Regex pattern match. Uses standard regex syntax.

```markdown
- `step-2-output` MATCHES "score: \\d+/\\d+"
- `step-2-output` MATCHES "ID: [a-f0-9]{8}"
```

### EQUALS

Exact equality. Most useful for exit codes and boolean values.

```markdown
- `step-1-output.exit_code` EQUALS 0
- `step-3-state.exists` EQUALS true
```

### EXISTS / NOT_EMPTY

Existence and non-emptiness checks.

```markdown
- `step-2-file` EXISTS
- `step-2-output` NOT_EMPTY
```

### JSON_PATH

Navigate JSON structure and check values. Uses `$.path.notation`.

```markdown
- `step-4-state` JSON_PATH "$.status" EQUALS "active"
- `step-4-state` JSON_PATH "$.items" COUNT_GTE 3
- `step-4-state` JSON_PATH "$.memories[0].type" EQUALS "decision"
```

### COUNT_GTE / COUNT_LTE

Count lines or items and compare against threshold.

```markdown
- `step-3-output` COUNT_GTE 3         # at least 3 lines
- `step-5-results` COUNT_LTE 10       # at most 10 matches
```

### HUMAN_REVIEW

Cannot be auto-evaluated. Provides context for human reviewer.

```markdown
- `step-6-output` HUMAN_REVIEW "Is the architectural recommendation sound and actionable?"
```

Use sparingly — only for genuinely qualitative criteria.

## Acceptance Criteria Map

Maps original scenario criteria to specific assertions:

```markdown
## Acceptance Criteria Map

| Criterion (from scenario) | Verified by | Steps |
|---------------------------|-------------|-------|
| Memory stored successfully | step-1-output CONTAINS "stored", step-1-state NOT_EMPTY | STEP-1 |
| Recalled memories are relevant | step-3-output HUMAN_REVIEW | STEP-3 |
| Context injected on continuation | step-4-trace JSON_PATH "$.systemMessage" NOT_EMPTY | STEP-4 |
```

Every criterion from the original scenario MUST appear in this table. If a criterion cannot be tested (too vague, no observable behavior), the writer flags it as untestable with a recommendation to improve the scenario.

## Evidence Manifest

Complete registry of all evidence IDs:

```markdown
## Evidence Manifest

| Evidence ID | Type | Description | Produced by |
|-------------|------|-------------|-------------|
| `pre-1-check` | command_output | Plugin installation check | PRE-1 |
| `step-1-output` | tool_result | Store command response | STEP-1 |
| `step-1-state` | command_output | Memory directory listing | STEP-1 |
| `step-2-output` | tool_result | Recall command response | STEP-2 |
```

## Example: Complete Test Plan

```markdown
# Test Plan: decision-recall

## Metadata
- **Source**: plugins/wicked-mem/scenarios/01-decision-recall.md
- **Generated**: 2024-01-15T10:30:00Z
- **Implementation files**: plugins/wicked-mem/commands/store.md, plugins/wicked-mem/scripts/memory.py
- **Scenario format**: plugin-acceptance

## Specification Notes
No specification issues found.

## Prerequisites

### PRE-1: Clean memory state
- **Check**: Run `rm -rf ~/.something-wicked/wicked-mem/memories/ 2>/dev/null; echo "clean"`
- **Evidence**: `pre-1-check` — command output
- **Assert**: `pre-1-check` CONTAINS "clean"

## Test Steps

### STEP-1: Store a decision memory
- **Action**: Invoke Skill: wicked-garden:mem-store, args: "Use JWT for auth tokens" --type decision --tags "auth,security"
- **Evidence required**:
  - `step-1-output` — Full Skill tool response text
  - `step-1-state` — Run `ls ~/.something-wicked/wicked-mem/memories/*.json 2>/dev/null | wc -l`
- **Assertions**:
  - `step-1-output` CONTAINS "stored" OR CONTAINS "saved" OR CONTAINS "created"
  - `step-1-output` NOT_CONTAINS "error"
  - `step-1-state` NOT_EMPTY

### STEP-2: Recall the decision
- **Action**: Invoke Skill: wicked-garden:mem-recall, args: "authentication token strategy"
- **Depends on**: STEP-1
- **Evidence required**:
  - `step-2-output` — Full Skill tool response text
- **Assertions**:
  - `step-2-output` CONTAINS "JWT"
  - `step-2-output` NOT_CONTAINS "No memories found"

## Acceptance Criteria Map

| Criterion | Verified by | Steps |
|-----------|-------------|-------|
| Memory stored successfully | step-1-output CONTAINS "stored", step-1-state NOT_EMPTY | STEP-1 |
| Recall finds relevant memories | step-2-output CONTAINS "JWT" | STEP-2 |

## Evidence Manifest

| Evidence ID | Type | Description | Produced by |
|-------------|------|-------------|-------------|
| `pre-1-check` | command_output | Clean state verification | PRE-1 |
| `step-1-output` | tool_result | Store command response | STEP-1 |
| `step-1-state` | command_output | Memory file count | STEP-1 |
| `step-2-output` | tool_result | Recall command response | STEP-2 |
```
