---
name: decisioning
title: File-Aware Smart Decisioning Scoring
description: Verify --files flag elevates complexity for high-impact file paths and preserves backward compatibility
type: testing
difficulty: beginner
estimated_minutes: 8
---

# File-Aware Smart Decisioning Scoring

This scenario verifies that passing file paths to `smart_decisioning.py` via `--files` produces
equal or higher complexity scores compared to text-only analysis, that TIER 1 file paths
(hooks, commands) produce maximum impact bonuses, and that the absence of the flag preserves
the original behavior exactly.

## Setup

```bash
# Verify smart_decisioning.py is available and supports --files
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json "test" > /dev/null 2>&1 \
  && echo "smart_decisioning.py available" || echo "NOT FOUND — ensure T6-1 is deployed"

python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json "test" --files "" > /dev/null 2>&1 \
  && echo "--files flag available" || echo "--files NOT available — T6-1 not yet deployed"
```

## Steps

### 1. Capture text-only baseline

```bash
BASELINE=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Fix a small config issue" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

echo "Baseline score: ${BASELINE}"
```

Record BASELINE for comparison in Steps 2 and 3.

### 2. TIER 1 hook files elevate score to >= 3

```bash
HOOK_SCORE=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Fix a small config issue" \
  --files "hooks/scripts/bootstrap.py,hooks/scripts/prompt_submit.py" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

echo "Hook file score: ${HOOK_SCORE}"
python3 -c "
baseline = ${BASELINE}
hook = ${HOOK_SCORE}
print('ELEVATED' if hook >= 3 else 'NOT_ELEVATED')
print('GTE_BASELINE' if hook >= baseline else 'BELOW_BASELINE')
"
```

**Expected**: `ELEVATED` and `GTE_BASELINE`

### 3. Non-matching file paths produce no bonus

```bash
DOC_SCORE=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Fix a small config issue" \
  --files "docs/README.md,notes/scratch.txt" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

echo "Doc file score: ${DOC_SCORE}"
python3 -c "
baseline = ${BASELINE}
doc = ${DOC_SCORE}
print('UNCHANGED' if doc == baseline else f'CHANGED (was {baseline}, now {doc})')
"
```

**Expected**: `UNCHANGED`

### 4. Single TIER 1 file (hooks.json) elevates score

```bash
HOOKS_JSON_SCORE=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Update hook event bindings" \
  --files "hooks/hooks.json" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

echo "hooks.json score: ${HOOKS_JSON_SCORE}"
[ "${HOOKS_JSON_SCORE}" -ge 3 ] && echo "TIER1_BONUS_APPLIED" || echo "TIER1_BONUS_MISSING"
```

**Expected**: `TIER1_BONUS_APPLIED`

### 5. Empty --files string does not crash

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Update something" --files "" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('VALID_OUTPUT' if d else 'INVALID')"
echo "Exit: $?"
```

**Expected**: `VALID_OUTPUT`, exit code 0

### 6. No --files flag is stable across two runs

```bash
SCORE1=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Fix a small typo in the documentation" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

SCORE2=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Fix a small typo in the documentation" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

echo "Scores: ${SCORE1} ${SCORE2}"
[ "${SCORE1}" = "${SCORE2}" ] && echo "STABLE" || echo "UNSTABLE"
```

**Expected**: `STABLE`

### 7. Mixed TIER 1 and unmatched files — TIER 1 wins

```bash
MIXED_SCORE=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/crew/smart_decisioning.py" --json \
  "Fix a small config issue" \
  --files "hooks/scripts/bootstrap.py,docs/README.md,notes/scratch.txt" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('complexity_score', d.get('complexity', 0)))")

echo "Mixed score: ${MIXED_SCORE}"
[ "${MIXED_SCORE}" -ge 3 ] && echo "TIER1_DOMINATES" || echo "TIER1_LOST"
```

**Expected**: `TIER1_DOMINATES`

## Expected Outcome

The file scoring mechanism provides a consistent uplift for changes to high-impact files,
ensuring that "fix a small bug in bootstrap.py" is never scored the same as "fix a typo
in README.md." The backward compatibility guarantee means no existing projects are
re-scored unexpectedly.

## Success Criteria

- [ ] --files with TIER 1 hook paths produces complexity >= 3
- [ ] File-enriched score >= text-only score for same description
- [ ] Non-matching file paths produce no score change versus text-only
- [ ] --files "" (empty string) does not crash, returns valid JSON output
- [ ] No --files flag produces same score as before the change (backward compatible)
- [ ] hooks.json as single file elevates impact to TIER 1 level
- [ ] Mixed TIER 1 and unmatched files: TIER 1 score applies (max wins)

## Value Demonstrated

Before this change, a description like "update config" would score low regardless of whether
it touched hooks/scripts/bootstrap.py (the most impactful file in the plugin) or a README.
File-aware scoring ensures that the complexity assessment reflects actual blast radius, not
just keyword density in the task description.

## Cleanup

No cleanup needed.
