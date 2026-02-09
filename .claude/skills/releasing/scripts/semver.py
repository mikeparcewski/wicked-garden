#!/usr/bin/env python3
"""
Semantic versioning utilities.

Usage:
    python semver.py bump <version> <type>
    python semver.py compare <version1> <version2>
    python semver.py validate <version>
"""

import re
import sys
from typing import Tuple, Optional


class SemVer:
    """Semantic version parser and manipulator."""

    PATTERN = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$'

    def __init__(self, version: str):
        match = re.match(self.PATTERN, version)
        if not match:
            raise ValueError(f"Invalid semantic version: {version}")

        self.major = int(match.group(1))
        self.minor = int(match.group(2))
        self.patch = int(match.group(3))
        self.prerelease = match.group(4)
        self.build = match.group(5)

    def bump(self, bump_type: str) -> 'SemVer':
        """Bump version by type."""
        if bump_type == 'major':
            return SemVer(f"{self.major + 1}.0.0")
        elif bump_type == 'minor':
            return SemVer(f"{self.major}.{self.minor + 1}.0")
        elif bump_type == 'patch':
            return SemVer(f"{self.major}.{self.minor}.{self.patch + 1}")
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    def __lt__(self, other: 'SemVer') -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __eq__(self, other: 'SemVer') -> bool:
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __gt__(self, other: 'SemVer') -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)


def validate_version(version: str) -> bool:
    """Validate if string is valid semantic version."""
    try:
        SemVer(version)
        return True
    except ValueError:
        return False


def compare_versions(v1: str, v2: str) -> int:
    """Compare two versions. Returns -1, 0, or 1."""
    try:
        ver1 = SemVer(v1)
        ver2 = SemVer(v2)
        if ver1 < ver2:
            return -1
        elif ver1 > ver2:
            return 1
        else:
            return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python semver.py <command> [args]")
        print("Commands:")
        print("  bump <version> <type>    - Bump version (major/minor/patch)")
        print("  compare <v1> <v2>        - Compare versions")
        print("  validate <version>       - Validate version format")
        sys.exit(1)

    command = sys.argv[1]

    if command == "bump":
        if len(sys.argv) < 4:
            print("Usage: python semver.py bump <version> <type>")
            sys.exit(1)

        version = sys.argv[2]
        bump_type = sys.argv[3]

        try:
            semver = SemVer(version)
            new_version = semver.bump(bump_type)
            print(new_version)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: python semver.py compare <v1> <v2>")
            sys.exit(1)

        v1 = sys.argv[2]
        v2 = sys.argv[3]

        result = compare_versions(v1, v2)
        if result < 0:
            print(f"{v1} < {v2}")
        elif result > 0:
            print(f"{v1} > {v2}")
        else:
            print(f"{v1} == {v2}")

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Usage: python semver.py validate <version>")
            sys.exit(1)

        version = sys.argv[2]
        if validate_version(version):
            print(f"Valid: {version}")
            sys.exit(0)
        else:
            print(f"Invalid: {version}")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
