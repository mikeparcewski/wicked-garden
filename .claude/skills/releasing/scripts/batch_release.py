#!/usr/bin/env python3
"""
Batch release tool for Wicked Garden marketplace.

Detects which plugins have changed since their last release tag,
and releases them sequentially with auto-detected version bumps.

Usage:
    python batch_release.py --changed              # Release all changed plugins
    python batch_release.py --changed --dry-run    # Preview batch release
    python batch_release.py --plugins p1,p2,p3     # Release specific plugins
    python batch_release.py --bump patch            # Force bump type for all

Examples:
    python batch_release.py --changed --dry-run
    python batch_release.py --plugins wicked-mem,wicked-smaht --bump minor
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


def get_all_plugins(repo_root: Path) -> List[Path]:
    """Get all plugin directories."""
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.exists():
        return []
    return sorted([
        p for p in plugins_dir.iterdir()
        if p.is_dir() and (p / ".claude-plugin" / "plugin.json").exists()
    ])


def get_changed_plugins(repo_root: Path) -> List[Dict]:
    """Find plugins with changes since their last release tag."""
    changed = []

    for plugin_dir in get_all_plugins(repo_root):
        plugin_name = plugin_dir.name
        rm = ReleaseManager(str(plugin_dir))
        last_tag = rm.get_last_tag()
        current_version = rm.get_current_version()

        if last_tag:
            # Check for changes since last tag
            result = subprocess.run(
                ["git", "diff", "--name-only", last_tag, "HEAD", "--", str(plugin_dir)],
                capture_output=True, text=True,
            )
            changed_files = [f for f in result.stdout.strip().split("\n") if f.strip()]
        else:
            # No tag = never released, all files are new
            changed_files = ["(never released)"]

        if changed_files:
            changed.append({
                "name": plugin_name,
                "path": str(plugin_dir),
                "current_version": current_version,
                "last_tag": last_tag,
                "changed_files": len(changed_files),
            })

    return changed


def run_release(plugin_path: str, bump: Optional[str], dry_run: bool) -> Dict:
    """Run release.py for a single plugin."""
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


def generate_commit_message(released: List[Dict]) -> str:
    """Generate aggregate commit message for batch release."""
    count = len(released)
    summaries = []
    for r in released:
        summaries.append(f"- {r['name']} v{r['new_version']}")

    return (
        f"release: bump {count} plugin{'s' if count != 1 else ''}\n\n"
        + "\n".join(summaries)
    )


def main():
    parser = argparse.ArgumentParser(description="Batch release Wicked Garden plugins")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--changed", action="store_true", help="Release all changed plugins")
    group.add_argument("--plugins", type=str, help="Comma-separated plugin names")
    parser.add_argument("--bump", choices=["major", "minor", "patch"], help="Force bump type")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    repo_root = get_repo_root()

    # Determine which plugins to release
    if args.changed:
        targets = get_changed_plugins(repo_root)
        if not targets:
            if args.json:
                print(json.dumps({"targets": [], "message": "No plugins have changes since their last release."}))
            else:
                print("No plugins have changes since their last release.")
            return
    else:
        plugin_names = [n.strip() for n in args.plugins.split(",")]
        targets = []
        for name in plugin_names:
            plugin_dir = repo_root / "plugins" / name
            if not plugin_dir.exists():
                print(f"Warning: Plugin not found: {name}", file=sys.stderr)
                continue
            rm = ReleaseManager(str(plugin_dir))
            targets.append({
                "name": name,
                "path": str(plugin_dir),
                "current_version": rm.get_current_version(),
                "last_tag": rm.get_last_tag(),
                "changed_files": -1,
            })

    # In JSON mode, output only valid JSON and exit
    if args.json:
        print(json.dumps({
            "targets": targets,
            "dry_run": args.dry_run,
            "bump": args.bump,
        }, indent=2))
        return

    # Show human-readable plan
    print(f"\n{'DRY RUN: ' if args.dry_run else ''}Batch Release Plan")
    print("=" * 60)
    print(f"Plugins to release: {len(targets)}")
    if args.bump:
        print(f"Forced bump: {args.bump}")
    print()

    for t in targets:
        tag_info = t["last_tag"] or "(never tagged)"
        files_info = f", {t['changed_files']} files changed" if t["changed_files"] >= 0 else ""
        print(f"  {t['name']} @ v{t['current_version']} (since: {tag_info}{files_info})")

    print()

    # Execute releases
    released = []
    failed = []

    for t in targets:
        print(f"\n--- Releasing {t['name']} ---")
        result = run_release(t["path"], args.bump, args.dry_run)

        if result["returncode"] == 0:
            # Extract new version from output
            new_version = t["current_version"]  # fallback
            for line in result["stdout"].split("\n"):
                if "New version:" in line or "→" in line:
                    parts = line.split()
                    for p in parts:
                        try:
                            SemVer(p)
                            new_version = p
                        except (ValueError, Exception):
                            continue

            released.append({
                "name": t["name"],
                "old_version": t["current_version"],
                "new_version": new_version,
            })
            print(result["stdout"])
        else:
            failed.append({"name": t["name"], "error": result["stderr"]})
            print(f"FAILED: {result['stderr']}", file=sys.stderr)

    # Summary
    print("\n" + "=" * 60)
    print(f"BATCH RELEASE {'(DRY RUN) ' if args.dry_run else ''}SUMMARY")
    print(f"  Released: {len(released)}")
    print(f"  Failed: {len(failed)}")

    if released and not args.dry_run:
        print(f"\nSuggested commit message:")
        print(generate_commit_message(released))
        print(f"\nDon't forget: git push --tags")


if __name__ == "__main__":
    main()
