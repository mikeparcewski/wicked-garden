#!/usr/bin/env python3
"""
GitHub Operations CLI - Power utilities for GitHub CLI.

Provides intelligent wrappers for common GitHub operations:
- Smart failure analysis with fix suggestions
- PR bulk operations and review queue
- Release automation with changelog generation
- Repository health checks
"""

import argparse
import json
import subprocess
import sys
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple


class GHError(Exception):
    """Custom exception for GitHub CLI errors."""
    pass


def run_gh(args: List[str], check: bool = True) -> Tuple[int, str, str]:
    """Run a gh command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        if check and result.returncode != 0:
            raise GHError(result.stderr.strip() or f"Command failed: gh {' '.join(args)}")
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        raise GHError("GitHub CLI (gh) not found. Install from https://cli.github.com/")


def run_gh_json(args: List[str]) -> Any:
    """Run gh command expecting JSON output."""
    _, stdout, _ = run_gh(args)
    if not stdout.strip():
        return None
    return json.loads(stdout)


# =============================================================================
# DIAGNOSE - Smart Failure Analysis
# =============================================================================

KNOWN_ERROR_PATTERNS = {
    r"npm ERR! (code E\d+|ERESOLVE|ENOENT)": {
        "category": "npm",
        "fix": "Try: rm -rf node_modules package-lock.json && npm install"
    },
    r"ModuleNotFoundError: No module named '(\w+)'": {
        "category": "python",
        "fix": "Missing dependency. Add to requirements.txt or run: pip install {}"
    },
    r"error\[E\d+\]: (.+)": {
        "category": "rust",
        "fix": "Rust compilation error - check the error message"
    },
    r"FATAL:\s+(.+)": {
        "category": "general",
        "fix": None
    },
    r"Error: Process completed with exit code (\d+)": {
        "category": "exit_code",
        "fix": None
    },
    r"OOMKilled|out of memory": {
        "category": "resources",
        "fix": "Increase runner memory or optimize build"
    },
    r"rate limit|API rate limit": {
        "category": "rate_limit",
        "fix": "Wait for rate limit reset or use authenticated requests"
    },
    r"permission denied|EACCES": {
        "category": "permissions",
        "fix": "Check file permissions or workflow permissions"
    },
    r"timed out|timeout": {
        "category": "timeout",
        "fix": "Increase timeout or optimize slow operations"
    },
}


def diagnose(repo: Optional[str] = None, suggest_fixes: bool = False) -> Dict[str, Any]:
    """Analyze the most recent failed workflow run."""

    # Get most recent failed run
    cmd = ["run", "list", "--status", "failure", "--limit", "1", "--json",
           "databaseId,displayTitle,conclusion,createdAt,url,headBranch,event"]
    if repo:
        cmd.extend(["--repo", repo])

    runs = run_gh_json(cmd)
    if not runs:
        return {"status": "ok", "message": "No failed runs found"}

    run = runs[0]
    run_id = run["databaseId"]

    # Get jobs
    cmd = ["run", "view", str(run_id), "--json", "jobs"]
    if repo:
        cmd.extend(["--repo", repo])
    jobs_data = run_gh_json(cmd)

    failed_jobs = [j for j in jobs_data.get("jobs", [])
                   if j.get("conclusion") not in ("success", "skipped", None)]

    # Get logs for failed jobs
    cmd = ["run", "view", str(run_id), "--log-failed"]
    if repo:
        cmd.extend(["--repo", repo])
    _, logs, _ = run_gh(cmd, check=False)

    # Extract and categorize errors
    errors = extract_errors(logs, suggest_fixes)

    result = {
        "run": {
            "id": run_id,
            "workflow": run["displayTitle"],
            "branch": run.get("headBranch"),
            "event": run.get("event"),
            "url": run["url"],
            "created": run["createdAt"]
        },
        "failed_jobs": [
            {
                "name": j["name"],
                "conclusion": j["conclusion"],
                "duration": calculate_duration(j.get("startedAt"), j.get("completedAt"))
            }
            for j in failed_jobs
        ],
        "errors": errors
    }

    return result


def extract_errors(logs: str, suggest_fixes: bool) -> List[Dict[str, Any]]:
    """Extract and categorize errors from logs."""
    errors = []
    seen = set()

    for line in logs.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Remove ANSI codes and timestamps
        clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
        clean = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*', '', clean)

        for pattern, info in KNOWN_ERROR_PATTERNS.items():
            match = re.search(pattern, clean, re.IGNORECASE)
            if match:
                error_key = f"{info['category']}:{match.group(0)[:50]}"
                if error_key not in seen:
                    seen.add(error_key)
                    error = {
                        "message": clean[:200],
                        "category": info["category"]
                    }
                    if suggest_fixes and info.get("fix"):
                        error["suggested_fix"] = info["fix"]
                    errors.append(error)
                break

    return errors[:20]  # Limit to 20 errors


def calculate_duration(start: Optional[str], end: Optional[str]) -> Optional[str]:
    """Calculate human-readable duration."""
    if not start or not end:
        return None
    try:
        s = datetime.fromisoformat(start.replace('Z', '+00:00'))
        e = datetime.fromisoformat(end.replace('Z', '+00:00'))
        delta = e - s
        minutes = int(delta.total_seconds() // 60)
        seconds = int(delta.total_seconds() % 60)
        return f"{minutes}m {seconds}s"
    except Exception:
        return None


# =============================================================================
# PR OPERATIONS
# =============================================================================

def pr_review_queue() -> List[Dict[str, Any]]:
    """List PRs that need your review."""
    result = run_gh_json([
        "search", "prs",
        "--review-requested=@me",
        "--state=open",
        "--json", "number,title,repository,author,createdAt,url"
    ])
    return result or []


def pr_merge_ready(dry_run: bool = True) -> List[Dict[str, Any]]:
    """List or merge PRs that are approved and passing."""
    # Get approved PRs
    result = run_gh_json([
        "pr", "list",
        "--json", "number,title,state,mergeable,reviewDecision,statusCheckRollup"
    ])

    ready = []
    for pr in (result or []):
        if (pr.get("reviewDecision") == "APPROVED" and
            pr.get("mergeable") == "MERGEABLE"):
            checks = pr.get("statusCheckRollup", [])
            all_passing = all(c.get("conclusion") == "SUCCESS" for c in checks)
            if all_passing or not checks:
                ready.append(pr)

    return ready


def pr_status(pr_number: int, repo: Optional[str] = None) -> Dict[str, Any]:
    """Get comprehensive PR status."""
    cmd = ["pr", "view", str(pr_number), "--json",
           "number,title,state,mergeable,reviewDecision,statusCheckRollup,"
           "additions,deletions,changedFiles,commits,comments,reviews"]
    if repo:
        cmd.extend(["--repo", repo])

    return run_gh_json(cmd)


# =============================================================================
# RELEASE AUTOMATION
# =============================================================================

def release(bump: str = "patch", dry_run: bool = True, notes: Optional[str] = None,
            repo: Optional[str] = None) -> Dict[str, Any]:
    """Create a release with auto-generated changelog."""

    # Get latest release
    cmd = ["release", "list", "--limit", "1", "--json", "tagName,publishedAt"]
    if repo:
        cmd.extend(["--repo", repo])
    releases = run_gh_json(cmd)

    last_tag = releases[0]["tagName"] if releases else None

    # Get commits since last release
    if last_tag:
        _, commits_log, _ = run_gh([
            "api", f"repos/:owner/:repo/compare/{last_tag}...HEAD",
            "--jq", ".commits[].commit.message"
        ], check=False)
    else:
        _, commits_log, _ = run_gh([
            "api", "repos/:owner/:repo/commits",
            "--jq", ".[].commit.message"
        ], check=False)

    commits = [c.split('\n')[0] for c in commits_log.strip().split('\n') if c]

    # Generate changelog
    changelog = generate_changelog(commits)

    # Calculate new version
    new_version = calculate_version(last_tag, bump)

    result = {
        "previous_version": last_tag,
        "new_version": new_version,
        "commits": len(commits),
        "changelog": changelog,
        "dry_run": dry_run
    }

    if not dry_run:
        body = notes + "\n\n" + changelog if notes else changelog
        cmd = ["release", "create", new_version, "--title", new_version,
               "--notes", body]
        if repo:
            cmd.extend(["--repo", repo])
        run_gh(cmd)
        result["released"] = True

    return result


def generate_changelog(commits: List[str]) -> str:
    """Generate changelog from commit messages."""
    features = []
    fixes = []
    other = []

    for msg in commits:
        msg_lower = msg.lower()
        if msg.startswith("feat") or "add" in msg_lower:
            features.append(f"- {msg}")
        elif msg.startswith("fix") or "bug" in msg_lower:
            fixes.append(f"- {msg}")
        elif not msg.startswith("Merge"):
            other.append(f"- {msg}")

    sections = []
    if features:
        sections.append("### Features\n" + "\n".join(features[:10]))
    if fixes:
        sections.append("### Bug Fixes\n" + "\n".join(fixes[:10]))
    if other and len(sections) == 0:
        sections.append("### Changes\n" + "\n".join(other[:10]))

    return "\n\n".join(sections) if sections else "- Minor updates"


def calculate_version(current: Optional[str], bump: str) -> str:
    """Calculate next version based on bump type."""
    if not current:
        return "v0.1.0"

    # Parse version (handles v prefix)
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


# =============================================================================
# REPO HEALTH
# =============================================================================

def health(repo: Optional[str] = None) -> Dict[str, Any]:
    """Check repository health."""
    checks = {}

    # Branch protection
    cmd = ["api", "repos/:owner/:repo/branches/main/protection", "-q", "."]
    if repo:
        cmd = ["api", f"repos/{repo}/branches/main/protection", "-q", "."]

    code, stdout, _ = run_gh(cmd, check=False)
    checks["branch_protection"] = code == 0

    # Open security advisories
    cmd = ["api", "repos/:owner/:repo/security-advisories", "-q", "length"]
    if repo:
        cmd = ["api", f"repos/{repo}/security-advisories", "-q", "length"]
    code, stdout, _ = run_gh(cmd, check=False)
    checks["security_advisories"] = int(stdout.strip() or 0) if code == 0 else "unknown"

    # Dependabot alerts
    cmd = ["api", "repos/:owner/:repo/dependabot/alerts", "-q", "[.[] | select(.state==\"open\")] | length"]
    if repo:
        cmd = ["api", f"repos/{repo}/dependabot/alerts", "-q", "[.[] | select(.state==\"open\")] | length"]
    code, stdout, _ = run_gh(cmd, check=False)
    checks["dependabot_alerts"] = int(stdout.strip() or 0) if code == 0 else "unknown"

    # Recent CI status
    runs = run_gh_json(["run", "list", "--limit", "5", "--json", "conclusion"] +
                       (["--repo", repo] if repo else []))
    if runs:
        failures = sum(1 for r in runs if r.get("conclusion") == "failure")
        checks["recent_ci_failures"] = failures

    return checks


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GitHub Operations CLI - Power utilities for gh",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # diagnose
    p = subparsers.add_parser("diagnose", help="Analyze failed workflow runs")
    p.add_argument("--repo", help="Repository (owner/name)")
    p.add_argument("--suggest-fixes", action="store_true", help="Include fix suggestions")

    # pr-review-queue
    subparsers.add_parser("pr-review-queue", help="List PRs needing your review")

    # pr-merge-ready
    p = subparsers.add_parser("pr-merge-ready", help="List PRs ready to merge")
    p.add_argument("--dry-run", action="store_true", default=True)

    # pr-status
    p = subparsers.add_parser("pr-status", help="Get PR status")
    p.add_argument("number", type=int, help="PR number")
    p.add_argument("--repo", help="Repository (owner/name)")

    # release
    p = subparsers.add_parser("release", help="Create a release")
    p.add_argument("--bump", choices=["major", "minor", "patch"], default="patch")
    p.add_argument("--dry-run", action="store_true", help="Preview without releasing")
    p.add_argument("--notes", help="Additional release notes")
    p.add_argument("--repo", help="Repository (owner/name)")

    # health
    p = subparsers.add_parser("health", help="Check repo health")
    p.add_argument("--repo", help="Repository (owner/name)")

    args = parser.parse_args()

    try:
        if args.command == "diagnose":
            result = diagnose(args.repo, args.suggest_fixes)
        elif args.command == "pr-review-queue":
            result = pr_review_queue()
        elif args.command == "pr-merge-ready":
            result = pr_merge_ready(args.dry_run)
        elif args.command == "pr-status":
            result = pr_status(args.number, args.repo)
        elif args.command == "release":
            result = release(args.bump, args.dry_run, args.notes, args.repo)
        elif args.command == "health":
            result = health(args.repo)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2))

    except GHError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
