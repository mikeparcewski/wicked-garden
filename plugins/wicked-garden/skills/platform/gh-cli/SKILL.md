---
name: gh-cli
description: GitHub CLI power utilities - workflow debugging, PR management, release automation, and repo operations. Use when working with GitHub via CLI for anything beyond basic git commands.
---

# GitHub CLI Power Utilities

Intelligent wrappers and patterns for GitHub CLI that go beyond basic commands.

## When to Use

- Debugging failed GitHub Actions (get actionable errors, not walls of logs)
- Managing PRs across multiple repos
- Automating releases with proper changelogs
- Bulk operations on issues/PRs
- Repository health checks

## Prerequisites

```bash
brew install gh && gh auth login  # macOS
```

## Core Capabilities

### 1. Smart Failure Analysis

Don't wade through logs - get the actual errors.

```bash
# Get actionable error summary
python3 scripts/gh_ops.py diagnose

# Specific repo
python3 scripts/gh_ops.py diagnose --repo owner/repo

# With suggested fixes
python3 scripts/gh_ops.py diagnose --suggest-fixes
```

**Output:** Structured error summary with job timelines, extracted failures, and fix suggestions based on common patterns.

### 2. PR Operations

Bulk PR management that scales.

```bash
# List PRs needing review across your repos
python3 scripts/gh_ops.py pr-review-queue

# Merge all approved PRs (with safety checks)
python3 scripts/gh_ops.py pr-merge-ready --dry-run

# PR health check (conflicts, checks, reviews)
python3 scripts/gh_ops.py pr-status 123
```

### 3. Release Automation

Generate releases with proper changelogs.

```bash
# Create release from unreleased commits
python3 scripts/gh_ops.py release --bump minor

# Preview changelog without releasing
python3 scripts/gh_ops.py release --dry-run

# Release with custom notes
python3 scripts/gh_ops.py release --notes "Breaking: API v2"
```

### 4. Repo Health

Quick health check for repositories.

```bash
python3 scripts/gh_ops.py health
```

**Checks:** Branch protection, required reviews, CI status, security advisories, dependency alerts.

## Quick Patterns

```bash
# Watch CI and notify on completion
gh run watch && osascript -e 'display notification "CI Done"'

# Open PR for current branch
gh pr create --fill --web

# Checkout PR locally
gh pr checkout 123

# View PR diff in terminal
gh pr diff 123

# Re-run failed jobs only
gh run rerun --failed

# List your open PRs across all repos
gh search prs --author=@me --state=open
```

## Integration with Other Tools

Works well with:
- **wicked-search**: Find code patterns, then use gh to create issues
- **wicked-kanban**: Track PR status alongside tasks

## References

- `refs/gh-ops.md` - Full script documentation
- `refs/patterns.md` - Common workflow patterns
- `refs/automation.md` - CI/CD integration examples
