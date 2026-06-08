#!/usr/bin/env python3
"""worktree_guard.py — prevent the agent-worktree cwd leak (issue #878).

When a subagent runs with ``isolation: worktree``, the Bash tool's persistent
cwd can drift back to the MAIN repo checkout between calls. Commits then land
on the agent's branch but in the main worktree — silently defeating isolation.
The only post-hoc tell is an unexpected entry in ``git worktree list``.

This guard is invoked from ``pre_tool.py``'s Bash handler. Given the command
and the PreToolUse payload ``cwd``, it returns one of:

  * ``None``                                   — not a worktree agent / no-op
  * ``{"action": "rewrite", "command": ...}``  — anchor execution in the worktree
  * ``{"action": "deny",    "reason":  ...}``  — command explicitly targets main repo

The rewrite prepends ``cd <worktree-root> &&`` so persistent-cwd state cannot
drag a later call into the wrong directory. Claude Code honors ``updatedInput``
for PreToolUse Bash hooks, so the rewrite takes effect transparently.

Contract: **pure and fail-open** — stdlib only, no raises escape ``evaluate``;
any internal error returns ``None`` so the guard can never break an agent run.
Main-repo path is derived generally via ``git rev-parse --git-common-dir`` —
nothing about any specific repo is hardcoded.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess

# Signature of an isolated agent worktree: <main>/.claude/worktrees/agent-<id>.
# Captures everything up to and including the agent-<id> segment, so a cwd that
# is a deeper subdirectory of the worktree still resolves to the worktree root.
_WORKTREE_SIG = re.compile(r"^(.*/\.claude/worktrees/agent-[^/]+)")

# `-C <path>` arguments (git, make, etc.) and a leading `cd <path>`.
_DASH_C = re.compile(r"(?:^|\s)-C\s+(\S+)")
_LEADING_CD = re.compile(r"^\s*cd\s+(\S+)")


def worktree_root(cwd: "str | None") -> "str | None":
    """Return the agent-worktree root if ``cwd`` is inside one, else ``None``."""
    if not cwd:
        return None
    m = _WORKTREE_SIG.match(cwd)
    return m.group(1) if m else None


def _main_repo_root(cwd: str) -> "str | None":
    """Best-effort main-repo root via ``git rev-parse --git-common-dir``.

    From inside a linked worktree the common dir is the MAIN repo's ``.git``;
    its parent is the main repo root. Returns ``None`` on any failure — callers
    must treat an unknown main root as "cannot prove a main-repo reference".
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode != 0:
            return None
        common = out.stdout.strip()
        if not common:
            return None
        if not os.path.isabs(common):
            common = os.path.abspath(os.path.join(cwd, common))
        # common dir is typically ``<main>/.git`` — main root is its parent.
        if os.path.basename(common) == ".git":
            common = os.path.dirname(common)
        return os.path.normpath(common)
    except Exception:
        return None


def _norm(path: str, base: str) -> str:
    """Normalize ``path`` to an absolute path, resolving relatives against ``base``."""
    path = path.strip().strip('"').strip("'")
    if not os.path.isabs(path):
        path = os.path.join(base, path)
    return os.path.normpath(path)


def _references_main_repo(command: str, main_root: "str | None", wt_root: str) -> bool:
    """True if ``command`` explicitly targets the main repo root (not the worktree).

    Compares normalized *full paths* for equality rather than substring matching,
    because the main repo root is a path *prefix* of the worktree root — a naive
    substring check would flag every command.
    """
    if not main_root or main_root == wt_root:
        return False
    candidates = list(_DASH_C.findall(command))
    lead = _LEADING_CD.match(command)
    if lead:
        candidates.append(lead.group(1))
    main_norm = os.path.normpath(main_root)
    for c in candidates:
        if _norm(c, wt_root) == main_norm:
            return True
    return False


def _anchor_prefix(wt_root: str) -> str:
    """The ``cd <worktree> && `` prefix, with the path safely shell-quoted."""
    return f"cd {shlex.quote(wt_root)} && "


def evaluate(command: "str | None", cwd: "str | None") -> "dict | None":
    """Decide what to do with a Bash ``command`` given the PreToolUse ``cwd``.

    Returns a decision dict (``rewrite`` / ``deny``) or ``None`` for a no-op.
    Never raises — fail-open is the contract.
    """
    try:
        if not command or not command.strip():
            return None

        wt_root = worktree_root(cwd)
        if not wt_root or not cwd:
            return None  # normal session — the guard does not engage

        main_root = _main_repo_root(cwd)
        if _references_main_repo(command, main_root, wt_root):
            return {
                "action": "deny",
                "reason": (
                    "[wicked-garden] worktree guard: this command targets the "
                    f"main repo ({main_root}) from inside an isolated worktree "
                    f"({wt_root}). Running it there would defeat worktree "
                    "isolation — changes/commits would land in the wrong "
                    "checkout. Drop the main-repo path / `-C` reference and run "
                    "against the worktree instead."
                ),
            }

        prefix = _anchor_prefix(wt_root)
        if command.lstrip().startswith(prefix):
            return None  # already anchored — idempotent, do not double-prefix

        return {"action": "rewrite", "command": prefix + command}
    except Exception:
        return None  # fail open — never break an agent run
