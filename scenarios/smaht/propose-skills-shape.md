---
name: propose-skills-shape
title: Session-mined Skill Builder Shape (MVP, #677)
description: Validates the propose-skills MVP — skill exists, helper runs, report file is created, top-3 inline summary present, no network calls
type: integration
difficulty: basic
estimated_minutes: 4
---

# Session-mined Skill Builder Shape (MVP)

Validates the structural shape of the session-mined skill builder MVP shipped
for issue #677. The MVP is intentionally narrow — read-only analyzer over local
session transcripts, markdown report, no scaffolding handoff, no interactive UI.

## Setup

```bash
# Resolve plugin root for direct script invocation
if [ -z "${CLAUDE_PLUGIN_ROOT}" ]; then
  PLUGIN_DIR=$(find "${HOME}/.claude/plugins/cache" -name "plugin.json" -path "*/wicked-garden/*" 2>/dev/null | head -1 | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null)
  if [ -z "$PLUGIN_DIR" ]; then
    PLUGIN_DIR="."
  fi
else
  PLUGIN_DIR="${CLAUDE_PLUGIN_ROOT}"
fi
echo "PLUGIN_DIR=$PLUGIN_DIR"
echo "$PLUGIN_DIR" > "${TMPDIR:-/tmp}/wg-propose-skills-scenario-dir"
```

## Steps

### Step 1: Skill file exists and is under the 200-line limit

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wg-propose-skills-scenario-dir")
SKILL="$PLUGIN_DIR/skills/smaht/propose-skills/SKILL.md"
[ -f "$SKILL" ] || { echo "FAIL: SKILL.md missing at $SKILL"; exit 1; }
LINES=$(wc -l < "$SKILL" | tr -d ' ')
[ "$LINES" -le 200 ] || { echo "FAIL: SKILL.md $LINES lines (>200)"; exit 1; }
echo "PASS: SKILL.md present, $LINES lines"
```

### Step 2: Helper script exists and is stdlib-only

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wg-propose-skills-scenario-dir")
HELPER="$PLUGIN_DIR/scripts/smaht/propose_skills.py"
[ -f "$HELPER" ] || { echo "FAIL: helper missing at $HELPER"; exit 1; }
# Reject any third-party import — the helper must be stdlib-only.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import ast, sys
tree = ast.parse(open('$HELPER').read())
banned = {'requests','httpx','aiohttp','urllib3','numpy','pandas','pydantic'}
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name.split('.')[0] not in banned, f'banned: {alias.name}'
    elif isinstance(node, ast.ImportFrom) and node.module:
        assert node.module.split('.')[0] not in banned, f'banned: {node.module}'
print('PASS: helper imports are stdlib-only')
"
```

### Step 3: Helper produces a markdown report file under TMPDIR

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wg-propose-skills-scenario-dir")
HELPER="$PLUGIN_DIR/scripts/smaht/propose_skills.py"
# Use a project slug that is unlikely to exist (no sessions) so the helper
# emits an empty report rather than processing real user data.
OUT_PATH=$(sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" "$HELPER" --project=__nonexistent_test_project__)
[ -f "$OUT_PATH" ] || { echo "FAIL: report file not created at $OUT_PATH"; exit 1; }
case "$OUT_PATH" in
  "${TMPDIR:-/tmp}"/wg-propose-skills-*.md|/tmp/wg-propose-skills-*.md|/var/folders/*/wg-propose-skills-*.md)
    echo "PASS: report created at $OUT_PATH" ;;
  *) echo "FAIL: report path '$OUT_PATH' not under TMPDIR"; exit 1 ;;
esac
echo "$OUT_PATH" > "${TMPDIR:-/tmp}/wg-propose-skills-scenario-report"
```

### Step 4: Report has the expected sections

```bash
REPORT=$(cat "${TMPDIR:-/tmp}/wg-propose-skills-scenario-report")
grep -q "^# Session-mined skill proposals" "$REPORT" || { echo "FAIL: missing header"; exit 1; }
grep -q "Sessions scanned" "$REPORT" || { echo "FAIL: missing summary line"; exit 1; }
echo "PASS: report has the expected header + summary"
```

### Step 5: Helper performs no network I/O (negative — no socket import)

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wg-propose-skills-scenario-dir")
HELPER="$PLUGIN_DIR/scripts/smaht/propose_skills.py"
# The helper must not import any networking module — verify by AST scan.
sh "${CLAUDE_PLUGIN_ROOT}/scripts/_python.sh" -c "
import ast
tree = ast.parse(open('$HELPER').read())
banned = {'socket','http','urllib','urllib3','httpx','requests','aiohttp','smtplib','ftplib','telnetlib'}
hits = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            top = alias.name.split('.')[0]
            if top in banned:
                hits.append(alias.name)
    elif isinstance(node, ast.ImportFrom) and node.module:
        top = node.module.split('.')[0]
        if top in banned:
            hits.append(node.module)
assert not hits, f'network modules imported: {hits}'
print('PASS: no network imports')
"
```

### Step 6: Slash command exists and references the helper

```bash
PLUGIN_DIR=$(cat "${TMPDIR:-/tmp}/wg-propose-skills-scenario-dir")
CMD="$PLUGIN_DIR/commands/smaht/propose-skills.md"
[ -f "$CMD" ] || { echo "FAIL: command missing at $CMD"; exit 1; }
grep -q "scripts/smaht/propose_skills.py" "$CMD" || { echo "FAIL: command does not invoke the helper"; exit 1; }
grep -q "Top 3 candidates" "$CMD" || { echo "FAIL: command missing inline-summary contract"; exit 1; }
echo "PASS: slash command present and shaped correctly"
```

## Expected Outcome

- `skills/smaht/propose-skills/SKILL.md` is present and ≤200 lines.
- `scripts/smaht/propose_skills.py` is present and stdlib-only (no banned
  third-party or networking imports).
- Running the helper writes a markdown report under `${TMPDIR:-/tmp}/`.
- The report has the standard header + summary line, even when no sessions
  match (graceful empty case).
- `commands/smaht/propose-skills.md` invokes the helper and instructs the
  caller to surface a top-3 inline summary (no auto-scaffolding).

## Success Criteria

- [ ] SKILL.md exists at `skills/smaht/propose-skills/SKILL.md` and is ≤200 lines
- [ ] Helper exists at `scripts/smaht/propose_skills.py` and uses only stdlib
- [ ] Running the helper produces a `wg-propose-skills-*.md` report under TMPDIR
- [ ] Report contains the expected header and summary line
- [ ] Helper has no socket/http/urllib/requests imports (no network calls)
- [ ] Slash command exists at `commands/smaht/propose-skills.md` and references the helper
- [ ] Slash command contract requires a top-3 inline summary (no auto-scaffold)
