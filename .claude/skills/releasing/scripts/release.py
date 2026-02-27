#!/usr/bin/env python3
"""
Release automation tool for the wicked-garden unified plugin.

Usage:
    python release.py <component-path> [options]

Options:
    --bump <major|minor|patch>  Force specific version bump
    --version <version>         Set specific version
    --dry-run                   Preview changes without applying
    --no-tag                    Skip git tag creation
    --since <tag>               Analyze commits since specific tag

Examples:
    python release.py .
    python release.py . --bump major
    python release.py . --dry-run
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add scripts directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from changelog import categorize_commit, get_commits_since
from semver import SemVer


class ReleaseManager:
    """Manages release workflow for marketplace components."""

    def __init__(self, component_path: str, dry_run: bool = False):
        self.component_path = Path(component_path)
        self.dry_run = dry_run
        self.plugin_json_path = self.component_path / ".claude-plugin" / "plugin.json"

        if not self.component_path.exists():
            raise ValueError(f"Component path does not exist: {component_path}")

    def get_plugin_name(self) -> str:
        """Get plugin name from plugin.json."""
        try:
            with open(self.plugin_json_path, "r") as f:
                data = json.load(f)
                return data.get("name", self.component_path.name)
        except Exception:
            return self.component_path.name

    def get_current_version(self) -> str:
        """Get current version from plugin.json."""
        path = self.plugin_json_path
        if not path.exists():
            # Try alternate location (some plugins use plugin.json at root)
            alt_path = self.component_path / "plugin.json"
            if alt_path.exists():
                path = alt_path
                self.plugin_json_path = alt_path
            else:
                return "0.1.0"  # Default for new components

        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data.get("version", "0.1.0")
        except Exception as e:
            print(f"Warning: Could not read plugin.json: {e}")
            return "0.1.0"

    def get_last_tag(self) -> Optional[str]:
        """Get last git tag for this component."""
        try:
            # Get all tags
            result = subprocess.run(
                ["git", "tag", "-l"], capture_output=True, text=True, check=True
            )

            tags = result.stdout.strip().split("\n")
            component_name = self.get_plugin_name()

            # Filter tags for this component (format: component-name-v1.0.0)
            component_tags = [
                tag for tag in tags if tag.startswith(f"{component_name}-v")
            ]

            if not component_tags:
                return None

            # Sort by semver and return latest
            def extract_version(tag):
                version_str = tag.split("-v")[-1]
                try:
                    return SemVer(version_str)
                except ValueError:
                    return None

            valid_tags = [(tag, extract_version(tag)) for tag in component_tags]
            valid_tags = [(tag, ver) for tag, ver in valid_tags if ver is not None]

            if not valid_tags:
                return None

            valid_tags.sort(key=lambda x: x[1], reverse=True)
            return valid_tags[0][0]

        except subprocess.CalledProcessError:
            return None

    def analyze_commits(self, since_tag: Optional[str] = None) -> Dict[str, List]:
        """Analyze commits and categorize them."""
        commits = get_commits_since(since_tag)

        categorized = {
            "breaking": [],
            "feature": [],
            "fix": [],
            "docs": [],
            "test": [],
            "refactor": [],
            "chore": [],
        }

        for commit in commits:
            category = categorize_commit(commit["message"])
            categorized[category].append(commit)

        return categorized

    def determine_version_bump(self, categorized: Dict[str, List]) -> str:
        """Determine version bump type from categorized commits."""
        if categorized["breaking"]:
            return "major"
        elif categorized["feature"]:
            return "minor"
        elif categorized["fix"]:
            return "patch"
        else:
            return "patch"  # Default to patch for chores/docs

    def update_plugin_version(self, new_version: str):
        """Update version in plugin.json."""
        if self.dry_run:
            print(
                f"[DRY RUN] Would update {self.plugin_json_path} to version {new_version}"
            )
            return

        if not self.plugin_json_path.exists():
            # Try alternate location (some plugins use plugin.json at root)
            alt_path = self.component_path / "plugin.json"
            if alt_path.exists():
                self.plugin_json_path = alt_path
            else:
                print(f"Warning: plugin.json not found at {self.plugin_json_path}")
                return

        try:
            with open(self.plugin_json_path, "r") as f:
                data = json.load(f)

            data["version"] = new_version

            with open(self.plugin_json_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")  # Add trailing newline

            print(f"✓ Updated plugin.json to version {new_version}")
        except Exception as e:
            print(f"Error: Failed to update plugin.json: {e}")
            sys.exit(1)

    def update_marketplace_version(self, new_version: str):
        """Update version in the root marketplace.json catalog."""
        # Find marketplace.json relative to git root
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True
            )
            git_root = Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            git_root = self.component_path.parent.parent  # fallback: plugins/../

        marketplace_path = git_root / ".claude-plugin" / "marketplace.json"
        if not marketplace_path.exists():
            print("  (no marketplace.json found, skipping)")
            return

        if self.dry_run:
            print(f"[DRY RUN] Would update marketplace.json entry to version {new_version}")
            return

        try:
            with open(marketplace_path, "r") as f:
                data = json.load(f)

            component_name = self.get_plugin_name()
            updated = False

            for plugin in data.get("plugins", []):
                if plugin.get("name") == component_name:
                    plugin["version"] = new_version
                    updated = True
                    break

            if updated:
                with open(marketplace_path, "w") as f:
                    json.dump(data, f, indent=2)
                    f.write("\n")
                print(f"✓ Updated marketplace.json to version {new_version}")
            else:
                print(f"  (plugin '{component_name}' not found in marketplace.json)")

        except Exception as e:
            print(f"Warning: Failed to update marketplace.json: {e}")

    def generate_changelog_content(
        self, categorized: Dict[str, List], version: str
    ) -> str:
        """Generate changelog content for this release."""
        lines = [f"## [{version}] - {datetime.now().strftime('%Y-%m-%d')}", ""]

        category_labels = {
            "breaking": "Breaking Changes",
            "feature": "Features",
            "fix": "Bug Fixes",
            "docs": "Documentation",
            "test": "Tests",
            "refactor": "Refactoring",
            "chore": "Chores",
        }

        for cat_key in [
            "breaking",
            "feature",
            "fix",
            "docs",
            "test",
            "refactor",
            "chore",
        ]:
            commits = categorized.get(cat_key, [])
            if commits:
                lines.append(f"### {category_labels[cat_key]}")
                for commit in commits:
                    short_hash = commit["hash"][:7]
                    lines.append(f"- {commit['message']} ({short_hash})")
                lines.append("")

        return "\n".join(lines)

    def update_changelog(self, content: str):
        """Update or create CHANGELOG.md."""
        changelog_path = self.component_path / "CHANGELOG.md"

        if self.dry_run:
            print(f"[DRY RUN] Would update {changelog_path}")
            print("\nChangelog content:")
            print(content)
            return

        existing_content = ""
        if changelog_path.exists():
            with open(changelog_path, "r") as f:
                existing_content = f.read()

            # Remove header if it exists
            if existing_content.startswith("# Changelog"):
                existing_content = existing_content.split("\n", 1)[1].lstrip()

        # Prepend new content
        full_content = f"# Changelog\n\n{content}\n{existing_content}"

        with open(changelog_path, "w") as f:
            f.write(full_content)

        print(f"✓ Updated CHANGELOG.md")

    def create_git_tag(self, version: str):
        """Create git tag for this release."""
        component_name = self.get_plugin_name()
        tag_name = f"{component_name}-v{version}"

        if self.dry_run:
            print(f"[DRY RUN] Would create git tag: {tag_name}")
            return

        try:
            subprocess.run(
                [
                    "git",
                    "tag",
                    "-a",
                    tag_name,
                    "-m",
                    f"Release {component_name} v{version}",
                ],
                check=True,
            )
            print(f"✓ Created git tag: {tag_name}")
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to create git tag: {e}")
            sys.exit(1)

    def generate_release_notes(self, categorized: Dict[str, List], version: str) -> str:
        """Generate release notes."""
        component_name = self.get_plugin_name()
        lines = [
            f"# Release {component_name} v{version}",
            "",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d')}",
            f"**Component**: {component_name}",
            "",
            "## Summary",
            "",
        ]

        # Generate summary
        stats = {
            "breaking": len(categorized.get("breaking", [])),
            "feature": len(categorized.get("feature", [])),
            "fix": len(categorized.get("fix", [])),
        }

        summary_parts = []
        if stats["breaking"] > 0:
            summary_parts.append(f"{stats['breaking']} breaking change(s)")
        if stats["feature"] > 0:
            summary_parts.append(f"{stats['feature']} new feature(s)")
        if stats["fix"] > 0:
            summary_parts.append(f"{stats['fix']} bug fix(es)")

        if summary_parts:
            lines.append("This release includes: " + ", ".join(summary_parts) + ".")
        else:
            lines.append("Maintenance release with minor improvements.")

        lines.extend(["", "## Changes", ""])

        # Add categorized changes
        category_labels = {
            "breaking": "Breaking Changes",
            "feature": "Features",
            "fix": "Bug Fixes",
            "docs": "Documentation",
            "test": "Tests",
            "refactor": "Refactoring",
            "chore": "Chores",
        }

        for cat_key in [
            "breaking",
            "feature",
            "fix",
            "docs",
            "test",
            "refactor",
            "chore",
        ]:
            commits = categorized.get(cat_key, [])
            if commits:
                lines.append(f"### {category_labels[cat_key]}")
                lines.append("")
                for commit in commits:
                    short_hash = commit["hash"][:7]
                    lines.append(f"- {commit['message']} ({short_hash})")
                lines.append("")

        # Add upgrade guide for breaking changes
        if categorized.get("breaking"):
            lines.extend(
                [
                    "## Upgrade Guide",
                    "",
                    "This release contains breaking changes. Please review the breaking changes above and update your code accordingly.",
                    "",
                ]
            )

        lines.extend(
            [
                "## Installation",
                "",
                "```bash",
                "# First, add the wicked-garden marketplace (one-time setup)",
                "claude marketplace add wickedagile/wicked-garden",
                "",
                "# Then install the plugin",
                f"claude plugin install {component_name}@wicked-garden",
                "```",
                "",
            ]
        )

        return "\n".join(lines)

    def save_release_notes(self, content: str, version: str):
        """Save release notes to file, removing old RELEASE-*.md files."""
        notes_path = self.component_path / f"RELEASE-{version}.md"

        if self.dry_run:
            print(f"[DRY RUN] Would save release notes to {notes_path}")
            print("\nRelease notes:")
            print(content)
            return

        # Remove old RELEASE files
        for old in self.component_path.glob("RELEASE-*.md"):
            if old.name != notes_path.name:
                old.unlink()

        with open(notes_path, "w") as f:
            f.write(content)

        print(f"✓ Generated release notes: {notes_path.name}")

    def run_release(
        self,
        bump_type: Optional[str] = None,
        target_version: Optional[str] = None,
        since_tag: Optional[str] = None,
        create_tag: bool = True,
    ) -> Tuple[str, Dict]:
        """Execute full release workflow."""
        print(f"Analyzing component: {self.component_path.name}")
        print()

        # Get current version
        current_version = self.get_current_version()
        print(f"Current version: {current_version}")

        # Get commits since last tag or specified tag
        if since_tag is None:
            last_tag = self.get_last_tag()
            if last_tag:
                print(f"Last tag: {last_tag}")
                since_tag = last_tag
            else:
                print("No previous tags found (first release)")

        # Analyze commits
        print("\nAnalyzing commits...")
        categorized = self.analyze_commits(since_tag)

        # Display commit summary
        total_commits = sum(len(commits) for commits in categorized.values())
        if total_commits == 0:
            print("No commits found since last release.")
            if not self.dry_run:
                sys.exit(0)

        print(f"Found {total_commits} commit(s):")
        for category, commits in categorized.items():
            if commits:
                print(f"  - {category}: {len(commits)}")

        # Determine version
        if target_version:
            new_version = target_version
            print(f"\nTarget version (specified): {new_version}")
        else:
            if bump_type:
                bump = bump_type
                print(f"\nVersion bump (specified): {bump}")
            else:
                bump = self.determine_version_bump(categorized)
                print(f"\nVersion bump (detected): {bump}")

            try:
                semver = SemVer(current_version)
                new_version_obj = semver.bump(bump)
                new_version = str(new_version_obj)
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)

        print(f"New version: {new_version}")

        if self.dry_run:
            print("\n[DRY RUN] Preview of changes:")

        # Update plugin.json
        print()
        self.update_plugin_version(new_version)

        # Update marketplace.json
        self.update_marketplace_version(new_version)

        # Generate and update changelog
        changelog_content = self.generate_changelog_content(categorized, new_version)
        self.update_changelog(changelog_content)

        # Generate release notes
        release_notes = self.generate_release_notes(categorized, new_version)
        self.save_release_notes(release_notes, new_version)

        # Create git tag
        if create_tag:
            self.create_git_tag(new_version)

        print()
        if self.dry_run:
            print("[DRY RUN] No changes were made.")
        else:
            print(f"✓ Release {new_version} complete!")
            print(f"\nNext steps:")
            print(f"  1. Review changes in {self.component_path}")
            print(
                f"  2. Commit changes: git add . && git commit -m 'release: {self.component_path.name} v{new_version}'"
            )
            if create_tag:
                print(
                    f"  3. Push tag: git push origin {self.component_path.name}-v{new_version}"
                )

        return new_version, categorized


def main():
    if len(sys.argv) < 2 or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    component_path = sys.argv[1]

    # Parse options
    dry_run = "--dry-run" in sys.argv
    no_tag = "--no-tag" in sys.argv
    bump_type = None
    target_version = None
    since_tag = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--bump" and i + 1 < len(sys.argv):
            bump_type = sys.argv[i + 1]
            if bump_type not in ["major", "minor", "patch"]:
                print(f"Error: Invalid bump type: {bump_type}")
                print("Must be one of: major, minor, patch")
                sys.exit(1)
            i += 2
        elif arg == "--version" and i + 1 < len(sys.argv):
            target_version = sys.argv[i + 1]
            # Validate version
            try:
                SemVer(target_version)
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
            i += 2
        elif arg == "--since" and i + 1 < len(sys.argv):
            since_tag = sys.argv[i + 1]
            i += 2
        elif arg in ["--dry-run", "--no-tag"]:
            i += 1
        else:
            print(f"Error: Unknown option: {arg}")
            sys.exit(1)

    try:
        manager = ReleaseManager(component_path, dry_run=dry_run)
        manager.run_release(
            bump_type=bump_type,
            target_version=target_version,
            since_tag=since_tag,
            create_tag=not no_tag,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
