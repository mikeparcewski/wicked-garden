#!/usr/bin/env python3
"""
GitLab Operations CLI - Power utilities for GitLab CLI (glab).

Provides intelligent wrappers for common GitLab operations:
- Pipeline failure analysis with fix suggestions
- MR bulk operations and review queue
- Release automation with changelog generation
"""

import argparse
import json
import subprocess
import sys
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class GLABError(Exception):
    """Custom exception for GitLab CLI errors."""
    pass


def run_glab(args: List[str], check: bool = True) -> Tuple[int, str, str]:
    """Run a glab command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["glab"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        if check and result.returncode != 0:
            raise GLABError(result.stderr.strip() or f"Command failed: glab {' '.join(args)}")
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        raise GLABError("GitLab CLI (glab) not found. Install from https://gitlab.com/gitlab-org/cli")


def run_glab_json(args: List[str]) -> Any:
    """Run glab command expecting JSON output."""
    _, stdout, _ = run_glab(args + ["--output", "json"])
    if not stdout.strip():
        return None
    return json.loads(stdout)


# Error patterns for GitLab CI
KNOWN_ERROR_PATTERNS = {
    r"npm ERR! (code E\d+|ERESOLVE|ENOENT)": {
        "category": "npm",
        "fix": "Try: rm -rf node_modules package-lock.json && npm install"
    },
    r"ModuleNotFoundError: No module named '(\w+)'": {
        "category": "python",
        "fix": "Missing dependency. Add to requirements.txt"
    },
    r"error\[E\d+\]: (.+)": {
        "category": "rust",
        "fix": "Rust compilation error"
    },
    r"Job failed: exit code (\d+)": {
        "category": "exit_code",
        "fix": None
    },
    r"OOMKilled|out of memory": {
        "category": "resources",
        "fix": "Increase runner memory"
    },
    r"Could not resolve host|network unreachable": {
        "category": "network",
        "fix": "Check network connectivity and DNS"
    },
}


def diagnose(project: Optional[str] = None, suggest_fixes: bool = False) -> Dict[str, Any]:
    """Analyze the most recent failed pipeline."""

    # Get pipelines
    cmd = ["ci", "list", "--status", "failed"]
    if project:
        cmd.extend(["--repo", project])

    code, stdout, stderr = run_glab(cmd, check=False)
    if code != 0:
        return {"status": "error", "message": stderr}

    # Parse output (glab ci list doesn't support JSON directly)
    lines = stdout.strip().split('\n')
    if not lines or lines[0].startswith("No"):
        return {"status": "ok", "message": "No failed pipelines found"}

    # Get the first failed pipeline ID from the output
    # Format: "ID    STATUS    REF    ..."
    pipeline_id = None
    for line in lines[1:]:  # Skip header
        parts = line.split()
        if parts:
            pipeline_id = parts[0]
            break

    if not pipeline_id:
        return {"status": "ok", "message": "No failed pipelines found"}

    # Get pipeline jobs
    cmd = ["ci", "view", pipeline_id]
    if project:
        cmd.extend(["--repo", project])
    _, pipeline_output, _ = run_glab(cmd, check=False)

    # Get failed job logs
    cmd = ["ci", "trace", pipeline_id]
    if project:
        cmd.extend(["--repo", project])
    _, logs, _ = run_glab(cmd, check=False)

    # Extract errors
    errors = extract_errors(logs, suggest_fixes)

    return {
        "pipeline_id": pipeline_id,
        "errors": errors,
        "raw_output": pipeline_output[:1000] if pipeline_output else None
    }


def extract_errors(logs: str, suggest_fixes: bool) -> List[Dict[str, Any]]:
    """Extract and categorize errors from logs."""
    errors = []
    seen = set()

    for line in logs.split('\n'):
        line = line.strip()
        if not line:
            continue

        for pattern, info in KNOWN_ERROR_PATTERNS.items():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                error_key = f"{info['category']}:{match.group(0)[:50]}"
                if error_key not in seen:
                    seen.add(error_key)
                    error = {
                        "message": line[:200],
                        "category": info["category"]
                    }
                    if suggest_fixes and info.get("fix"):
                        error["suggested_fix"] = info["fix"]
                    errors.append(error)
                break

    return errors[:20]


def mr_review_queue() -> List[Dict[str, Any]]:
    """List MRs needing review."""
    try:
        result = run_glab_json([
            "mr", "list",
            "--reviewer=@me",
            "--state=opened"
        ])
        return result or []
    except Exception:
        # Fallback to non-JSON
        _, stdout, _ = run_glab(["mr", "list", "--reviewer=@me", "--state=opened"], check=False)
        return [{"raw": stdout}]


def mr_merge_ready(dry_run: bool = True) -> List[Dict[str, Any]]:
    """List MRs that are approved and passing CI."""
    try:
        result = run_glab_json(["mr", "list", "--state=opened"])
        ready = []
        for mr in (result or []):
            # Check if approved and CI passing
            if mr.get("approved") and mr.get("merge_status") == "can_be_merged":
                ready.append(mr)
        return ready
    except Exception:
        _, stdout, _ = run_glab(["mr", "list", "--state=opened"], check=False)
        return [{"raw": stdout}]


def mr_status(mr_id: int, project: Optional[str] = None) -> Dict[str, Any]:
    """Get comprehensive MR status."""
    cmd = ["mr", "view", str(mr_id)]
    if project:
        cmd.extend(["--repo", project])

    try:
        return run_glab_json(cmd)
    except Exception:
        _, stdout, _ = run_glab(cmd, check=False)
        return {"raw": stdout}


def release(bump: str = "patch", dry_run: bool = True, notes: Optional[str] = None,
            project: Optional[str] = None) -> Dict[str, Any]:
    """Create a release with changelog."""

    # Get latest release
    cmd = ["release", "list"]
    if project:
        cmd.extend(["--repo", project])
    _, releases_output, _ = run_glab(cmd, check=False)

    # Parse version from first line
    last_tag = None
    for line in releases_output.strip().split('\n'):
        if line and not line.startswith("NAME"):
            parts = line.split()
            if parts:
                last_tag = parts[0]
                break

    # Calculate new version
    new_version = calculate_version(last_tag, bump)

    changelog = notes or f"Release {new_version}"

    result = {
        "previous_version": last_tag,
        "new_version": new_version,
        "changelog": changelog,
        "dry_run": dry_run
    }

    if not dry_run:
        cmd = ["release", "create", new_version, "--notes", changelog]
        if project:
            cmd.extend(["--repo", project])
        run_glab(cmd)
        result["released"] = True

    return result


def calculate_version(current: Optional[str], bump: str) -> str:
    """Calculate next version."""
    if not current:
        return "v0.1.0"

    match = re.match(r'v?(\d+)\.(\d+)\.(\d+)', current)
    if not match:
        return "v0.1.0"

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    if bump == "major":
        return f"v{major + 1}.0.0"
    elif bump == "minor":
        return f"v{major}.{minor + 1}.0"
    else:
        return f"v{major}.{minor}.{patch + 1}"


def main():
    parser = argparse.ArgumentParser(description="GitLab Operations CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # diagnose
    p = subparsers.add_parser("diagnose", help="Analyze failed pipelines")
    p.add_argument("--project", help="Project path (group/project)")
    p.add_argument("--suggest-fixes", action="store_true")

    # mr-review-queue
    subparsers.add_parser("mr-review-queue", help="List MRs needing review")

    # mr-merge-ready
    p = subparsers.add_parser("mr-merge-ready", help="List MRs ready to merge")
    p.add_argument("--dry-run", action="store_true", default=True)

    # mr-status
    p = subparsers.add_parser("mr-status", help="Get MR status")
    p.add_argument("id", type=int, help="MR ID")
    p.add_argument("--project", help="Project path")

    # release
    p = subparsers.add_parser("release", help="Create a release")
    p.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--notes", help="Release notes")
    p.add_argument("--project", help="Project path")

    args = parser.parse_args()

    try:
        if args.command == "diagnose":
            result = diagnose(args.project, args.suggest_fixes)
        elif args.command == "mr-review-queue":
            result = mr_review_queue()
        elif args.command == "mr-merge-ready":
            result = mr_merge_ready(args.dry_run)
        elif args.command == "mr-status":
            result = mr_status(args.id, args.project)
        elif args.command == "release":
            result = release(args.bump, args.dry_run, args.notes, args.project)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2))

    except GLABError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
