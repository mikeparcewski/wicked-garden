# Scenario Executor — Prose-Step Interpretation

When a scenario step has no fenced code block, classify it using this decision
tree **in order** — first match wins.

## 1. Slash Command Reference

**Signal**: step mentions `/wicked-garden:*` or `/wicked-*`

**Action**: extract the command and args, invoke via Skill tool.

```
Skill(skill="wicked-garden:{domain}:{command}", args="{args}")
```

**Example**: "Run `/wicked-garden:smaht:debug`"
→ `Skill(skill="wicked-garden:smaht:debug")`

## 2. Prompt Submission

**Signal**: step says "send", "submit", "ask", "prompt", or quotes a user
message to process.

**Action**: this is a user prompt to process through smaht. v6 replaced the
push-model orchestrator (deleted in #428) with a pull-model — invoke the
`wicked-garden:smaht:smaht` command or call brain directly:

```bash
# Pull-model: brain search is the default "gather" action
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import json, urllib.request, os
port = int(os.environ.get('WICKED_BRAIN_PORT', '4242'))
req = urllib.request.Request(f'http://localhost:{port}/api',
    data=json.dumps({'action':'search','params':{'query':'the prompt text'}}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
print(urllib.request.urlopen(req, timeout=5).read().decode())
"
```

If the step is about routing only (not full context), skip — there is no HOT/FAST/SLOW
router in v6. The caller picks which adapters to invoke.

## 3. Verification / Assertion

**Signal**: step says "verify", "check", "confirm", "expect", "should",
"assert", "must".

**Action**: run the relevant status/debug command and check output against the
expected condition.

- For smaht state: `Skill(skill="wicked-garden:smaht:debug")` or read session files
- For crew state: `Skill(skill="wicked-garden:crew:status")`
- For memory: `Skill(skill="wicked-garden:mem:recall", args="query")`
- For file content: use Read/Grep tools

Parse the output; compare against the stated expectation; PASS if met, FAIL if not.

## 4. Observation / Inspection

**Signal**: step says "observe", "look at", "inspect", "examine", "review".

**Action**: run the relevant debug/status command and capture its output for
subsequent verification steps.

- For smaht: `Skill(skill="wicked-garden:smaht:debug")`
- For crew: `Skill(skill="wicked-garden:crew:status")`
- For native tasks: read session tasks under `${CLAUDE_CONFIG_DIR}/tasks/{session_id}/`
  and filter by `metadata.event_type`
- For files/logs: use Read tool on the specified path

Record the captured output as evidence for the step result.

## 5. Session Lifecycle

**Signal**: step says "start a session", "open a new session", "begin a session",
"session startup".

**Action**: run the bootstrap hook script directly:

```bash
echo '{"session_id": "scenario-test-'$$'"}' | \
  sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" \
  "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/bootstrap.py"
```

## 6. Fallback — Best Interpretation

**Signal**: none of the above matched.

**Action**: execute your best interpretation. Analyze the prose for:
- What action is being described (the verb)
- What system/component is involved (the noun)
- What the expected outcome is (after "expected", "should", "result")

Then execute using the most appropriate tool (Bash, Skill, Read, Grep, Write).

**NEVER mark as SKIPPED.** Use MANUAL only for steps that are truly
non-automatable (e.g., "have a human review this"). Even UI checks can often
be automated with `agent-browser snapshot` or `curl`.

## Common Prose Patterns

| Prose pattern | Action |
|---------------|--------|
| "Run `/wicked-garden:X:Y`" | `Skill(skill="wicked-garden:X:Y")` |
| "Verify output contains X" | Check previous output or re-run command, grep for X |
| "Check that field F has value V" | Run debug/status, parse output |
| "Expected: list includes A, B" | Run query command, verify A and B appear |
| "Submit this prompt: ..." | Invoke underlying skill or orchestrator script |
| "Observe the session startup" | Run `/wicked-garden:smaht:debug` |
| "Configure X to Y" | Run the relevant config/setup command |
| "Visually inspect the page" | `agent-browser open <url> && agent-browser snapshot` or `curl -sf <url>` |
| "Open a new session" | Run session init script or invoke `smaht:debug` to verify state |
| "Check the UI renders correctly" | Capture DOM snapshot, grep for expected elements |
| "Verify no errors in console" | Check stderr, log files, or debug output for error patterns |

## Prose Interpretation Principles

1. **Identify the action**: what is the step asking you to do?
2. **Identify the expected outcome**: what should the result look like?
3. **Execute and verify**: run the action, then check the outcome
4. **Never SKIP**: you have tools for everything. If a step says "observe the UI",
   use `agent-browser snapshot` or `curl`. If it says "visually verify", capture
   a screenshot or DOM snapshot and check for expected elements.
