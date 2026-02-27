# Common glab CLI Patterns

Quick reference for GitLab CLI operations.

## Pipeline Operations

```bash
# List recent pipelines
glab ci list

# View pipeline details
glab ci view <pipeline-id>

# Watch pipeline live
glab ci view --live

# View job logs
glab ci trace <job-id>

# Retry failed jobs
glab ci retry

# Cancel pipeline
glab ci delete <pipeline-id>

# Trigger manual job
glab ci run
```

## Merge Requests

```bash
# Create MR with auto-fill
glab mr create --fill

# Create draft MR
glab mr create --draft

# Checkout MR locally
glab mr checkout 123

# View MR changes
glab mr diff 123

# Approve MR
glab mr approve 123

# Merge MR
glab mr merge 123 --squash --remove-source-branch

# List open MRs
glab mr list --state=opened

# MRs assigned to me
glab mr list --assignee=@me

# MRs I need to review
glab mr list --reviewer=@me
```

## Issues

```bash
# Create issue
glab issue create --title "Bug" --description "Details"

# Close issue
glab issue close 123

# List open issues
glab issue list --state=opened

# Issues assigned to me
glab issue list --assignee=@me
```

## Releases

```bash
# List releases
glab release list

# Create release
glab release create v1.0.0 --notes "Release notes"

# Upload assets
glab release upload v1.0.0 ./dist/*
```

## Project

```bash
# Clone project
glab repo clone group/project

# Fork project
glab repo fork group/project

# View project info
glab repo view
```

## Authentication

```bash
# Login
glab auth login

# Check status
glab auth status

# List configured hosts
glab config get host
```

## API Access

```bash
# GET request
glab api projects/:id

# POST request
glab api projects/:id/issues -X POST -f title="Bug"

# With JQ filter
glab api projects/:id --jq '.name'
```
