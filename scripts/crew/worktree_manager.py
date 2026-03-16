#!/usr/bin/env python3
"""
Worktree Manager — wicked-crew issue #252.

Manages git worktrees for parallel build task execution.

Functions:
    check_capability()       → bool: verifies git state + worktree support
    create_worktree(project, task_id) → str: path to new worktree
    merge_worktree(worktree_path, target_branch) → dict: merge result
    cleanup_worktree(worktree_path) → bool: remove worktree + branch
    list_active_worktrees(project) → list[str]: active worktree paths

Usage:
    python3 worktree_manager.py check-capability
    python3 worktree_manager.py list-worktrees --project my-project
    python3 worktree_manager.py create-worktree --project my-project --task-id task-123
    python3 worktree_manager.py cleanup-worktree --path /tmp/crew-my-project-task-123
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: List[str], cwd: Optional[str] = None, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the completed process.

    Raises subprocess.CalledProcessError on non-zero exit if capture=False,
    otherwise returns the process object for the caller to inspect.
    """
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
    )


def _git_root() -> Optional[str]:
    """Return the git repository root or None if not in a git repo."""
    result = _run(["git", "rev-parse", "--show-toplevel"])
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _is_clean(repo_root: str) -> bool:
    """Return True if the working tree has no uncommitted changes."""
    result = _run(["git", "status", "--porcelain"], cwd=repo_root)
    return result.returncode == 0 and result.stdout.strip() == ""


def _branch_exists(branch_name: str, repo_root: str) -> bool:
    """Return True if the branch exists locally."""
    result = _run(["git", "rev-parse", "--verify", branch_name], cwd=repo_root)
    return result.returncode == 0


def _worktree_branch_name(project: str, task_id: str) -> str:
    """Generate a consistent branch name for a worktree."""
    # Sanitize: replace non-alphanumeric (except - and _) with -
    safe_project = re.sub(r"[^a-zA-Z0-9_-]", "-", project)
    safe_task = re.sub(r"[^a-zA-Z0-9_-]", "-", task_id)
    return f"crew-{safe_project}-{safe_task}"


def _worktree_path(project: str, task_id: str) -> str:
    """Generate a worktree path in the temp directory."""
    branch = _worktree_branch_name(project, task_id)
    tmpdir = os.environ.get("TMPDIR") or __import__("tempfile").gettempdir()
    return f"{tmpdir}/{branch}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_capability() -> bool:
    """Verify that git worktrees are supported and the repo is in a usable state.

    Returns True if:
    - We are inside a git repository
    - git worktree command is available
    - The repo is not in a detached HEAD state (worktrees need a branch)

    Does NOT require a clean working tree — callers can decide whether to
    proceed with uncommitted changes.
    """
    try:
        # Must be in a git repo
        root = _git_root()
        if not root:
            return False

        # git worktree list must succeed (available in git 2.5+)
        result = _run(["git", "worktree", "list", "--porcelain"], cwd=root)
        if result.returncode != 0:
            return False

        # HEAD must point to a branch (not detached)
        head_result = _run(["git", "symbolic-ref", "--short", "HEAD"], cwd=root)
        if head_result.returncode != 0:
            return False

        return True

    except (FileNotFoundError, OSError):
        # git not available
        return False


def create_worktree(project: str, task_id: str, base_branch: Optional[str] = None) -> str:
    """Create a git worktree for parallel build execution.

    Creates a new branch `crew-{project}-{task_id}` from `base_branch`
    (defaults to current HEAD branch) and checks it out in a new worktree
    at `/tmp/crew-{project}-{task_id}`.

    Args:
        project: Project name (used in branch and path name)
        task_id: Task ID string (used in branch and path name)
        base_branch: Branch to base the worktree on. Defaults to current HEAD branch.

    Returns:
        Path to the created worktree directory.

    Raises:
        RuntimeError: If the worktree could not be created.
    """
    root = _git_root()
    if not root:
        raise RuntimeError("Not inside a git repository")

    branch = _worktree_branch_name(project, task_id)
    worktree_path = _worktree_path(project, task_id)

    # Determine base
    if base_branch is None:
        head_result = _run(["git", "symbolic-ref", "--short", "HEAD"], cwd=root)
        if head_result.returncode == 0:
            base_branch = head_result.stdout.strip()
        else:
            base_branch = "main"

    # Create the worktree with a new branch
    cmd = ["git", "worktree", "add", "-b", branch, worktree_path, base_branch]
    result = _run(cmd, cwd=root)

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create worktree '{worktree_path}' from '{base_branch}': "
            f"{result.stderr.strip()}"
        )

    return worktree_path


def merge_worktree(worktree_path: str, target_branch: Optional[str] = None) -> Dict:
    """Merge a worktree branch back to the target branch.

    Performs a three-way merge with conflict detection.

    Args:
        worktree_path: Path to the worktree directory.
        target_branch: Branch to merge into. Defaults to main/master.

    Returns:
        Dict with keys:
            success (bool): True if merge completed without conflicts
            conflicts (list[str]): List of conflicted file paths (empty if clean)
            message (str): Human-readable result summary
            branch (str): The worktree's branch name
    """
    root = _git_root()
    if not root:
        return {"success": False, "conflicts": [], "message": "Not a git repo", "branch": ""}

    worktree_dir = Path(worktree_path)
    if not worktree_dir.exists():
        return {"success": False, "conflicts": [], "message": f"Worktree path not found: {worktree_path}", "branch": ""}

    # Get the worktree's branch name
    branch_result = _run(["git", "symbolic-ref", "--short", "HEAD"], cwd=worktree_path)
    if branch_result.returncode != 0:
        return {"success": False, "conflicts": [], "message": "Could not determine worktree branch", "branch": ""}
    worktree_branch = branch_result.stdout.strip()

    # Determine target branch
    if target_branch is None:
        for candidate in ["main", "master"]:
            if _branch_exists(candidate, root):
                target_branch = candidate
                break
        if target_branch is None:
            target_branch = "main"

    # Checkout target branch in the main worktree and merge
    checkout_result = _run(["git", "checkout", target_branch], cwd=root)
    if checkout_result.returncode != 0:
        return {
            "success": False,
            "conflicts": [],
            "message": f"Failed to checkout {target_branch}: {checkout_result.stderr.strip()}",
            "branch": worktree_branch,
        }

    merge_result = _run(["git", "merge", "--no-ff", worktree_branch], cwd=root)

    if merge_result.returncode == 0:
        return {
            "success": True,
            "conflicts": [],
            "message": f"Merged '{worktree_branch}' into '{target_branch}' successfully",
            "branch": worktree_branch,
        }

    # Conflict: get list of conflicted files
    status_result = _run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=root)
    conflicts = [f.strip() for f in status_result.stdout.splitlines() if f.strip()]

    # Abort the failed merge to leave the repo in a clean state
    _run(["git", "merge", "--abort"], cwd=root)

    return {
        "success": False,
        "conflicts": conflicts,
        "message": (
            f"Merge conflict detected: {len(conflicts)} conflicted files. "
            f"Merge aborted. Escalate to human review."
        ),
        "branch": worktree_branch,
    }


def cleanup_worktree(worktree_path: str) -> bool:
    """Remove a worktree and its associated branch.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        True if cleanup succeeded, False otherwise.
    """
    root = _git_root()
    if not root:
        return False

    worktree_dir = Path(worktree_path)

    # Get branch name before removing worktree
    branch = None
    if worktree_dir.exists():
        branch_result = _run(["git", "symbolic-ref", "--short", "HEAD"], cwd=worktree_path)
        if branch_result.returncode == 0:
            branch = branch_result.stdout.strip()

    # Remove the worktree
    remove_result = _run(["git", "worktree", "remove", "--force", worktree_path], cwd=root)
    removed = remove_result.returncode == 0
    if not removed:
        # Try prune as fallback
        prune_result = _run(["git", "worktree", "prune"], cwd=root)
        removed = prune_result.returncode == 0

    # Delete the branch if found
    if branch:
        _run(["git", "branch", "-D", branch], cwd=root)

    return removed


def list_active_worktrees(project: str) -> List[str]:
    """List active worktrees for a project.

    Filters git worktree list to those matching the `crew-{project}-*` pattern.

    Args:
        project: Project name to filter by.

    Returns:
        List of worktree paths matching the project.
    """
    root = _git_root()
    if not root:
        return []

    result = _run(["git", "worktree", "list", "--porcelain"], cwd=root)
    if result.returncode != 0:
        return []

    # Parse porcelain output: each worktree block starts with "worktree <path>"
    safe_project = re.sub(r"[^a-zA-Z0-9_-]", "-", project)
    prefix = f"crew-{safe_project}-"
    worktrees = []

    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            wt_path = line[len("worktree "):].strip()
            wt_name = Path(wt_path).name
            if wt_name.startswith(prefix):
                worktrees.append(wt_path)

    return worktrees


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage git worktrees for wicked-crew parallel builds")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # check-capability
    subparsers.add_parser("check-capability", help="Check if worktrees are supported")

    # list-worktrees
    list_p = subparsers.add_parser("list-worktrees", help="List active worktrees for a project")
    list_p.add_argument("--project", required=True, help="Project name")
    list_p.add_argument("--json", action="store_true", help="Output as JSON")

    # create-worktree
    create_p = subparsers.add_parser("create-worktree", help="Create a new worktree for a task")
    create_p.add_argument("--project", required=True, help="Project name")
    create_p.add_argument("--task-id", required=True, help="Task ID")
    create_p.add_argument("--base-branch", default=None, help="Base branch (default: current HEAD)")
    create_p.add_argument("--json", action="store_true", help="Output as JSON")

    # merge-worktree
    merge_p = subparsers.add_parser("merge-worktree", help="Merge a worktree branch back to target")
    merge_p.add_argument("--path", required=True, help="Worktree path")
    merge_p.add_argument("--target-branch", default=None, help="Target branch (default: main/master)")
    merge_p.add_argument("--json", action="store_true", help="Output as JSON")

    # cleanup-worktree
    cleanup_p = subparsers.add_parser("cleanup-worktree", help="Remove a worktree and its branch")
    cleanup_p.add_argument("--path", required=True, help="Worktree path")
    cleanup_p.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "check-capability":
        capable = check_capability()
        if getattr(args, "json", False):
            print(json.dumps({"capable": capable}))
        else:
            print("capable" if capable else "not capable")
        sys.exit(0 if capable else 1)

    elif args.command == "list-worktrees":
        worktrees = list_active_worktrees(args.project)
        if getattr(args, "json", False):
            print(json.dumps({"worktrees": worktrees}))
        else:
            for wt in worktrees:
                print(wt)
            if not worktrees:
                print(f"No active worktrees for project: {args.project}")

    elif args.command == "create-worktree":
        try:
            path = create_worktree(args.project, args.task_id, args.base_branch)
            if getattr(args, "json", False):
                print(json.dumps({"path": path, "success": True}))
            else:
                print(path)
        except RuntimeError as e:
            if getattr(args, "json", False):
                print(json.dumps({"success": False, "error": str(e)}))
            else:
                print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "merge-worktree":
        result = merge_worktree(args.path, args.target_branch)
        if getattr(args, "json", False):
            print(json.dumps(result))
        else:
            status = "MERGED" if result["success"] else "CONFLICT"
            print(f"[{status}] {result['message']}")
            if result["conflicts"]:
                print("Conflicted files:")
                for f in result["conflicts"]:
                    print(f"  {f}")
        sys.exit(0 if result["success"] else 1)

    elif args.command == "cleanup-worktree":
        success = cleanup_worktree(args.path)
        if getattr(args, "json", False):
            print(json.dumps({"success": success, "path": args.path}))
        else:
            print("cleaned up" if success else "cleanup failed")
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
