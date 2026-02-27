#!/usr/bin/env python3
"""
Release tool for the wicked-garden unified plugin.

Since the repo is a single plugin, this script releases from the repo root.
The --changed flag checks if there are any changes since the last tag.

Usage:
    python batch_release.py --changed              # Release if changed
    python batch_release.py --changed --dry-run    # Preview release
    python batch_release.py --bump patch           # Force bump type

Examples:
    python batch_release.py --changed --dry-run
    python batch_release.py --bump minor
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add scripts directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from release import ReleaseManager
from semver import SemVer


def get_repo_root() -> Path:
    """Get the git repo root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def has_changes_since_tag(repo_root: Path) -> Dict:
    """Check if the unified plugin has changes since its last release tag."""
    rm = ReleaseManager(str(repo_root))
    last_tag = rm.get_last_tag()
    current_version = rm.get_current_version()
    plugin_name = rm.get_plugin_name()

    if last_tag:
        # Check for changes since last tag (excluding .claude/ dev tools)
        result = subprocess.run(
            ["git", "diff", "--name-only", last_tag, "HEAD", "--",
             str(repo_root / "commands"),
             str(repo_root / "agents"),
             str(repo_root / "skills"),
             str(repo_root / "hooks"),
             str(repo_root / "scripts"),
             str(repo_root / "scenarios"),
             str(repo_root / ".claude-plugin"),
             ],
            capture_output=True, text=True,
        )
        changed_files = [f for f in result.stdout.strip().split("\n") if f.strip()]
    else:
        # No tag = never released
        changed_files = ["(never released)"]

    if changed_files:
        return {
            "name": plugin_name,
            "path": str(repo_root),
            "current_version": current_version,
            "last_tag": last_tag,
            "changed_files": len(changed_files),
        }

    return None


def run_release(plugin_path: str, bump: Optional[str], dry_run: bool) -> Dict:
    """Run release.py for the plugin."""
    cmd = [sys.executable, str(script_dir / "release.py"), plugin_path]
    if bump:
        cmd.extend(["--bump", bump])
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main():
    parser = argparse.ArgumentParser(description="Release the wicked-garden plugin")
    parser.add_argument("--changed", action="store_true", help="Release only if changed since last tag")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], help="Force bump type")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    repo_root = get_repo_root()

    # Check for changes
    if args.changed:
        target = has_changes_since_tag(repo_root)
        if not target:
            if args.json:
                print(json.dumps({"targets": [], "message": "No changes since last release."}))
            else:
                print("No changes since last release.")
            return
    else:
        rm = ReleaseManager(str(repo_root))
        target = {
            "name": rm.get_plugin_name(),
            "path": str(repo_root),
            "current_version": rm.get_current_version(),
            "last_tag": rm.get_last_tag(),
            "changed_files": -1,
        }

    # In JSON mode, output only valid JSON and exit
    if args.json:
        print(json.dumps({
            "targets": [target],
            "dry_run": args.dry_run,
            "bump": args.bump,
        }, indent=2))
        return

    # Show plan
    tag_info = target["last_tag"] or "(never tagged)"
    files_info = f", {target['changed_files']} files changed" if target["changed_files"] >= 0 else ""

    print(f"\n{'DRY RUN: ' if args.dry_run else ''}Release Plan")
    print("=" * 60)
    print(f"Plugin: {target['name']}")
    print(f"Current version: v{target['current_version']} (since: {tag_info}{files_info})")
    if args.bump:
        print(f"Forced bump: {args.bump}")
    print()

    # Execute release
    result = run_release(target["path"], args.bump, args.dry_run)

    if result["returncode"] == 0:
        print(result["stdout"])
        if not args.dry_run:
            print(f"\nDon't forget: git push --tags")
    else:
        print(f"FAILED: {result['stderr']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
