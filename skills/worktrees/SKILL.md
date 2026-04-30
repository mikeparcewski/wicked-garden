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

Subagent dispatched into an isolated worktree commits inside that worktree. Branch ref lives only in the worktree; when the worktree is removed, the commit is **dangling** — reachable only via `git fsck --no-reflogs --lost-found` until `git gc` collects it (14-day default via `gc.pruneExpire`). The subagent's "Commit SHA: abc1234" report becomes a lie. Code may also be sitting in the main worktree as unstaged changes.

**Trust-but-verify rule** — every time a subagent reports a commit, run the ancestry check from `refs/recipes.md` §1.

### 2. Orphan branches with unique work, no worktree on disk

Worktree dir is gone (auto-cleaned, deleted weeks ago); branch (local or `origin/crew/<name>`) still points at commits NOT in main; `git worktree list` says nothing about it. Bulk-deleting branches because "no worktree = no work" silently loses everything between fork-point and tip.

Detection commands in `refs/recipes.md` §2. Each branch needs an explicit salvage decision (see Salvage flow below).

### 3. Dangling commits, no branch ref at all

Commit object exists but no branch points at it. **Time sensitive** — once `git gc` runs (default grace 14 days), the object is unreachable forever. List + preserve commands in `refs/recipes.md` §3.

**Decision must be prompt** — there is no third state. Either preserve or accept the loss.

## Authoritative signal for "is this work safe to delete"

Branch + remote ref state, **not** on-disk worktree presence. Worktree-dir absence is the LEAST reliable indicator of merge state. Safe-delete recipe in `refs/recipes.md` §4.

## Salvage flow (when you find unique work)

For each candidate branch:

1. **Locate** — `.claude/worktrees/agent-*` and project-specific dirs (e.g. `~/.command_iq/worktrees/crew-*`). Run `git worktree list`.
2. **Identify** — branch name + HEAD SHA.
3. **Classify** using ancestry-based checks (NOT tree-identity diffs — main may have advanced past a fully-merged branch). Verdict table and signals in `refs/recipes.md` §5.
4. **Act** per verdict:
   - **ALREADY_MERGED** → delete using the safety recipe.
   - **SALVAGEABLE** → do not delete; extract plan first; delete only after extraction lands on main.
   - **DEAD** → delete branch + log the deletion (subject + date).

Manual file-by-file extraction often beats `git cherry-pick` on noisy branches — see `refs/recipes.md` §7.

## When the subagent reports a commit but the work is partly unstaged

Dangling commit SHA + unstaged changes in main worktree shows up when the subagent edited shared files (main worktree sees as unstaged) before its own commit (lands in worktree branch). Both halves need attention. Re-landing recipe in `refs/recipes.md` §6.

## Trust-but-verify checklist for subagent reports

Whenever a subagent's summary says "commit SHA: XYZ":

1. `git merge-base --is-ancestor XYZ origin/main` — must return true (exit 0). Use `origin/main` (not `HEAD`); the latter false-positives if you're on a feature branch. `git fetch origin main` first if origin is stale.
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
