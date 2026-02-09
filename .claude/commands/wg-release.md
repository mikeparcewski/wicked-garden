---
description: Manage versions and generate changelogs for marketplace components
argument-hint: [component-path] [--bump major|minor|patch] [--dry-run] [--batch]
allowed-tools: Read, Write, Bash(python3:*, git:*)
---

Release a marketplace component with version management and changelog generation.

## Arguments

Parse the provided arguments: $ARGUMENTS

Expected format: `[component-path] [options]` OR `--batch [options]`

### Single Plugin Release
- **component-path**: Path to the component to release
- **--bump [type]**: Specify version bump (major, minor, patch)
- **--dry-run**: Preview changes without applying them
- **--version [X.Y.Z]**: Set specific version
- **--no-tag**: Skip git tag creation

### Batch Release
- **--batch**: Release all plugins with changes since their last tag
- **--batch --plugins p1,p2,p3**: Release specific plugins
- **--batch --bump patch**: Force bump type for all
- **--batch --dry-run**: Preview batch release

## If --batch is in arguments

Run the batch release script:

```bash
python3 .claude/skills/releasing/scripts/batch_release.py --changed $REMAINING_ARGS
```

If `--plugins` is specified, pass `--plugins` instead of `--changed`.

## If a single path is provided

Run the release script:

```bash
python3 .claude/skills/releasing/scripts/release.py $ARGUMENTS
```

## If no path or bump type is provided

Enter interactive mode:
1. What component are you releasing? (Or use `--batch` for all changed plugins)
2. Show current version from plugin.json
3. Analyze commits since last release
4. Suggest version bump based on commit messages
5. Ask for confirmation before proceeding

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
4. Update version in plugin.json
5. Update version in marketplace.json (auto-finds entry by plugin name)
6. Sync plugin to local cache (`~/.claude/plugins/cache/wicked-garden/{name}/{version}/`)
7. Generate/update CHANGELOG.md
8. Create git tag (unless --no-tag)
9. Generate release notes

## After release

1. Show new version number
2. Display changelog entries
3. Remind to push tags: `git push --tags`
4. Suggest announcing the release

## Dry Run Mode

Always recommend `--dry-run` first:
```
/wg-release path/to/component --dry-run
```

This shows what would change without making modifications.
