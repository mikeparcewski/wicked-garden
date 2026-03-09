# Evidence Protocol: Validation

How evidence is evaluated, verified, and managed in the acceptance testing pipeline.

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
**Process**: Search for "stored" in stdout -> found at position 7
**Verdict**: PASS

**Assertion**: `step-2-output` MATCHES `ID: [a-f0-9]{6,}`
**Evidence**: stdout = `Memory stored: Use JWT (ID: mem_abc123)`
**Process**: Apply regex -> `ID: mem_abc123` does NOT match `[a-f0-9]{6,}` because "mem_" prefix is not hex
**Verdict**: FAIL — regex expected hex-only ID, but actual ID has "mem_" prefix.

**Assertion**: `step-3-state` JSON_PATH `$.memories[0].type` EQUALS "decision"
**Evidence**: state = `{"memories": [{"type": "decision", "content": "..."}]}`
**Process**: Navigate JSON path -> `$.memories[0].type` = "decision" -> compare with "decision"
**Verdict**: PASS

### Edge Cases in Evaluation

**Missing evidence**: Verdict = INCONCLUSIVE (never PASS)
**Empty evidence**: `NOT_EMPTY` assertion fails; `CONTAINS` on empty string fails
**Error in evidence**: An error message is evidence. `CONTAINS "error"` would PASS against it.
**Multiple matches**: For CONTAINS, any match suffices. For MATCHES, any regex match suffices.
**JSON parse failure**: If evidence is not valid JSON and assertion uses JSON_PATH, verdict = FAIL with note "evidence is not valid JSON."

## SHA-256 Checksum Requirements (AC-202-2)

Every required evidence item must have a SHA-256 checksum recorded in the artifact registry.

### What to Hash

- Compute SHA-256 over the **raw captured content** — the bytes as produced by the tool, before any markdown formatting or display transformation.
- For `command_output`: hash the stdout string UTF-8 encoded.
- For `file_content`: hash the file content bytes.
- For `tool_result`: hash the tool response text UTF-8 encoded.
- For `state_snapshot`: hash the JSON/text output UTF-8 encoded.
- For inline evidence (no file path): hash the captured text as recorded in the evidence collection, UTF-8 encoded.

### Computing the Checksum

The executor computes checksums using Python's stdlib `hashlib`:

```python
import hashlib
sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
```

The result is a 64-character lowercase hex string. Store it in the artifact registry `sha256` field.

### Reviewer Verification

The reviewer verifies each checksum by:
1. Locating the evidence item in the evidence report.
2. Extracting the raw content (same pre-formatting text the executor would have hashed).
3. Computing SHA-256 of that content.
4. Comparing with the `sha256` field in the registry.

A mismatch means the evidence report was modified after the registry was written — return `INCONCLUSIVE` with cause `EVIDENCE_INTEGRITY_FAILURE`.

## Artifact Registry Schema

The artifact registry is the authoritative record of what evidence was captured. It is written by the executor at the end of the evidence checkpoint and read by the reviewer before evaluation begins.

### Full Schema

```json
{
  "schema_version": "1.0",
  "scenario_slug": "kebab-case-scenario-name",
  "created_at": "ISO 8601 timestamp",
  "executor": "wicked-garden:qe:acceptance-test-executor",
  "artifacts": [
    {
      "id": "step-N-output",
      "type": "command_output | file_content | state_snapshot | api_response | tool_result",
      "captured_at": "ISO 8601 timestamp",
      "path": "absolute file path, or null if evidence is inline in the report",
      "sha256": "64-character hex digest of raw content, UTF-8 encoded",
      "size_bytes": 1234,
      "step_id": "STEP-N",
      "required": true
    }
  ],
  "completeness": {
    "required_count": 5,
    "captured_count": 4,
    "missing": ["step-3-output"]
  }
}
```

### Field Notes

| Field | Notes |
|-------|-------|
| `id` | Must match the evidence ID in the test plan's evidence manifest (e.g., `step-1-output`) |
| `type` | One of the evidence types defined in this document |
| `path` | Absolute path if evidence was written to a file; `null` for inline evidence |
| `sha256` | Hash of raw content, not formatted markdown. See SHA-256 section above. |
| `size_bytes` | Byte count of content. For inline evidence, byte count of the UTF-8 encoded string. |
| `step_id` | The test plan step that produced this artifact (e.g., `STEP-1`, `PRE-2`) |
| `required` | `true` if the test plan's evidence manifest marks this item as required |
| `completeness.missing` | Array of `id` values for required items that were not captured after all recapture attempts |

## Forced Recapture Protocol

When a required evidence item is missing after initial capture, the executor attempts one recapture.

### Protocol Steps

1. **Identify**: After all steps complete, check which required evidence IDs are absent from the collection.
2. **Attempt recapture**: For each missing item, re-execute the step action exactly once.
   - If captured on retry: mark as `recaptured`, compute checksum, add to registry.
   - If still missing after retry: mark step as `EVIDENCE_MISSING`.
3. **Decision gate**: If any required items are still missing after all recapture attempts:
   - Write the registry with `completeness.missing` populated.
   - Emit the `## Forced Recapture Required` directive.
   - **Do not compile the evidence report.** Stop and await re-invocation.
4. **Registry always written**: The registry is written regardless of completeness. The `completeness.missing` field communicates partial captures to the reviewer.

### One Retry Rule

Only one recapture attempt is made per missing item. This prevents infinite loops when:
- A command is consistently failing (environment issue)
- A file is never created (implementation bug)
- A tool is unavailable

After one retry, record the failure and move on. The reviewer will receive an incomplete registry and return INCONCLUSIVE.

### Forced Recapture Directive Format

```markdown
## Forced Recapture Required

The following required evidence items are missing after one recapture attempt:

- {step-N-output}: [{description -- what was expected, e.g., stdout from command X}]
- {step-M-file}: [{description -- what was expected, e.g., file created at path Y}]

The evidence registry was written to: {REGISTRY_PATH}
Registry completeness: {captured_count}/{required_count} items captured

Before the reviewer can evaluate this run, fix the missing evidence and re-execute:
  /wicked-garden:qe:acceptance --phase execute --plan {TEST_PLAN_PATH}
```

## Canonical Artifact Paths

All QE artifacts use paths resolved through `resolve_path.py` for portability across environments.

### Path Resolution

```bash
QE_DIR=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_path.py" wicked-qe 2>/dev/null \
         || echo "${TMPDIR:-/tmp}/wicked-qe-evidence")
SCENARIO_SLUG=$(echo "{scenario_name}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g')
```

### Canonical Paths

| Artifact | Canonical Path |
|----------|---------------|
| Test plan | `${QE_DIR}/test-plans/${SCENARIO_SLUG}.md` |
| Evidence report | `${QE_DIR}/evidence/${SCENARIO_SLUG}.md` |
| Artifact registry | `${QE_DIR}/evidence/${SCENARIO_SLUG}-registry.json` |
| Verdict | `${QE_DIR}/verdicts/${SCENARIO_SLUG}.json` |

### Fallback Behavior

If `resolve_path.py` is unavailable (e.g., running outside the plugin), fall back to:

```bash
QE_DIR="${TMPDIR:-/tmp}/wicked-qe-evidence"
```

This fallback is temporary and session-scoped. Registry files written to the fallback path will not persist across sessions.

### Slug Generation

The scenario slug is derived from the scenario file name or test plan title:

- Convert to lowercase
- Replace all non-alphanumeric characters with hyphens
- Collapse consecutive hyphens to one
- Example: `"01 Decision Recall!"` -> `"01-decision-recall-"`

All three pipeline agents (writer, executor, reviewer) and the acceptance command use the same slug derivation to ensure path consistency.

## Common Pitfalls

### For Writers

- **Under-specifying evidence**: "Capture the output" is not enough. Specify stdout vs stderr, what to include.
- **Ambiguous assertions**: "CONTAINS response" — does the word "response" actually appear in the output?
- **Over-relying on HUMAN_REVIEW**: If >30% of assertions are HUMAN_REVIEW, the test plan needs more concrete assertions.

### For Executors

- **Summarizing instead of capturing**: Don't paraphrase. Copy the exact output.
- **Skipping evidence on failure**: A failed command still produces evidence (error messages, exit codes).
- **Missing timestamps**: Every step needs a timestamp for duration analysis.
- **Skipping the evidence checkpoint**: Step 5b is mandatory. Never omit the registry write, even if all evidence was captured successfully.
- **Wrong hash input**: Hash the raw captured content, not the formatted markdown. "stdout: `foo`" hashes differently from "foo".

### For Reviewers

- **Generous interpretation**: "stored" in "attempting to store" is technically a CONTAINS match but semantically wrong. Flag as PASS with a note.
- **Ignoring specification notes**: The writer flagged issues for a reason.
- **Auto-failing on partial evidence**: If 4 of 5 evidence items are present, evaluate what you can. Mark the missing one INCONCLUSIVE.
- **Skipping the registry pre-check**: Always check for the registry before evaluating any assertion. An absent registry means INCONCLUSIVE for the entire run, not just affected steps.
- **Skipping checksum verification**: Verify SHA-256 for each evidence item before treating it as reliable. A mismatch is not a minor issue — it means evidence integrity is uncertain.
