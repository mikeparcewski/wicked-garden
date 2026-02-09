# Common gh CLI Patterns

Quick reference for common GitHub CLI operations.

## Workflow Debugging

```bash
# Watch current run
gh run watch

# Re-run only failed jobs
gh run rerun --failed

# View logs for specific job
gh run view --log --job=build

# Cancel running workflow
gh run cancel
```

## PR Management

```bash
# Create PR with auto-fill
gh pr create --fill

# Create draft PR
gh pr create --draft

# Checkout PR locally
gh pr checkout 123

# View PR diff
gh pr diff 123

# Merge PR
gh pr merge 123 --squash --delete-branch

# Request review
gh pr edit 123 --add-reviewer @username
```

## Search

```bash
# Your open PRs
gh search prs --author=@me --state=open

# PRs needing review
gh search prs --review-requested=@me

# Recent issues
gh search issues --repo owner/name --sort=created

# Code search
gh search code "TODO" --language=python
```

## Repository

```bash
# Clone and cd
gh repo clone owner/name -- --depth=1

# Fork and clone
gh repo fork --clone

# Create from template
gh repo create new-name --template owner/template

# View repo info
gh repo view --json description,stargazerCount
```

## Issues

```bash
# Create issue
gh issue create --title "Bug" --body "Description"

# Close with comment
gh issue close 123 --comment "Fixed in #456"

# List your issues
gh issue list --assignee=@me
```

## Releases

```bash
# Create release
gh release create v1.0.0 --generate-notes

# Upload assets
gh release upload v1.0.0 ./dist/*

# Download assets
gh release download v1.0.0
```

## API

```bash
# GET request
gh api repos/:owner/:repo

# POST with data
gh api repos/:owner/:repo/issues -f title="Bug" -f body="desc"

# Paginate
gh api repos/:owner/:repo/issues --paginate

# JQ filter
gh api repos/:owner/:repo --jq '.stargazers_count'
```

## Aliases

```bash
# Create alias
gh alias set pv 'pr view'

# Use alias
gh pv 123

# List aliases
gh alias list
```
