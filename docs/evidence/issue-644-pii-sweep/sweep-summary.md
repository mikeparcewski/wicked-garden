# PII Sweep Evidence — Issue #644

Generated: 2026-04-25
Branch: fix/644-pii-sweep
Base commit: 09eab0b

## Scope

Broad PII hygiene sweep across `docs/evidence/` tree. Follows PR #642 which
sanitized 2 files in `docs/evidence/cluster-a-p1-smaht-rename/`.

## Substitution Rules Applied

1. Worktree paths: `/Users/michael.parcewski/Projects/wicked-garden/.claude/worktrees/agent-XXXX/subpath` → `./subpath`
2. Project root paths: `/Users/michael.parcewski/Projects/wicked-garden/subpath` → `./subpath`
3. Generic home paths: `/Users/michael.parcewski/` → `~/` (for non-project paths)

The substitution applies passes in order (most-specific first) to avoid the
`././` collapse bug seen in PR #642's regex approach.

## Files Modified (27)

| File | Lines Changed |
|------|--------------|
| pr-v8-4/pytest-daemon.txt | 2 |
| pr-v8-4/timeout-proof.txt | 2 |
| pr-v8-3/migration-rollback-test.txt | 2 |
| pr-v8-3/after-grep-status-writes.txt | 14 |
| pr-v8-3/before-grep-status-writes.txt | 14 |
| pr-v8-3/rework-bug-post-fix.txt | 2 |
| pr-v8-3/rework-bug-pre-fix.txt | 2 |
| pr-v8-2/parity-harness-output.txt | 2 |
| pr-v8-2/pytest-daemon.txt | 2 |
| pr-v8-5/test-flip-proof.txt | 2 |
| cluster-a-followup-637/pytest-results.txt | 2 |
| pr-facilitator-scorer/pytest-output.txt | 2 |
| pr-facilitator-scorer/pytest-output-post-fix.txt | 2 |
| pr-mem-store-cleanup/pytest.txt | 2 |
| cluster-a-cut-smaht-learn-libs/pytest.txt | 7 |
| pr-v8-7/node-without-wt-test-output.txt | 2 |
| pr-v8-8/b1-e2e-test-output.txt | 2 |
| pr-v8-8/b2-depth-guard-test-output.txt | 2 |
| pr-v8-6/before-grep-old-surfaces.txt | 16 |
| pr-v8-6/pr5-tests-post-rebase.txt | 2 |
| pr-v8-6/after-grep-old-surfaces.txt | 17 |
| pr-v8-6/pr6-tests-post-rebase.txt | 2 |
| cluster-a-followup-634/pytest-results.txt | 6 |
| cluster-a-mem-zombie-cleanup/stop-hook-smoke-test.txt | 1 |
| cluster-a-mem-zombie-cleanup/fixup-pytest.txt | 8 |
| cluster-a-mem-zombie-cleanup/pytest-results.txt | 8 |
| pr-5/contract-rendered.md | 1 |

**Total: 126 lines sanitized across 27 files**

## File Not Modified (intentionally)

`cluster-a-followup-636/pii-grep-post.txt` — contains `/Users/` only in:
- A literal grep command string (line 4, documentation of the grep command used)
- A sed pattern string (line 12, documentation of the technique)
- A prose sentence referencing other directories (line 15)

None of these are actual PII paths — no substitution needed.

## Post-Sweep Verification

```
grep -rEn '/Users/' docs/evidence/ --include='*.txt' --include='*.md' --include='*.json'
```

Result: 3 hits, all in `cluster-a-followup-636/pii-grep-post.txt` (intentional
documentation content — grep command syntax and prose, not username paths).

Exit code: 0 (grep found matches — but they are all intentional, not PII).

## No-Collapse Verification

The regex bug from PR #642 (producing `././CHANGELOG.md`) was avoided by:
- Using Python re.sub with a capture-group approach: `'.' + subpath` (not `'./' + subpath`)
- When subpath is empty string (bare worktree root), returns `'.'` not `'./'`
- When subpath starts with `/`, `'.' + '/subpath'` = `'./subpath'` (correct)
- Pre-verified on all pattern types in dry-run before applying

## Follow-Up Recommendation (out of scope for this PR)

Add a pre-commit hook or `wg-check` rule to catch `/Users/[username]/` patterns
in `docs/evidence/` files before they are committed. Suggested implementation:
a shell check in `.git/hooks/pre-commit` or a new wg-check validation that
greps evidence files for absolute home directory paths.
