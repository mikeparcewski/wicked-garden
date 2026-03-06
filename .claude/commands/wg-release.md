---
description: Manage versions and generate changelogs for the wicked-garden plugin
argument-hint: [--bump major|minor|patch] [--dry-run]
allowed-tools: Read, Write, Edit, Bash(python3:*, git:*, gh:*), Skill, Agent
---

Release the wicked-garden plugin with version management and changelog generation.

## Arguments

Parse the provided arguments: $ARGUMENTS

- **--bump [type]**: Specify version bump (major, minor, patch)
- **--dry-run**: Preview changes without applying them
- **--version [X.Y.Z]**: Set specific version
- **--no-tag**: Skip git tag creation

## Step 1: Quality Gate

Before any release, run the full quality check:

```
/wg-check --full
```

If `/wg-check --full` reports **NEEDS WORK**:

1. Review each issue identified
2. For each issue, delegate to the appropriate specialist agent to resolve it (e.g., engineering for code issues, product for description/value issues, qe for test issues)
3. After specialists resolve issues, re-run `/wg-check --full` to confirm **READY**
4. Do NOT proceed to Step 2 until the check passes

## Step 2: Version Analysis

If arguments are provided with a bump type, use them directly.

If no bump type is provided, enter interactive mode:
1. Show current version from `.claude-plugin/plugin.json`
2. Analyze commits since last release
3. Suggest version bump based on commit messages
4. Ask for confirmation before proceeding

### Semantic Versioning Rules

**Version format:** MAJOR.MINOR.PATCH

**Auto-detection from commits:**
- `BREAKING CHANGE:`, `feat!:`, `fix!:` → major bump
- `feat:`, `feature:` → minor bump
- `fix:`, `bugfix:` → patch bump
- `docs:`, `chore:`, `refactor:` → no bump (but included in changelog)

## Step 3: Release

Run the release script targeting the repo root:

```bash
python3 .claude/skills/releasing/scripts/release.py . $ARGUMENTS
```

### Release Process

1. Collect commits since last tag
2. Categorize commits by type
3. Determine version bump
4. Update version in `.claude-plugin/plugin.json`
5. Update version in `.claude-plugin/marketplace.json`
6. Generate/update `CHANGELOG.md` at repo root
7. Create git tag (unless --no-tag)
8. Create GitHub release with release notes via `gh release create`

## Step 4: Push & Verify

After the release is created:

1. Push commits and tags: `git push && git push --tags`
2. Verify the GitHub release exists:

```bash
gh release view "v${new_version}"
```

3. Show new version number and changelog entries

## Dry Run Mode

Always recommend `--dry-run` first:
```
/wg-release --dry-run
```

This shows what would change without making modifications. Dry run skips the quality gate.
