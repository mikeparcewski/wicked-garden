---
name: worktrees
description: |
  Git worktree hygiene — when to create, how to clean up, and what fails silently.
  Captures three classes of bug that recur with worktree-based agent isolation:
  subagent dangling commits, orphan branches with unique work, and time-sensitive
  dangling-commit garbage collection. Includes detection commands, the salvage
  decision flow, and the trust-but-verify rule for subagent commit reports.

  Use when: a subagent reports a commit SHA, after a worktree-based agent finishes,
  cleaning up `.claude/worktrees/`, salvaging old crew worktrees, "is this branch
  in main?", verifying agent-claimed commits actually landed, planning multi-agent
  parallel work in worktrees.
status: stable
---

# Worktrees

Git worktrees let multiple branches be checked out simultaneously and let
agent runtimes (Claude Code's `Agent({isolation: 'worktree'})`, crew runners,
etc.) make changes in isolation without disturbing the main checkout. Useful —
and a quiet source of three repeating bugs.

## Three failure modes (memorize these)

### 1. Subagent dangling commits

A subagent dispatched into an isolated worktree commits inside that
worktree. The commit lands in the object database but the branch ref
lives only inside the worktree. When the worktree is removed (auto or
manual), the commit becomes **dangling** — reachable only via
`git fsck --no-reflogs --lost-found` until `git gc` collects it
(default 2-week grace via `gc.pruneExpire`).

The subagent reports "Commit SHA: abc1234" in its summary. The main
agent treats that as shipped. Reality: the commit is not in `main`'s
ancestry. The fix code may also be sitting in the main worktree as
**unstaged changes** (because the subagent edited shared files before
its own commit took place — the harness behavior here is fuzzy).

**Trust-but-verify rule** — every time a subagent reports a commit:

```bash
git merge-base --is-ancestor <sha> HEAD && echo "in main" || echo "DANGLING"
```

If DANGLING, the fix didn't land. Either re-commit the working-tree
changes yourself, or `git cherry-pick <sha>` to bring the dangling
commit forward.

### 2. Orphan branches with unique work, no worktree on disk

The CLAUDE.md hygiene contract that ships with most projects covers
the "delete worktree + branch when content is in main" case. It does
NOT cover this:

- Worktree dir is gone (deleted weeks ago, auto-cleaned, etc.)
- Branch (local or `origin/crew/<name>`) still points at commits
  that are NOT in main
- `git worktree list` and `git worktree prune` say nothing about it
- The work is invisible to worktree commands

If you bulk-delete branches because "no worktree means no work", you
silently lose anything between fork-point and tip. Detection:

```bash
# Local branches with unique commits not in main
git for-each-ref refs/heads/ --format='%(refname:short)' \
  | xargs -I{} sh -c 'unique=$(git log origin/main..{} --oneline 2>/dev/null | wc -l); [ "$unique" -gt 0 ] && echo "{}: $unique unique"'

# Remote crew/* branches with unique commits not in main
git for-each-ref refs/remotes/origin/crew/ --format='%(refname:short)' \
  | xargs -I{} sh -c 'unique=$(git log origin/main..{} --oneline 2>/dev/null | wc -l); [ "$unique" -gt 0 ] && echo "{}: $unique unique"'
```

Each such branch needs an explicit salvage decision (see Salvage flow
below). Do NOT bulk-delete on the assumption that "no worktree = no work".

### 3. Dangling commits, no branch ref at all

The commit object exists but no branch points at it. Reachable only
via `git fsck --no-reflogs --lost-found` until `git gc` runs. **Time
sensitive** — once gc runs (default grace: 14 days via
`gc.pruneExpire`), the commit object is unreachable forever.

```bash
# List dangling commits
git fsck --no-reflogs --lost-found 2>&1 | grep "dangling commit"

# Inspect one (shows its tree + parent + message)
git show <sha> --stat | head -20

# Preserve one before gc takes it
git branch salvage-<topic> <sha>
git push origin salvage-<topic>
```

**Decision must be prompt** — there is no third state. Either preserve
or accept the loss.

## Authoritative signal for "is this work safe to delete"

Branch + remote ref state, **not** on-disk worktree presence.
Worktree-dir absence is the LEAST reliable indicator of merge state.

The full safety check before deleting any worktree-or-branch:

```bash
# 1. Verify content is in main (MUST be empty before proceeding)
git log origin/main..<branch-name> --oneline

# 2. Then delete (only if step 1 was empty)
git worktree unlock <path> 2>/dev/null   # in case it's locked
git worktree remove --force <path>
git branch -D <branch-name>
```

## Salvage flow (when you find unique work)

For each candidate branch:

1. **Locate** — `.claude/worktrees/agent-*` and project-specific dirs (e.g.
   `~/.command_iq/worktrees/crew-*`). Run `git worktree list`.
2. **Identify** — branch name + HEAD SHA.
3. **Compare against main**:
   - `git diff <branch>..origin/main` empty → content already in main
   - `git log origin/main --oneline | grep -i <subject-keyword>` matches → squash-merged
   - `git log origin/main..<branch> --oneline` shows commits not in main → unique work
4. **Classify** as one of:
   - **ALREADY_MERGED** — content byte-identical to main or commit subject is in main's log. Safe to delete.
   - **SALVAGEABLE** — orphaned but valuable. Note what's there. Either cherry-pick or extract patterns manually.
   - **DEAD** — abandoned with no useful changes. Delete with note.
5. **For ALREADY_MERGED**: delete using the safety check above.
   **For SALVAGEABLE**: do not delete; produce an extract plan; only delete after extraction lands on main.
   **For DEAD**: delete branch + log the deletion (subject + date).

Manual file-by-file extraction beats `git cherry-pick` when the candidate
branch has 70k+ LOC of regenerated noise (lockfiles, brain index json,
snapshot files) plus a few hundred LOC of real work. Cherry-pick drags
everything; manual extraction keeps only the substantive change set.

## When the subagent reports a commit but the work is partly unstaged

This combination — dangling commit SHA + unstaged changes in main worktree —
shows up when the subagent edited shared files (which the main worktree
sees as unstaged) before making its commit (which lands in the worktree's
branch). Both halves of the work need attention:

```bash
# Check if the working tree has uncommitted changes from the subagent
git status -s

# If yes, and they look like the fix the subagent claimed:
git diff --stat                                    # confirm scope is right
cd packages/<service> && npx tsc --noEmit          # typecheck
# Run any relevant tests to confirm the fix works
git add <files> && git commit -m "..."
```

You're effectively re-landing the subagent's work as your own commit
because the subagent's worktree commit is unreachable.

## Trust-but-verify checklist for subagent reports

Whenever a subagent's summary says "commit SHA: XYZ":

1. `git merge-base --is-ancestor XYZ HEAD` — must return true (exit 0)
2. `git status -s` — should be empty if the commit is real and complete
3. `git show XYZ --stat | head` — confirm the change set matches what the subagent described
4. If any of those fail, the subagent's work needs re-landing or follow-up

Skipping this check has cost time before. The closing comment on a
GitHub issue citing a dangling SHA is misleading future archaeology.

## Cross-references

- The CLAUDE.md "Worktree hygiene" section in projects that use worktree
  isolation should reference this skill instead of redefining the rules.
- This skill complements `wicked-garden:engineering:review` — that
  reviews code changes; this reviews whether the changes actually
  landed where they should.
