---
description: Manage versions and generate changelogs for the wicked-garden plugin
argument-hint: [--bump major|minor|patch] [--dry-run]
allowed-tools: Read, Write, Bash(python3:*, git:*)
---

Release the wicked-garden plugin with version management and changelog generation.

## Arguments

Parse the provided arguments: $ARGUMENTS

- **--bump [type]**: Specify version bump (major, minor, patch)
- **--dry-run**: Preview changes without applying them
- **--version [X.Y.Z]**: Set specific version
- **--no-tag**: Skip git tag creation

## If arguments are provided

Run the release script targeting the repo root (the single unified plugin):

```bash
python3 .claude/skills/releasing/scripts/release.py . $ARGUMENTS
```

## If no bump type is provided

Enter interactive mode:
1. Show current version from `.claude-plugin/plugin.json`
2. Analyze commits since last release
3. Suggest version bump based on commit messages
4. Ask for confirmation before proceeding

## Semantic Versioning Rules

**Version format:** MAJOR.MINOR.PATCH

**Auto-detection from commits:**
- `BREAKING CHANGE:`, `feat!:`, `fix!:` → major bump
- `feat:`, `feature:` → minor bump
- `fix:`, `bugfix:` → patch bump
- `docs:`, `chore:`, `refactor:` → no bump (but included in changelog)

## Release Process

1. Collect commits since last tag
2. Categorize commits by type
3. Determine version bump
4. Update version in `.claude-plugin/plugin.json`
5. Update version in `.claude-plugin/marketplace.json`
6. Generate/update `CHANGELOG.md` at repo root
7. Create git tag (unless --no-tag)
8. Generate release notes (`RELEASE-{version}.md`)

## After release

1. Show new version number
2. Display changelog entries
3. Remind to push tags: `git push --tags`
4. Suggest announcing the release

## Dry Run Mode

Always recommend `--dry-run` first:
```
/wg-release --dry-run
```

This shows what would change without making modifications.
