---
name: release
description: |
  Release management and versioning toolkit for the wicked-garden plugin.
  Automates changelog generation, semantic versioning, and version bumping from git history.
  Use when preparing releases, generating changelogs, or managing plugin versions.
---

# Release Tool

Automated release management for the wicked-garden plugin.

## Purpose

Streamlines the release process:
- **Changelog generation** - Auto-generate from commit messages
- **Semantic versioning** - Intelligent version bumping (major/minor/patch)
- **Version management** - Update plugin.json, create git tags
- **Release notes** - Template-based release documentation

## Usage

### Command Line Mode

```bash
# Auto-detect version bump from commits
python3 .claude/skills/releasing/scripts/release.py .

# Specify version bump
python3 .claude/skills/releasing/scripts/release.py . --bump major
python3 .claude/skills/releasing/scripts/release.py . --bump minor
python3 .claude/skills/releasing/scripts/release.py . --bump patch

# Dry run (preview changes)
python3 .claude/skills/releasing/scripts/release.py . --dry-run

# Check if changes exist since last tag
python3 .claude/skills/releasing/scripts/batch_release.py --changed --dry-run

# Force release with bump type
python3 .claude/skills/releasing/scripts/batch_release.py --bump minor
```

### Via Dev Command

```bash
/wg-release --dry-run
/wg-release --bump minor
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

## Changelog Generation

### Commit Categorization

```markdown
# Changelog

## [1.0.0] - 2026-01-13

### Breaking Changes
- feat!: redesign cache API (#45)

### Features
- feat: add namespace isolation (#42)
- feat: add TTL support with auto-expiration (#43)

### Bug Fixes
- fix: resolve race condition in file writes (#44)

### Documentation
- docs: update README with new API examples
```

### Conventional Commits

Supports [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Scopes** (domain areas): `crew`, `smaht`, `mem`, `search`, `jam`, `kanban`, `engineering`, `product`, `platform`, `qe`, `data`, `delivery`, `agentic`, `scenarios`, `patch`, `observability`

## Release Workflow

### Step-by-Step Process

1. **Collect commits** since last release tag
2. **Categorize commits** by type (breaking, features, fixes)
3. **Determine version bump** from commit types
4. **Update** `.claude-plugin/plugin.json` version field
5. **Generate** CHANGELOG.md entries
6. **Create git tag** (e.g., `v1.3.0`)
7. **Generate** release notes (RELEASE-{version}.md)

### Change Detection

The release tool checks for changes in these directories since the last tag:

- `commands/` - Slash commands
- `agents/` - Subagents
- `skills/` - Expertise modules
- `hooks/` - Event bindings and scripts
- `scripts/` - Domain APIs
- `scenarios/` - Acceptance tests
- `.claude-plugin/` - Plugin metadata

Changes in `.claude/` (dev tools) do NOT trigger a release.

## Scripts

### release.py

Core release engine. Handles version bumping, changelog generation, and git tagging.

### batch_release.py

Wrapper that checks for changes since the last tag before releasing.

### changelog.py

Generates changelog from git history with commit categorization.

### semver.py

Semantic version parsing, comparison, and bumping utilities.

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

      - name: Release if changed
        run: python3 .claude/skills/releasing/scripts/batch_release.py --changed

      - name: Push tags
        run: git push --tags
```

## Best Practices

### Commit Messages

- Use conventional commits format
- Include domain scope: `feat(crew): add checkpoint injection`
- Reference issue numbers (#42)
- Explain "why" not just "what"

### Versioning

- Start at 0.1.0 for initial release
- Bump to 1.0.0 when API is stable
- Use pre-release versions for testing (1.0.0-beta.1)
- Never reuse version numbers

### Changelog

- Group by category (breaking, features, fixes)
- Include commit hashes for traceability
- Link to issues/PRs where relevant

## References

- Semantic Versioning: https://semver.org/
- Conventional Commits: https://www.conventionalcommits.org/
