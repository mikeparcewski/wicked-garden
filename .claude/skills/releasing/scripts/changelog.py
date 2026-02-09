#!/usr/bin/env python3
"""
Generate changelog from git commit history.

Usage:
    python changelog.py <component-path> [--since <tag>] [--format <format>]

Formats:
    markdown (default), json, plain
"""

import subprocess
import re
import sys
import json
from datetime import datetime
from typing import List, Dict, Any


def get_commits_since(tag: str = None) -> List[Dict[str, str]]:
    """Get commits since specified tag or all commits."""
    if tag:
        cmd = ["git", "log", f"{tag}..HEAD", "--pretty=format:%H|%s|%an|%ai"]
    else:
        cmd = ["git", "log", "--pretty=format:%H|%s|%an|%ai"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return parse_commits(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to get git commits: {e}", file=sys.stderr)
        return []


def parse_commits(output: str) -> List[Dict[str, str]]:
    """Parse git log output into structured commits."""
    commits = []
    for line in output.strip().split('\n'):
        if not line:
            continue
        parts = line.split('|')
        if len(parts) == 4:
            commits.append({
                'hash': parts[0],
                'message': parts[1],
                'author': parts[2],
                'date': parts[3]
            })
    return commits


def categorize_commit(message: str) -> str:
    """Categorize commit by type."""
    if re.search(r'(BREAKING CHANGE|!):', message):
        return 'breaking'
    elif message.startswith('feat'):
        return 'feature'
    elif message.startswith('fix'):
        return 'fix'
    elif message.startswith('docs'):
        return 'docs'
    elif message.startswith('test'):
        return 'test'
    elif message.startswith('refactor'):
        return 'refactor'
    else:
        return 'chore'


def generate_markdown(commits: List[Dict[str, str]], version: str = "Unreleased") -> str:
    """Generate markdown changelog."""
    lines = [f"## [{version}] - {datetime.now().strftime('%Y-%m-%d')}", ""]

    categories = {
        'breaking': ('Breaking Changes', []),
        'feature': ('Features', []),
        'fix': ('Bug Fixes', []),
        'docs': ('Documentation', []),
        'test': ('Tests', []),
        'refactor': ('Refactoring', []),
        'chore': ('Chores', [])
    }

    for commit in commits:
        category = categorize_commit(commit['message'])
        categories[category][1].append(commit)

    for cat_key, (cat_name, cat_commits) in categories.items():
        if cat_commits:
            lines.append(f"### {cat_name}")
            for commit in cat_commits:
                short_hash = commit['hash'][:7]
                lines.append(f"- {commit['message']} ({short_hash})")
            lines.append("")

    return "\n".join(lines)


def generate_json(commits: List[Dict[str, str]], version: str = "Unreleased") -> str:
    """Generate JSON changelog."""
    categorized = {}

    for commit in commits:
        category = categorize_commit(commit['message'])
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(commit)

    output = {
        "version": version,
        "date": datetime.now().isoformat(),
        "changes": categorized
    }

    return json.dumps(output, indent=2)


def generate_plain(commits: List[Dict[str, str]], version: str = "Unreleased") -> str:
    """Generate plain text changelog."""
    lines = [f"{version} - {datetime.now().strftime('%Y-%m-%d')}", ""]

    for commit in commits:
        lines.append(f"  - {commit['message']} ({commit['hash'][:7]})")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python changelog.py <component-path> [--since <tag>] [--format <format>]")
        sys.exit(1)

    component_path = sys.argv[1]
    since_tag = None
    output_format = "markdown"

    # Parse arguments
    for i, arg in enumerate(sys.argv[2:]):
        if arg == "--since" and i + 2 < len(sys.argv):
            since_tag = sys.argv[i + 3]
        elif arg == "--format" and i + 2 < len(sys.argv):
            output_format = sys.argv[i + 3]

    # Get commits
    commits = get_commits_since(since_tag)

    if not commits:
        print("No commits found.")
        sys.exit(0)

    # Generate changelog
    if output_format == "json":
        print(generate_json(commits))
    elif output_format == "plain":
        print(generate_plain(commits))
    else:
        print(generate_markdown(commits))


if __name__ == "__main__":
    main()
