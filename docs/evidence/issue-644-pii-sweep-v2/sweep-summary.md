PII sweep summary — issue-644 v2
Generated: 2026-04-25

## Context

Replaces PR #655 (council 5-0 REJECT: incomplete sweep, regression, scope creep).
Branches from origin/main @ 09eab0b.

## Pre-sweep audit

Command: grep -rEn "/Users/" docs/evidence/ > pre-sweep-FULL-grep.txt
Result: 129 hits across 28 files

## Files swept (28)

- docs/evidence/cluster-a-cut-smaht-learn-libs/pytest.txt
- docs/evidence/cluster-a-followup-634/pytest-results.txt
- docs/evidence/cluster-a-followup-636/pii-grep-post.txt  (0 lines changed — 3 exceptions, see below)
- docs/evidence/cluster-a-followup-637/pytest-results.txt
- docs/evidence/cluster-a-mem-zombie-cleanup/fixup-pytest.txt
- docs/evidence/cluster-a-mem-zombie-cleanup/pytest-results.txt
- docs/evidence/cluster-a-mem-zombie-cleanup/stop-hook-smoke-test.txt
- docs/evidence/cluster-a-p1-smaht-rename/cross-ref-grep-post.txt  (././ artifact fixed)
- docs/evidence/pr-5/contract-rendered.md  (sibling wicked-testing path)
- docs/evidence/pr-facilitator-scorer/pytest-output-post-fix.txt
- docs/evidence/pr-facilitator-scorer/pytest-output.txt
- docs/evidence/pr-mem-store-cleanup/pytest.txt
- docs/evidence/pr-v8-2/parity-harness-output.txt
- docs/evidence/pr-v8-2/pytest-daemon.txt
- docs/evidence/pr-v8-3/after-grep-status-writes.txt
- docs/evidence/pr-v8-3/before-grep-status-writes.txt
- docs/evidence/pr-v8-3/migration-rollback-test.txt
- docs/evidence/pr-v8-3/rework-bug-post-fix.txt
- docs/evidence/pr-v8-3/rework-bug-pre-fix.txt
- docs/evidence/pr-v8-4/pytest-daemon.txt
- docs/evidence/pr-v8-4/timeout-proof.txt
- docs/evidence/pr-v8-5/test-flip-proof.txt
- docs/evidence/pr-v8-6/after-grep-old-surfaces.txt
- docs/evidence/pr-v8-6/before-grep-old-surfaces.txt
- docs/evidence/pr-v8-6/pr5-tests-post-rebase.txt
- docs/evidence/pr-v8-6/pr6-tests-post-rebase.txt
- docs/evidence/pr-v8-7/node-without-wt-test-output.txt
- docs/evidence/pr-v8-8/b1-e2e-test-output.txt
- docs/evidence/pr-v8-8/b2-depth-guard-test-output.txt
- docs/evidence/issue-644-pii-sweep-v2/pre-sweep-FULL-grep.txt  (meta-inventory, sanitized inline)

## Transformation passes applied (4-pass)

1. Worktree paths with subpath: `/Users/.../wicked-garden/.claude/worktrees/agent-XXX/<subpath>` → `./<subpath>`
2. Worktree root bare: `/Users/.../wicked-garden/.claude/worktrees/agent-XXX` → `.`
2b. Project root: `/Users/.../wicked-garden/<subpath>` → `./<subpath>`
3. Sibling project paths: `/Users/.../<sibling>/<subpath>` → `~/<sibling>/<subpath>`
4. Generic home: `/Users/...` → `~`

## Post-sweep audit

Command: grep -rEn "/Users/" docs/evidence/ (excluding issue-644-pii-sweep-v2/ meta-files)
Result: 3 hits — all documented exceptions in cluster-a-followup-636/pii-grep-post.txt

## Documented exceptions (3 lines in pii-grep-post.txt)

All three are in `docs/evidence/cluster-a-followup-636/pii-grep-post.txt`. They are NOT
filesystem PII — they are documentation of the sanitization process itself:

1. Line 4: `Command: grep -rEn "/Users/" docs/evidence/cluster-a-p1-smaht-rename/`
   — This is the literal grep command that was run to verify sanitization. The string
   `/Users/` here is the grep PATTERN, not a path.

2. Line 12: `  s|/Users/[^/]+/Projects/wicked-garden/\.claude/worktrees/[^/]+/|./|g`
   — This is the sed substitution pattern used for sanitization. Sanitizing it would
   corrupt the regex character class notation (`[^/]+` → broken).

3. Line 15: `  Additional /Users/ paths exist in other evidence directories (pr-v8-3, pr-v8-4, etc.).`
   — Prose note documenting out-of-scope items in the original PR #636. The string
   `/Users/` here is a prose reference, not a path.

## ././ artifact repair

`docs/evidence/cluster-a-p1-smaht-rename/cross-ref-grep-post.txt` had pre-existing `././`
artifacts from commit 8b8d15b (#642) where the 3-pass regex collapsed
`worktrees/agent-XXX/./CHANGELOG.md` → `././CHANGELOG.md`.
Fixed to `./CHANGELOG.md` (correct relative path form).

Post-fix ././ check: 0 hits across entire docs/evidence/ tree.

## Sibling project paths

One sibling path handled:
  docs/evidence/pr-5/contract-rendered.md line 116:
  `wicked-testing (\`/Users/michael.parcewski/Projects/wicked-testing\`)` →
  `wicked-testing (\`~/wicked-testing\`)`

## Scope discipline

git diff --name-only: 29 files, all in docs/evidence/.
No non-evidence files touched.

## Tests

Baseline (main @ 09eab0b): 5 failed, 1698 passed (pre-existing failures)
This branch: 5 failed, 1698 passed (unchanged)
