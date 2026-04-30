# Worktree Recipes

Detection, salvage, and verification commands for the three worktree failure modes.

## 1. Verify a subagent commit landed in main

Use `origin/main` (not `HEAD`) so a checked-out feature branch doesn't false-positive. Run `git fetch origin main` first if origin is stale.

```bash
git merge-base --is-ancestor <sha> origin/main && echo "in main" || echo "DANGLING"
```

If DANGLING: re-commit working-tree changes yourself, or `git cherry-pick <sha>` to bring the dangling commit forward.

## 2. Find orphan branches with unique work (no worktree on disk)

```bash
# Local branches with unique commits not in main
git for-each-ref refs/heads/ --format='%(refname:short)' \
  | xargs -I{} sh -c 'unique=$(git rev-list --count origin/main..{} 2>/dev/null); [ "${unique:-0}" -gt 0 ] && echo "{}: $unique unique"'

# Remote crew/* branches with unique commits not in main
git for-each-ref refs/remotes/origin/crew/ --format='%(refname:short)' \
  | xargs -I{} sh -c 'unique=$(git rev-list --count origin/main..{} 2>/dev/null); [ "${unique:-0}" -gt 0 ] && echo "{}: $unique unique"'
```

Each such branch needs an explicit salvage decision — do NOT bulk-delete on the assumption that "no worktree = no work".

## 3. Find and preserve dangling commits before gc

`git gc` runs after default 14-day grace (`gc.pruneExpire`); after that, dangling commit objects are unreachable forever.

```bash
# List dangling commits
git fsck --no-reflogs --lost-found 2>&1 | grep "dangling commit"

# Inspect one (shows tree + parent + message)
git show <sha> --stat | head -20

# Preserve one before gc takes it
git branch salvage-<topic> <sha>
git push origin salvage-<topic>
```

## 4. Safe delete of worktree + branch

Only delete after step 1 returns empty.

```bash
# 1. Verify content is in main (MUST be empty before proceeding)
git log origin/main..<branch-name> --oneline

# 2. Then delete (only if step 1 was empty)
git worktree unlock <path> 2>/dev/null   # in case it's locked
git worktree remove --force <path>
git branch -D <branch-name>
```

## 5. Salvage classification (per candidate branch)

Use ancestry-based checks, NOT tree-identity diffs. Main may have advanced past a fully-merged branch; tree-identity will lie about it.

| Verdict | Signal | Action |
|---------|--------|--------|
| **ALREADY_MERGED** | `git log origin/main..<branch>` empty AND `git cherry -v` shows zero `+` rows | Safe to delete using §4 |
| **SALVAGEABLE** | `git cherry -v origin/main <branch>` shows `+` rows | Do not delete; produce extract plan; delete only after extraction lands on main |
| **DEAD** | Abandoned with no useful changes | Delete branch + log the deletion (subject + date) |

`git cherry -v` is more reliable than subject-grepping — it shows patch equivalence even when squash + cherry-pick changed the commit message text.

`git rev-list --count origin/main..<branch>` returns the count of unique-by-ancestry commits — supporting context, not a verdict on its own.

## 6. Re-land work after a dangling commit + unstaged changes

This combination shows up when a subagent edited shared files (which the main worktree sees as unstaged) before making its commit (which lands in the worktree's branch). Both halves need attention:

```bash
# Check if the working tree has uncommitted changes from the subagent
git status -s

# If yes, and they look like the fix the subagent claimed:
git diff --stat                                    # confirm scope is right
# Run project-specific verification — typecheck / build / unit tests as appropriate
# (e.g. `npx tsc --noEmit`, `cargo check`, `pytest`, `go test ./...`, etc.)
git add <files> && git commit -m "..."
```

You're effectively re-landing the subagent's work as your own commit because the subagent's worktree commit is unreachable.

## 7. Manual extraction beats cherry-pick on noisy branches

When a candidate branch has 70k+ LOC of regenerated noise (lockfiles, brain-index json, snapshot files) plus a few hundred LOC of real work, `git cherry-pick` drags everything. Manual file-by-file extraction keeps only the substantive change set.
