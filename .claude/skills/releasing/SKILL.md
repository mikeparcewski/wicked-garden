---
name: release
description: |
  Release management and versioning toolkit for marketplace components.
  Automates changelog generation, semantic versioning, and version bumping from git history.
  Use when preparing releases, generating changelogs, or managing component versions.
---

# Release Tool

Automated release management for Wicked Garden marketplace components.

## Purpose

Streamlines the release process:
- **Changelog generation** - Auto-generate from commit messages
- **Semantic versioning** - Intelligent version bumping (major/minor/patch)
- **Version management** - Update plugin.json, create git tags
- **Release notes** - Template-based release documentation

## Usage

### Interactive Mode

```bash
cd tools/release
python scripts/release.py

# Interactive prompts:
# > Component: plugins/wicked-memory
# > Current version: 0.1.0
# > Changes since last release:
#   - 5 features
#   - 3 bug fixes
#   - 1 breaking change
# > Suggested version: 1.0.0 (major)
# > Proceed? (y/n)

# Result:
# ✓ Updated version to 1.0.0
# ✓ Generated CHANGELOG.md
# ✓ Created git tag v1.0.0
# ✓ Generated release notes
```

### Command Line Mode

```bash
# Auto-detect version bump from commits
python scripts/release.py plugins/wicked-memory

# Specify version bump
python scripts/release.py plugins/wicked-memory --bump major
python scripts/release.py plugins/wicked-memory --bump minor
python scripts/release.py plugins/wicked-memory --bump patch

# Dry run (preview changes)
python scripts/release.py plugins/wicked-memory --dry-run

# Custom version
python scripts/release.py plugins/wicked-memory --version 2.0.0

# Skip git tag
python scripts/release.py plugins/wicked-memory --no-tag

# Generate changelog only
python scripts/changelog.py plugins/wicked-memory > CHANGELOG.md
```

## Semantic Versioning Rules

### Version Format

`MAJOR.MINOR.PATCH` (e.g., `1.2.3`)

- **MAJOR** - Breaking changes, incompatible API changes
- **MINOR** - New features, backwards-compatible functionality
- **PATCH** - Bug fixes, backwards-compatible fixes

### Commit Message Detection

Auto-detect version bump from commit messages:

| Commit Pattern | Version Bump | Example |
|----------------|--------------|---------|
| `BREAKING CHANGE:`, `feat!:`, `fix!:` | major | `feat!: redesign cache API` |
| `feat:`, `feature:` | minor | `feat: add TTL support` |
| `fix:`, `bugfix:` | patch | `fix: handle null keys` |
| `docs:`, `chore:`, `refactor:` | none | `docs: update README` |
| No prefix | patch | `improve error messages` |

### Examples

```bash
# Commits since v0.1.0:
# - feat: add namespace isolation
# - feat: add TTL support
# - fix: resolve race condition
# - docs: update examples

# Auto-detected: MINOR bump (0.1.0 → 0.2.0)

# Commits since v0.2.0:
# - feat!: redesign cache API
# - BREAKING CHANGE: remove deprecated methods

# Auto-detected: MAJOR bump (0.2.0 → 1.0.0)
```

## Changelog Generation

### Commit Categorization

```markdown
# Changelog

## [1.0.0] - 2026-01-13

### Breaking Changes
- feat!: redesign cache API (#45)
- BREAKING CHANGE: remove deprecated set_sync method

### Features
- feat: add namespace isolation (#42)
- feat: add TTL support with auto-expiration (#43)

### Bug Fixes
- fix: resolve race condition in file writes (#44)
- fix: handle null keys gracefully (#46)

### Documentation
- docs: update README with new API examples
- docs: add migration guide for v1.0.0

### Chores
- chore: update dependencies
- refactor: simplify validation logic
```

### Conventional Commits

Supports [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types**:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Code style (formatting, whitespace)
- `refactor` - Code refactoring
- `test` - Add/update tests
- `chore` - Maintenance tasks

**Examples**:
```bash
feat(cache): add namespace isolation

Implement namespace-level access control to prevent
cross-plugin data access.

Closes #42
```

### Custom Changelog Format

Create `tools/release/templates/changelog.md.tpl`:

```markdown
# {{plugin_name}} v{{version}}

Released: {{date}}

## What's New

{{#breaking_changes}}
### ⚠️ Breaking Changes
{{#items}}
- {{message}} ([{{hash}}]({{url}}))
{{/items}}
{{/breaking_changes}}

{{#features}}
### ✨ Features
{{#items}}
- {{message}} ([{{hash}}]({{url}}))
{{/items}}
{{/features}}

{{#fixes}}
### 🐛 Bug Fixes
{{#items}}
- {{message}} ([{{hash}}]({{url}}))
{{/items}}
{{/fixes}}
```

## Release Workflow

### Step-by-Step Process

1. **Collect commits since last release**
   ```python
   commits = get_commits_since_last_tag(component_path)
   ```

2. **Categorize commits**
   ```python
   categorized = categorize_commits(commits)
   # Returns: { 'breaking': [...], 'features': [...], 'fixes': [...] }
   ```

3. **Determine version bump**
   ```python
   bump_type = determine_version_bump(categorized)
   # Returns: 'major' | 'minor' | 'patch'
   ```

4. **Calculate new version**
   ```python
   current = get_current_version(component_path)
   new_version = bump_version(current, bump_type)
   # 0.1.0 + minor → 0.2.0
   ```

5. **Update plugin.json**
   ```python
   update_plugin_version(component_path, new_version)
   ```

6. **Generate changelog**
   ```python
   changelog = generate_changelog(categorized, new_version)
   write_changelog(component_path, changelog)
   ```

7. **Create git tag**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   ```

8. **Generate release notes**
   ```python
   notes = generate_release_notes(categorized, new_version)
   write_release_notes(component_path, notes)
   ```

## Scripts

### changelog.py

Generates changelog from git history.

```python
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
from datetime import datetime

def get_commits_since(tag):
    """Get commits since specified tag."""
    cmd = ["git", "log", f"{tag}..HEAD", "--pretty=format:%H|%s|%an|%ai"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return parse_commits(result.stdout)

def categorize_commit(message):
    """Categorize commit by type."""
    if re.search(r'(BREAKING CHANGE|!):', message):
        return 'breaking'
    elif message.startswith('feat'):
        return 'feature'
    elif message.startswith('fix'):
        return 'fix'
    elif message.startswith('docs'):
        return 'docs'
    else:
        return 'chore'

def generate_markdown(commits, version):
    """Generate markdown changelog."""
    lines = [f"## [{version}] - {datetime.now().strftime('%Y-%m-%d')}", ""]

    categories = {
        'breaking': ('Breaking Changes', []),
        'feature': ('Features', []),
        'fix': ('Bug Fixes', []),
        'docs': ('Documentation', []),
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
```

### semver.py

Semantic version manipulation utilities.

```python
#!/usr/bin/env python3
"""
Semantic versioning utilities.

Usage:
    python semver.py bump <version> <type>
    python semver.py compare <version1> <version2>
    python semver.py validate <version>
"""

import re
from typing import Tuple

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
```

## Release Notes Template

### Standard Template

```markdown
# Release {{version}}

**Date**: {{date}}
**Component**: {{component_name}}

## Summary

{{summary}}

## Changes

{{changelog}}

## Upgrade Guide

{{#breaking_changes}}
### Breaking Changes

{{#items}}
#### {{title}}

**What changed**: {{description}}

**Migration**:
\`\`\`{{language}}
{{migration_code}}
\`\`\`

**Before**:
\`\`\`{{language}}
{{before_code}}
\`\`\`

**After**:
\`\`\`{{language}}
{{after_code}}
\`\`\`
{{/items}}
{{/breaking_changes}}

## Installation

\`\`\`bash
# First, add the wicked-garden marketplace (one-time setup)
claude marketplace add wickedagile/wicked-garden

# Then install the plugin
claude plugin install {{component_name}}@wicked-garden
\`\`\`

## Contributors

{{#contributors}}
- @{{username}} ({{commit_count}} commits)
{{/contributors}}

## Full Changelog

{{repo_url}}/compare/v{{previous_version}}...v{{version}}
```

## Integration

### CI/CD Release Pipeline

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for changelog

      - name: Detect changes
        id: changes
        run: |
          CHANGED=$(git diff --name-only HEAD~1 HEAD | grep -E '^plugins/' | cut -d'/' -f1-2 | sort -u)
          echo "components=$CHANGED" >> $GITHUB_OUTPUT

      - name: Release changed components
        run: |
          for component in ${{ steps.changes.outputs.components }}; do
            python tools/release/scripts/release.py "$component" --auto
          done

      - name: Push tags
        run: git push --tags
```

### Manual Release Checklist

```markdown
## Pre-Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md reviewed
- [ ] Version number approved
- [ ] Breaking changes documented
- [ ] Migration guide written (if breaking)
- [ ] Contributors acknowledged

## Release Steps

1. Run release tool: `python tools/release/scripts/release.py <component>`
2. Review generated changelog
3. Review version bump
4. Confirm and execute
5. Verify git tag created
6. Push to remote: `git push --tags`
7. Create GitHub release (if applicable)
8. Announce in community channels

## Post-Release

- [ ] Monitor for issues
- [ ] Update documentation site
- [ ] Announce in changelog
- [ ] Close related issues/PRs
```

## Best Practices

### Commit Messages

- Use conventional commits format
- Be specific and descriptive
- Reference issue numbers (#42)
- Explain "why" not just "what"

### Versioning

- Start at 0.1.0 for new components
- Bump to 1.0.0 when API is stable
- Use pre-release versions for testing (1.0.0-beta.1)
- Never reuse version numbers

### Changelog

- Group by category (breaking, features, fixes)
- Include commit hashes for traceability
- Link to issues/PRs where relevant
- Keep entries concise and user-focused

### Release Notes

- Summarize key changes
- Highlight breaking changes prominently
- Provide upgrade/migration guidance
- Thank contributors

## References

- Requirements: `.something-wicked/wicked-feature-dev/specs/something-wicked-v2/requirements.md` (FR-005)
- Design: `.something-wicked/wicked-feature-dev/specs/something-wicked-v2/design.md` (tools/ section)
- Semantic Versioning: https://semver.org/
- Conventional Commits: https://www.conventionalcommits.org/
