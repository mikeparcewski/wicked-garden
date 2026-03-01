# Evidence Protocol Reference

How evidence is captured, structured, referenced, and evaluated in the acceptance testing pipeline.

## Evidence Lifecycle

```
Writer defines ──→ Executor captures ──→ Reviewer evaluates
  what to collect     actual artifacts      against assertions
```

Each evidence item has:
- **ID**: Unique identifier (e.g., `step-1-output`)
- **Type**: What kind of artifact (command_output, file_content, etc.)
- **Content**: The actual captured data
- **Metadata**: Timestamp, duration, execution notes

## Capture Rules

### Rule 1: Capture Everything Specified

If the test plan says to capture it, the executor must capture it. Missing evidence means the reviewer cannot evaluate that assertion — verdict becomes INCONCLUSIVE, not auto-PASS.

### Rule 2: Capture Verbatim

Evidence is captured exactly as produced. The executor does not:
- Summarize output ("it printed some JSON" → capture the actual JSON)
- Filter output (capture all of stdout, not just the interesting part)
- Interpret errors (capture the error message, don't explain it)

### Rule 3: Capture Context

For every evidence item, also record:
- Timestamp when captured
- Duration of the operation (for performance-sensitive assertions)
- Any unexpected behavior during capture (timeout, partial output, retries)

### Rule 4: Capture Side Effects

If executing a step creates files, modifies state, or triggers observable side effects, note them even if not explicitly required by the test plan. The reviewer may need this context.

## Evidence Types in Detail

### command_output

Captures the full result of a shell command.

```markdown
- `step-1-output`:
  - stdout: ```
    Memory stored: Use JWT for auth tokens (ID: mem_abc123)
    Type: decision | Tags: auth, security
    ```
  - stderr: ```
    ```
  - exit_code: 0
  - duration_ms: 342
```

**Capture method**: Bash tool. Record stdout, stderr, and exit code separately.

### file_content

Captures the contents of a file at a point in time.

```markdown
- `step-2-file`:
  - path: /home/user/.something-wicked/wicked-garden/local/wicked-mem/memories/mem_abc123.json
  - exists: true
  - size_bytes: 245
  - content: ```json
    {
      "id": "mem_abc123",
      "content": "Use JWT for auth tokens",
      "type": "decision",
      "tags": ["auth", "security"],
      "created_at": "2024-01-15T10:30:00Z"
    }
    ```
```

**Capture method**: Read tool. Also record existence and size.

### file_exists

Boolean check for file/directory existence.

```markdown
- `step-3-dir`:
  - path: /home/user/.something-wicked/wicked-garden/local/wicked-mem/memories/
  - exists: true
  - type: directory
  - children: 3 files
```

**Capture method**: Glob tool or `ls` via Bash.

### state_snapshot

Captures system state at a point in time. Preferably structured (JSON).

```markdown
- `step-4-state`:
  - captured_at: 2024-01-15T10:30:05Z
  - content: ```json
    {
      "memory_count": 3,
      "types": {"decision": 2, "pattern": 1},
      "total_size_bytes": 890
    }
    ```
```

**Capture method**: Run a state-inspection command (e.g., `python3 script.py --status`).

### tool_result

Captures the full response from a Claude tool invocation.

```markdown
- `step-5-result`:
  - tool: Skill
  - skill: wicked-garden:mem:recall
  - args: "authentication"
  - response: ```
    ## Recalled Memories

    ### 1. Use JWT for auth tokens
    **Type**: decision | **Tags**: auth, security
    **Stored**: 2024-01-15

    > Use JWT for auth tokens instead of session cookies...
    ```
```

**Capture method**: Record the full text returned by the tool.

### hook_trace

Captures hook behavior — what the hook received and returned.

```markdown
- `step-6-trace`:
  - hook: PostToolUse (wicked-smaht context injection)
  - fired: true
  - input_excerpt: {"tool_name": "Skill", ...}
  - output: {"continue": true, "systemMessage": "Context: ..."}
```

**Capture method**: Hooks fire automatically. Capture any `systemMessage` in tool responses. For deeper inspection, check hook log files if available.

### search_result

Captures code or content search results.

```markdown
- `step-7-search`:
  - tool: Grep
  - pattern: "def store_memory"
  - files_matched: 2
  - results: ```
    scripts/mem/memory.py:45: def store_memory(content, type, tags):
    scripts/mem/memory.py:102: def store_memory_batch(items):
    ```
```

**Capture method**: Grep or Glob tool results.

## Evidence Evaluation

### How the Reviewer Processes Evidence

For each assertion, the reviewer:

1. **Locates the evidence** by ID in the evidence report
2. **Extracts the relevant portion** (stdout for CONTAINS, exit_code for EQUALS, etc.)
3. **Applies the operator** mechanically
4. **Records the verdict** with evidence citation

### Evaluation Examples

**Assertion**: `step-1-output` CONTAINS "stored"
**Evidence**: stdout = `Memory stored: Use JWT for auth tokens (ID: mem_abc123)`
**Process**: Search for "stored" in stdout → found at position 7
**Verdict**: PASS

**Assertion**: `step-2-output` MATCHES `ID: [a-f0-9]{6,}`
**Evidence**: stdout = `Memory stored: Use JWT (ID: mem_abc123)`
**Process**: Apply regex → `ID: mem_abc123` does NOT match `[a-f0-9]{6,}` because "mem_" prefix is not hex
**Verdict**: FAIL — regex expected hex-only ID, but actual ID has "mem_" prefix.

**Assertion**: `step-3-state` JSON_PATH `$.memories[0].type` EQUALS "decision"
**Evidence**: state = `{"memories": [{"type": "decision", "content": "..."}]}`
**Process**: Navigate JSON path → `$.memories[0].type` = "decision" → compare with "decision"
**Verdict**: PASS

### Edge Cases in Evaluation

**Missing evidence**: Verdict = INCONCLUSIVE (never PASS)
**Empty evidence**: `NOT_EMPTY` assertion fails; `CONTAINS` on empty string fails
**Error in evidence**: An error message is evidence. `CONTAINS "error"` would PASS against it.
**Multiple matches**: For CONTAINS, any match suffices. For MATCHES, any regex match suffices.
**JSON parse failure**: If evidence is not valid JSON and assertion uses JSON_PATH, verdict = FAIL with note "evidence is not valid JSON."

## Evidence Report Structure

The executor produces this structure:

```markdown
# Evidence Report: {test plan name}

## Execution Metadata
- **Test plan**: {source}
- **Executed by**: acceptance-test-executor
- **Started**: 2024-01-15T10:30:00Z
- **Completed**: 2024-01-15T10:30:45Z
- **Total duration**: 45s

## Prerequisite Evidence

### PRE-1: {description}
- **Executed**: 2024-01-15T10:30:01Z
- **Evidence**:
  - `pre-1-check`:
    - stdout: `clean`
    - exit_code: 0

## Step Evidence

### STEP-1: {description}
- **Executed**: 2024-01-15T10:30:02Z
- **Duration**: 1.2s
- **Action taken**: Invoked Skill tool with skill="wicked-garden:mem:store" ...
- **Evidence**:
  - `step-1-output`:
    - response: `Memory stored: Use JWT... (ID: mem_abc123)`
  - `step-1-state`:
    - stdout: `1`
    - exit_code: 0
- **Execution notes**: None

## Post-Execution State
- **Completed at**: 2024-01-15T10:30:45Z
- **Steps executed**: 5 of 5
- **Steps skipped**: 0
- **Files created**: {SM_LOCAL_ROOT}/wicked-mem/memories/mem_abc123.json
```

## Common Pitfalls

### For Writers

- **Under-specifying evidence**: "Capture the output" is not enough. Specify stdout vs stderr, what to include.
- **Ambiguous assertions**: "CONTAINS response" — does the word "response" actually appear in the output?
- **Over-relying on HUMAN_REVIEW**: If >30% of assertions are HUMAN_REVIEW, the test plan needs more concrete assertions.

### For Executors

- **Summarizing instead of capturing**: Don't paraphrase. Copy the exact output.
- **Skipping evidence on failure**: A failed command still produces evidence (error messages, exit codes).
- **Missing timestamps**: Every step needs a timestamp for duration analysis.

### For Reviewers

- **Generous interpretation**: "stored" in "attempting to store" is technically a CONTAINS match but semantically wrong. Flag as PASS with a note.
- **Ignoring specification notes**: The writer flagged issues for a reason.
- **Auto-failing on partial evidence**: If 4 of 5 evidence items are present, evaluate what you can. Mark the missing one INCONCLUSIVE.
